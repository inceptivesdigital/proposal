"""One button that walks the whole proposal and fixes what it can.

Deterministic repairs first, because they are safe and free. Only copy that is
genuinely too long for its box is sent to the model, and only that fragment.
"""
import json

from .kit import register_fonts, wrap, capacity
from .model import check_milestones
from .render import render, core_page_is_empty

SHORTEN_SYSTEM = """You shorten proposal copy to fit a fixed space.

You are given fragments, each with the text and the maximum number of \
characters it may use. Return the same fragments, shortened, keeping the \
meaning and the specifics. Plain, confident, no hype, no em-dashes. Never drop \
a number, a price or a product name.

Reply with {"fixes":[{"path":"...","value":"..."}]} and nothing else."""


def scan(data, screens=None):
    """Render once and collect everything worth fixing."""
    register_fonts()
    meta = render(data, "/tmp/_qa.pdf", screens or {})
    issues = []
    for f in meta.get("failures", []):
        issues.append({"kind": "error", "page": f["page"], "detail": f["error"],
                       "fixable": False})
    for q in meta.get("qa", []):
        page = q.get("page")
        issues.append({"kind": q["kind"],
                       "page": (page + 1) if isinstance(page, int) else None,
                       "detail": q["detail"], "fixable": False})

    # copy that overruns the space measured for its own field
    over = []
    for t in meta.get("textmap", []):
        value = _get(data, t["path"])
        if isinstance(value, str) and t.get("limit") and len(value) > t["limit"]:
            over.append({"path": t["path"], "label": t["label"],
                         "limit": t["limit"], "length": len(value),
                         "text": value})
    ok, total, summed, msg = check_milestones(
        data.get("page12", {}), data.get("meta", {}).get("region", "US"))
    return {"issues": issues, "over_length": over, "pages": meta["pages"],
            "milestones_ok": ok, "milestone_warning": msg,
            "milestone_total": total, "milestone_sum": summed}


PLACEHOLDERS = ("kandy", "lorem", "ipsum", "your company", "client name",
                "acme", "untitled", "tbd", "xxx", "todo")


def review(data, screens=None):
    """Every finding, each with a proposed change the user can accept or skip."""
    found = scan(data, screens)
    meta = data.get("meta", {})
    items = []

    def add(kind, title, detail, path=None, value=None, severity="warn"):
        items.append({"id": "f%d" % len(items), "kind": kind, "title": title,
                      "detail": detail, "path": path, "value": value,
                      "severity": severity,
                      "fixable": path is not None})

    # --- content correctness ------------------------------------------------
    company = str(meta.get("client_company", "")).strip()
    contact = str(meta.get("client_contact", "")).strip()
    if not company:
        add("content", "No client company", "The company name is empty, so page 2 "
            "and page 14 will read oddly.", severity="error")
    if not contact:
        add("content", "No client contact", "The cover and the signature block "
            "both need a contact name.", severity="error")

    blob = json.dumps(data).lower()
    for word in PLACEHOLDERS:
        if word in blob and word not in company.lower():
            add("content", "Placeholder text found",
                'The word "%s" still appears somewhere in the proposal.' % word,
                severity="error")

    # a client name from another proposal, left in the body copy
    for path in ("page14.cards.0.body", "page2.text"):
        text = str(_get(data, path) or "")
        if company and text and company not in text and "{client" not in text:
            add("content", "Client name may be stale",
                "%s does not mention %s." % (path, company))

    risk = str(data.get("page14", {}).get("risk_area", ""))
    if not risk or "core functionality" in risk:
        add("content", "App-store risk not specific",
            "Page 14 still uses the generic risk wording. Name what about this "
            "app is likely to draw review.",
            "page14.risk_area", None)

    # --- money --------------------------------------------------------------
    if not found["milestones_ok"]:
        add("money", "Milestones do not match the total",
            found["milestone_warning"], severity="error")

    # --- design -------------------------------------------------------------
    for o in found["over_length"]:
        add("design", "Text overruns its box",
            "%s is %d characters against a limit of %d, so the type will shrink."
            % (o["label"], o["length"], o["limit"]), o["path"], None)
    for i in found["issues"]:
        where = "Page %s: " % i["page"] if i["page"] else ""
        add("design", i["kind"].replace("-", " ").capitalize(),
            where + i["detail"],
            severity="error" if i["kind"] == "error" else "warn")

    surfaces = data.get("page3", {}).get("surfaces") or []
    words = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six"}
    want = "%s Connected Surfaces" % words.get(len(surfaces), len(surfaces))
    if surfaces and data["page3"].get("surfaces_heading") != want:
        add("design", "Surfaces heading disagrees with the count",
            'It says "%s" but there are %d surfaces.'
            % (data["page3"].get("surfaces_heading"), len(surfaces)),
            "page3.surfaces_heading", want)

    for path, label in (("page3.surfaces", "surfaces"),
                        ("page4.cards", "differentiator cards"),
                        ("page10.stack", "stack items"),
                        ("page10.services", "integrations")):
        node = _get(data, path) or []
        empty = [i for i, c in enumerate(node)
                 if not str(c.get("title", "")).strip()
                 and not str(c.get("body", "")).strip()]
        if empty:
            add("design", "Empty %s" % label,
                "%d of the %s have no content and print as blank boxes."
                % (len(empty), label), path,
                [c for i, c in enumerate(node) if i not in empty])

    cards4 = data.get("page4", {}).get("cards") or []
    if len(cards4) and len(cards4) < 3:
        add("design", "Fewer than three differentiator cards",
            "There are %d. The row is drawn to fit whatever it holds, so this "
            "is only worth fixing if you want a third point."
            % len(cards4), "page4.cards", None, "warn")

    return {"items": items, "pages": found["pages"]}


def apply_selected(data, items, ids, client=None):
    """Apply only the findings the user ticked."""
    done = []
    chosen = [i for i in items if i["id"] in set(ids)]
    for item in chosen:
        if item.get("path") and item.get("value") is not None:
            _set(data, item["path"], item["value"])
            done.append(item["title"])
        elif item.get("path"):
            done.append(item["title"] + " (queued for rewrite)")
    # anything needing a rewrite goes in one model call
    rewrite = [i for i in chosen if i.get("path") and i.get("value") is None]
    if rewrite:
        frags = []
        for i in rewrite:
            text = _get(data, i["path"])
            if isinstance(text, str) and text:
                frags.append({"path": i["path"], "limit": max(len(text)//2, 40),
                              "text": text})
        for f in _shorten(frags, client):
            _set(data, f["path"], f["value"])
    return done


def repair(data, client=None):
    """Apply every safe fix, then shorten what is still too long."""
    done = []

    # 1. cards with no content at all
    for path in ("page3.surfaces", "page4.cards", "page10.stack",
                 "page10.services", "page9.cards"):
        node = _get(data, path)
        if isinstance(node, list):
            kept = [c for c in node
                    if str(c.get("title", "")).strip() or str(c.get("body", "")).strip()]
            if len(kept) != len(node):
                done.append("removed %d empty card(s) from %s"
                            % (len(node)-len(kept), path))
                _set(data, path, kept)

    # 2. a surfaces heading that disagrees with the count
    surfaces = data.get("page3", {}).get("surfaces") or []
    words = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six"}
    want = "%s Connected Surfaces" % words.get(len(surfaces), len(surfaces))
    if surfaces and data["page3"].get("surfaces_heading") != want:
        data["page3"]["surfaces_heading"] = want
        done.append("surfaces heading now says %s" % want)

    # 3. Core Features pages with nothing on them
    before = len(data.get("core_pages") or [])
    data["core_pages"] = [s for s in (data.get("core_pages") or [])
                          if not core_page_is_empty(s)]
    if len(data["core_pages"]) != before:
        done.append("dropped %d empty feature page(s)"
                    % (before - len(data["core_pages"])))

    # 4. milestone descriptions that are missing
    for i, row in enumerate(data.get("page12", {}).get("rows") or []):
        if not str(row.get("desc", "")).strip():
            row["desc"] = "Delivery and sign-off for this phase."
            done.append("filled milestone %d description" % (i+1))

    # 5. copy still too long for its box
    found = scan(data)
    if found["over_length"] and client is not False:
        fixes = _shorten(found["over_length"], client)
        for f in fixes:
            _set(data, f["path"], f["value"])
            done.append("shortened %s" % f["path"])

    return {"changes": done, "remaining": scan(data)}


def _shorten(fragments, client=None):
    from .extract import _call, _client
    payload = json.dumps({"fragments": [
        {"path": f["path"], "max_characters": f["limit"], "text": f["text"]}
        for f in fragments[:14]]}, ensure_ascii=False)
    try:
        out = _call(_client(client), SHORTEN_SYSTEM, payload, 3000)
    except Exception:                                         # noqa: BLE001
        return []
    good = []
    for f in out.get("fixes", []):
        want = next((x for x in fragments if x["path"] == f.get("path")), None)
        if want and isinstance(f.get("value"), str) and \
                len(f["value"]) <= want["limit"]:
            good.append(f)
    return good


def _keys(path):
    return [int(p) if p.lstrip("-").isdigit() else p for p in path.split(".")]


def _get(data, path):
    node = data
    for k in _keys(path):
        try:
            node = node[k]
        except (KeyError, IndexError, TypeError):
            return None
    return node


def _set(data, path, value):
    keys = _keys(path)
    node = data
    for k in keys[:-1]:
        node = node[k]
    node[keys[-1]] = value
