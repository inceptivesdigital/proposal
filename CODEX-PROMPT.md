# Prompt for Codex

Paste this as your first message, and attach `HANDOVER.md`, the
`proposal-creator` reference repo, the 15 page files (PSD where you have them,
PDF otherwise), and the Glancyr font files.

---

You are rebuilding a production system called the **Inceptives Digital Proposal
Creator**. I am attaching two specifications and a working reference implementation.
`HANDOVER.md` describes the system and where every element sits on the page.
`CONTENT-SPEC.md` describes what to write in each field, in what voice, with a
measured character limit for every one of them. Read the specification in full before writing any
code. It contains measurements recovered by hand from the client's design files
that cannot be re-derived cheaply, and a section on mistakes made in the first
build that I do not want repeated.

## What it does

Inceptives Digital is an app development agency. Their sales team writes 15-page
PDF proposals. Every proposal uses the same designed template; only the words,
the prices and the app screenshots change.

The system takes a call transcript plus a handful of typed fields and produces a
finished 15-page PDF in about a minute, keeps every page editable, and never
lets the branding drift.

## The rule everything follows

**Layout is code. Content is data. The model only ever writes the data.**

Each page is a fixed background image plus a small block of JSON. A renderer
draws text onto that image at coordinates measured from the original design. The
AI produces the JSON and nothing else. There must be no code path in which a
model influences position, size, colour or typography.

## Hard requirements

1. Output must be visually identical to the client's template. Section 5.2 of
   the specification has every measurement. Copy the numbers exactly. All
   coordinates are PDF points, bottom-left origin, and every `y` is a text
   baseline, not a bounding-box top.
2. The model never writes prices, client names, dates or legal terms. Amounts
   are overwritten from typed values after the model call, so a hallucinated
   number is structurally incapable of reaching a client.
3. Milestone amounts must sum to the stated total. When they do not, say so
   before rendering, and correct by adjusting middle milestones only, never the
   first or last.
4. A proposal stays editable after it is sent. Implement as versions: a share
   link stays pinned to the version the client received until someone
   explicitly republishes.
5. Text is edited by clicking it on the rendered page, not only in a side panel.
   The renderer emits a text map of every editable string's position; the
   browser overlays an input on it.
6. Every list is dynamic. Deleting a card must re-space the page, not leave a
   hole.
7. Cost per proposal in cents, not dollars.

## Generation

Three focused model calls, each as its own HTTP request:

1. **Brief** — read the transcript, decide what the product is, who uses it,
   which interfaces exist and which features belong to each. No sales copy.
2. **Front pages** — pages 1, 3 and 4, with a worked example in the prompt so
   the model has a standard to hit.
3. **Features and technical** — the Core Features pages, the optional commercial
   page, the technical requirements and the milestone descriptions.

Do not combine them into one request. Three sequential model calls exceed a
60-second serverless limit and return a gateway timeout with no body.

## UI screens

Each proposal needs five to eight app screens that look like the client's app
and match the words printed next to them.

**Use GPT image generation for the photographs inside the screens, not for the
screens themselves.** Diffusion models render text as plausible gibberish, and a
proposal screen full of fake words is worse than a placeholder. Generate the
photographic content — property exteriors, interiors, people, product shots —
then place those images into UI that is rendered as HTML and screenshotted, so
the typography is real and crisp.

A slot with no screen must render a dashed "UI screen pending" box so a draft
still reviews cleanly.

## Robustness, learned the hard way

- **Normalize every model response before anything else touches it.** Models
  rename keys and change shapes. Section 8 lists the exact failures observed and
  what to coerce.
- **Guard the layout.** Real client copy is longer than the designer's
  placeholder text. Shrink headlines to fit, fit body blocks to their box, flow
  lists rather than pinning them to fixed baselines, and report every compromise
  in the UI.
- **Never let one page kill a render.** Catch per page, draw the reason on the
  page, carry on.
- **Always surface the real error.** Read the API's response body, not just the
  status code. Section 12 is a list of hours lost to generic error messages.
- **Serve the editor `no-store`** and show the server build in the UI, so a
  redeploy is visibly a redeploy.

## Where to start

Build in the order in section 13. Stages 1 to 3 — asset pack, renderer,
normalizer and layout QA — are the foundation and must be right before any model
is wired in. A JSON file in and a correct PDF out, with no AI involved, is the
milestone that proves the system.

Work through the test plan in section 14 as you go. The acceptance test for the
layout guards is section 9: deliberately overlong copy in every slot, nothing
spills, every compromise reported.

When you implement the generation prompts, embed `CONTENT-SPEC.md` in them.
Its limits were measured against the real font at the real size in the real
column width, so content written to them fits without the renderer shrinking
type. Its self-check list at the end should run before any content is returned.

Tell me what you would change about this design before you start.
