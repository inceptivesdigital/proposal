"""Repairing the artwork itself.

A comment like "this part of the background looks blurred" is a design problem,
not a content one. The plate is a raster, so the fix is to rebuild the marked
rectangle from the page's own colours.

Written with Pillow alone. It previously used numpy, which is not installed on
the deployment, so every repaired page failed to draw.
"""
import hashlib
import os
import tempfile

from PIL import Image, ImageDraw, ImageFilter

from .kit import PLATES, W, H

CACHE = os.path.join(tempfile.gettempdir(), "proposal_patches")
S = 300 / 72.0

MODES = ("clean", "smooth", "lighten", "flatten")


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
    try:
        os.makedirs(CACHE, exist_ok=True)
        out = os.path.join(CACHE, "p%s_%s.jpg" % (page, _key(page, patches)))
        if os.path.exists(out):
            return out
        _build(base, out, patches)
        return out
    except Exception:                                         # noqa: BLE001
        return base          # a failed repair must never stop the page drawing


def _box(im, patch):
    """A patch in PDF points becomes a pixel box, clamped to the image."""
    x0 = max(int(patch.get("x", 0) * S), 0)
    x1 = min(int((patch.get("x", 0) + patch.get("w", 0)) * S), im.width)
    y_top = H - patch.get("y", 0) - patch.get("h", 0)
    y0 = max(int(y_top * S), 0)
    y1 = min(int((y_top + patch.get("h", 0)) * S), im.height)
    return x0, y0, x1, y1


def _vertical_fill(im, box, pad=14):
    """A gradient built from the clean rows above and below the region.

    Pillow does this by taking a one-pixel strip from each side, stretching
    both to fill the box, and blending between them with a linear mask.
    """
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    top_y = max(y0 - pad, 0)
    bot_y = min(y1 + pad, im.height - 1)
    top = im.crop((x0, top_y, x1, top_y + 1)).resize((w, h), Image.BILINEAR)
    bot = im.crop((x0, bot_y - 1, x1, bot_y)).resize((w, h), Image.BILINEAR)
    ramp = Image.linear_gradient("L").resize((w, h), Image.BILINEAR)
    return Image.composite(bot, top, ramp)


def _build(base, out, patches):
    im = Image.open(base).convert("RGB")
    if im.size != (int(W * S), int(H * S)):
        im = im.resize((int(W * S), int(H * S)), Image.LANCZOS)

    for p in patches:
        mode = p.get("mode", "clean")
        box = _box(im, p)
        if box[2] - box[0] < 4 or box[3] - box[1] < 4:
            continue

        if mode == "smooth":
            patch = im.crop(box).filter(ImageFilter.GaussianBlur(30))
        elif mode == "flatten":
            small = im.crop(box).resize((1, 1), Image.BILINEAR)
            patch = Image.new("RGB", (box[2]-box[0], box[3]-box[1]),
                              small.getpixel((0, 0)))
        else:
            patch = _vertical_fill(im, box)
            if mode == "lighten":
                white = Image.new("RGB", patch.size, (255, 255, 255))
                patch = Image.blend(patch, white, 0.65)
        im.paste(patch, (box[0], box[1]))

    # feather every seam so a repair does not read as a rectangle
    for p in patches:
        pad = int(20 * S)
        x0, y0, x1, y1 = _box(im, p)
        bx = (max(x0 - pad, 0), max(y0 - pad, 0),
              min(x1 + pad, im.width), min(y1 + pad, im.height))
        if bx[2] - bx[0] < 8 or bx[3] - bx[1] < 8:
            continue
        region = im.crop(bx)
        blurred = region.filter(ImageFilter.GaussianBlur(11))
        mask = Image.new("L", region.size, 255)
        ImageDraw.Draw(mask).rectangle(
            [pad, pad, region.width - pad, region.height - pad], fill=0)
        mask = mask.filter(ImageFilter.GaussianBlur(pad * 0.6))
        im.paste(Image.composite(blurred, region, mask), bx)

    im.save(out, quality=88, optimize=True)
    return out


def for_page(data, page):
    """The patches recorded against this page, if any."""
    return [p for p in (data.get("patches") or [])
            if str(p.get("page")) == str(page)]
