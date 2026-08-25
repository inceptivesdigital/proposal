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
    PROPOSAL_MODEL        optional, defaults to claude-sonnet-4-6
    PROPOSAL_EDIT_MODEL   optional, same default

Redeploy after adding them.

**5. Protect it before anyone finds it**

Settings → Deployment Protection → enable Vercel Authentication.
There is no sign-in yet, and `/api/generate` spends your API credits.

**6. Add the domain**

Settings → Domains → add `proposals.inceptivesdigital.com`.
Vercel gives you a CNAME. Add it at your DNS provider. TLS is automatic.

**7. Verify**

    https://proposals.inceptivesdigital.com/api/health
    -> {"ok": true, "assets": true}

`assets: false` means the plates did not ship. Check they are committed and that
`includeFiles` in `vercel.json` still lists `assets/**`.

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
    POST /api/generate        {transcript, meta, milestones, total_value}
    POST /api/preview         {data, page, scale} -> one page as PNG
    POST /api/render          {data} -> full PDF, base64
    POST /api/edit            {data, path, instruction} -> ops, 423 if locked

## Still to do

**No server-side persistence.** The editor keeps documents in browser
localStorage, with save and open as JSON. Versions, share links and notes all
work but live in that object. Making share links real means adding Vercel
Postgres and putting `renderer/store.py` behind two endpoints.

**No sign-in.** Deployment Protection covers you until it exists.
