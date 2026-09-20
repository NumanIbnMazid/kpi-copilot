#!/usr/bin/env python3
"""
What a person typed into the sheet, carried into the next run.

Every run rewrites the workbook. If that were all it did, the first edit a lead made would
be the last one they bothered with. So a run begins by reading the sheet it wrote last time:

    what was written into each yellow cell   (sheet_state.json, saved beside the ledger)
    what is there now                         (the .xlsx, or the live Google Sheet)

Every difference is an edit somebody made on purpose, and each is filed where that kind of
fact lives, as a person's answer - the highest authority there is:

    a Yes/No, a type, a period on a register row   -> the ledger, by: human
    a date or an hours figure on a row             -> the ledger, as a value set by hand
    anything on the Periods tab, the project dates -> facts/periods.yaml
    a reason on KPI Summary                        -> facts/reasons.yaml
    a value set by hand, with its why              -> manual.yaml
    an answer on Open Questions                    -> the ledger's answers
    a row typed in by hand                         -> facts/extra_rows.yaml

One thing is deliberately not applied: a counting rule changed on the Config tab. The live
numbers follow it at once, which is useful for seeing what it would do - but a counting rule
moves how this project compares with every other, so it is reported, with the way to change
it properly, and left alone.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Callable

import board as B
import sheet_model as M
from sheet_xlsx import plain_value

Grid = Callable[[str, int, int], Any]

TASK_JUDGED = {"period": "period", "type": "nature", "understood": "understood", "reopened": "reopened"}
DEFECT_JUDGED = {"period": "period", "kind": "nature", "phase": "phase", "pre_existing": "pre_existing",
                 "rejected": "rejected"}
PHASE_IN = {"Pre-release": "QA", "Post-release": "Post-release"}
FINAL_IN = {v: k for k, v in M.FINAL_OUT.items() if k != "Closed"}
RULE_WORDS = {"count_obs": "policy.count_observations", "count_imp": "policy.count_improvements",
              "count_pre": "policy.count_pre_existing", "count_post": "policy.count_post_release",
              "velocity_unit": "the project's velocity_unit", "hours_basis": "sources.hours_basis",
              "commit_on": "workflow.commitment.met_when", "cr_den": "a cr_denominator rule override"}


def _spec(tab: M.Tab) -> dict | None:
    rb = tab.readback
    if not rb:
        return None
    out = {k: v for k, v in rb.items() if k != "cols"}
    if "cols" in rb:
        out["fields"] = [(i, c[0], c[3]) for i, c in enumerate(rb["cols"], start=1)]
    return out


def _model_grid(tab: M.Tab) -> Grid:
    def grid(_name: str, r: int, c: int) -> Any:
        cell = tab.cells.get((r, c)) or {}
        return None if cell.get("f") else plain_value(cell.get("v"))
    rows = max((r for r, _ in tab.cells), default=0)
    grid.rows = lambda _n: rows                                          # type: ignore[attr-defined]
    return grid


def _read(name: str, spec: dict, grid: Grid) -> dict:
    kind = spec["kind"]
    if kind == "cells":
        cells = {k: grid(name, r, c) for k, (r, c) in spec["cells"].items()}
        rules = {k: grid(name, r, c) for k, (r, c) in (spec.get("rules") or {}).items()}
        return {"cells": cells, "rules": rules}
    last = getattr(grid, "rows", lambda _n: 400)(name)
    if kind == "summary":
        rows = {}
        for r in range(spec["first"], max(spec["last"], spec["first"]) + 1):
            per, kpi = grid(name, r, spec["period"]), grid(name, r, spec["kpi"])
            if per and kpi:
                rows[f"{per}|{kpi}"] = {"why": grid(name, r, spec["why"]), "value": grid(name, r, spec["manual_value"]),
                                        "manual_why": grid(name, r, spec["manual_why"])}
        return {"rows": rows}
    if kind == "questions":
        return {"rows": {str(grid(name, r, spec["id"])): {"answer": grid(name, r, spec["answer"])}
                         for r in range(spec["first"], last + 1) if grid(name, r, spec["id"])}}
    rows, fields = {}, spec["fields"]
    idx = {key: i for i, key, _ in fields}
    for r in range(spec["first"], last + 1):
        rec = {key: grid(name, r, i) for i, key, role in fields if role == "in" or key in ("key", "title", "item")}
        if not any(v is not None for k, v in rec.items() if k != "item"):
            continue
        # A row the tool wrote is known by its hidden Row ID. One typed in by hand has none,
        # and is known by what the person called it.
        rid = (f"#{r - spec['first'] + 1}" if spec["key"] == "name"
               else str(rec.get("item") or f"hand:{rec.get('key') or ''}|{rec.get('title') or ''}"))
        rows[rid] = rec
    _ = idx
    return {"rows": rows}


def snapshot(tabs: list[M.Tab], destination: dict) -> dict:
    """What this run wrote into every cell a person may change."""
    state = {"model": M.MODEL_VERSION, "written_at": B.now_iso(), "destination": destination, "spec": {}, "values": {}}
    for tab in tabs:
        spec = _spec(tab)
        if spec:
            state["spec"][tab.name] = spec
            state["values"][tab.name] = _read(tab.name, spec, _model_grid(tab))
    return state


def save_state(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, indent=1, default=str, ensure_ascii=False), encoding="utf-8")


def load_state(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except (OSError, json.JSONDecodeError) as e:
        raise SystemExit(f"Cannot read sheet baseline {path}. Restore it before refreshing the review sheet: {e}") from e


def _same(a: Any, b: Any) -> bool:
    a, b = plain_value(a), plain_value(b)
    if a == b:
        return True
    try:
        return abs(float(a) - float(b)) < 1e-9
    except (TypeError, ValueError):
        return str(a or "").strip() == str(b or "").strip()


def _iso(v: Any) -> Any:
    """A date typed into a sheet arrives as a date, a serial number or text, depending on
    the sheet. Facts files hold ISO text."""
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()[:10]
    if isinstance(v, (int, float)) and 30000 < v < 80000:
        return (dt.date(1899, 12, 30) + dt.timedelta(days=int(v))).isoformat()
    if isinstance(v, str):
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
            try:
                return dt.datetime.strptime(v.strip(), fmt).date().isoformat()
            except ValueError:
                continue
    return v


def fold(state: dict, grid: Grid, ledger, facts: dict, manual: dict, board_items: dict, who: str = "") -> list[str]:
    """Find every edit and file it. Returns one line per edit, for the run's report."""
    said: list[str] = []
    today = dt.date.today().isoformat()
    why = f"changed in the sheet, read back {today}"

    def spec_of(tab: str) -> dict:
        s = dict(state["spec"][tab])
        if "fields" in s:
            s["fields"] = [tuple(f) for f in s["fields"]]
        if "cells" in s:
            s["cells"] = {k: tuple(v) for k, v in s["cells"].items()}
            s["rules"] = {k: tuple(v) for k, v in (s.get("rules") or {}).items()}
        return s

    # Read every tab before accepting any edit. A partial read must not become a new baseline.
    current = {}
    for tab in state.get("values") or {}:
        if getattr(grid, "rows", lambda _: 1)(tab) == 0:
            raise ValueError(f"Review tab '{tab}' is missing or empty; restore it before refreshing")
        current[tab] = _read(tab, spec_of(tab), grid)
    for tab, before in (state.get("values") or {}).items():
        now = current[tab]

        if tab == "Config":
            proj = facts.setdefault("periods", {}).setdefault("project", {})
            for k, v in now["cells"].items():
                if not _same(v, before["cells"].get(k)):
                    proj[k] = _iso(v)
                    said.append(f"Config · {k.replace('_', ' ')} -> {_iso(v)}")
            for k, v in (now.get("rules") or {}).items():
                if not _same(v, (before.get("rules") or {}).get(k)):
                    said.append(f"Config · '{v}' was set for a counting rule in the sheet. NOT applied: it changes how "
                                f"this project compares with others. To change it for real, set {RULE_WORDS.get(k, k)} "
                                f"in the profile (ask the assistant to, with the reason) and run again.")
            continue

        if tab == "KPI Summary":
            for rid, rec in now["rows"].items():
                old = before["rows"].get(rid) or {}
                per, kpi = rid.split("|", 1)
                if not _same(rec.get("why"), old.get("why")):
                    reasons = facts.setdefault("reasons", {})
                    reasons.setdefault(per, {})[kpi] = rec.get("why") or ""
                    reasons.setdefault("_authors", {})[rid] = "human"
                    said.append(f"{per} · {kpi}: reason taken from the sheet")
                if not _same(rec.get("value"), old.get("value")) or not _same(rec.get("manual_why"), old.get("manual_why")):
                    if rec.get("value") in (None, ""):
                        (manual.get(per) or {}).pop(kpi, None)
                        said.append(f"{per} · {kpi}: hand-set value removed")
                    else:
                        manual.setdefault(per, {})[kpi] = {"value": rec["value"], "why": rec.get("manual_why") or "",
                                                           "by": who, "at": today}
                        said.append(f"{per} · {kpi}: set by hand to {rec['value']}"
                                    + ("" if rec.get("manual_why") else " - but with no reason, so it will be refused"))
            continue

        if tab == "Open Questions":
            for qid, rec in now["rows"].items():
                ans = rec.get("answer")
                if ans not in (None, "") and not _same(ans, (before["rows"].get(qid) or {}).get("answer")):
                    _file_answer(qid, ans, ledger, facts)
                    said.append(f"Answered: {qid} -> {ans}")
            continue

        if tab == "Periods":
            plist = facts.setdefault("periods", {}).setdefault("periods", [])
            prior_by_name = {v.get("name"): v for v in before["rows"].values() if v.get("name")}
            names_now = [v.get("name") for v in now["rows"].values()]
            if len(names_now) != len(set(names_now)) or any(not n for n in names_now):
                raise ValueError("Periods need unique, non-empty names before refreshing")
            for rid, rec in now["rows"].items():
                old = prior_by_name.get(rec.get("name")) or before["rows"].get(rid) or {}
                changed = {k: v for k, v in rec.items() if not _same(v, old.get(k))}
                if not changed:
                    continue
                target = next((p for p in plist if p.get("name") == rec.get("name")), None)
                if target is None and old.get("name") not in names_now:
                    target = next((p for p in plist if p.get("name") == old.get("name")), None)
                if target is None:
                    target = {k: _iso(v) for k, v in old.items() if v is not None}
                    target["name"] = rec["name"]
                    plist.append(target)
                i = next(j for j, p in enumerate(plist) if p is target)
                for k, v in rec.items():
                    if k in ("key", "title", "item") or _same(v, old.get(k)):
                        continue
                    if k == "name" and plist[i].get("name") and v:
                        plist[i]["old_name"] = plist[i]["name"]
                    plist[i][k] = _iso(v) if k != "name" else v
                    (plist[i].get("_from_timeline") or {}).pop(k, None)
                    said.append(f"Periods · {rec.get('name') or rid} · {k.replace('_', ' ')} -> {_iso(v)}")
            continue

        judged = TASK_JUDGED if tab == "Task Register" else DEFECT_JUDGED
        extra = facts.setdefault("extra_rows", {}).setdefault("tasks" if tab == "Task Register" else "defects", [])
        for rid, rec in now["rows"].items():
            old = before["rows"].get(rid)
            by_hand, plan_row = rid.startswith("hand:"), rid.startswith("plan:")
            item_id = "" if (by_hand or plan_row) else rid.split("#", 1)[0]
            key = rec.get("key") or rec.get("title") or rid
            if old is None:
                if rec.get("key") or rec.get("title"):
                    row = {k: _iso(v) for k, v in rec.items() if v is not None and k != "item"}
                    extra[:] = [x for x in extra if (x.get("key"), x.get("title")) != (row.get("key"), row.get("title"))] + [row]
                    said.append(f"{tab} · {row.get('key') or row.get('title')}: a row added by hand, kept")
                continue
            for k, v in rec.items():
                if k in ("key", "title", "item") or _same(v, old.get(k)):
                    continue
                label = f"{tab} · {key or item_id} · {k.replace('_', ' ')} -> {v}"
                if plan_row:
                    qid = "scope:" + rid.split(":", 1)[1]
                    ans = dict(ledger.answer(qid) or {})
                    ans[k] = _iso(v)
                    ledger.set_answer(qid, ans, "human", why)
                elif by_hand:
                    for x in extra:
                        if x.get("key") == rec.get("key") and x.get("title") == rec.get("title"):
                            x[k] = _iso(v)
                elif k in judged:
                    val = PHASE_IN.get(v, v) if k == "phase" else v
                    it = board_items.get(item_id) or {}
                    ledger.set(item_id, judged[k], val, "human", why, fingerprint=B.fingerprint(it) if it else None,
                               key=key, title=rec.get("title"), who=who)
                else:
                    val = FINAL_IN.get(v, v) if k == "final_status" else _iso(v)
                    ledger.set(item_id, f"set:{k}", val, "human", why, key=key, title=rec.get("title"), who=who)
                said.append(label)
    return said


def _file_answer(qid: str, answer: Any, ledger, facts: dict) -> None:
    """An answer on the Open Questions tab goes where that fact lives."""
    iso = _iso(answer)
    if qid.startswith("reason:"):
        per, name = qid[7:].split("|", 1)
        reasons = facts.setdefault("reasons", {})
        reasons.setdefault(per, {})[name] = str(answer).strip()
        reasons.setdefault("_authors", {})[qid[7:]] = "human"
        reasons.setdefault("_questions", {}).pop(qid[7:], None)
        return
    if qid.startswith("judge:"):
        import judge
        item_id, field = qid[6:].rsplit(":", 1)
        allowed = ([p["name"] for p in (facts.get("periods") or {}).get("periods") or []]
                   if field == "period" else judge.FIELDS.get(field))
        if not allowed or answer not in allowed:
            raise ValueError(f"{qid}: choose one of {', '.join(allowed or [])}")
        ledger.set(item_id, field, answer, "human", "Answered the open question")
        ledger.forget(item_id, "deferred:" + field)
        return
    is_date = isinstance(iso, str) and len(iso) == 10 and iso[4] == "-" and iso[7] == "-"
    if qid.startswith("handover:") and is_date:
        for p in (facts.get("periods") or {}).get("periods") or []:
            if p.get("name") == qid.split(":", 1)[1]:
                p["handover_date"] = iso
                return
    if qid.startswith("scope:"):
        ledger.set_answer(qid, {"delivered": iso} if is_date else {"note": str(answer)}, "human",
                          "answered in the sheet")
        return
    ledger.set_answer(qid, iso, "human", "answered in the sheet")
