"""Single ASGI entrypoint. Vercel runs one Python app, so the editor and every
API route are served from here.

One bundle instead of four means the 5MB asset pack ships once, cold starts are
shared, and there is a single entrypoint for Vercel to find.
"""
import base64
import io
import json
import os
import sys
import tempfile

from fastapi import Cookie, FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from renderer import render                    # noqa: E402
from renderer.edit import edit_node            # noqa: E402
from renderer.extract import (                 # noqa: E402
    extract, make_brief, make_front, make_features, combine,
    make_screens, screen_slots)
from renderer.uiscreens import render_screen    # noqa: E402
from renderer import v0screens as V0            # noqa: E402
from renderer import htmlscreens as FAST         # noqa: E402
from renderer import db as DB                   # noqa: E402
from renderer import agent as AG                # noqa: E402
from renderer import qafix as QA                # noqa: E402
from renderer import learn as LEARN              # noqa: E402
from renderer import usage as USAGE              # noqa: E402
from renderer import mailer as MAIL               # noqa: E402
from renderer import sql as SQL                   # noqa: E402
from renderer import documents as DOCS            # noqa: E402
from renderer.model import CURRENCIES             # noqa: E402

PUBLIC = os.path.join(ROOT, "public")
app = FastAPI(title="Inceptives Digital Proposal Studio", docs_url=None,
              redoc_url=None, openapi_url=None)


@app.middleware("http")
async def security_headers(request, call_next):
    """Standard hardening: no framing, no sniffing, no referrer leakage."""
    response = await call_next(request)
    response.headers["x-frame-options"] = "DENY"
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["referrer-policy"] = "no-referrer"
    response.headers["permissions-policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["content-security-policy"] = (
        "default-src 'self'; img-src 'self' data: blob:; "
        "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; "
        "form-action 'self'")
    return response


# ------------------------------------------------------------------ helpers
def screens_from(payload):
    """Screens arrive as data URLs from the browser; write them to /tmp."""
    out = {}
    for key, value in (payload or {}).items():
        if not isinstance(value, str) or "," not in value:
            continue
        raw = base64.b64decode(value.split(",", 1)[1])
        path = os.path.join(tempfile.gettempdir(), "scr_%s.png" % abs(hash(key)))
        with open(path, "wb") as fh:
            fh.write(raw)
        out[key] = path
    return out


def render_pdf(data, screens, only=None):
    out = os.path.join(tempfile.gettempdir(), "proposal.pdf")
    meta = render(data, out, screens, only=only)
    with open(out, "rb") as fh:
        return fh.read(), meta


# ------------------------------------------------------------------- models
class RenderIn(BaseModel):
    data: dict
    screens_data: dict = {}


class PreviewIn(BaseModel):
    data: dict
    page: int = 0
    scale: float = 1.5
    screens_data: dict = {}


class GenerateIn(BaseModel):
    transcript: str
    meta: dict
    milestones: list = []
    total_value: float = 0


class BriefIn(BaseModel):
    transcript: str
    meta: dict


class FrontIn(BaseModel):
    brief: dict
    meta: dict


class FeaturesIn(BaseModel):
    brief: dict
    front: dict
    meta: dict
    milestones: list = []
    total_value: float = 0


class ScreensPdfIn(BaseModel):
    pdf: str            # data URL or raw base64 of the UX Pilot export
    scale: float = 2.0


class AutoScreensIn(BaseModel):
    data: dict
    brief: dict = {}
    engine: str = "auto"        # auto | builtin | v0 | fast | none
    only_first: bool = False    # generate one screen, for testing
    index: int = -1             # generate exactly this slot, for progress
    slot_ids: list = []         # generate only these slots
    have: list = []             # slots that already have a screen


class RecoverIn(BaseModel):
    sources: dict = {}          # slot id -> {"url": ..., "chat_id": ..., "device": ...}


class OneScreenIn(BaseModel):
    data: dict
    slot_id: str


class AuthIn(BaseModel):
    email: str
    password: str
    name: str = ""


class DocIn(BaseModel):
    filename: str = ""
    data: str = ""              # data URL from the browser


class VerifyIn(BaseModel):
    email: str
    code: str


class SaveIn(BaseModel):
    data: dict
    note: str = "Edited"
    screens: dict = {}


class NameIn(BaseModel):
    name: str = ""


class DataIn(BaseModel):
    data: dict


class ChatIn(BaseModel):
    data: dict
    instruction: str
    context: dict = {}
    proposal_id: str = ""
    images: dict = {}          # id -> data URL, attached in the chat


class EditIn(BaseModel):
    data: dict
    path: str
    instruction: str


# ------------------------------------------------------------------- routes
BUILD = "2026-08-29.3-db-probe"
PRODUCTION = os.environ.get("ENVIRONMENT", "").lower() in ("production", "prod")


def production_warnings():
    """Things that are fine on a laptop and not fine in front of clients."""
    out = []
    reachable, detail = SQL.ping()
    if not reachable:
        out.append("The database is not reachable: %s" % detail)
    if not SQL.persistent():
        out.append("No DATABASE_URL, and the only writable place here is a "
                   "temporary folder. Accounts and proposals will disappear "
                   "when the server restarts. Add DATABASE_URL.")
    elif not SQL.IS_PG:
        out.append("Running on a local SQLite file. Fine on your own machine, "
                   "not on a serverless host.")
    if not MAIL.configured():
        out.append("No mail server, so sign-up codes are printed to the log "
                   "instead of emailed.")
    if os.environ.get("COOKIE_SECURE", "0") != "1":
        out.append("COOKIE_SECURE is not 1, so session cookies are sent over "
                   "plain HTTP as well as HTTPS.")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        out.append("ANTHROPIC_API_KEY is not set, so nothing can be generated.")
    return out


@app.get("/")
def index():
    # never cache the editor: a stale copy keeps calling old endpoints
    return FileResponse(os.path.join(PUBLIC, "index.html"),
                        headers={"cache-control": "no-store, must-revalidate"})


@app.get("/assets/{name}")
def asset(name: str):
    """Static brand assets. The name is sanitised before it touches the disk."""
    safe = os.path.basename(name)
    path = os.path.join(PUBLIC, "assets", safe)
    if not os.path.isfile(path) or not safe.lower().endswith((".png", ".jpg",
                                                              ".svg", ".ico")):
        raise HTTPException(404, "No such asset.")
    return FileResponse(path, headers={"cache-control": "public, max-age=86400"})


@app.get("/sample.json")
def sample():
    path = os.path.join(PUBLIC, "sample.json")
    if not os.path.exists(path):
        raise HTTPException(404, "no sample bundled")
    return FileResponse(path)


@app.get("/api/health")
def health():
    """Reports the three things that actually break a deployment."""
    from renderer.extract import MODEL as GEN_MODEL
    from renderer.edit import MODEL as EDIT_MODEL
    plates = os.path.join(ROOT, "assets", "plates")
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    from renderer.extract import BRIEF_MODEL
    return {
        "ok": True,
        "build": BUILD,
        "database": SQL.backend(),
        "database_reachable": SQL.ping()[0],
        "tables": SQL.table_check(),
        "mail_configured": MAIL.configured(),
        "warnings": production_warnings(),
        "staged_endpoints": True,
        "assets": os.path.isdir(plates) and len(os.listdir(plates)) >= 15,
        "anthropic_key_set": bool(key),
        "brief_model": BRIEF_MODEL,
        "v0_screens": V0.configured(),
        "fast_screens": FAST.configured(),
        "screenshot_provider": V0.SHOT_PROVIDER,
        "photo_source": "unsplash" if FAST.UNSPLASH_KEY else "picsum",
        "v0_base": V0.V0_BASE,
        "generate_model": GEN_MODEL,
        "edit_model": EDIT_MODEL,
    }


@app.post("/api/render")
def api_render(body: RenderIn):
    try:
        pdf, meta = render_pdf(body.data, screens_from(body.screens_data))
    except Exception as exc:                                  # noqa: BLE001
        raise HTTPException(400, str(exc))
    name = (body.data.get("meta", {}).get("project_name") or "proposal")
    return {
        "pdf": base64.b64encode(pdf).decode(),
        "filename": "%s.pdf" % name.replace(" ", "_"),
        "milestones_ok": meta["milestones_ok"],
        "milestone_warning": meta["milestone_warning"],
        "failures": meta.get("failures", []),
        "qa": meta.get("qa", []),
    }


class OutlineIn(BaseModel):
    data: dict


@app.post("/api/outline")
def api_outline(body: OutlineIn):
    """Page names, editable-field counts and layout issues for the page rail."""
    from renderer.render import page_plan
    from renderer.kit import register_fonts
    register_fonts()
    try:
        pdf, meta = render_pdf(body.data, {}, only=None)
    except Exception as exc:                                  # noqa: BLE001
        raise HTTPException(400, str(exc))
    counts = {}
    for t in meta.get("textmap", []):
        counts[t["page"]] = counts.get(t["page"], 0) + 1
    from renderer.agent import KEY_FOR_NAME
    core = 0
    pages = []
    for i, n in enumerate(meta["names"]):
        key = KEY_FOR_NAME.get(n)
        if key is None and n.startswith("Core Features"):
            key = "core_pages.%d" % core
            core += 1
        pages.append({"index": i, "name": n, "fields": counts.get(i, 0),
                      "key": key or ""})
    return {"pages": pages, "qa": meta.get("qa", []),
            "failures": meta.get("failures", []),
            "textmap": meta.get("textmap", [])}


@app.post("/api/preview")
def api_preview(body: PreviewIn):
    try:
        # render only the requested page, so typing stays responsive
        pdf, meta = render_pdf(body.data, screens_from(body.screens_data),
                               only=body.page)
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(io.BytesIO(pdf))
        buf = io.BytesIO()
        doc[0].render(scale=body.scale).to_pil().save(buf, format="PNG")
    except Exception as exc:                                  # noqa: BLE001
        raise HTTPException(400, str(exc))
    idx = min(body.page, meta["pages"] - 1)
    return {"page": idx, "pages": meta["pages"], "name": meta["names"][idx],
            "failures": meta.get("failures", []), "qa": meta.get("qa", []),
            "textmap": [t for t in meta.get("textmap", [])],
            "png": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()}


@app.post("/api/generate")
def api_generate(body: GenerateIn):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(
            500, "ANTHROPIC_API_KEY is not set on the server. Add it in Vercel "
                 "under Settings > Environment Variables, then redeploy.")
    try:
        data = extract(body.transcript, body.meta, body.milestones,
                       body.total_value)
    except Exception as exc:                                  # noqa: BLE001
        raise HTTPException(400, str(exc))
    return {"data": data, "warnings": data.pop("_warnings", [])}


def _need_key():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(
            500, "ANTHROPIC_API_KEY is not set on the server. Add it in Vercel "
                 "under Settings > Environment Variables, then redeploy.")


# Generation runs as three requests rather than one, because three model calls
# in a single request exceed the platform's 60 second limit and return a 504.
@app.get("/api/currencies")
def api_currencies():
    """The currencies a proposal can be priced in."""
    return {"currencies": [{"code": c, "symbol": v[0].strip(), "name": v[1]}
                           for c, v in CURRENCIES.items()]}


@app.post("/api/read-document")
def api_read_document(body: DocIn):
    """Pull the text out of an uploaded transcript or brief."""
    try:
        text = DOCS.read_data_url(body.filename, body.data)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:                                  # noqa: BLE001
        raise HTTPException(400, "Could not read that file: %s" % exc)
    return {"text": text, "characters": len(text),
            "filename": os.path.basename(body.filename or "document")}


@app.post("/api/brief")
def api_brief(body: BriefIn, session: str = Cookie(None)):
    _need_key()
    u = DB.user_for(session)
    USAGE.set_context(u["id"] if u else None, "new")
    try:
        return {"brief": make_brief(body.transcript, body.meta)}
    except Exception as exc:                                  # noqa: BLE001
        raise HTTPException(400, str(exc))


@app.post("/api/front")
def api_front(body: FrontIn, session: str = Cookie(None)):
    _need_key()
    u = DB.user_for(session)
    USAGE.set_context(u["id"] if u else None, "new")
    try:
        return {"front": make_front(body.brief, body.meta)}
    except Exception as exc:                                  # noqa: BLE001
        raise HTTPException(400, str(exc))


@app.post("/api/features")
def api_features(body: FeaturesIn, session: str = Cookie(None)):
    _need_key()
    u = DB.user_for(session)
    USAGE.set_context(u["id"] if u else None, "new")
    try:
        rest = make_features(body.brief, body.front, body.meta,
                             len(body.milestones))
        data = combine(body.front, rest, body.meta, body.milestones,
                       body.total_value)
    except Exception as exc:                                  # noqa: BLE001
        raise HTTPException(400, str(exc))
    return {"data": data, "warnings": data.pop("_warnings", [])}


@app.post("/api/screens-from-pdf")
def api_screens_from_pdf(body: ScreensPdfIn):
    """Split a UX Pilot export into one cropped image per screen.

    UX Pilot exports every screen in a single PDF, so the app does the splitting
    rather than asking anyone to cut images up by hand.
    """
    try:
        raw = body.pdf.split(",", 1)[-1]
        data = base64.b64decode(raw)
        import numpy as np
        import pypdfium2 as pdfium
        from PIL import Image
        doc = pdfium.PdfDocument(io.BytesIO(data))
        out = []
        for i in range(len(doc)):
            im = doc[i].render(scale=body.scale).to_pil().convert("RGB")
            arr = np.asarray(im).astype(int)
            bg = np.median(arr.reshape(-1, 3), axis=0)
            mask = np.abs(arr - bg).sum(2) > 16
            ys, xs = np.where(mask)
            if len(xs):
                pad = 6
                im = im.crop((max(int(xs.min())-pad, 0), max(int(ys.min())-pad, 0),
                              min(int(xs.max())+pad, im.width),
                              min(int(ys.max())+pad, im.height)))
            buf = io.BytesIO()
            im.save(buf, format="PNG", optimize=True)
            out.append({"page": i + 1, "w": im.width, "h": im.height,
                        "png": "data:image/png;base64," +
                               base64.b64encode(buf.getvalue()).decode()})
    except Exception as exc:                                  # noqa: BLE001
        raise HTTPException(400, "Could not read that PDF: %s" % exc)
    return {"screens": out}


@app.get("/api/test-keys")
def api_test_keys():
    """Calls v0 and the screenshot provider for real, so a wrong key shows up
    here rather than halfway through generating a proposal."""
    return V0.test_keys()


@app.get("/api/v0-chats")
def api_v0_chats():
    """Builds already sitting in the v0 account, so nothing is paid for twice."""
    if not V0.V0_KEY:
        raise HTTPException(400, "V0_API_KEY is not set.")
    try:
        return {"chats": V0.list_chats(30)}
    except Exception as exc:                                  # noqa: BLE001
        raise HTTPException(400, str(exc))


@app.post("/api/screens-recover")
def api_screens_recover(body: RecoverIn):
    """Re-photograph builds that already exist. No model call, no credits."""
    out, errors = {}, []
    for slot_id, src in (body.sources or {}).items():
        try:
            url = src.get("url")
            if not url and src.get("chat_id"):
                url = V0.preview_for_chat(src["chat_id"])
            png = V0.refetch(url, src.get("device", "phone"))
            out[slot_id] = ("data:image/png;base64," +
                            base64.b64encode(png).decode())
        except Exception as exc:                              # noqa: BLE001
            errors.append("%s: %s" % (slot_id, exc))
    return {"screens": out, "count": len(out), "errors": errors}


@app.post("/api/screen-slots")
def api_screen_slots(body: DataIn):
    """The screens this proposal needs, so the editor can work through them."""
    return {"slots": screen_slots(body.data)}


@app.post("/api/auto-screens")
def api_auto_screens(body: AutoScreensIn):
    """Design and draw every screen the proposal needs, in one request.

    No UX Pilot, no export, no upload: the model writes a spec per screen and
    the renderer draws it in the proposal's own palette.
    """
    _need_key()
    slots = screen_slots(body.data)
    if not slots:
        return {"screens": {}, "count": 0, "engine": body.engine}
    if body.slot_ids:                       # only the ones asked for
        wanted = set(body.slot_ids)
        slots = [s for s in slots if s["id"] in wanted]
    elif body.have:                         # fill the gaps, leave the rest alone
        done = set(body.have)
        slots = [s for s in slots if s["id"] not in done]
    if not slots:
        return {"screens": {}, "count": 0, "engine": body.engine,
                "note": "Every slot already has a screen."}
    if body.index >= 0:
        slots = slots[body.index:body.index+1]

    engine = body.engine
    if engine == "auto":
        # fast beats v0 on time by a wide margin and costs no v0 credits
        engine = ("fast" if FAST.configured()
                  else "v0" if V0.configured() else "builtin")

    if engine == "fast":
        if not FAST.configured():
            raise HTTPException(
                400, "Fast screens need SCREENSHOT_PROVIDER and "
                     "SCREENSHOT_API_KEY set on the server.")
        _need_key()
        name = body.data.get("meta", {}).get("project_name", "the app")
        todo = slots[:1] if body.only_first else slots
        if body.index >= 0:
            todo = slots
        try:
            pngs, _html = FAST.build(todo, name)
        except Exception as exc:                              # noqa: BLE001
            raise HTTPException(400, str(exc))
        out = {}
        for slot, png in zip(todo, pngs):
            out[slot["id"]] = ("data:image/png;base64," +
                               base64.b64encode(png).decode())
        u = DB.user_for(session) if "session" in dir() else None
        return {"screens": out, "count": len(out), "engine": "fast",
                "errors": [], "batched": True}
    if engine == "v0":
        if not V0.configured():
            raise HTTPException(
                400, "v0 screens need V0_API_KEY plus SCREENSHOT_PROVIDER and "
                     "SCREENSHOT_API_KEY set on the server.")
        out, errors = {}, []
        name = body.data.get("meta", {}).get("project_name", "the app")
        todo = slots[:1] if body.only_first else slots
        for slot in todo:
            try:
                png, url = V0.build_screen(V0.prompt_for(slot, name),
                                           slot["device"])
                out[slot["id"]] = ("data:image/png;base64," +
                                   base64.b64encode(png).decode())
            except Exception as exc:                          # noqa: BLE001
                detail = getattr(exc, "body", "") or str(exc)
                errors.append("%s: %s" % (slot["id"], detail[:220]))
        return {"screens": out, "count": len(out), "engine": "v0",
                "errors": errors}
    try:
        specs = make_screens(slots, body.brief, body.data.get("meta", {}))
    except Exception as exc:                                  # noqa: BLE001
        raise HTTPException(400, str(exc))
    by_id = {s.get("id"): s for s in specs if isinstance(s, dict)}
    out = {}
    for slot in slots:
        spec = by_id.get(slot["id"])
        if not spec:
            continue
        try:
            im = render_screen(spec, slot["device"]).convert("RGB")
        except Exception:                                     # noqa: BLE001
            continue
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True)
        out[slot["id"]] = ("data:image/png;base64," +
                           base64.b64encode(buf.getvalue()).decode())
    return {"screens": out, "count": len(out), "engine": "builtin"}


@app.get("/api/screen-slots")
def api_screen_slots(data: str = ""):
    return {"note": "POST the document to /api/auto-screens instead"}


@app.post("/api/v0-screen")
def api_v0_screen(body: OneScreenIn):
    """Build one screen through v0.

    Each screen is its own request. A v0 build plus a screenshot can take most
    of a minute, so doing several in one request would hit the platform limit.
    """
    if not V0.configured():
        raise HTTPException(400, "v0 screens need V0_API_KEY, SCREENSHOT_PROVIDER "
                                 "and SCREENSHOT_API_KEY.")
    slot = next((s for s in screen_slots(body.data)
                 if s["id"] == body.slot_id), None)
    if not slot:
        raise HTTPException(404, "no screen slot called %r" % body.slot_id)
    name = body.data.get("meta", {}).get("project_name", "the app")
    try:
        png, url = V0.build_screen(V0.prompt_for(slot, name), slot["device"])
    except Exception as exc:                                  # noqa: BLE001
        detail = getattr(exc, "body", "") or str(exc)
        raise HTTPException(400, "%s: %s" % (slot["id"], detail[:400]))
    return {"id": slot["id"], "url": url,
            "png": "data:image/png;base64," + base64.b64encode(png).decode()}


# ------------------------------------------------------------------ accounts
def me(session):
    user = DB.user_for(session)
    if not user:
        raise HTTPException(401, "Sign in to continue.")
    return user


def admin(session):
    user = me(session)
    if not DB.is_admin(user):
        raise HTTPException(403, "Administrators only.")
    return user


def _secure_cookie():
    return os.environ.get("COOKIE_SECURE", "0") == "1"


@app.post("/api/auth/signup")
def api_signup(body: AuthIn):
    """Step one. No account exists until the emailed code comes back."""
    try:
        code = DB.start_signup(body.email, body.password, body.name)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:                                  # noqa: BLE001
        # on a fresh deployment this is almost always storage
        ok, detail = SQL.ping()
        if not ok:
            raise HTTPException(
                500, "The database is not reachable, so accounts cannot be "
                     "created. %s" % detail)
        if not SQL.persistent():
            raise HTTPException(
                500, "The server has nowhere to save accounts. Add a "
                     "DATABASE_URL environment variable pointing at your "
                     "Postgres database, then redeploy.")
        raise HTTPException(500, "Could not start the sign-up: %s" % exc)
    try:
        sent = MAIL.send_code(body.email.strip().lower(), code)
    except Exception as exc:                                  # noqa: BLE001
        raise HTTPException(400, str(exc))
    return {"pending": True, "email": body.email.strip().lower(),
            "mail_configured": MAIL.configured(),
            "note": ("We sent a six-digit code to %s." % body.email
                     if sent.get("sent") else
                     "No mail server is configured, so the code was printed in "
                     "the server log.")}


@app.post("/api/auth/verify")
def api_verify(body: VerifyIn, response: Response):
    """Step two. The code proves the address, so the account is created."""
    try:
        out = DB.verify_signup(body.email, body.code)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    response.set_cookie("session", out["token"], httponly=True, samesite="lax",
                        secure=_secure_cookie(), max_age=60*60*24*14)
    return {"user": out["user"]}


@app.post("/api/auth/login")
def api_login(body: AuthIn, response: Response):
    try:
        out = DB.login(body.email, body.password)
    except ValueError as exc:
        raise HTTPException(401, str(exc))
    response.set_cookie("session", out["token"], httponly=True, samesite="lax",
                        secure=_secure_cookie(), max_age=60*60*24*14)
    return {"user": out["user"]}


@app.post("/api/auth/logout")
def api_logout(response: Response, session: str = Cookie(None)):
    DB.logout(session)
    response.delete_cookie("session")
    return {"ok": True}


@app.get("/api/auth/me")
def api_me(session: str = Cookie(None)):
    return {"user": DB.user_for(session),
            "allowed_domains": DB.ALLOWED_DOMAINS,
            "mail_configured": MAIL.configured(),
            "accounts": len(DB.users())}


# ----------------------------------------------------------------- proposals
@app.get("/api/proposals")
def api_list(session: str = Cookie(None)):
    return {"proposals": DB.listing(me(session)["id"])}


@app.post("/api/proposals")
def api_create(body: SaveIn, session: str = Cookie(None)):
    u = me(session)
    name = body.data.get("meta", {}).get("project_name") or "Untitled proposal"
    pid = DB.create(u["id"], name, body.data, u["name"])
    return {"id": pid}


@app.get("/api/proposals/{pid}")
def api_get(pid: str, session: str = Cookie(None)):
    try:
        return DB.load(pid, me(session)["id"])
    except KeyError as exc:
        raise HTTPException(404, str(exc))


@app.post("/api/proposals/{pid}/save")
def api_save(pid: str, body: SaveIn, session: str = Cookie(None)):
    u = me(session)
    try:
            n = DB.save(pid, u["id"], body.data, u["name"], body.note, body.screens)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    return {"version": n}


@app.post("/api/proposals/{pid}/duplicate")
def api_duplicate(pid: str, body: NameIn, session: str = Cookie(None)):
    u = me(session)
    try:
        return {"id": DB.duplicate(pid, u["id"], body.name or None, u["name"])}
    except KeyError as exc:
        raise HTTPException(404, str(exc))


@app.get("/api/proposals/{pid}/versions")
def api_versions(pid: str, session: str = Cookie(None)):
    return {"versions": DB.versions(pid, me(session)["id"])}


@app.get("/api/proposals/{pid}/log")
def api_log(pid: str, session: str = Cookie(None)):
    return {"log": DB.log(pid, me(session)["id"])}


@app.post("/api/proposals/{pid}/restore/{n}")
def api_restore(pid: str, n: int, session: str = Cookie(None)):
    u = me(session)
    return {"version": DB.restore(pid, u["id"], n, u["name"])}


@app.post("/api/proposals/{pid}/undo")
def api_undo(pid: str, session: str = Cookie(None)):
    u = me(session)
    try:
        return {"version": DB.undo(pid, u["id"], u["name"])}
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/proposals/{pid}/publish")
def api_publish(pid: str, session: str = Cookie(None)):
    u = me(session)
    return DB.publish(pid, u["id"], u["name"])


@app.delete("/api/proposals/{pid}")
def api_delete(pid: str, session: str = Cookie(None)):
    DB.delete(pid, me(session)["id"])
    return {"ok": True}


# --------------------------------------------------------------- chat agent
@app.post("/api/qa-scan")
def api_qa_scan(body: DataIn):
    """What is wrong with this proposal, without changing anything."""
    return QA.scan(body.data, screens_from({}))


class ApplyIn(BaseModel):
    data: dict
    items: list = []
    ids: list = []


@app.post("/api/qa-review")
def api_qa_review(body: DataIn):
    """Everything wrong with the proposal, each with a proposed fix."""
    return QA.review(body.data, {})


@app.post("/api/qa-apply")
def api_qa_apply(body: ApplyIn):
    """Apply only the findings the user ticked."""
    data = json.loads(json.dumps(body.data))
    try:
        done = QA.apply_selected(data, body.items, body.ids)
    except Exception as exc:                                  # noqa: BLE001
        raise HTTPException(400, str(exc))
    return {"data": data, "applied": done}


@app.post("/api/qa-fix")
def api_qa_fix(body: DataIn):
    """Fix everything that can be fixed safely, then shorten what overruns."""
    _need_key()
    data = json.loads(json.dumps(body.data))
    try:
        out = QA.repair(data)
    except Exception as exc:                                  # noqa: BLE001
        raise HTTPException(400, str(exc))
    return {"data": data, "changes": out["changes"],
            "remaining": out["remaining"]}


@app.post("/api/chat")
def api_chat(body: ChatIn, session: str = Cookie(None)):
    """Plain-English editing. The model returns operations, never a document."""
    _need_key()
    user = DB.user_for(session)
    USAGE.set_context(user["id"] if user else None, body.proposal_id or "-")
    ctx = dict(body.context or {})
    if body.images:
        ctx["images"] = [{"id": k, "note": "attached by the user"}
                         for k in body.images]
    if user:
        ctx["preferences"] = [p["text"] for p in LEARN.preferences(user["id"])]
    try:
        out = AG.chat(body.data, body.instruction, context=ctx or None)
    except Exception as exc:                                  # noqa: BLE001
        raise HTTPException(400, str(exc))
    data = json.loads(json.dumps(body.data))
    applied = AG.apply_ops(data, out["ops"])
    learned, rule = None, None
    if user:
        learned = LEARN.record(user["id"], body.proposal_id or "-",
                               body.instruction, applied > 0)
        # what actually moved, so the lesson is tied to a field not just a phrase
        for path in DB.changed_paths(body.data, data)[:6]:
            if path.startswith("_"):
                continue
            r = LEARN.record_correction(
                user["id"], body.proposal_id or "-", path,
                _at(body.data, path), _at(data, path), body.instruction)
            if r.get("is_rule"):
                rule = r
    if user:
        DB.note_activity(user["id"], user["email"], "asked the assistant",
                         body.instruction[:160], body.proposal_id or "")
    return {"data": data, "applied": applied, "note": out["note"],
            "ops": out["ops"], "learned": learned, "rule": rule}


def _at(data, path):
    node = data
    for key in path.split("."):
        try:
            node = node[int(key)] if key.isdigit() else node[key]
        except Exception:                                     # noqa: BLE001
            return ""
    return node if isinstance(node, str) else ""


@app.get("/api/admin/overview")
def api_admin_overview(session: str = Cookie(None)):
    """System health, usage and what it is costing."""
    admin(session)
    plates = os.path.join(ROOT, "assets", "plates")
    return {
        "health": {
            "build": BUILD,
            "assets": os.path.isdir(plates) and len(os.listdir(plates)) >= 15,
            "anthropic_key_set": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "fast_screens": FAST.configured(),
            "v0_screens": V0.configured(),
            "screenshot_provider": V0.SHOT_PROVIDER,
            "photo_source": ("Unsplash, matched to the subject"
                             if FAST.UNSPLASH_KEY else
                             "Picsum. Set UNSPLASH_ACCESS_KEY for photography "
                             "matched to the subject."),
            "generate_model": os.environ.get("PROPOSAL_MODEL", "claude-sonnet-5"),
            "allowed_domains": DB.ALLOWED_DOMAINS,
        },
        "database": {"backend": SQL.backend(), "reachable": SQL.ping()[0]},
        "mail_configured": MAIL.configured(),
        "totals": USAGE.totals(),
        "average_proposal": USAGE.average_proposal_cost(),
        "by_user": USAGE.by_user(),
        "by_proposal": USAGE.by_proposal(),
        "by_kind": USAGE.by_kind(),
        "recent": USAGE.recent(),
        "users": DB.users(),
        "rules": LEARN.rules(),
        "activity": DB.activity(120),
        "activity_by_user": DB.activity_summary(),
    }


@app.post("/api/admin/user-role")
def api_user_role(body: dict, session: str = Cookie(None)):
    admin(session)
    DB.set_role(body.get("user_id", ""), body.get("role", "member"))
    return {"ok": True}


@app.post("/api/admin/user-disabled")
def api_user_disabled(body: dict, session: str = Cookie(None)):
    admin(session)
    DB.set_disabled(body.get("user_id", ""), bool(body.get("disabled")))
    return {"ok": True}


@app.get("/api/credits")
def api_credits():
    """Does the account actually have room to work? Calls each service."""
    out = {"anthropic": {"ok": False, "detail": ""}}
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        out["anthropic"]["detail"] = "ANTHROPIC_API_KEY is not set."
    else:
        try:
            import anthropic
            c = anthropic.Anthropic()
            m = c.messages.create(
                model=os.environ.get("PROPOSAL_MODEL", "claude-sonnet-5"),
                max_tokens=8, messages=[{"role": "user", "content": "ping"}])
            out["anthropic"] = {"ok": True,
                                "detail": "Key works and the account has credit."}
            USAGE.set_context(None, "healthcheck")
            USAGE.record_model(m.model, "health check",
                               getattr(m.usage, "input_tokens", 0),
                               getattr(m.usage, "output_tokens", 0))
        except Exception as exc:                              # noqa: BLE001
            text = str(exc)
            out["anthropic"] = {
                "ok": False,
                "detail": ("Out of credit or over the rate limit." if
                           "credit" in text.lower() or "429" in text
                           else text[:220])}
    out["screens"] = V0.test_keys()
    out["spend"] = {"total": USAGE.totals().get("cost", 0),
                    "average_proposal": USAGE.average_proposal_cost()}
    return out


@app.get("/api/rules")
def api_rules():
    """What the team has corrected enough times that generation now follows it."""
    return {"rules": LEARN.rules(), "prompt": LEARN.rules_for_prompt()}


@app.post("/api/rules/mute")
def api_mute_rule(body: NameIn, session: str = Cookie(None)):
    me(session)
    LEARN.mute_rule(body.name, True)
    return {"ok": True}


@app.get("/api/preferences")
def api_preferences(session: str = Cookie(None)):
    """What this team keeps asking for."""
    user = DB.user_for(session)
    if not user:
        return {"preferences": [], "history": []}
    return {"preferences": LEARN.preferences(user["id"]),
            "history": LEARN.history(user["id"], 20)}


@app.post("/api/preferences/suggest")
def api_suggest(body: DataIn, session: str = Cookie(None)):
    """Preferences worth offering on this proposal."""
    user = DB.user_for(session)
    if not user:
        return {"suggestions": []}
    return {"suggestions": LEARN.suggestions(user["id"], body.data)}


@app.post("/api/preferences/mute")
def api_mute(body: NameIn, session: str = Cookie(None)):
    user = me(session)
    LEARN.mute(user["id"], body.name, True)
    return {"ok": True}


@app.post("/api/edit")
def api_edit(body: EditIn):
    try:
        return {"ops": edit_node(body.data, body.path, body.instruction)}
    except PermissionError as exc:
        return JSONResponse({"error": str(exc)}, status_code=423)
    except Exception as exc:                                  # noqa: BLE001
        raise HTTPException(400, str(exc))
