# Deploying to proposals.inceptivesdigital.com

The whole thing is one Python app. Vercel runs `api/index.py`, which serves both
the editor and the API. One bundle, so the 5MB asset pack ships once.

## Step by step

**1. Put the code in a Git repo**

    cd proposal-creator
    git init
    git add .
    git commit -m "proposal creator"
    git branch -M main
    git remote add origin git@github.com:<you>/proposal-creator.git
    git push -u origin main

`assets/` must be committed. The renderer reads the plates and fonts from disk,
so if they are gitignored every render fails on a missing file.

**2. Check locally first (optional but saves a round trip)**

    pip install -r requirements.txt uvicorn
    uvicorn api.index:app --reload
    # open http://127.0.0.1:8000

**3. Import into Vercel**

Vercel dashboard → Add New → Project → import the repo.

- Framework Preset: **Other**
- Build Command: leave empty
- Output Directory: leave empty
- Install Command: leave empty

Deploy.

**4. Environment variables**

Project → Settings → Environment Variables:

    ANTHROPIC_API_KEY     required, server-side only
    PROPOSAL_MODEL        optional, defaults to claude-sonnet-5
    PROPOSAL_BRIEF_MODEL  optional, stage 1 only, defaults to claude-sonnet-5
    PROPOSAL_EDIT_MODEL   optional, same default
    PROPOSAL_MAX_TOKENS   optional, defaults to 16000
    PROPOSAL_STAGED       optional, "0" reverts to the old single call
    PROPOSAL_INCLUDE_LAUNCH   optional, "0" drops the Launch & Deployment row
    PROPOSAL_INCLUDE_SUPPORT  optional, "0" drops the Post-Launch Support row
    PROPOSAL_MAX_TRANSCRIPT  optional, defaults to 60000 characters

Redeploy after adding them.

**5. Protect it before anyone finds it**

Settings → Deployment Protection → enable Vercel Authentication.
There is no sign-in yet, and `/api/generate` spends your API credits.

**6. Add the domain**

Settings → Domains → add `proposals.inceptivesdigital.com`.
Vercel gives you a CNAME. Add it at your DNS provider. TLS is automatic.

**7. Verify**

    https://proposals.inceptivesdigital.com/api/health

    {"ok": true, "assets": true, "anthropic_key_set": true,
     "generate_model": "claude-sonnet-5", "edit_model": "claude-sonnet-5"}

Read it before debugging anything else:

- `assets: false` — the plates did not ship. Check they are committed and that
  `includeFiles` in `vercel.json` still lists `assets/**`.
- `anthropic_key_set: false` — Generate will fail. Add the key and redeploy.
- wrong model name — set `PROPOSAL_MODEL` to a model your API key can call.

## Two errors you have already hit, and why

**"Function Runtimes must have a valid version"** — `vercel.json` had
`"runtime": "python3.12"`. That field takes a versioned builder package such as
`@vercel/python@4.3.0`, not a language name. For Python you omit it entirely.

**"No python entrypoint found in default locations"** — Vercel treats a repo
with `requirements.txt` or `pyproject.toml` at the root as one Python
application and looks for a single ASGI app, not a folder of separate handlers.
Hence one FastAPI app at `api/index.py` and

    [tool.vercel]
    entrypoint = "api.index:app"

in `pyproject.toml`.

`includeFiles` matters too: without it the bundle holds only the handler, and
`renderer/` and `assets/` never ship.

## Endpoints

    GET  /                    the editor
    GET  /api/health          asset sanity check
    POST /api/brief           {transcript, meta}          -> {brief}
    POST /api/front           {brief, meta}                -> {front}
    POST /api/features        {brief, front, meta, milestones, total_value}
                                                           -> {data, warnings}
    POST /api/generate        all three in one request; local use only
    POST /api/preview         {data, page, scale} -> one page as PNG
    POST /api/render          {data} -> full PDF, base64
    POST /api/edit            {data, path, instruction} -> ops, 423 if locked

## Still to do

**No server-side persistence.** The editor keeps documents in browser
localStorage, with save and open as JSON. Versions, share links and notes all
work but live in that object. Making share links real means adding Vercel
Postgres and putting `renderer/store.py` behind two endpoints.

**No sign-in.** Deployment Protection covers you until it exists.


## Reading a failure

Every failure now says what happened. The message appears in the browser alert
and in the Vercel function log.

- **"ANTHROPIC_API_KEY is not set"** — add it and redeploy.
- **"Model call failed using model 'x'"** — the model string is wrong for your
  key, or the key is invalid. `PROPOSAL_MODEL` overrides it.
- **"The model ran out of room"** — the transcript was long enough that the
  reply was cut off mid-JSON. Trim it, or raise `PROPOSAL_MAX_TOKENS`.
- **504 with no JSON body** — the request outran the platform limit. The editor
  now calls `/api/brief`, `/api/front` and `/api/features` in sequence so each
  gets its own 60 seconds. `/api/generate` still does all three in one request
  and will time out on Vercel; it is there for local use and the CLI.
- **"The model did not return valid JSON"** — the first 300 characters of the
  reply are included so you can see what it said instead.

For the raw response: browser DevTools, Network tab, click `generate`, Response.
Or Vercel dashboard, Deployments, the current one, Functions, Logs.


## Content quality

Generation runs as three focused calls, not one:

1. **Brief** — reads the transcript and decides what the product is, who uses it,
   which interfaces exist and which features belong to each. No sales copy.
2. **Front pages** — writes pages 1, 3 and 4 against that brief, with a worked
   example in the prompt so it has a standard to hit.
3. **Features and technical** — lays out the Core Features pages, page 9 if there
   is a commercial angle, page 10 and the milestone descriptions.

The single-call version asked for fifteen pages at once and spent a few hundred
tokens per page, which is why the copy was thin. Three calls cost a few cents
more and are markedly better.

For the best copy set `PROPOSAL_MODEL=claude-opus-5`. Sonnet is the default
because it is faster and cheaper; Opus writes better sales copy.


## If Generate still fails after a redeploy

Open `/api/health` first. It now reports the live build:

    {"build": "2026-08-26.3-staged", "staged_endpoints": true, ...}

- **`staged_endpoints` missing or false** — the deployment is older than the
  three-request split. Redeploy.
- **`build` is right but the browser still fails the same way** — you are
  running a cached copy of the editor. Hard refresh: Cmd-Shift-R on Mac,
  Ctrl-Shift-R on Windows. The editor now shows the server build in its header,
  so a mismatch is visible without opening DevTools.

Stage 1 runs on `PROPOSAL_BRIEF_MODEL` (Sonnet by default) even when
`PROPOSAL_MODEL` is set to Opus, because comprehension does not need the slower
model and stage 1 should never be the thing that times out.

### Capturing a HAR that actually contains something

1. Open DevTools **before** clicking Generate
2. Network tab, tick **Preserve log**
3. Click Generate, wait for the failure
4. Right-click any row, Save all as HAR with content
