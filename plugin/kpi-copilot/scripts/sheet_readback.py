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
import re
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
                if spec.get("summary"):
                    rows[f"{per}|{kpi}"]["summary"] = grid(name, r, spec["summary"])
        return {"rows": rows}
    if kind == "questions":
        # Sheets written before the history columns kept About, Question and Asked on in 2, 3 and 6.
        cols = {"about": spec.get("about", 2), "question": spec.get("question", 3), "asked_on": spec.get("asked", 6)}
        return {"rows": {str(grid(name, r, spec["id"])): {"answer": grid(name, r, spec["answer"]),
                                                          **{k: grid(name, r, c) for k, c in cols.items()}}
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


def upgrade_summary(state: dict, results: dict) -> None:
    """Capture edits to column L even when upgrading a workbook that called it automatic."""
    spec = (state.get("spec") or {}).get("KPI Summary") or {}
    if not spec or spec.get("summary"):
        return
    prior = {f"{p['period']}|{m['name']}": m for p in results.get("periods") or [] for m in p.get("measures") or []}
    rows = state["values"]["KPI Summary"]["rows"]
    if any(key not in prior for key in rows):
        raise ValueError("The previous generated notes are needed to preserve edits to the result summary.")
    spec["summary"] = 12
    for key, row in rows.items():
        row["summary"] = prior[key].get("summary_note", " || ".join(x for x in prior[key].get("note_parts") or [] if x))


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


# A Google Sheet read with formatted values hands every number back as text; the facts file
# holds these as numbers, as the extract contract requires.
PERIOD_NUMBERS = {"pms_period_id": int, "team_hours": float}


def _period_value(k: str, v: Any) -> Any:
    kind = PERIOD_NUMBERS.get(k)
    if kind is None:
        return _iso(v)
    if isinstance(v, str):
        text = v.strip().replace(",", "")
        if not text:
            return None
        try:
            v = float(text)
        except ValueError:
            return v
    if isinstance(v, float) and (kind is int or v.is_integer()):
        return int(v) if v.is_integer() else v
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

        if tab == "Dashboard":
            facts["view"] = now["cells"]
            continue

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
                summary_changed = "summary" in rec and not _same(rec.get("summary"), old.get("summary"))
                context_changed = not _same(rec.get("why"), old.get("why"))
                if summary_changed:
                    reasons = facts.setdefault("reasons", {})
                    reasons.setdefault("_summaries", {})[rid] = rec.get("summary") or ""
                    reasons.setdefault("_summary_authors", {})[rid] = "human"
                    reasons.setdefault("_summary_bases", {})[rid] = (state["spec"][tab].get("note_bases") or {}).get(rid)
                    said.append(f"{per} · {kpi}: result summary taken from the sheet")
                if summary_changed or context_changed:
                    basis = (state["spec"][tab].get("note_bases") or {}).get(rid)
                    if basis:
                        facts.setdefault("reasons", {}).setdefault("_human_reviews", {})[rid] = basis
                if context_changed:
                    reasons = facts.setdefault("reasons", {})
                    reasons.setdefault(per, {})[kpi] = rec.get("why") or ""
                    reasons.setdefault("_authors", {})[rid] = "human"
                    reasons.setdefault("_questions", {}).pop(rid, None)
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
                ledger.seen_question(qid, rec.get("about"), rec.get("question"), _iso(rec.get("asked_on")))
                ans = rec.get("answer")
                if ans not in (None, "") and not _same(ans, (before["rows"].get(qid) or {}).get("answer")):
                    applied = _file_answer(qid, ans, ledger, facts)
                    said.append(f"Answered: {qid} -> {ans}" + (f"  (applied: {applied})" if applied else
                                                               "  (for the assistant to apply)"))
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
                if old.get("name") in spec_of(tab).get("historical_periods", []):
                    if set(changed) & {"name", "start", "end"}:
                        raise ValueError("Refresh that historical period before changing its name or date bounds.")
                    facts.setdefault("history_periods", {}).setdefault(old["name"], {}).update(
                        {k: _iso(v) for k, v in changed.items()})
                    said.append(f"Periods · {rec['name']}: archived review edits kept")
                    continue
                target = next((p for p in plist if p.get("name") == rec.get("name")), None)
                if target is None and old.get("name") not in names_now:
                    target = next((p for p in plist if p.get("name") == old.get("name")), None)
                if target is None:
                    target = {k: _period_value(k, v) for k, v in old.items() if v is not None}
                    target["name"] = rec["name"]
                    plist.append(target)
                i = next(j for j, p in enumerate(plist) if p is target)
                for k, v in rec.items():
                    if k in ("key", "title", "item") or _same(v, old.get(k)):
                        continue
                    if k == "name" and plist[i].get("name") and v:
                        plist[i]["old_name"] = plist[i]["name"]
                    plist[i][k] = _period_value(k, v) if k != "name" else v
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
            if rid.startswith("history:"):
                changes = {k: v for k, v in rec.items() if k not in ("key", "title", "item")
                           and not _same(v, (old or {}).get(k))}
                if "period" in changes:
                    raise ValueError("Refresh that historical period to change its row membership.")
                edits = facts.setdefault("history_edits", {}).setdefault(rid, {})
                for k, v in changes.items():
                    field = {"kind": "kind", "remarks": "remarks"}.get(k, k)
                    if k == "planned":
                        v = v == "Yes"
                    elif k == "phase":
                        v = PHASE_IN.get(v, v)
                    elif k == "final_status":
                        v = FINAL_IN.get(v, v)
                    edits[field] = _iso(v)
                if changes:
                    said.append(f"{tab} · {key}: archived review edits kept; refresh its period to recompute the saved result")
                continue
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
                elif "#estimate-" in rid or rid.endswith("#defect"):
                    # Separately estimated deliverables may share a card, not their review edits.
                    val = PHASE_IN.get(v, v) if k == "phase" else FINAL_IN.get(v, v) if k == "final_status" else _iso(v)
                    ledger.set(rid, f"set:{k}", val, "human", why,
                               key=key, title=rec.get("title"), who=who)
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


def _file_answer(qid: str, answer: Any, ledger, facts: dict) -> str | None:
    """An answer on the Open Questions tab goes where that fact lives. Returns what was
    applied, or None when the answer needs somebody to act on it."""
    applied = _apply_answer(qid, answer, ledger, facts)
    if applied:
        ledger.settle(qid, "applied", applied, "tool")
    return applied


def _apply_answer(qid: str, answer: Any, ledger, facts: dict) -> str | None:
    iso = _iso(answer)
    if qid.startswith("reason:"):
        per, name = qid[7:].split("|", 1)
        reasons = facts.setdefault("reasons", {})
        reasons.setdefault(per, {})[name] = str(answer).strip()
        reasons.setdefault("_authors", {})[qid[7:]] = "human"
        reasons.setdefault("_questions", {}).pop(qid[7:], None)
        ledger.set_answer(qid, str(answer).strip(), "human", "answered in the sheet")
        return f"used as the reason for {per} · {name}"
    if qid.startswith("judge:"):
        import judge
        item_id, field = qid[6:].rsplit(":", 1)
        allowed = ([p["name"] for p in (facts.get("periods") or {}).get("periods") or []]
                   if field == "period" else judge.FIELDS.get(field))
        answer = _allowed_answer(answer, allowed, field)
        if answer is None:
            raise ValueError(f"{qid}: choose one of {', '.join(allowed or [])}")
        ledger.set(item_id, field, answer, "human", "Answered the open question")
        ledger.forget(item_id, "deferred:" + field)
        ledger.set_answer(qid, answer, "human", "answered in the sheet")
        return f"{field.replace('_', ' ')} set to {answer}"
    is_date = isinstance(iso, str) and len(iso) == 10 and iso[4] == "-" and iso[7] == "-"
    if qid.startswith("handover:") and not is_date:
        # "Handed over to the client on 09/25" is an answer too. Only one date in the
        # sentence is unambiguous; anything else stays with the assistant.
        found = _dates_in(str(answer))
        if len(found) == 1:
            iso, is_date = found[0], True
    if qid.startswith("handover:") and is_date:
        for p in (facts.get("periods") or {}).get("periods") or []:
            if p.get("name") == qid.split(":", 1)[1]:
                p["handover_date"] = iso
                ledger.set_answer(qid, answer, "human", "answered in the sheet")
                return f"handover date set to {iso[5:7]}/{iso[8:10]}"
    if qid.startswith("scope:"):
        ledger.set_answer(qid, {"delivered": iso} if is_date else {"note": str(answer)}, "human",
                          "answered in the sheet")
        return f"delivered on {iso[5:7]}/{iso[8:10]}" if is_date else None
    ledger.set_answer(qid, iso, "human", "answered in the sheet")
    return None


def _dates_in(text: str, year: int | None = None) -> list[str]:
    """ISO dates written in a sentence: 2026-09-25, 09/25/2026 or 09/25 (this year)."""
    year = year or dt.date.today().year
    out = []
    for m in re.finditer(r"\b(\d{4})-(\d{2})-(\d{2})\b|\b(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b", text or ""):
        try:
            if m.group(1):
                d = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            else:
                d = dt.date(int(m.group(6) or year), int(m.group(4)), int(m.group(5)))
        except ValueError:
            continue
        if d.isoformat() not in out:
            out.append(d.isoformat())
    return out


def _allowed_answer(answer: Any, allowed: list[str] | None, field: str) -> str | None:
    """Accept an unambiguous human sentence as well as a dropdown's exact value.

    Open Questions is intentionally a prose-friendly surface. Requiring somebody to replace
    "count this as understood" with the literal word ``Yes`` loses a valid decision and can
    stop every later sheet edit from being read. Keep this deliberately narrow: only exact
    choices, or the two plain-English forms of the understood judgement, are normalised.
    """
    if not allowed:
        return None
    raw = str(answer).strip()
    exact = {str(value).casefold(): str(value) for value in allowed}
    if raw.casefold() in exact:
        return exact[raw.casefold()]
    if field == "understood" and {value.casefold() for value in allowed} == {"yes", "no"}:
        words = " ".join(raw.casefold().replace("'", "").split())
        if "not understood" in words or "count" in words and "as misunderstood" in words:
            return exact["no"]
        if "count" in words and "understood" in words:
            return exact["yes"]
    return None
