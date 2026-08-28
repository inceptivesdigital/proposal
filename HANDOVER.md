# Inceptives Digital — Proposal Creator
## Complete system specification and rebuild brief

Written for a developer or coding agent rebuilding this system from scratch.
It contains the working architecture, every measurement that was recovered by
hand, the decisions that turned out to be right, and — in its own section — the
mistakes that cost the most time, so they are not repeated.

Reference implementation: the `proposal-creator` repository this document ships
with. It works. Read it when a description here is ambiguous.

Companion document: **`CONTENT-SPEC.md`** — what to write in every field, in what
voice, with a measured character limit for each. This document covers structure
and position; that one covers words.

---

# 1. What this system is

Inceptives Digital is a UK/US app development agency. Their sales team writes
15-page PDF proposals for prospective clients. Every proposal uses the same
designed template; only the words, prices and app screenshots change.

The system turns a **call transcript** into a **finished 15-page PDF** in about
a minute, keeps every page editable, and never lets the branding drift.

**Non-negotiables**

1. Every proposal must be visually identical to the template. No drift, ever.
2. The AI writes words. It never writes prices, client names or legal terms.
3. A proposal stays editable after it has been sent to a client.
4. Cost per proposal should be cents, not dollars.

---

# 2. The one architectural decision that matters

> **Layout is code. Content is data. The model only ever writes the data.**

Each page is a fixed background image (a "plate") plus a small block of JSON.
A renderer draws text onto the plate at coordinates measured from the original
design. The AI produces the JSON and nothing else.

This is why branding cannot drift: there is no code path in which a model
influences position, size, colour or typography.

Everything else in this document follows from that decision.

```
transcript ──► [3 model calls] ──► proposal.json ──► [renderer] ──► PDF
                                        ▲
                                        │
                                   editor UI
```

---

# 3. The source material and its traps

The client supplies the template as PDFs (and, better, PSDs). Three traps,
each of which cost real time.

## 3.1 The text in the PDFs is scrambled

Every character in the supplied PDFs is shifted **two positions backwards in
the font's internal glyph order**. The files render gibberish in every PDF
viewer — confirmed independently in Poppler and PDFium.

To recover the real text:

1. Read each embedded CFF subset. Glyph names are `cidNNNNN`, where `NNNNN` is
   the glyph id in the original font.
2. The true character is the glyph at `cid + 2` in the **real** Glancyr font.
3. Build `gid -> char` from the real font's cmap, preferring ASCII codepoints
   when several map to one glyph, and mapping ligature glyph names
   (`f_i` -> `fi`) explicitly.

Without this you cannot read the client's own copy. Do not skip it: page 2 and
page 14 both contain the previous client's name buried in what looks like
boilerplate.

## 3.2 PSD is the better input

`psd-tools` reads the PSDs directly and gives:

- correct, unscrambled text
- exact layer bounding boxes
- the ability to hide layers and re-render, which yields a **clean background
  plate for free**

If a page is available as PSD, use it. Extracting a plate from a PDF means
erasing baked-in elements by hand (§4.2).

## 3.3 The font

Glancyr, supplied as OTFs plus a variable TTF.

- The OTFs are CFF-flavoured and reportlab cannot embed them.
- Instantiate static TTFs from the variable font instead:
  `wght 250 = ExtraLight, 400 = Light, 550 = Regular, 700 = Medium,
   850 = SemiBold, 1000 = Bold`, `ital = 0`.
- Verify advance widths against the shipped OTFs character by character. They
  matched exactly, so the instances are safe substitutes.

**Missing glyphs.** Glancyr has no `·` (U+00B7) and no `•` (U+2022). It does
have `—` (U+2014) and `’`. Any middle dot must be drawn in Helvetica while the
surrounding words stay in Glancyr. This affects the eyebrow lines
("Core Features · Buyer App"), the milestone timeline note, and the signature
block subtitles.

---

# 4. Plates

## 4.1 What a plate is

A 300dpi A4 JPEG (2480 × 3508) containing the page artwork: background,
logo, card frames, icon tiles, decorative rules. **No text, no icons, no
device mockups.**

## 4.2 Cleaning a plate

Extract image 0 from the page PDF, then erase everything that must become
dynamic:

- icon glyphs inside icon tiles (they would double up under vector icons)
- checkmark glyphs
- UI mockups and device frames
- numbered badges
- anything whose count can change

Erase by interpolating across the region from its neighbours, then blur the
seam. Two techniques, chosen by what surrounds the region:

- **Horizontal blend** for small regions inside a flat card.
- **Vertical blend plus heavy blur** for large regions over gradient artwork.
  A light blur leaves visible vertical banding — this happened on pages 7 and
  8 and had to be redone with a much larger blur radius and a feathered left
  edge so the wave artwork fades rather than stopping dead.

**Never paste a band from the rendered original into a plate.** It drags the
scrambled text in with it. This was tried on page 2 and had to be reverted.

## 4.3 Which pages need what

| Page | Erase from plate |
|---|---|
| 1 | nothing (plate is clean) |
| 2 | nothing. **Page 2 has no logo** — the heading starts at the top |
| 3 | the four surface cards (they are artwork; making the count dynamic means redrawing them as vector) |
| 4 | the three differentiator icon glyphs |
| 5 | four UI mockups, four icon glyphs |
| 6 | four icon glyphs, sixteen checkmarks |
| 7 | the whole tablet device, four icon glyphs |
| 8 | the whole laptop device, six icon glyphs |
| 9 | the phone mockup and floating card, three icon glyphs |
| 10 | supplied as PSD — hide text and icon layers, re-render |
| 11 | nothing |
| 12 | all row cards, all numbered badges, the total pill |
| 13 | nothing (counts are fixed at 8 and 5) |
| 14 | nothing (six cards fixed) |
| 15 | nothing |

Pages 3, 7, 8 and 9 lose wave artwork that sat behind the erased elements.
It is unrecoverable from a flattened export. **Ask the client for the
background layer as a separate PNG** for these pages; the PSD route gives it
free.

---

# 5. Page inventory

A4, 595.2 × 841.92 points. All coordinates below are **PDF points with a
bottom-left origin**, and every `y` is a **text baseline**, not a bounding-box
top. Getting this wrong shifts every line by the font descender.

| # | Page | Nature |
|---|---|---|
| 1 | Cover | variable |
| 2 | Company Overview | static, plus the client name in the closing sentence |
| 3 | App overview + connected surfaces | variable, dynamic surface count |
| 4 | The Differentiator | variable, exactly 3 cards |
| 5–8 | Core Features | one page per entry in `core_pages[]` |
| 9 | Direct Marketing Engine | optional — include only when a commercial angle exists |
| 10 | Technical Requirements | variable, dynamic count in both columns |
| 11 | How We Build | fully static |
| 12 | Milestones & Investment | variable, dynamic rows, sum-checked |
| 13 | Deliverables & Responsibilities | near-static, editable |
| 14 | Terms & Client Protection | near-static; client name + risk area per client |
| 15 | Next Steps & Signatures | variable signers |

## 5.1 Core Features page templates

Three shapes, chosen by what the interface needs:

- **`kind: "grid"`** (template 5). 2×2 cards, each a two-line title, a mix of
  lead lines and bulleted points, and a UI screen on the right. Max 4 cards.
- **`kind: "list"`** (template 6). Same interface continued, 4 checklist cards
  of up to 4 items, no visuals.
- **`kind: "device"`** (templates 7 and 8). Feature blocks down the left and
  one large device screen on the right. Template 7 = tablet, max 4 blocks.
  Template 8 = web dashboard, max 6 blocks.

**Rule:** the first interface gets a grid page, plus a list page if it has more
features than fit. Every later interface gets exactly one device page.

## 5.2 Measured geometry

These numbers were recovered by measuring the client's files. They are the
most expensive thing in this document. Copy them exactly.

```python
W, H = 595.2, 841.92

P1 = dict(title_x=[52.8, 51.2], title_y=[609.87, 542.37],
          title_size=[52.29, 73.50], title_maxw=[491, 415],
          body_x=53.4, body_y=473.95, body_lead=20, body_size=14, body_maxw=330,
          blocks=[(128.2, 323.75, 302.30, 288.85),
                  (128.9, 224.87, 203.42, 191.53),
                  (129.2, 125.03, 106.22, None)])
# title line 1 near-black #070707, line 2 blue #4460A9

P2 = dict(eyebrow=(34.1, 734.8, 39.84), headline=(34.1, [695.0, 668.0], 26.08),
          body_x=34.0, body_y=637.2, body_lead=16.0, body_size=12.0,
          body_maxw=396, para_gap=32.0,
          stat_x=[67.3, 199.1, 313.1, 468.1], stat_y=328.4, stat_size=18.0,
          sub_x=[[59.2, 49.5], [185.7, 177.5], [313.0, 340.6], [453.2, 472.8]],
          sub_y=[305.9, 293.9], sub_size=9.0, awards=(210.0, 195.7, 16.02))

P3 = dict(head_x=42.2, head_y=656.5, head_lead=26.55, head_size=24.70,
          head_maxw=505, body_x=42.2, body_y=572.4, body_lead=15.30,
          body_size=11.24, body_maxw=430,
          h_cx=297.6, h_y=338.5, h_size=18.97,
          rule=dict(cx=297.6, y=331.9, w=113.2, h=1.2),
          row=dict(x0=44.4, x1=550.5, gutter=13.0, top=318.0, bot=108.2,
                   radius=9.0, icon_cy=269.9, icon_size=34.0, title_dy=92.3,
                   rule_dy=103.0, rule_w=21.7, rule_h=1.5, body_dy=119.6,
                   body_lead=14.4, title_size=10.99, body_size=9.99))

P4 = dict(title_x=41.3, title_y=[651.5, 606.5], title_size=47.24,
          one_x=41.3, one_y=568.4, one_size=23.26, one_maxw=360, one_lead=24,
          divider=dict(x=42.0, y=552.0, w=89.0, h=1.0),
          desc_x=42.0, desc_y=526.9, desc_lead=20.9, desc_size=13.58,
          desc_maxw=276,
          icon_cx=[73.0, 250.5, 426.5], icon_cy=254.9, icon_box=25.0,
          title2_x=[107.9, 285.2, 462.1], title2_y=[257.0, 243.1],
          title2_size=13.97, title2_maxw=95,
          body_x=[55.5, 232.1, 406.8], body_y=187.8, body_lead=23.0,
          body_size=12.0, body_maxw=142)
# "The" near-black, "Differentiator" blue #4460A9, divider #C6CBDB

P5 = dict(eyebrow=(36.1, 721.3, 15.53), headline=(36.6, [675.9, 638.3], 37.65),
          icon=[(66.0, 577.0), (333.0, 577.0), (66.0, 313.7), (333.0, 313.7)],
          tx=[95.5, 361.7, 95.5, 362.6],
          ty=[[580.0, 563.0], [580.2, 563.2], [316.7, 299.7], [316.9, 299.9]],
          bx=[47.8, 317.8, 47.8, 314.4], by=[530.0, 530.0, 264.8, 264.8],
          bw=[136, 118, 122, 112],
          slots=[(193, 275, 273, 475), (440, 552, 265, 471),
                 (178, 283, 532, 729), (435, 550, 525, 733)])
GRID_BOTTOM = {0: 356.0, 1: 356.0, 2: 92.0, 3: 92.0}   # floor of each card
# body flows at lead 12.0 with a 12.0 gap between items

P6 = dict(eyebrow=(42.2, 726.2, 14.0), headline=(42.2, [674.3, 639.3], 35.03),
          icon_x=94.3, icon_y=[551.0, 408.0, 249.0, 116.5],
          title_x=157.1, title_y=[587.5, 445.4, 278.1, 148.8],
          item_x=[170.7, 171.9, 171.9, 171.9],
          item_y=[[565.3, 542.3, 519.3, 496.3], [423.2, 400.2, 377.2, 354.2],
                  [255.9, 236.4, 216.9, 197.4], [129.4, 109.9, 90.4, 70.9]],
          check_x=161.8, item_w=262)
# checkmark centre y = item baseline + 3.0, diameter 9.6

P7 = dict(eyebrow=(42.2, 708.7, 14.0), headline=(42.2, [657.1, 620.1], 36.99),
          intro=dict(x=42.6, y=593.5, lead=18.0, size=12.44, maxw=352),
          icon_x=66.5, icon_box=24, anchor=[493.4, 382.0, 244.0, 135.3],
          title_x=108.0, body_x=112.1, body_w=176, device=(300, 200, 268, 372))
# icon centre y = anchor - 13.9 ; body flows from anchor - 14.9, lead 11.5, gap 8.5

P8 = dict(eyebrow=(36.2, 719.2, 14.0), headline=(36.2, [684.2, 655.2], 30.49),
          icon_x=53.8, icon_box=23,
          icon_y=[601.8, 495.5, 390.3, 287.4, 195.1, 101.5],
          anchor=[620.0, 512.9, 405.9, 300.8, 212.5, 114.1],
          title_x=88.1, body_x=92.8, body_w=176, device=(296, 250, 282, 330))
# title 10.50 Medium, body 8.0 Light, lead 11.0, gap 7.5

P9 = dict(eyebrow=(35.5, 694.4, 14.48),
          headline=(36.2, [655.1, 617.9, 580.7], 36.19),
          desc=dict(x=36.5, y=546.2, lead=18.0, size=12.44, maxw=322),
          icon=[(73.9, 385.3), (73.9, 290.2), (73.9, 198.0)],
          title_x=109.6, title_y=[398.8, 306.7, 210.0], body_w=113,
          promo=(270, 600, 176, 106), phone=(372, 250, 214, 458))
# promo/phone are (x, top-origin y, w, h)

P10 = dict(eyebrow=(35.8, H-123.1, 14.4),
           headline=(38.4, [H-181.0, H-213.1], 30.6),
           left=dict(x=44.5, w=234.7, top=666.8, bot=232.8, tile_cx=93.8,
                     text_x=138.2),
           right=dict(x=306.3, w=243.0, tile_cx=347.4, card_x=370.0,
                      card_w=166.4, text_x=384.5),
           pad=14.0,
           foot=dict(x=82.4, w=383.7, top=766.0, bot=686.0, icon_cx=128.0,
                     text_x=173.5, text_y=706.3, lead=15.0, size=10.6, maxw=262))
# top/bot are top-origin; both columns pitch = (height - 2*pad) / count

P11 = dict(eyebrow=(35.5, 717.3, 14.98),
           headline=(34.7, [681.8, 650.5, 619.2], 32.18),
           num_x=[51.9, 48.8, 48.8, 48.8, 48.9, 48.5],
           num_y=[550.4, 463.4, 376.4, 289.4, 202.4, 115.4], num_size=23.84,
           text_x=194.1,
           title_y=[562.4, 476.5, 390.6, 304.7, 218.5, 132.4], title_size=13.35,
           body_y=[548.3, 462.4, 376.5, 290.6, 204.4, 118.3],
           body_lead=12.0, body_size=10.0, body_maxw=222)

P12 = dict(eyebrow=(35.5, 713.9, 14.98), headline=(34.7, [669.8, 641.2], 29.44),
           total=dict(x=372.7, w=131.3, top=162.0, h=53.8),
           band=dict(top=231.8, bot=746.2, gap=9.8),
           card=dict(x=86.9, w=417.3, title_x=101.5, desc_x=102.2,
                     pill_w=79.0, pill_h=25.0),
           badge=dict(cx=56.1, r=19.4),
           foot=dict(x=43.6, y=[62.1, 51.1, 40.1], size=9.0, rule_x=39.0))
# row height = (band - (n-1)*gap) / n ; badges alternate blue #2563EB / green
# title baseline = row_top + card_height - 21.1 ; desc starts 37.6 down, lead 11.6
# amount pill centred vertically, right-aligned 8pt inside the card

P13 = dict(eyebrow=(35.5, 722.4, 14.21), headline=(34.7, [678.5, 648.6], 30.69),
           left_head=(110.8, 572.1, 16.37),
           right_head=(371.2, [581.7, 565.7], 16.37),
           lx=73.3, rx=334.9, size=10.0, llead=15.0, rlead=17.0,
           lw=179, rw=159,
           ly=[526.8, 481.2, 434.7, 388.4, 342.3, 295.7, 249.4, 204.3],
           ry=[512.7, 446.0, 379.2, 312.8, 232.1],
           foot=(119.2, [123.2, 106.2], 10.0, 320))

P14 = dict(eyebrow=(34.5, 714.0, 14.51),
           headline=(35.5, [657.4, 626.7, 596.1], 31.34),
           cols=[46.9, 219.4, 391.9], rows=[476.7, 258.6], body=[461.4, 243.3],
           lead=15.3, size=10.21, maxw=132,
           foot=(142.2, [105.1, 89.7, 74.4], 9.7, 348))

P15 = dict(eyebrow=(34.5, 711.6, 14.51), headline=(33.6, 670.4, 34.80),
           step_x=127.9, num_x=[62.3, 58.7, 58.9, 58.7, 58.9],
           step_y=[620.6, 558.7, 500.1, 438.2, 379.9],
           num_y=[616.5, 556.0, 496.5, 435.8, 376.5],
           help_x=119.0, help_y=306.2, contact_y=281.4,
           sign_head=(34.5, 219.8, 20.93), sign_note=(34.8, 194.6, 11.0),
           name_y=89.9, sub_y=69.9, cols=[99.3, 348.2])
```

## 5.3 Palette

```
INK      #070707   body and headings
GREY     #5C666F   eyebrows, secondary text
BODY     #383F51   card body copy
BLUE     #2563EB   primary accent, buttons, badges
NAVY     #4460A9   title line 2, headers, section rules
GREEN    #68A85C   "Included" pills, success
LINE     #E0E5F0   hairlines
```

---

# 6. The content model

One JSON document per proposal. See `samples/kestrel.json` in the reference
repo for a complete worked example.

```jsonc
{
  "meta": {
    "client_contact": "", "client_company": "", "project_name": "",
    "region": "US",            // US = $ + Texas law, UK = £ + England & Wales
    "signer_name": "", "signer_role": "", "date": ""
  },
  "screens": { "<slot id>": "<image path or data url>" },

  "page1":  { "title": ["line one", "line two"], "description": "" },
  "page2":  { /* static defaults, {client_company} interpolated */ },
  "page3":  { "one_liner": "", "description": ["para", "para"],
              "surfaces_heading": "Four Connected Surfaces",
              "surfaces": [{ "title": "", "blurb": "", "icon": "ic_home" }] },
  "page4":  { "one_liner": "", "description": "",
              "cards": [{ "title": "", "body": "", "icon": "" }] },  // exactly 3

  "core_pages": [
    { "template": 5, "kind": "grid", "eyebrow": "Core Features · X (Y)",
      "headline": ["", ""],
      "cards": [{ "title": ["", ""], "icon": "", "screen": "slot id",
                  "items": [{ "text": "", "bullet": true }] }] },
    { "template": 6, "kind": "list", "eyebrow": "", "headline": ["", ""],
      "cards": [{ "title": "", "icon": "", "items": ["", ""] }] },
    { "template": 7, "kind": "device", "eyebrow": "", "headline": ["", ""],
      "intro": "", "screen": "slot id",
      "blocks": [{ "title": "", "icon": "", "lead": "", "bullets": [""] }] }
  ],

  "page9":  { "include": false, "headline": ["", "", ""], "description": "",
              "cards": [{ "title": "", "body": "", "icon": "" }],
              "promo": { "greeting": "", "lines": ["", ""], "button": "" },
              "screen": "slot id" },
  "page10": { "stack": [{ "title": "", "body": "", "icon": "" }],
              "services": [{ "title": "", "body": "", "icon": "" }],
              "footnote": "" },
  "page12": { "total_value": 14000, "total_note": "Total · 12–13 working weeks",
              "rows": [{ "title": "", "duration": "1–2 wks",
                         "amount": 2000, "desc": "" }] },
  "page13": { /* static defaults; need[4] is the per-client dependency */ },
  "page14": { /* static defaults; risk_area is per-client */ },
  "page15": { /* static defaults */ }
}
```

## 6.1 Typed by the user, never by the model

```
meta.client_contact, client_company, project_name, region,
signer_name, signer_role
page12.total_value and every milestone amount
```

Amounts are **overwritten from the typed values after the model call**. A
hallucinated price must be structurally incapable of reaching a client.

## 6.2 Static boilerplate

Pages 2, 11, 13, 14 and 15 ship as defaults in code and are merged in locally.
The model only overrides a field where it deliberately returns one.

Two strings on page 14 are per-client and **must be swapped every time**:

- the client company in the IP-transfer card
- `risk_area`, the thing about this app most likely to draw app-store scrutiny

The original template had the previous client's name hardcoded in both places.
So did page 2 and page 15. Audit every "static" page for a buried client name.

## 6.3 The milestone sum check

Run before every render. If the milestone amounts do not equal the stated
total, report it. When correcting, **adjust the middle milestones only, never
the first or last** — this is the client's own house rule, and it keeps the
payment weighting intact.

Launch & Deployment and Post-Launch Support are marked green "Included" with
no payment. Both should be optional per proposal.

---

# 7. Generation pipeline

**Three focused model calls, not one.** A single call asking for all fifteen
pages spends a few hundred tokens per page and produces thin, generic copy.
This was the single largest quality problem in the first build.

### Stage 1 — Brief (fast model, ~2500 tokens)

Input: transcript, project name, client company.
Output: a factual brief. No sales copy.

```jsonc
{ "what_it_is": "one sentence",
  "who_uses_it": ["each distinct user type named in the source"],
  "interfaces": [{ "name": "", "platform": "", "for": "",
                   "features": [{ "title": "", "detail": "",
                                  "supporting": [""] }] }],
  "commercial_angle": "the money argument, or null",
  "differentiator": "the sharpest thing rivals do not do",
  "tech_needs": [""],
  "store_risk": "or null" }
```

Rules in the prompt: every feature must come from the transcript; do not pad;
group features by interface; an interface with fewer than three features is
probably part of another one.

### Stage 2 — Front pages (best model, ~3000 tokens)

Input: the brief. Output: pages 1, 3 and 4.

**Include a worked example in the prompt.** Without one the model invents its
own house style. The example that worked:

```
page1.title: ["Real Estate Management", "Application"]
page3.one_liner: "One platform where buyers search, tour, and make offers and
                  where you watch every listing move in real time."
page4.one_liner: "Know the price before you see the house."
page4.cards[0]: {"title": "Value before you view",
                 "body": "An instant valuation on every listing removes the
                          biggest reason buyers walk away."}
```

with the note: *name the user's actual job, put the benefit before the
mechanism, stay short enough to read in one breath.*

### Stage 3 — Features and technical (best model, ~8000 tokens)

Input: brief + front pages. Output: `core_pages`, `page9`, `page10`,
milestone descriptions, `page14.risk_area`.

### House style, in every prompt

- British-neutral, plain, confident
- No hype, no filler, **no em-dashes**
- Never invent a client name, price, date or timeline
- Every feature traceable to the source; fewer items rather than padding
- Icons only from the allowed list

### Why three requests, not three calls in one request

Serverless platforms cap a request at 60 seconds. Three sequential model calls
exceed that and return a gateway timeout with no body. **Each stage must be its
own HTTP request**, orchestrated by the client, so each gets its own budget.

---

# 8. The normalizer — do not skip this

Models rename keys and change shapes constantly. Left unchecked this crashes
the editor and produces blank cards.

Real failures observed:

- `page1.title` returned as a string where two lines were expected
- `page4.cards` returned with `heading`/`description` instead of `title`/`body`,
  producing three empty boxes
- `"amount": "1,000"` as a string
- `"template": "5"` as a string
- a plain string where a list of objects was expected
- an empty string in a checklist, which crashed `wrap()[0]` with an IndexError

The normalizer coerces every field before anything downstream sees it:

- exactly N lines, splitting a string on word boundaries if needed
- accept aliases: `title|heading|name|label|header`,
  `body|blurb|lead|desc|description|text|detail|copy|summary`
- drop cards that are genuinely empty rather than rendering blank boxes
- `"1,000"` → `1000`, `"5"` → `5`
- default icons, default headings, pad missing paragraphs

Test it by feeding deliberately malformed output and asserting a complete PDF
still renders.

---

# 9. Layout QA

Real client copy is longer than the designer's placeholder text. Without
guards it spills out of cards and off the page.

Every render must:

1. **Shrink headlines to fit** the available width before drawing.
2. **Fit body blocks to their box**: reduce size, then clip, and report when
   content was dropped.
3. **Flow lists rather than pinning them to fixed baselines.** The original
   design's baselines assume the designer's exact line counts; real copy
   produces holes. Flow with a lead inside an item and a larger gap between
   items.
4. **Report empty slots** — page 4 always shows three boxes, so two cards means
   a visible gap.
5. **Never let one page kill the render.** Catch per page, draw the reason on
   the page itself, and carry on.

Surface the findings in the UI under the preview:

```jsonc
{ "page": 4, "kind": "clipped",    "detail": "differentiator description: text is longer than its box" }
{ "page": 4, "kind": "empty-slot", "detail": "2 differentiator cards had no content" }
{ "page": 6, "kind": "error",      "detail": "IndexError: list index out of range" }
```

**Acceptance test:** feed a 25-word one-liner, a tripled description, six
overlong bullets in one card and a two-line headline. Nothing may spill; every
compromise must be reported.

---

# 10. UI screens

The hardest part, and the one with the most dead ends. Read §12 before
choosing an approach.

## 10.1 What is needed

Each proposal needs one screen per grid card and one per device page, roughly
five to eight in total. They must look like the client's app and must match the
words printed next to them.

## 10.2 Approaches, in the order they were tried

| Approach | Result |
|---|---|
| Procedural illustration | Works offline, instant, free. Reads as clip art. Rejected by the client. |
| UX Pilot, manual | Excellent quality. Requires copy, paste, generate, export, upload. Rejected as a permanent workflow. |
| UX Pilot MCP, automated | **Not possible.** Every generation tool is `prepare-*` and opens a confirmation widget. No headless path. |
| Built-in spec renderer | Model writes a block spec, renderer draws it. One click, instant, good structure. Image areas are tinted blocks, not photographs. |
| v0 Platform API | Headless and high quality. Needs a screenshot service. See below. |

## 10.3 Recommended for the rebuild: HTML generation plus screenshot

Have the model write **HTML/CSS for each screen** against a fixed design system,
then rasterise it with a headless browser. This gives:

- pixel-crisp text, which image models cannot do
- real layout control
- photographic imagery via licensed image URLs
- full automation with no third-party design tool

The screenshot step needs either a headless Chromium in your runtime or a
screenshot API (ScreenshotOne, Urlbox, Browserless). ScreenshotOne was verified
working; use the **access key**, not the secret key.

## 10.4 On GPT image generation

The brief asks for GPT image generation. Use it carefully:

**Do not use an image model to generate whole UI screens.** Diffusion models
render text as plausible-looking gibberish. A proposal screen full of fake
words is worse than a placeholder, and a client will notice.

**Do use an image model for the photographs inside the screens** — property
exteriors, interiors, people, product shots. Generate those, then place them
into HTML-rendered UI where the text is real. That combination gives
photographic imagery and crisp typography at the same time.

If whole-screen image generation is attempted anyway, gate it behind a review
step and read every string in the output before it reaches a client.

## 10.5 v0 Platform API, if you keep it

- Base `https://api.v0.dev/v1` returns a publicly reachable `demoUrl` that a
  screenshot service can load.
- Base `https://api.v0.dev/v2` puts previews behind a short-lived token that
  must be proxied by your own backend. A screenshot provider cannot reach it.
  Fall back to creating a real Vercel deployment, whose URL is public.
- **Do not send a `modelId` unless you know the exact value your account
  accepts.** An unrecognised id returns HTTP 422.
- Always surface the API's response body in errors. A bare status code wastes
  hours.

## 10.6 Screen slots

Derive slots from the proposal itself:

```
grid card   -> "p{template}_c{index}", device "phone"
device page -> "p{template}_device",   device "tablet" (t7) or "web" (t8)
page 9      -> "p9_phone",             device "phone"
```

A slot with no screen must render a dashed "UI screen pending" box so a draft
reviews cleanly.

---

# 11. The editor

## 11.1 Live editing on the design

The renderer emits a **text map**: for every editable string, its page, JSON
path, x, baseline y, width, height, size and font. The browser overlays a
transparent box on the preview at those coordinates. Click it, an inline
textarea opens, type, blur commits.

This is what makes it feel like Canva rather than a form.

- Escape cancels, Cmd/Ctrl-Enter commits
- Rebuild the overlay whenever the preview or the window size changes
- Roughly 110 targets across a full deck

## 11.2 What must stay in a side panel

Structural operations a click cannot express: add, delete, reorder, change
icon, switch region.

## 11.3 Locked fields

Never editable by prompt, and not clickable on the design:

```
meta.*                  typed facts
page12.total*           money
*.amount                money
page14.cards.*          legal statements
```

## 11.4 Prompt editing

Send **only the selected node**, never the document. A few hundred tokens
instead of several thousand, and structurally incapable of changing anything
else. Reject the result if its shape changed — a two-line title that comes back
as three lines breaks the layout.

## 11.5 Versioning and sharing

The client's requirement: **a proposal stays editable after it is sent.**

Implement as versions, never in-place edits:

- every edit writes a new version
- `send()` issues a share link **pinned to the version that was sent**
- the team can keep editing; the client keeps seeing what they received
- `republish()` explicitly moves the link forward, with a timestamp
- `diff(a, b)` lists which JSON paths changed

Without pinning you get a dispute you cannot win: the client read one document
and the link now shows another.

Annotations are internal notes pinned to a JSON path and are **never rendered
into the PDF**.

---

# 12. Where the first build went wrong

The honest list. Each of these cost real time.

**1. Declaring "PSD is unusable".** It is perfectly usable via `psd-tools`,
which also hands over clean plates and correct text. This wrong call meant
seven pages were reconstructed from flattened PDFs by hand.

**2. Shipping the original plates.** Every page was carefully cleaned during
development, then the *uncleaned* plates were packaged. Result: doubled icons,
the previous client's laptop screen showing through, overlapping badges. Always
ship the cleaned assets and verify by rendering.

**3. Using bounding-box tops as baselines.** pdfminer's `y0` is the glyph box
bottom, not the baseline. Use the text matrix. Everything was offset by a
descender until this was caught.

**4. One model call for fifteen pages.** Produced thin, generic copy. Three
focused calls with a worked example fixed it. This was mistaken for an
"environment problem" — it was a prompt design problem.

**5. Three model calls inside one HTTP request.** Exceeded the 60-second
platform limit, returning a 504 with no body. Each stage needs its own request.

**6. Reading the wrong error field.** The frontend read `j.error` while the
API returned `detail`. Every failure showed as "request failed" for several
rounds. Always surface the real message.

**7. Not importing `urllib.error`.** The handler never caught HTTPError, so
API error bodies were discarded and a 422 arrived as a meaningless string.

**8. A hardcoded model id that did not exist.** Both for the LLM
(`claude-sonnet-4-6` instead of `claude-sonnet-5`) and for v0. Make model ids
configurable and default to blank where the provider can choose.

**9. Serving the editor from cache.** Redeploys appeared to change nothing
because the browser held the old HTML. Serve it `no-store` and show the server
build in the UI.

**10. Assuming preview URLs are public.** v0 v2 previews need a token proxy. A
screenshot service would have photographed nothing.

**11. Erasing artwork with too little blur.** Left visible vertical banding
over gradients. Use a large radius and feather the seam.

**12. Trusting "static" pages.** Pages 2, 14 and 15 all had the previous
client's name buried in them. Decode and read every page before believing it.

**13. Fixed baselines for variable-length lists.** The design's baselines
assume the designer's line counts. Real copy leaves holes. Flow instead.

---

# 13. Build order

1. **Asset pack.** Fifteen cleaned plates, font instances, icon library, one
   geometry file. Verify by rendering a page and comparing to the original.
2. **Schema and renderer.** JSON in, PDF out, no AI. This alone is a working
   generator driven by a config file.
3. **Normalizer and layout QA.** Before any model is wired in.
4. **Transcript to JSON.** The three staged calls, as three endpoints.
5. **Editor.** Preview, text-map overlay, side panel for structure.
6. **Screens.** HTML generation plus screenshot; image model for photographs
   only.
7. **Versioning, sharing, annotations.**
8. **Deploy.**

Stages 1 to 3 are the foundation. Everything after is convenience.

---

# 14. Test plan

## Renderer
- [ ] All 15 pages render from the sample document with no failures
- [ ] Rendered pages match the client's originals when overlaid
- [ ] Deleting a surface re-spaces the row evenly
- [ ] Adding a tech stack item re-pitches the column
- [ ] Removing a milestone renumbers the badges and re-spaces the rows
- [ ] A missing screen draws the dashed placeholder
- [ ] Text is selectable and copies correctly out of the PDF

## Normalizer
- [ ] String where a two-line list is expected → split on a word boundary
- [ ] Aliased keys → content preserved
- [ ] `"1,000"` → `1000`
- [ ] Empty checklist item → no crash
- [ ] Deliberately malformed model output → complete PDF still renders

## Layout QA
- [ ] 25-word one-liner does not run off the page
- [ ] Tripled description does not spill out of its card
- [ ] Six overlong bullets in one card are shrunk, then reported
- [ ] Fewer than three differentiator cards is reported
- [ ] A page that raises prints the reason and the others still render

## Money
- [ ] Milestones not summing to the total is reported before render
- [ ] The correction adjusts middle milestones only
- [ ] A model-supplied amount is overwritten by the typed value
- [ ] UK region renders £ and US renders $

## Content safety
- [ ] No page contains a hardcoded previous client name
- [ ] `page14.risk_area` reflects this app, not the last one
- [ ] Page 2's closing sentence names the current client

## Editor
- [ ] Clicking text on the preview opens an inline editor at the right spot
- [ ] Escape cancels, Cmd-Enter commits
- [ ] Locked fields are not clickable and refuse prompt edits with 423
- [ ] Prompt edit returning a different shape is rejected
- [ ] Every edit creates a version; restore works

## Sending
- [ ] Editing after send does not change what the share link shows
- [ ] Republish moves the link forward and records when
- [ ] Annotations never appear in the PDF

## Deployment
- [ ] Health endpoint reports build, assets, keys and models
- [ ] A wrong key is reported by name, not as a generic failure
- [ ] Editor HTML is served `no-store`
- [ ] Each generation stage completes inside the platform's request limit

---

# 15. Assets checklist

```
assets/plates/page1..15.jpg     300dpi A4, cleaned per §4.3
assets/fonts/                   Glancyr static instances from the variable font
icon library                    ~20 vector icons, drawn on a 24×24 grid
```

Ask the client for, and chase:

- **background layers as separate PNGs** for pages 3, 7, 8, 9 — the wave
  artwork behind erased elements is otherwise lost
- **PSDs for every page**, which makes all of the above unnecessary
- a licensed photo pack, or approval to use generated imagery

---

# 16. Reference implementation

The accompanying repository is working code for everything above except the
HTML-plus-screenshot screen generator. Use it as the specification of record
where this document is ambiguous.

```
renderer/kit.py         fonts, wrapping, flow, panels, QA, text map
renderer/icons.py       vector icon library
renderer/model.py       schema, static defaults, money, milestone check
renderer/normalize.py   model output coercion
renderer/pages_a.py     pages 1–9
renderer/pages_b.py     pages 10–15
renderer/render.py      page plan, orchestration, per-page error capture
renderer/extract.py     staged generation prompts
renderer/uiscreens.py   spec-driven screen renderer
renderer/store.py       versions, sharing, annotations
renderer/edit.py        scoped prompt editing, locked paths
api/index.py            single ASGI app, all endpoints
public/index.html       editor, live-edit overlay
samples/kestrel.json    a complete worked proposal
```
