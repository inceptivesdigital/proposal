"""Turns a proposal JSON into the finished 15-page PDF. No AI, no network."""
from reportlab.pdfgen import canvas

from .kit import (W, H, register_fonts, QA, TEXTMAP, qa_reset,
                  set_page, set_patch_source)
from . import pages_a as A
from . import pages_b as B
from .custom import custom_page
from .model import check_milestones


def _has_text(v):
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, tuple)):
        return any(_has_text(x) for x in v)
    if isinstance(v, dict):
        return any(_has_text(x) for k, x in v.items() if k != "icon")
    return False


def core_page_is_empty(spec):
    """A Core Features page with no items, bullets or leads is dropped."""
    kind = spec.get("kind")
    if kind == "grid":
        cards = spec.get("cards") or []
        return not any(_has_text(c.get("items")) for c in cards)
    if kind == "list":
        cards = spec.get("cards") or []
        return not any(_has_text(c.get("items")) for c in cards)
    blocks = spec.get("blocks") or []
    return not any(_has_text(b.get("lead")) or _has_text(b.get("bullets"))
                   for b in blocks)


def _apply_no_screens(data):
    """One switch removes every mockup, and the copy reflows to fill the space."""
    flag = bool(data.get("no_screens"))
    for spec in data.get("core_pages") or []:
        spec["no_screens"] = flag
    if isinstance(data.get("page9"), dict):
        data["page9"]["no_screens"] = flag


def page_plan(data, screens):
    """The ordered list of page renderers for this document.

    Built first so a preview can render one page instead of the whole deck.
    """
    _apply_no_screens(data)
    hidden = set(data.get("hidden") or [])
    plan = []

    def add(key, name, fn):
        if key not in hidden:
            plan.append((name, fn))

    add("page1", "Cover", lambda c: A.page1(c, data))
    add("page2", "Company Overview", lambda c: A.page2(c, data))
    add("page3", "App Overview", lambda c: A.page3(c, data))
    data["_screens"] = screens
    add("page4", "Differentiator", lambda c: A.page4(c, data))
    kept = 0
    for i, spec in enumerate(data.get("core_pages", [])):
        spec["_path"] = "core_pages.%d" % i
        if core_page_is_empty(spec) or ("core_pages.%d" % i) in hidden:
            spec["_skipped"] = True      # surfaced in the layout checks
            continue
        spec.pop("_skipped", None)
        kept += 1
        plan.append(("Core Features %d" % kept,
                     lambda c, s=spec: A.core_page(c, s, screens)))
    if data.get("page9", {}).get("include"):
        add("page9", "Marketing Engine", lambda c: A.page9(c, data, screens))
    add("page10", "Technical Requirements", lambda c: B.page10(c, data))
    add("page11", "How We Build", lambda c: B.page11(c, data))
    add("page12", "Milestones & Investment", lambda c: B.page12(c, data))
    add("page13", "Deliverables", lambda c: B.page13(c, data))
    add("page14", "Terms & Protection", lambda c: B.page14(c, data))

    # pages the agent created, on the blank branded plate
    for j, spec in enumerate(data.get("custom_pages") or []):
        key = "custom_pages.%d" % j
        if key in hidden:
            continue
        title = as_page_name(spec)
        plan.append((title, lambda c, s=spec, k=j: custom_page(c, s, screens, k)))

    add("page15", "Next Steps & Signatures", lambda c: B.page15(c, data))
    return plan


def as_page_name(spec):
    head = spec.get("headline") or spec.get("title") or "New page"
    if isinstance(head, (list, tuple)):
        head = " ".join(str(h) for h in head if h)
    return str(head)[:38] or "New page"


def render(data, out_path, screens=None, only=None):
    """only: an index or list of indexes to render, for fast previews."""
    register_fonts()
    qa_reset()
    set_patch_source(data)
    screens = screens or {}
    from .kit import qa_note
    from .model import currency_of
    ok, _, _, msg = check_milestones(data.get("page12", {}),
                                     data.get("meta", {}).get("region", "US"),
                                     currency_of(data))
    plan = page_plan(data, screens)
    for i, spec in enumerate(data.get("core_pages", [])):
        if spec.get("_skipped"):
            QA.append({"page": None, "kind": "page-skipped",
                       "detail": "A Core Features page had no content and was "
                                 "left out of the proposal"})
    if only is None:
        wanted = range(len(plan))
    elif isinstance(only, int):
        wanted = [max(0, min(only, len(plan)-1))]
    else:
        wanted = only

    c = canvas.Canvas(out_path, pagesize=(W, H))
    c.setTitle("%s \u2014 Proposal" % data["meta"].get("project_name", "Proposal"))
    c.setAuthor("Inceptives Digital")
    failures = []
    for i in wanted:
        set_page(i)
        try:
            plan[i][1](c)
        except Exception as exc:                            # noqa: BLE001
            failures.append({"page": i + 1, "name": plan[i][0],
                             "error": "%s: %s" % (type(exc).__name__, exc)})
            _error_page(c, plan[i][0], i + 1, exc)
        c.showPage()
    c.save()
    return {"path": out_path, "pages": len(plan),
            "names": [n for n, _ in plan], "failures": failures,
            "qa": list(QA), "textmap": list(TEXTMAP),
            "milestones_ok": ok, "milestone_warning": msg}


def _error_page(c, name, number, exc):
    """Draw the reason on the page so a preview stays usable."""
    from .kit import register_fonts, wrap
    register_fonts()
    c.setFillColorRGB(0.99, 0.96, 0.94)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColorRGB(0.55, 0.22, 0.18)
    c.setFont("G-Med", 18)
    c.drawString(48, H - 90, "Page %d (%s) could not be drawn" % (number, name))
    c.setFont("G-Light", 11)
    c.setFillColorRGB(0.32, 0.20, 0.18)
    text = "%s: %s" % (type(exc).__name__, exc)
    for i, ln in enumerate(wrap(text, "G-Light", 11, W - 96)[:8]):
        c.drawString(48, H - 122 - i*16, ln)
    c.setFillColorRGB(0.45, 0.40, 0.38)
    c.setFont("G-Light", 10)
    c.drawString(48, H - 300,
                 "Every other page still rendered. Fix the field named above, "
                 "or send this message on.")
