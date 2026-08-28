"""POST a proposal document, get the finished PDF back as base64."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import base64
from http.server import BaseHTTPRequestHandler

from _lib import read_json, reply, fail, screens_from, render_pdf


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            payload = read_json(self)
            data = payload["data"]
            pdf, result = render_pdf(data, screens_from(payload))
            reply(self, 200, {
                "pdf": base64.b64encode(pdf).decode(),
                "filename": "%s.pdf" % (data["meta"].get("project_name")
                                        or "proposal").replace(" ", "_"),
                "milestones_ok": result["milestones_ok"],
                "milestone_warning": result["milestone_warning"],
            })
        except Exception as exc:                       # noqa: BLE001
            fail(self, 400, str(exc))
