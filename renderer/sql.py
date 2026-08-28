"""One database layer, two backends.

SQLite when you run it on your own machine, Postgres when DATABASE_URL is set.
The rest of the code writes ordinary SQL with ? placeholders and does not care
which is underneath.
"""
import os
import re
import sqlite3
import threading

URL = (os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or
       os.environ.get("POSTGRES_URL_NON_POOLING") or "")
IS_PG = URL.startswith("postgres")

SQLITE_PATH = os.environ.get(
    "PROPOSAL_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "proposals.db"))

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
    return "postgres" if IS_PG else "sqlite"


def ping():
    """Is the database reachable? Used by the admin health view."""
    try:
        with connect() as c:
            c.execute("SELECT 1")
        return True, backend()
    except Exception as exc:                                  # noqa: BLE001
        return False, str(exc)[:200]
