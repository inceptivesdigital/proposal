"""Page renderers 10-15."""
from .kit import *
from .icons import draw_icon
from . import icons as IC
from .model import money


def ic(name):
    return getattr(IC, name, IC.ic_home)


# --------------------------------------------------------------- page 10
P10 = dict(eyebrow=(35.8, H-123.1, 14.4), headline=(38.4, [H-181.0, H-213.1], 30.6),
           left=dict(x=44.5, w=234.7, top=666.8, bot=232.8, tile_cx=93.8,
                     text_x=138.2),
           right=dict(x=306.3, w=243.0, tile_cx=347.4, card_x=370.0,
                      card_w=166.4, text_x=384.5),
           pad=14.0,
           foot=dict(x=82.4, w=383.7, top=766.0, bot=686.0, icon_cx=128.0,
                     text_x=173.5, text_y=706.3, lead=15.0, size=10.6, maxw=262))
SOFT = (0.99, 0.995, 1.0)
GREEN_L = (0.55, 0.74, 0.42)
ICON_BLUE = (0.16, 0.32, 0.62)


def page10(c, d):
    plate(c, 10)
    p = d["page10"]
    gap = float((d.get("spacing") or {}).get("page10", 1.0))
    eyebrow(c, *P10["eyebrow"][:2], p["eyebrow"], P10["eyebrow"][2])
    fit_headline(c, P10["headline"][0], P10["headline"][1], p["headline"],
                 P10["headline"][2], W - P10["headline"][0] - 40, page=10)
    L, R, PAD = P10["left"], P10["right"], P10["pad"]
    py0, py1 = H - L["top"], H - L["bot"]
    ph = py1 - py0
    soft_panel(c, L["x"], py0, L["w"], ph, 14, SOFT, 0.10)
    soft_panel(c, R["x"], py0, R["w"], ph, 14, SOFT, 0.10)

    items = p["stack"]
    pitch = (ph - 2*PAD) / max(len(items), 1)
    body_w = L["w"] - (L["text_x"]-L["x"]) - 16

    # One size for the whole column, chosen so the tallest item still clears
    # its neighbour. Without this a long body runs into the next heading.
    tsize, bsize, lead = 11.6, 8.8, 11.0 * gap
    room = pitch - 12                      # breathing space between items
    while bsize > 6.6:
        lead = bsize * 1.25 * gap
        tallest = max([tsize + 4 + len(wrap(as_text(x.get("body")), "G-Light",
                                            bsize, body_w)) * lead
                       for x in items] or [0])
        if tallest <= room:
            break
        bsize -= 0.2
        if bsize < 7.6 and tsize > 9.6:
            tsize -= 0.2                   # shrink the heading only at the end

    for i, it in enumerate(items):
        cy = py1 - PAD - pitch*(i + 0.5)
        tile(c, L["tile_cx"], cy)
        draw_icon(c, L["tile_cx"], cy, 20, ic(it.get("icon", "ic_code")),
                  ICON_BLUE, 1.7)
        lines = wrap(as_text(it.get("body")), "G-Light", bsize, body_w)
        max_lines = max(int((room - tsize - 4) / lead), 1)
        if len(lines) > max_lines:
            qa_note(0, "clipped",
                    "technical stack item %d was too long for its row" % (i+1))
            lines = lines[:max_lines]
        blk = tsize + 4 + len(lines)*lead
        ty = cy + blk/2 - tsize*0.8
        c.setFillColorRGB(*INK)
        c.setFont("G-Med", tsize)
        c.drawString(L["text_x"], ty, fit_text(as_text(it.get("title")),
                                               "G-Med", tsize, body_w))
        map_field("page10.stack.%d.title" % i, L["text_x"], ty, body_w,
                  tsize*1.2, tsize, "G-Med")
        draw_lines(c, lines, L["text_x"], ty - (tsize + 3.2), lead, "G-Light",
                   bsize, (0.30, 0.34, 0.41),
                   path="page10.stack.%d.body" % i, maxw=body_w)
        if i:
            c.setStrokeColorRGB(0.90, 0.92, 0.95)
            c.setLineWidth(0.7)
            c.line(L["text_x"]-8, py1-PAD-pitch*i, L["x"]+L["w"]-14,
                   py1-PAD-pitch*i)

    c.setStrokeColorRGB(*GREEN_L)
    c.setLineWidth(0.9)
    bx0, bx1 = L["x"]+L["w"]+4, R["x"]-6
    byc = (py0+py1)/2
    c.line(bx0, byc, bx1-9, byc)
    path = c.beginPath()
    path.moveTo(bx1-9, byc+52)
    path.curveTo(bx1, byc+52, bx1, byc+40, bx1, byc+30)
    path.lineTo(bx1, byc-30)
    path.curveTo(bx1, byc-40, bx1, byc-52, bx1-9, byc-52)
    c.drawPath(path)
    for i in range(len(items)):
        c.setFillColorRGB(*GREEN_L)
        c.circle(L["x"]-7, py1 - PAD - pitch*(i + 0.5), 2.2, stroke=0, fill=1)

    svc = p["services"]
    sp = (ph - 2*PAD) / max(len(svc), 1)
    ch = min(sp - 7, 62)
    # same treatment on the right: fit the longest service into its card
    ssize, slead = 7.9, 9.4 * gap
    while ssize > 6.2:
        slead = ssize * 1.2 * gap
        tallest = max([10.4 + 3 + len(wrap(as_text(x.get("body")), "G-Light",
                                           ssize, R["card_w"]-24)) * slead
                       for x in svc] or [0])
        if tallest <= ch - 8:
            break
        ssize -= 0.15
    for i, s in enumerate(svc):
        cy = py1 - PAD - sp*(i + 0.5)
        soft_panel(c, R["card_x"], cy-ch/2, R["card_w"], ch, 9, (1, 1, 1), 0.07)
        tile(c, R["tile_cx"], cy, 15.5)
        draw_icon(c, R["tile_cx"], cy, 17.5, ic(s.get("icon", "ic_cloud")),
                  ICON_BLUE, 1.6)
        lines = wrap(as_text(s.get("body")), "G-Light", ssize, R["card_w"]-24)
        max_lines = max(int((ch - 18) / slead), 1)
        if len(lines) > max_lines:
            qa_note(0, "clipped",
                    "integration %d was too long for its card" % (i+1))
            lines = lines[:max_lines]
        ts = fit_one_line(s["title"], "G-Med", 10.4, R["card_w"]-24, floor=7.6)
        c.setFillColorRGB(*INK)
        c.setFont("G-Med", ts)
        c.drawString(R["text_x"], cy + 2.4 + (len(lines)-1)*4.6, s["title"])
        map_field("page10.services.%d.title" % i, R["text_x"],
                  cy + 2.4 + (len(lines)-1)*4.6, R["card_w"]-24, 13, ts, "G-Med")
        draw_lines(c, lines, R["text_x"], cy - 8.4 * gap + (len(lines)-1)*4.6,
                   slead, "G-Light", ssize, (0.30, 0.34, 0.41),
                   path="page10.services.%d.body" % i, maxw=R["card_w"]-24)

    F = P10["foot"]
    fy0, fy1 = H-F["top"], H-F["bot"]
    soft_panel(c, F["x"], fy0, F["w"], fy1-fy0, 12, (1, 1, 1), 0.09)
    draw_icon(c, F["icon_cx"], (fy0+fy1)/2, 40, IC.ic_cloud, (0.16, 0.36, 0.72), 1.5)
    draw_lines(c, wrap(p["footnote"], "G-Light", F["size"], F["maxw"])[:3],
               F["text_x"], H-F["text_y"], F["lead"], "G-Light", F["size"],
               (0.24, 0.28, 0.35))


# --------------------------------------------------------------- page 11
P11 = dict(eyebrow=(35.5, 717.3, 14.98),
           headline=(34.7, [681.8, 650.5, 619.2], 32.18),
           num_x=[51.9, 48.8, 48.8, 48.8, 48.9, 48.5],
           num_y=[550.4, 463.4, 376.4, 289.4, 202.4, 115.4], num_size=23.84,
           text_x=194.1,
           title_y=[562.4, 476.5, 390.6, 304.7, 218.5, 132.4], title_size=13.35,
           body_y=[548.3, 462.4, 376.5, 290.6, 204.4, 118.3],
           body_lead=12.0, body_size=10.0, body_maxw=222)


def page11(c, d):
    """How We Build. Fully static, verified free of client-specific wording."""
    plate(c, 11)
    p = d["page11"]
    eyebrow(c, *P11["eyebrow"][:2], p["eyebrow"], P11["eyebrow"][2])
    headline(c, P11["headline"][0], P11["headline"][1], p["headline"],
             P11["headline"][2])
    for i, step in enumerate(p["steps"][:6]):
        draw_lines(c, ["%02d" % (i+1)], P11["num_x"][i], P11["num_y"][i], 0,
                   "G-Med", P11["num_size"], INK)
        draw_lines(c, [step["title"]], P11["text_x"], P11["title_y"][i], 0,
                   "G-Med", P11["title_size"], INK)
        draw_lines(c, wrap(step["body"], "G-Light", P11["body_size"],
                           P11["body_maxw"])[:2],
                   P11["text_x"], P11["body_y"][i], P11["body_lead"], "G-Light",
                   P11["body_size"], BODY)


# --------------------------------------------------------------- page 12
P12 = dict(eyebrow=(35.5, 713.9, 14.98), headline=(34.7, [669.8, 641.2], 29.44),
           total=dict(x=372.7, w=131.3, top=162.0, h=53.8, note_y=H-146.2+4),
           band=dict(top=231.8, bot=746.2, gap=9.8),
           card=dict(x=86.9, w=417.3, title_x=101.5, desc_x=102.2,
                     pill_w=79.0, pill_h=25.0),
           badge=dict(cx=56.1, r=19.4),
           foot=dict(x=43.6, y=[62.1, 51.1, 40.1], size=9.0, rule_x=39.0))
BLUE_B, GREEN_B = (37/255, 99/255, 235/255), (0.42, 0.66, 0.31)
PILL_BG, PILL_INC = (0.906, 0.929, 0.973), (0.871, 0.937, 0.867)
P12_FOOT = [
    "Prices are estimates and may vary with additional features requested during the project.",
    "Each milestone payment is due upon its successful completion and approval before the next",
    "phase begins. Extended support beyond 30 days is available under a separate agreement.",
]


def page12(c, d):
    plate(c, 12)
    from .model import currency_of
    p, cur = d["page12"], currency_of(d)
    eyebrow(c, *P12["eyebrow"][:2], p["eyebrow"], P12["eyebrow"][2])
    fit_headline(c, P12["headline"][0], P12["headline"][1], p["headline"],
                 P12["headline"][2], P12["total"]["x"] - P12["headline"][0] - 14,
                 page=12)
    T = P12["total"]
    ty = H - T["top"] - T["h"]
    soft_panel(c, T["x"], ty, T["w"], T["h"], 10, (1, 1, 1), 0.09)
    total = p.get("total") or money(p.get("total_value", 0), cur)
    # AED, SAR and THB are set as codes, so the total has to fit the pill
    tsize = fit_one_line(total, "G-Med", 31.01, T["w"] - 18, floor=15.0,
                         step=0.4)
    c.setFillColorRGB(*INK)
    c.setFont("G-Med", tsize)
    c.drawCentredString(T["x"]+T["w"]/2, ty + 16 + (31.01 - tsize) * 0.32, total)
    note = p.get("total_note", "")
    parts = note.split(" \u00b7 ")
    width = (sw(parts[0], "G-Light", 9.17) +
             (sw("  \u00b7  ", "Helvetica", 7.9) +
              sw(parts[1], "G-Light", 9.17) if len(parts) > 1 else 0))
    dotted(c, T["x"] + T["w"] - width, T["note_y"], parts, "G-Light", 9.17, GREY)

    B, C, G = P12["band"], P12["card"], P12["badge"]
    rows = p["rows"]
    n = max(len(rows), 1)
    band = B["bot"] - B["top"]
    ch = (band - (n-1)*B["gap"]) / n
    for i, r in enumerate(rows):
        top = B["top"] + i*(ch + B["gap"])
        y = H - top - ch
        soft_panel(c, C["x"], y, C["w"], ch, 9, (1, 1, 1), 0.09)
        cy = y + ch/2
        c.setFillColorRGB(*(BLUE_B if i % 2 == 0 else GREEN_B))
        c.circle(G["cx"], cy, G["r"], stroke=0, fill=1)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("G-Med", 20.48)
        c.drawCentredString(G["cx"], cy-7.2, str(i+1))
        if i:
            c.setStrokeColorRGB(0.72, 0.79, 0.90)
            c.setLineWidth(1.1)
            c.line(G["cx"], cy+G["r"], G["cx"],
                   cy+G["r"]+B["gap"]+(ch-2*G["r"])/2+2)
        ty2 = y + ch - 21.1
        c.setFillColorRGB(*INK)
        c.setFont("G-Med", 13.04)
        c.drawString(C["title_x"], ty2, r["title"])
        map_field("page12.rows.%d.title" % i, C["title_x"], ty2, 240, 16,
                  13.04, "G-Med")
        tw = sw(r["title"], "G-Med", 13.04)
        if r.get("duration"):
            c.setFillColorRGB(*GREY)
            c.setFont("Helvetica", 7.6)
            c.drawString(C["title_x"]+tw+6, ty2+1.4, "\u00b7 " + r["duration"])
        draw_block(c, r.get("desc", ""), C["desc_x"], y + ch - 37.6, 11.6,
                   "G-Light", 8.92, 300, 2, (0.30, 0.34, 0.41), 12,
                   "milestone %d description" % (i+1))
        map_field("page12.rows.%d.desc" % i, C["desc_x"], y + ch - 37.6, 300,
                  23, 8.92, "G-Light")
        amount = r.get("amount")
        label = amount if isinstance(amount, str) else money(amount, cur)

        inc = str(label).lower() == "included"
        pw = C["pill_w"] + (10 if inc else 0)
        px = C["x"] + C["w"] - 8 - pw
        c.setFillColorRGB(*(PILL_INC if inc else PILL_BG))
        c.roundRect(px, cy-C["pill_h"]/2, pw, C["pill_h"], 7, stroke=0, fill=1)
        c.setFillColorRGB(*((0.24, 0.50, 0.22) if inc else INK))
        base = 13.6 if inc else 15.32
        psize = fit_one_line(label, "G-Med", base, pw - 12, floor=9.0, step=0.25)
        c.setFont("G-Med", psize)
        c.drawCentredString(px+pw/2, cy - 4.8 + (base - psize) * 0.3, label)

    F = P12["foot"]
    c.setStrokeColorRGB(0.42, 0.48, 0.60)
    c.setLineWidth(1.6)
    c.line(F["rule_x"], F["y"][2]-4, F["rule_x"], F["y"][0]+9)
    for ln, y in zip(P12_FOOT, F["y"]):
        draw_lines(c, [ln], F["x"], y, 0, "G-Light", F["size"], (0.28, 0.32, 0.39))


# --------------------------------------------------------------- page 13
P13 = dict(eyebrow=(35.5, 722.4, 14.21), headline=(34.7, [678.5, 648.6], 30.69),
           left_head=(110.8, 572.1, 16.37), right_head=(371.2, [581.7, 565.7], 16.37),
           lx=73.3, rx=334.9, size=10.0, llead=15.0, rlead=17.0, lw=179, rw=159,
           ly=[526.8, 481.2, 434.7, 388.4, 342.3, 295.7, 249.4, 204.3],
           ry=[512.7, 446.0, 379.2, 312.8, 232.1],
           foot=(119.2, [123.2, 106.2], 10.0, 320))


def page13(c, d):
    plate(c, 13)
    p = d["page13"]
    eyebrow(c, *P13["eyebrow"][:2], p["eyebrow"], P13["eyebrow"][2])
    headline(c, P13["headline"][0], P13["headline"][1], p["headline"],
             P13["headline"][2])
    c.setFillColorRGB(*INK)
    c.setFont("G-Med", P13["left_head"][2])
    c.drawString(P13["left_head"][0], P13["left_head"][1], p["deliver_head"])
    for ln, y in zip(p["need_head"], P13["right_head"][1]):
        c.drawString(P13["right_head"][0], y, ln)
    for i, (text, y) in enumerate(zip(p["deliver"], P13["ly"])):
        draw_lines(c, wrap(text, "G-Light", P13["size"], P13["lw"])[:2],
                   P13["lx"], y, P13["llead"], "G-Light", P13["size"],
                   (0.16, 0.19, 0.24), path="page13.deliver.%d" % i,
                   maxw=P13["lw"])
    for i, (text, y) in enumerate(zip(p["need"], P13["ry"])):
        draw_lines(c, wrap(text, "G-Light", P13["size"], P13["rw"])[:3],
                   P13["rx"], y, P13["rlead"], "G-Light", P13["size"],
                   (0.16, 0.19, 0.24), path="page13.need.%d" % i,
                   maxw=P13["rw"])
    F = P13["foot"]
    draw_lines(c, wrap(p["footnote"], "G-XLight", F[2], F[3])[:2],
               F[0], F[1][0], 17.0, "G-XLight", F[2], (0.24, 0.28, 0.35),
               path="page13.footnote", maxw=F[3])


# --------------------------------------------------------------- page 14
P14 = dict(eyebrow=(34.5, 714.0, 14.51),
           headline=(35.5, [657.4, 626.7, 596.1], 31.34),
           cols=[46.9, 219.4, 391.9], rows=[476.7, 258.6], body=[461.4, 243.3],
           lead=15.3, size=10.21, maxw=132,
           foot=(142.2, [105.1, 89.7, 74.4], 9.7, 348))


def page14(c, d):
    plate(c, 14)
    p, m = d["page14"], d["meta"]
    eyebrow(c, *P14["eyebrow"][:2], p["eyebrow"], P14["eyebrow"][2])
    headline(c, P14["headline"][0], P14["headline"][1], p["headline"],
             P14["headline"][2])
    for i, card in enumerate(p["cards"][:6]):
        x = P14["cols"][i % 3]
        ty, by = P14["rows"][i//3], P14["body"][i//3]
        c.setFillColorRGB(*INK)
        c.setFont("G-Reg", P14["size"])
        c.drawString(x, ty, card["title"])
        body = card["body"].format(client_company=m.get("client_company", ""))
        map_field("page14.cards.%d.title" % i, x, ty, P14["maxw"], 14,
                  P14["size"], "G-Reg")
        draw_lines(c, wrap(body, "G-Light", P14["size"], P14["maxw"])[:6],
                   x, by, P14["lead"], "G-Light", P14["size"], (0.22, 0.26, 0.32),
                   path="page14.cards.%d.body" % i, maxw=P14["maxw"])
    F = P14["foot"]
    foot = p["footnote"].format(risk_area=p.get("risk_area", ""))
    draw_lines(c, wrap(foot, "G-Light", F[2], F[3])[:3], F[0], F[1][0], 15.4,
               "G-Light", F[2], (0.24, 0.28, 0.35), path="page14.risk_area",
               maxw=F[3])


# --------------------------------------------------------------- page 15
P15 = dict(eyebrow=(34.5, 711.6, 14.51), headline=(33.6, 670.4, 34.80),
           step_x=127.9, num_x=[62.3, 58.7, 58.9, 58.7, 58.9],
           step_y=[620.6, 558.7, 500.1, 438.2, 379.9],
           num_y=[616.5, 556.0, 496.5, 435.8, 376.5],
           help_x=119.0, help_y=306.2, contact_y=281.4,
           sign_head=(34.5, 219.8, 20.93), sign_note=(34.8, 194.6, 11.0),
           name_y=89.9, sub_y=69.9, cols=[99.3, 348.2])


def page15(c, d):
    plate(c, 15)
    p, m = d["page15"], d["meta"]
    eyebrow(c, *P15["eyebrow"][:2], p["eyebrow"], P15["eyebrow"][2])
    c.setFillColorRGB(*INK)
    c.setFont("G-Med", P15["headline"][2])
    c.drawString(P15["headline"][0], P15["headline"][1], p["headline"])
    for i, text in enumerate(p["steps"][:5]):
        c.setFillColorRGB(*INK)
        c.setFont("G-Med", 25.0)
        c.drawString(P15["num_x"][i], P15["num_y"][i], str(i+1))
        draw_lines(c, [text], P15["step_x"], P15["step_y"][i], 0, "G-Light",
                   11.0, (0.16, 0.19, 0.24), path="page15.steps.%d" % i,
                   maxw=330)
    draw_lines(c, [p["help_line"]], P15["help_x"], P15["help_y"], 0, "G-Light",
               11.0, (0.22, 0.26, 0.32))
    dotted(c, P15["help_x"], P15["contact_y"], p["contact"], "G-Reg", 13.52, INK)
    c.setFillColorRGB(*INK)
    c.setFont("G-Med", P15["sign_head"][2])
    c.drawString(P15["sign_head"][0], P15["sign_head"][1], p["sign_head"])
    draw_lines(c, [p["sign_note"]], P15["sign_note"][0], P15["sign_note"][1], 0,
               "G-Light", P15["sign_note"][2], (0.22, 0.26, 0.32))
    signers = [(m.get("client_contact", ""), [m.get("client_company", "")]),
               (m.get("signer_name", ""),
                [m.get("signer_role", ""), "Inceptives Digital"])]
    for i, (x, (name, sub)) in enumerate(zip(P15["cols"], signers)):
        draw_lines(c, [name], x, P15["name_y"], 0, "G-Med", 11.5, INK)
        parts = [s for s in sub if s]
        avail = (P15["cols"][1] - 18 - x) if i == 0 else (W - 34 - x)
        size, sep = 10.5, "  \u00b7  "
        width = lambda s: (sum(sw(p, "G-Light", s) for p in parts) +
                           sw(sep, "Helvetica", s*0.86) * (len(parts)-1))
        while width(size) > avail and size > 7.4:
            size -= 0.2
        if width(size) > avail and len(parts) > 1:   # still too wide: stack it
            draw_lines(c, [parts[0]], x, P15["sub_y"] + 5.5, 0, "G-Light",
                       size, (0.30, 0.34, 0.41))
            draw_lines(c, [" \u00b7 ".join(parts[1:])], x, P15["sub_y"] - 5.0, 0,
                       "G-Light", size, (0.30, 0.34, 0.41))
        else:
            dotted(c, x, P15["sub_y"], parts, "G-Light", size, (0.30, 0.34, 0.41))
