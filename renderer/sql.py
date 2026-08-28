"""One database layer, two backends.

SQLite when you run it on your own machine, Postgres when DATABASE_URL is set.
The rest of the code writes ordinary SQL with ? placeholders and does not care
which is underneath.
"""
import os
import re
import sqlite3
import tempfile
import threading

URL = (os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or
       os.environ.get("POSTGRES_URL_NON_POOLING") or "")
IS_PG = URL.startswith("postgres")

def _writable(path):
    folder = os.path.dirname(path) or "."
    try:
        os.makedirs(folder, exist_ok=True)
        probe = os.path.join(folder, ".write-probe")
        with open(probe, "w") as fh:
            fh.write("x")
        os.remove(probe)
        return True
    except Exception:                                         # noqa: BLE001
        return False


_WANTED = os.environ.get(
    "PROPOSAL_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "proposals.db"))

# On a serverless host the project folder is read-only, so fall back to /tmp.
# That works, but /tmp is wiped when the function goes cold, so it is flagged
# loudly rather than silently losing people's accounts.
EPHEMERAL = False
if not IS_PG and not _writable(_WANTED):
    _WANTED = os.path.join(tempfile.gettempdir(), "proposals.db")
    EPHEMERAL = True

SQLITE_PATH = _WANTED

_local = threading.local()


def _pg_sql(sql):
    """Translate the SQLite dialect we write into Postgres."""
    sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
    sql = sql.replace("AUTOINCREMENT", "")
    sql = re.sub(r"\?", "%s", sql)
    return sql


class Rows(list):
    pass


class Cursor(object):
    """A thin cursor that always yields dict-like rows."""

    def __init__(self, raw, is_pg):
        self._raw = raw
        self._pg = is_pg

    def fetchone(self):
        row = self._raw.fetchone()
        return dict(row) if row is not None else None

    def fetchall(self):
        return [dict(r) for r in self._raw.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())


class Connection(object):
    def __init__(self):
        if IS_PG:
            import psycopg
            from psycopg.rows import dict_row
            self._c = psycopg.connect(URL, row_factory=dict_row,
                                      autocommit=False)
        else:
            self._c = sqlite3.connect(SQLITE_PATH, timeout=20)
            self._c.row_factory = sqlite3.Row
            self._c.execute("PRAGMA journal_mode=WAL")
            self._c.execute("PRAGMA foreign_keys=ON")

    def execute(self, sql, args=()):
        if IS_PG:
            cur = self._c.cursor()
            cur.execute(_pg_sql(sql), tuple(args))
            return Cursor(cur, True)
        return Cursor(self._c.execute(sql, tuple(args)), False)

    def executescript(self, script):
        """Schema setup. Postgres needs the statements run one at a time."""
        if IS_PG:
            cur = self._c.cursor()
            for stmt in [s.strip() for s in script.split(";") if s.strip()]:
                try:
                    cur.execute(_pg_sql(stmt))
                except Exception:                             # noqa: BLE001
                    self._c.rollback()          # an index or table already there
            self._c.commit()
            return
        self._c.executescript(script)

    def columns(self, table):
        if IS_PG:
            rows = self.execute(
                "SELECT column_name AS name FROM information_schema.columns "
                "WHERE table_name = ?", (table,)).fetchall()
        else:
            rows = self.execute("PRAGMA table_info(%s)" % table).fetchall()
        return {r["name"] for r in rows}

    def commit(self):
        self._c.commit()

    def rollback(self):
        self._c.rollback()

    def close(self):
        try:
            self._c.close()
        except Exception:                                     # noqa: BLE001
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()
        return False


def connect():
    return Connection()


def backend():
    if IS_PG:
        return "postgres"
    return "sqlite (temporary)" if EPHEMERAL else "sqlite"


def persistent():
    """Will anything written here survive? Only Postgres, or a real disk."""
    return IS_PG or not EPHEMERAL


def ping():
    """Is the database reachable? Used by the admin health view."""
    try:
        with connect() as c:
            c.execute("SELECT 1")
        return True, backend()
    except Exception as exc:                                  # noqa: BLE001
        return False, str(exc)[:200]


def table_check():
    """Which tables exist. A fresh database that never got its schema is the
    usual reason sign-up fails on an otherwise healthy deployment."""
    want = ["users", "sessions", "pending", "proposals", "versions", "activity"]
    try:
        with connect() as c:
            if IS_PG:
                rows = c.execute(
                    "SELECT table_name AS name FROM information_schema.tables "
                    "WHERE table_schema = 'public'").fetchall()
            else:
                rows = c.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        have = {r["name"] for r in rows}
        return {"present": sorted(have & set(want)),
                "missing": sorted(set(want) - have)}
    except Exception as exc:                                  # noqa: BLE001
        return {"error": str(exc)[:200]}
