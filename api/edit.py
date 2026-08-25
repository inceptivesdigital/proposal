"""Rewrite one node by prompt. The model never sees the whole document."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from http.server import BaseHTTPRequestHandler

from _lib import read_json, reply, fail
from renderer.edit import edit_node


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            p = read_json(self)
            ops = edit_node(p["data"], p["path"], p["instruction"])
            reply(self, 200, {"ops": ops})
        except PermissionError as exc:
            fail(self, 423, str(exc))
        except Exception as exc:                       # noqa: BLE001
            fail(self, 400, str(exc))
