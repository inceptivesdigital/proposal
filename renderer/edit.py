"""Prompt editing, scoped to one node.

The model receives only the node named by the path, never the whole document, so
a rewrite costs a few hundred tokens instead of several thousand and cannot
touch anything the user did not select.
"""
import json
import os
import re

from .store import get, parse

MODEL = os.environ.get("PROPOSAL_EDIT_MODEL", "claude-sonnet-4-6")

SYSTEM = """You rewrite one fragment of an Inceptives Digital proposal.

You are given the JSON value at a single path and an instruction. Return the \
rewritten value as JSON, with exactly the same shape and type as the input: a \
string stays a string, a two-item list stays two items, an object keeps every key.

House rules: British-neutral, plain, confident. No hype, no filler, no em-dashes. \
Keep it close to the original length so it still fits the layout. Never invent \
client names, prices, dates or timelines; if the fragment contains one, carry it \
through unchanged.

Return only the JSON value. No commentary, no code fences."""

# Anything on this list is a typed fact or a legal/contract string. Prompt
# editing is refused so a rewrite can never quietly change a price or a term.
LOCKED_PREFIXES = (
    "meta",
    "page12.total", "page12.total_value",
    "page14.cards",
)
LOCKED_SUFFIXES = ("amount",)


def is_locked(path):
    if any(path == p or path.startswith(p + ".") for p in LOCKED_PREFIXES):
        return True
    return parse(path)[-1] in LOCKED_SUFFIXES


def _strip_fences(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
    return text


def _same_shape(a, b):
    if isinstance(a, str):
        return isinstance(b, str)
    if isinstance(a, list):
        return isinstance(b, list) and len(a) == len(b)
    if isinstance(a, dict):
        return isinstance(b, dict) and set(a) == set(b)
    return type(a) is type(b)


def edit_node(data, path, instruction, client=None):
    """Returns an ops list ready for Proposal.apply, or raises."""
    if is_locked(path):
        raise PermissionError(
            "%s is a typed or contractual value and is edited by hand, not by prompt."
            % path)
    node = get(data, path)
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    payload = json.dumps({"path": path, "value": node,
                          "instruction": instruction}, ensure_ascii=False)
    msg = client.messages.create(
        model=MODEL, max_tokens=1200, system=SYSTEM,
        messages=[{"role": "user", "content": payload}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text")
    new = json.loads(_strip_fences(text))
    if not _same_shape(node, new):
        raise ValueError("model changed the shape of %s; edit rejected" % path)
    return [{"op": "set", "path": path, "value": new}]
