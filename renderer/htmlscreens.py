"""Fast, high-definition screens without v0.

v0 builds a React project and boots a sandbox for every request, which is why a
set of screens took half an hour. Claude can write the same interface as plain
HTML in one call, and every screenshot provider will render raw HTML directly.
That turns 30 minutes into roughly a minute, with no v0 credits at all, and the
type stays crisp because it is real text rather than a generated image.
"""
import base64
import hashlib
import io
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from .extract import _call, _client
from .v0screens import SHOT_PROVIDER, SHOT_KEY, VIEWPORT, HTTP_TIMEOUT

MODEL = os.environ.get("PROPOSAL_SCREEN_MODEL",
                       os.environ.get("PROPOSAL_MODEL", "claude-sonnet-5"))
GAP = 48                       # px between screens in the strip
MAX_TOKENS = int(os.environ.get("PROPOSAL_SCREEN_TOKENS", "16000"))

SYSTEM = """You write the HTML for a row of app screens, to be photographed and
placed in a sales proposal.

Return ONE complete HTML document. Inline every style in a <style> block. No
JavaScript, no external CSS, no fonts from the network, no comments.

House style: light UI, generous white space, 12px rounded cards, soft shadows
(0 1px 2px rgba(16,24,40,.06), 0 8px 24px rgba(16,24,40,.06)), system sans
(-apple-system, "Segoe UI", Roboto, sans-serif), accent blue #2563EB, deep navy
header #3A5498, success green #68AC5A, text #11141A, muted #6B7280, hairline
#E7EBF2, page background #F6F8FB.

Photography: where a screen needs a photo, write
<img src="PHOTO:two or three words describing the subject" alt="...">
for example PHOTO:modern kitchen interior, PHOTO:smiling woman portrait,
PHOTO:suburban house exterior. Do not invent an image URL: the server turns
PHOTO: into a real photograph before the page is rendered. Always give the img
a width, a height, object-fit:cover and a rounded corner. Never use a grey
placeholder block.

Layout, follow exactly:
- <body> is display:flex, flex-direction:row, align-items:flex-start,
  gap:GAPpx, padding:GAPpx, margin:0, background:#FFFFFF, width:TOTALpx.
- Each screen is a div of exactly the width and height given, flex:0 0 auto,
  overflow:hidden, border:1px solid #E7EBF2, border-radius:12px,
  background:#FFFFFF, and box-sizing:border-box.
- Fill each screen: a header, then the content described, then a bottom bar on
  phone screens. No empty space at the bottom.
- Nothing outside the screens. No page title, no captions, no labels.

The content of each screen must be exactly what is described, using the
client's own words and realistic sample data from their business."""


def configured():
    return SHOT_PROVIDER != "none" and bool(SHOT_KEY)


def build_prompt(slots, project_name):
    total = sum(VIEWPORT.get(s.get("device", "phone"), VIEWPORT["phone"])[0]
                for s in slots) + GAP * (len(slots) + 1)
    parts = []
    for i, slot in enumerate(slots):
        w, h = VIEWPORT.get(slot.get("device", "phone"), VIEWPORT["phone"])
        points = "\n".join("   - %s" % p for p in slot.get("points", []) if p)
        parts.append('SCREEN %d — "%s", exactly %dpx by %dpx (%s)\n%s'
                     % (i + 1, slot.get("title", ""), w, h,
                        slot.get("device", "phone"), points))
    return ("App: %s\nGAP = %d\nTOTAL = %d\n\n%s"
            % (project_name, GAP, total, "\n\n".join(parts)))


UNSPLASH_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "")
PHOTO_RE = re.compile(r'src=["\']PHOTO:([^"\']{2,80})["\']', re.I)
_PHOTO_CACHE = {}


def _unsplash(subject):
    """Ask Unsplash for a photo of this subject. Needs a free access key."""
    q = urllib.parse.urlencode({"query": subject, "per_page": 1,
                                "orientation": "landscape",
                                "content_filter": "high"})
    req = urllib.request.Request(
        "https://api.unsplash.com/search/photos?%s" % q,
        headers={"authorization": "Client-ID %s" % UNSPLASH_KEY,
                 "accept-version": "v1"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode())
    results = data.get("results") or []
    if not results:
        return None
    urls = results[0].get("urls") or {}
    return urls.get("small") or urls.get("regular")


def _fallback(subject):
    """No key, or nothing found: a real photograph chosen deterministically,
    so the same subject always gets the same picture."""
    seed = hashlib.sha1(subject.lower().encode()).hexdigest()[:12]
    return "https://picsum.photos/seed/%s/800/600" % seed


def resolve_photos(html):
    """Replace every PHOTO: marker with a URL that actually loads."""
    def swap(match):
        subject = match.group(1).strip()
        if subject not in _PHOTO_CACHE:
            url = None
            if UNSPLASH_KEY:
                try:
                    url = _unsplash(subject)
                except Exception:                             # noqa: BLE001
                    url = None
            _PHOTO_CACHE[subject] = url or _fallback(subject)
        return 'src="%s"' % _PHOTO_CACHE[subject]
    html, n = PHOTO_RE.subn(swap, html)
    # anything that still points at a guessed Unsplash id is replaced too
    html = re.sub(r'src=["\']https://images\.unsplash\.com/[^"\']*["\']',
                  lambda m: 'src="%s"' % _fallback(m.group(0)), html)
    return html, n


def make_html(slots, project_name, client=None):
    system = SYSTEM.replace("GAPpx", "%dpx" % GAP).replace("TOTALpx", "%dpx" %
        (sum(VIEWPORT.get(s.get("device", "phone"), VIEWPORT["phone"])[0]
             for s in slots) + GAP * (len(slots) + 1)))
    msg = _client(client).messages.create(
        model=MODEL, max_tokens=MAX_TOKENS, system=system,
        messages=[{"role": "user",
                   "content": build_prompt(slots, project_name)}])
    try:
        from .usage import record_model
        u = getattr(msg, "usage", None)
        record_model(MODEL, "screen html", getattr(u, "input_tokens", 0) or 0,
                     getattr(u, "output_tokens", 0) or 0)
    except Exception:                                         # noqa: BLE001
        pass
    text = "".join(b.text for b in msg.content if b.type == "text")
    if getattr(msg, "stop_reason", None) == "max_tokens":
        raise RuntimeError("The screen HTML was cut off at %d tokens. Raise "
                           "PROPOSAL_SCREEN_TOKENS or generate fewer screens "
                           "at once." % MAX_TOKENS)
    return _extract_html(text)


def _extract_html(text):
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n", "", text)
    text = re.sub(r"\n```$", "", text)
    start = text.lower().find("<!doctype")
    if start < 0:
        start = text.lower().find("<html")
    if start < 0:
        raise RuntimeError("The model did not return an HTML document. It "
                           "began: %s" % text[:200].replace("\n", " "))
    return text[start:]


def shoot_html(html, width, height):
    """Every provider will render raw HTML, so nothing has to be hosted."""
    w, h = min(int(width), 3840), min(int(height), 2160)
    if SHOT_PROVIDER == "screenshotone":
        body = {"access_key": SHOT_KEY, "html": html, "viewport_width": w,
                "viewport_height": h, "device_scale_factor": 2, "format": "png",
                "full_page": True, "delay": 5}
        req = urllib.request.Request(
            "https://api.screenshotone.com/take", method="POST",
            data=json.dumps(body).encode(),
            headers={"content-type": "application/json"})
    elif SHOT_PROVIDER == "urlbox":
        body = {"html": html, "width": w, "height": h, "retina": True,
                "format": "png", "full_page": True, "delay": 5000}
        req = urllib.request.Request(
            "https://api.urlbox.com/v1/render/sync", method="POST",
            data=json.dumps(body).encode(),
            headers={"content-type": "application/json",
                     "authorization": "Bearer %s" % SHOT_KEY})
    else:
        body = {"html": html, "options": {"type": "png", "fullPage": True},
                "viewport": {"width": w, "height": h, "deviceScaleFactor": 2},
                "gotoOptions": {"waitUntil": "networkidle0"},
                "waitForTimeout": 3000}
        req = urllib.request.Request(
            "https://production-sfo.browserless.io/screenshot?token=%s" % SHOT_KEY,
            method="POST", data=json.dumps(body).encode(),
            headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            return r.read()
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode()[:300]
        except Exception:                                     # noqa: BLE001
            pass
        raise RuntimeError("The screenshot service returned HTTP %s. %s"
                           % (exc.code, detail))


def slice_strip(png, slots):
    """Cut the strip into one image per screen at the known offsets."""
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGB")
    widths = [VIEWPORT.get(s.get("device", "phone"), VIEWPORT["phone"])[0]
              for s in slots]
    heights = [VIEWPORT.get(s.get("device", "phone"), VIEWPORT["phone"])[1]
               for s in slots]
    planned = sum(widths) + GAP * (len(slots) + 1)
    scale = im.width / float(planned)
    out, x = [], GAP * scale
    for w, h in zip(widths, heights):
        bottom = min((GAP + h) * scale, im.height)
        crop = im.crop((int(round(x)), int(round(GAP * scale)),
                        int(round(x + w * scale)), int(round(bottom))))
        buf = io.BytesIO()
        crop.save(buf, format="PNG", optimize=True)
        out.append(buf.getvalue())
        x += (w + GAP) * scale
    return out


def build(slots, project_name, client=None):
    """All screens, start to finish. One model call plus one screenshot."""
    if not configured():
        raise RuntimeError("Fast screens need SCREENSHOT_PROVIDER and "
                           "SCREENSHOT_API_KEY set on the server.")
    html = make_html(slots, project_name, client)
    html, photos = resolve_photos(html)
    total = sum(VIEWPORT.get(s.get("device", "phone"), VIEWPORT["phone"])[0]
                for s in slots) + GAP * (len(slots) + 1)
    tall = max(VIEWPORT.get(s.get("device", "phone"), VIEWPORT["phone"])[1]
               for s in slots) + GAP * 2
    png = shoot_html(html, total, tall)
    try:
        from .usage import record_units
        record_units("screenshot", SHOT_PROVIDER, 1, "screen strip")
    except Exception:                                         # noqa: BLE001
        pass
    if len(png) < 6000:
        raise RuntimeError("The rendered strip came back almost empty.")
    return slice_strip(png, slots), html
