"""What every proposal costs.

Each model call and each screenshot is recorded against the user and the
proposal that caused it, priced from a table, so the admin view can answer
"what did this client's proposal cost us" without guesswork.
"""
import os

from .db import conn, now

SCHEMA = """
CREATE TABLE IF NOT EXISTS usage (
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, user_id TEXT, proposal_id TEXT,
  kind TEXT, provider TEXT, model TEXT, stage TEXT,
  input_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0,
  units INTEGER DEFAULT 0, cost REAL DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_usage_user ON usage(user_id, id);
CREATE INDEX IF NOT EXISTS ix_usage_prop ON usage(proposal_id, id);
"""

# US dollars per million tokens. Override with PRICE_<MODEL>_IN / _OUT.
PRICES = {
    "claude-opus-5":    (15.0, 75.0),
    "claude-sonnet-5":  (3.0,  15.0),
    "claude-haiku-4-5": (0.80, 4.0),
}
DEFAULT_PRICE = (3.0, 15.0)

# flat costs per call, for things billed per unit rather than per token
UNIT_COSTS = {
    "screenshot": float(os.environ.get("PRICE_SCREENSHOT", "0.003")),
    "v0_build": float(os.environ.get("PRICE_V0_BUILD", "0.20")),
}

_CTX = {"user_id": None, "proposal_id": None}


def set_context(user_id, proposal_id):
    """Everything recorded until the next call belongs to this user and job."""
    _CTX["user_id"] = user_id
    _CTX["proposal_id"] = proposal_id or "-"


def _init(c):
    c.executescript(SCHEMA)


def _price(model):
    key = (model or "").lower()
    for name, pair in PRICES.items():
        if key.startswith(name):
            env_in = os.environ.get("PRICE_%s_IN" % name.upper().replace("-", "_"))
            env_out = os.environ.get("PRICE_%s_OUT" % name.upper().replace("-", "_"))
            return (float(env_in) if env_in else pair[0],
                    float(env_out) if env_out else pair[1])
    return DEFAULT_PRICE


def record_model(model, stage, input_tokens, output_tokens):
    per_in, per_out = _price(model)
    cost = (input_tokens / 1e6) * per_in + (output_tokens / 1e6) * per_out
    _write("model", "anthropic", model, stage, input_tokens, output_tokens, 0, cost)
    return cost


def record_units(kind, provider, units=1, stage=""):
    cost = UNIT_COSTS.get(kind, 0.0) * units
    _write(kind, provider, "", stage, 0, 0, units, cost)
    return cost


def _write(kind, provider, model, stage, tin, tout, units, cost):
    try:
        with conn() as c:
            _init(c)
            c.execute("INSERT INTO usage (at,user_id,proposal_id,kind,provider,"
                      "model,stage,input_tokens,output_tokens,units,cost) "
                      "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      (now(), _CTX["user_id"], _CTX["proposal_id"], kind,
                       provider, model, stage, tin, tout, units, round(cost, 6)))
    except Exception:                                         # noqa: BLE001
        pass          # accounting must never break a render


def _rows(sql, args=()):
    with conn() as c:
        _init(c)
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def totals():
    r = _rows("SELECT COUNT(*) AS calls, COALESCE(SUM(cost),0) AS cost, "
              "COALESCE(SUM(input_tokens),0) AS tin, "
              "COALESCE(SUM(output_tokens),0) AS tout FROM usage")
    return r[0] if r else {}


def by_user():
    return _rows(
        "SELECT u.email, u.name, COUNT(*) AS calls, "
        "COALESCE(SUM(x.cost),0) AS cost, "
        "COUNT(DISTINCT x.proposal_id) AS proposals "
        "FROM usage x LEFT JOIN users u ON u.id = x.user_id "
        "GROUP BY x.user_id, u.email, u.name ORDER BY cost DESC")


def by_proposal(limit=50):
    return _rows(
        "SELECT p.name, p.id, COALESCE(u.email,'') AS email, "
        "COUNT(*) AS calls, COALESCE(SUM(x.cost),0) AS cost "
        "FROM usage x LEFT JOIN proposals p ON p.id = x.proposal_id "
        "LEFT JOIN users u ON u.id = x.user_id "
        "GROUP BY x.proposal_id, p.name, p.id, u.email "
        "ORDER BY cost DESC LIMIT ?", (limit,))


def by_kind():
    return _rows("SELECT kind, provider, COUNT(*) AS calls, "
                 "COALESCE(SUM(cost),0) AS cost FROM usage "
                 "GROUP BY kind, provider ORDER BY cost DESC")


def recent(limit=40):
    return _rows("SELECT at, kind, model, stage, input_tokens, output_tokens, "
                 "cost, proposal_id FROM usage ORDER BY id DESC LIMIT ?", (limit,))


def for_proposal(pid):
    r = _rows("SELECT COUNT(*) AS calls, COALESCE(SUM(cost),0) AS cost "
              "FROM usage WHERE proposal_id=?", (pid,))
    return r[0] if r else {"calls": 0, "cost": 0}


def average_proposal_cost():
    r = _rows("SELECT AVG(c) AS mean FROM (SELECT SUM(cost) AS c FROM usage "
              "WHERE proposal_id <> '-' GROUP BY proposal_id) AS per_proposal")
    return (r[0].get("mean") or r[0].get("avg") or 0) if r else 0
