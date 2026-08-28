"""Repairing the artwork itself.

A comment like "this part of the background looks blurred" is a design problem,
not a content one. The plate is a raster, so the fix is to rebuild the marked
rectangle from the page's own colours: sample clean rows above and below, blend
across, and feather the seam. Patched plates are cached, so a page is only
rebuilt when its patches change.
"""
import hashlib
import os
import tempfile

from .kit import PLATES, W, H

CACHE = os.path.join(tempfile.gettempdir(), "proposal_patches")
S = 300 / 72.0

MODES = ("clean", "smooth", "lighten")


def _key(page, patches):
    raw = repr((page, [(round(p.get("x", 0), 1), round(p.get("y", 0), 1),
                        round(p.get("w", 0), 1), round(p.get("h", 0), 1),
                        p.get("mode", "clean")) for p in patches]))
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def plate_path(page, patches):
    """The plate for this page with the requested repairs applied."""
    base = os.path.join(PLATES, "page%s.jpg" % page)
    if not patches or not os.path.exists(base):
        return base
    os.makedirs(CACHE, exist_ok=True)
    out = os.path.join(CACHE, "p%s_%s.jpg" % (page, _key(page, patches)))
    if os.path.exists(out):
        return out
    _build(base, out, patches)
    return out


def _build(base, out, patches):
    import numpy as np
    from PIL import Image, ImageFilter

    im = Image.open(base).convert("RGB")
    if im.size != (int(W * S), int(H * S)):
        im = im.resize((int(W * S), int(H * S)), Image.LANCZOS)
    a = np.asarray(im).astype(float)
    Hp, Wp, _ = a.shape

    for p in patches:
        mode = p.get("mode", "clean")
        # regions arrive in PDF points with a bottom-left origin
        x0 = max(int(p.get("x", 0) * S), 0)
        x1 = min(int((p.get("x", 0) + p.get("w", 0)) * S), Wp)
        y_top = H - p.get("y", 0) - p.get("h", 0)
        j0 = max(int(y_top * S), 0)
        j1 = min(int((y_top + p.get("h", 0)) * S), Hp)
        if x1 - x0 < 4 or j1 - j0 < 4:
            continue

        if mode == "smooth":
            band = im.crop((x0, j0, x1, j1)).filter(ImageFilter.GaussianBlur(30))
            a[j0:j1, x0:x1] = np.asarray(band).astype(float)
        else:
            pad = int(14 * S)
            top = a[max(j0 - pad, 0):j0, x0:x1]
            bot = a[j1:min(j1 + pad, Hp), x0:x1]
            if not len(top):
                top = a[j0:j0 + 2, x0:x1]
            if not len(bot):
                bot = a[j1 - 2:j1, x0:x1]
            top, bot = top.mean(0), bot.mean(0)
            t = np.linspace(0, 1, j1 - j0)[:, None, None]
            filled = top[None] * (1 - t) + bot[None] * t
            if mode == "lighten":
                filled = filled * 0.35 + 255 * 0.65
            a[j0:j1, x0:x1] = filled

    res = Image.fromarray(np.clip(a, 0, 255).astype("uint8"))

    # feather every seam so a repair does not read as a rectangle
    for p in patches:
        pad = int(20 * S)
        x0 = max(int(p.get("x", 0) * S) - pad, 0)
        x1 = min(int((p.get("x", 0) + p.get("w", 0)) * S) + pad, Wp)
        y_top = H - p.get("y", 0) - p.get("h", 0)
        j0 = max(int(y_top * S) - pad, 0)
        j1 = min(int((y_top + p.get("h", 0)) * S) + pad, Hp)
        if x1 - x0 < 8 or j1 - j0 < 8:
            continue
        box = (x0, j0, x1, j1)
        blurred = res.crop(box).filter(ImageFilter.GaussianBlur(11))
        mask = Image.new("L", (x1 - x0, j1 - j0), 255)
        from PIL import ImageDraw
        ImageDraw.Draw(mask).rectangle(
            [pad, pad, (x1 - x0) - pad, (j1 - j0) - pad], fill=0)
        mask = mask.filter(ImageFilter.GaussianBlur(pad * 0.6))
        res.paste(Image.composite(blurred, res.crop(box), mask), box)

    res.save(out, quality=88, optimize=True)
    return out


def for_page(data, page):
    """The patches recorded against this page, if any."""
    return [p for p in (data.get("patches") or [])
            if str(p.get("page")) == str(page)]
