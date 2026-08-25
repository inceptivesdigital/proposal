# Deploying to proposals.inceptivesdigital.com

Zero build step. Vercel serves `public/` statically and runs `api/*.py` as
Python functions.

## 1. Repo

    git init && git add . && git commit -m "proposal creator"
    git remote add origin <your repo> && git push -u origin main

`assets/` is ~5MB and must be committed; the renderer reads the plates and fonts
from disk at runtime.

## 2. Vercel project

Import the repo. Framework preset: **Other**. No build command, no output dir.

Vercel detects `api/*.py` as Python functions on its own. Do **not** put a
`runtime` key in `vercel.json`; that field expects a versioned builder package
(`@vercel/python@4.3.0`) and `"python3.12"` fails with *"Function Runtimes must
have a valid version"*. The config here only sets memory, duration and which
files to bundle.

`includeFiles` matters: without it the function bundle would not contain
`renderer/` or `assets/`, and every render would fail on a missing plate.

**Vercel Pro is required.** Hobby caps functions at 10 seconds; a full render
takes about 3 seconds warm and more on a cold start.

## 3. Environment variables

    ANTHROPIC_API_KEY   server-side only, never exposed to the browser
    PROPOSAL_MODEL          optional, defaults to claude-sonnet-4-6
    PROPOSAL_EDIT_MODEL     optional, same default

## 4. Domain

Project → Settings → Domains → add `proposals.inceptivesdigital.com`.
Vercel gives you the CNAME. TLS is issued automatically.

## 5. Endpoints

    POST /api/generate  {transcript, meta, milestones, total_value} -> {data, warnings}
    POST /api/preview   {data, page, scale}                         -> {png, page, pages, name}
    POST /api/render    {data}                                      -> {pdf (base64), filename}
    POST /api/edit      {data, path, instruction}                   -> {ops}   423 if locked

`/api/preview` renders only the requested page, so it stays responsive while
someone types.

## Known limits, and what to do about them

**No server-side persistence yet.** The editor keeps the document in browser
localStorage and you can save or open a JSON file. Versions, share links and
notes live in that object. To make them real, add Vercel Postgres and move
`renderer/store.py` behind two endpoints (`/api/proposals`, `/api/share`).
That is the next piece of work, not a workaround.

**Authentication is not wired up.** Put the project behind Vercel Authentication
(Settings → Deployment Protection) until proper sign-in exists. Do not leave it
open: the render endpoint runs on your account and the generate endpoint spends
your API credits.

**UI screens are uploaded, not generated.** Export them from UX Pilot and attach
them; missing screens render a dashed "UI screen pending" box so a draft still
reviews cleanly.
