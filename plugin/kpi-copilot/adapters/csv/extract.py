#!/usr/bin/env python3
"""
CSV adapter - the universal one.

Every issue tracker worth using can export a CSV. This adapter turns that export into KIF,
which means a team on ClickUp, Linear, Azure DevOps, Monday, Trello, GitHub Issues or a
hand-maintained spreadsheet can produce real KPIs on their first afternoon, without waiting
for anyone to write them an integration.

It is not a poor relation. What it cannot do is read status history, so Delivery Commitment,
Rework Rate and Task Comprehension depend on columns the export carries or the person fills
in. It says so in `capabilities`, and the engine reports those KPIs as "Not measured" with
the reason rather than inventing them.

Column mapping lives in the profile under `tracker.options.columns`, so nobody has to rename
a single header in their export:

    tracker:
      adapter: csv
      options:
        file: exports/board.csv
        columns:
          key: "Issue key"
          title: "Summary"
          type: "Issue Type"
          status: "Status"
          assignee: "Assignee"
          created: "Created"
          delivered: "Ready for QA date"
          closed: "Resolved"
          hours_dev: "Original Estimate"
          period: "Sprint"
        defects_file: exports/bugs.csv      # optional; else defects come from the same file

Usage:
    python3 extract.py --profile profile.yaml --project q3-release --out run.kif.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
from profile_lib import load as load_profile, resolve as resolve_profile  # noqa: E402

ADAPTER = "csv"
VERSION = "1.0.0"

# Header names people actually have, so the mapping is usually empty in practice.
GUESSES: dict[str, list[str]] = {
    "key": ["key", "issue key", "id", "ticket", "ticket id", "task id", "identifier"],
    "title": ["title", "summary", "name", "task name", "subject"],
    "type": ["type", "issue type", "work type", "category", "kind"],
    "status": ["status", "state", "column", "stage", "list"],
    "assignee": ["assignee", "owner", "assigned to", "responsible"],
    "reporter": ["reporter", "created by", "reported by", "requester"],
    "created": ["created", "created at", "created date", "opened"],
    "delivered": ["delivered", "ready for qa", "ready for qa date", "dev complete", "in test date"],
    "closed": ["closed", "resolved", "completed at", "done date", "closed date"],
    "hours_dev": ["estimate", "original estimate", "estimated time", "estimated hours", "dev hours"],
    "hours_qa": ["qa hours", "qa estimate", "testing hours"],
    "story_points": ["story points", "points", "sp"],
    "period": ["sprint", "milestone", "period", "iteration", "release", "cycle", "fix version"],
    "labels": ["labels", "tags", "label"],
    "link": ["link", "url", "issue url", "permalink"],
    "priority": ["priority", "severity"],
    "resolution": ["resolution", "resolution status"],
}

TRUE = {"yes", "y", "true", "1", "done", "complete", "completed"}


def _load_any(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        import yaml  # type: ignore
        return yaml.safe_load(text)
    return json.loads(text)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _date(value: str | None) -> str | None:
    """People export dates in whatever their locale does. Try the ones that actually turn up
    and give back None rather than a wrong date."""
    if not value:
        return None
    v = str(value).strip()
    if not v:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%b-%Y", "%d %b %Y", "%Y/%m/%d",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%m/%d/%Y %H:%M"):
        try:
            return datetime.strptime(v[: len(fmt) + 6].strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", v)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def _num(value: str | None) -> float | None:
    if value is None:
        return None
    v = re.sub(r"[^0-9.\-]", "", str(value))
    try:
        return float(v) if v not in ("", "-", ".") else None
    except ValueError:
        return None


def build_mapping(headers: list[str], configured: dict) -> tuple[dict, list[str]]:
    """Configured mapping wins; anything not configured is guessed from the header name.
    Returns the mapping and a list of fields we could not find, which becomes the warnings."""
    mapping, missing = {}, []
    lookup = {_norm(h): h for h in headers}
    for field, candidates in GUESSES.items():
        if field in configured and configured[field] in headers:
            mapping[field] = configured[field]
            continue
        hit = next((lookup[_norm(c)] for c in candidates if _norm(c) in lookup), None)
        if hit:
            mapping[field] = hit
        else:
            missing.append(field)
    return mapping, missing


def read_rows(path: Path) -> tuple[list[dict], list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        sample = f.read(8192)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        rows = [r for r in reader]
        return rows, list(reader.fieldnames or [])


def classify(row: dict, m: dict, conv: dict) -> tuple[str, str | None]:
    """Decide what a row is. Order matters: an explicit exclusion beats everything, then the
    team's CR marker, then whether the plan claims it."""
    title = (row.get(m.get("title", "")) or "").strip()
    kind = (row.get(m.get("type", "")) or "").strip()
    labels = (row.get(m.get("labels", "")) or "")

    for pattern in conv.get("exclude_patterns") or []:
        try:
            if re.search(pattern, title, re.I):
                return "Excluded", f"Title matches the team's 'not a deliverable' rule ({pattern})"
        except re.error:
            continue

    cr_marker = conv.get("cr_marker")
    if cr_marker:
        try:
            if re.search(cr_marker, f"{title} {labels} {kind}", re.I):
                return "CR", None
        except re.error:
            pass
    return "Task", None


def is_defect(row: dict, m: dict, conv: dict) -> tuple[bool, str]:
    """Returns (is a defect, what kind). Handles all four ways teams mark defects."""
    title = (row.get(m.get("title", "")) or "").strip()
    kind = (row.get(m.get("type", "")) or "").strip()
    labels = (row.get(m.get("labels", "")) or "")
    by = conv.get("defect_by", "title-pattern")
    defect_values = [v.lower() for v in (conv.get("defect_values") or ["bug", "defect"])]
    obs_values = [v.lower() for v in (conv.get("observation_values") or ["observation", "improvement"])]

    haystack = {"title-pattern": title, "issue-type": kind, "label": labels, "field": kind}.get(by, title)

    if by == "title-pattern" and conv.get("defect_pattern"):
        try:
            mo = re.match(conv["defect_pattern"], title, re.I)
            if mo:
                word = (mo.group(1) if mo.groups() else "Bug").title()
                return True, word if word in ("Bug", "Observation", "Improvement") else "Bug"
        except re.error:
            pass
        return False, ""

    low = haystack.lower()
    for v in obs_values:
        if v in low:
            return True, "Improvement" if "improve" in v else "Observation"
    for v in defect_values:
        if v in low:
            return True, "Bug"
    return False, ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Turn a tracker CSV export into KIF.")
    ap.add_argument("--profile", required=True, type=Path)
    ap.add_argument("--project", help="Project id from the profile's projects list.")
    ap.add_argument("--file", type=Path, help="Override the CSV path from the profile.")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)

    profile, proj = resolve_profile(load_profile(args.profile), args.project)
    tracker = profile.get("tracker") or {}
    options = tracker.get("options") or {}
    conv = profile.get("conventions") or {}
    csv_path = args.file or Path(options.get("file", ""))
    if not csv_path or not csv_path.exists():
        base = args.profile.parent / str(csv_path)
        if base.exists():
            csv_path = base
        else:
            print(
                f"Cannot find the export. Set tracker.options.file in the profile, or pass --file.\n"
                f"Looked for: {csv_path}",
                file=sys.stderr,
            )
            return 2

    rows, headers = read_rows(csv_path)
    if not rows:
        print(f"{csv_path} has no rows.", file=sys.stderr)
        return 2

    mapping, missing = build_mapping(headers, options.get("columns") or {})
    warnings: list[str] = []
    if "key" not in mapping:
        print(
            "No column looks like a ticket key. Add tracker.options.columns.key to the profile.\n"
            f"Columns found: {', '.join(headers)}",
            file=sys.stderr,
        )
        return 2

    for field in ("delivered", "hours_dev", "period"):
        if field in missing:
            warnings.append(
                f"No column for '{field}' in the export, so anything depending on it is left blank "
                f"rather than guessed."
            )

    # Capabilities: claim only what this export actually carries.
    caps = ["created_date", "closed_date"]
    if "assignee" in mapping:
        caps.append("assignee")
    if "hours_dev" in mapping:
        caps.append("estimates")
    if "story_points" in mapping:
        caps.append("story_points")
    if "type" in mapping:
        caps.append("issue_type")
    if "labels" in mapping:
        caps.append("labels")
    if "reporter" in mapping:
        caps.append("reporter")
    # A CSV never has status history. That is the honest limit of this adapter.
    warnings.append(
        "A CSV export has no status history, so reopens and client clarifications are only counted "
        "where the export carries a column for them. Rework Rate and Task Comprehension will say so."
    )

    def g(row: dict, field: str) -> str | None:
        col = mapping.get(field)
        return (row.get(col) or "").strip() if col else None

    default_period = (proj.get("period_model") and "Full Project") or "Full Project"
    periods_seen: dict[str, dict] = {}
    tasks, defects, review = [], [], []

    for row in rows:
        key = g(row, "key")
        if not key:
            continue
        period = g(row, "period") or default_period
        periods_seen.setdefault(period, {"name": period[:25]})

        defect, kind = is_defect(row, mapping, conv)
        if defect:
            reporter = g(row, "reporter") or ""
            client_names = [c.lower() for c in (conv.get("client_names") or [])]
            phase = "Post-release" if reporter.lower() in client_names else "QA"
            resolution = (g(row, "resolution") or "").lower()
            rejected = "Yes" if any(
                w in resolution for w in ("invalid", "duplicate", "won't", "wont", "cannot reproduce",
                                          "not reproducible", "by design", "not a bug")
            ) else ("No" if resolution else None)
            defects.append({
                "period": period, "key": key, "link": g(row, "link"),
                "title": g(row, "title") or "", "kind": kind,
                "reported_by": reporter or None, "reported_on": _date(g(row, "created")),
                "phase": phase, "pre_existing": None, "rejected": rejected,
                "rejection_reason": g(row, "resolution"),
                "final_status": None, "evidence": g(row, "link"), "remarks": "",
            })
            if rejected is None:
                review.append({
                    "kind": "rejection", "subject": key,
                    "question": f"Was {key} a real defect, or was it closed as not a bug?",
                    "proposal": "Treat it as a real defect", "link": g(row, "link"),
                })
            continue

        ttype, reason = classify(row, mapping, conv)
        closed = _date(g(row, "closed"))
        delivered = _date(g(row, "delivered"))
        if not delivered and closed:
            delivered = closed
            review.append({
                "kind": "date", "subject": key,
                "question": f"{key} has no delivery date in the export. Use the closed date, {closed}?",
                "proposal": f"Use {closed}", "link": g(row, "link"),
            })
        tasks.append({
            "period": period, "key": key, "link": g(row, "link"),
            "title": g(row, "title") or "", "type": ttype,
            "exclude_reason": reason,
            "planned": ttype == "Task",
            "hours_dev": _num(g(row, "hours_dev")),
            "hours_qa": _num(g(row, "hours_qa")),
            "hours_source": "Tracker estimate" if g(row, "hours_dev") else None,
            "story_points": _num(g(row, "story_points")),
            "assignee": g(row, "assignee"),
            "created": _date(g(row, "created")),
            "delivered": delivered,
            "closed": closed,
            "status": g(row, "status"),
            # Left null on purpose: a CSV cannot prove any of these, and a guess here would
            # quietly move three KPIs.
            "understood": None, "met_client_date": None, "met_commitment": None, "reopened": None,
            "remarks": "",
        })

    kif = {
        "kif_version": "1.0",
        "generated": {
            "adapter": ADAPTER, "adapter_version": VERSION,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_url": str(csv_path), "capabilities": caps, "warnings": warnings,
        },
        "project": {
            "name": proj.get("name") or profile.get("owner", {}).get("account") or csv_path.stem,
            "tracker": options.get("tracker_name") or "CSV export",
            "tracker_url": tracker.get("url"),
            "pms_project_id": proj.get("pms_project_id"),
            "period_type": proj.get("period_model") or (profile.get("periods") or {}).get("model") or "Full project",
            "velocity_unit": proj.get("velocity_unit")
                or ("Story Points" if "story_points" in mapping and "hours_dev" not in mapping else "Estimated Hours"),
            "client_check": (profile.get("periods") or {}).get("client_check_default", "Handover"),
        },
        "periods": list(periods_seen.values()) or [{"name": "Full Project"}],
        "tasks": tasks,
        "defects": defects,
        "review": review[:40],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(kif, indent=2), encoding="utf-8")
    print(
        f"Wrote {args.out}: {len(tasks)} task rows, {len(defects)} defect rows, "
        f"{len(kif['periods'])} period(s), {len(review)} question(s) for review."
    )
    if missing:
        print(f"No column found for: {', '.join(missing)}. Map them in tracker.options.columns if the export has them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
