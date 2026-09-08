"""Every proposal sent for signature, and what happened to it.

One row per contract, carrying who sent it, who it went to, the money, and
every dated step from signing in the studio to the client's signature. This is
what the admin table and each user's own dashboard read from.
"""
import json
import time

from .sql import connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS contracts (
  id TEXT PRIMARY KEY, proposal_id TEXT, version INTEGER, user_id TEXT,
  user_name TEXT, user_email TEXT,
  client_name TEXT, client_company TEXT, client_email TEXT,
  project_name TEXT, currency TEXT, total REAL, initial REAL,
  provider TEXT, document_id TEXT, link TEXT, state TEXT,
  sent_via TEXT, subject TEXT, message TEXT,
  signed_by_user_at TEXT, sent_at TEXT, viewed_at TEXT, completed_at TEXT,
  declined_at TEXT, created_at TEXT, updated_at TEXT,
  trail TEXT, signed_pdf TEXT);
CREATE INDEX IF NOT EXISTS ix_contracts_user ON contracts(user_id, created_at);
CREATE INDEX IF NOT EXISTS ix_contracts_prop ON contracts(proposal_id);
"""

STATES = ("draft", "signed_by_user", "sent", "viewed", "completed", "declined")
_READY = [False]


def _conn():
    c = connect()
    if not _READY[0]:
        c.executescript(SCHEMA)
        c.commit()
        _READY[0] = True
    return c


def _now():
    from .db import now
    return now()


def money_of(data):
    """The total, and the first payable milestone, which is what gets invoiced
    first and is the figure everyone asks about."""
    page = (data or {}).get("page12") or {}
    total = page.get("total_value")
    initial = None
    for row in page.get("rows") or []:
        if isinstance(row.get("amount"), (int, float)):
            initial = row["amount"]
            break
    return total, initial


def create(proposal_id, version, user, data, state="draft"):
    from .model import currency_of
    meta = (data or {}).get("meta") or {}
    total, initial = money_of(data)
    cid = "%s-%d" % (proposal_id[:12], int(time.time()))
    with _conn() as c:
        c.execute("INSERT INTO contracts (id,proposal_id,version,user_id,"
                  "user_name,user_email,client_name,client_company,client_email,"
                  "project_name,currency,total,initial,provider,document_id,"
                  "link,state,sent_via,subject,message,created_at,updated_at,"
                  "trail) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (cid, proposal_id, version, user.get("id"),
                   user.get("name"), user.get("email"),
                   meta.get("client_contact", ""), meta.get("client_company", ""),
                   meta.get("client_email", ""), meta.get("project_name", ""),
                   currency_of(data), total, initial, "", "", "", state, "",
                   "", "", _now(), _now(), "[]"))
    return cid


def update(cid, **fields):
    if not fields:
        return
    fields["updated_at"] = _now()
    if "trail" in fields and not isinstance(fields["trail"], str):
        fields["trail"] = json.dumps(fields["trail"])
    sets = ", ".join("%s=?" % k for k in fields)
    with _conn() as c:
        c.execute("UPDATE contracts SET %s WHERE id=?" % sets,
                  list(fields.values()) + [cid])


def get(cid):
    with _conn() as c:
        row = c.execute("SELECT * FROM contracts WHERE id=?", (cid,)).fetchone()
    return _shape(row) if row else None


def for_proposal(proposal_id):
    with _conn() as c:
        rows = c.execute("SELECT * FROM contracts WHERE proposal_id=? "
                         "ORDER BY created_at DESC", (proposal_id,)).fetchall()
    return [_shape(r) for r in rows]


def listing(user_id=None, limit=300):
    """Everything, or just one person's, newest first."""
    with _conn() as c:
        if user_id:
            rows = c.execute("SELECT * FROM contracts WHERE user_id=? "
                             "ORDER BY created_at DESC LIMIT ?",
                             (user_id, limit)).fetchall()
        else:
            rows = c.execute("SELECT * FROM contracts ORDER BY created_at DESC "
                             "LIMIT ?", (limit,)).fetchall()
    return [_shape(r) for r in rows]


def totals(user_id=None):
    """Headline figures for the dashboard."""
    rows = listing(user_id, 5000)
    out = {"count": len(rows), "value": 0.0, "won": 0.0, "awaiting": 0,
           "completed": 0, "drafts": 0}
    for r in rows:
        out["value"] += r.get("total") or 0
        if r["state"] == "completed":
            out["completed"] += 1
            out["won"] += r.get("total") or 0
        elif r["state"] in ("sent", "viewed", "signed_by_user"):
            out["awaiting"] += 1
        elif r["state"] == "draft":
            out["drafts"] += 1
    return out


def _shape(row):
    out = dict(row)
    try:
        out["trail"] = json.loads(out.get("trail") or "[]")
    except Exception:                                         # noqa: BLE001
        out["trail"] = []
    out.pop("signed_pdf", None)          # never travels with a listing
    return out


def add_event(cid, who, what, at=None, detail=""):
    """Append to the trail, keeping it in order and without duplicates."""
    row = get(cid)
    if not row:
        return
    trail = row["trail"]
    stamp = at or _now()
    if any(e.get("what") == what and e.get("who") == who for e in trail):
        return
    trail.append({"who": who, "what": what, "at": stamp, "detail": detail})
    update(cid, trail=trail)


def store_signed_pdf(cid, blob):
    import base64
    with _conn() as c:
        c.execute("UPDATE contracts SET signed_pdf=?, updated_at=? WHERE id=?",
                  (base64.b64encode(blob).decode(), _now(), cid))


def signed_pdf(cid):
    import base64
    with _conn() as c:
        row = c.execute("SELECT signed_pdf FROM contracts WHERE id=?",
                        (cid,)).fetchone()
    if not row or not row["signed_pdf"]:
        return None
    return base64.b64decode(row["signed_pdf"])


def by_document(document_id):
    with _conn() as c:
        row = c.execute("SELECT * FROM contracts WHERE document_id=?",
                        (document_id,)).fetchone()
    return _shape(row) if row else None
