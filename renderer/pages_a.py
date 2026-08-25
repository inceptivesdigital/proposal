"""Page renderers 1-9. Every measurement here was taken from Ali's source files."""
from .kit import *
from .icons import draw_icon, poly
from . import icons as IC
from .model import money


def ic(name):
    return getattr(IC, name, IC.ic_home)


# --------------------------------------------------------------- page 1
P1 = dict(title_x=[52.8, 51.2], title_y=[609.87, 542.37],
          title_size=[52.29, 73.50], title_maxw=[491, 415],
          body_x=53.4, body_y=473.95, body_lead=20, body_size=14, body_maxw=330,
          blocks=[(128.2, 323.75, 302.30, 288.85),
                  (128.9, 224.87, 203.42, 191.53),
                  (129.2, 125.03, 106.22, None)])
BLUE_T = (68/255, 96/255, 169/255)


def page1(c, d):
    plate(c, 1)
    m = d["meta"]
    t = d["page1"]["title"]
    for i in (0, 1):
        size = fit_one_line(t[i], "G-Med", P1["title_size"][i],
                            P1["title_maxw"][i], floor=20, step=0.25)
        c.setFont("G-Med", size)
        c.setFillColorRGB(*(INK if i == 0 else BLUE_T))
        c.drawString(P1["title_x"][i], P1["title_y"][i], t[i])
        map_field("page1.title.%d" % i, P1["title_x"][i], P1["title_y"][i],
                  P1["title_maxw"][i], size*1.2, size, "G-Med")
    draw_lines(c, wrap(d["page1"]["description"], "G-Light", P1["body_size"],
                       P1["body_maxw"])[:4],
               P1["body_x"], P1["body_y"], P1["body_lead"], "G-Light",
               P1["body_size"], path="page1.description", maxw=P1["body_maxw"])
    rows = [("Prepared for", m["client_contact"], m["client_company"]),
            ("Prepared by", m["signer_name"], m["signer_role"]),
            ("Date", m.get("date", ""), None)]
    for (x, ly, ny, sy), (label, name, sub) in zip(P1["blocks"], rows):
        draw_lines(c, [label], x, ly, 0, "G-Light", 10.04, INK)
        draw_lines(c, [name], x, ny, 0, "G-Med", 13.83, INK)
        if sub and sy:
            draw_lines(c, [sub], x, sy, 0, "G-XLight", 9.57, INK)


# --------------------------------------------------------------- page 2
P2 = dict(eyebrow=(34.1, 734.8, 39.84),
          headline=(34.1, [695.0, 668.0], 26.08),
          body_x=34.0, body_y=637.2, body_lead=16.0, body_size=12.0,
          body_maxw=396, para_gap=32.0,
          stat_x=[67.3, 199.1, 313.1, 468.1], stat_y=328.4, stat_size=18.0,
          sub_x=[[59.2, 49.5], [185.7, 177.5], [313.0, 340.6], [453.2, 472.8]],
          sub_y=[305.9, 293.9], sub_size=9.0,
          awards=(210.0, 195.7, 16.02))


def page2(c, d):
    """Company Overview. Static apart from the client name in the closing line."""
    plate(c, 2)
    p, m = d["page2"], d["meta"]
    c.setFillColorRGB(*INK)
    c.setFont("G-Semi", P2["eyebrow"][2])
    c.drawString(P2["eyebrow"][0], P2["eyebrow"][1], p["eyebrow"])
    headline(c, P2["headline"][0], P2["headline"][1], p["headline"],
             P2["headline"][2])
    y = P2["body_y"]
    for para in p["paragraphs"]:
        text = para.format(client_company=m.get("client_company", ""))
        lines = wrap(text, "G-XLight", P2["body_size"], P2["body_maxw"])
        draw_lines(c, lines, P2["body_x"], y, P2["body_lead"], "G-XLight",
                   P2["body_size"], BODY)
        y -= len(lines)*P2["body_lead"] + (P2["para_gap"] - P2["body_lead"])
    for i, st in enumerate(p["stats"][:4]):
        parts = st["value"].split(" \u00b7 ")
        if len(parts) > 1:
            dotted(c, P2["stat_x"][i], P2["stat_y"], parts, "G-Semi", 12.10, INK)
        else:
            draw_lines(c, [st["value"]], P2["stat_x"][i], P2["stat_y"], 0,
                       "G-Semi", P2["stat_size"], INK)
        for j, ln in enumerate(st["lines"][:2]):
            draw_lines(c, [ln], P2["sub_x"][i][j], P2["sub_y"][j], 0, "G-Light",
                       P2["sub_size"], BODY)
    draw_lines(c, [p["awards_heading"]], P2["awards"][0], P2["awards"][1], 0,
               "G-Med", P2["awards"][2], INK)


# --------------------------------------------------------------- page 3
P3 = dict(head_x=42.2, head_y=656.5, head_lead=26.55, head_size=24.70,
          head_maxw=505,
          body_x=42.2, body_y=572.4, body_lead=15.30, body_size=11.24,
          body_maxw=430,
          h_cx=297.6, h_y=338.5, h_size=18.97,
          rule=dict(cx=297.6, y=331.9, w=113.2, h=1.2),
          row=dict(x0=44.4, x1=550.5, gutter=13.0, top=318.0, bot=108.2,
                   radius=9.0, icon_cy=269.9, icon_size=34.0, title_dy=92.3,
                   rule_dy=103.0, rule_w=21.7, rule_h=1.5, body_dy=119.6,
                   body_lead=14.4, title_size=10.99, body_size=9.99))


def page3(c, d):
    plate(c, 3)
    p = d["page3"]
    size = P3["head_size"]
    while len(wrap(p["one_liner"], "G-Med", size, P3["head_maxw"])) > 3 and size > 14:
        size -= 0.3
    lines, size = fit_block(p["one_liner"], "G-Med", size, P3["head_maxw"], 3,
                            floor=14)
    draw_lines(c, lines, P3["head_x"], P3["head_y"], P3["head_lead"], "G-Med",
               size, path="page3.one_liner", maxw=P3["head_maxw"])
    lines = []
    for i, para in enumerate(p["description"]):
        if i:
            lines.append("")
        lines += wrap(para, "G-Light", P3["body_size"], P3["body_maxw"])
    c.setFont("G-Light", P3["body_size"])
    c.setFillColorRGB(*INK)
    para, start = 0, 0
    for i, ln in enumerate(lines):
        if ln:
            c.drawString(P3["body_x"], P3["body_y"] - i*P3["body_lead"], ln)
        else:
            map_field("page3.description.%d" % para, P3["body_x"],
                      P3["body_y"] - start*P3["body_lead"], P3["body_maxw"],
                      (i-start)*P3["body_lead"], P3["body_size"], "G-Light")
            para += 1; start = i + 1
    if start < len(lines):
        map_field("page3.description.%d" % para, P3["body_x"],
                  P3["body_y"] - start*P3["body_lead"], P3["body_maxw"],
                  (len(lines)-start)*P3["body_lead"], P3["body_size"], "G-Light")
    c.setFillColorRGB(*INK)
    c.setFont("G-Semi", P3["h_size"])
    c.drawCentredString(P3["h_cx"], P3["h_y"], p["surfaces_heading"])
    map_field("page3.surfaces_heading", P3["h_cx"]-120, P3["h_y"], 240,
              P3["h_size"]*1.3, P3["h_size"], "G-Semi", "center")
    r = P3["rule"]
    c.setFillColorRGB(*NAVY)
    c.rect(r["cx"] - r["w"]/2, r["y"], r["w"], r["h"], stroke=0, fill=1)

    R = P3["row"]
    items = p["surfaces"]
    n = max(len(items), 1)
    gut = R["gutter"] if n <= 5 else 9.0
    cw = (R["x1"] - R["x0"] - gut*(n-1)) / n
    ch = R["top"] - R["bot"]
    for i, s in enumerate(items):
        x = R["x0"] + i*(cw + gut)
        cx = x + cw/2
        c.saveState()
        c.setFillColorRGB(1, 1, 1)
        c.setFillAlpha(0.45)
        c.roundRect(x, R["bot"], cw, ch, R["radius"], stroke=0, fill=1)
        c.setFillAlpha(1)
        c.setStrokeColorRGB(0.85, 0.89, 0.95)
        c.setLineWidth(0.6)
        c.roundRect(x, R["bot"], cw, ch, R["radius"], stroke=1, fill=0)
        c.restoreState()
        if s.get("icon"):
            draw_icon(c, cx, R["icon_cy"], min(R["icon_size"], cw*0.34),
                      ic(s["icon"]))
        ts = fit_one_line(s["title"], "G-Med", R["title_size"], cw-8, floor=6.5)
        c.setFillColorRGB(*INK)
        c.setFont("G-Med", ts)
        c.drawCentredString(cx, R["top"]-R["title_dy"], s["title"])
        map_field("page3.surfaces.%d.title" % i, x+4, R["top"]-R["title_dy"],
                  cw-8, ts*1.3, ts, "G-Med", "center")
        c.setFillColorRGB(*NAVY)
        c.rect(cx - R["rule_w"]/2, R["top"]-R["rule_dy"], R["rule_w"],
               R["rule_h"], stroke=0, fill=1)
        c.setFillColorRGB(*INK)
        bs = R["body_size"] if n <= 4 else 8.8
        c.setFont("G-Light", bs)
        blurb = wrap(s.get("blurb", ""), "G-Light", bs, cw-12)[:4]
        for j, ln in enumerate(blurb):
            c.drawCentredString(cx, R["top"]-R["body_dy"] - j*R["body_lead"], ln)
        map_field("page3.surfaces.%d.blurb" % i, x+4, R["top"]-R["body_dy"],
                  cw-8, max(len(blurb), 1)*R["body_lead"], bs, "G-Light", "center")


# --------------------------------------------------------------- page 4
P4 = dict(title_x=41.3, title_y=[651.5, 606.5], title_size=47.24,
          one_x=41.3, one_y=568.4, one_size=23.26, one_maxw=360, one_lead=24,
          divider=dict(x=42.0, y=552.0, w=89.0, h=1.0),
          desc_x=42.0, desc_y=526.9, desc_lead=20.9, desc_size=13.58,
          desc_maxw=276,
          icon_cx=[73.0, 250.5, 426.5], icon_cy=254.9, icon_box=25.0,
          title2_x=[107.9, 285.2, 462.1], title2_y=[257.0, 243.1],
          title2_size=13.97, title2_maxw=95,
          body_x=[55.5, 232.1, 406.8], body_y=187.8, body_lead=23.0,
          body_size=12.0, body_maxw=142)
RULE_GREY = (198/255, 203/255, 219/255)


def page4(c, d):
    plate(c, 4)
    p = d["page4"]
    headline(c, P4["title_x"], [P4["title_y"][0]], ["The"], P4["title_size"])
    headline(c, P4["title_x"], [P4["title_y"][1]], ["Differentiator"],
             P4["title_size"], BLUE_T)
    size = fit_one_line(p["one_liner"], "G-Med", P4["one_size"],
                        P4["one_maxw"], floor=13)
    lines = wrap(p["one_liner"], "G-Med", size, P4["one_maxw"])[:2]
    c.setFillColorRGB(*INK)
    c.setFont("G-Med", size)
    for i, ln in enumerate(lines):          # bottom-anchored: the rule never moves
        c.drawString(P4["one_x"], P4["one_y"] + (len(lines)-1-i)*P4["one_lead"], ln)
    map_field("page4.one_liner", P4["one_x"], P4["one_y"], P4["one_maxw"],
              len(lines)*P4["one_lead"], size, "G-Med")
    dv = P4["divider"]
    c.setFillColorRGB(*RULE_GREY)
    c.rect(dv["x"], dv["y"], dv["w"], dv["h"], stroke=0, fill=1)
    draw_block(c, p["description"], P4["desc_x"], P4["desc_y"], P4["desc_lead"],
               "G-Light", P4["desc_size"], P4["desc_maxw"], 7, INK, 4,
               "differentiator description")
    map_field("page4.description", P4["desc_x"], P4["desc_y"], P4["desc_maxw"],
              7*P4["desc_lead"], P4["desc_size"], "G-Light")
    cards = [c_ for c_ in p["cards"][:3]
             if as_text(c_.get("title")).strip() or as_text(c_.get("body")).strip()]
    if len(cards) < 3:
        qa_note(4, "empty-slot",
                "%d differentiator card(s) had no content and were left blank; "
                "the artwork shows three boxes" % (3 - len(cards)))
    for i, card in enumerate(cards):
        draw_icon(c, P4["icon_cx"][i], P4["icon_cy"], P4["icon_box"],
                  ic(card.get("icon", "ic_spark")))
        ts = P4["title2_size"]
        tl = wrap(card["title"], "G-Reg", ts, P4["title2_maxw"])
        while len(tl) > 2 and ts > 10:
            ts -= 0.3
            tl = wrap(card["title"], "G-Reg", ts, P4["title2_maxw"])
        c.setFillColorRGB(*INK)
        c.setFont("G-Reg", ts)
        ys = P4["title2_y"] if len(tl) == 2 else [sum(P4["title2_y"])/2]
        for ln, y in zip(tl, ys):
            c.drawString(P4["title2_x"][i], y, ln)
        map_field("page4.cards.%d.title" % i, P4["title2_x"][i], ys[0],
                  P4["title2_maxw"], len(tl)*14, ts, "G-Reg")
        draw_lines(c, wrap(card["body"], "G-XLight", P4["body_size"],
                           P4["body_maxw"])[:4],
                   P4["body_x"][i], P4["body_y"], P4["body_lead"], "G-XLight",
                   P4["body_size"], path="page4.cards.%d.body" % i,
                   maxw=P4["body_maxw"])


# --------------------------------------------------- pages 5-8 (core features)
P5 = dict(eyebrow=(36.1, 721.3, 15.53), headline=(36.6, [675.9, 638.3], 37.65),
          icon=[(66.0, 577.0), (333.0, 577.0), (66.0, 313.7), (333.0, 313.7)],
          tx=[95.5, 361.7, 95.5, 362.6],
          ty=[[580.0, 563.0], [580.2, 563.2], [316.7, 299.7], [316.9, 299.9]],
          bx=[47.8, 317.8, 47.8, 314.4], by=[530.0, 530.0, 264.8, 264.8],
          bw=[136, 118, 122, 112],
          slots=[(193, 275, 273, 475), (440, 552, 265, 471),
                 (178, 283, 532, 729), (435, 550, 525, 733)])

P6 = dict(eyebrow=(42.2, 726.2, 14.0), headline=(42.2, [674.3, 639.3], 35.03),
          icon_x=94.3, icon_y=[551.0, 408.0, 249.0, 116.5],
          title_x=157.1, title_y=[587.5, 445.4, 278.1, 148.8],
          item_x=[170.7, 171.9, 171.9, 171.9],
          item_y=[[565.3, 542.3, 519.3, 496.3], [423.2, 400.2, 377.2, 354.2],
                  [255.9, 236.4, 216.9, 197.4], [129.4, 109.9, 90.4, 70.9]],
          check_x=161.8, item_w=262)

P7 = dict(eyebrow=(42.2, 708.7, 14.0), headline=(42.2, [657.1, 620.1], 36.99),
          intro=dict(x=42.6, y=593.5, lead=18.0, size=12.44, maxw=352),
          icon_x=66.5, icon_box=24, anchor=[493.4, 382.0, 244.0, 135.3],
          title_x=108.0, body_x=112.1, body_w=176,
          device=(300, 200, 268, 372))

P8 = dict(eyebrow=(36.2, 719.2, 14.0), headline=(36.2, [684.2, 655.2], 30.49),
          icon_x=53.8, icon_box=23,
          icon_y=[601.8, 495.5, 390.3, 287.4, 195.1, 101.5],
          anchor=[620.0, 512.9, 405.9, 300.8, 212.5, 114.1],
          title_x=88.1, body_x=92.8, body_w=176,
          device=(296, 250, 282, 330))


GRID_BOTTOM = {0: 356.0, 1: 356.0, 2: 92.0, 3: 92.0}   # floor of each card


def _grid_items(c, items, x, y0, maxw, page, idx):
    """Shrink the whole block until it fits inside the card, then clip."""
    pairs = [(it.get("bullet", False), as_text(it.get("text"))) for it in items]
    floor = GRID_BOTTOM[idx]
    size, lead, gap = 9.5, 12.0, 12.0
    while size > 6.4:
        height = 0
        for _, t in pairs:
            height += len(wrap(t, "G-Light", size, maxw))*lead + gap
        if y0 - height >= floor:
            break
        size -= 0.25
        lead = size*1.26
        gap = lead
    kept, height = [], 0
    for b, t in pairs:
        h = len(wrap(t, "G-Light", size, maxw))*lead + gap
        if y0 - (height + h) < floor:
            qa_note(page, "clipped",
                    "card %d: dropped an item that did not fit" % (idx+1))
            break
        kept.append((b, t)); height += h
    flow(c, kept, x, y0, size, maxw, lead, gap)


def _core_grid(c, page, spec, screens):
    """Page 5 style: 2x2 cards, each with a UI glimpse."""
    plate(c, page)
    eyebrow(c, *P5["eyebrow"][:2], spec["eyebrow"], P5["eyebrow"][2])
    fit_headline(c, P5["headline"][0], P5["headline"][1], spec["headline"],
                 P5["headline"][2], W - P5["headline"][0] - 30, page=page)
    for i, card in enumerate(spec["cards"][:len(P5["icon"])]):
        draw_icon(c, *P5["icon"][i], 21, ic(card.get("icon", "ic_home")))
        c.setFillColorRGB(*INK)
        c.setFont("G-Med", 12.68)
        for j, (ln, y) in enumerate(zip(card["title"][:2], P5["ty"][i])):
            c.drawString(P5["tx"][i], y, ln)
            map_field("%s.cards.%d.title.%d" % (spec["_path"], i, j),
                      P5["tx"][i], y, 120, 15, 12.68, "G-Med")
        _grid_items(c, card["items"], P5["bx"][i], P5["by"][i], P5["bw"][i],
                    page, i)
        x0, x1, y0, y1 = P5["slots"][i]
        path = screens.get(card.get("screen", ""))
        if path:
            from PIL import Image
            im = Image.open(path)
            fx, fy, fw, fh = fit_box(im.width, im.height, x0, H-y1,
                                     x1-x0, y1-y0)
            place_image(c, path, fx, fy, fw, fh)
        else:
            placeholder(c, x0, H-y1, x1-x0, y1-y0)


def _core_list(c, page, spec):
    """Page 6 style: same interface continued, check-list cards, no visuals."""
    plate(c, page)
    eyebrow(c, *P6["eyebrow"][:2], spec["eyebrow"], P6["eyebrow"][2])
    fit_headline(c, P6["headline"][0], P6["headline"][1], spec["headline"],
                 P6["headline"][2], W - P6["headline"][0] - 30, page=page)
    for i, card in enumerate(spec["cards"][:len(P6["icon_y"])]):
        draw_icon(c, P6["icon_x"], P6["icon_y"][i], 26,
                  ic(card.get("icon", "ic_check")))
        c.setFillColorRGB(*INK)
        c.setFont("G-Reg", 13.39)
        c.drawString(P6["title_x"], P6["title_y"][i], card["title"])
        map_field("%s.cards.%d.title" % (spec["_path"], i), P6["title_x"],
                  P6["title_y"][i], 240, 16, 13.39, "G-Reg")
        for j, (text, y) in enumerate(zip(card["items"], P6["item_y"][i])):
            draw_icon(c, P6["check_x"], y+3.0, 9.6, IC.ic_check,
                      (0.24, 0.27, 0.32), 1.5)
            c.setFillColorRGB(*INK)
            c.setFont("G-Light", 9.5)
            lines = wrap(text, "G-Light", 9.5, P6["item_w"]) or [""]
            c.drawString(P6["item_x"][i], y, lines[0])
            map_field("%s.cards.%d.items.%d" % (spec["_path"], i, j),
                      P6["item_x"][i], y, P6["item_w"], 12, 9.5, "G-Light")


def _core_device(c, page, spec, screens, cfg):
    """Pages 7-8 style: feature blocks left, one device screen right."""
    plate(c, page)
    eyebrow(c, cfg["eyebrow"][0], cfg["eyebrow"][1], spec["eyebrow"],
            cfg["eyebrow"][2])
    fit_headline(c, cfg["headline"][0], cfg["headline"][1], spec["headline"],
                 cfg["headline"][2], W - cfg["headline"][0] - 30, page=page)
    if spec.get("intro") and "intro" in cfg:
        it = cfg["intro"]
        draw_lines(c, wrap(spec["intro"], "G-Light", it["size"], it["maxw"])[:3],
                   it["x"], it["y"], it["lead"], "G-Light", it["size"])
    small = page == 8
    tsize, bsize = (10.50, 8.0) if small else (11.60, 9.0)
    lead, gap = (11.0, 7.5) if small else (11.5, 8.5)
    for i, blk in enumerate(spec["blocks"][:len(cfg["anchor"])]):
        anchor = cfg["anchor"][i]
        cy = cfg["icon_y"][i] if "icon_y" in cfg else anchor - 13.9
        draw_icon(c, cfg["icon_x"], cy, cfg["icon_box"],
                  ic(blk.get("icon", "ic_home")))
        c.setFillColorRGB(*INK)
        c.setFont("G-Med", tsize)
        c.drawString(cfg["title_x"], anchor, blk["title"])
        map_field("%s.blocks.%d.title" % (spec["_path"], i), cfg["title_x"],
                  anchor, cfg["body_w"], tsize*1.3, tsize, "G-Med")
        map_field("%s.blocks.%d.lead" % (spec["_path"], i), cfg["body_x"],
                  anchor - (13.6 if small else 14.9), cfg["body_w"], 24,
                  bsize, "G-Light")
        items = [(False, blk["lead"])] + [(True, b) for b in blk.get("bullets", [])]
        flow(c, items, cfg["body_x"], anchor - (13.6 if small else 14.9),
             bsize, cfg["body_w"], lead, gap)
    box = cfg["device"]
    device_with_screen(c, screens.get(spec.get("screen", "")), *box)


def core_page(c, spec, screens):
    kind = spec.get("kind", "grid")
    page = spec["template"]
    if kind == "grid":
        _core_grid(c, page, spec, screens)
    elif kind == "list":
        _core_list(c, page, spec)
    else:
        _core_device(c, page, spec, screens, P7 if page == 7 else P8)


# --------------------------------------------------------------- page 9
P9 = dict(eyebrow=(35.5, 694.4, 14.48), headline=(36.2, [655.1, 617.9, 580.7],
                                                  36.19),
          desc=dict(x=36.5, y=546.2, lead=18.0, size=12.44, maxw=322),
          icon=[(73.9, 385.3), (73.9, 290.2), (73.9, 198.0)],
          title_x=109.6, title_y=[398.8, 306.7, 210.0], body_w=113,
          promo=(270, 600, 176, 106),
          phone=(372, 250, 214, 458))


def page9(c, d, screens=None):
    plate(c, 9)
    p = d["page9"]
    eyebrow(c, *P9["eyebrow"][:2], p["eyebrow"], P9["eyebrow"][2])
    headline(c, P9["headline"][0], P9["headline"][1], p["headline"],
             P9["headline"][2])
    ds = P9["desc"]
    draw_lines(c, wrap(p["description"], "G-Light", ds["size"], ds["maxw"])[:5],
               ds["x"], ds["y"], ds["lead"], "G-Light", ds["size"])
    px, ptop, pw, ph = P9["phone"]
    py = H - ptop - ph
    c.saveState()
    c.setFillColorRGB(0.30, 0.34, 0.40, alpha=0.18)
    c.roundRect(px+3, py-6, pw, ph, 22, stroke=0, fill=1)
    c.setFillAlpha(1)
    c.setFillColorRGB(0.18, 0.20, 0.23)
    c.roundRect(px, py, pw, ph, 22, stroke=0, fill=1)
    c.restoreState()
    scr = screens.get(p.get("screen", "")) if screens else None
    inset = 7
    if scr:
        from PIL import Image
        im = Image.open(scr)
        fx, fy, fw, fh = fit_box(im.width, im.height, px+inset, py+inset,
                                 pw-2*inset, ph-2*inset, anchor="center")
        place_image(c, scr, fx, fy, fw, fh, radius=15)
    else:
        placeholder(c, px+inset, py+inset, pw-2*inset, ph-2*inset)

    x, top, w, h = P9["promo"]
    y = H - top - h
    pr = p.get("promo", {})
    c.saveState()
    c.setFillColorRGB(0.30, 0.36, 0.46, alpha=0.20)
    c.roundRect(x+2, y-4, w, h, 12, stroke=0, fill=1)
    c.setFillAlpha(1)
    c.setFillColorRGB(1, 1, 1)
    c.roundRect(x, y, w, h, 12, stroke=0, fill=1)
    c.setFillColorRGB(*BLUE)
    c.circle(x+26, y+h-30, 16, stroke=0, fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.roundRect(x+17, y+h-36, 18, 12, 2.4, stroke=0, fill=1)
    c.setStrokeColorRGB(*BLUE)
    c.setLineWidth(1.1)
    c.line(x+17, y+h-24, x+26, y+h-30)
    c.line(x+26, y+h-30, x+35, y+h-24)
    c.setFillColorRGB(*INK)
    c.setFont("G-Med", 10.4)
    c.drawString(x+50, y+h-26, pr.get("greeting", ""))
    c.setFont("G-Light", 9.6)
    c.setFillColorRGB(0.24, 0.28, 0.34)
    for i, ln in enumerate(pr.get("lines", [])[:2]):
        c.drawString(x+50, y+h-42-i*14, ln)
    c.setFillColorRGB(*GREEN)
    c.roundRect(x+50, y+12, 76, 20, 10, stroke=0, fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("G-Med", 9.2)
    c.drawCentredString(x+88, y+18, pr.get("button", ""))
    c.restoreState()
    for i, card in enumerate(p["cards"][:3]):
        draw_icon(c, *P9["icon"][i], 24, ic(card.get("icon", "ic_db")))
        c.setFillColorRGB(*INK)
        c.setFont("G-Med", 11.27)
        c.drawString(P9["title_x"], P9["title_y"][i], card["title"])
        flow(c, [(False, card["body"])], P9["title_x"], P9["title_y"][i]-12.9,
             9.0, P9["body_w"], 11.0, 0)
