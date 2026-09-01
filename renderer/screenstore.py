"""Where the UI screens live.

They used to travel in every preview and render request, which is how a request
grew past the platform's 4.5 MB limit and started returning 413. Now each one is
uploaded once, kept against its proposal, and referred to by name.
"""
import base64
import hashlib
import os
import time

from .sql import connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS screen_jobs (
  proposal_id TEXT NOT NULL, slot TEXT NOT NULL, started INTEGER,
  engine TEXT, PRIMARY KEY (proposal_id, slot));
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


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------
# A build takes minutes, and an impatient second click would start the same
# work again and pay for it twice. Each slot is claimed before work starts and
# released when it finishes.

STALE_SECONDS = int(os.environ.get("SCREEN_JOB_STALE", "1800"))


def claim(proposal_id, slots, engine=""):
    """Take the slots nobody else is working on. Returns (mine, busy)."""
    if not proposal_id:
        return list(slots), []
    now_s = int(time.time())
    mine, busy = [], []
    with _conn() as c:
        c.execute("DELETE FROM screen_jobs WHERE started < ?",
                  (now_s - STALE_SECONDS,))
        held = {r["slot"] for r in
                c.execute("SELECT slot FROM screen_jobs WHERE proposal_id=?",
                          (proposal_id,)).fetchall()}
        seen = set()
        for slot in slots:
            sid = slot["id"] if isinstance(slot, dict) else slot
            if sid in seen:
                continue          # a slot can appear twice in one proposal
            seen.add(sid)
            if sid in held:
                busy.append(sid)
                continue
            try:
                c.execute("INSERT INTO screen_jobs (proposal_id,slot,started,"
                          "engine) VALUES (?,?,?,?)",
                          (proposal_id, sid, now_s, engine))
            except Exception:                                 # noqa: BLE001
                busy.append(sid)          # someone else claimed it first
                continue
            mine.append(slot)
    return mine, busy


def release(proposal_id, slots):
    if not proposal_id:
        return
    with _conn() as c:
        for slot in slots:
            sid = slot["id"] if isinstance(slot, dict) else slot
            c.execute("DELETE FROM screen_jobs WHERE proposal_id=? AND slot=?",
                      (proposal_id, sid))


def running(proposal_id):
    """Slots currently being built, with how long they have been going."""
    if not proposal_id:
        return []
    now_s = int(time.time())
    with _conn() as c:
        rows = c.execute("SELECT slot, started, engine FROM screen_jobs "
                         "WHERE proposal_id=?", (proposal_id,)).fetchall()
    return [{"slot": r["slot"], "engine": r["engine"],
             "seconds": now_s - (r["started"] or now_s)} for r in rows]


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------
# Building a set of screens takes minutes, and a single request cannot. A job
# records what is wanted; each step does one small piece and returns. Nothing
# runs long enough to be cut off, and a job survives a reload.

import json as _json
import secrets as _secrets

JOB_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY, proposal_id TEXT, engine TEXT, pending TEXT, done TEXT,
  errors TEXT, chat_id TEXT, state TEXT, started INTEGER, updated INTEGER);
"""
_JOBS_READY = [False]


def _jobs():
    c = _conn()
    if not _JOBS_READY[0]:
        c.executescript(JOB_SCHEMA)
        c.commit()
        _JOBS_READY[0] = True
    return c


def start_job(proposal_id, engine, slot_ids):
    job_id = _secrets.token_hex(8)
    now_s = int(time.time())
    with _jobs() as c:
        c.execute("INSERT INTO jobs (id,proposal_id,engine,pending,done,errors,"
                  "chat_id,state,started,updated) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (job_id, proposal_id, engine, _json.dumps(list(slot_ids)),
                   "[]", "[]", "", "running", now_s, now_s))
    return job_id


def get_job(job_id):
    with _jobs() as c:
        row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        return None
    out = dict(row)
    for key in ("pending", "done", "errors"):
        try:
            out[key] = _json.loads(out[key] or "[]")
        except Exception:                                     # noqa: BLE001
            out[key] = []
    return out


def update_job(job_id, pending=None, done=None, errors=None, chat_id=None,
               state=None):
    sets, args = ["updated=?"], [int(time.time())]
    if pending is not None:
        sets.append("pending=?"); args.append(_json.dumps(list(pending)))
    if done is not None:
        sets.append("done=?"); args.append(_json.dumps(list(done)))
    if errors is not None:
        sets.append("errors=?"); args.append(_json.dumps(list(errors)))
    if chat_id is not None:
        sets.append("chat_id=?"); args.append(chat_id)
    if state is not None:
        sets.append("state=?"); args.append(state)
    args.append(job_id)
    with _jobs() as c:
        c.execute("UPDATE jobs SET %s WHERE id=?" % ", ".join(sets), args)


def active_job(proposal_id):
    """A job still running for this proposal, if there is one."""
    with _jobs() as c:
        row = c.execute("SELECT id FROM jobs WHERE proposal_id=? AND "
                        "state='running' ORDER BY started DESC LIMIT 1",
                        (proposal_id,)).fetchone()
    return row["id"] if row else None


def sweep_jobs(max_age=3600):
    with _jobs() as c:
        c.execute("UPDATE jobs SET state='expired' WHERE state='running' "
                  "AND updated < ?", (int(time.time()) - max_age,))
