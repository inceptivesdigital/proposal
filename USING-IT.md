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

## The studio layout

Three columns.

**Left, the page rail.** All 15 pages with a thumbnail, the page name and how
many editable fields it has. A warning badge appears when a layout check fires.

**Middle, the canvas.** The live page. Undo and redo, zoom, "Rewrite selection",
and a layout-check indicator that stays green while the proposal is clean.

**Right, the inspector.** Three tabs.

- **Content** — what you have selected, its text, a character counter with a
  live "Fits safely" verdict, "Rewrite with AI", and page actions for the lists
  you can add to and delete from.
- **Checks** — every layout issue, by page.
- **Notes** — internal review notes, never printed.

The top bar carries the document name, whether there are unsaved changes, and
New, Versions, Save, Download PDF and Publish.

## Editing on the design itself

Hover the preview and any editable text highlights. Click it, type, click away.
The page redraws with your words in the right font, size and position.

Click a field on the page and it loads into the inspector, where you edit it
with a live character count against the real space available. "Fits safely"
means the renderer will not have to shrink the type; "Close to the limit" is a
warning; "Too long" means it will shrink.

- **Cmd-Z / Ctrl-Z** undoes, **Cmd-Shift-Z** redoes
- Everything is versioned, so Versions then Restore recovers anything

The panel on the left still exists for the things a click cannot do: adding and
deleting cards, reordering milestones, changing icons.

Fields shown greyed with "edited by hand" cannot be clicked on the design.
Prices, client details and the page 14 legal statements are deliberately typed,
never rewritten in place.

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

## UI screens

1. Click **UI screens**
2. Click **Generate all screens**

That is the whole job. The app reads the proposal, designs a screen for every
feature card and every interface, draws them in the Inceptives palette and
attaches them. Nothing is exported, uploaded or pasted.

Each screen is a real layout: headers, search fields, filter chips, listing
tiles, list rows with status pills, KPI cards, charts. The content comes from
the card it belongs to, so the screens always match the words next to them.

### If you would rather use UX Pilot

Open "Use UX Pilot instead" in the same dialog. Copy the mobile prompt, paste it
into UX Pilot's mobile canvas, do the same with the wide-screen prompt on the
desktop canvas, export everything as one PDF, and drop the PDF in. Each page is
split and cropped automatically, then assign them in order.

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
