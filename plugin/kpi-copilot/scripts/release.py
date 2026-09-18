#!/usr/bin/env python3
"""
Cut a new version of the plugin so installed copies actually pick up your changes.

The thing that surprises everyone: Claude Code installs a plugin by **copying** it into
`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`. Editing this folder afterwards
changes nothing for anyone who installed it - `claude plugin update` will cheerfully report
"already at the latest version" and walk away. The version is the only signal that there is
something new.

And the version lives in two files, which must agree:

  plugin/kpi-copilot/.claude-plugin/plugin.json   -> "version"
  .claude-plugin/marketplace.json                 -> plugins[].version

Bump one and not the other and you get a confusing half-state. That is what this script is
for: it bumps both, runs the self-test first so you do not ship a broken version, and prints
the two commands everyone else needs to run.

    python3 scripts/release.py --patch        # 1.0.1 -> 1.0.2
    python3 scripts/release.py --minor        # 1.0.1 -> 1.1.0
    python3 scripts/release.py --set 2.0.0
    python3 scripts/release.py --check        # what is the state right now

If you are iterating rather than releasing, do not use this at all - run
`claude --plugin-dir <this folder>`, which loads in place with no cache and no version.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent                     # plugin/kpi-copilot
PROJECT_ROOT = PLUGIN_ROOT.parent.parent      # KPI Copilot
PLUGIN_JSON = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = PROJECT_ROOT / ".claude-plugin" / "marketplace.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _entry(market: dict, name: str) -> dict | None:
    return next((p for p in market.get("plugins", []) if p.get("name") == name), None)


def current() -> tuple[str, str | None, str]:
    plugin = _read(PLUGIN_JSON)
    name = plugin["name"]
    market = _read(MARKETPLACE_JSON)
    entry = _entry(market, name)
    return plugin.get("version", "0.0.0"), (entry or {}).get("version"), name


def bump(version: str, part: str) -> str:
    try:
        major, minor, patch = (int(x) for x in version.split("."))
    except ValueError:
        raise SystemExit(f"Version '{version}' is not major.minor.patch, so it cannot be bumped. Use --set.")
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Bump the plugin version in both manifests.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--patch", action="store_const", const="patch", dest="part")
    g.add_argument("--minor", action="store_const", const="minor", dest="part")
    g.add_argument("--major", action="store_const", const="major", dest="part")
    g.add_argument("--set", dest="exact", help="Set an exact version.")
    ap.add_argument("--check", action="store_true", help="Report the state and change nothing.")
    ap.add_argument("--skip-tests", action="store_true", help="Release without running selftest. Say why in the commit.")
    a = ap.parse_args(argv)

    plugin_v, market_v, name = current()

    if a.check or not (a.part or a.exact):
        print(f"plugin.json      {plugin_v}")
        print(f"marketplace.json {market_v or '(no version set)'}")
        if market_v != plugin_v:
            print("\nThese disagree. Installed copies follow the marketplace entry, so bump both "
                  "(--patch) before telling anyone to update.")
        else:
            print("\nIn step. Anyone who has installed it is on this version, or behind it.")
        print(f"\nTo release a change:\n  python3 scripts/release.py --patch\n"
              f"\nThen everyone else runs:\n"
              f"  claude plugin marketplace update {_read(MARKETPLACE_JSON)['name']}\n"
              f"  claude plugin update {name}@{_read(MARKETPLACE_JSON)['name']}\n"
              f"  /reload-plugins        (or restart Claude)")
        return 0

    if not a.skip_tests:
        print("Running the self-test first...")
        r = subprocess.run([sys.executable, "scripts/selftest.py"], cwd=PLUGIN_ROOT,
                           capture_output=True, text=True)
        tail = (r.stdout or "").strip().splitlines()[-1:] or [""]
        print(f"  {tail[0]}")
        if r.returncode != 0:
            print("\nSelf-test failed, so nothing was bumped. Fix it, or pass --skip-tests "
                  "if you genuinely mean to ship this.", file=sys.stderr)
            return 1

    new = a.exact or bump(plugin_v, a.part)

    plugin = _read(PLUGIN_JSON)
    plugin["version"] = new
    _write(PLUGIN_JSON, plugin)

    market = _read(MARKETPLACE_JSON)
    entry = _entry(market, name)
    if entry is None:
        print(f"'{name}' is not listed in {MARKETPLACE_JSON}. Add it, then bump again.", file=sys.stderr)
        return 2
    entry["version"] = new
    _write(MARKETPLACE_JSON, market)

    market_name = market["name"]
    print(f"\n{plugin_v} -> {new}, in both manifests.\n")
    print("On this machine:")
    print(f"  claude plugin marketplace update {market_name}")
    print(f"  claude plugin update {name}@{market_name}")
    print("  /reload-plugins        (or restart Claude)\n")
    print("Everyone else runs the same two commands. If the folder is shared over a drive they")
    print("already have, that is all they need; if it is a git repo, they pull first.\n")
    print("Nothing reaches an installed copy until this version changes - Claude Code installs")
    print("a plugin by copying it, and only the version tells it there is something new.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
