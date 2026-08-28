"""Where the UI screens live.

They used to travel in every preview and render request, which is how a request
grew past the platform's 4.5 MB limit and started returning 413. Now each one is
uploaded once, kept against its proposal, and referred to by name.
"""
import base64
import hashlib

from .sql import connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS screens (
  proposal_id TEXT NOT NULL, slot TEXT NOT NULL, mime TEXT, bytes INTEGER,
  sha TEXT, data TEXT, at TEXT,
  PRIMARY KEY (proposal_id, slot));
"""

MAX_BYTES = 4 * 1024 * 1024          # one screen; the whole set is never sent
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


def put(proposal_id, slot, data_url):
    """Store one screen. Returns its size, so the caller can report it."""
    head, _, raw = (data_url or "").partition(",")
    mime = "image/png"
    if head.startswith("data:") and ";" in head:
        mime = head[5:head.index(";")] or mime
    blob = base64.b64decode(raw or "")
    if not blob:
        raise ValueError("That screen was empty.")
    if len(blob) > MAX_BYTES:
        raise ValueError("That image is larger than 4 MB.")
    sha = hashlib.sha1(blob).hexdigest()
    with _conn() as c:
        c.execute("DELETE FROM screens WHERE proposal_id=? AND slot=?",
                  (proposal_id, slot))
        c.execute("INSERT INTO screens (proposal_id,slot,mime,bytes,sha,data,at)"
                  " VALUES (?,?,?,?,?,?,?)",
                  (proposal_id, slot, mime, len(blob), sha,
                   base64.b64encode(blob).decode(), _now()))
    return {"slot": slot, "bytes": len(blob), "sha": sha}


def get(proposal_id, slot):
    with _conn() as c:
        row = c.execute("SELECT mime, data FROM screens WHERE proposal_id=? "
                        "AND slot=?", (proposal_id, slot)).fetchone()
    if not row:
        return None
    return row["mime"], base64.b64decode(row["data"])


def listing(proposal_id):
    with _conn() as c:
        rows = c.execute("SELECT slot, bytes, sha, at FROM screens "
                         "WHERE proposal_id=?", (proposal_id,)).fetchall()
    return rows


def slots_present(proposal_id):
    return {r["slot"] for r in listing(proposal_id)}


def delete(proposal_id, slot=None):
    with _conn() as c:
        if slot:
            c.execute("DELETE FROM screens WHERE proposal_id=? AND slot=?",
                      (proposal_id, slot))
        else:
            c.execute("DELETE FROM screens WHERE proposal_id=?", (proposal_id,))


def copy_to(from_id, to_id):
    """Duplicating a proposal should bring its screens along."""
    with _conn() as c:
        rows = c.execute("SELECT slot, mime, bytes, sha, data FROM screens "
                         "WHERE proposal_id=?", (from_id,)).fetchall()
        for r in rows:
            c.execute("DELETE FROM screens WHERE proposal_id=? AND slot=?",
                      (to_id, r["slot"]))
            c.execute("INSERT INTO screens (proposal_id,slot,mime,bytes,sha,"
                      "data,at) VALUES (?,?,?,?,?,?,?)",
                      (to_id, r["slot"], r["mime"], r["bytes"], r["sha"],
                       r["data"], _now()))
    return len(rows)


def to_files(proposal_id, folder):
    """Write them to disk for the renderer, which works with file paths."""
    import os
    if not proposal_id:
        return {}
    os.makedirs(folder, exist_ok=True)
    out = {}
    with _conn() as c:
        rows = c.execute("SELECT slot, data, sha FROM screens WHERE "
                         "proposal_id=?", (proposal_id,)).fetchall()
    for r in rows:
        path = os.path.join(folder, "%s_%s.png" % (r["slot"], r["sha"][:8]))
        if not os.path.exists(path):
            with open(path, "wb") as fh:
                fh.write(base64.b64decode(r["data"]))
        out[r["slot"]] = path
    return out
