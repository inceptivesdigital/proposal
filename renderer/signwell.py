"""Sending a proposal for signature, through SignWell.

Written as an adapter so the rest of the system never names a provider. The
proposal is already signed by the sender when it gets here, so every document
has exactly one recipient: the client.
"""
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

API = os.environ.get("SIGNWELL_API_BASE", "https://www.signwell.com/api/v1")
KEY = os.environ.get("SIGNWELL_API_KEY", "")
# Real contracts by default. Set SIGNWELL_TEST_MODE=1 only while trying things
# out: test documents are watermarked and only reach your own domain.
TEST_MODE = os.environ.get("SIGNWELL_TEST_MODE", "0") == "1"
TIMEOUT = int(os.environ.get("SIGNWELL_TIMEOUT", "60"))

NAME = "SignWell"


def configured():
    return bool(KEY)


def _headers():
    return {"X-Api-Key": KEY, "content-type": "application/json",
            "accept": "application/json"}


def _call(method, path, payload=None):
    url = "%s%s" % (API, path)
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=_headers(),
                                 method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read().decode()
        return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode()[:400]
        except Exception:                                     # noqa: BLE001
            pass
        raise RuntimeError("%s returned HTTP %s. %s" % (NAME, exc.code, detail))
    except urllib.error.URLError as exc:
        raise RuntimeError("%s could not be reached: %s" % (NAME, exc.reason))


def send(pdf_bytes, filename, client_name, client_email, subject, message,
         send_email=True, sender_name="", reply_to=""):
    """Create the document and, unless told otherwise, have SignWell email it.

    Returns the document id and the client's signing link.
    """
    if not configured():
        raise RuntimeError("SIGNWELL_API_KEY is not set on the server.")
    payload = {
        "test_mode": TEST_MODE,
        "name": filename,
        "subject": subject,
        "message": message,
        "files": [{"name": filename,
                   "file_base64": base64.b64encode(pdf_bytes).decode()}],
        "recipients": [{"id": "1", "name": client_name, "email": client_email,
                        "send_email": bool(send_email)}],
        "fields": [[
            {"api_id": "client_signature", "type": "signature", "required": True,
             "recipient_id": "1", "page": 0, "x": 0, "y": 0},
        ]],
        "embedded_signing": True,
        "draft": False,
        "apply_signing_order": False,
        "reminders": True,
    }
    if reply_to:
        payload["reply_to"] = reply_to
    if sender_name:
        payload["sender_name"] = sender_name
    out = _call("POST", "/documents/", payload)
    return _summarise(out)


def _summarise(out):
    """The few things the rest of the system cares about."""
    recipients = out.get("recipients") or []
    link = ""
    for r in recipients:
        link = r.get("embedded_signing_url") or r.get("signing_url") or link
    return {"id": out.get("id"), "status": out.get("status", "sent"),
            "link": link, "name": out.get("name", ""), "raw_status": out}


def status(document_id):
    out = _call("GET", "/documents/%s/" % document_id)
    return _summarise(out)


def remind(document_id):
    """Ask the service to email the client again."""
    return _call("POST", "/documents/%s/remind/" % document_id, {})


def signed_pdf(document_id):
    """The completed document, with its certificate page."""
    url = "%s/documents/%s/completed_pdf/?audit_page=true" % (API, document_id)
    req = urllib.request.Request(url, headers={"X-Api-Key": KEY})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError("Could not fetch the signed PDF: HTTP %s" % exc.code)


def audit_trail(document_id):
    """Every recorded event, for the trail shown in the studio."""
    out = _call("GET", "/documents/%s/" % document_id)
    events = []
    for r in out.get("recipients") or []:
        for key, label in (("sent_at", "sent"), ("viewed_at", "viewed"),
                           ("completed_at", "signed"),
                           ("declined_at", "declined")):
            if r.get(key):
                events.append({"who": r.get("email", ""), "what": label,
                               "at": r.get(key)})
    for key, label in (("created_at", "created"), ("completed_at", "completed")):
        if out.get(key):
            events.append({"who": "document", "what": label, "at": out[key]})
    return sorted(events, key=lambda e: str(e["at"]))


def check():
    """Is the key live? Used by the API health panel."""
    if not configured():
        return {"ok": False, "detail": "SIGNWELL_API_KEY is not set."}
    try:
        _call("GET", "/me/")
        return {"ok": True, "detail": "Key accepted%s."
                % (" (test mode)" if TEST_MODE else "")}
    except Exception as exc:                                  # noqa: BLE001
        return {"ok": False, "detail": str(exc)[:200]}
