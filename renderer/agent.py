"""The chat agent.

The user types what they want in plain English. The model returns operations,
never a document: it can edit fields, add or remove list items, hide a designed
page, or create a new page. Everything it creates is drawn by the same renderer
on the same branded plate, so a generated page cannot look foreign.
"""
import json
import os
import re

from .extract import _call, _client, _parse_json                # noqa: F401
from .model import ICON_NAMES
from .store import parse

MODEL = os.environ.get("PROPOSAL_AGENT_MODEL",
                       os.environ.get("PROPOSAL_MODEL", "claude-sonnet-5"))

PAGE_KEYS = ["page1", "page2", "page3", "page4", "page9", "page10", "page11",
             "page12", "page13", "page14", "page15"]

LOCKED = ("meta", "page12.total", "page14.cards")

SYSTEM = """You edit an Inceptives Digital proposal on behalf of a salesperson.

You are given a summary of the current proposal and one instruction. You reply \
with operations, never with a whole document.

Operations:
 {"op":"set","path":"page4.one_liner","value":"..."}
 {"op":"append","path":"page10.services","value":{"title":"...","body":"...","icon":"ic_cloud"}}
 {"op":"delete","path":"page3.surfaces.2"}
 {"op":"hide","page":"page9"}                 remove a designed page
 {"op":"show","page":"page9"}                 put it back
 {"op":"add_page","value":{"eyebrow":"...","headline":["line one","line two"],
    "intro":"one or two sentences","columns":2,
    "cards":[{"title":"...","body":"one or two sentences","icon":"ic_shield"}]}}
 {"op":"delete_page","index":0}               remove a page you created
 {"op":"no_screens","value":true}             remove every UI mockup from the
                                              whole proposal (or false to keep)
 {"op":"clear_screen","page":"core_pages.0"}  remove the mockups from one page
 {"op":"clean_area","page":"page4",
  "region":{"x":300,"y":300,"w":280,"h":240},"mode":"clean"}
                                              repair the page artwork inside a
                                              rectangle: use this when someone
                                              marks a blurred, smudged or
                                              leftover patch of BACKGROUND.
                                              mode is "clean" (rebuild from the
                                              page's own colours), "smooth"
                                              (blur it away) or "lighten".
                                              When "pointing_at" has a region,
                                              use that region verbatim.
 {"op":"clean_background","page":"page4","value":true}
                                              page 4's artwork carries a phone
                                              mockup; true swaps in a clean
                                              plate with no mockup
 {"op":"place_image","page":"page4","image":"<image id the user uploaded>"}
                                              put an uploaded image into that
                                              page's device slot
 {"op":"spacing","page":"page10","value":1.2}  open up or tighten the spacing on
                                              a page (1.0 is the design default,
                                              1.3 is airier, 0.85 is tighter)

Worked examples:
 "delete the UI screens from pages 5, 6 and 7" -> [{"op":"no_screens","value":true}]
 "drop the marketing page" -> [{"op":"hide","page":"page9"}]
 "add a page about security" -> [{"op":"add_page","value":{...}}]
 "make the differentiator punchier" -> [{"op":"set","path":"page4.one_liner","value":"..."}]

When "pointing_at" is present the user has marked a spot on the page and their
instruction is about that spot. It names the page, and lists the fields under
the mark with their current text and their character limit. Prefer those fields
over anything else, and keep any rewrite inside the limit given. If the comment
asks for something structural (more space, remove this card, delete this page),
use the matching operation on that page.

Every page in the summary carries the number printed on the PDF. When the user
says "page 8", find the entry with page_number 8 and use its key. Never claim a
page does not exist without checking that list.

Spacing and density ARE things you can change, with the spacing operation. Do
not tell the user to pass it to a designer.

You CAN repair the artwork. If a comment is about the page background rather
than the words — a blurred patch, a smudge, a leftover shape, an area that
looks wrong — use clean_area on the region the user marked. That is a design
fix and it is yours to make. Only say something is impossible when no operation
covers it, and never report a change you did not make.

The one thing outside your reach is redesigning the page: you cannot move the
logo, restyle the waves or change the brand colours.

"uploaded_images" lists images the user has attached. Use place_image with one
of those ids when they ask for an image to go on a page.

Rules:
- Never touch prices, client details or the page 14 legal statements. If asked, \
refuse in the note and make no operation for it.
- A new page needs between two and six cards, a two-line headline, and an \
eyebrow naming the section. Keep card bodies to one or two sentences.
- Match the house voice: plain, confident, no hype, no em-dashes.
- Icons only from the supplied list.
- Change only what was asked. Do not tidy anything else.
- "house_preferences" are things this team has asked for repeatedly on other
  proposals. Apply one only if the instruction is consistent with it, and say
  in the note that you did.

Reply with {"ops":[...],"note":"one short sentence on what you did"} and \
nothing else."""


KEY_FOR_NAME = {
    "Cover": "page1", "Company Overview": "page2", "App Overview": "page3",
    "Differentiator": "page4", "Marketing Engine": "page9",
    "Technical Requirements": "page10", "How We Build": "page11",
    "Milestones & Investment": "page12", "Deliverables": "page13",
    "Terms & Protection": "page14", "Next Steps & Signatures": "page15",
}


def summarise(data):
    """A compact picture of the proposal.

    Pages are listed with the number actually printed on the PDF, because that
    is the number the user will quote. Referring to internal keys made the
    assistant answer "there is no page 8" when page 8 plainly exists.
    """
    from .render import page_plan
    out = {"pages": [], "custom_pages": [], "hidden": data.get("hidden") or [],
           "ui_mockups_shown": not data.get("no_screens")}
    core, custom = 0, 0
    for n, (name, _) in enumerate(page_plan(data, {}), start=1):
        key = KEY_FOR_NAME.get(name)
        if key is None and name.startswith("Core Features"):
            key = "core_pages.%d" % core
            core += 1
        elif key is None:
            key = "custom_pages.%d" % custom
            custom += 1
        entry = {"page_number": n, "key": key, "title": name}
        block = data.get(key) if key.startswith("page") else None
        if isinstance(block, dict):
            head = block.get("headline") or block.get("one_liner") or ""
            entry["heading"] = (" ".join(head) if isinstance(head, list)
                                else str(head))[:90]
        out["pages"].append(entry)
    for i, cp in enumerate(data.get("custom_pages") or []):
        out["custom_pages"].append({"index": i,
                                    "heading": " ".join(cp.get("headline") or [])[:90]})
    out["lists"] = {k: len(data.get(a, {}).get(b, []) if b else data.get(a, []))
                    for k, (a, b) in {
                        "page3.surfaces": ("page3", "surfaces"),
                        "page4.cards": ("page4", "cards"),
                        "page10.stack": ("page10", "stack"),
                        "page10.services": ("page10", "services"),
                        "page12.rows": ("page12", "rows"),
                    }.items()}
    return out


def is_locked(path):
    return any(path == p or path.startswith(p + ".") for p in LOCKED) \
        or path.endswith(".amount")


def chat(data, instruction, client=None, context=None):
    """context describes where the user pointed: which page, which fields sit
    under the mark, and what they currently say. With that, "make this shorter"
    is unambiguous."""
    payload = json.dumps({"proposal": summarise(data),
                          "instruction": instruction,
                          "pointing_at": context or None,
                          "uploaded_images": (context or {}).get("images") or [],
                          "house_preferences": (context or {}).get("preferences") or [],
                          "allowed_icons": ICON_NAMES}, ensure_ascii=False)
    out = _call(_client(client), SYSTEM, payload, 3000, model=MODEL)
    ops = [o for o in (out.get("ops") or []) if isinstance(o, dict)]
    kept, refused = [], []
    for o in ops:
        path = o.get("path", "")
        if path and is_locked(path):
            refused.append(path)
            continue
        kept.append(o)
    note = out.get("note", "")
    if refused:
        note += (" Left alone: %s, which are typed or contractual."
                 % ", ".join(sorted(set(refused))))
    return {"ops": kept, "note": note.strip()}


PLATE_FOR_KEY = {"page1": 1, "page2": 2, "page3": 3, "page4": 4, "page9": 9,
                 "page10": 10, "page11": 11, "page12": 12, "page13": 13,
                 "page14": 14, "page15": 15}


def _page_number(key):
    """Patches are recorded against the plate, which is what gets repaired."""
    if key in PLATE_FOR_KEY:
        return PLATE_FOR_KEY[key]
    if key.startswith("core_pages."):
        return 5            # the grid template; device pages carry their own
    return 4


def apply_ops(data, ops):
    """Apply agent operations to a document. Returns the number applied."""
    applied = 0
    for o in ops:
        kind = o.get("op")
        try:
            if kind == "hide":
                data.setdefault("hidden", [])
                if o["page"] not in data["hidden"]:
                    data["hidden"].append(o["page"])
            elif kind == "show":
                data["hidden"] = [p for p in (data.get("hidden") or [])
                                  if p != o.get("page")]
            elif kind == "clean_area":
                region = o.get("region") or {}
                if region.get("w") and region.get("h"):
                    data.setdefault("patches", []).append(
                        {"page": _page_number(o.get("page", "page4")),
                         "x": float(region.get("x", 0)),
                         "y": float(region.get("y", 0)),
                         "w": float(region["w"]), "h": float(region["h"]),
                         "mode": o.get("mode", "clean")})
            elif kind == "clean_background":
                page = data.setdefault(o.get("page", "page4"), {})
                page["clean_background"] = bool(o.get("value", True))
            elif kind == "place_image":
                page = data.setdefault(o.get("page", "page4"), {})
                page["screen"] = o.get("image", "")
                page["clean_background"] = True
            elif kind == "spacing":
                data.setdefault("spacing", {})[o["page"]] = float(o.get("value", 1.0))
            elif kind == "no_screens":
                data["no_screens"] = bool(o.get("value", True))
            elif kind == "clear_screen":
                key = o.get("page", "")
                if key.startswith("core_pages."):
                    idx = int(key.split(".")[1])
                    pages = data.get("core_pages") or []
                    if 0 <= idx < len(pages):
                        pages[idx]["no_screens"] = True
                elif key == "page9" and isinstance(data.get("page9"), dict):
                    data["page9"]["no_screens"] = True
            elif kind == "add_page":
                data.setdefault("custom_pages", []).append(o["value"])
            elif kind == "delete_page":
                pages = data.get("custom_pages") or []
                idx = int(o.get("index", -1))
                if 0 <= idx < len(pages):
                    pages.pop(idx)
            elif kind in ("set", "append", "insert", "delete", "move"):
                _mutate(data, o)
            else:
                continue
            applied += 1
        except Exception:                                     # noqa: BLE001
            continue
    return applied


def _mutate(data, o):
    keys = parse(o["path"])
    node = data
    for k in keys[:-1]:
        node = node[k]
    last = keys[-1]
    kind = o["op"]
    if kind == "set":
        node[last] = o["value"]
    elif kind == "append":
        node[last].append(o["value"])
    elif kind == "insert":
        node.insert(last, o["value"])
    elif kind == "delete":
        del node[last]
    elif kind == "move":
        node.insert(o["value"], node.pop(last))
