"""Shared drawing toolkit. Layout lives in code; content only ever arrives as data."""
import os
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLATES = os.path.join(ROOT, "assets", "plates")
FONTS = os.path.join(ROOT, "assets", "fonts")

W, H = 595.2, 841.92          # A4 in points
INK = (7/255,)*3
GREY = (0.36, 0.40, 0.45)
BODY = (0.22, 0.26, 0.32)
BLUE = (37/255, 99/255, 235/255)
NAVY = (68/255, 96/255, 169/255)
GREEN = (0.41, 0.66, 0.36)
LINE = (0.88, 0.90, 0.94)

_registered = False


def register_fonts():
    global _registered
    if _registered:
        return
    for name, weight in [("G-Light", "Light"), ("G-Reg", "Regular"),
                         ("G-Med", "Medium"), ("G-Semi", "SemiBold"),
                         ("G-XLight", "ExtraLight")]:
        pdfmetrics.registerFont(TTFont(name, os.path.join(
            FONTS, "GlancyrStatic-%s.ttf" % weight)))
    _registered = True


def plate(canvas, page):
    canvas.drawImage(os.path.join(PLATES, "page%d.jpg" % page), 0, 0,
                     width=W, height=H)


def as_text(value):
    """Layout code should never crash on an unexpected type."""
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return " ".join(as_text(v) for v in value if v is not None)
    return str(value)


def sw(text, font, size):
    return pdfmetrics.stringWidth(as_text(text), font, size)


def wrap(text, font, size, maxw):
    out, cur = [], ""
    for word in as_text(text).split():
        t = (cur + " " + word).strip()
        if sw(t, font, size) <= maxw:
            cur = t
        else:
            out.append(cur)
            cur = word
    if cur:
        out.append(cur)
    return out


def fit_one_line(text, font, size, maxw, floor=8.0, step=0.2):
    """Shrink until the string fits on a single line."""
    while sw(text, font, size) > maxw and size > floor:
        size -= step
    return size


def draw_lines(c, lines, x, y0, lead, font, size, colour=INK, path=None,
               maxw=None):
    c.setFont(font, size)
    c.setFillColorRGB(*colour)
    for i, ln in enumerate(lines):
        c.drawString(x, y0 - i*lead, as_text(ln))
    n = max(len(lines), 1)
    if path:
        width = maxw or max([sw(l, font, size) for l in lines] or [40])
        map_field(path, x, y0, width, (n-1)*(lead or size) + size*1.25,
                  size, font)
    return y0 - len(lines)*lead


def flow(c, items, x, y0, size, maxw, lead, gap, font="G-Light",
         bullet_dx=-4.2, colour=INK):
    """Lay out (is_bullet, text) items with even spacing. Returns the final y."""
    y = y0
    for bullet, text in items:
        for j, ln in enumerate(wrap(text, font, size, maxw)):
            if bullet and j == 0:
                c.setFillColorRGB(*colour)
                c.circle(x + bullet_dx, y + size*0.30, size*0.105,
                         stroke=0, fill=1)
            c.setFillColorRGB(*colour)
            c.setFont(font, size)
            c.drawString(x, y, ln)
            y -= lead
        y -= gap
    return y


def dotted(c, x, y, parts, font, size, colour=GREY, sep="  \u00b7  "):
    """Glancyr has no middle dot, so that one glyph is set in Helvetica."""
    for i, part in enumerate(parts):
        if i:
            c.setFont("Helvetica", size*0.86)
            c.setFillColorRGB(*colour)
            c.drawString(x, y, sep)
            x += sw(sep, "Helvetica", size*0.86)
        c.setFont(font, size)
        c.setFillColorRGB(*colour)
        c.drawString(x, y, part)
        x += sw(part, font, size)
    return x


def eyebrow(c, x, y, text, size, colour=GREY):
    dotted(c, x, y, (text or "").split(" \u00b7 "), "G-Light", size, colour)


def headline(c, x, ys, lines, size, colour=INK):
    c.setFillColorRGB(*colour)
    c.setFont("G-Med", size)
    for ln, y in zip(lines, ys):
        c.drawString(x, y, ln)


def soft_panel(c, x, y, w, h, r=10, fill=(1, 1, 1), shadow=0.09):
    c.saveState()
    c.setFillColorRGB(0.38, 0.44, 0.56, alpha=shadow)
    c.roundRect(x + 1.3, y - 2.8, w, h, r, stroke=0, fill=1)
    c.setFillAlpha(1)
    c.setFillColorRGB(*fill)
    c.roundRect(x, y, w, h, r, stroke=0, fill=1)
    c.restoreState()


def tile(c, cx, cy, s=17.5, fill=(0.985, 0.99, 0.997)):
    c.saveState()
    c.setFillColorRGB(0.42, 0.48, 0.60, alpha=0.13)
    c.roundRect(cx - s + 1, cy - s - 2.5, 2*s, 2*s, s*0.44, stroke=0, fill=1)
    c.setFillAlpha(1)
    c.setFillColorRGB(*fill)
    c.roundRect(cx - s, cy - s, 2*s, 2*s, s*0.44, stroke=0, fill=1)
    c.restoreState()


def place_image(c, path, x, y, w, h, radius=None):
    if not path or not os.path.exists(path):
        placeholder(c, x, y, w, h)
        return
    if radius:
        c.saveState()
        p = c.beginPath()
        p.roundRect(x, y, w, h, radius)
        c.clipPath(p, stroke=0, fill=0)
        c.drawImage(path, x, y, w, h, mask="auto")
        c.restoreState()
    else:
        c.drawImage(path, x, y, w, h, mask="auto")


def placeholder(c, x, y, w, h):
    """Marks a missing UI screen so a draft still renders and reviews cleanly."""
    c.saveState()
    c.setFillColorRGB(0.93, 0.945, 0.965)
    c.setStrokeColorRGB(0.78, 0.82, 0.88)
    c.setDash(3, 3)
    c.setLineWidth(0.8)
    c.roundRect(x, y, w, h, 8, stroke=1, fill=1)
    c.setDash()
    c.setFillColorRGB(0.50, 0.55, 0.62)
    c.setFont("G-Light", min(8.0, w*0.09))
    c.drawCentredString(x + w/2, y + h/2 - 3, "UI screen pending")
    c.restoreState()


def fit_box(img_w, img_h, x0, y0, w, h, anchor="right"):
    """Aspect-preserving fit inside a slot; nothing is ever stretched."""
    ar = img_w / float(img_h)
    fw, fh = h*ar, h
    if fw > w:
        fw, fh = w, w/ar
    fx = x0 + (w - fw if anchor == "right" else (w - fw)/2)
    return fx, y0 + (h - fh)/2, fw, fh


# ---------------------------------------------------------------- design QA
# Layout defects that only appear with real client copy: a headline wider than
# the page, body text longer than its card, an empty card slot. Each is handled
# here rather than left for someone to spot in a PDF.

QA = []
TEXTMAP = []          # {"page","path","x","y","w","h","size","font","align"}
_PAGE = [0]


def qa_reset():
    del QA[:]
    del TEXTMAP[:]
    _PAGE[0] = 0


def set_page(n):
    _PAGE[0] = n


def map_field(path, x, y, w, h, size=10, font="G-Light", align="left"):
    """Record a click target for the editor overlay. y is the text baseline."""
    if not path:
        return
    TEXTMAP.append({"page": _PAGE[0], "path": path, "x": round(x, 1),
                    "y": round(y, 1), "w": round(w, 1), "h": round(h, 1),
                    "size": round(size, 2), "font": font, "align": align})


def qa_note(page, kind, detail):
    QA.append({"page": page, "kind": kind, "detail": detail})


def fit_block(text, font, size, maxw, max_lines, floor=6.0, step=0.25):
    """Shrink until the text fits in max_lines, then clip and report."""
    s = size
    while s > floor:
        lines = wrap(text, font, s, maxw)
        if len(lines) <= max_lines:
            return lines, s
        s -= step
    lines = wrap(text, font, floor, maxw)
    return lines[:max_lines], floor


def draw_block(c, text, x, y, lead, font, size, maxw, max_lines,
               colour=INK, page=None, label=""):
    lines, used = fit_block(text, font, size, maxw, max_lines)
    if len(wrap(text, font, used, maxw)) > max_lines and page:
        qa_note(page, "clipped", "%s: text is longer than its box" % label)
    draw_lines(c, lines, x, y, lead, font, used, colour)
    return used


def fit_headline(c, x, ys, lines, size, maxw, colour=INK, page=None):
    """Never let a headline run off the page."""
    for ln in lines:
        size = fit_one_line(as_text(ln), "G-Med", size, maxw, floor=size*0.55)
    headline(c, x, ys, [as_text(l) for l in lines], size, colour)
    return size


def device_frame(c, x, y, w, h, r=14):
    c.saveState()
    c.setFillColorRGB(0.30, 0.34, 0.40, alpha=0.18)
    c.roundRect(x+3, y-6, w, h, r, stroke=0, fill=1)
    c.setFillAlpha(1)
    c.setFillColorRGB(0.18, 0.20, 0.23)
    c.roundRect(x, y, w, h, r, stroke=0, fill=1)
    c.restoreState()


def device_with_screen(c, path, x, y, w, h, r=14, inset=7):
    device_frame(c, x, y, w, h, r)
    if path and os.path.exists(path):
        from PIL import Image
        im = Image.open(path)
        fx, fy, fw, fh = fit_box(im.width, im.height, x+inset, y+inset,
                                 w-2*inset, h-2*inset, anchor="center")
        place_image(c, path, fx, fy, fw, fh, radius=r-4)
    else:
        placeholder(c, x+inset, y+inset, w-2*inset, h-2*inset)
