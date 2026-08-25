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
from renderer.extract import extract           # noqa: E402

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


class EditIn(BaseModel):
    data: dict
    path: str
    instruction: str


# ------------------------------------------------------------------- routes
@app.get("/")
def index():
    return FileResponse(os.path.join(PUBLIC, "index.html"))


@app.get("/sample.json")
def sample():
    path = os.path.join(PUBLIC, "sample.json")
    if not os.path.exists(path):
        raise HTTPException(404, "no sample bundled")
    return FileResponse(path)


@app.get("/api/health")
def health():
    return {"ok": True, "assets": os.path.isdir(os.path.join(ROOT, "assets", "plates"))}


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
            "png": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()}


@app.post("/api/generate")
def api_generate(body: GenerateIn):
    try:
        data = extract(body.transcript, body.meta, body.milestones,
                       body.total_value)
    except Exception as exc:                                  # noqa: BLE001
        raise HTTPException(400, str(exc))
    return {"data": data, "warnings": data.pop("_warnings", [])}


@app.post("/api/edit")
def api_edit(body: EditIn):
    try:
        return {"ops": edit_node(body.data, body.path, body.instruction)}
    except PermissionError as exc:
        return JSONResponse({"error": str(exc)}, status_code=423)
    except Exception as exc:                                  # noqa: BLE001
        raise HTTPException(400, str(exc))
