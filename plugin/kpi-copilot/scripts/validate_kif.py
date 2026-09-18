#!/usr/bin/env python3
"""
Check a KIF document before anybody trusts a number that came out of it.

Two layers. The schema catches shape problems. The second layer catches the things that are
schema-valid and still wrong - a task pointing at a period that does not exist, an excluded
row with no reason, a delivery date before the item was created. Those are the ones that
produce a plausible number nobody can defend later.

Usage:
    python3 validate_kif.py --kif run.kif.json [--strict]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA = HERE.parent / "schemas" / "kif.schema.json"
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _d(v):
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date() if v else None
    except ValueError:
        return None


def check(kif: dict) -> tuple[list[str], list[str]]:
    errors, warnings = [], []

    def err(m): errors.append(m)
    def warn(m): warnings.append(m)

    if kif.get("kif_version") != "1.0":
        err(f"kif_version is {kif.get('kif_version')!r}, expected '1.0'.")
    for key in ("project", "periods", "tasks", "defects"):
        if key not in kif:
            err(f"Missing top-level '{key}'.")
    if errors:
        return errors, warnings

    periods = {p.get("name") for p in kif["periods"]}
    if not periods:
        err("No periods. Every project needs at least one, usually 'Full Project'.")
    for p in kif["periods"]:
        name = p.get("name", "")
        if len(name) > 25:
            err(f"Period name '{name}' is {len(name)} characters; PMS allows 25.")
        for f in ("start", "end", "client_date", "commit_date", "handover_date"):
            if p.get(f) and not DATE.match(str(p[f])):
                err(f"Period '{name}' has {f}='{p[f]}', which is not YYYY-MM-DD.")
        s, e = _d(p.get("start")), _d(p.get("end"))
        if s and e and e < s:
            err(f"Period '{name}' ends ({p['end']}) before it starts ({p['start']}).")

    seen: dict[str, int] = {}
    for i, t in enumerate(kif["tasks"]):
        where = f"task[{i}] {t.get('key', '?')}"
        if not t.get("key"):
            err(f"{where}: no key.")
        if t.get("period") not in periods:
            err(f"{where}: period '{t.get('period')}' is not in the periods list.")
        if t.get("type") == "Excluded" and not t.get("exclude_reason"):
            # Without a reason nobody can answer "why is my 40-item board showing 12 items".
            err(f"{where}: excluded with no exclude_reason.")
        if t.get("type") not in ("Task", "CR", "Scope", "Excluded"):
            err(f"{where}: type '{t.get('type')}' is not one of Task, CR, Scope, Excluded.")
        for f in ("created", "delivered", "closed", "client_date", "commit_date"):
            if t.get(f) and not DATE.match(str(t[f])):
                err(f"{where}: {f}='{t[f]}' is not YYYY-MM-DD.")
        c, dl, cl = _d(t.get("created")), _d(t.get("delivered")), _d(t.get("closed"))
        if c and dl and dl < c:
            warn(f"{where}: delivered {t['delivered']} is before it was created {t['created']}.")
        if dl and cl and cl < dl:
            warn(f"{where}: closed {t['closed']} is before it was delivered {t['delivered']}.")
        if t.get("closed") and not t.get("delivered") and t.get("type") != "Excluded":
            warn(f"{where}: closed but never delivered. Velocity will skip it.")
        if t.get("reopened") == "Yes" and not t.get("rework_evidence"):
            warn(f"{where}: counted as rework with no evidence link.")
        for field, ev in (("understood", "understood_evidence"), ("met_commitment", "commitment_evidence")):
            if t.get(field) == "No" and not t.get(ev):
                warn(f"{where}: {field}=No with no evidence. This is the kind of call that gets questioned.")
        key = t.get("key")
        if key:
            seen[key] = seen.get(key, 0) + 1

    dupes = [k for k, n in seen.items() if n > 1]
    if dupes:
        warn(f"Keys appearing more than once: {', '.join(sorted(dupes)[:10])}. "
             f"Intentional for split components, wrong otherwise.")

    for i, d in enumerate(kif["defects"]):
        where = f"defect[{i}] {d.get('key', '?')}"
        if d.get("period") not in periods:
            err(f"{where}: period '{d.get('period')}' is not in the periods list.")
        if d.get("rejected") == "Yes" and not d.get("rejection_reason"):
            warn(f"{where}: rejected with no reason. The note prints reasons, so it will read oddly.")
        if d.get("reported_on") and not DATE.match(str(d["reported_on"])):
            err(f"{where}: reported_on='{d['reported_on']}' is not YYYY-MM-DD.")

    gen = kif.get("generated") or {}
    if not gen.get("capabilities"):
        warn("No capabilities declared. The engine cannot tell a missing value from an unobservable one, "
             "so it will trust every blank. Declare them in the adapter.")
    if not gen.get("adapter"):
        warn("No adapter name recorded, so nobody can tell where these numbers came from.")

    deliverables = [t for t in kif["tasks"] if t.get("type") in ("Task", "CR", "Scope")]
    if not deliverables:
        err("No deliverable rows at all - every task is Excluded. Check the exclusion patterns; "
            "that is nearly always an over-broad regex.")
    excluded = len(kif["tasks"]) - len(deliverables)
    if deliverables and excluded > len(deliverables):
        warn(f"{excluded} rows excluded against {len(deliverables)} deliverables. Worth a look at the patterns.")

    return errors, warnings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate a KIF document.")
    ap.add_argument("--kif", required=True, type=Path)
    ap.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    a = ap.parse_args(argv)

    kif = json.loads(a.kif.read_text(encoding="utf-8"))

    # Schema check when jsonschema is available; the hand-written checks below run regardless,
    # so a missing library degrades the check rather than skipping it.
    try:
        import jsonschema  # type: ignore
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        v = jsonschema.Draft7Validator(schema)
        schema_errors = [f"{'/'.join(str(p) for p in e.path) or '(root)'}: {e.message}"
                         for e in sorted(v.iter_errors(kif), key=lambda e: list(e.path))]
    except ImportError:
        schema_errors = []
        print("(jsonschema not installed - running the hand-written checks only. "
              "pip3 install jsonschema for full validation.)", file=sys.stderr)

    errors, warnings = check(kif)
    errors = schema_errors + errors

    if errors:
        print(f"{len(errors)} problem(s):")
        for e in errors:
            print(f"  ERROR  {e}")
    if warnings:
        print(f"{len(warnings)} thing(s) worth a look:")
        for w in warnings:
            print(f"  WARN   {w}")
    if not errors and not warnings:
        print(f"{a.kif.name} is valid: {len(kif['tasks'])} task rows, {len(kif['defects'])} defect rows, "
              f"{len(kif['periods'])} period(s).")
    elif not errors:
        print(f"\n{a.kif.name} is valid, with {len(warnings)} warning(s).")

    return 1 if errors or (a.strict and warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
