"""A full pass over the system, in the order a person actually uses it.

Run it after any change. It exercises every endpoint with the model, the
signing service and the mail server stubbed, so it proves the wiring rather
than the third parties.
"""
import base64
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("PROPOSAL_DB", tempfile.mktemp(suffix=".db"))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("  %s %-42s %s" % ("ok  " if ok else "FAIL", name, detail[:60]))


def main():
    import renderer.extract as X
    import renderer.agent as AG
    import renderer.signwell as SW
    import renderer.mailer as MAIL
    from PIL import Image, ImageDraw

    data = json.load(open("samples/kestrel.json"))
    data["meta"].update(client_email="chris@example.com",
                        client_contact="Chris Deross",
                        client_company="VFW Post 7420",
                        project_name="VFW App")
    slots = X.screen_slots(data)

    class Blk:
        type = "text"

        def __init__(self, t):
            self.text = t

    class Msg:
        def __init__(self, t):
            self.content = [Blk(t)]
            self.stop_reason = "end_turn"
            self.usage = types.SimpleNamespace(input_tokens=9, output_tokens=9)

    screens_reply = {"screens": [{"id": s["id"], "device": s["device"],
                                  "blocks": [{"type": "header", "title": "S"}]}
                                 for s in slots]}
    X._client = lambda c=None: types.SimpleNamespace(
        messages=types.SimpleNamespace(
            create=lambda **k: Msg(json.dumps(screens_reply))))
    AG._client = lambda c=None: types.SimpleNamespace(
        messages=types.SimpleNamespace(create=lambda **k: Msg(json.dumps(
            {"ops": [{"op": "set", "path": "page4.one_liner",
                      "value": "Short and sharp."}],
             "note": "Tightened it.", "answer": ""}))))

    mails = []
    SW.configured = lambda: True
    SW.send = lambda pdf, fn, n, e, s, m, send_email=True, sender_name="", \
        reply_to="": {"id": "doc_1", "status": "sent",
                      "link": "https://www.signwell.com/s/x", "name": fn}
    SW.status = lambda d: {"id": d, "status": "completed", "link": ""}
    SW.audit_trail = lambda d: [
        {"who": "chris@example.com", "what": "sent", "at": "2026-09-01 10:00"},
        {"who": "chris@example.com", "what": "viewed", "at": "2026-09-01 10:30"},
        {"who": "chris@example.com", "what": "signed", "at": "2026-09-01 10:40"}]
    SW.signed_pdf = lambda d: b"%PDF-1.4 signed"
    SW.remind = lambda d: (mails.append("reminder"), {"ok": True})[1]

    from fastapi.testclient import TestClient
    from api.index import app
    c = TestClient(app, raise_server_exceptions=False)

    print("\naccounts")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = c.post("/api/auth/signup",
                   json={"email": "a@inceptivesdigital.com",
                         "password": "longenough12", "name": "Ali"})
    check("sign up", r.status_code == 200)
    code = re.search(r": (\d{6})", buf.getvalue())
    check("verification code issued", bool(code))
    r = c.post("/api/auth/verify", json={"email": "a@inceptivesdigital.com",
                                         "code": code.group(1)})
    check("verify and sign in", r.status_code == 200,
          "role %s" % r.json().get("user", {}).get("role"))
    check("outside domain refused",
          c.post("/api/auth/signup", json={"email": "x@gmail.com",
                                           "password": "longenough12"}
                 ).status_code == 400)
    check("password reset starts",
          c.post("/api/auth/reset",
                 json={"email": "a@inceptivesdigital.com"}).status_code == 200)

    print("\nproposals")
    r = c.post("/api/proposals", json={"data": data})
    check("create", r.status_code == 200)
    pid = r.json()["id"]
    check("list", len(c.get("/api/proposals").json()["proposals"]) == 1)
    check("outline",
          len(c.post("/api/outline", json={"data": data}).json()["pages"]) == 15)
    check("preview a page",
          c.post("/api/preview", json={"data": data, "page": 3, "scale": 0.6,
                                       "proposal_id": pid}).status_code == 200)
    check("save a version",
          c.post("/api/proposals/%s/save" % pid,
                 json={"data": data, "note": "t"}).json()["version"] == 2)
    check("change log",
          len(c.get("/api/proposals/%s/log" % pid).json()["log"]) >= 2)
    check("undo", c.post("/api/proposals/%s/undo" % pid,
                         json={}).status_code == 200)
    check("duplicate",
          c.post("/api/proposals/%s/duplicate" % pid,
                 json={"name": "copy"}).status_code == 200)

    print("\ncontent")
    check("qa review",
          "items" in c.post("/api/qa-review", json={"data": data}).json())
    r = c.post("/api/chat", json={"data": data, "instruction": "tighten page 4",
                                  "proposal_id": pid})
    check("assistant", r.status_code == 200 and r.json()["applied"] == 1)
    check("currencies",
          len(c.get("/api/currencies").json()["currencies"]) == 10)
    check("read a document",
          c.post("/api/read-document",
                 json={"filename": "n.txt",
                       "data": "data:text/plain;base64," +
                               base64.b64encode(b"Call notes.").decode()}
                 ).json()["characters"] == 11)

    print("\nscreens")
    job = c.post("/api/screens/start",
                 json={"data": data, "proposal_id": pid,
                       "engine": "builtin"}).json()
    check("job starts", bool(job.get("job_id")), job.get("note", ""))
    steps = 0
    while steps < 12:
        out = c.post("/api/screens/step",
                     json={"data": data, "job_id": job["job_id"],
                           "proposal_id": pid}).json()
        steps += 1
        if out.get("finished"):
            break
    check("job finishes", out.get("finished") and len(out["done"]) == len(slots),
          "%d step(s)" % steps)
    check("screens stored",
          len(c.get("/api/screens/state/%s" % pid).json()["have"]) == len(slots))
    again = c.post("/api/screens/start", json={"data": data, "proposal_id": pid,
                                               "engine": "builtin"}).json()
    check("no rebuild when present", not again.get("job_id"),
          again.get("note", "")[:40])
    check("image served",
          c.get("/api/screens/img/%s/%s" % (pid, slots[0]["id"])
                ).status_code == 200)

    print("\nsigning")
    im = Image.new("RGBA", (400, 140), (0, 0, 0, 0))
    ImageDraw.Draw(im).line([(20, 110), (120, 30), (220, 110), (340, 40)],
                            fill=(20, 24, 32, 255), width=6)
    b = io.BytesIO()
    im.save(b, format="PNG")
    check("save a signature",
          c.post("/api/signature",
                 json={"kind": "drawn", "role": "Account Strategist",
                       "data": "data:image/png;base64," +
                               base64.b64encode(b.getvalue()).decode()}
                 ).status_code == 200)
    r = c.post("/api/contracts/sign", json={"proposal_id": pid, "data": data})
    check("sign in the studio", r.status_code == 200)
    cid = r.json()["contract_id"]
    MAIL.configured = lambda: True
    MAIL.send_contract = lambda to, name, subj, body, link: (
        mails.append("our email"), {"sent": True})[1]
    r = c.post("/api/contracts/send", json={"contract_id": cid, "via": "both"})
    check("send by both routes",
          r.status_code == 200 and "our email" in mails)
    check("signing link", bool(r.json()["link"]))
    c.post("/api/contracts/%s/refresh" % cid)
    row = c.get("/api/contracts/%s" % cid).json()["contract"]
    check("client signs", row["state"] == "completed")
    check("audit trail", len(row["trail"]) == 3,
          ", ".join(e["what"] for e in row["trail"]))
    check("money recorded",
          row["total"] == 14000 and row["initial"] == 2000,
          "%s total, %s first" % (row["total"], row["initial"]))
    check("signed pdf",
          c.get("/api/contracts/%s/signed.pdf" % cid).status_code == 200)
    check("webhook accepted",
          c.post("/api/webhooks/signwell",
                 json={"data": {"object": {"id": "doc_1"}}}).status_code == 200)
    mine = c.get("/api/contracts?mine=1").json()
    check("my documents table", mine["totals"]["completed"] == 1)

    print("\noutput")
    r = c.post("/api/render", json={"data": data, "proposal_id": pid})
    check("render the pdf", r.status_code == 200 and len(r.json()["pdf"]) > 1000)
    check("publish",
          c.post("/api/proposals/%s/publish" % pid, json={}).status_code == 200)

    print("\nadmin")
    adm = c.get("/api/admin/overview")
    check("overview", adm.status_code == 200)
    j = adm.json()
    check("no broken panels",
          not [k for k, v in j.items() if isinstance(v, dict) and v.get("error")])
    check("contracts in admin", len(j.get("contracts", [])) == 1)
    check("costs recorded", (j.get("totals") or {}).get("calls", 0) > 0,
          "$%.4f" % (j.get("totals", {}).get("cost") or 0))
    check("activity recorded", len(j.get("activity", [])) > 3)
    check("admin page serves", c.get("/admin").status_code == 200)

    print("\nplatform")
    h = c.get("/api/health").json()
    check("editor serves", c.get("/").status_code == 200)
    check("all files present", not h["files"]["missing"],
          ", ".join(h["files"]["missing"]))
    check("all dependencies loaded",
          all(v == "ok" for v in h["dependencies"].values()))
    check("database reachable", h["database_reachable"], h["database"])
    check("security headers",
          c.get("/").headers.get("content-security-policy", "").startswith(
              "default-src"))

    print("\n%d passed, %d failed" % (len(PASS), len(FAIL)))
    if FAIL:
        print("failing: " + ", ".join(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
