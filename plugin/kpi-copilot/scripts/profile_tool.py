#!/usr/bin/env python3
"""
Create and check a profile.

`init` writes a profile with every section present and commented, so a person editing it by
hand knows what each part is for. `validate` checks it against the schema and then against
the things a schema cannot see - a tool id referenced from Sources that does not exist in
Tools, an output mode that contradicts itself, a delivered-when rule with no states in it.

Usage:
    python3 profile_tool.py init     --out profile.yaml [--from answers.json]
    python3 profile_tool.py validate --profile profile.yaml
    python3 profile_tool.py explain  --key workflow.delivered_when
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SCHEMA = HERE.parent / "schemas" / "profile.schema.json"

sys.path.insert(0, str(HERE))
from profile_lib import OVERRIDABLE, resolve, visible_tools  # noqa: E402

TEMPLATE = """profile_version: "1.0"

# Written by kpi-setup. Edit here or in the KPI Profile Workbook - they are two views of the
# same thing, and scripts/workbook.py converts between them.

owner:
  name: ""
  email: ""
  role: ""
  account: ""
  timezone: Asia/Dhaka

organization:
  # Fixed for everyone in the company. Changing these here does not change what PMS expects.
  pms_base_url: https://pms.example.com
  kpi_registry: kpi_registry.json
  note_format: "what is measured || the numbers || what was left out || why"
  evidence_required: true

# Where everything lives. Add a row for each place this project's truth is kept: the board,
# the chat spaces, the plan, the estimates sheet, the folder the working file goes in.
tools:
  - id: tracker
    kind: issue-tracker
    name: ""
    url_or_id: ""
    description: "What this is and why it matters, for someone who has never seen the project."
    used_for: [scope, dates, defects, evidence]
    access: ""

tracker:
  adapter: csv          # asana | jira | csv. csv works with an export from anything.
  project_ref: ""
  url: ""
  estimate_field: ""
  story_point_field: ""
  key_field: ""
  options: {}

conventions:
  key_pattern: ""       # e.g. '[A-Z]+-\\d+'. Blank = use the tracker's own id.
  defect_by: issue-type # title-pattern | issue-type | label | separate-board | field
  defect_pattern: ""
  defect_values: [Bug]
  observation_values: [Observation, Improvement]
  exclude_patterns: []  # cards that are not deliverables
  cr_marker: ""
  client_names: []      # exact names, so a client-found defect can be told from a QA one

workflow:
  # The most important section. This is what turns your column names into a number that can
  # be compared with another team's.
  delivered_when:
    signal: status-entered
    values: []
  closed_when:
    values: []
  reopened_when:
    values: []
    ignore_first_qa_fail: true
  clarification_when:
    values: []
    also_comments: true

sources:
  # All optional. Anything missing becomes "Not measured" with a reason, never a guess.
  plan: {kind: none}
  estimates: {kind: none}
  timeline: {kind: none}
  evidence_channels: []
  hours_first: tracker
  hours_basis: dev

periods:
  model: Delivery cycle
  naming: "Initial Scope, Additional Requests N"
  client_check_default: Handover

policy:
  count_observations: false
  count_improvements: false
  count_pre_existing: false
  count_post_release: true

output:
  mode: review-only     # review-only | dry-run | assisted-push | auto-push
  unattended: false
  workbook: xlsx
  workbook_location: ./runs
  run_folder: runs

custom_instructions:
  # Your own instructions. Style is free. Rule overrides are allowed but printed in every
  # run summary. Targets are set per project in PMS, not here, so the workbook and PMS cannot
  # disagree about the same number; the counting behind each KPI does not vary.
  notes_style: ""
  always: []
  never: []
  glossary: []
  rule_overrides: []
  escalation: ""

projects:
  - id: ""
    name: ""
    pms_project_id: null
"""


def _load(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        import yaml  # type: ignore
        return yaml.safe_load(text)
    return json.loads(text)


def _deep_merge(base: dict, extra: dict) -> dict:
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def init(out: Path, answers: Path | None) -> int:
    if out.exists():
        print(f"{out} already exists. Delete it or pick another path.", file=sys.stderr)
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    if answers:
        import yaml  # type: ignore
        base = yaml.safe_load(TEMPLATE)
        merged = _deep_merge(base, _load(answers))
        out.write_text(yaml.safe_dump(merged, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
    else:
        out.write_text(TEMPLATE, encoding="utf-8")
    print(f"Wrote {out}")
    return 0


def validate(path: Path) -> int:
    profile = _load(path)
    errors, warnings = [], []

    try:
        import jsonschema  # type: ignore
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        for e in sorted(jsonschema.Draft7Validator(schema).iter_errors(profile), key=lambda e: list(e.path)):
            where = "/".join(str(p) for p in e.path) or "(root)"
            # The one schema failure people actually hit deserves a sentence rather than a
            # list of enum members: they tried to set something that lives elsewhere.
            if "rule_overrides" in where and where.endswith("/rule"):
                bad = str(e.instance)
                if bad.startswith("threshold"):
                    # Thresholds are per project in PMS, so wanting a different one is normal.
                    # What must not happen is the target living here as well, because then the
                    # workbook and PMS disagree about the same number.
                    errors.append(
                        f"{where}: set '{bad}' on this project in PMS instead. Targets are configurable "
                        f"per project there, and the next run reads whatever PMS holds and marks it as this "
                        f"project's own. A target kept in this file would make the workbook and PMS disagree."
                    )
                else:
                    errors.append(
                        f"{where}: '{bad}' is not a rule this tool can apply. KPI ids and the definition of "
                        f"each ratio come from PMS and the shared counting rules; the supported rules are "
                        f"listed in the schema."
                    )
            else:
                errors.append(f"{where}: {e.message}")
    except ImportError:
        warnings.append("jsonschema is not installed, so only the hand-written checks ran. pip3 install jsonschema")

    tools = {t.get("id") for t in (profile.get("tools") or [])}
    accounts = {a.get("id") for a in (profile.get("accounts") or [])}
    project_ids = [p.get("id") for p in (profile.get("projects") or [])]

    # -- ids are unique -----------------------------------------------------------------
    for label, ids in (("accounts", [a.get("id") for a in (profile.get("accounts") or [])]),
                       ("projects", project_ids)):
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            errors.append(f"{label} has more than one entry with id {', '.join(sorted(str(d) for d in dupes))}. "
                          f"Ids are how everything else refers to them, so they have to be unique.")

    # -- accounts and tool scoping ------------------------------------------------------
    for pr in profile.get("projects") or []:
        acct = pr.get("account")
        if acct and acct not in accounts:
            errors.append(f"Project '{pr.get('id')}' belongs to account '{acct}', which is not on the "
                          f"Accounts tab. Known: {', '.join(sorted(accounts)) or 'none'}.")
    for t in profile.get("tools") or []:
        for ref in t.get("accounts") or []:
            if ref not in accounts:
                errors.append(f"Tool '{t.get('id')}' is tagged with account '{ref}', which does not exist.")
        for ref in t.get("projects") or []:
            if ref not in project_ids:
                errors.append(f"Tool '{t.get('id')}' is tagged with project '{ref}', which does not exist.")

    # -- overrides name real sections ---------------------------------------------------
    for label, rows in (("Account", profile.get("accounts") or []), ("Project", profile.get("projects") or [])):
        for row in rows:
            bad = [k for k in (row.get("overrides") or {}) if k not in OVERRIDABLE]
            if bad:
                errors.append(f"{label} '{row.get('id')}' overrides {', '.join(bad)}, which is not an "
                              f"overridable section. You can override: {', '.join(OVERRIDABLE)}.")

    # -- people and client-facing tools --------------------------------------------------
    # A client-facing space whose people are unknown to the defect rules is the quiet way a
    # client-reported bug gets counted as a QA one.
    for t in profile.get("tools") or []:
        if t.get("client_facing") and not (t.get("people") or []):
            warnings.append(f"Tool '{t.get('id')}' is marked client-facing but lists nobody. Add the client "
                            f"people, so a defect they report can be told from one QA raised.")

    # -- every project's resolved sources point at tools that project can see ------------
    # A project reaching for another account's chat space is a real mistake, and one that
    # otherwise shows up as an empty evidence search three weeks later.
    def _check_sources(srcs: dict, seen: set, where: str) -> None:
        for name in ("plan", "estimates", "timeline"):
            ref = (srcs.get(name) or {}).get("tool_id")
            if ref and ref not in seen:
                errors.append(f"{where}: sources.{name}.tool_id is '{ref}', which is not a tool this "
                              f"project can see. Add it to the Tools tab, or tag it with this account.")
        for ch in srcs.get("evidence_channels") or []:
            if ch not in seen:
                errors.append(f"{where}: sources.evidence_channels lists '{ch}', which is not a tool this "
                              f"project can see. Tools are scoped by account, so check its Accounts column.")

    if project_ids:
        for pr in profile.get("projects") or []:
            try:
                merged, _ = resolve(profile, pr.get("id"))
            except SystemExit as e:
                errors.append(str(e))
                continue
            seen = {t.get("id") for t in merged.get("tools") or []}
            known = {n.lower() for n in (merged.get("conventions") or {}).get("client_names") or []}
            for t in merged.get("tools") or []:
                if not t.get("client_facing"):
                    continue
                unlisted = [n for n in (t.get("people") or []) if n.lower() not in known]
                if unlisted and known:
                    warnings.append(f"Project '{pr.get('id')}': {t.get('id')} lists {', '.join(unlisted)} as "
                                    f"people in a client-facing space, but they are not in "
                                    f"conventions.client_names. A defect they report would be counted as "
                                    f"found by QA.")
            _check_sources(merged.get("sources") or {}, seen, f"Project '{pr.get('id')}'")
            out_cfg = merged.get("output") or {}
            if out_cfg.get("mode") == "auto-push" and not out_cfg.get("unattended"):
                errors.append(f"Project '{pr.get('id')}' resolves to mode 'auto-push' with unattended off. "
                              f"Check its account's overrides.")
            if out_cfg.get("notify") and out_cfg["notify"] not in seen:
                errors.append(f"Project '{pr.get('id')}': output.notify is '{out_cfg['notify']}', which is "
                              f"not a tool this project can see.")
    else:
        _check_sources(profile.get("sources") or {}, tools, "profile")

    out = profile.get("output") or {}
    if out.get("mode") == "auto-push" and not out.get("unattended"):
        errors.append("output.mode is 'auto-push' but output.unattended is off, so a run would stop and wait "
                      "for a person who is not there. Pick one or the other.")
    if out.get("notify") and out["notify"] not in tools:
        errors.append(f"output.notify is '{out['notify']}', which is not an id on the Tools tab.")
    if out.get("workbook") == "google-sheets" and not out.get("workbook_location"):
        warnings.append("Working files are set to Google Sheets but no folder is given, so the run will not know "
                        "where to put them.")

    wf = profile.get("workflow") or {}
    if not (wf.get("delivered_when") or {}).get("values"):
        warnings.append("workflow.delivered_when has no states, so Velocity and the default meaning of "
                        "'delivered on time' fall back to the closed date, which usually flatters the "
                        "numbers.")
    if not (wf.get("closed_when") or {}).get("values"):
        warnings.append("workflow.closed_when has no states, so Rework Rate has nothing to measure against.")

    import re as _re
    for field, pattern in (("conventions.key_pattern", (profile.get("conventions") or {}).get("key_pattern")),
                           ("conventions.defect_pattern", (profile.get("conventions") or {}).get("defect_pattern")),
                           ("conventions.cr_marker", (profile.get("conventions") or {}).get("cr_marker"))):
        if pattern:
            try:
                _re.compile(pattern)
            except _re.error as e:
                errors.append(f"{field} is not a valid regular expression: {e}")
    for i, p in enumerate(((profile.get("conventions") or {}).get("exclude_patterns") or [])):
        try:
            _re.compile(p)
        except _re.error as e:
            errors.append(f"conventions.exclude_patterns[{i}] is not a valid regular expression: {e}")

    ci = profile.get("custom_instructions") or {}
    for i, ov in enumerate(ci.get("rule_overrides") or []):
        if not ov.get("why"):
            errors.append(f"custom_instructions.rule_overrides[{i}] has no 'why'. Every override is printed in "
                          f"the run summary, so it needs a reason a reader can follow.")

    projects = profile.get("projects") or []
    if not projects:
        warnings.append("No projects listed, so a run has nothing to point at.")
    for p in projects:
        if not p.get("pms_project_id") and (out.get("mode") in ("assisted-push", "auto-push")):
            warnings.append(f"Project '{p.get('id')}' has no pms_project_id, so it cannot be pushed.")

    for e in errors:
        print(f"  ERROR  {e}")
    for w in warnings:
        print(f"  WARN   {w}")
    if not errors and not warnings:
        print(f"{path.name} looks good.")
    elif not errors:
        print(f"\n{path.name} is valid, with {len(warnings)} warning(s).")
    return 1 if errors else 0


def explain(key: str) -> int:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    node: Any = schema.get("properties", {})
    for part in key.split("."):
        node = (node.get(part) or {})
        if "properties" in node and part != key.split(".")[-1]:
            node = node["properties"]
    if not node:
        print(f"No setting called '{key}'.", file=sys.stderr)
        return 2
    print(f"{key}\n")
    if node.get("description"):
        print(node["description"] + "\n")
    xw = node.get("x-workbook") or {}
    if xw.get("hint"):
        print(f"Hint: {xw['hint']}")
    if node.get("enum"):
        print(f"Allowed: {', '.join(str(v) for v in node['enum'] if v is not None)}")
    if node.get("default") is not None:
        print(f"Default: {node['default']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Create and check a KPI Copilot profile.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init"); i.add_argument("--out", required=True, type=Path); i.add_argument("--from", dest="answers", type=Path)
    v = sub.add_parser("validate"); v.add_argument("--profile", required=True, type=Path)
    e = sub.add_parser("explain"); e.add_argument("--key", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "init":
        return init(a.out, a.answers)
    if a.cmd == "validate":
        return validate(a.profile)
    return explain(a.key)


if __name__ == "__main__":
    raise SystemExit(main())
