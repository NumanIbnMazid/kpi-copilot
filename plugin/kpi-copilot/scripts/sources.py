#!/usr/bin/env python3
"""
The sources a run may read - those, and no others.

A profile names where scope, hours and dates come from: the plan, the estimates, a timeline
or project tracker. That list is an allowlist. A run reads exactly what is on it; whatever
those cannot answer becomes a question to a person, not a search through chat and mail.
Reaching further is always possible, but it is asked for - `--deep`, or a source the lead
adds - never something a run decides for itself. That is the difference between a run that
ends and one that wanders.

Two more things make this fast:

  * A source is fetched straight to disk, and only when it has changed. Drive says when a
    file was last modified; if that has not moved since the cached copy, nothing is
    downloaded. The plan PDF is read once in the life of a project.

  * Nobody re-reads a document to extract the same facts. A tabular source (an estimates
    sheet, a timeline) is read through a column mapping written once at setup. Anything else
    (a PDF plan) is digested once by the assistant into facts/*.yaml, and the digest records
    the fingerprint of what it read - so the run can say "the plan changed since this was
    written" instead of silently trusting a stale copy.

    sources:
      plan:      {kind: pdf,   ref: <Drive link | id | local path>}
      estimates: {kind: sheet, ref: ..., map: {tab: ..., columns: {title: "Item", dev_hours: "Dev (h)"}}}
      timeline:  {kind: sheet, ref: ..., map: {events: {...}, log: {...}}}

No Google sign-in? Drop an export in <project>/inbox/<role>.<ext> and it is picked up.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Any

import board as B
import google_api as G

ROLES = ("plan", "estimates", "timeline")


def declared(profile: dict, project: dict | None = None) -> list[dict]:
    """The sources this project may read. A project can name its own plan and estimates
    (`plan_ref`, `estimates_ref`) without repeating the whole sources block."""
    src = profile.get("sources") or {}
    out = []
    for role in ROLES:
        cfg = dict(src.get(role) or {})
        own = (project or {}).get(f"{role}_ref")
        if own:
            cfg["ref"] = own
            cfg.setdefault("kind", "pdf" if role == "plan" else "sheet")
        if cfg.get("ref") and cfg.get("kind") not in (None, "none"):
            out.append({"role": role, **cfg})
    return out


def _sha(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()[:16]


def _meta_path(cache: Path, role: str) -> Path:
    return cache / f"{role}.meta.json"


def _read_meta(cache: Path, role: str) -> dict:
    p = _meta_path(cache, role)
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}


def pull(profile: dict, project_dir: Path, base_dir: Path, offline: bool = False,
         project: dict | None = None) -> list[dict]:
    """Bring every declared source up to date on disk. Returns one status per source:
    {role, state: fresh|unchanged|cached|missing, path, fingerprint, note}."""
    cache, inbox = project_dir / "cache" / "sources", project_dir / "inbox"
    cache.mkdir(parents=True, exist_ok=True)
    session: G.Session | None = None
    out = []
    for s in declared(profile, project):
        role, ref = s["role"], str(s["ref"])
        meta = _read_meta(cache, role)
        if meta.get("ref") != ref:
            meta = {}  # a different plan is not an offline copy of the current source
        st: dict[str, Any] = {"role": role, "kind": s.get("kind"), "ref": ref, "state": "missing",
                              "path": meta.get("path"), "fingerprint": meta.get("fingerprint"), "note": ""}

        dropped = sorted(inbox.glob(f"{role}.*")) if inbox.exists() else []
        local = next((p for p in (Path(ref).expanduser(), base_dir / ref) if p.is_file()), None)
        if dropped:
            dest = cache / f"{role}{dropped[0].suffix.lower()}"
            shutil.move(str(dropped[0]), dest)
            st.update(state="fresh", path=str(dest), fingerprint=_sha(dest), note="taken from the inbox")
        elif local:
            fp = _sha(local)
            st.update(state="unchanged" if fp == meta.get("fingerprint") else "fresh", path=str(local), fingerprint=fp)
        elif G.looks_like_drive(ref) and not offline and G.how_signed_in():
            try:
                session = session or G.Session()
                info = G.drive_meta(session, G.file_id(ref) or ref)
                fp = f"{info.get('modifiedTime')}"
                if fp == meta.get("fingerprint") and meta.get("path") and Path(meta["path"]).exists():
                    st.update(state="unchanged", note=f"not modified since {fp[:10]}")
                else:
                    dest = G.drive_fetch(session, info["id"], info.get("mimeType") or "", cache / role)
                    st.update(state="fresh", path=str(dest), fingerprint=fp, note=info.get("name") or "")
                st["url"] = info.get("webViewLink")
            except G.GoogleError as e:
                st.update(state="cached" if meta.get("path") else "missing", note=str(e))
        elif meta.get("path") and Path(meta["path"]).exists():
            st.update(state="cached", note="using the copy already on disk; could not check for a newer one")
        else:
            st["note"] = (f"cannot read it from here. Save an export as {inbox}/{role}.xlsx (or .csv, .pdf) "
                          f"and it will be picked up" + ("" if G.how_signed_in() or not G.looks_like_drive(ref)
                                                         else ", or connect Google once: kpi.py auth google"))
        if st["path"] and st["state"] in ("fresh", "unchanged"):
            _meta_path(cache, role).write_text(json.dumps(
                {"path": st["path"], "fingerprint": st["fingerprint"], "pulled_at": B.now_iso(),
                 "ref": ref, "url": st.get("url")}, indent=1), encoding="utf-8")
        out.append(st)
    return out


# --------------------------------------------------------------------------------------
# reading tables through a mapping
# --------------------------------------------------------------------------------------

def _cell(v: Any) -> Any:
    if isinstance(v, (datetime, date)):
        return v.isoformat()[:10]
    if isinstance(v, float) and v.is_integer():
        return int(v)  # Sheet exports often store identifier 10 as 10.0.
    if isinstance(v, str):
        return v.strip()
    return v


def read_tables(path: Path) -> dict[str, list[list[Any]]]:
    """Every tab as rows of plain values. xlsx and csv; anything else has no tables."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as f:
            return {path.stem: [[_cell(c) for c in row] for row in csv.reader(f)]}
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook
        wb = load_workbook(path, data_only=True, read_only=True)
        return {ws.title: [[_cell(c) for c in row] for row in ws.iter_rows(values_only=True)]
                for ws in wb.worksheets}
    return {}


def _find_header(rows: list[list[Any]], wanted: list[str]) -> tuple[int, dict[str, int]] | None:
    want = {B.norm(w): w for w in wanted if w}
    for r, row in enumerate(rows[:40]):
        seen = {B.norm(str(c)): i for i, c in enumerate(row) if c not in (None, "")}
        # A header the mapping names may carry a suffix in the sheet: "Actual" vs "Actual (auto)".
        hits = {}
        for nw, original in want.items():
            idx = seen.get(nw)
            if idx is None:
                idx = next((i for k, i in seen.items() if k.startswith(nw) or nw.startswith(k) and len(k) >= 4), None)
            if idx is not None:
                hits[original] = idx
        if len(hits) >= max(2, (len(want) + 1) // 2):
            return r, hits
    return None


def table(path: Path, spec: dict) -> tuple[list[dict], str]:
    """Rows of {field: value} from one mapped table. Returns (rows, problem)."""
    cols: dict[str, str] = spec.get("columns") or {}
    if not cols:
        return [], "the mapping names no columns"
    rule_fields = set(spec.get("where") or {}) | set(spec.get("values") or {})
    for override in spec.get("overrides") or []:
        if not override.get("match") or not override.get("why"):
            return [], "a row override needs match fields and a reason"
        rule_fields |= set(override["match"])
    for field in rule_fields:
        if field not in cols:
            return [], f"mapping rule for '{field}' needs a column mapping first"
    tabs = read_tables(path)
    if not tabs:
        return [], f"{Path(path).name} is not a spreadsheet, so it has no tables to map"
    if spec.get("tab") and spec["tab"] not in tabs:
        return [], f"mapped tab '{spec['tab']}' is missing; correct the mapping instead of reading another tab"
    names = [spec["tab"]] if spec.get("tab") else list(tabs)
    for name in names:
        found = _find_header(tabs[name], list(cols.values()))
        if not found:
            continue
        hrow, idx = found
        missing = [h for h in cols.values() if h not in idx]
        if missing:
            return [], f"column(s) not found in '{name}': {', '.join(missing)}"
        out = []
        for row in tabs[name][hrow + 1:]:
            rec = {f: (row[idx[h]] if h in idx and idx[h] < len(row) else None) for f, h in cols.items()}
            if not any(v not in (None, "") for v in rec.values()):
                continue
            for override in spec.get("overrides") or []:
                if all(B.norm(str(rec.get(field) if rec.get(field) is not None else "")) == B.norm(str(value))
                       for field, value in override["match"].items()):
                    rec.update(override.get("set") or {})
                    rec["mapping_reason"] = override["why"]
            if any(B.norm(str(rec.get(field) if rec.get(field) is not None else "")) not in
                   {B.norm(str(v)) for v in (allowed if isinstance(allowed, list) else [allowed])}
                   for field, allowed in (spec.get("where") or {}).items()):
                continue
            for field, choices in (spec.get("values") or {}).items():
                lookup = {B.norm(str(k)): v for k, v in choices.items()}
                key = B.norm(str(rec.get(field) if rec.get(field) is not None else ""))
                if key not in lookup:
                    return [], f"'{name}' has an unmapped value for '{field}'; add it to map.values before running"
                rec[field] = lookup[key]
            out.append(rec)
        return out, ""
    return [], f"no tab has the headers {', '.join(list(cols.values())[:4])}..."


def _truthy(v: Any) -> bool:
    return str(v).strip().lower() in ("true", "yes", "y", "1", "x", "✓")


def _iso(v: Any) -> str | None:
    """Sheets that keep dates as text write them mm/dd/yyyy; everything downstream is ISO."""
    if v in (None, ""):
        return None
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y", "%m/%d/%y", "%Y/%m/%d", "%d %b %Y"):
        try:
            return datetime.strptime(s[:11].strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def facts_from_mapping(status: dict, cfg: dict, facts: dict) -> list[str]:
    """Rebuild whatever facts a mapped, tabular source can supply. Returns what it did, in
    words. Hand-written values are never overwritten: a mapped value fills a blank, or
    replaces a value this same mapping wrote earlier."""
    role, path, mp = status["role"], status.get("path"), cfg.get("map") or {}
    if not path or not mp:
        return []
    said: list[str] = []
    stamp = {"id": role, "fingerprint": status.get("fingerprint"), "as_of": B.now_iso()[:10]}

    if role in ("plan", "estimates") and mp.get("columns"):
        rows, problem = table(Path(path), mp)
        if problem:
            status["problem"] = problem
            return [f"{role}: {problem}. Previous mapped facts are withheld from this run."]
        items = []
        for r in rows:
            if not r.get("title") and not r.get("board_key"):
                continue
            it = {k: v for k, v in r.items() if v not in (None, "")}
            for d in ("approved_on", "commit_date", "client_date", "delivered"):
                if d in it:
                    it[d] = _iso(it[d])
            items.append(it)
        kept = {k: v for k, v in (facts.get(role) or {}).items() if k not in ("items", "source")}
        facts[role] = {"source": stamp, **kept, "items": items}
        said.append(f"{role}: {len(items)} rows read through the column mapping")
        if problem:
            said.append(f"{role}: {problem}")

    if role == "timeline":
        per = facts.setdefault("periods", {})
        if mp.get("events"):
            rows, problem = table(Path(path), mp["events"])
            if problem:
                status["problem"] = problem
                return [f"timeline: {problem}"]
            types = [B.norm(t) for t in (mp["events"].get("handover_types") or ["Handover", "Delivery", "Release"])]
            done = [B.norm(t) for t in (mp["events"].get("done_states") or ["Done", "Complete", "Completed"])]
            for p in per.get("periods") or []:
                mine = [r for r in rows if B.norm(str(r.get("period") or "")) == B.norm(p.get("name") or "")
                        and any(t in B.norm(str(r.get("type") or "")) for t in types)]
                got = [(_iso(r.get("actual")), r) for r in mine
                       if _iso(r.get("actual")) and (not r.get("state") or B.norm(str(r["state"])) in done)]
                planned = [_iso(r.get("baseline")) for r in mine if _iso(r.get("baseline"))]
                auto = p.setdefault("_from_timeline", {})
                if got and (not p.get("handover_date") or auto.get("handover_date") == p.get("handover_date")):
                    newest = max(got, key=lambda x: x[0])[0]
                    if newest != p.get("handover_date"):
                        said.append(f"{p['name']}: handover {newest} read from the timeline")
                    p["handover_date"] = auto["handover_date"] = newest
                elif not got and auto.get("handover_date") == p.get("handover_date"):
                    p.pop("handover_date", None)
                    auto.pop("handover_date", None)
                if planned and not p.get("plan_client_date"):
                    p["plan_client_date"] = p["plan_commit_date"] = max(planned)
            if problem:
                said.append(f"timeline events: {problem}")
        if mp.get("log"):
            rows, problem = table(Path(path), mp["log"])
            if problem:
                status["problem"] = problem
                return [f"timeline log: {problem}. Previous context is withheld from this run."]
            only = mp["log"].get("only_flagged", True)
            log = [{"date": _iso(r.get("date")) or r.get("date"), "type": r.get("type"), "period": r.get("period") or "",
                    "what": str(r.get("what") or "")[:400], "why": str(r.get("why") or "")[:300]}
                   for r in rows if (not only or "kpi" not in r or _truthy(r.get("kpi")))]
            per["log"] = log[:80]
            said.append(f"timeline log: {len(per['log'])} entries kept as context for the notes")
            if problem:
                said.append(f"timeline log: {problem}")
        per["timeline_source"] = stamp
    return said


def staleness(statuses: list[dict], facts: dict) -> list[str]:
    """A digest that was written from an older version of its source. Said out loud, because
    a stale plan is a wrong denominator that looks exactly like a right one."""
    out = []
    for st in statuses:
        role = st["role"]
        if role not in ("plan", "estimates") or not st.get("fingerprint"):
            continue
        f = facts.get(role) or {}
        if not f.get("items"):
            where = st.get("path") or st.get("ref")
            out.append(f"facts/{role}.yaml is empty, and the {role} is at {where}. Read it once and write "
                       f"its items there (shape: references/facts.md)" if st.get("path") else
                       f"facts/{role}.yaml is empty and the {role} could not be read: {st.get('note')}")
        elif (f.get("source") or {}).get("fingerprint") != st["fingerprint"]:
            out.append(f"The {role} changed after facts/{role}.yaml was written "
                       f"({(f.get('source') or {}).get('as_of')}). Re-read {st.get('path')} and update it, then set "
                       f"source.fingerprint to {st['fingerprint']}")
    return out


def usable_facts(statuses: list[dict], facts: dict) -> tuple[dict, list[str]]:
    """Retain stored evidence for repair, but do not calculate from a stale digest."""
    import copy
    active, blocked = copy.deepcopy(facts), []
    for st in statuses:
        role = st["role"]
        fact = facts.get(role) or {}
        problem = st.get("problem")
        if st["state"] == "missing":
            problem = st.get("note") or "source is unavailable"
        if role in ("plan", "estimates") and st.get("path"):
            if (fact.get("source") or {}).get("fingerprint") != st.get("fingerprint"):
                problem = f"digest needs updating from {st['path']}; source.fingerprint must be {st.get('fingerprint')}"
        if problem:
            blocked.append(f"{role}: {problem}")
            if role in ("plan", "estimates"):
                active[role] = {}
            elif role == "timeline":
                active.setdefault("periods", {}).pop("log", None)
                for period in (active.get("periods") or {}).get("periods") or []:
                    for key, value in (period.get("_from_timeline") or {}).items():
                        if period.get(key) == value:
                            period.pop(key, None)
        elif st["state"] == "cached":
            blocked.append(f"{role}: freshness could not be checked; reconnect and rerun before sending to PMS")
    return active, blocked
