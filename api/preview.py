"""POST a document plus a page index, get a PNG preview of that page."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import base64
import io
from http.server import BaseHTTPRequestHandler

from _lib import read_json, reply, fail, screens_from, render_pdf


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            payload = read_json(self)
            page = int(payload.get("page", 0))
            scale = float(payload.get("scale", 1.4))
            # render only the requested page, not the whole deck
            pdf, meta = render_pdf(payload["data"], screens_from(payload),
                                   only=page)
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(io.BytesIO(pdf))
            buf = io.BytesIO()
            doc[0].render(scale=scale).to_pil().save(buf, format="PNG")
            reply(self, 200, {
                "page": min(page, meta["pages"] - 1),
                "pages": meta["pages"],
                "name": meta["names"][min(page, meta["pages"] - 1)],
                "png": "data:image/png;base64," +
                       base64.b64encode(buf.getvalue()).decode(),
            })
        except Exception as exc:                       # noqa: BLE001
            fail(self, 400, str(exc))
