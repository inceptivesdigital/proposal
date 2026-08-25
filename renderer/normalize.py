"""Force model output into the exact shape the renderer and editor expect.

A model will occasionally return a string where a two-line list belongs, or omit
a key entirely. Rather than let that reach the browser and crash the editor,
every field is coerced here, once, on the server.
"""

DEFAULT_ICON = "ic_home"


def _s(v, default=""):
    if isinstance(v, str):
        return v
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return " ".join(_s(x) for x in v if x)
    return default


def _split_lines(text, n):
    """Break one string into n balanced lines on word boundaries."""
    words = _s(text).split()
    if not words:
        return [""] * n
    per = max(1, len(words) // n)
    out, i = [], 0
    for k in range(n):
        take = words[i:] if k == n - 1 else words[i:i + per]
        out.append(" ".join(take))
        i += len(take)
    return out


def _lines(v, n):
    """Exactly n strings, whatever the model gave us."""
    if isinstance(v, list):
        items = [_s(x) for x in v]
        if len(items) >= n:
            if len(items) > n:                      # fold the tail into the last
                items = items[:n - 1] + [" ".join(items[n - 1:])]
            return items
        return items + [""] * (n - len(items))
    return _split_lines(v, n)


def _list_of(v):
    if isinstance(v, list):
        return v
    if isinstance(v, dict):
        return [v]
    return []


def _paras(v, n=2):
    if isinstance(v, list):
        items = [_s(x) for x in v if _s(x)]
    else:
        items = [_s(v)] if _s(v) else []
    while len(items) < n:
        items.append("")
    return items[:n] if n else items


def _card(item, title_lines=None):
    """title/body/icon, with the title split across lines when asked."""
    d = item if isinstance(item, dict) else {"title": _s(item)}
    out = {
        "title": _lines(d.get("title"), title_lines) if title_lines
                 else _s(d.get("title")),
        "icon": _s(d.get("icon")) or DEFAULT_ICON,
    }
    for key in ("body", "blurb", "lead", "desc"):
        if key in d:
            out[key] = _s(d[key])
    return out


def normalize(d):
    d = dict(d or {})

    p1 = dict(d.get("page1") or {})
    d["page1"] = {"title": _lines(p1.get("title"), 2),
                  "description": _s(p1.get("description"))}

    p3 = dict(d.get("page3") or {})
    surfaces = [_card(s) for s in _list_of(p3.get("surfaces"))]
    for s in surfaces:
        s.setdefault("blurb", "")
    d["page3"] = {
        "eyebrow": _s(p3.get("eyebrow")),
        "one_liner": _s(p3.get("one_liner")),
        "description": _paras(p3.get("description"), 2),
        "surfaces_heading": _s(p3.get("surfaces_heading")) or _heading(len(surfaces)),
        "surfaces": surfaces,
    }

    p4 = dict(d.get("page4") or {})
    cards = [_card(c) for c in _list_of(p4.get("cards"))][:3]
    for c in cards:
        c.setdefault("body", "")
    d["page4"] = {"eyebrow": _s(p4.get("eyebrow")) or "The Differentiator",
                  "one_liner": _s(p4.get("one_liner")),
                  "description": _s(p4.get("description")),
                  "cards": cards}

    d["core_pages"] = [_core(cp) for cp in _list_of(d.get("core_pages"))]

    p9 = dict(d.get("page9") or {})
    include = bool(p9.get("include"))
    promo = p9.get("promo") if isinstance(p9.get("promo"), dict) else {}
    p9cards = [_card(c) for c in _list_of(p9.get("cards"))][:3]
    for c in p9cards:
        c.setdefault("body", "")
    d["page9"] = {
        "include": include,
        "eyebrow": _s(p9.get("eyebrow")) or "Direct Marketing Engine",
        "headline": _lines(p9.get("headline"), 3),
        "description": _s(p9.get("description")),
        "cards": p9cards,
        "promo": {"greeting": _s(promo.get("greeting")),
                  "lines": _lines(promo.get("lines"), 2),
                  "button": _s(promo.get("button"))},
        "screen": _s(p9.get("screen")),
    }

    p10 = dict(d.get("page10") or {})
    d["page10"] = {
        "eyebrow": _s(p10.get("eyebrow")) or "Technical Requirements",
        "headline": _lines(p10.get("headline") or ["Built modern,",
                                                   "Built to scale"], 2),
        "stack": [_body_card(x, "ic_code") for x in _list_of(p10.get("stack"))],
        "services": [_body_card(x, "ic_cloud") for x in _list_of(p10.get("services"))],
        "footnote": _s(p10.get("footnote")),
    }

    p12 = dict(d.get("page12") or {})
    d["page12"] = {
        "eyebrow": _s(p12.get("eyebrow")) or "Milestones, Timeline & Investment",
        "headline": _lines(p12.get("headline") or ["Pay as each",
                                                   "milestone is approved"], 2),
        "total": _s(p12.get("total")),
        "total_note": _s(p12.get("total_note")),
        "total_value": p12.get("total_value"),
        "rows": [_row(r) for r in _list_of(p12.get("rows"))],
    }
    return d


def _heading(n):
    words = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six"}
    return "%s Connected Surfaces" % words.get(n, str(n))


def _body_card(item, icon):
    c = _card(item)
    c.setdefault("body", "")
    given = _s(item.get("icon")) if isinstance(item, dict) else ""
    c["icon"] = given or icon
    return c


def _row(r):
    r = r if isinstance(r, dict) else {"title": _s(r)}
    amount = r.get("amount")
    if isinstance(amount, str) and amount.strip().replace(",", "").isdigit():
        amount = int(amount.replace(",", ""))
    return {"title": _s(r.get("title")), "duration": _s(r.get("duration")),
            "amount": amount if isinstance(amount, (int, float)) else _s(amount),
            "desc": _s(r.get("desc") or r.get("description"))}


def _core(cp):
    cp = dict(cp or {})
    try:
        template = int(cp.get("template", 5))
    except (TypeError, ValueError):
        template = 5
    kind = _s(cp.get("kind")) or {5: "grid", 6: "list"}.get(template, "device")
    out = {"template": template, "kind": kind,
           "eyebrow": _s(cp.get("eyebrow")),
           "headline": _lines(cp.get("headline"), 2)}
    if kind == "grid":
        cards = []
        for c in _list_of(cp.get("cards"))[:4]:
            c = c if isinstance(c, dict) else {"title": _s(c)}
            items = []
            for it in _list_of(c.get("items")):
                if isinstance(it, dict):
                    items.append({"text": _s(it.get("text")),
                                  "bullet": bool(it.get("bullet"))})
                else:
                    items.append({"text": _s(it)})
            cards.append({"title": _lines(c.get("title"), 2),
                          "icon": _s(c.get("icon")) or DEFAULT_ICON,
                          "screen": _s(c.get("screen")), "items": items})
        out["cards"] = cards
    elif kind == "list":
        cards = []
        for c in _list_of(cp.get("cards"))[:4]:
            c = c if isinstance(c, dict) else {"title": _s(c)}
            cards.append({"title": _s(c.get("title")),
                          "icon": _s(c.get("icon")) or "ic_check",
                          "items": [_s(i) for i in _list_of(c.get("items"))][:4]})
        out["cards"] = cards
    else:
        limit = 6 if template == 8 else 4
        blocks = []
        for b in _list_of(cp.get("blocks"))[:limit]:
            b = b if isinstance(b, dict) else {"title": _s(b)}
            blocks.append({"title": _s(b.get("title")),
                           "icon": _s(b.get("icon")) or DEFAULT_ICON,
                           "lead": _s(b.get("lead") or b.get("body")),
                           "bullets": [_s(x) for x in _list_of(b.get("bullets"))]})
        out["blocks"] = blocks
        if cp.get("intro"):
            out["intro"] = _s(cp.get("intro"))
    return out
