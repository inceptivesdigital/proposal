"""What this team keeps asking for.

Every instruction given to the assistant is recorded. When the same request
turns up on several proposals it becomes a house preference: the assistant is
told about it, and the editor offers to apply it to a new proposal rather than
waiting to be asked a fourth time.
"""
import json
import re

from .db import conn, now

SCHEMA = """
CREATE TABLE IF NOT EXISTS instructions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,
  proposal_id TEXT, at TEXT, text TEXT, norm TEXT, applied INTEGER);
CREATE TABLE IF NOT EXISTS preferences (
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, norm TEXT,
  text TEXT, seen INTEGER, last_at TEXT, muted INTEGER DEFAULT 0,
  UNIQUE(user_id, norm));
CREATE TABLE IF NOT EXISTS corrections (
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, proposal_id TEXT,
  at TEXT, path TEXT, field TEXT, instruction TEXT, before TEXT, after TEXT);
CREATE TABLE IF NOT EXISTS rules (
  id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT, norm TEXT UNIQUE,
  text TEXT, field TEXT, seen INTEGER, last_at TEXT, muted INTEGER DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_instr ON instructions(user_id, id);
CREATE INDEX IF NOT EXISTS ix_corr ON corrections(path, id);
"""

# a correction seen on this many different proposals becomes a standing rule
RULE_THRESHOLD = 2

# how many proposals must carry the same request before it becomes a preference
THRESHOLD = 3

STOP = {"the", "a", "an", "on", "in", "to", "of", "and", "for", "this", "that",
        "please", "can", "you", "it", "is", "are", "i", "we", "my", "our",
        "page", "proposal", "make", "do", "put", "set", "change"}


def _init(c):
    c.executescript(SCHEMA)


# The same request arrives worded a dozen ways, so match on intent first and
# fall back to a word fingerprint only for things not on this list.
INTENTS = [
    ("remove-ui-screens",
     ("screen", "mockup", "mock-up", "ui"), ("delete", "remove", "drop", "no", "without")),
    ("remove-marketing-page", ("marketing",), ("delete", "remove", "drop", "hide")),
    ("clean-page4-background",
     ("background", "phone", "mockup"), ("clean", "remove", "delete", "blur")),
    ("open-up-spacing",
     ("spacing", "gap", "cramped", "closer", "tight", "breathing"),
     ("more", "add", "open", "increase", "loose")),
    ("shorten-copy",
     ("shorter", "shorten", "trim", "concise", "brief", "cut"), ()),
    ("sharper-differentiator", ("differentiator", "punchier", "sharper"), ()),
    ("add-security-page", ("security", "compliance"), ("add", "new", "create")),
]


def normalise(text):
    """A fingerprint that groups differently-worded versions of one request."""
    low = (text or "").lower()
    words = set(re.findall(r"[a-z]+", low))
    for name, subject, verbs in INTENTS:
        if any(s in low for s in subject) and (not verbs or words & set(verbs)):
            return name
    keep = [w for w in sorted(words) if w not in STOP and len(w) > 2]
    return " ".join(keep[:8])


def record(user_id, proposal_id, text, applied=True):
    """Log an instruction and promote it once it recurs across proposals."""
    norm = normalise(text)
    if not norm:
        return None
    with conn() as c:
        _init(c)
        c.execute("INSERT INTO instructions (user_id,proposal_id,at,text,norm,"
                  "applied) VALUES (?,?,?,?,?,?)",
                  (user_id, proposal_id, now(), text, norm, 1 if applied else 0))
        # count distinct proposals, not repeats within one
        n = c.execute("SELECT COUNT(DISTINCT proposal_id) AS n FROM instructions "
                      "WHERE user_id=? AND norm=? AND applied=1",
                      (user_id, norm)).fetchone()["n"]
        if n >= THRESHOLD:
            c.execute("INSERT INTO preferences (user_id,norm,text,seen,last_at) "
                      "VALUES (?,?,?,?,?) ON CONFLICT(user_id,norm) DO UPDATE "
                      "SET seen=excluded.seen, last_at=excluded.last_at",
                      (user_id, norm, text, n, now()))
    return {"norm": norm, "seen": n, "is_preference": n >= THRESHOLD}


def preferences(user_id, include_muted=False):
    with conn() as c:
        _init(c)
        rows = c.execute(
            "SELECT norm, text, seen, last_at, muted FROM preferences "
            "WHERE user_id=? %s ORDER BY seen DESC"
            % ("" if include_muted else "AND muted=0"), (user_id,)).fetchall()
    return [dict(r) for r in rows]


def mute(user_id, norm, muted=True):
    with conn() as c:
        _init(c)
        c.execute("UPDATE preferences SET muted=? WHERE user_id=? AND norm=?",
                  (1 if muted else 0, user_id, norm))


def suggestions(user_id, data):
    """Preferences worth offering on this proposal, skipping any already true."""
    out = []
    for p in preferences(user_id):
        if _already_done(p["norm"], data):
            continue
        out.append(p)
    return out


def _already_done(norm, data):
    if "screens" in norm and ("ui" in norm or "mockup" in norm):
        return bool(data.get("no_screens"))
    if "marketing" in norm:
        return "page9" in (data.get("hidden") or []) \
            or not data.get("page9", {}).get("include")
    return False


def history(user_id, limit=50):
    with conn() as c:
        _init(c)
        rows = c.execute("SELECT at, text, proposal_id FROM instructions "
                         "WHERE user_id=? ORDER BY id DESC LIMIT ?",
                         (user_id, limit)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Corrections and standing rules
# ---------------------------------------------------------------------------
# Rules are held for the whole team, not one account. If one person keeps
# correcting the same thing, nobody else should have to correct it again.

FIELD_NAMES = {
    "page1.title": "the cover title",
    "page1.description": "the cover description",
    "page3.one_liner": "the app one-liner",
    "page3.description": "the app overview paragraphs",
    "page4.one_liner": "the differentiator line",
    "page4.description": "the differentiator description",
    "page4.cards": "the differentiator cards",
    "page9": "the marketing page",
    "page10.stack": "the technology stack",
    "page10.services": "the integrations list",
    "page12.rows": "the milestone descriptions",
    "page14.risk_area": "the app-store risk wording",
    "core_pages": "the core feature pages",
}


def field_name(path):
    for prefix, name in FIELD_NAMES.items():
        if path.startswith(prefix):
            return name
    return path.split(".")[0]


def _generalise(path):
    """page4.cards.2.body -> page4.cards.body, so a rule covers every card."""
    parts = [p for p in path.split(".") if not p.isdigit()]
    return ".".join(parts)


def record_correction(user_id, proposal_id, path, before, after, instruction=""):
    """Log what was changed, and promote it once it recurs across proposals."""
    field = _generalise(path)
    norm = "%s|%s" % (field, normalise(instruction) if instruction else "edit")
    with conn() as c:
        _init(c)
        c.execute("INSERT INTO corrections (user_id,proposal_id,at,path,field,"
                  "instruction,before,after) VALUES (?,?,?,?,?,?,?,?)",
                  (user_id, proposal_id, now(), path, field, instruction,
                   str(before)[:600], str(after)[:600]))
        n = c.execute("SELECT COUNT(DISTINCT proposal_id) AS n FROM corrections "
                      "WHERE field=? AND instruction<>''", (field,)).fetchone()["n"]
        if n >= RULE_THRESHOLD and instruction:
            c.execute("INSERT INTO rules (scope,norm,text,field,seen,last_at) "
                      "VALUES ('team',?,?,?,?,?) ON CONFLICT(norm) DO UPDATE SET "
                      "seen=excluded.seen, last_at=excluded.last_at, "
                      "text=excluded.text",
                      (norm, instruction, field, n, now()))
    return {"field": field, "seen": n, "is_rule": bool(instruction) and n >= RULE_THRESHOLD}


def rules(include_muted=False):
    with conn() as c:
        _init(c)
        rows = c.execute("SELECT norm, text, field, seen, last_at, muted FROM "
                         "rules %s ORDER BY seen DESC LIMIT 40"
                         % ("" if include_muted else "WHERE muted=0")).fetchall()
    return [dict(r) for r in rows]


def mute_rule(norm, muted=True):
    with conn() as c:
        _init(c)
        c.execute("UPDATE rules SET muted=? WHERE norm=?",
                  (1 if muted else 0, norm))


def rules_for_prompt(limit=12):
    """The house rules, phrased for a generation prompt."""
    out = []
    for r in rules()[:limit]:
        out.append("- On %s: %s (corrected on %d proposals)"
                   % (field_name(r["field"]), r["text"].rstrip("."), r["seen"]))
    return out


def corrections_for(field, limit=3):
    """Recent before/after pairs, as worked examples."""
    with conn() as c:
        _init(c)
        rows = c.execute("SELECT before, after, instruction FROM corrections "
                         "WHERE field=? AND after<>'' ORDER BY id DESC LIMIT ?",
                         (field, limit)).fetchall()
    return [dict(r) for r in rows]
