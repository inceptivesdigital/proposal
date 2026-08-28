# Content specification
## What to write on every page, in what voice, and how long

Companion to `HANDOVER.md`. That document says where text goes; this one says
what the text should be.

Every character limit here was **measured against the real font at the real
size in the real column width**. They are the point at which the renderer starts
shrinking type. Write to the target, treat the maximum as a hard ceiling.

---

# House voice

Applies to every string on every page.

**Do**
- Plain, confident, British-neutral. Write as a senior engineer would speak to a
  business owner who is paying.
- Name the reader's actual job. "Know the price before you see the house" beats
  "Leveraging AI-driven valuation intelligence".
- Benefit first, mechanism second.
- Concrete nouns from the client's own world: listings, viewings, bingo nights,
  post commander, salon chair.
- Short sentences. One idea each.

**Never**
- Em-dashes. Use a comma or a full stop.
- Hype words: seamless, cutting-edge, revolutionary, robust, leverage, empower,
  unlock, game-changing, world-class, best-in-class, state-of-the-art.
- Filler openers: "In today's fast-paced world", "We are excited to".
- Padding to fill a slot. Fewer, better items always.
- Any fact not present in the transcript. If the source is thin, write less.
- Inventing a client name, price, date, timeline or headcount.

**Traceability rule.** Every feature, integration and claim must map to
something actually said in the transcript. If you cannot point at the sentence
it came from, delete it.

**Two glyphs are unavailable** in the brand font: `·` and `•`. Do not use them
in body copy. The renderer handles the middle dot in eyebrow lines itself.

---

# Page 1 — Cover

| Field | Target | Max | Lines |
|---|---|---|---|
| `title[0]` | 12–18 chars | **19** | 1 |
| `title[1]` | 6–10 chars | **11** | 1 |
| `description` | 130–170 chars | **196** | 4 |

**Title.** Two lines, printed at 52pt and 73pt. Line 1 is the qualifier, line 2
is the noun, and line 2 is the bigger one, so it must be short.

- Good: `["Real Estate Management", "Application"]`, `["VFW Post", "Member App"]`
- Bad: `["The VFW Post Member", "Application Platform"]` — line 2 too long, and
  it reads as a sentence broken in half rather than two deliberate lines.

**Description.** One sentence. What the product is and who it is for. No
features.

> An AI-powered property discovery and transaction platform that lets buyers
> value, tour and secure a home with confidence.

---

# Page 2 — Company Overview

**Static.** Do not rewrite. The only variable is the client company name, which
the renderer interpolates into the closing sentence of paragraph two.

Check that it reads correctly with the client's name in place. "committed to
seeing VFW Post 1234 thrive long after launch" is fine; a very long company name
may push the paragraph to an extra line.

---

# Page 3 — Overview and connected surfaces

| Field | Target | Max | Lines |
|---|---|---|---|
| `one_liner` | 90–115 chars | **123** | 3 |
| `description[0]` | 320–380 chars | **400** | 5 |
| `description[1]` | 400–460 chars | **480** | 6 |
| `surfaces[].title` | 12–18 chars | **21** | 1 |
| `surfaces[].blurb` | 40–80 chars | **96** | 4 |

**One-liner.** The promise, not the feature list. It should survive being read
aloud in one breath. Aim for a two-part structure: what the user gets, and what
the owner gets.

> One platform where buyers search, tour, and make offers and where you watch
> every listing move in real time.

**Paragraph 1.** What the product is and what it unites. Name the user types.
End by listing the capabilities it brings together, four to six of them.

**Paragraph 2.** The journey in order, then what the business side gains. Start
with the primary user, end with "Meanwhile, staff and ownership gain…".

**Surfaces.** One per interface the app genuinely needs, between two and six.
Title is the interface name, blurb is one short line of what it does.

`surfaces_heading` must spell the count in words and agree with the number of
surfaces: "Two Connected Surfaces", "Four Connected Surfaces".

Two to three surfaces is normal for a small build. Do not invent a fourth to
fill the row; the renderer re-spaces.

---

# Page 4 — The Differentiator

| Field | Target | Max | Lines |
|---|---|---|---|
| `one_liner` | 24–30 chars | **31** | 1 |
| `description` | 240–280 chars | **294** | 7 |
| `cards[].title` | 18–26 chars | **28** | 2 |
| `cards[].body` | 70–95 chars | **100** | 4 |

This page carries the single sharpest commercial argument. Choose one thing,
not three.

**One-liner.** Very short, and it must fit on one line. This is the hardest
constraint in the deck.

- Good: `Know the price before you see the house.` (39 chars, shrinks slightly)
- Good: `Nobody misses the night again.`
- Bad: `Our AI-powered simulation engine transforms the customer journey` — too
  long, and it describes the mechanism rather than the outcome.

**Description.** Mechanism, then business effect. Two or three sentences. End on
money or time saved.

> Every listing carries an instant valuation built from comparable sales, price
> history, and local trends. Buyers see whether a home is priced fairly before
> they book a viewing, and sellers see what the market will actually pay.
> Certainty up, wasted viewings down, negotiation stronger.

**Cards.** Exactly three. Each title is two short lines; each body is one
sentence saying why it matters commercially.

If you can only find two genuine differentiators, say so rather than padding.
The renderer reports the empty slot and the page shows a gap, which is a
prompt to fix the content, not to invent a third.

---

# Pages 5 to 8 — Core Features

One page per entry in `core_pages`. Group features by which interface uses them.

## Page 5 template — `kind: "grid"`

Max 4 cards, each with a UI screen.

| Field | Target | Max | Lines |
|---|---|---|---|
| `cards[].title[0]` and `[1]` | 10–17 chars each | **19** | 1 each |
| `cards[].items[].text` left column | 40–55 chars | **60** | 2 |
| `cards[].items[].text` right column | 35–48 chars | **52** | 2 |

Four to five items per card. Structure them as: a lead line with no bullet, then
one or two bulleted supporting points, then optionally another lead line.

```json
"items": [
  {"text": "Register by email, phone, or social account"},
  {"text": "Secure login & account authentication", "bullet": true},
  {"text": "Profile with saved searches, budget & must-haves", "bullet": true},
  {"text": "Personalized criteria walkthrough"},
  {"text": "Alert preferences set at onboarding", "bullet": true}
]
```

Lead lines state the capability. Bullets add specifics. Use `&` rather than
"and" to save width.

## Page 6 template — `kind: "list"`

Only when the first interface has more features than fit on the grid page.
Exactly 4 cards, exactly 4 items each, one line per item.

| Field | Target | Max | Lines |
|---|---|---|---|
| `cards[].title` | 20–32 chars | **37** | 1 |
| `cards[].items[]` | 40–54 chars | **58** | 1 |

Items are single lines and get a check mark. Write them as capabilities, not
sentences. No full stops.

> Pick a viewing slot with live agent availability
> Automated reminders ahead of the visit

## Pages 7 and 8 templates — `kind: "device"`

One page per later interface. Template 7 for tablet or staff tools, max 4
blocks. Template 8 for dashboards or owner tools, max 6 blocks.

| Field | Target | Max | Lines |
|---|---|---|---|
| `intro` (template 7 only) | 140–170 chars | **177** | 3 |
| template 7 `blocks[].title` | 18–28 chars | **30** | 1 |
| template 7 `blocks[].lead` and bullets | 55–75 chars | **82** | 2 |
| template 8 `blocks[].title` | 20–30 chars | **34** | 1 |
| template 8 `blocks[].lead` and bullets | 60–85 chars | **92** | 2 |

Each block: a title, a lead line stating the capability, and zero to two
bullets adding specifics. Template 8 blocks are tighter, so keep them shorter
even though the character count allows more.

**Eyebrow format**, all four templates:
`Core Features · <Interface Name> (<Platform>)`
e.g. `Core Features · Agent Interface (In-Office Tablet)`

**Headlines** are two lines and should describe the outcome for that interface,
not the interface itself.

- Good: `["Your team walks in", "already knowing the day"]`
- Bad: `["Agent Tablet", "Interface Features"]`

---

# Page 9 — Direct Marketing Engine

**Include this page only when the transcript names a genuine commercial angle**:
owning a customer database, removing a middleman fee, driving repeat revenue,
replacing print or advertising spend. Otherwise set `include: false` and the
page is dropped from the deck entirely. Do not force it.

| Field | Target | Max | Lines |
|---|---|---|---|
| `headline[0..2]` | 12–16 chars each | **18** | 1 each |
| `description` | 230–260 chars | **270** | 5 |
| `cards[].title` | 14–19 chars | **20** | 1 |
| `cards[].body` | 55–70 chars | **78** | 3 |
| `promo.greeting` | 8–14 chars | **26** | 1 |
| `promo.lines[0..1]` | 20–26 chars each | **26** | 1 each |

**Headline.** Three short lines. It is set at 36pt, so each line is very short.

> `["A buyer list you", "own and can reach in", "one tap."]`

**Description.** How the database is built, what can be sent, and what it
replaces. End on the cost that disappears.

> …no portal fees, no per-lead charges, no rented audience.

**Cards.** Exactly three: build the database, message directly, drive repeat
revenue. Adapt the wording to the client's business.

**Promo.** The floating message on the phone. It must be a believable
notification for this client, and it carries the whole argument.

> greeting: `Hi Sarah!`
> lines: `Price drop on 22 Larkin Way.` / `Now $598,000, down $26k.`
> button: `View home`

---

# Page 10 — Technical Requirements

| Field | Target | Max | Lines |
|---|---|---|---|
| `stack[].title` | 8–18 chars | **21** | 1 |
| `stack[].body` | 55–80 chars | **87** | 3 |
| `services[].title` | 16–24 chars | **27** | 1 |
| `services[].body` | 40–65 chars | **74** | 2 |
| `footnote` | 130–150 chars | **156** | 3 |

**Stack**, left column, 4 to 6 items: the core technology choices. Frontend,
Backend, Cloud Hosting, Database, and anything the features actually demand
(search indexing, real-time, geospatial).

**Services**, right column, 4 to 8 items: third-party integrations. Each must
correspond to a feature described earlier in the deck. If the proposal never
mentions payments, do not list Stripe.

Include `App Store & Google Play` with the fee line as the last service when
the app ships to stores.

**Specificity is the whole point of this page.** "PostgreSQL + PostGIS for
geospatial search & saved areas" earns trust. "Modern scalable database" does
not.

**Footnote** is the cloud cost note. Keep the existing wording unless the
hosting story genuinely differs.

---

# Page 11 — How We Build

**Static.** Six numbered steps describing how Inceptives works. No client
content at all. Do not touch.

---

# Page 12 — Milestones and Investment

| Field | Target | Max | Lines |
|---|---|---|---|
| `rows[].title` | 22–38 chars | **45** | 1 |
| `rows[].duration` | as shown | — | 1 |
| `rows[].desc` | 95–125 chars | **140** | 2 |
| `total_note` | as shown | — | 1 |

**Amounts and the total are typed by the user, never written here.**

**Titles** follow the house sequence and rarely change:

1. Project Initiation & Onboarding — 1–2 wks
2. UI/UX Wireframes & Prototyping — 1–2 wks
3. UI/UX Screen Designs — 1–2 wks
4. Web & Mobile Alpha Frontend — 2–3 wks
5. Backend, Integration & Beta — 2–3 wks
6. Beta Release, Versioning & Testing — 3–4 wks
7. Launch & Deployment — 1–2 wks — **Included**
8. Post-Launch Support — 30 days — **Included**

**Descriptions** are where this page earns its keep. Each must name what is
actually built in that phase, for this client.

- Good: `APIs, PostGIS search, valuation engine, payments & beta build`
- Bad: `Backend development and integration work`

`total_note` format: `Total · 12–13 working weeks`, summing the durations.

The last two rows are marked green "Included" with no payment. Both are
optional per proposal.

---

# Page 13 — Deliverables and Responsibilities

**Near-static.** Eight deliverables and five client responsibilities, fixed
counts because the check marks and arrows are part of the artwork.

| Field | Target | Max | Lines |
|---|---|---|---|
| `deliver[]` | 45–65 chars | **74** | 2 |
| `need[]` | 55–85 chars | **99** | 3 |

Change only `need[4]`, the client-supplied dependency, and only when this client
must provide something specific.

- Property platform: `Listing feed / MLS access, test users & sample data for UAT`
- Booking platform: `Staff rota, service list & sample data for UAT`
- Default: `A compliance guide plus test users / sample data for UAT`

---

# Page 14 — Terms and Client Protection

**Near-static.** Six protection cards. Do not rewrite the legal wording.

Two things change every proposal:

**1. Client company** in the IP-transfer card. The renderer interpolates it.

**2. `risk_area`** — the thing about this specific app most likely to draw
app-store scrutiny.

| Field | Target | Max |
|---|---|---|
| `risk_area` | 45–70 chars | **75** |

Write it as a noun phrase beginning with "the", because it is dropped into
"given {risk_area}, minor adjustments may be required".

- Property app: `the app's use of location data and third-party listing feeds`
- Community app: `the app's use of push notifications and member-only content`
- Health app: `the nature of the health data the app collects`
- Fintech: `the app's handling of payment credentials`

Generic filler here wastes a genuinely useful clause. Name the real exposure.

---

# Page 15 — Next Steps and Signatures

**Near-static.** Five numbered steps.

| Field | Target | Max | Lines |
|---|---|---|---|
| `steps[]` | 35–55 chars | **63** | 1 |

Signer details come from the typed fields, never written.

Change the steps only if the engagement genuinely differs, for example a
discovery phase before the build.

---

# Quick reference

| Page | Fields to write | Roughly |
|---|---|---|
| 1 | title ×2, description | 3 |
| 2 | — | static |
| 3 | one_liner, 2 paragraphs, heading, 2–6 surfaces | 6–14 |
| 4 | one_liner, description, 3 cards | 8 |
| 5 | eyebrow, headline ×2, up to 4 cards × ~5 items | ~25 |
| 6 | eyebrow, headline ×2, 4 cards × 4 items | 23 |
| 7 | eyebrow, headline ×2, intro, up to 4 blocks | ~16 |
| 8 | eyebrow, headline ×2, up to 6 blocks | ~22 |
| 9 | headline ×3, description, 3 cards, promo | 13 |
| 10 | 4–6 stack, 4–8 services, footnote | 11–15 |
| 11 | — | static |
| 12 | up to 8 titles + descriptions, total note | ~17 |
| 13 | one dependency line | 1 |
| 14 | risk_area | 1 |
| 15 | — | static |

---

# Self-check before returning content

1. Does every feature trace to a sentence in the transcript?
2. Any em-dashes, `·` or `•` in body copy? Remove them.
3. Any hype words from the banned list?
4. Does `surfaces_heading` match the surface count in words?
5. Is page 4 carrying exactly three cards with real content?
6. Is page 9 included only because a real commercial angle exists?
7. Does every service on page 10 correspond to a feature described earlier?
8. Is `risk_area` specific to this app?
9. Is any field over its maximum? Cut rather than let the renderer shrink type.
10. Read the one-liners aloud. If you run out of breath, they are too long.
