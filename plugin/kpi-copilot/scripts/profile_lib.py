#!/usr/bin/env python3
"""
Loading a profile, and resolving it for one project.

A project lead usually runs more than one project, and often across more than one client
account - Northwind on Asana and Google Chat, Acme on Jira and Slack. Making them keep a
separate profile per project would duplicate the Tools registry, the owner block and the
output settings, and those copies would drift within a month.

In practice almost everything that varies varies **per account**, not per project: Northwind's
five projects share one tracker, one chat space, one set of conventions. So there are three
levels, and each one only says what differs from the one above it:

    1. profile defaults   how you usually work
    2. account            what is true for every project on this client
    3. project            what is true for just this one

    accounts:
      - id: northwind
        name: Northwind
        overrides:
          tracker: {adapter: asana}
          sources: {evidence_channels: [chat-northwind-devqa]}

      - id: acme
        name: Acme
        overrides:
          tracker: {adapter: jira, project_ref: ACME}
          sources: {evidence_channels: [slack-acme]}
          output:  {mode: review-only}   # this client's numbers get typed in by hand

    projects:
      - {id: q3-release,     account: northwind, pms_project_id: 101}
      - {id: gateway,        account: northwind, pms_project_id: 102}
      - id: acme-identity
        account: acme
        pms_project_id: 201
        overrides:
          periods: {model: Sprint}       # just this project

A lead with one account and one tracker writes neither block and notices nothing.

Merge rules, and they matter:

- **Dicts merge, deeply.** Overriding `workflow.delivered_when.values` leaves
  `workflow.closed_when` alone.
- **Lists replace.** A different team's `exclude_patterns` are *their* patterns, not yours
  plus theirs. Accumulating them is how one team's regex quietly eats another team's work.
- **Scalars replace.** Obviously.
- `owner` and `organization` never vary: they describe the person and the company.
- `tools` is one registry for everything you work on. Each entry can say which accounts or
  projects it belongs to; one that says neither is shared (PMS, your Drive folder). Resolving
  for a project narrows the registry to what that project can actually see, so a run on Acme
  never reaches for Northwind's chat space.

Every script that reads a profile goes through `resolve()` so they cannot disagree about what
a project's settings are.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

# Sections a project may override. Deliberately not `owner`, `tools` or `organization` -
# those describe the person and the company, not a project.
OVERRIDABLE = (
    "tracker", "conventions", "workflow", "sources", "periods", "policy",
    "output", "custom_instructions",
)


def load(path: str | Path) -> dict:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except ImportError as e:
            raise SystemExit(
                f"{p.name} is YAML but PyYAML is not installed. Run: pip3 install pyyaml"
            ) from e
        return yaml.safe_load(text) or {}
    return json.loads(text)


def deep_merge(base: Any, over: Any) -> Any:
    """Dicts merge; everything else replaces. See the note about lists above."""
    if isinstance(base, dict) and isinstance(over, dict):
        out = dict(base)
        for k, v in over.items():
            out[k] = deep_merge(out.get(k), v) if k in out else copy.deepcopy(v)
        return out
    return copy.deepcopy(over)


def find_project(profile: dict, project_id: str | None) -> dict:
    """The named project, or the only one, or the first. A profile with several projects and
    no id given is ambiguous enough to be worth an error rather than a guess."""
    projects = profile.get("projects") or []
    if not projects:
        return {}
    if project_id:
        hit = next((p for p in projects if p.get("id") == project_id), None)
        if hit is None:
            known = ", ".join(str(p.get("id")) for p in projects)
            raise SystemExit(f"No project called '{project_id}' in this profile. Known: {known}")
        return hit
    if len(projects) == 1:
        return projects[0]
    known = ", ".join(str(p.get("id")) for p in projects)
    raise SystemExit(
        f"This profile covers several projects, so --project is required. Known: {known}"
    )


def find_account(profile: dict, account_id: str | None) -> dict:
    if not account_id:
        return {}
    hit = next((a for a in (profile.get("accounts") or []) if a.get("id") == account_id), None)
    if hit is None:
        known = ", ".join(str(a.get("id")) for a in (profile.get("accounts") or [])) or "none defined"
        raise SystemExit(
            f"Project references account '{account_id}', which is not in this profile. Known: {known}"
        )
    return hit


def _check_overrides(overrides: dict, where: str) -> None:
    unknown = [k for k in overrides if k not in OVERRIDABLE]
    if unknown:
        raise SystemExit(
            f"{where} tries to override {', '.join(unknown)}, which is not an overridable section. "
            f"You can override: {', '.join(OVERRIDABLE)}."
        )


def visible_tools(profile: dict, account_id: str | None, project_id: str | None) -> list[dict]:
    """The tools this project can see: the shared ones, plus those tagged with its account or
    itself. Narrowing matters - a run on Acme should not go looking in Northwind's chat space
    for a handover date, and a mistyped tool id should fail loudly rather than silently
    reading somebody else's project."""
    out = []
    for t in profile.get("tools") or []:
        accounts, projects = t.get("accounts") or [], t.get("projects") or []
        if not accounts and not projects:
            out.append(t)
        elif account_id and account_id in accounts:
            out.append(t)
        elif project_id and project_id in projects:
            out.append(t)
    return out


def resolve(profile: dict, project_id: str | None = None) -> tuple[dict, dict]:
    """Returns (profile as it applies to this project, the project row).

    Layers, in order: profile defaults, then the project's account, then the project. The
    returned value is a full profile - same shape, same keys - so every caller treats it
    exactly as it treated a single-project profile. That is why adding accounts did not mean
    touching the engine's logic at all.
    """
    project = find_project(profile, project_id)
    account = find_account(profile, project.get("account"))
    merged = copy.deepcopy(profile)

    acct_over = account.get("overrides") or {}
    proj_over = project.get("overrides") or {}
    _check_overrides(acct_over, f"Account '{account.get('id')}'")
    _check_overrides(proj_over, f"Project '{project.get('id')}'")

    for overrides in (acct_over, proj_over):
        for section in OVERRIDABLE:
            if section in overrides:
                merged[section] = deep_merge(merged.get(section) or {}, overrides[section])

    merged["tools"] = visible_tools(profile, account.get("id"), project.get("id"))

    # A few project fields are shorthands for an override, kept because they read better on
    # the Projects tab than a nested block would.
    if project.get("tracker_ref"):
        merged.setdefault("tracker", {})["project_ref"] = project["tracker_ref"]
    if project.get("velocity_unit"):
        merged.setdefault("periods", {})["velocity_unit"] = project["velocity_unit"]
    if project.get("period_model"):
        merged.setdefault("periods", {})["model"] = project["period_model"]
    for field, section, key in (("plan_ref", "plan", "ref"), ("estimates_ref", "estimates", "ref")):
        if project.get(field):
            merged.setdefault("sources", {}).setdefault(section, {})[key] = project[field]

    merged["_project"] = project
    merged["_account"] = account
    return merged, project


def describe_overrides(profile: dict) -> list[dict]:
    """Flatten every account's and project's overrides into rows, for the workbook and the run
    summary. Seeing them side by side is how somebody notices that two projects drifted apart
    for a reason nobody remembers."""
    rows = []
    for a in profile.get("accounts") or []:
        for section, block in (a.get("overrides") or {}).items():
            for path, value in _flatten(block, section):
                rows.append({"scope": "account", "id": a.get("id"), "setting": path, "value": value})
    for p in profile.get("projects") or []:
        for section, block in (p.get("overrides") or {}).items():
            for path, value in _flatten(block, section):
                rows.append({"scope": "project", "id": p.get("id"), "setting": path, "value": value})
    return rows


def _flatten(node: Any, prefix: str) -> list[tuple[str, str]]:
    if isinstance(node, dict):
        out = []
        for k, v in node.items():
            out.extend(_flatten(v, f"{prefix}.{k}"))
        return out
    if isinstance(node, list):
        return [(prefix, ", ".join(str(x) for x in node))]
    return [(prefix, "" if node is None else str(node))]


def spec_at(schema: dict, dotted: str) -> dict:
    """The schema entry for a dotted path like 'workflow.closed_when.values'. Used so the
    round trip asks the schema what a field is instead of guessing from the text - guessing
    turned 'means merged, not accepted.' into a two-item list, which is the kind of bug that
    only shows up when somebody's sentence happens to contain a comma."""
    node = schema.get("properties") or {}
    spec: dict = {}
    for part in dotted.split("."):
        spec = (node.get(part) or {}) if isinstance(node, dict) else {}
        if not spec:
            return {}
        node = spec.get("properties") or ((spec.get("items") or {}).get("properties")) or {}
    return spec


def unflatten(rows: list[dict], schema: dict | None = None) -> dict[tuple[str, str], dict]:
    """The inverse: workbook rows back into {(scope, id): {section: {...}}}.

    With a schema, types come from it. Without one, a value stays a string - which is wrong
    less often than a guess.
    """
    out: dict[tuple[str, str], dict] = {}
    for row in rows:
        scope, rid = (row.get("scope") or "project"), row.get("id")
        path, value = row.get("setting"), row.get("value")
        if not (rid and path):
            continue
        parts = str(path).split(".")
        node = out.setdefault((scope, rid), {})
        for part in parts[:-1]:
            node = node.setdefault(part, {})

        v: Any = value
        spec = spec_at(schema, str(path)) if schema else {}
        t = spec.get("type")
        types = set(t) if isinstance(t, list) else {t}
        if isinstance(value, str):
            if "array" in types:
                v = [x.strip() for x in value.split(",") if x.strip()]
            elif "boolean" in types:
                v = value.strip().lower() in ("yes", "true", "1", "on")
            elif "integer" in types and value.strip():
                try:
                    v = int(float(value))
                except ValueError:
                    v = None
            elif "number" in types and value.strip():
                try:
                    v = float(value)
                except ValueError:
                    v = None
            elif not spec:
                # No schema entry, usually an adapter-specific option. Keep booleans, leave
                # everything else as written rather than inventing a list.
                if value.strip().lower() in ("true", "false"):
                    v = value.strip().lower() == "true"
        elif isinstance(value, bool) and "array" in types:
            v = [value]
        node[parts[-1]] = v
    return out


def list_projects(profile: dict) -> list[dict]:
    """Every project with the account it belongs to, for listings and error messages."""
    accounts = {a.get("id"): a for a in (profile.get("accounts") or [])}
    return [
        {
            "id": p.get("id"),
            "name": p.get("name"),
            "account": p.get("account"),
            "account_name": (accounts.get(p.get("account")) or {}).get("name"),
            "pms_project_id": p.get("pms_project_id"),
            "adapter": (resolve(profile, p.get("id"))[0].get("tracker") or {}).get("adapter"),
        }
        for p in (profile.get("projects") or [])
    ]


if __name__ == "__main__":
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="Show a profile as it applies to one project.")
    ap.add_argument("--profile", required=True, type=Path)
    ap.add_argument("--project")
    ap.add_argument("--section", help="Print just this section.")
    ap.add_argument("--list", action="store_true", help="List the projects and what each resolves to.")
    a = ap.parse_args()

    profile = load(a.profile)

    if a.list:
        rows = list_projects(profile)
        if not rows:
            print("This profile has no projects yet.")
            raise SystemExit(0)
        w = max(len(str(r["id"])) for r in rows)
        print(f"{'project'.ljust(w)}  {'account':<12}{'adapter':<9}{'PMS':<7}name")
        for r in rows:
            print(f"{str(r['id']).ljust(w)}  {str(r['account'] or '-'):<12}"
                  f"{str(r['adapter'] or '-'):<9}{str(r['pms_project_id'] or '-'):<7}{r['name'] or ''}")
        over = describe_overrides(profile)
        if over:
            print(f"\nOverrides ({len(over)}):")
            w = max(len(o["setting"]) for o in over) + 2
            for o in over:
                print(f"  {o['scope']:<8}{str(o['id']):<16}{o['setting'].ljust(w)}{o['value']}")
        raise SystemExit(0)

    merged, project = resolve(profile, a.project)
    merged.pop("_project", None)
    merged.pop("_account", None)
    if a.section:
        print(json.dumps(merged.get(a.section), indent=2))
    else:
        print(json.dumps(merged, indent=2))
