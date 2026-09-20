#!/usr/bin/env python3
"""
Keep the KPI definitions in step with PMS.

The nine KPIs, their ids, their thresholds and their official wording belong to PMS, not to
us. Copying them into our code would mean that the day somebody changes a threshold in PMS,
every project lead quietly keeps scoring against the old one and nobody finds out until a
review meeting.

So: read them from PMS, cache the answer, and stamp it with a date. The engine prints the
cache's age, and preflight flags a stale one.

This never writes to PMS.

Usage:
    python3 kpi_registry.py --refresh --profile profile.yaml       # pull from PMS
    python3 kpi_registry.py --refresh --from-json pms_dump.json    # from a saved response
    python3 kpi_registry.py --show                                 # what we have now
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SCHEMAS = HERE.parent / "schemas"
DEFAULT = SCHEMAS / "kpi_registry.default.json"
CACHE = SCHEMAS / "kpi_registry.json"


def resolve_path(profile_path: Path | None, profile: dict, explicit: Path | None = None) -> Path:
    """Resolve once, relative to the profile rather than the assistant's working folder."""
    if explicit:
        return explicit
    configured = (profile.get("organization") or {}).get("kpi_registry")
    base = profile_path.resolve().parent if profile_path else Path.cwd()
    candidate = base / (configured or "kpi_registry.json")
    if candidate.is_file():
        return candidate
    if configured and configured != "kpi_registry.json":
        raise SystemExit(f"KPI registry not found: {candidate}. Refresh it or correct organization.kpi_registry.")
    # A shared installed-plugin cache may belong to another company. Never adopt it.
    return DEFAULT

# How a PMS KPI name maps onto the keys the engine uses. Names are what PMS shows a human;
# keys are what our code says. Matching on the name keeps working if PMS renumbers.
NAME_TO_KEY = {
    "velocity": "velocity",
    "task comprehension": "task_comprehension",
    "client expectation": "client_expectation",
    "delivery commitment": "delivery_commitment",
    "defect rate": "defect_rate",
    "escaped defect rate": "escaped_defect_rate",
    "rejection rate": "rejection_rate",
    "defect rejection rate": "rejection_rate",
    "rework rate": "rework_rate",
    "cr rate": "cr_rate",
    "change request rate": "cr_rate",
}


def _load(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        import yaml  # type: ignore
        return yaml.safe_load(text)
    return json.loads(text)


def fetch_project(base_url: str, project_id: int, token: str | None) -> list[dict]:
    """A project's own KPI settings. PMS lets a threshold be set per project, so this is where
    a real target comes from - the company-wide list is only the fallback."""
    url = base_url.rstrip("/") + f"/api/projects/{project_id}/kpis?includePeriods=false"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = json.loads(r.read().decode("utf-8"))
    return raw if isinstance(raw, list) else (raw.get("kpis") or raw.get("data") or [])


def project_thresholds(rows: list[dict]) -> tuple[dict, list[str]]:
    """Pull {kpi_key: {threshold, direction}} out of a project's KPI rows. Only a setting that
    is actually present is recorded; a project that inherits the default records nothing, so
    the engine can tell "this project chose 25" from "nobody set one"."""
    out, unknown = {}, []
    for row in rows:
        name = str(row.get("name") or row.get("kpiName") or "").strip()
        key = NAME_TO_KEY.get(name.lower())
        if not key:
            if name:
                unknown.append(name)
            continue
        threshold = next((row[k] for k in ("threshold", "minValue", "maxValue") if row.get(k) is not None), None)
        if threshold is None:
            continue
        entry = {"threshold": threshold}
        if row.get("maxValue") is not None and row.get("minValue") is None:
            entry["direction"] = "lower-is-better"
        elif row.get("minValue") is not None:
            entry["direction"] = "higher-is-better"
        out[key] = entry
    return out, unknown


def fetch(base_url: str, token: str | None) -> Any:
    """Read the KPI master list from PMS. A token is optional: in most setups the browser
    session is what has access, and the run reads the page instead. This path exists for
    machines that do hold a service token."""
    url = base_url.rstrip("/") + "/api/kpis"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def merge(pms_rows: list[dict], fallback: dict) -> dict:
    """PMS owns the ids, names, thresholds and descriptions. We own the headings and the
    counting basis, because those are wording choices, not company definitions. Merging keeps
    both without either overwriting the other."""
    by_key = {k["key"]: dict(k) for k in fallback.get("kpis", [])}
    out, unknown = [], []

    for row in pms_rows:
        name = str(row.get("name") or row.get("kpiName") or "").strip()
        key = NAME_TO_KEY.get(name.lower())
        if not key:
            unknown.append(name)
            continue
        base = by_key.get(key, {"key": key, "heading": name, "basis": "", "requires": []})
        threshold = next((row[k] for k in ("threshold", "minValue", "maxValue") if row.get(k) is not None), None)
        base.update({
            "name": name,
            "pms_id": row.get("id", row.get("kpiId", base.get("pms_id"))),
            "threshold": threshold if threshold is not None else base.get("threshold"),
            "description_pms": row.get("description") or base.get("description_pms", ""),
        })
        if row.get("maxValue") is not None and row.get("minValue") is None:
            base["direction"] = "lower-is-better"
        elif row.get("minValue") is not None:
            base["direction"] = "higher-is-better"
        rng = row.get("range") or ([0, 1000] if key == "velocity" else [0, 100])
        base["range"] = rng
        out.append(base)
        by_key.pop(key, None)

    # A KPI PMS no longer returns is kept, flagged, not silently dropped - dropping one would
    # make a project's KPI set change shape without anyone deciding that.
    for key, leftover in by_key.items():
        leftover["status"] = "not returned by PMS on the last refresh"
        out.append(leftover)

    return {
        "registry_version": "1.0",
        "source": "pms",
        "synced_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "unknown_from_pms": unknown,
        "value_range": fallback.get("value_range"),
        "note": "Synced from PMS. Headings and counting basis are ours; ids, names, thresholds and "
                "descriptions are whatever PMS returned.",
        "kpis": out,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Sync KPI definitions from PMS.")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--profile", type=Path)
    ap.add_argument("--from-json", type=Path, help="A saved PMS response, for when the API is not reachable from here.")
    ap.add_argument("--project", type=int, action="append", default=[],
                    help="A PMS project id whose own thresholds to read. Repeatable. Omitted: every "
                         "pms_project_id in the profile.")
    ap.add_argument("--project-from-json", type=Path,
                    help="A saved /api/projects/<id>/kpis response; use with a single --project.")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)

    profile = _load(a.profile) if a.profile else {}
    a.out = a.out or ((a.profile.resolve().parent / ((profile.get("organization") or {}).get("kpi_registry")
                                                  or "kpi_registry.json")) if a.profile else CACHE)

    fallback = _load(DEFAULT)

    if a.show or not a.refresh:
        current = _load(a.out) if a.out.exists() else fallback
        age = current.get("synced_at") or "never"
        print(f"Source: {current.get('source')}   Synced: {age}")
        print(f"{'KPI':<24}{'id':>4}  {'target':<10}{'range':<12}")
        for k in current.get("kpis", []):
            tgt = ("min " if k.get("direction") == "higher-is-better" else "max ") + str(k.get("threshold"))
            print(f"{k.get('name', ''):<24}{str(k.get('pms_id', '')):>4}  {tgt:<10}{str(k.get('range', '')):<12}"
                  + ("  " + k["status"] if k.get("status") else ""))
        if current.get("source") == "bundled-fallback":
            print("\nThis is the bundled fallback from September 2026, not PMS. Refresh before a run that matters.")
        return 0

    rows: list[dict] = []
    if a.from_json:
        raw = _load(a.from_json)
        rows = raw if isinstance(raw, list) else (raw.get("data") or raw.get("kpis") or [])
    else:
        if not a.profile:
            print("Need --profile (for the PMS URL) or --from-json.", file=sys.stderr)
            return 2
        profile = _load(a.profile)
        base = (profile.get("organization") or {}).get("pms_base_url")
        token = os.environ.get("PMS_TOKEN")
        try:
            raw = fetch(base, token)
            rows = raw if isinstance(raw, list) else (raw.get("data") or raw.get("kpis") or [])
        except urllib.error.HTTPError as e:
            print(f"PMS answered {e.code}. If it is 401 or 403, this machine has no PMS token: open the KPI "
                  f"page in the signed-in browser instead and save the response with --from-json.", file=sys.stderr)
            return 3
        except Exception as e:  # noqa: BLE001
            print(f"Could not reach PMS ({type(e).__name__}: {e}). The bundled fallback still works, but say so "
                  f"when reporting the numbers.", file=sys.stderr)
            return 3

    if not rows:
        print("PMS returned no KPI rows. Leaving the current registry alone.", file=sys.stderr)
        return 3

    reg = merge(rows, fallback)

    # Per-project thresholds. PMS lets a project set its own targets, so the company list is
    # only a fallback and a run scored against it may be scored against the wrong bar.
    profile = _load(a.profile) if a.profile else {}
    wanted = a.project or [
        p["pms_project_id"] for p in (profile.get("projects") or []) if p.get("pms_project_id")
    ]
    base = (profile.get("organization") or {}).get("pms_base_url", "")
    token = os.environ.get("PMS_TOKEN")
    reg["projects"] = {}
    for pid in wanted:
        try:
            if a.project_from_json:
                prows = _load(a.project_from_json)
                prows = prows if isinstance(prows, list) else (prows.get("kpis") or prows.get("data") or [])
            else:
                prows = fetch_project(base, pid, token)
        except Exception as e:  # noqa: BLE001
            print(f"Could not read project {pid}'s own thresholds ({type(e).__name__}). It will be scored "
                  f"against the PMS defaults, and every run says so.", file=sys.stderr)
            continue
        own, _ = project_thresholds(prows)
        if own:
            reg["projects"][str(pid)] = own
            bits = ", ".join(f"{k} {v['threshold']}" for k, v in sorted(own.items()))
            print(f"Project {pid} sets its own targets: {bits}")
        else:
            print(f"Project {pid} uses the PMS defaults for every KPI.")

    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(reg, indent=2), encoding="utf-8")
    print(f"Wrote {a.out}: {len(reg['kpis'])} KPIs, {len(reg['projects'])} project(s) with their own "
          f"targets, synced {reg['synced_at']}.")
    if reg["unknown_from_pms"]:
        print(f"PMS returned KPIs we have no mapping for: {', '.join(reg['unknown_from_pms'])}. "
              f"Add them to NAME_TO_KEY and teach the engine how to count them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
