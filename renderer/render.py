"""Turns a proposal JSON into the finished 15-page PDF. No AI, no network."""
from reportlab.pdfgen import canvas

from .kit import W, H, register_fonts, QA, TEXTMAP, qa_reset, set_page
from . import pages_a as A
from . import pages_b as B
from .model import check_milestones


def page_plan(data, screens):
    """The ordered list of page renderers for this document.

    Built first so a preview can render one page instead of the whole deck.
    """
    plan = [("Cover", lambda c: A.page1(c, data)),
            ("Company Overview", lambda c: A.page2(c, data)),
            ("App Overview", lambda c: A.page3(c, data)),
            ("Differentiator", lambda c: A.page4(c, data))]
    for i, spec in enumerate(data.get("core_pages", [])):
        spec["_path"] = "core_pages.%d" % i
        plan.append(("Core Features %d" % (i+1),
                     lambda c, s=spec: A.core_page(c, s, screens)))
    if data.get("page9", {}).get("include"):
        plan.append(("Marketing Engine", lambda c: A.page9(c, data, screens)))
    plan += [("Technical Requirements", lambda c: B.page10(c, data)),
             ("How We Build", lambda c: B.page11(c, data)),
             ("Milestones & Investment", lambda c: B.page12(c, data)),
             ("Deliverables", lambda c: B.page13(c, data)),
             ("Terms & Protection", lambda c: B.page14(c, data)),
             ("Next Steps & Signatures", lambda c: B.page15(c, data))]
    return plan


def render(data, out_path, screens=None, only=None):
    """only: an index or list of indexes to render, for fast previews."""
    register_fonts()
    qa_reset()
    screens = screens or {}
    ok, _, _, msg = check_milestones(data.get("page12", {}),
                                     data.get("meta", {}).get("region", "US"))
    plan = page_plan(data, screens)
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
