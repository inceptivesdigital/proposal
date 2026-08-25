# Using the Proposal Creator

## Every proposal, start to finish

**1. Open it.** The URL, or double-click `start.sh` (Mac) / `start.bat` (Windows)
if you are running it locally.

**2. Click "New from transcript".** Fill in seven boxes:

    Client contact        Hannan Shahnoor
    Client company        Kestrel Property Group
    Project / app name    Kestrel Property App
    Region                US or UK
    Signer name           whoever from your team signs
    Signer role           Account Strategist
    Total price           14000
    Milestone amounts     2000, 3000, 2000, 3000, 2000, 2000

Then paste the call transcript, or type the requirements in plain English.

If the milestones do not add up to the total, it tells you before you generate.

**3. Click Generate.** About 20 seconds. You get all 15 pages.

**4. Read it and fix anything.** Every box on the left is editable and the
preview updates as you type. Add or delete feature cards, milestones, tech items.
To reword something, click into it and press "Edit selection by prompt", then
type what you want, e.g. "make this punchier".

**5. Click Download PDF.** Send it.

That is the whole job. Three minutes, most of it reading.

## Things worth knowing

**Prices are never written by the AI.** It writes descriptions; the amounts come
from what you typed. It cannot invent a number.

**Some fields will not take a prompt.** Client details, the total, milestone
amounts and the six legal statements on page 14. Those are typed by hand on
purpose, so a rewrite can never quietly change a price or a contract term.

**You can keep editing after sending.** Click Send and the client's link is
pinned to the version they received. Edit freely; they keep seeing what they were
sent until you choose to republish.

**UI screens.** Generate them in UX Pilot, export as PDF, upload them. Pages
without a screen show a dashed "UI screen pending" box, so you can review the
whole proposal before the screens exist.

**Save your work.** "Save JSON" downloads the proposal, "Open JSON" loads it
back. Until server storage is added, this is the backup.

## Attaching UI screens

1. Generate the screens in UX Pilot, export as PNG
2. Click **UI screens** in the toolbar
3. You get one slot per screen the proposal needs, each labelled with its page
   and card, e.g. "Page 5 · Onboarding & Search Setup"
4. Choose a file for each slot. The preview updates immediately.

Slots you leave empty print a dashed "UI screen pending" box, so a proposal can
be reviewed and even sent internally before the screens exist. Screens are saved
with the proposal, so Save JSON keeps them and Open JSON brings them back.

## The layout check

Under the preview you will see any layout issue the renderer found:

- **clipped** — copy was longer than its box. The renderer shrinks the type
  first and only drops content as a last resort, but it tells you either way so
  you can shorten it by hand.
- **empty-slot** — a card in the artwork has no content. Page 4 always shows
  three differentiator boxes; if the AI only found two, that is flagged.
- **error** — a page failed outright. The reason is printed on the page itself.

A clean proposal shows nothing here.
