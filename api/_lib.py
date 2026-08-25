"""Shared bootstrap for the Vercel Python functions."""
import base64
import io
import json
import os
import sys
import tempfile

# the renderer package sits one level up from api/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from renderer import render                      # noqa: E402
from renderer.model import check_milestones      # noqa: E402


def read_json(handler):
    length = int(handler.headers.get("content-length") or 0)
    return json.loads(handler.rfile.read(length) or b"{}")


def reply(handler, status, payload):
    body = json.dumps(payload).encode()
    handler.send_response(status)
    handler.send_header("content-type", "application/json")
    handler.send_header("content-length", str(len(body)))
    handler.send_header("cache-control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def fail(handler, status, message):
    reply(handler, status, {"error": message})


def screens_from(payload):
    """Screens arrive as data URLs from the browser and are written to /tmp."""
    out = {}
    for key, value in (payload.get("screens_data") or {}).items():
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
    result = render(data, out, screens, only=only)
    with open(out, "rb") as fh:
        return fh.read(), result
