"""The proposal content model.

Every page reads from this and nothing else. Layout, colour, typography and
geometry live in the renderer; this file is purely what changes per client.
"""
from copy import deepcopy

ICON_NAMES = [
    "ic_user_star", "ic_home", "ic_pin", "ic_spark", "ic_calendar", "ic_card",
    "ic_person", "ic_shield", "ic_chart", "ic_db", "ic_chat", "ic_code",
    "ic_server", "ic_cloud", "ic_cloud_up", "ic_search", "ic_mail",
    "ic_mobile", "ic_map", "ic_check",
]

# Boilerplate that is identical on every proposal. The generator never asks the
# model to rewrite these; they are only editable by hand in the UI.
STATIC_DEFAULTS = {
    "page2": {
        "eyebrow": "Company Overview",
        "headline": ["We build the products businesses",
                     "cannot afford to get wrong."],
        "paragraphs": [
            "At Inceptives Digital, technology is only as impactful as the "
            "experience it delivers. For over a decade, our senior team of "
            "designers, developers, and product thinkers has turned ideas into "
            "polished, scalable, market-ready products for startups and "
            "established businesses across the globe.",
            "We don't just write code or design interfaces \u2014 we understand how "
            "products fit into people's lives. Whether launching an MVP against "
            "the clock, redesigning for a better experience, or scaling to "
            "millions of users, we combine creativity, strategy, and technical "
            "excellence. We're not just your development team; we're your "
            "technology partner, committed to seeing {client_company} thrive "
            "long after launch.",
        ],
        "stats": [
            {"value": "10+ yrs", "lines": ["Crafting mobile &", "web products globally"]},
            {"value": "Senior", "lines": ["CTO-led strategy &", "engineering, every build"]},
            {"value": "iOS \u00b7 Android \u00b7 Web", "lines": ["One accountable team,", "end to end"]},
            {"value": "30-day", "lines": ["Post-launch support", "after go-live"]},
        ],
        "awards_heading": "Awards & Recognition",
    },
    "page11": {
        "eyebrow": "How We Build",
        "headline": ["Senior minds on your", "product every stage,",
                     "every decision."],
        "steps": [
            {"title": "Product Intelligence",
             "body": "CTO-led analysis of business model, users & market before a line of code."},
            {"title": "Design with Intent",
             "body": "Every screen stress-tested against real behaviour before development."},
            {"title": "Precision Engineering",
             "body": "Senior engineers own the core \u2014 clean, documented, built to hand over."},
            {"title": "Adversarial Testing",
             "body": "Edge cases & stress loads found in our environment, not yours."},
            {"title": "Precision Launch",
             "body": "Go-live managed with the same rigour as the build itself."},
            {"title": "Continuous Partnership",
             "body": "We stay in \u2014 monitoring, refining & evolving as the business grows."},
        ],
    },
    "page13": {
        "eyebrow": "Deliverables & Responsibilities",
        "headline": ["A clear split, so the", "project stays on schedule"],
        "deliver_head": "What we deliver",
        "need_head": ["What we'll need", "from you"],
        "deliver": [
            "Business analysis translating vision into user flows & requirements",
            "Beta sprint planning ahead of the final release",
            "Lo-fi wireframes & hi-fi UI prototypes aligned to your brand",
            "Fully functional web & mobile app for iOS and Android",
            "Secure, scalable Super Admin dashboard with robust controls",
            "All communication triggers & sharing configured",
            "Rigorous QA, bug fixing & performance optimization",
            "Post-launch support & maintenance per the agreed SLA",
        ],
        "need": [
            "Timely approval of scope, features & design mockups",
            "Brand assets, style guides, fonts & color palette",
            "Active participation in discovery & review cycles",
            "Preferences for developer accounts, hosting, domain & third-party APIs",
            "A compliance guide plus test users / sample data for UAT",
        ],
        "footnote": ("Prompt inputs keep the timeline on track. We encourage open, "
                     "consistent communication to address any changes as they arise."),
    },
    "page14": {
        "eyebrow": "Terms & Client Protection",
        "headline": ["A framework built on", "transparency, fairness",
                     "& accountability"],
        "cards": [
            {"title": "You own everything",
             "body": "Full code, copyrights & IP transfer to {client_company} on "
                     "completion \u2014 with the right to modify and distribute freely."},
            {"title": "Milestone protection",
             "body": "You're only responsible for the last completed milestone; "
                     "ongoing work is billed pro-rata, nothing for incomplete work."},
            {"title": "Fair revisions & refunds",
             "body": "Limited revisions per phase to hit quality standards, with a "
                     "fair, assessment-based refund path if deliverables can't be met."},
            {"title": "Clean handover",
             "body": "On any termination you keep all completed source code, designs "
                     "& assets \u2014 free to continue with any provider."},
            {"title": "Data & privacy first",
             "body": "Auditing rights, data-protection measures & privacy policies "
                     "aligned to relevant laws throughout the engagement."},
            {"title": "One clear agreement",
             "body": "New work is handled via written change orders. Full Terms & "
                     "Conditions are provided as a companion document."},
        ],
        # risk_area is the one per-client string on this page
        "footnote": ("App Store & Google Play acceptance depends on their independent "
                     "review; given {risk_area}, minor adjustments may be required to "
                     "meet store guidelines."),
        "risk_area": "the nature of the app's core functionality",
    },
    "page15": {
        "eyebrow": "Next Steps",
        "headline": "Let's start building.",
        "steps": [
            "Finalize approval of scope, pricing & milestones",
            "Approve the design brief & wireframe prototypes",
            "Lock the technical architecture plan",
            "Begin development on the planned sprint",
            "Staging, QA & deployment \u2014 launch & monitor",
        ],
        "help_line": "Have questions or need help with any deliverable? We're here.",
        "contact": ["info@inceptivesdigital.com", "(469) 788-8527"],
        "sign_head": "Signatures",
        "sign_note": ("By signing below, both parties acknowledge and agree to the "
                      "terms outlined in this proposal."),
    },
}

REQUIRED_TYPED = [
    "client_contact", "client_company", "project_name", "region",
    "signer_name", "signer_role",
]


def blank():
    """An empty proposal with the boilerplate already filled in."""
    return {
        "meta": {
            "client_contact": "", "client_company": "", "project_name": "",
            "region": "US",          # "US" or "UK"
            "signer_name": "", "signer_role": "Account Strategist",
            "date": "",
        },
        "page1": {"title": ["", ""], "description": ""},
        "page3": {"eyebrow": "", "one_liner": "", "description": ["", ""],
                  "surfaces_heading": "", "surfaces": []},
        "page4": {"eyebrow": "The Differentiator", "one_liner": "",
                  "description": "", "cards": []},
        "core_pages": [],            # pages 5-8, one entry per rendered page
        "page9": {"include": False, "eyebrow": "Direct Marketing Engine",
                  "headline": ["", "", ""], "description": "", "cards": [],
                  "promo": {"greeting": "", "lines": ["", ""], "button": ""},
                  "screen": ""},
        "page10": {"eyebrow": "Technical Requirements",
                   "headline": ["Built modern,", "Built to scale"],
                   "stack": [], "services": [], "footnote": ""},
        "page12": {"eyebrow": "Milestones, Timeline & Investment",
                   "headline": ["Pay as each", "milestone is approved"],
                   "total": "", "total_note": "", "rows": []},
        "page2": deepcopy(STATIC_DEFAULTS["page2"]),
        "page11": deepcopy(STATIC_DEFAULTS["page11"]),
        "page13": deepcopy(STATIC_DEFAULTS["page13"]),
        "page14": deepcopy(STATIC_DEFAULTS["page14"]),
        "page15": deepcopy(STATIC_DEFAULTS["page15"]),
    }


CURRENCY = {"US": "$", "UK": "\u00a3"}


def money(value, region="US"):
    """2000 -> $2,000 . Strings pass through untouched (e.g. 'Included')."""
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    try:
        return "%s%s" % (CURRENCY.get(region, "$"), "{:,}".format(int(value)))
    except (TypeError, ValueError):
        return str(value)


def check_milestones(page12, region="US"):
    """Returns (ok, stated_total, milestone_sum, message).

    Sending a proposal whose milestones do not equal the stated total is the kind
    of error that costs a deal, so this runs before every render.
    """
    rows = page12.get("rows", [])
    amounts = [r.get("amount") for r in rows
               if isinstance(r.get("amount"), (int, float))]
    total = page12.get("total_value")
    if total is None or not amounts:
        return True, total, sum(amounts), ""
    s = sum(amounts)
    if s == total:
        return True, total, s, ""
    diff = s - total
    msg = ("Milestone amounts sum to %s but the stated total is %s (%s %s). "
           "Adjust the middle milestones, never the first or last."
           % (money(s, region), money(total, region),
              "over by" if diff > 0 else "under by",
              money(abs(diff), region)))
    return False, total, s, msg
