"""Pages the chat agent creates, drawn on the blank branded plate.

A generated page has to look like it belongs, so it reuses the same eyebrow,
headline, card and icon vocabulary as the designed pages. Only the arrangement
is free.
"""
import os

from .kit import (W, H, INK, GREY, BODY, PLATES, wrap, draw_lines, draw_block,
                  fit_headline, soft_panel, tile, eyebrow, as_text, map_field,
                  qa_note, place_image, placeholder, fit_box)
from .icons import draw_icon
from . import icons as IC

BASE = os.path.join(PLATES, "base.jpg")
ICON_BLUE = (0.16, 0.32, 0.62)

LAYOUT = dict(
    eyebrow=(42.2, 726.2, 14.0),
    headline=(42.2, [674.3, 639.3], 35.03),
    intro=dict(x=42.6, y=596.0, lead=18.0, size=12.44, maxw=430),
    band=dict(top=272.0, bot=760.0, x=42.0, w=511.0, gap=12.0),
)


def _ic(name):
    return getattr(IC, name, IC.ic_home)


def base_plate(c):
    if os.path.exists(BASE):
        c.drawImage(BASE, 0, 0, width=W, height=H)


def custom_page(c, spec, screens=None, index=0):
    """spec: {title|headline, eyebrow, intro, cards[], columns, screen}"""
    base_plate(c)
    L = LAYOUT
    path = "custom_pages.%d" % index

    eyebrow(c, L["eyebrow"][0], L["eyebrow"][1],
            as_text(spec.get("eyebrow")) or "Additional Detail", L["eyebrow"][2])

    head = spec.get("headline") or [as_text(spec.get("title"))]
    if isinstance(head, str):
        head = [head]
    head = (list(head) + ["", ""])[:2]
    fit_headline(c, L["headline"][0], L["headline"][1], head, L["headline"][2],
                 W - L["headline"][0] - 40)
    for i, ln in enumerate(head):
        map_field("%s.headline.%d" % (path, i), L["headline"][0],
                  L["headline"][1][i], W - L["headline"][0] - 40, 38,
                  L["headline"][2], "G-Med")

    top = L["band"]["top"]
    if spec.get("intro"):
        it = L["intro"]
        draw_block(c, spec["intro"], it["x"], it["y"], it["lead"], "G-Light",
                   it["size"], it["maxw"], 4, INK, None, "intro")
        map_field("%s.intro" % path, it["x"], it["y"], it["maxw"], 4*it["lead"],
                  it["size"], "G-Light")

    cards = [c_ for c_ in (spec.get("cards") or [])
             if as_text(c_.get("title")) or as_text(c_.get("body"))]
    if not cards:
        qa_note(0, "empty-page", "A generated page had no cards")
        return

    cols = int(spec.get("columns") or (2 if len(cards) > 3 else 1))
    cols = max(1, min(cols, 3))
    B = L["band"]
    rows = (len(cards) + cols - 1) // cols
    cw = (B["w"] - (cols-1)*B["gap"]) / cols
    available = abs(B["bot"] - B["top"]) - (rows-1)*B["gap"]

    # height each row actually needs, so a short card is not a tall empty box
    need = []
    for row in range(rows):
        tallest = 0
        for card in cards[row*cols:(row+1)*cols]:
            lines = len(wrap(as_text(card.get("body", "")), "G-Light", 9.6, cw-40))
            tallest = max(tallest, 60 + lines*13.0)
        need.append(min(max(tallest, 86), available/rows))
    spare = available - sum(need)
    if spare > 0 and rows:
        need = [n + min(spare/rows, 26) for n in need]

    y_top = H - B["top"]
    for i, card in enumerate(cards):
        col, row = i % cols, i // cols
        ch = need[row]
        x = B["x"] + col*(cw + B["gap"])
        y = y_top - sum(need[:row+1]) - row*B["gap"]
        soft_panel(c, x, y, cw, ch, 12, (1, 1, 1), 0.09)
        tile(c, x + 30, y + ch - 32, 16.5)
        draw_icon(c, x + 30, y + ch - 32, 19, _ic(card.get("icon", "ic_check")),
                  ICON_BLUE, 1.7)
        ty = y + ch - 26
        c.setFillColorRGB(*INK)
        c.setFont("G-Med", 12.4)
        c.drawString(x + 58, ty, as_text(card.get("title"))[:44])
        map_field("%s.cards.%d.title" % (path, i), x + 58, ty, cw - 70, 15,
                  12.4, "G-Med")
        draw_block(c, card.get("body", ""), x + 20, y + ch - 52, 13.0,
                   "G-Light", 9.6, cw - 40, max(int((ch - 60)/13), 1), BODY,
                   None, "card body")
        map_field("%s.cards.%d.body" % (path, i), x + 20, y + ch - 52, cw - 40,
                  ch - 60, 9.6, "G-Light")
