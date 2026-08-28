"""Draw app screens in-app, from a structured spec.

UX Pilot cannot be driven from a server, so screens are generated here instead:
the model writes a spec describing each screen, and this module draws it with
the same palette and type as the proposal itself. No copy and paste, no export,
no upload.
"""
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "assets", "fonts")
SS = 6                          # supersample, downsampled 3x on the way out

INK, MUT, FAINT = (17, 20, 26), (127, 137, 152), (226, 231, 238)
BLUE, BLUEL, NAVY = (37, 99, 235), (225, 234, 253), (58, 84, 152)
GREEN, GREENL, AMBER = (104, 172, 90), (223, 240, 221), (206, 152, 62)
TINTS = [(203, 216, 232), (206, 220, 208), (219, 214, 206), (208, 212, 224),
         (214, 208, 218), (200, 214, 218)]


def _font(weight, size):
    return ImageFont.truetype(
        os.path.join(FONTS, "GlancyrStatic-%s.ttf" % weight), max(int(size*SS), 1))


class Canvas(object):
    """Coordinates are in logical points; output is 3x that."""

    def __init__(self, w, h, fill=(255, 255, 255, 255)):
        self.w, self.h = w, h
        self.im = Image.new("RGBA", (int(w*SS), int(h*SS)), fill)
        self.d = ImageDraw.Draw(self.im, "RGBA")

    def rect(self, box, r=0, fill=None, outline=None, width=1):
        b = [v*SS for v in box]
        if r:
            self.d.rounded_rectangle(b, radius=r*SS, fill=fill, outline=outline,
                                     width=max(int(width*SS), 1))
        else:
            self.d.rectangle(b, fill=fill, outline=outline,
                             width=max(int(width*SS), 1))

    def circle(self, cx, cy, r, fill=None, outline=None, width=1):
        self.d.ellipse([(cx-r)*SS, (cy-r)*SS, (cx+r)*SS, (cy+r)*SS], fill=fill,
                       outline=outline, width=max(int(width*SS), 1))

    def line(self, pts, fill, width=1):
        self.d.line([(x*SS, y*SS) for x, y in pts], fill=fill,
                    width=max(int(width*SS), 1), joint="curve")

    def tw(self, s, weight, size):
        return self.d.textlength(s or "", font=_font(weight, size))/SS

    def text(self, x, y, s, weight="Light", size=8, fill=INK, maxw=None,
             center=None):
        s = s or ""
        if maxw:
            while s and self.tw(s, weight, size) > maxw:
                s = s[:-1]
        f = _font(weight, size)
        if center is not None:
            x = center - self.tw(s, weight, size)/2
        self.d.text((x*SS, y*SS), s, font=f, fill=fill)

    def photo(self, box, tint=0, label=None):
        """A photographic-looking image block. Real photos drop in here later."""
        x0, y0, x1, y1 = box
        c = TINTS[tint % len(TINTS)]
        self.rect(box, min(6, (y1-y0)*0.12), fill=c)
        w, h = x1-x0, y1-y0
        self.d.ellipse([(x0+w*0.68)*SS, (y0+h*0.12)*SS,
                        (x0+w*0.86)*SS, (y0+h*0.34)*SS], fill=(255, 255, 255, 90))
        self.d.polygon([((x0+w*0.06)*SS, (y1-h*0.06)*SS),
                        ((x0+w*0.40)*SS, (y0+h*0.42)*SS),
                        ((x0+w*0.70)*SS, (y1-h*0.06)*SS)],
                       fill=tuple(int(v*0.88) for v in c))
        self.d.polygon([((x0+w*0.46)*SS, (y1-h*0.06)*SS),
                        ((x0+w*0.72)*SS, (y0+h*0.55)*SS),
                        ((x0+w*0.98)*SS, (y1-h*0.06)*SS)],
                       fill=tuple(int(v*0.80) for v in c))
        if label:
            self.text(x0+w*0.06, y1-h*0.26, label, "Medium", h*0.14,
                      (255, 255, 255), maxw=w*0.88)

    def out(self):
        return self.im.resize((int(self.w*3), int(self.h*3)), Image.LANCZOS)


# --------------------------------------------------------------- block types
def _header(c, b, y, w):
    h = 26
    c.rect([0, y, w, y+h], 0, fill=NAVY+(255,))
    c.text(12, y+7, b.get("title", ""), "Medium", 9.5, (255, 255, 255), maxw=w-70)
    if b.get("right"):
        c.text(0, y+9, b["right"], "Light", 7.2, (226, 233, 245),
               center=w-34)
    c.circle(w-18, y+13, 8, fill=(255, 255, 255, 60))
    return y + h + 8


def _search(c, b, y, w):
    c.rect([10, y, w-10, y+18], 8, fill=(248, 250, 252, 255),
           outline=FAINT+(255,), width=0.5)
    c.circle(23, y+9, 4, outline=MUT, width=1.2)
    c.line([(26, y+12), (29, y+15)], MUT, 1.2)
    c.text(34, y+5, b.get("text", ""), "Light", 7.4, (96, 106, 122), maxw=w-60)
    return y + 24


def _chips(c, b, y, w):
    x = 10
    for i, label in enumerate(b.get("items", [])[:5]):
        cw = c.tw(label, "Light", 7) + 14
        if x + cw > w - 8:
            break
        on = i == b.get("active", 0)
        c.rect([x, y, x+cw, y+15], 7,
               fill=BLUE+(255,) if on else (245, 247, 250, 255),
               outline=None if on else FAINT+(255,), width=0.5)
        c.text(x+7, y+3.5, label, "Light", 7,
               (255, 255, 255) if on else (104, 114, 130))
        x += cw + 5
    return y + 22


def _hero(c, b, y, w):
    h = b.get("height", 96)
    c.photo([10, y, w-10, y+h], b.get("tint", 0), b.get("caption"))
    y += h + 6
    if b.get("title"):
        c.text(11, y, b["title"], "Medium", 9.2, INK, maxw=w-22)
        y += 13
    if b.get("subtitle"):
        c.text(11, y, b["subtitle"], "Light", 7.2, MUT, maxw=w-22)
        y += 11
    return y + 4


def _tiles(c, b, y, w):
    items = b.get("items", [])[:6]
    cols = b.get("cols", 2)
    tw = (w - 20 - (cols-1)*6) / max(cols, 1)
    th = tw * b.get("ratio", 0.72)
    for i, it in enumerate(items):
        col, row = i % cols, i // cols
        x = 10 + col*(tw+6)
        ty = y + row*(th+22)
        c.photo([x, ty, x+tw, ty+th], i)
        if isinstance(it, dict):
            c.text(x+1, ty+th+2, it.get("title", ""), "Medium", 7.4, INK, maxw=tw)
            c.text(x+1, ty+th+11, it.get("sub", ""), "Light", 6.2, MUT, maxw=tw)
        else:
            c.text(x+1, ty+th+2, str(it), "Medium", 7.4, INK, maxw=tw)
    rows = (len(items) + cols - 1)//max(cols, 1)
    return y + rows*(th+22) + 4


PILLS = {"green": (GREENL, (62, 118, 58)), "blue": (BLUEL, BLUE),
         "amber": ((250, 240, 216), (150, 110, 40)), "grey": ((238, 241, 246), MUT)}


def _list(c, b, y, w):
    for i, row in enumerate(b.get("items", [])[:6]):
        h = 34
        c.rect([10, y, w-10, y+h], 6, fill=(250, 251, 253, 255),
               outline=FAINT+(255,), width=0.4)
        tx = 16
        if b.get("thumb", True):
            c.photo([15, y+5, 15+24, y+h-5], i)
            tx = 45
        c.text(tx, y+7, row.get("title", ""), "Medium", 7.6, INK, maxw=w-tx-60)
        c.text(tx, y+18, row.get("sub", ""), "Light", 6.4, MUT, maxw=w-tx-60)
        if row.get("pill"):
            bg, fg = PILLS.get(row.get("tone", "blue"), PILLS["blue"])
            pw = c.tw(row["pill"], "Light", 6.2) + 10
            c.rect([w-14-pw, y+11, w-14, y+23], 6, fill=bg+(255,))
            c.text(w-9-pw, y+13.5, row["pill"], "Light", 6.2, fg)
        y += h + 5
    return y + 2


def _kpis(c, b, y, w):
    items = b.get("items", [])[:4]
    n = max(len(items), 1)
    cw = (w - 20 - (n-1)*5)/n
    for i, k in enumerate(items):
        x = 10 + i*(cw+5)
        c.rect([x, y, x+cw, y+38], 6, fill=(250, 251, 253, 255),
               outline=FAINT+(255,), width=0.4)
        c.text(x+6, y+5, k.get("label", ""), "Light", 5.8, MUT, maxw=cw-10)
        c.text(x+6, y+14, k.get("value", ""), "Medium", 10, INK, maxw=cw-10)
        c.text(x+6, y+28, k.get("delta", ""), "Light", 5.8, GREEN, maxw=cw-10)
    return y + 46


def _chart(c, b, y, w):
    h = b.get("height", 78)
    c.rect([10, y, w-10, y+h], 6, fill=(250, 251, 253, 255),
           outline=FAINT+(255,), width=0.4)
    c.text(16, y+6, b.get("title", ""), "Medium", 7.6, INK)
    vals = b.get("values") or [.2, .35, .3, .5, .45, .62, .58, .74, .7, .88]
    x0, y0, pw, ph = 18, y+22, w-38, h-32
    for i in range(4):
        c.line([(x0, y0+ph*i/3), (x0+pw, y0+ph*i/3)], (240, 243, 247), 0.5)
    pts = [(x0 + pw*i/max(len(vals)-1, 1), y0+ph - ph*v) for i, v in enumerate(vals)]
    c.line(pts, BLUE, 1.4)
    return y + h + 6


def _split(c, b, y, w):
    h = b.get("height", 92)
    c.photo([10, y, w-10, y+h], b.get("tint", 0))
    c.d.rectangle([10*SS, y*SS, (w/2)*SS, (y+h)*SS], fill=(18, 30, 50, 70))
    c.line([(w/2, y), (w/2, y+h)], (255, 255, 255), 1.2)
    c.circle(w/2, y+h/2, 5, fill=(255, 255, 255, 255))
    c.text(16, y+8, b.get("left_label", ""), "Medium", 5.6, (235, 240, 246))
    c.text(16, y+16, b.get("left_value", ""), "Medium", 9, (255, 255, 255))
    c.text(0, y+8, b.get("right_label", ""), "Medium", 5.6, (235, 240, 246),
           center=w*0.74)
    c.text(0, y+16, b.get("right_value", ""), "Medium", 9, (255, 255, 255),
           center=w*0.74)
    return y + h + 8


def _fields(c, b, y, w):
    for f in b.get("items", [])[:4]:
        c.text(12, y, f.get("label", ""), "Light", 6.4, MUT)
        c.rect([10, y+9, w-10, y+25], 6, fill=(249, 250, 253, 255),
               outline=FAINT+(255,), width=0.5)
        c.text(16, y+13.5, f.get("value", ""), "Light", 7.2, (98, 108, 124),
               maxw=w-32)
        y += 32
    return y + 2


def _button(c, b, y, w):
    tone = b.get("tone", "blue")
    fill = GREEN if tone == "green" else BLUE
    c.rect([10, y, w-10, y+20], 8, fill=fill+(255,))
    c.text(0, y+5.5, b.get("label", ""), "Medium", 8.2, (255, 255, 255),
           center=w/2)
    return y + 28


def _social(c, b, y, w):
    c.line([(14, y+6), (w*0.32, y+6)], FAINT, 0.5)
    c.text(0, y+1, b.get("label", "or continue with"), "Light", 6.4, MUT,
           center=w/2)
    c.line([(w*0.68, y+6), (w-14, y+6)], FAINT, 0.5)
    y += 14
    for i, mark in enumerate(["G", "", "f"]):
        cx = w/2 + (i-1)*w*0.24
        c.rect([cx-w*0.09, y, cx+w*0.09, y+22], 6, fill=(255, 255, 255, 255),
               outline=FAINT+(255,), width=0.5)
        if mark:
            c.text(0, y+5, mark, "Medium", 10,
                   (66, 120, 190) if mark == "G" else (58, 88, 168), center=cx)
        else:
            c.circle(cx, y+11, 5, fill=(32, 34, 38))
    return y + 30


def _nav(c, b, y, w, h):
    items = b.get("items", ["Home", "Search", "Profile"])[:4]
    c.rect([8, h-32, w-8, h-8], 8, fill=(252, 253, 255, 255),
           outline=FAINT+(255,), width=0.5)
    for i, label in enumerate(items):
        cx = 8 + (w-16)*(i+0.5)/len(items)
        on = i == b.get("active", 0)
        if on:
            c.rect([cx-11, h-27, cx+11, h-14], 5, fill=BLUEL+(255,))
        c.circle(cx, h-22.5, 3.6, outline=BLUE if on else MUT, width=1.2)
        c.text(0, h-14, label, "Light", 5.4, BLUE if on else MUT, center=cx)
    return y


BLOCKS = {"header": _header, "search": _search, "chips": _chips, "hero": _hero,
          "tiles": _tiles, "list": _list, "kpis": _kpis, "chart": _chart,
          "split": _split, "fields": _fields, "button": _button,
          "social": _social}

SIZES = {"phone": (150, 320), "tablet": (400, 280), "web": (460, 300)}


def render_screen(spec, device=None):
    """spec: {"device": "phone|tablet|web", "blocks": [...]} -> PIL image."""
    device = device or spec.get("device", "phone")
    w, h = SIZES.get(device, SIZES["phone"])
    c = Canvas(w, h, (255, 255, 255, 255))
    y = 0
    nav = None
    for b in spec.get("blocks", []):
        kind = b.get("type")
        if kind == "nav":
            nav = b
            continue
        fn = BLOCKS.get(kind)
        if not fn:
            continue
        if y > h - 30:
            break
        y = fn(c, b, y, w)
    if nav:
        _nav(c, nav, y, w, h)
    return c.out()


def save_screen(spec, path, device=None):
    render_screen(spec, device).convert("RGB").save(path, quality=92)
    return path
