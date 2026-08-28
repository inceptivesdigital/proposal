# Inceptives Digital — Proposal Creator

Renders the 15-page Inceptives proposal from a single JSON file.
Layout, typography, colour and geometry live in code. Content lives in data.
The AI only ever writes the JSON; it never draws a page, so branding cannot drift.

## Run it

    pip install reportlab pillow
    python cli.py samples/kestrel.json out.pdf

## Layout

    assets/plates/page1..15.jpg   background artwork, 300dpi
    assets/fonts/                 Glancyr static instances (from the variable font)
    renderer/kit.py               fonts, wrapping, flow, panels, image fitting
    renderer/icons.py             20 vector icons, drawn not rasterised
    renderer/model.py             content schema, defaults, money, milestone check
    renderer/pages_a.py           pages 1-9
    renderer/pages_b.py           pages 10-15
    renderer/render.py            JSON -> PDF
    samples/kestrel.json          a complete worked example

## Content model

Typed by the user, never invented:
  meta.client_contact, client_company, project_name, region (US|UK),
  signer_name, signer_role, date
  page12.total_value and the milestone rows

Derived by the AI from the transcript: everything else.

`check_milestones()` runs before every render and reports when the milestone
amounts do not equal the stated total.

## Pages

  1  Cover                      variable
  2  Company Overview           static (client name in the closing line)
  3  App overview / surfaces    variable, dynamic card count
  4  The Differentiator         variable, 3 cards, new icons per client
  5-8 Core Features             one entry per page in core_pages[]
       kind="grid"   page 5 template, 2x2 cards with UI glimpses
       kind="list"   page 6 template, checklist cards, no visuals
       kind="device" page 7/8 templates, feature blocks plus one screen
  9  Direct Marketing Engine    optional; include only when there is an upside angle
  10 Technical Requirements     variable, dynamic count in both columns
  11 How We Build               static
  12 Milestones & Investment    variable, dynamic rows, sum-checked
  13 Deliverables               near-static, editable
  14 Terms & Client Protection  near-static; client name + risk area per client
  15 Next Steps & Signatures    variable signers

## Screens

`screens` maps an id to an image path. Missing screens render a dashed
"UI screen pending" box so a draft still reviews cleanly.

## Transcript to JSON

    from renderer.extract import extract
    data = extract(transcript, meta, milestones=[2000,3000,2000,3000,2000,2000],
                   total_value=14000)

One model call. The model writes content only:

- It is handed the typed fields and told to use them exactly.
- Milestone amounts are overwritten from the typed values after the call, so a
  hallucinated number can never reach a client.
- Boilerplate for pages 2, 11, 13, 14 and 15 is merged in locally and only
  overridden where the model returned something.
- `data["_warnings"]` carries the milestone sum check.

Set `ANTHROPIC_API_KEY`. Override the model with `PROPOSAL_MODEL`.

## Documents, versions and sending

Proposals stay editable after they are sent, so nothing is ever overwritten in
place. Every edit writes a new version.

    from renderer.store import Proposal
    p = Proposal(data, author="fasih")
    share = p.send(author="fasih")        # link pinned to the sent version
    p.apply([{"op":"set","path":"page4.one_liner","value":"..."}], author="fasih")
    p.resolve_share(share["token"])       # still the version the client was sent
    p.republish(share["token"])           # deliberately point the link at latest
    p.diff_summary(1, 2)                  # which paths changed

Ops: set, insert, append, delete, move. Paths are dotted, e.g.
`page4.cards.2.title`, `page3.surfaces.3`.

`p.annotate(path, body, author)` stores internal review notes. Annotations are
never rendered into the PDF.

## Prompt editing

    from renderer.edit import edit_node
    ops = edit_node(p.data, "page4.description", "make this punchier")
    p.apply(ops, author="fasih", note="prompt edit")

The model sees only the selected node, so an edit costs a few hundred tokens.
The returned value must keep the same shape or the edit is rejected.

Locked from prompt editing: everything under `meta`, `page12.total*`, any
`amount`, and the six `page14.cards` legal statements. Those are edited by hand.
