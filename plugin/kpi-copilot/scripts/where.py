#!/usr/bin/env python3
"""
Where does everything live?

The single most common question from somebody who set this up a month ago and now needs to
change one thing. Nothing here is clever: it resolves the paths a run actually uses and says
which exist, so nobody has to guess whether their edits are going to the file the tools read.

    python3 scripts/where.py --profile profile.yaml
    python3 scripts/where.py --profile profile.yaml --project acme-identity
    python3 scripts/where.py --profile profile.yaml --open          # reveal the folder
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from profile_lib import load as load_profile, resolve as resolve_profile  # noqa: E402


def _mark(p: Path) -> str:
    if p.is_dir():
        n = sum(1 for _ in p.iterdir()) if p.exists() else 0
        return f"exists, {n} item{'' if n == 1 else 's'}"
    return "exists" if p.exists() else "not created yet"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Print where every file this uses lives.")
    ap.add_argument("--profile", required=True, type=Path)
    ap.add_argument("--project", help="Resolve output paths for one project.")
    ap.add_argument("--open", action="store_true", help="Open the profile's folder in the file manager.")
    a = ap.parse_args(argv)

    profile_path = a.profile.resolve()
    home = profile_path.parent
    raw = load_profile(profile_path) if profile_path.exists() else {}
    merged, project = (resolve_profile(raw, a.project) if raw.get("projects") else (raw, {}))
    out_cfg = merged.get("output") or {}
    org = merged.get("organization") or {}

    run_folder = Path(out_cfg.get("run_folder") or "runs")
    if not run_folder.is_absolute():
        run_folder = home / run_folder

    rows: list[tuple[str, Path | str, str]] = [
        ("Your profile", profile_path, _mark(profile_path)),
        ("  edit it as a spreadsheet", home / "KPI Profile Workbook.xlsx",
         _mark(home / "KPI Profile Workbook.xlsx")),
        ("Readiness checklist", home / "preflight.json", _mark(home / "preflight.json")),
        ("The 'why' text for notes", home / "reasons.yaml", _mark(home / "reasons.yaml")),
        ("Values set by hand", home / "manual.yaml", _mark(home / "manual.yaml")),
        ("Run output", run_folder, _mark(run_folder)),
        ("KPI definitions cached from PMS",
         PLUGIN_ROOT / "schemas" / (org.get("kpi_registry") or "kpi_registry.json"),
         _mark(PLUGIN_ROOT / "schemas" / (org.get("kpi_registry") or "kpi_registry.json"))),
        ("The plugin itself", PLUGIN_ROOT, _mark(PLUGIN_ROOT)),
    ]

    print(f"\nEverything for {profile_path.name}"
          + (f", project '{project.get('id')}'" if project.get("id") else "") + "\n")
    w = max(len(r[0]) for r in rows)
    for label, path, state in rows:
        print(f"  {label.ljust(w)}  {path}")
        print(f"  {' ' * w}  ({state})")

    print("\nWhere results go")
    wb = out_cfg.get("workbook")
    loc = out_cfg.get("workbook_location") or "(not set)"
    if wb == "google-sheets":
        print(f"  Working file        a Google Sheet in Drive folder {loc}")
        tpl = out_cfg.get("workbook_template")
        print(f"  Copied from         {tpl if tpl else '(no template - a fresh sheet is built)'}")
    elif wb == "xlsx":
        target = Path(loc) if loc != "(not set)" else run_folder
        if not target.is_absolute():
            target = home / target
        print(f"  Working file        an .xlsx in {target}")
    else:
        print("  Working file        none - results are printed only")
    print(f"  PMS                 {org.get('pms_base_url', '(not set)')}"
          f"  (mode: {out_cfg.get('mode', 'not set')})")
    if project.get("pms_project_id"):
        print(f"  This project        {org.get('pms_base_url','')}/all-projects/"
              f"{project['pms_project_id']}/kpis")

    if raw.get("projects"):
        print("\nProjects in this profile")
        for p in raw["projects"]:
            m, _ = resolve_profile(raw, p.get("id"))
            print(f"  {str(p.get('id')):<18} account {str(p.get('account') or '-'):<12}"
                  f" adapter {str((m.get('tracker') or {}).get('adapter') or '-'):<8}"
                  f" PMS {p.get('pms_project_id') or '-'}")

    print("\nTo change something")
    print(f"  the spreadsheet way   python3 scripts/workbook.py read --xlsx \"{home / 'KPI Profile Workbook.xlsx'}\" \\")
    print(f"                          --out \"{profile_path}\"")
    print(f"  the text way          open {profile_path} in any editor, then")
    print(f"                          python3 scripts/profile_tool.py validate --profile \"{profile_path}\"")
    print(f"  what a setting means  python3 scripts/profile_tool.py explain --key workflow.delivered_when")
    print()

    if a.open:
        cmd = {"darwin": ["open"], "win32": ["explorer"]}.get(sys.platform, ["xdg-open"])
        subprocess.run(cmd + [str(home)], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
