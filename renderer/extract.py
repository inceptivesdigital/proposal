"""Turns a call transcript into a complete proposal JSON in one model call.

The model writes content only. It never touches layout, colour or geometry, and
it is not allowed to invent the typed fields (client, company, region, money).
"""
import json
import os
import re

from .model import STATIC_DEFAULTS, ICON_NAMES, check_milestones, money
from .normalize import normalize

MODEL = os.environ.get("PROPOSAL_MODEL", "claude-sonnet-5")
# stage 1 is comprehension, not copywriting, so it stays on a fast model even
# when PROPOSAL_MODEL is set to something slower
BRIEF_MODEL = os.environ.get("PROPOSAL_BRIEF_MODEL", "claude-sonnet-5")
BRIEF_TRANSCRIPT_CHARS = int(os.environ.get("PROPOSAL_BRIEF_CHARS", "40000"))
# stage 1 writes one entry per feature, so a detailed transcript needs room
BRIEF_TOKENS = int(os.environ.get("PROPOSAL_BRIEF_TOKENS", "8000"))
FRONT_TOKENS = int(os.environ.get("PROPOSAL_FRONT_TOKENS", "4000"))
FEATURE_TOKENS = int(os.environ.get("PROPOSAL_FEATURE_TOKENS", "12000"))
MAX_TOKENS = int(os.environ.get("PROPOSAL_MAX_TOKENS", "16000"))
STAGED = os.environ.get("PROPOSAL_STAGED", "1") != "0"
# the two complimentary rows are house standard but not universal
INCLUDE_LAUNCH = os.environ.get("PROPOSAL_INCLUDE_LAUNCH", "1") != "0"
INCLUDE_SUPPORT = os.environ.get("PROPOSAL_INCLUDE_SUPPORT", "1") != "0"
MAX_TRANSCRIPT_CHARS = int(os.environ.get("PROPOSAL_MAX_TRANSCRIPT", "60000"))

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
    transcript = (transcript or "")[:MAX_TRANSCRIPT_CHARS]
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
    return text.strip()


def repair_json(text):
    """Close what is open and drop what does not match.

    A reply is occasionally a bracket out, which is a shame to throw away when
    the content is fine. This walks the string, tracking whether it is inside a
    quote, and rebuilds a balanced document.
    """
    out, stack, in_string, escape = [], [], False, False
    for ch in text:
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
        elif ch in "{[":
            stack.append(ch)
            out.append(ch)
        elif ch in "}]":
            want = "{" if ch == "}" else "["
            if stack and stack[-1] == want:
                stack.pop()
                out.append(ch)
            # a closer that matches nothing is dropped
        else:
            out.append(ch)
    if in_string:
        out.append('"')
    while stack:
        out.append("}" if stack.pop() == "{" else "]")
    return "".join(out)


def _parse_json(text):
    """Models sometimes wrap JSON in a sentence, or miscount a bracket."""
    text = _strip_fences(text)
    for candidate in (text, None):
        if candidate is None:
            start, end = text.find("{"), text.rfind("}")
            if start == -1 or end <= start:
                break
            candidate = text[start:end + 1]
        try:
            return json.loads(candidate)
        except ValueError:
            try:
                return json.loads(repair_json(candidate))
            except ValueError:
                continue
    raise ValueError("no JSON object found in the reply")


def extract(transcript, meta, milestones, total_value, client=None):
    """Returns a proposal dict ready to render."""
    if STAGED:
        return extract_staged(transcript, meta, milestones, total_value, client)
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    try:
        msg = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM,
            messages=[{"role": "user",
                       "content": build_user_prompt(transcript, meta,
                                                    milestones, total_value)}],
        )
    except Exception as exc:                                   # noqa: BLE001
        raise RuntimeError("Model call failed using model %r: %s. Set "
                           "PROPOSAL_MODEL to a model your API key can use."
                           % (model, exc))
    _meter(msg, model, _stage_of(system))
    text = "".join(b.text for b in msg.content if b.type == "text")
    if getattr(msg, "stop_reason", None) == "max_tokens":
        raise RuntimeError(
            "The model ran out of room before finishing the proposal "
            "(%d tokens). Shorten the transcript, or raise PROPOSAL_MAX_TOKENS."
            % MAX_TOKENS)
    try:
        data = _parse_json(text)
    except ValueError as exc:
        raise RuntimeError(
            "The model did not return valid JSON (%s). First 300 characters of "
            "its reply: %s" % (exc, text[:300].replace("\n", " ")))
    return assemble(data, meta, milestones, total_value)


def assemble(generated, meta, milestones, total_value):
    """Merge model output with the boilerplate and the typed money values.

    Amounts come from the user, never the model, so a hallucinated number can
    never reach a client.
    """
    from copy import deepcopy
    # coerce every field before anything downstream sees it, so a model that
    # returns a string where two lines belong cannot break the editor
    d = normalize(deepcopy(generated))
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
    risk = d.pop("_risk_area", "")
    if risk:
        d["page14"]["risk_area"] = risk
    ok, _, _, warning = check_milestones(p12, meta.get("region", "US"))
    d["_warnings"] = [] if ok else [warning]
    return d


# ---------------------------------------------------------------------------
# Staged generation
# ---------------------------------------------------------------------------
# Stage 1 reads the transcript and decides what the product actually is.
# Stages 2 and 3 write copy against that brief, each with a worked example so
# the model has a quality bar to hit rather than inventing a house style.

BRIEF_SYSTEM = """You are a technical pre-sales lead at Inceptives Digital. Read the transcript and produce a factual brief. You are not writing sales copy yet.

Return JSON:
{
 "what_it_is": "one sentence, plain",
 "who_uses_it": ["each distinct user type named in the source"],
 "interfaces": [{"name":"Buyer App","platform":"Web & Mobile","for":"buyers",
                 "features":[{"title":"...","detail":"...","supporting":["..."]}]}],
 "commercial_angle": "the money argument for the client, or null if there isn't one",
 "differentiator": "the single sharpest thing this product does that rivals don't",
 "tech_needs": ["specific technical requirements implied by the features"],
 "store_risk": "the thing most likely to draw app-store scrutiny, or null"
}

Rules: every feature must come from the transcript. Do not pad. If the source is thin, return fewer features. Group features by which interface uses them. An interface with fewer than three features is probably part of another interface. Return only JSON."""

COPY_EXAMPLE = """Worked example of the standard, for a property app:

page1.title: ["Real Estate Management", "Application"]
page3.one_liner: "One platform where buyers search, tour, and make offers and where you watch every listing move in real time."
page4.one_liner: "Know the price before you see the house."
page4.cards[0]: {"title":"Value before you view","body":"An instant valuation on every listing removes the biggest reason buyers walk away."}

Note what these do: name the user's actual job, put the benefit before the mechanism, and stay short enough to read in one breath. Match that standard for this client's business, never that client's words."""

COPY_SYSTEM = """You write proposal copy for Inceptives Digital. You are given a brief and you return JSON for the front pages only.

""" + COPY_EXAMPLE + """

Return exactly:
{"page1":{"title":["line one","line two"],"description":"one sentence"},
 "page3":{"one_liner":"...","description":["para one","para two"],
          "surfaces_heading":"Four Connected Surfaces",
          "surfaces":[{"title":"...","blurb":"one short line","icon":"ic_..."}]},
 "page4":{"one_liner":"short punch","description":"mechanism then business effect",
          "cards":[{"title":"...","body":"one sentence","icon":"ic_..."}]}}

page1.title line two must be short, two or three words. page3.description is two paragraphs: what it unites, then the journey and what the business side gains. page4 has exactly three cards. surfaces_heading must spell the count in words and match the number of surfaces. British-neutral, plain, no hype, no em-dashes. Return only JSON."""

FEATURES_SYSTEM = """You lay out the Core Features pages for an Inceptives proposal, from a brief.

One "grid" page per first interface, max 4 cards, each card a two-line title and a mix of lead lines and bulleted supporting points. If that interface has more features than fit, add one "list" page for it, max 4 cards of up to 4 short items.
Every later interface gets exactly one "device" page: template 7 for a tablet or staff tool, template 8 for a dashboard or owner tool. Max 4 blocks on 7, 6 on 8.

Return:
{"core_pages":[{"template":5,"kind":"grid","eyebrow":"Core Features \u00b7 <Interface> (<Platform>)",
  "headline":["line one","line two"],
  "cards":[{"title":["Two word","Title"],"icon":"ic_...","items":[
     {"text":"lead line, no bullet"},{"text":"supporting point","bullet":true}]}]}],
 "page9":{"include":false},
 "page10":{"stack":[{"title":"Frontend","body":"...","icon":"ic_code"}],
           "services":[{"title":"...","body":"...","icon":"ic_..."}],
           "footnote":"..."},
 "page12_descriptions":["one line per milestone, in order"],
 "page14_risk_area":"the nature of ..."}

Include page9 only if the brief names a commercial angle; if so give it a headline of three short lines, a description, three cards and a promo message.
page10.stack is 4 to 6 core technologies, services 4 to 8 integrations, both specific to this product. Return only JSON."""


def _meter(msg, model, stage):
    """Record what the call cost, so a proposal can be priced."""
    try:
        from .usage import record_model
        u = getattr(msg, "usage", None)
        record_model(model, stage, getattr(u, "input_tokens", 0) or 0,
                     getattr(u, "output_tokens", 0) or 0)
    except Exception:                                         # noqa: BLE001
        pass


def _stage_of(system):
    if system.startswith(TECHNICAL_SYSTEM[:60]):
        return "writing the technical pages"
    if system.startswith(BRIEF_SYSTEM[:60]):
        return "reading the transcript"
    if system.startswith(COPY_SYSTEM[:60]):
        return "writing the front pages"
    if system.startswith(FEATURES_SYSTEM[:60]):
        return "laying out the features"
    return "generating"


def _var_for(system):
    if system.startswith(TECHNICAL_SYSTEM[:60]):
        return "PROPOSAL_TECHNICAL_TOKENS"
    if system.startswith(BRIEF_SYSTEM[:60]):
        return "PROPOSAL_BRIEF_TOKENS"
    if system.startswith(COPY_SYSTEM[:60]):
        return "PROPOSAL_FRONT_TOKENS"
    if system.startswith(FEATURES_SYSTEM[:60]):
        return "PROPOSAL_FEATURE_TOKENS"
    return "PROPOSAL_MAX_TOKENS"


def house_rules_block():
    """Everything this team has corrected more than once, so the same mistake
    is not made on the next client."""
    try:
        from .learn import rules_for_prompt
        lines = rules_for_prompt()
    except Exception:                                         # noqa: BLE001
        return ""
    if not lines:
        return ""
    return ("\n\nCORRECTIONS THIS TEAM HAS MADE BEFORE. These are not "
            "suggestions. Write it their way first time:\n" + "\n".join(lines))


def _call(client, system, payload, max_tokens=8000, model=None):
    model = model or MODEL
    try:
        msg = client.messages.create(
            model=model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": payload}])
    except Exception as exc:                                   # noqa: BLE001
        raise RuntimeError("Model call failed using model %r: %s. Set "
                           "PROPOSAL_MODEL to a model your API key can use."
                           % (model, exc))
    _meter(msg, model, _stage_of(system))
    text = "".join(b.text for b in msg.content if b.type == "text")
    if getattr(msg, "stop_reason", None) == "max_tokens":
        raise RuntimeError(
            "The model ran out of room at %d tokens while %s. Either trim the "
            "transcript to the parts that describe the app, or raise %s."
            % (max_tokens, _stage_of(system), _var_for(system)))
    try:
        return _parse_json(text)
    except ValueError as exc:
        raise RuntimeError("The model did not return valid JSON (%s). Reply "
                           "began: %s" % (exc, text[:300].replace("\n", " ")))


def _client(client=None):
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    return client


def _brief_budget(transcript):
    """Scale the budget with the source, so a long call is not truncated."""
    chars = len(transcript or "")
    return max(BRIEF_TOKENS, min(16000, 2000 + chars // 3))


def make_brief(transcript, meta, client=None):
    """Stage 1. Comprehension only, no sales copy."""
    return _call(_client(client), BRIEF_SYSTEM, json.dumps(
        {"transcript": (transcript or "")[:BRIEF_TRANSCRIPT_CHARS],
         "project_name": meta.get("project_name"),
         "client_company": meta.get("client_company")},
        ensure_ascii=False), _brief_budget(transcript), model=BRIEF_MODEL)


def make_front(brief, meta, client=None):
    """Stage 2. Pages 1, 3 and 4."""
    ctx = {"brief": brief, "client_company": meta.get("client_company"),
           "project_name": meta.get("project_name"), "allowed_icons": ICON_NAMES}
    return _call(_client(client), COPY_SYSTEM + house_rules_block(),
                 json.dumps(ctx, ensure_ascii=False), FRONT_TOKENS)


TECHNICAL_SYSTEM = """You write the closing pages of an Inceptives Digital proposal, from a brief and the feature pages already written.

Return exactly:
{"page9":{"include":false},
 "page10":{"stack":[{"title":"Frontend","body":"...","icon":"ic_code"}],
           "services":[{"title":"...","body":"...","icon":"ic_..."}],
           "footnote":"..."},
 "page12_descriptions":["one line per milestone, in order"],
 "page14_risk_area":"the nature of ..."}

Include page9 only if the brief names a commercial angle; if so give it a headline of three short lines, a description, three cards and a promo message.
page10.stack is 4 to 6 core technologies, services 4 to 8 integrations, both specific to this product and each matching a feature described earlier.
page14_risk_area is a noun phrase beginning with "the", naming what about this app is most likely to draw app-store scrutiny.
British-neutral, plain, no hype, no em-dashes. Return only JSON."""


def make_features(brief, front, meta, milestone_count, client=None):
    """Stage 3. The Core Features pages only, so the request stays short."""
    ctx = {"brief": brief, "front": front, "allowed_icons": ICON_NAMES,
           "client_company": meta.get("client_company"),
           "project_name": meta.get("project_name")}
    return _call(_client(client), FEATURES_SYSTEM + house_rules_block(),
                 json.dumps(ctx, ensure_ascii=False), FEATURE_TOKENS)


def make_technical(brief, front, core_pages, meta, milestone_count,
                   client=None):
    """Stage 4. Commercial page, technical requirements, milestone lines."""
    ctx = {"brief": brief, "front": front, "core_pages": core_pages,
           "allowed_icons": ICON_NAMES,
           "client_company": meta.get("client_company"),
           "project_name": meta.get("project_name"),
           "milestone_count": milestone_count}
    return _call(_client(client), TECHNICAL_SYSTEM + house_rules_block(),
                 json.dumps(ctx, ensure_ascii=False), 6000)


def combine(front, rest, meta, milestones, total_value):
    """Merge the stage outputs into a finished document."""
    data = {}
    data.update(front or {})
    rest = rest or {}
    data["core_pages"] = rest.get("core_pages", [])
    data["page9"] = rest.get("page9", {"include": False})
    data["page10"] = rest.get("page10", {})
    data["page12"] = {"rows": _rows_from(rest.get("page12_descriptions", []),
                                         milestones)}
    data["_risk_area"] = rest.get("page14_risk_area", "")
    return assemble(data, meta, milestones, total_value)


def extract_staged(transcript, meta, milestones, total_value, client=None):
    """Three focused calls instead of one broad one."""
    client = _client(client)
    brief = make_brief(transcript, meta, client)
    front = make_front(brief, meta, client)
    feats = make_features(brief, front, meta, len(milestones), client)
    tech = make_technical(brief, front, feats.get("core_pages", []), meta,
                          len(milestones), client)
    rest = dict(feats)
    rest.update(tech)
    return combine(front, rest, meta, milestones, total_value)


DEFAULT_MILESTONES = [
    ("Project Initiation & Onboarding", "1\u20132 wks"),
    ("UI/UX Wireframes & Prototyping", "1\u20132 wks"),
    ("UI/UX Screen Designs", "1\u20132 wks"),
    ("Web & Mobile Alpha Frontend", "2\u20133 wks"),
    ("Backend, Integration & Beta", "2\u20133 wks"),
    ("Beta Release, Versioning & Testing", "3\u20134 wks"),
]


def _rows_from(descriptions, milestones):
    rows = []
    for i in range(len(milestones)):
        title, dur = (DEFAULT_MILESTONES[i] if i < len(DEFAULT_MILESTONES)
                      else ("Milestone %d" % (i + 1), "2\u20133 wks"))
        desc = descriptions[i] if i < len(descriptions) else ""
        rows.append({"title": title, "duration": dur, "amount": milestones[i],
                     "desc": desc})
    if INCLUDE_LAUNCH:
        rows.append({"title": "Launch & Deployment", "duration": "1\u20132 wks",
                     "amount": "Included",
                     "desc": "Code freeze, app store publishing & production "
                             "deployment"})
    if INCLUDE_SUPPORT:
        rows.append({"title": "Post-Launch Support", "duration": "30 days",
                     "amount": "Included",
                     "desc": "Technical support, bug fixing & performance "
                             "monitoring"})
    return rows


# ---------------------------------------------------------------------------
# Screen specs
# ---------------------------------------------------------------------------

SCREEN_SYSTEM = """You design app screens as structured data. You are given the feature cards from a proposal and you return one screen spec per card.

A spec is: {"id": "<the slot id you were given>", "device": "phone|tablet|web",
            "blocks": [ ... ]}

Block types, use only these:
 {"type":"header","title":"...","right":"optional right-hand text"}
 {"type":"search","text":"what is typed in the field"}
 {"type":"chips","items":["Price","Beds"],"active":0}
 {"type":"hero","caption":"text over the image","title":"...","subtitle":"...","tint":0}
 {"type":"tiles","cols":2,"items":[{"title":"$589k","sub":"3 bd"}],"ratio":0.72}
 {"type":"list","items":[{"title":"...","sub":"...","pill":"New","tone":"blue|green|amber|grey"}]}
 {"type":"kpis","items":[{"label":"Revenue","value":"$128,450","delta":"+12.6%"}]}
 {"type":"chart","title":"Revenue Overview"}
 {"type":"split","left_label":"ASKING","left_value":"$624,000","right_label":"ESTIMATE","right_value":"$612,000"}
 {"type":"fields","items":[{"label":"Email","value":"you@email.com"}]}
 {"type":"button","label":"...","tone":"blue|green"}
 {"type":"social"}
 {"type":"nav","items":["Home","Tours","Profile"],"active":0}

Rules. A phone screen fits about five blocks, a tablet or web screen about four. Put a header first and a nav last on phone screens. Use realistic sample content drawn from this client's business, never lorem ipsum and never another industry's words. Keep every string short enough to fit a phone width. Return {"screens": [ ... ]} and nothing else."""


def make_screens(slots, brief, meta, client=None):
    """slots: [{"id": ..., "device": ..., "title": ..., "points": [...]}]"""
    payload = json.dumps({"slots": slots, "brief": brief,
                          "project_name": meta.get("project_name"),
                          "client_company": meta.get("client_company")},
                         ensure_ascii=False)
    out = _call(_client(client), SCREEN_SYSTEM, payload, 8000)
    return out.get("screens", [])


def screen_slots(data):
    """Every screen this proposal needs, derived from its own content.

    Two cards can share one screen id, so the list is deduplicated: the image
    is built once and used in both places.
    """
    slots = []
    for cp in data.get("core_pages", []):
        if cp.get("kind") == "grid":
            for j, card in enumerate(cp.get("cards", [])):
                title = " ".join(card.get("title") or [])
                slots.append({
                    "id": card.get("screen") or "p%s_c%d" % (cp.get("template"), j),
                    "device": "phone", "title": title or "Screen %d" % (j+1),
                    "points": [i.get("text", "") for i in card.get("items", [])]})
        elif cp.get("kind") == "device":
            wide = "web" if cp.get("template") == 8 else "tablet"
            slots.append({
                "id": cp.get("screen") or "p%s_device" % cp.get("template"),
                "device": wide, "title": cp.get("eyebrow") or "",
                "points": ["%s: %s" % (b.get("title"), b.get("lead"))
                           for b in cp.get("blocks", [])]})
    p9 = data.get("page9") or {}
    if p9.get("include"):
        slots.append({"id": p9.get("screen") or "p9_phone", "device": "phone",
                      "title": "Direct marketing",
                      "points": [c.get("body", "") for c in p9.get("cards", [])]})
    out, seen = [], set()
    for slot in slots:
        if slot["id"] in seen:
            continue
        seen.add(slot["id"])
        out.append(slot)
    return out
