#!/usr/bin/env python3
"""
The board snapshot: what the tracker says, with no judgement in it.

An adapter's job used to be "produce KIF", which meant every adapter also had to decide what
was a defect, what was rework and what the client had to explain. The Asana one could not, so
in practice an assistant did all of it by hand on every run - which is where the half hour
went, and why two runs of the same board could disagree.

So reading and judging are now two steps. A reader produces this snapshot: items, their
fields, their status moves and their comments, exactly as the tracker holds them. Everything
that needs a rule or a brain happens afterwards, in one place, for every tracker alike
(classify.py, judge.py).

The snapshot is also the cache. Each item carries `modified_at`, so the next run asks the
tracker only for what changed and reuses the history it already has.

    board.json
      tracker, project_ref, project_name, url, fetched_at, capabilities[], sections[]
      items[]: id, key, url, title, description, section, completed, created_at, created_by,
               completed_at, modified_at, due_on, assignee, tags[], fields{}, parent,
               events[]   {at, kind: section|completed|reopened|field, from, to, field, by}
               comments[] {at, by, text, url}
               history_at (when events/comments were last read; null = never)
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

BOARD_VERSION = "1.0"


class ReaderError(RuntimeError):
    """A tracker could not be read. The message is for a person: what happened, and what to do."""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save(path: Path, board: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(board, indent=1, ensure_ascii=False), encoding="utf-8")


def day(value: str | None) -> str | None:
    """'2026-07-16T09:12:44.000Z' -> '2026-07-16'. Dates are compared as days everywhere."""
    return str(value)[:10] if value else None


def fingerprint(item: dict) -> str:
    """Changes when something a judgement could depend on changes - and only then. A
    judgement made against one fingerprint is reused until the item moves, is renamed,
    gains a comment or has a field edited; a new 'like' or a reassignment does not reopen
    a settled question."""
    basis = {
        "title": item.get("title"),
        "section": item.get("section"),
        "completed": bool(item.get("completed")),
        "fields": item.get("fields") or {},
        "tags": sorted(item.get("tags") or []),
        "events": item.get("events") or [],
        "comments": item.get("comments") or [],
        "created_by": item.get("created_by"),
        "created_at": item.get("created_at"),
        "completed_at": item.get("completed_at"),
        "description": hashlib.sha1((item.get("description") or "").encode("utf-8")).hexdigest()[:8],
    }
    raw = json.dumps(basis, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


# --------------------------------------------------------------------------------------
# Tags people type into titles - and mistype
# --------------------------------------------------------------------------------------
#
# Teams mark things in the title: "[Existing]", "[CR]", "(Vendor)", "[Web][Device]". A
# literal match on "[Existing]" works until somebody types "[Exisiting]", and then a bug that
# was already in the product is counted against the team and nobody notices, because the
# regex did exactly what it was told.
#
# So tags are read tolerantly: every bracketed group is lexed out of the title, normalised,
# and compared to the team's vocabulary allowing for a slip of the keyboard. A tolerant match
# is never silent - the caller gets told it was fuzzy, so the sheet can say "read [Exisiting]
# as Existing" next to the row and a person can disagree.

_TAG = re.compile(r"[\[\(\{]\s*([^\]\)\}]{1,40}?)\s*[\]\)\}]")


def tags_of(title: str) -> list[str]:
    """Every bracketed group in a title, in order, as typed."""
    return [m.group(1).strip() for m in _TAG.finditer(title or "") if m.group(1).strip()]


def strip_tags(title: str) -> str:
    return re.sub(r"\s{2,}", " ", _TAG.sub(" ", title or "")).strip(" -:·")


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def edit_distance(a: str, b: str, cap: int = 3) -> int:
    """Damerau-Levenshtein, so a swapped pair of letters ('Exsiting') costs one, not two.
    Stops counting past `cap`; nobody needs to know two words are nine edits apart."""
    if a == b:
        return 0
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev2: list[int] | None = None
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if prev2 is not None and i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        if min(cur) > cap:
            return cap + 1
        prev2, prev = prev, cur
    return prev[-1]


def _allowance(word: str) -> int:
    """How many slips a word of this length can absorb before it is a different word. 'CR'
    gets none - one edit away from 'CR' is half the alphabet."""
    n = len(word)
    return 0 if n <= 3 else (1 if n <= 7 else 2)


def match_vocab(tag: str, vocab: Iterable[str]) -> tuple[str | None, str]:
    """Match one tag against a vocabulary. Returns (canonical word, how): how is 'exact',
    'fuzzy' or ''. A tag that merely starts with a vocabulary word ('Existing Issue',
    'Existing - kiosk') is exact; a misspelling within the allowance is fuzzy."""
    t = norm(tag)
    if not t:
        return None, ""
    words = [w for w in vocab if norm(w)]
    for w in words:
        if t == norm(w) or t.startswith(norm(w)) and len(norm(w)) >= 4:
            return w, "exact"
    best: tuple[int, str] | None = None
    for w in words:
        nw = norm(w)
        allow = _allowance(nw)
        if not allow:
            continue
        # Compare against the same-length head too, so '[Exisiting Bug]' still finds 'Existing'.
        for cand in {t, t[: len(nw)], t[: len(nw) + 1]}:
            d = edit_distance(cand, nw, cap=allow)
            if d <= allow and (best is None or d < best[0]):
                best = (d, w)
    return (best[1], "fuzzy") if best else (None, "")


def find_tag(title: str, vocab: Iterable[str]) -> tuple[str | None, str, str]:
    """(canonical, how, the tag as typed) for the first tag in the title that matches."""
    vocab = list(vocab)
    fuzzy: tuple[str, str] | None = None
    for raw in tags_of(title):
        word, how = match_vocab(raw, vocab)
        if how == "exact":
            return word, how, raw
        if how == "fuzzy" and fuzzy is None:
            fuzzy = (word, raw)  # type: ignore[assignment]
    if fuzzy:
        return fuzzy[0], "fuzzy", fuzzy[1]
    return None, "", ""


# --------------------------------------------------------------------------------------
# Reading history
# --------------------------------------------------------------------------------------

def _in(name: str | None, names: Iterable[str]) -> bool:
    n = norm(name or "")
    return bool(n) and any(n == norm(x) for x in names)


def moves(item: dict) -> list[dict]:
    """Status moves in time order. A section change and a status-field change are the same
    thing to a reader: the card went from one state to another."""
    out = [e for e in (item.get("events") or []) if e.get("kind") in ("section", "field")]
    return sorted(out, key=lambda e: e.get("at") or "")


def first_entered(item: dict, states: Iterable[str]) -> str | None:
    """The day the item first entered any of these states."""
    states = list(states)
    for e in moves(item):
        if _in(e.get("to"), states):
            return day(e.get("at"))
    return None


def last_entered(item: dict, states: Iterable[str]) -> str | None:
    states = list(states)
    hit = None
    for e in moves(item):
        if _in(e.get("to"), states):
            hit = day(e.get("at"))
    return hit


def entered_after(item: dict, first: Iterable[str], then: Iterable[str]) -> dict | None:
    """The first move into `then` that happened after the item had entered `first`. This is
    the shape of rework: closed, and afterwards back in play."""
    first, then = list(first), list(then)
    seen_first = False
    for e in moves(item):
        if _in(e.get("to"), first):
            seen_first = True
        elif seen_first and _in(e.get("to"), then):
            return e
    return None


def ever_in(item: dict, states: Iterable[str]) -> list[dict]:
    states = list(states)
    return [e for e in moves(item) if _in(e.get("to"), states)]


def comments_between(item: dict, start: str | None, end: str | None, limit: int = 6) -> list[dict]:
    out = []
    for c in item.get("comments") or []:
        at = c.get("at") or ""
        if (not start or at >= start) and (not end or at <= end):
            out.append(c)
    return out[:limit]


def summary(board: dict) -> dict[str, Any]:
    items = board.get("items") or []
    return {
        "items": len(items),
        "with_history": sum(1 for i in items if i.get("history_at")),
        "sections": len(board.get("sections") or []),
        "fetched_at": board.get("fetched_at"),
    }
