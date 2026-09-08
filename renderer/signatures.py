"""Signatures held against a user account.

Each person sets theirs up once: drawn with a mouse, typed in a signature face,
or uploaded from a photo of their real one. It is then applied to a proposal in
one click, before the document goes to the client.
"""
import base64
import io

from .sql import connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS signatures (
  user_id TEXT PRIMARY KEY, kind TEXT, data TEXT, name TEXT, role TEXT,
  width INTEGER, height INTEGER, at TEXT);
"""

MAX_BYTES = 2 * 1024 * 1024
KINDS = ("drawn", "typed", "uploaded")
_READY = [False]


def _conn():
    c = connect()
    if not _READY[0]:
        c.executescript(SCHEMA)
        c.commit()
        _READY[0] = True
    return c


def _now():
    from .db import now
    return now()


def save(user_id, kind, data_url, name="", role=""):
    """Keep one signature per person. Setting a new one replaces the old."""
    if kind not in KINDS:
        raise ValueError("A signature is drawn, typed or uploaded.")
    raw = (data_url or "").partition(",")[2]
    try:
        blob = base64.b64decode(raw)
    except Exception:                                         # noqa: BLE001
        raise ValueError("That signature image could not be read.")
    if not blob:
        raise ValueError("The signature was empty.")
    if len(blob) > MAX_BYTES:
        raise ValueError("That image is larger than 2 MB.")

    from PIL import Image
    im = Image.open(io.BytesIO(blob))
    im = _trim(im.convert("RGBA"))
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    clean = base64.b64encode(buf.getvalue()).decode()

    with _conn() as c:
        c.execute("DELETE FROM signatures WHERE user_id=?", (user_id,))
        c.execute("INSERT INTO signatures (user_id,kind,data,name,role,width,"
                  "height,at) VALUES (?,?,?,?,?,?,?,?)",
                  (user_id, kind, clean, name, role, im.width, im.height,
                   _now()))
    return {"kind": kind, "width": im.width, "height": im.height,
            "name": name, "role": role}


def _trim(im):
    """Crop the empty space around a drawn signature so it sits on the line."""
    alpha = im.split()[-1]
    box = alpha.getbbox()
    if box:
        im = im.crop(box)
    if im.width > 1200:
        ratio = 1200.0 / im.width
        im = im.resize((1200, max(int(im.height * ratio), 1)))
    return im


def get(user_id):
    with _conn() as c:
        row = c.execute("SELECT * FROM signatures WHERE user_id=?",
                        (user_id,)).fetchone()
    return dict(row) if row else None


def as_data_url(user_id):
    row = get(user_id)
    if not row:
        return None
    return "data:image/png;base64," + row["data"]


def to_file(user_id, folder):
    """The renderer works with file paths."""
    import os
    row = get(user_id)
    if not row:
        return None
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "sig_%s.png" % user_id)
    with open(path, "wb") as fh:
        fh.write(base64.b64decode(row["data"]))
    return path


def delete(user_id):
    with _conn() as c:
        c.execute("DELETE FROM signatures WHERE user_id=?", (user_id,))


def typed_image(text, face="cursive", size=120):
    """Render a typed name as a signature. Kept server side so every user's
    typed signature looks the same wherever they set it up."""
    from PIL import Image, ImageDraw, ImageFont
    import glob
    import os
    candidates = sorted(glob.glob(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", "fonts", "*.ttf")))
    font = None
    for path in candidates:
        if "light" in path.lower() or "regular" in path.lower():
            try:
                font = ImageFont.truetype(path, size)
                break
            except Exception:                                 # noqa: BLE001
                continue
    if font is None:
        font = ImageFont.load_default()
    pad = 24
    tmp = Image.new("RGBA", (10, 10))
    box = ImageDraw.Draw(tmp).textbbox((0, 0), text, font=font)
    im = Image.new("RGBA", (box[2] - box[0] + pad * 2,
                            box[3] - box[1] + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad - box[0], pad - box[1]), text, font=font,
                            fill=(18, 21, 28, 255))
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
