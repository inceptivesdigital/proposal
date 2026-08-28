"""Accounts and saved proposals, on SQLite locally and Postgres in production.

Everything a user does is a new version, never an overwrite, so a proposal can
be duplicated, compared, and rolled back. The change log records who did what
and which fields moved.
"""
import hashlib
import hmac
import json
import os
import secrets
from .sql import connect, backend
import time



# Only these email domains may hold an account. Everything else is refused at
# signup, so a leaked URL is not a way in.
ALLOWED_DOMAINS = [d.strip().lower() for d in os.environ.get(
    "ALLOWED_EMAIL_DOMAINS", "inceptivesdigital.com").split(",") if d.strip()]
SESSION_DAYS = int(os.environ.get("SESSION_DAYS", "14"))
MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "8"))
OTP_MINUTES = int(os.environ.get("OTP_MINUTES", "10"))
OTP_MAX_TRIES = int(os.environ.get("OTP_MAX_TRIES", "5"))
LOCKOUT_MINUTES = int(os.environ.get("LOGIN_LOCKOUT_MINUTES", "15"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT,
  pw_hash TEXT NOT NULL, salt TEXT NOT NULL, created TEXT,
  role TEXT DEFAULT 'member', disabled INTEGER DEFAULT 0, last_seen TEXT);
CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY, user_id TEXT NOT NULL, created TEXT, expires TEXT);
CREATE TABLE IF NOT EXISTS login_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, at INTEGER, ok INTEGER);
CREATE TABLE IF NOT EXISTS pending (
  email TEXT PRIMARY KEY, name TEXT, pw_hash TEXT, salt TEXT,
  code_hash TEXT, expires INTEGER, tries INTEGER DEFAULT 0, sent_at INTEGER);
CREATE TABLE IF NOT EXISTS resets (
  email TEXT PRIMARY KEY, code_hash TEXT, salt TEXT, expires INTEGER,
  tries INTEGER DEFAULT 0, sent_at INTEGER);
CREATE TABLE IF NOT EXISTS activity (
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, user_id TEXT, email TEXT,
  action TEXT, detail TEXT, proposal_id TEXT);
CREATE INDEX IF NOT EXISTS ix_activity ON activity(id);
CREATE TABLE IF NOT EXISTS proposals (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT, status TEXT,
  created TEXT, updated TEXT, screens TEXT, copied_from TEXT);
CREATE TABLE IF NOT EXISTS versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, proposal_id TEXT NOT NULL,
  n INTEGER NOT NULL, at TEXT, author TEXT, note TEXT, data TEXT);
CREATE TABLE IF NOT EXISTS changes (
  id INTEGER PRIMARY KEY AUTOINCREMENT, proposal_id TEXT NOT NULL,
  version INTEGER, at TEXT, author TEXT, action TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS shares (
  token TEXT PRIMARY KEY, proposal_id TEXT NOT NULL, version INTEGER,
  follow_latest INTEGER, at TEXT);
CREATE INDEX IF NOT EXISTS ix_versions ON versions(proposal_id, n);
CREATE INDEX IF NOT EXISTS ix_changes ON changes(proposal_id, id);
CREATE INDEX IF NOT EXISTS ix_proposals ON proposals(user_id, updated);
"""


def now():
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime())


# columns added after the first release; existing databases are upgraded in place
MIGRATIONS = [
    ("users", "role", "TEXT DEFAULT 'member'"),
    ("users", "disabled", "INTEGER DEFAULT 0"),
    ("users", "last_seen", "TEXT"),
    ("sessions", "expires", "TEXT"),
    ("proposals", "screens", "TEXT"),
    ("proposals", "copied_from", "TEXT"),
]


def _migrate(c):
    for table, column, spec in MIGRATIONS:
        try:
            have = c.columns(table)
        except Exception:                                     # noqa: BLE001
            continue
        if have and column not in have:
            try:
                c.execute("ALTER TABLE %s ADD COLUMN %s %s"
                          % (table, column, spec))
            except Exception:                             # noqa: BLE001
                pass
    # the very first account on an upgraded database becomes the administrator
    try:
        row = c.execute("SELECT COUNT(*) AS n FROM users WHERE role='admin'").fetchone()
        if row and not row["n"]:
            first = c.execute("SELECT id FROM users ORDER BY created LIMIT 1").fetchone()
            if first:
                c.execute("UPDATE users SET role='admin' WHERE id=?", (first["id"],))
    except Exception:                                         # noqa: BLE001
        pass


_READY = [False]


def conn():
    c = connect()
    if not _READY[0]:
        c.executescript(SCHEMA)
        _migrate(c)
        c.commit()
        _READY[0] = True
    return c


def _hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(),
                               240_000).hex()


def domain_of(email):
    return (email or "").strip().lower().rsplit("@", 1)[-1]


def domain_allowed(email):
    return not ALLOWED_DOMAINS or domain_of(email) in ALLOWED_DOMAINS


def _expiry():
    return time.strftime("%Y-%m-%d %H:%M",
                         time.gmtime(time.time() + SESSION_DAYS * 86400))


def _note_attempt(email, ok):
    """Recorded on its own connection: the failure is raised as an exception,
    which would otherwise roll the record back."""
    with conn() as c:
        c.executescript(SCHEMA)
        c.execute("INSERT INTO login_attempts (email,at,ok) VALUES (?,?,?)",
                  (email, int(time.time()), 1 if ok else 0))


def _locked_out(c, email):
    """Too many recent failures on this address, so stop guessing."""
    cutoff = int(time.time()) - LOCKOUT_MINUTES * 60
    n = c.execute("SELECT COUNT(*) AS n FROM login_attempts WHERE email=? "
                  "AND ok=0 AND at > ?", (email, cutoff)).fetchone()["n"]
    return n >= MAX_ATTEMPTS


# --------------------------------------------------------------------- users
def start_signup(email, password, name=""):
    """Step one: check the rules, hold the details, and issue a code."""
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("A valid work email is required.")
    if len(password or "") < 10:
        raise ValueError("Use a password of at least 10 characters.")
    if not domain_allowed(email):
        raise ValueError("Accounts are limited to %s addresses."
                         % " or ".join("@" + d for d in ALLOWED_DOMAINS))
    with conn() as c:
        if c.execute("SELECT 1 AS x FROM users WHERE email=?", (email,)).fetchone():
            raise ValueError("That email already has an account. Sign in instead.")
        row = c.execute("SELECT sent_at FROM pending WHERE email=?",
                        (email,)).fetchone()
        if row and row["sent_at"] and int(time.time()) - row["sent_at"] < 45:
            raise ValueError("A code was just sent. Check your inbox, or wait "
                             "a moment before asking for another.")
        salt = secrets.token_hex(16)
        code = "%06d" % secrets.randbelow(1000000)
        c.execute("DELETE FROM pending WHERE email=?", (email,))
        c.execute("INSERT INTO pending (email,name,pw_hash,salt,code_hash,"
                  "expires,tries,sent_at) VALUES (?,?,?,?,?,?,0,?)",
                  (email, name or email.split("@")[0], _hash(password, salt),
                   salt, _hash(code, salt),
                   int(time.time()) + OTP_MINUTES * 60, int(time.time())))
    return code


def start_reset(email):
    """Issue a reset code. The reply is the same whether or not the account
    exists, so this cannot be used to discover who has one."""
    email = (email or "").strip().lower()
    with conn() as c:
        row = c.execute("SELECT id FROM users WHERE email=? AND disabled=0",
                        (email,)).fetchone()
        if not row:
            return None
        prev = c.execute("SELECT sent_at FROM resets WHERE email=?",
                         (email,)).fetchone()
        if prev and prev["sent_at"] and int(time.time()) - prev["sent_at"] < 45:
            raise ValueError("A code was just sent. Check your inbox, or wait "
                             "a moment before asking for another.")
        salt = secrets.token_hex(16)
        code = "%06d" % secrets.randbelow(1000000)
        c.execute("DELETE FROM resets WHERE email=?", (email,))
        c.execute("INSERT INTO resets (email,code_hash,salt,expires,tries,"
                  "sent_at) VALUES (?,?,?,?,0,?)",
                  (email, _hash(code, salt), salt,
                   int(time.time()) + OTP_MINUTES * 60, int(time.time())))
    note_activity(row["id"], email, "asked to reset their password")
    return code


def finish_reset(email, code, new_password):
    """Check the code, set the new password, and end every existing session."""
    email = (email or "").strip().lower()
    if len(new_password or "") < 10:
        raise ValueError("Use a password of at least 10 characters.")
    with conn() as c:
        row = c.execute("SELECT * FROM resets WHERE email=?", (email,)).fetchone()
        if not row:
            raise ValueError("No reset is waiting for that address. Start again.")
        if row["expires"] < int(time.time()):
            c.execute("DELETE FROM resets WHERE email=?", (email,))
            raise ValueError("That code has expired. Ask for a new one.")
        if row["tries"] >= OTP_MAX_TRIES:
            c.execute("DELETE FROM resets WHERE email=?", (email,))
            raise ValueError("Too many wrong codes. Start the reset again.")
        if not hmac.compare_digest(_hash(code or "", row["salt"]),
                                   row["code_hash"]):
            c.execute("UPDATE resets SET tries = tries + 1 WHERE email=?",
                      (email,))
            raise ValueError("That code is not right.")
        user = c.execute("SELECT id, name, role FROM users WHERE email=?",
                         (email,)).fetchone()
        salt = secrets.token_hex(16)
        c.execute("UPDATE users SET pw_hash=?, salt=? WHERE email=?",
                  (_hash(new_password, salt), salt, email))
        c.execute("DELETE FROM resets WHERE email=?", (email,))
        # anyone holding an old session is signed out, which is the point
        c.execute("DELETE FROM sessions WHERE user_id=?", (user["id"],))
        c.execute("DELETE FROM login_attempts WHERE email=?", (email,))
    note_activity(user["id"], email, "reset their password",
                  "all sessions ended")
    return _issue(user["id"], email, user["name"], user["role"])


def clear_reset(email):
    with conn() as c:
        c.execute("DELETE FROM resets WHERE email=?",
                  ((email or "").strip().lower(),))


def clear_pending(email):
    """Drop a half-finished sign-up so the person can try again at once."""
    with conn() as c:
        c.execute("DELETE FROM pending WHERE email=?",
                  ((email or "").strip().lower(),))


def verify_signup(email, code):
    """Step two: the code proves they hold the address, so create the account."""
    email = (email or "").strip().lower()
    with conn() as c:
        row = c.execute("SELECT * FROM pending WHERE email=?", (email,)).fetchone()
        if not row:
            raise ValueError("No sign-up is waiting for that address. Start again.")
        if row["expires"] < int(time.time()):
            c.execute("DELETE FROM pending WHERE email=?", (email,))
            raise ValueError("That code has expired. Ask for a new one.")
        if row["tries"] >= OTP_MAX_TRIES:
            c.execute("DELETE FROM pending WHERE email=?", (email,))
            raise ValueError("Too many wrong codes. Start the sign-up again.")
        if not hmac.compare_digest(_hash(code or "", row["salt"]),
                                   row["code_hash"]):
            c.execute("UPDATE pending SET tries = tries + 1 WHERE email=?",
                      (email,))
            raise ValueError("That code is not right.")
        first = c.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"] == 0
        uid = secrets.token_hex(8)
        c.execute("INSERT INTO users (id,email,name,pw_hash,salt,created,role) "
                  "VALUES (?,?,?,?,?,?,?)",
                  (uid, email, row["name"], row["pw_hash"], row["salt"], now(),
                   "admin" if first else "member"))
        c.execute("DELETE FROM pending WHERE email=?", (email,))
    note_activity(uid, email, "signed up",
                  "first account, made administrator" if first else "")
    return _issue(uid, email, row["name"], "admin" if first else "member")


def _issue(uid, email, name, role):
    with conn() as c:
        token = secrets.token_hex(32)
        c.execute("INSERT INTO sessions (token,user_id,created,expires) "
                  "VALUES (?,?,?,?)", (token, uid, now(), _expiry()))
    return {"token": token,
            "user": {"id": uid, "email": email, "name": name, "role": role}}


def note_activity(user_id, email, action, detail="", proposal_id=""):
    """A plain record of who did what, for the admin view."""
    try:
        with conn() as c:
            c.execute("INSERT INTO activity (at,user_id,email,action,detail,"
                      "proposal_id) VALUES (?,?,?,?,?,?)",
                      (now(), user_id, email, action, str(detail)[:300],
                       proposal_id))
    except Exception:                                         # noqa: BLE001
        pass


def activity(limit=200):
    with conn() as c:
        rows = c.execute("SELECT at, email, action, detail, proposal_id FROM "
                         "activity ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return rows


def activity_summary():
    with conn() as c:
        rows = c.execute(
            "SELECT email, COUNT(*) AS actions, MAX(at) AS last_at "
            "FROM activity GROUP BY email ORDER BY actions DESC").fetchall()
    return rows


def signup(email, password, name=""):
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("A valid work email is required.")
    if len(password or "") < 10:
        raise ValueError("Use a password of at least 10 characters.")
    if not domain_allowed(email):
        raise ValueError("Accounts are limited to %s addresses."
                         % " or ".join("@" + d for d in ALLOWED_DOMAINS))
    with conn() as c:
        if c.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            raise ValueError("That email already has an account.")
        salt = secrets.token_hex(16)
        uid = secrets.token_hex(8)
        first = c.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"] == 0
        c.execute("INSERT INTO users (id,email,name,pw_hash,salt,created,role) "
                  "VALUES (?,?,?,?,?,?,?)",
                  (uid, email, name or email.split("@")[0],
                   _hash(password, salt), salt, now(),
                   "admin" if first else "member"))
    return login(email, password)


def login(email, password):
    email = (email or "").strip().lower()
    with conn() as c:
        if _locked_out(c, email):
            raise ValueError("Too many failed attempts. Try again in %d minutes."
                             % LOCKOUT_MINUTES)
        row = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        # hash even when the account does not exist, so timing gives nothing away
        salt = row["salt"] if row else "absent"
        digest = _hash(password or "", salt)
        ok = bool(row) and not row["disabled"] and hmac.compare_digest(
            digest, row["pw_hash"])
    _note_attempt(email, ok)
    if not ok:
        # one message for every failure, so nothing is revealed
        raise ValueError("Email or password is wrong.")
    with conn() as c:
        token = secrets.token_hex(32)
        c.execute("INSERT INTO sessions (token,user_id,created,expires) "
                  "VALUES (?,?,?,?)", (token, row["id"], now(), _expiry()))
        c.execute("UPDATE users SET last_seen=? WHERE id=?", (now(), row["id"]))
    note_activity(row["id"], row["email"], "signed in")
    return {"token": token, "user": {"id": row["id"], "email": row["email"],
                                     "name": row["name"], "role": row["role"]}}


def logout(token):
    with conn() as c:
        c.execute("DELETE FROM sessions WHERE token=?", (token,))


def user_for(token):
    if not token or len(token) < 24:
        return None
    with conn() as c:
        row = c.execute(
            "SELECT u.id, u.email, u.name, u.role, u.disabled, s.expires "
            "FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token=?", (token,)).fetchone()
        if not row or row["disabled"]:
            return None
        if row["expires"] and row["expires"] < now():
            c.execute("DELETE FROM sessions WHERE token=?", (token,))
            return None
        c.execute("UPDATE users SET last_seen=? WHERE id=?", (now(), row["id"]))
    out = dict(row)
    out.pop("expires", None)
    out.pop("disabled", None)
    return out


def is_admin(user):
    return bool(user) and user.get("role") == "admin"


def users():
    with conn() as c:
        rows = c.execute("SELECT id, email, name, role, created, last_seen, "
                         "disabled FROM users ORDER BY created").fetchall()
    return [dict(r) for r in rows]


def set_role(user_id, role):
    with conn() as c:
        c.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))


def set_disabled(user_id, disabled=True):
    with conn() as c:
        c.execute("UPDATE users SET disabled=? WHERE id=?",
                  (1 if disabled else 0, user_id))
        if disabled:
            c.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))


# ----------------------------------------------------------------- proposals
def create(user_id, name, data, author="", note="Created"):
    pid = secrets.token_hex(8)
    with conn() as c:
        c.execute("INSERT INTO proposals VALUES (?,?,?,?,?,?,?,?)",
                  (pid, user_id, name or "Untitled proposal", "draft",
                   now(), now(), "{}", None))
        c.execute("INSERT INTO versions (proposal_id,n,at,author,note,data) "
                  "VALUES (?,?,?,?,?,?)",
                  (pid, 1, now(), author, note, json.dumps(data)))
        _log(c, pid, 1, author, "created", name or "Untitled proposal")
    note_activity(user_id, "", "created a proposal", name, pid)
    return pid


def listing(user_id):
    with conn() as c:
        rows = c.execute(
            "SELECT p.*, (SELECT MAX(n) FROM versions v WHERE v.proposal_id=p.id)"
            " AS versions FROM proposals p WHERE user_id=? ORDER BY updated DESC",
            (user_id,)).fetchall()
    return [dict(r) for r in rows]


def load(pid, user_id=None):
    with conn() as c:
        p = c.execute("SELECT * FROM proposals WHERE id=?", (pid,)).fetchone()
        if not p or (user_id and p["user_id"] != user_id):
            raise KeyError("No such proposal.")
        v = c.execute("SELECT * FROM versions WHERE proposal_id=? "
                      "ORDER BY n DESC LIMIT 1", (pid,)).fetchone()
    return {"proposal": dict(p), "version": v["n"],
            "data": json.loads(v["data"]),
            "screens": json.loads(p["screens"] or "{}")}


def save(pid, user_id, data, author="", note="Edited", screens=None):
    with conn() as c:
        p = c.execute("SELECT * FROM proposals WHERE id=?", (pid,)).fetchone()
        if not p or p["user_id"] != user_id:
            raise KeyError("No such proposal.")
        prev = c.execute("SELECT data, n FROM versions WHERE proposal_id=? "
                         "ORDER BY n DESC LIMIT 1", (pid,)).fetchone()
        n = (prev["n"] if prev else 0) + 1
        c.execute("INSERT INTO versions (proposal_id,n,at,author,note,data) "
                  "VALUES (?,?,?,?,?,?)", (pid, n, now(), author, note,
                                           json.dumps(data)))
        fields = changed_paths(json.loads(prev["data"]), data) if prev else []
        _log(c, pid, n, author, "edited", note +
             (" (%s)" % ", ".join(fields[:6]) if fields else ""))
        c.execute("UPDATE proposals SET updated=?, name=?%s WHERE id=?" %
                  (", screens=?" if screens is not None else ""),
                  ((now(), data.get("meta", {}).get("project_name") or p["name"])
                   + ((json.dumps(screens),) if screens is not None else ())
                   + (pid,)))
    return n


def duplicate(pid, user_id, new_name=None, author=""):
    src = load(pid, user_id)
    name = new_name or (src["proposal"]["name"] + " (copy)")
    nid = create(user_id, name, src["data"], author, "Duplicated")
    with conn() as c:
        c.execute("UPDATE proposals SET copied_from=?, screens=? WHERE id=?",
                  (pid, json.dumps(src["screens"]), nid))
        _log(c, nid, 1, author, "duplicated",
             "copied from %s" % src["proposal"]["name"])
    note_activity(user_id, "", "duplicated a proposal",
                  src["proposal"]["name"], nid)
    return nid


def versions(pid, user_id=None):
    with conn() as c:
        p = c.execute("SELECT user_id FROM proposals WHERE id=?", (pid,)).fetchone()
        if not p or (user_id and p["user_id"] != user_id):
            raise KeyError("No such proposal.")
        rows = c.execute("SELECT n, at, author, note FROM versions "
                         "WHERE proposal_id=? ORDER BY n DESC", (pid,)).fetchall()
    return [dict(r) for r in rows]


def restore(pid, user_id, n, author=""):
    with conn() as c:
        row = c.execute("SELECT data FROM versions WHERE proposal_id=? AND n=?",
                        (pid, n)).fetchone()
        if not row:
            raise KeyError("No such version.")
    return save(pid, user_id, json.loads(row["data"]), author,
                "Restored version %d" % n)


def undo(pid, user_id, author=""):
    """Step back one version by writing the previous state as a new version."""
    vs = versions(pid, user_id)
    if len(vs) < 2:
        raise ValueError("Nothing to undo.")
    return restore(pid, user_id, vs[1]["n"], author)


def log(pid, user_id=None, limit=200):
    with conn() as c:
        p = c.execute("SELECT user_id FROM proposals WHERE id=?", (pid,)).fetchone()
        if not p or (user_id and p["user_id"] != user_id):
            raise KeyError("No such proposal.")
        rows = c.execute("SELECT version, at, author, action, detail FROM changes "
                         "WHERE proposal_id=? ORDER BY id DESC LIMIT ?",
                         (pid, limit)).fetchall()
    return [dict(r) for r in rows]


def delete(pid, user_id):
    with conn() as c:
        p = c.execute("SELECT user_id FROM proposals WHERE id=?", (pid,)).fetchone()
        if not p or p["user_id"] != user_id:
            raise KeyError("No such proposal.")
        for table in ("versions", "changes"):
            c.execute("DELETE FROM %s WHERE proposal_id=?" % table, (pid,))
        c.execute("DELETE FROM shares WHERE proposal_id=?", (pid,))
        c.execute("DELETE FROM proposals WHERE id=?", (pid,))


def publish(pid, user_id, author=""):
    with conn() as c:
        p = c.execute("SELECT * FROM proposals WHERE id=?", (pid,)).fetchone()
        if not p or p["user_id"] != user_id:
            raise KeyError("No such proposal.")
        v = c.execute("SELECT MAX(n) AS n FROM versions WHERE proposal_id=?",
                      (pid,)).fetchone()["n"] or 1
        token = secrets.token_hex(10)
        c.execute("INSERT INTO shares VALUES (?,?,?,?,?)",
                  (token, pid, v, 0, now()))
        c.execute("UPDATE proposals SET status='sent' WHERE id=?", (pid,))
        _log(c, pid, v, author, "published", "link pinned to v%d" % v)
    note_activity(user_id, "", "published a proposal", p["name"], pid)
    return {"token": token, "version": v}


def _log(c, pid, n, author, action, detail):
    c.execute("INSERT INTO changes (proposal_id,version,at,author,action,detail) "
              "VALUES (?,?,?,?,?,?)", (pid, n, now(), author, action, detail))


def changed_paths(a, b, prefix="", out=None):
    """Which JSON paths differ. Drives the change log detail."""
    if out is None:
        out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if str(k).startswith("_"):
                continue
            p = "%s.%s" % (prefix, k) if prefix else str(k)
            if k not in a or k not in b:
                out.append(p)
            else:
                changed_paths(a[k], b[k], p, out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(prefix or ".")
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                changed_paths(x, y, "%s.%d" % (prefix, i), out)
    elif a != b:
        out.append(prefix or ".")
    return out
