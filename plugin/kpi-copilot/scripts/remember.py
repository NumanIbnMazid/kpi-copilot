#!/usr/bin/env python3
"""
Write something learned in conversation into the profile, so it holds next time.

People configure this tool by talking, not by editing YAML. "Put the KPI sheets in the
Northwind Drive folder." "Always show me the previous period next to the new one." "Never push
on a Friday." "The #acme-delivery channel is where builds get announced."

Every one of those is a setting. Acted on once and forgotten, the person has to say it again
next month and wonders why the tool never learns. Written into the profile, it holds - and,
just as important, the next person can see it and knows why it is there.

Three rules, and they are the whole design:

  1. **Ask first.** This never runs without the person having agreed to it. A tool that
     rewrites your configuration because it thought it understood you is worse than one that
     forgets.
  2. **Record why.** Every change carries the sentence it came from. Six months later, "why
     is the workbook location set to this folder" has an answer.
  3. **Validate, or roll back.** A profile that no longer loads is a worse outcome than a
     setting that did not stick, so the write is reverted if validation fails.

Usage:
    remember.py --profile p.yaml --set output.workbook_location=1ZuOaAl... \\
        --why "asked in chat: keep the KPI sheets in the Northwind Drive folder"

    remember.py --profile p.yaml --add custom_instructions.always="Show the previous period" \\
        --why "asked in chat"

    remember.py --profile p.yaml --scope account:northwind --set output.mode=review-only \\
        --why "Northwind numbers are entered by hand for now"

    remember.py --profile p.yaml --tool id=slack-acme,kind=chat,name=#acme-delivery \\
        --why "named in chat as where builds are announced"

    remember.py --profile p.yaml --history          # what has been learned, and why
"""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from profile_lib import OVERRIDABLE, load as load_profile  # noqa: E402


def _dump(data: Any, path: Path) -> None:
    import yaml  # type: ignore
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100),
                    encoding="utf-8")


def _coerce(text: str) -> Any:
    """'yes' is a boolean, '12' is a number, 'a, b' is a list, everything else is text."""
    t = text.strip()
    low = t.lower()
    if low in ("yes", "true"):
        return True
    if low in ("no", "false"):
        return False
    if low in ("null", "none", ""):
        return None
    try:
        return int(t) if t.lstrip("-").isdigit() else float(t)
    except ValueError:
        pass
    return t


def _target(profile: dict, scope: str) -> tuple[dict, str]:
    """Where the setting goes: the profile itself, or an account's / project's overrides."""
    if scope in ("", "profile", None):
        return profile, "profile defaults"
    kind, _, ident = scope.partition(":")
    bucket = {"account": "accounts", "project": "projects"}.get(kind)
    if not bucket or not ident:
        raise SystemExit(f"--scope must be 'profile', 'account:<id>' or 'project:<id>', not '{scope}'.")
    row = next((r for r in (profile.get(bucket) or []) if r.get("id") == ident), None)
    if row is None:
        known = ", ".join(str(r.get("id")) for r in (profile.get(bucket) or [])) or "none"
        raise SystemExit(f"No {kind} called '{ident}'. Known: {known}.")
    return row.setdefault("overrides", {}), f"{kind} '{ident}'"


def _apply(node: dict, dotted: str, value: Any, append: bool) -> tuple[Any, Any]:
    parts = dotted.split(".")
    for part in parts[:-1]:
        nxt = node.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            node[part] = nxt
        node = nxt
    leaf = parts[-1]
    before = copy.deepcopy(node.get(leaf))
    if append:
        current = node.get(leaf)
        if not isinstance(current, list):
            current = [] if current in (None, "") else [current]
        if value not in current:
            current.append(value)
        node[leaf] = current
    else:
        node[leaf] = value
    return before, node[leaf]


def _parse_tool(spec: str) -> dict:
    out: dict = {}
    for part in spec.split(","):
        k, _, v = part.partition("=")
        k, v = k.strip(), v.strip()
        if not k:
            continue
        if k in ("used_for", "accounts", "projects", "people"):
            out[k] = [x.strip() for x in v.split("|") if x.strip()]
        elif k == "client_facing":
            out[k] = v.lower() in ("yes", "true", "1")
        else:
            out[k] = v
    if not out.get("id"):
        raise SystemExit("A tool needs at least id=, kind= and name=.")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write a learned setting into the profile.")
    ap.add_argument("--profile", required=True, type=Path)
    ap.add_argument("--set", dest="sets", action="append", default=[], metavar="KEY=VALUE")
    ap.add_argument("--add", dest="adds", action="append", default=[], metavar="KEY=VALUE",
                    help="Append to a list setting rather than replacing it.")
    ap.add_argument("--tool", dest="tools", action="append", default=[],
                    metavar="id=..,kind=..,name=..", help="Add or update a Tools entry.")
    ap.add_argument("--scope", default="profile",
                    help="profile | account:<id> | project:<id>. Where the setting belongs.")
    ap.add_argument("--why", default="", help="The sentence this came from. Required for a change.")
    ap.add_argument("--by", default="", help="Who asked.")
    ap.add_argument("--history", action="store_true", help="Show what has been learned, and why.")
    ap.add_argument("--dry-run", action="store_true", help="Show the change without writing.")
    a = ap.parse_args(argv)

    profile = load_profile(a.profile)

    if a.history:
        learned = profile.get("learned") or []
        if not learned:
            print("Nothing has been learned into this profile yet.")
            return 0
        print(f"{len(learned)} setting(s) learned from conversation:\n")
        for e in learned:
            scope = f" [{e['scope']}]" if e.get("scope") not in (None, "profile defaults") else ""
            print(f"  {e.get('at', '?')}  {e.get('setting')}{scope}")
            print(f"              {e.get('before')!r} -> {e.get('after')!r}")
            print(f"              {e.get('why')}" + (f"  (asked by {e['by']})" if e.get("by") else ""))
        return 0

    if not (a.sets or a.adds or a.tools):
        print("Nothing to do. Pass --set, --add, --tool or --history.", file=sys.stderr)
        return 2
    if not a.why:
        print("--why is required. It is written next to the setting, so that six months from now "
              "somebody can tell why it is set that way.", file=sys.stderr)
        return 2

    original = copy.deepcopy(profile)
    node, where = _target(profile, a.scope)
    changes: list[dict] = []

    for spec, append in [(s, False) for s in a.sets] + [(s, True) for s in a.adds]:
        key, _, raw = spec.partition("=")
        key = key.strip()
        if not key or "=" not in spec:
            raise SystemExit(f"Expected KEY=VALUE, got '{spec}'.")
        section = key.split(".")[0]
        if where != "profile defaults" and section not in OVERRIDABLE:
            raise SystemExit(
                f"'{section}' cannot be set on {where} - only {', '.join(OVERRIDABLE)} can. "
                f"Set it at the profile level instead."
            )
        before, after = _apply(node, key, _coerce(raw), append)
        changes.append({"setting": key, "scope": where, "before": before, "after": after})

    for spec in a.tools:
        entry = _parse_tool(spec)
        tools = profile.setdefault("tools", [])
        existing = next((t for t in tools if t.get("id") == entry["id"]), None)
        if existing:
            before = copy.deepcopy(existing)
            existing.update(entry)
            changes.append({"setting": f"tools[{entry['id']}]", "scope": "profile defaults",
                            "before": before, "after": copy.deepcopy(existing)})
        else:
            tools.append(entry)
            changes.append({"setting": f"tools[{entry['id']}]", "scope": "profile defaults",
                            "before": None, "after": entry})

    stamp = date.today().isoformat()
    profile.setdefault("learned", []).extend(
        {**c, "at": stamp, "why": a.why, **({"by": a.by} if a.by else {})} for c in changes
    )

    print(f"{len(changes)} change(s) to {a.profile.name}:\n")
    for c in changes:
        scope = "" if c["scope"] == "profile defaults" else f" [{c['scope']}]"
        print(f"  {c['setting']}{scope}")
        print(f"    {c['before']!r} -> {c['after']!r}")
    print(f"\n  because: {a.why}")

    if a.dry_run:
        print("\nDry run. Nothing written.")
        return 0

    _dump(profile, a.profile)

    # Validate, and put the old file back rather than leaving a profile that will not load.
    r = subprocess.run([sys.executable, str(HERE / "profile_tool.py"), "validate",
                        "--profile", str(a.profile)], capture_output=True, text=True)
    if r.returncode != 0:
        _dump(original, a.profile)
        print("\nThat change made the profile invalid, so it was rolled back:\n", file=sys.stderr)
        print(r.stdout, file=sys.stderr)
        return 1

    print(f"\nWritten to {a.profile}. It will apply from the next run.")
    print("Rebuild the workbook so the spreadsheet view matches:")
    print(f"  python3 scripts/workbook.py build --profile {a.profile} --out \"KPI Profile Workbook.xlsx\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
