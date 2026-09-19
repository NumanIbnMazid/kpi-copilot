#!/usr/bin/env python3
"""
Asana, the legacy converter.

Converts the output of an in-browser extractor (the `window.__kpi` shape) into KIF. It is
kept for anybody who still has such a file. It is not how Asana is read any more.

That route had no reader of its own, so in practice an assistant scraped the board, judged
every card by hand and carried the result back through a chat window - on every run. It was
slow, and two runs of the same board could disagree. `api.py` beside this file reads the
board through the API in seconds and makes no judgements; `scripts/classify.py` then judges
every tracker's cards the same way. `scripts/kpi.py run` uses those.

Usage:
    python3 extract.py --profile profile.yaml --from-extract kpi.json --out run.kif.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
from profile_lib import load as load_profile, resolve as resolve_profile  # noqa: E402

ADAPTER = "asana"
VERSION = "1.0.0"

HERE = Path(__file__).resolve().parent

YESNO = {"Yes": "Yes", "No": "No", "Pending": "Pending", "": None, None: None}
FINAL_STATUS = {
    "Fixed / Closed": "Fixed", "Fixed": "Fixed", "Closed": "Closed",
    "Rejected": "Rejected", "Deferred": "Deferred", "Open": "Open",
}


def _load(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        import yaml  # type: ignore
        return yaml.safe_load(text)
    return json.loads(text)


def _f(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "", "-") else None
    except (TypeError, ValueError):
        return None


def _s(value: Any) -> str | None:
    v = str(value).strip() if value is not None else ""
    return v or None


def convert(extract: dict, profile: dict, project_cfg: dict) -> dict:
    """Turn the browser extractor's output into KIF. A straight rename in most places; the
    interesting parts are the three-way Yes/No/Pending fields and the phase mapping, where
    the legacy names and the KIF names differ."""
    pd = extract.get("projectDates") or {}
    periods = []
    for p in extract.get("periodRows") or []:
        periods.append({
            "name": (p.get("name") or "")[:25],
            "old_name": _s(p.get("oldName")),
            "pms_period_id": int(p["pmsId"]) if str(p.get("pmsId") or "").isdigit() else None,
            "start": _s(p.get("start")), "end": _s(p.get("end")),
            "client_date": _s(p.get("clientDate")), "commit_date": _s(p.get("commitDate")),
            "client_check": _s(p.get("clientCheck")),
            # 'releaseDate' in the legacy shape is the handover build. Blank means not handed
            # over yet, and the engine turns that into an honest "nothing to measure".
            "handover_date": _s(p.get("releaseDate")),
            "team_hours": _f(p.get("teamHours")),
            "plan_client_date": _s(p.get("planClientDate")),
            "plan_commit_date": _s(p.get("planCommitDate")),
            "notes": p.get("notes") or "", "plan_text": p.get("planText") or "",
        })
    if not periods:
        periods = [{"name": "Full Project"}]

    tasks = []
    for t in extract.get("taskRows") or []:
        ttype = t.get("type") or "Task"
        tasks.append({
            "period": t.get("period") or periods[0]["name"],
            "key": t.get("key") or "", "link": _s(t.get("link")),
            "title": t.get("title") or "", "type": ttype,
            "exclude_reason": _s(t.get("remark")) if ttype == "Excluded" else None,
            "planned": (t.get("initial") == "Yes") if ttype != "Excluded" else None,
            # 'dev' is the hours the legacy pipeline settled on; 'est' is the raw estimate.
            "hours_dev": _f(t.get("dev")) if t.get("dev") not in (None, "") else _f(t.get("est")),
            "hours_qa": _f(t.get("qaC")) if t.get("qaC") not in (None, "") else _f(t.get("qa")),
            "hours_source": _s(t.get("src")),
            "story_points": _f(t.get("sp")),
            "assignee": _s(t.get("assignee")),
            "created": _s(t.get("created")),
            "delivered": _s(t.get("devdone")),
            "closed": _s(t.get("closed")),
            "status": _s(t.get("status")),
            "understood": YESNO.get(t.get("und"), None),
            "understood_evidence": _s(t.get("uel")) or _s(t.get("ue")),
            "met_client_date": YESNO.get(t.get("cexp"), None),
            "client_date": _s(t.get("cdate")),
            "met_commitment": YESNO.get(t.get("commit"), None),
            "commit_date": _s(t.get("vdate")),
            "reopened": YESNO.get(t.get("reo"), None),
            "rework_evidence": _s(t.get("rel")) or _s(t.get("re")),
            "remarks": t.get("remark") or "",
        })

    defects = []
    for d in extract.get("defectRows") or []:
        phase = d.get("phase")
        defects.append({
            "period": d.get("period") or periods[0]["name"],
            "key": d.get("key") or "", "link": _s(d.get("link")),
            "title": d.get("title") or "",
            "kind": d.get("kind") or "Bug",
            "reported_by": _s(d.get("by")),
            "reported_on": _s(d.get("on")),
            "phase": "Post-release" if phase == "Post-release" else "QA",
            "pre_existing": YESNO.get(d.get("existing"), None),
            "rejected": YESNO.get(d.get("rej"), None),
            "rejection_reason": _s(d.get("reason")),
            "evidence": _s(d.get("ev")),
            "final_status": FINAL_STATUS.get(d.get("fs"), None),
            "remarks": d.get("remark") or "",
        })

    review = [
        {"kind": "other", "subject": (line.split(" ", 1) or [""])[0], "question": line, "proposal": None, "link": None}
        for line in (extract.get("review") or [])
    ]

    cfg = extract.get("cfg") or {}
    return {
        "kif_version": "1.0",
        "generated": {
            "adapter": ADAPTER, "adapter_version": VERSION,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_url": f"https://app.asana.com/0/{cfg.get('projectGid', '')}",
            "capabilities": ["status_history", "comments", "assignee", "estimates",
                             "story_points", "created_date", "closed_date", "reporter"],
            "warnings": [],
        },
        "project": {
            "name": extract.get("projName") or project_cfg.get("name") or "",
            "tracker": "Asana",
            "tracker_url": f"https://app.asana.com/0/{cfg.get('projectGid', '')}",
            "pms_project_id": project_cfg.get("pms_project_id") or cfg.get("pmsProjectId"),
            "period_type": project_cfg.get("period_model") or cfg.get("periodType") or "Delivery cycle",
            "velocity_unit": project_cfg.get("velocity_unit") or cfg.get("velocityUnit") or "Estimated Hours",
            "client_date": _s(pd.get("clientDate")),
            "commit_date": _s(pd.get("commitDate")),
            "client_check": pd.get("clientCheck") or "Handover",
            "dates_why": cfg.get("datesWhy") or "",
            "sources_text": cfg.get("sourcesText") or "",
        },
        "periods": periods, "tasks": tasks, "defects": defects, "review": review[:40],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Turn an Asana browser extract into KIF.")
    ap.add_argument("--profile", required=True, type=Path)
    ap.add_argument("--project", help="Project id from the profile's projects list.")
    ap.add_argument("--from-extract", type=Path, help="JSON saved from window.__kpi.")
    ap.add_argument("--api", action="store_true", help="Moved: use scripts/kpi.py run, or adapters/asana/api.py.")
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args(argv)

    if a.api:
        print("Reading Asana directly is `python3 scripts/kpi.py run --profile ... --project ...` "
              "(or adapters/asana/api.py on its own). This file only converts a legacy extract.",
              file=sys.stderr)
        return 2

    if not a.from_extract or not a.from_extract.exists():
        print(
            "Need --from-extract pointing at a legacy window.__kpi JSON file.\n"
            "To read Asana itself, use: python3 scripts/kpi.py run --profile ... --project ...",
            file=sys.stderr,
        )
        return 2

    profile, project_cfg = resolve_profile(load_profile(a.profile), a.project)
    extract = _load(a.from_extract)

    # A saved window.name hand-off is sometimes wrapped; unwrap it rather than failing.
    if isinstance(extract, dict) and "all" in extract and isinstance(extract["all"], str):
        bundle = json.loads(extract["all"])
        extract = bundle.get(a.project) or list(bundle.values())[0]

    kif = convert(extract, profile, project_cfg)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(kif, indent=2), encoding="utf-8")
    print(f"Wrote {a.out}: {len(kif['tasks'])} task rows, {len(kif['defects'])} defect rows, "
          f"{len(kif['periods'])} period(s), {len(kif['review'])} question(s) for review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
