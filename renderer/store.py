"""Proposal documents, versions and edits.

Proposals stay editable after sending, so every change writes a new version and
nothing is ever overwritten in place. A share link pins the version the client
was actually shown unless it is explicitly set to follow the latest, which means
a document can be corrected after sending without silently changing what someone
has already read or signed against.
"""
import copy
import time
import uuid


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Proposal(object):
    def __init__(self, data, author="", proposal_id=None):
        self.id = proposal_id or uuid.uuid4().hex[:12]
        self.status = "draft"
        self.versions = [{"n": 1, "created_at": _now(), "author": author,
                          "note": "created", "data": copy.deepcopy(data)}]
        self.shares = []            # {token, version, follow_latest, created_at}
        self.annotations = []       # internal only, never rendered

    # ------------------------------------------------------------ versions
    @property
    def latest(self):
        return self.versions[-1]

    @property
    def data(self):
        return self.latest["data"]

    def commit(self, data, author="", note=""):
        v = {"n": self.latest["n"] + 1, "created_at": _now(), "author": author,
             "note": note or "edit", "data": copy.deepcopy(data)}
        self.versions.append(v)
        return v

    def version(self, n):
        for v in self.versions:
            if v["n"] == n:
                return v
        raise KeyError("no version %s" % n)

    def restore(self, n, author=""):
        return self.commit(self.version(n)["data"], author,
                           "restored version %d" % n)

    def diff_summary(self, a, b):
        """Which JSON paths changed between two versions. Drives the audit trail."""
        return sorted(_changed_paths(self.version(a)["data"],
                                     self.version(b)["data"]))

    # --------------------------------------------------------------- edits
    def apply(self, ops, author="", note=""):
        """ops: list of {op, path, value}. op in set|insert|delete|move."""
        data = copy.deepcopy(self.data)
        for o in ops:
            _apply_one(data, o)
        return self.commit(data, author, note or "%d edit(s)" % len(ops))

    # -------------------------------------------------------------- sharing
    def send(self, author="", follow_latest=False):
        """Marks the proposal sent and issues a link pinned to this version."""
        self.status = "sent"
        share = {"token": uuid.uuid4().hex[:16], "version": self.latest["n"],
                 "follow_latest": follow_latest, "created_at": _now(),
                 "author": author}
        self.shares.append(share)
        return share

    def resolve_share(self, token):
        for s in self.shares:
            if s["token"] == token:
                return self.latest if s["follow_latest"] else self.version(s["version"])
        raise KeyError("unknown share token")

    def republish(self, token):
        """Point an existing link at the current version, and say so."""
        for s in self.shares:
            if s["token"] == token:
                s["version"] = self.latest["n"]
                s["republished_at"] = _now()
                return s
        raise KeyError("unknown share token")

    # ---------------------------------------------------------- annotations
    def annotate(self, path, body, author=""):
        note = {"id": uuid.uuid4().hex[:8], "path": path, "body": body,
                "author": author, "created_at": _now(), "resolved": False}
        self.annotations.append(note)
        return note

    def resolve_annotation(self, note_id):
        for a in self.annotations:
            if a["id"] == note_id:
                a["resolved"] = True
                return a
        raise KeyError("unknown annotation")

    def to_dict(self):
        return {"id": self.id, "status": self.status, "versions": self.versions,
                "shares": self.shares, "annotations": self.annotations}


# ------------------------------------------------------------- path helpers
def parse(path):
    """'page4.cards.2.title' -> ['page4', 'cards', 2, 'title']"""
    out = []
    for part in path.split("."):
        out.append(int(part) if part.lstrip("-").isdigit() else part)
    return out


def get(data, path):
    node = data
    for key in parse(path):
        node = node[key]
    return node


def _parent(data, keys):
    node = data
    for key in keys[:-1]:
        node = node[key]
    return node, keys[-1]


def _apply_one(data, op):
    kind = op["op"]
    keys = parse(op["path"])
    node, last = _parent(data, keys)
    if kind == "set":
        node[last] = op["value"]
    elif kind == "insert":
        node.insert(last if isinstance(last, int) else len(node), op["value"])
    elif kind == "append":
        node[last].append(op["value"])
    elif kind == "delete":
        del node[last]
    elif kind == "move":
        item = node.pop(last)
        node.insert(op["value"], item)
    else:
        raise ValueError("unknown op %r" % kind)


def _changed_paths(a, b, prefix=""):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in set(a) | set(b):
            if k.startswith("_"):
                continue
            p = "%s.%s" % (prefix, k) if prefix else str(k)
            if k not in a or k not in b:
                yield p
            else:
                for x in _changed_paths(a[k], b[k], p):
                    yield x
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            yield prefix or "."
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                for p in _changed_paths(x, y, "%s.%d" % (prefix, i)):
                    yield p
    elif a != b:
        yield prefix or "."
