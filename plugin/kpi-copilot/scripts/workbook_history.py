"""Retain completed period inputs and results independently of a run's tracker window.

A project owns one workbook. Runs own their own payloads (including PMS scope). Updating
one period replaces it by date bounds, while the workbook retains all other periods.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path


def period_key(period: dict) -> str:
    if period.get("start") and period.get("end"):
        return str(period["start"]) + "/" + str(period["end"])
    return "name:" + period["name"]


def row_id(key, role, row, index):
    identity = row.get("_row") or row.get("_item") or row.get("key") or str(index)
    token = hashlib.sha256((key + "|" + role + "|" + str(identity)).encode()).hexdigest()[:24]
    return "history:" + token


def apply_edits(kif, facts, profile=None, as_of=None):
    """Historical human corrections remain authoritative when that period is refreshed."""
    keys = {p["name"]: period_key(p) for p in kif.get("periods", [])}
    for p in kif.get("periods", []):
        p.update((facts.get("history_periods") or {}).get(p["name"], {}))
    for role in ("tasks", "defects"):
        counters = {}
        for row in kif.get(role, []):
            name = row.get("period")
            if name not in keys:
                continue
            index = counters.get(name, 0)
            counters[name] = index + 1
            edits = (facts.get("history_edits") or {}).get(row_id(keys[name], role, row, index), {})
            scoped_out = row.get("exclude_reason") in (
                "assignee is outside the configured project team",
                "no tracker assignee to establish project-team scope")
            row.update(edits)
            if scoped_out:
                row.update(type="Excluded", planned=False)
            period_edits = (facts.get("history_periods") or {}).get(name, {})
            dates = {"delivered", "client_date", "commit_date", "client_expected", "team_committed"}
            if role == "tasks" and as_of and (dates.intersection(edits) or period_edits):
                from classify import on_time, _later
                period = next(p for p in kif["periods"] if p["name"] == name)
                project = kif.get("project", {})
                for field in ("client_date", "commit_date"):
                    if field in period_edits and field not in edits:
                        row[field] = period_edits[field]
                if edits.get("client_expected") == "No":
                    row["client_date"] = None
                if edits.get("team_committed") == "No":
                    row["commit_date"] = None
                dl, ho = row.get("delivered"), period.get("handover_date")
                check = period.get("client_check") or project.get("client_check") or "Handover"
                by_handover = "handover" in str(((profile or {}).get("workflow", {}).get("commitment") or {})
                                                .get("met_when") or "").lower()
                row["met_client_date"] = on_time(dl if check == "Delivery" else _later(dl, ho),
                                                  row.get("client_date"), as_of)
                row["met_commitment"] = on_time(_later(dl, ho) if by_handover else dl,
                                                row.get("commit_date"), as_of)


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1, default=str)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def upsert(history: dict, kif: dict, results: dict, ctx: dict) -> None:
    entries = history.setdefault("periods", {})
    measured = {p["period"]: p for p in results.get("periods", [])}
    names = [p["name"] for p in kif.get("periods", [])]
    keys = [period_key(p) for p in kif.get("periods", [])]
    if len(keys) != len(set(keys)) or len(names) != len(set(names)):
        raise ValueError("A run must have unique period names and date bounds.")
    for p in kif.get("periods", []):
        name = p["name"]
        if name not in measured:
            raise ValueError(f"Period {name} has no computed results; history was not replaced.")
        entry = {"period": p, "result": measured[name], "project": kif.get("project", {}),
                 "generated": kif.get("generated", {}), "as_of": ctx.get("as_of"),
                 "tasks": [t for t in kif.get("tasks", []) if t.get("period") == name],
                 "defects": [d for d in kif.get("defects", []) if d.get("period") == name],
                 "reasons": (ctx.get("reasons") or {}).get(name, {}),
                 "manual": (ctx.get("manual") or {}).get(name, {}),
                 "questions": [q for q in ctx.get("questions", []) if q.get("about") == name]}
        entries[period_key(p)] = copy.deepcopy(entry)


def load(project_dir: Path) -> dict:
    path = project_dir / "workbook_history.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    history = {"version": 1, "periods": {}}
    # Upgrade existing installations using their saved engine inputs, never by guessing
    # what a partially scoped tracker query used to contain. Newest computation wins.
    for p in sorted((project_dir / "runs").glob("*/results.json"), key=lambda x: x.stat().st_mtime_ns):
        source = p.with_name("run.kif.json")
        if not source.exists():
            continue
        import yaml
        reasons_path = p.with_name("reasons.used.yaml")
        reasons = yaml.safe_load(reasons_path.read_text()) if reasons_path.exists() else {}
        kif = json.loads(source.read_text())
        upsert(history, kif, json.loads(p.read_text()), {"reasons": reasons or {},
               "as_of": (kif.get("generated", {}).get("at") or "")[:10]})
    return history


def combine(history: dict, kif: dict, results: dict, ctx: dict) -> tuple[dict, dict, dict]:
    out, res, context = copy.deepcopy(kif), copy.deepcopy(results), copy.deepcopy(ctx)
    active = {period_key(p) for p in kif.get("periods", [])}
    out.update(periods=[], tasks=[], defects=[])
    res["periods"] = []
    questions = {q["id"]: q for q in context.get("questions", [])}
    entries = sorted(history.get("periods", {}).items(), key=lambda kv: (
        str(kv[1]["period"].get("start") or ""), str(kv[1]["period"].get("end") or ""), kv[0]))
    names = [e["period"]["name"] for _, e in entries]
    if len(names) != len(set(names)):
        raise ValueError("Period names repeat across years. Add the year so each period has a unique label.")
    context["period_as_of"] = {}
    context["historical_periods"] = []
    for key, original in entries:
        e = copy.deepcopy(original)
        name = e["period"]["name"]
        if key not in active:
            context["historical_periods"].append(name)
            e["period"].update((context.get("history_periods") or {}).get(name, {}))
        out["periods"].append(e["period"])
        res["periods"].append(e["result"])
        context["period_as_of"][name] = e.get("as_of") or "Saved run"
        for role in ("tasks", "defects"):
            for i, row in enumerate(e[role]):
                if key not in active:
                    # A card can occur in several reporting windows. Archive edits must
                    # never overwrite the active card's ledger entry.
                    row["_row"] = row_id(key, role, row, i)
                    edits = (context.get("history_edits") or {}).get(row["_row"], {})
                    row.update(edits)
                out[role].append(row)
        for field in ("reasons", "manual"):
            context.setdefault(field, {}).setdefault(name, e.get(field) or {})
        for q in e.get("questions", []):
            questions.setdefault(q["id"], q)
    context["questions"] = list(questions.values())
    return out, res, context
