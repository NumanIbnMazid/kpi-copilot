#!/usr/bin/env python3
"""
The project's memory: judgements, and the facts they rest on.

A run used to start from nothing. Every judgement - is this a change request, was this bug
already in the product, did the client have to explain the requirement - was made again from
scratch, by whoever or whatever was running it that day. That is slow, and it is also how the
same board produced 53 deliverables one week and 41 the next.

So a judgement is made once and kept, with who made it, why, and what the item looked like
at the time:

    <workspace>/<project>/
        ledger.json            item-level judgements, with provenance
        facts/periods.yaml     the periods: dates, handover, PMS ids, team hours, the story
        facts/plan.yaml        the agreed scope: items, hours, milestones
        facts/estimates.yaml   approved additions: items, hours, when approved
        facts/reasons.yaml     the "why" for each period and KPI

Three authors can write a judgement, and they outrank each other in a fixed order:

    human  >  ai  >  rule

A rule's answer is never stored - rules are cheap, and they get better when the code does.
An assistant's answer is stored against the item's fingerprint and reused until the item
changes; then it is asked again, and shown what it said last time. A person's answer stays
until a person changes it, and if the item moved underneath it the sheet says so.

The facts files are plain YAML on purpose. They are the part of a project a lead actually
knows, and the yellow cells of the workbook are the same facts seen from the other side:
whatever is typed there is read back into these files at the start of the next run.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

LEDGER_VERSION = "1.0"
RANK = {"rule": 0, "ai": 1, "human": 2}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Ledger:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, Any] = {"ledger_version": LEDGER_VERSION, "items": {}, "answers": {}, "runs": []}
        if path.exists():
            try:
                self.data.update(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                pass
        self.dirty = False

    # -- judgements ---------------------------------------------------------------------

    def get(self, item_id: str, field: str) -> dict | None:
        return ((self.data["items"].get(item_id) or {}).get("judgements") or {}).get(field)

    def usable(self, item_id: str, field: str, fingerprint: str | None) -> dict | None:
        """The stored judgement, if it still applies. A person's always does. An assistant's
        does while the item has not changed since it answered."""
        j = self.get(item_id, field)
        if not j:
            return None
        if j.get("by") == "human":
            return j
        if fingerprint is None or j.get("fingerprint") == fingerprint:
            return j
        return None

    def stale(self, item_id: str, field: str, fingerprint: str | None) -> dict | None:
        """An assistant's judgement the item has since moved out from under."""
        j = self.get(item_id, field)
        if j and j.get("by") != "human" and fingerprint and j.get("fingerprint") != fingerprint:
            return j
        return None

    def set(self, item_id: str, field: str, value: Any, by: str, why: str = "", *,
            evidence: str | None = None, fingerprint: str | None = None, key: str | None = None,
            title: str | None = None, who: str = "") -> bool:
        """Record a judgement. Returns False, and changes nothing, when a higher-ranked
        author has already answered - an assistant does not get to overrule a person."""
        cur = self.get(item_id, field)
        if cur and RANK.get(cur.get("by"), 0) > RANK.get(by, 0):
            return False
        if cur and cur.get("value") == value and cur.get("by") == by and cur.get("fingerprint") == fingerprint:
            return True
        entry = self.data["items"].setdefault(item_id, {"judgements": {}})
        if key:
            entry["key"] = key
        if title:
            entry["title"] = title[:140]
        entry.setdefault("judgements", {})[field] = {
            "value": value, "by": by, "why": why, "evidence": evidence,
            "fingerprint": fingerprint, "at": _now(), **({"who": who} if who else {}),
        }
        self.dirty = True
        return True

    def forget(self, item_id: str, field: str) -> None:
        if self.get(item_id, field):
            del self.data["items"][item_id]["judgements"][field]
            self.dirty = True

    # -- answers to questions that are not about one item --------------------------------

    def answer(self, qid: str) -> Any:
        return (self.data["answers"].get(qid) or {}).get("value")

    def set_answer(self, qid: str, value: Any, by: str = "human", why: str = "") -> None:
        self.data["answers"][qid] = {"value": value, "by": by, "why": why, "at": _now()}
        self.dirty = True

    # -- what the numbers were last time ------------------------------------------------

    def last_run(self) -> dict | None:
        return self.data["runs"][-1] if self.data["runs"] else None

    def record_run(self, values: dict, meta: dict | None = None) -> None:
        self.data["runs"].append({"at": _now(), "values": values, **(meta or {})})
        self.data["runs"] = self.data["runs"][-40:]
        self.dirty = True

    def save(self) -> None:
        if not self.dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=1, ensure_ascii=False), encoding="utf-8")
        self.dirty = False


# --------------------------------------------------------------------------------------
# facts files
# --------------------------------------------------------------------------------------

FACT_FILES = ("periods", "plan", "estimates", "reasons")


def _yaml():
    import yaml  # type: ignore
    return yaml


def _plain(node: Any) -> Any:
    """YAML reads an unquoted 2026-09-11 as a date. Everything downstream compares ISO
    strings, so dates are normalised on the way in rather than at every comparison."""
    if isinstance(node, dict):
        return {k: _plain(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_plain(v) for v in node]
    if isinstance(node, (datetime, date)):
        return node.isoformat()[:10]
    return node


def load_facts(project_dir: Path, name: str) -> dict:
    path = project_dir / "facts" / f"{name}.yaml"
    if not path.exists():
        return {}
    try:
        return _plain(_yaml().safe_load(path.read_text(encoding="utf-8")) or {})
    except Exception as e:  # noqa: BLE001 - a broken facts file must name itself
        raise SystemExit(f"{path} does not parse as YAML: {e}")


def save_facts(project_dir: Path, name: str, data: dict) -> Path:
    path = project_dir / "facts" / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_yaml().safe_dump(data, sort_keys=False, allow_unicode=True, width=100),
                    encoding="utf-8")
    return path


def all_facts(project_dir: Path) -> dict[str, dict]:
    return {name: load_facts(project_dir, name) for name in FACT_FILES}
