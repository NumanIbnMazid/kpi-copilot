#!/usr/bin/env python3
"""Build documentation workbooks from fictional fixtures using the shipped writers.

No live accounts, profile discovery, external sources or production writes are used.
Run with the repository's configured Python environment. Output contains draft reviews.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPTS = ROOT / "plugin" / "kpi-copilot" / "scripts"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="Folder for the four fictional .xlsx files.")
    args = parser.parse_args()
    out = args.out.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    # Explicit fixture paths and --offline prevent any live source acquisition.
    with tempfile.TemporaryDirectory(prefix="kpi-fictional-samples-") as tmp:
        workspace = Path(tmp) / "workspace"
        shutil.copytree(HERE / "workspace", workspace)
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("KPI_", "PMS_", "ASANA_", "JIRA_", "GITHUB_", "GOOGLE_"))}
        for client, project, title in (
            ("northwind", "northwind-q3", "Northwind Demo Release"),
            ("acme", "acme-identity", "Acme Demo Identity"),
        ):
            folder = workspace / "clients" / client
            profile = folder / "profile.yaml"
            commands = [
                ["profile_tool.py", "validate", "--profile", str(profile)],
                ["workbook.py", "build", "--profile", str(profile), "--out",
                 str(out / f"{client.title()} - Profile Workbook.xlsx")],
                ["kpi.py", "run", "--profile", str(profile), "--project", project,
                 "--offline", "--today", "2026-09-18", "--by", "Fictional sample reviewer"],
            ]
            if client == "northwind":
                commands[-1] += ["--board", str(folder / project / "inputs" / "board.json")]
            for script, *argv in commands:
                result = subprocess.run([sys.executable, str(SCRIPTS / script), *argv],
                                        cwd=ROOT, env=env, text=True, capture_output=True)
                if result.returncode:
                    raise SystemExit(result.stdout + result.stderr)
            source = folder / project / f"KPI Tracker - {title}.xlsx"
            shutil.copyfile(source, out / f"{client.title()} - KPI Tracker.xlsx")
            print(f"Built {client.title()} profile and KPI workbooks (fictional draft, offline).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
