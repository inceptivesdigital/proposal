"""Turns a call transcript into a complete proposal JSON in one model call.

The model writes content only. It never touches layout, colour or geometry, and
it is not allowed to invent the typed fields (client, company, region, money).
"""
import json
import os
import re

from .model import STATIC_DEFAULTS, ICON_NAMES, check_milestones, money

MODEL = os.environ.get("PROPOSAL_MODEL", "claude-sonnet-4-6")

SYSTEM = """You write proposal content for Inceptives Digital, a UK/US app \
development agency. You are given a call transcript or written requirements and \
you return ONE JSON object. You never write layout, styling or geometry.

House rules, applied without exception:

- British-neutral, plain, confident. No hype, no filler, no em-dashes.
- Never invent a client name, company, price, date or timeline. Those are \
supplied to you; use them exactly as given.
- Sales copy is specific to this client's business. Never generic agency language.
- Every feature you list must be traceable to something said in the source. If \
the source is thin, write fewer items rather than padding.
- Icons come only from the supplied list.

Structure you must produce:

page1.title      two lines. Line 1 is the qualifier, line 2 the noun. Keep line 2 short.
page1.description one sentence, what the product is and who it is for.

page3.one_liner  one sentence, max 3 lines when set at 24pt. The promise, not the feature list.
page3.description two paragraphs. First: what the product is and what it unites. \
Second: the user journey, then what the business side gains.
page3.surfaces   one per interface the app actually needs, 2 to 6. title + short blurb + icon.
page3.surfaces_heading must agree with the count, e.g. "Four Connected Surfaces".

page4            the single sharpest commercial differentiator. one_liner is a \
short punch. description explains the mechanism and the business effect. Three \
cards, each a two-line title and one-sentence body.

core_pages       one entry per rendered page. Group features by interface.
  First interface: a "grid" page (max 4 cards, each with items). If it has more \
features than fit, add a "list" page for the same interface (max 4 cards, 4 items each).
  Every later interface: exactly one "device" page, template 7 for a tablet or \
staff tool, template 8 for a dashboard or owner tool. Max 4 blocks on template 7, \
6 on template 8.
  grid card items: mark bullet=true for supporting points, leave it off for lead lines.

page9            include ONLY if the app has a genuine revenue or cost-saving \
angle for the client (owning a customer database, removing a middleman fee, \
repeat revenue). Otherwise set include=false and leave the rest empty.

page10.stack     4 to 6 core technology items. services: 4 to 8 integrations. \
Both must fit the app actually described.
page10.footnote  the cloud cost note.

page12.rows      one per supplied milestone, in order, plus "Launch & Deployment" \
and "Post-Launch Support" with amount "Included". You write title, duration and a \
one-line desc. You do NOT choose amounts; they are supplied.
page12.total_note e.g. "Total \u00b7 12\u201313 working weeks", summing your durations.

page13.need[4]   adapt only if this client must supply a specific data feed or system.
page14.risk_area name the thing about THIS app most likely to draw app-store \
scrutiny, as a noun phrase starting with "the".

Return only the JSON object. No commentary, no code fences."""


def build_user_prompt(transcript, meta, milestones, total_value):
    return json.dumps({
        "transcript": transcript,
        "typed_by_user_use_exactly": {
            "client_contact": meta["client_contact"],
            "client_company": meta["client_company"],
            "project_name": meta["project_name"],
            "region": meta["region"],
            "signer_name": meta["signer_name"],
            "signer_role": meta["signer_role"],
        },
        "milestones_amounts_in_order": milestones,
        "total_value": total_value,
        "allowed_icons": ICON_NAMES,
    }, ensure_ascii=False)


def _strip_fences(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
    return text


def extract(transcript, meta, milestones, total_value, client=None):
    """One model call. Returns a proposal dict ready to render."""
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    msg = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=SYSTEM,
        messages=[{"role": "user",
                   "content": build_user_prompt(transcript, meta, milestones,
                                                total_value)}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text")
    data = json.loads(_strip_fences(text))
    return assemble(data, meta, milestones, total_value)


def assemble(generated, meta, milestones, total_value):
    """Merge model output with the boilerplate and the typed money values.

    Amounts come from the user, never the model, so a hallucinated number can
    never reach a client.
    """
    from copy import deepcopy
    d = deepcopy(generated)
    d["meta"] = dict(meta)
    for key in ("page2", "page11", "page13", "page14", "page15"):
        base = deepcopy(STATIC_DEFAULTS[key])
        base.update({k: v for k, v in d.get(key, {}).items() if v})
        d[key] = base
    p12 = d.setdefault("page12", {})
    p12.setdefault("eyebrow", "Milestones, Timeline & Investment")
    p12.setdefault("headline", ["Pay as each", "milestone is approved"])
    p12["total_value"] = total_value
    p12["total"] = money(total_value, meta.get("region", "US"))
    rows = p12.get("rows", [])
    paid = [r for r in rows if str(r.get("amount", "")).lower() != "included"]
    for row, amount in zip(paid, milestones):
        row["amount"] = amount
    ok, _, _, warning = check_milestones(p12, meta.get("region", "US"))
    d["_warnings"] = [] if ok else [warning]
    return d
