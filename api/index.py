"""Single ASGI entrypoint. Vercel runs one Python app, so the editor and every
API route are served from here.

One bundle instead of four means the 5MB asset pack ships once, cold starts are
shared, and there is a single entrypoint for Vercel to find.
"""
import base64
import io
import os
import sys
import tempfile

from fastapi import FastAPI, HTTPException
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

PUBLIC = os.path.join(ROOT, "public")
app = FastAPI(title="Inceptives Proposal Creator", docs_url=None, redoc_url=None)


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
    engine: str = "auto"        # auto | builtin | v0


class EditIn(BaseModel):
    data: dict
    path: str
    instruction: str


# ------------------------------------------------------------------- routes
BUILD = "2026-08-26.10-key-test"


@app.get("/")
def index():
    # never cache the editor: a stale copy keeps calling old endpoints
    return FileResponse(os.path.join(PUBLIC, "index.html"),
                        headers={"cache-control": "no-store, must-revalidate"})


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
        "staged_endpoints": True,
        "assets": os.path.isdir(plates) and len(os.listdir(plates)) >= 15,
        "anthropic_key_set": bool(key),
        "brief_model": BRIEF_MODEL,
        "v0_screens": V0.configured(),
        "screenshot_provider": V0.SHOT_PROVIDER,
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
@app.post("/api/brief")
def api_brief(body: BriefIn):
    _need_key()
    try:
        return {"brief": make_brief(body.transcript, body.meta)}
    except Exception as exc:                                  # noqa: BLE001
        raise HTTPException(400, str(exc))


@app.post("/api/front")
def api_front(body: FrontIn):
    _need_key()
    try:
        return {"front": make_front(body.brief, body.meta)}
    except Exception as exc:                                  # noqa: BLE001
        raise HTTPException(400, str(exc))


@app.post("/api/features")
def api_features(body: FeaturesIn):
    _need_key()
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


@app.post("/api/auto-screens")
def api_auto_screens(body: AutoScreensIn):
    """Design and draw every screen the proposal needs, in one request.

    No UX Pilot, no export, no upload: the model writes a spec per screen and
    the renderer draws it in the proposal's own palette.
    """
    _need_key()
    slots = screen_slots(body.data)
    if not slots:
        return {"screens": {}, "count": 0}

    engine = body.engine
    if engine == "auto":
        engine = "v0" if V0.configured() else "builtin"
    if engine == "v0":
        if not V0.configured():
            raise HTTPException(
                400, "v0 screens need V0_API_KEY plus SCREENSHOT_PROVIDER and "
                     "SCREENSHOT_API_KEY set on the server.")
        out, errors = {}, []
        name = body.data.get("meta", {}).get("project_name", "the app")
        for slot in slots:
            try:
                png, url = V0.build_screen(V0.prompt_for(slot, name),
                                           slot["device"])
                out[slot["id"]] = ("data:image/png;base64," +
                                   base64.b64encode(png).decode())
            except Exception as exc:                          # noqa: BLE001
                errors.append("%s: %s" % (slot["id"], exc))
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


@app.post("/api/edit")
def api_edit(body: EditIn):
    try:
        return {"ops": edit_node(body.data, body.path, body.instruction)}
    except PermissionError as exc:
        return JSONResponse({"error": str(exc)}, status_code=423)
    except Exception as exc:                                  # noqa: BLE001
        raise HTTPException(400, str(exc))
