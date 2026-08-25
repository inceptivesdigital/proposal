"""Transcript in, complete proposal document out. One model call."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from http.server import BaseHTTPRequestHandler

from _lib import read_json, reply, fail
from renderer.extract import extract


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            p = read_json(self)
            data = extract(p["transcript"], p["meta"],
                           p.get("milestones", []), p.get("total_value", 0))
            reply(self, 200, {"data": data,
                              "warnings": data.pop("_warnings", [])})
        except Exception as exc:                       # noqa: BLE001
            fail(self, 400, str(exc))
