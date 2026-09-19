#!/usr/bin/env python3
"""
KPI Copilot preflight.

Answers one question before anybody wastes an afternoon: is this machine, this account and
this profile actually ready to produce KPIs?

Some things a script can check on its own (Python version, files, folders, whether PMS
answers at all). Some things only a signed-in browser or a person can confirm (is the Drive
connector enabled, can this account see PMS project 101, does the Jira token work). Those
come back as MANUAL with a precise instruction, and the kpi-setup skill walks them one by
one and records the answers here. A manual item that has been confirmed stays confirmed
until its 'checked_at' goes stale.

Every check says three things: what it is, why it matters, and what to do when it fails -
because the person hitting a red line is usually not the person who can fix it, and they
need to know who to ask.

Usage:
    python3 preflight.py --profile profile.yaml [--state preflight.json]
                         [--markdown checklist.md] [--json] [--strict]
    python3 preflight.py --profile profile.yaml --confirm browser-signed-in --by "Numan"
    python3 preflight.py --profile profile.yaml --fail pms-api-reachable --why "403 from /api"
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent

sys.path.insert(0, str(Path(__file__).resolve().parent))
from profile_lib import load as load_profile, resolve as resolve_profile  # noqa: E402


PASS, FAIL, MANUAL, SKIP, WARN = "pass", "fail", "manual", "skip", "warn"
BLOCKING, DEGRADED, OPTIONAL = "blocking", "degraded", "optional"

# How long a human-confirmed item is trusted before we ask again. Sessions expire, tokens
# rotate, people change laptops.
MANUAL_TTL_DAYS = 30


@dataclass
class Check:
    id: str
    group: str
    label: str
    why: str
    fix: str
    severity: str = BLOCKING
    state: str = MANUAL
    detail: str = ""
    checked_at: str | None = None
    checked_by: str | None = None
    owner: str = "you"  # who can actually resolve it: you | IT | PMS admin | tracker admin

    def as_dict(self) -> dict:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _stale(ts: str | None) -> bool:
    if not ts:
        return True
    try:
        when = datetime.fromisoformat(ts)
    except ValueError:
        return True
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - when > timedelta(days=MANUAL_TTL_DAYS)


def _load_any(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except ImportError:
            return None
        return yaml.safe_load(text)
    return json.loads(text)


def _host_reachable(url: str, timeout: float = 6.0) -> tuple[bool, str]:
    """Can this machine reach the host at all. Deliberately not a sign-in test: a 401 or a
    redirect to a login page still proves the network path and DNS work, which is the thing
    that is usually broken (VPN off, wrong network)."""
    if not url:
        return False, "no URL configured"
    try:
        from urllib.parse import urlparse

        host = urlparse(url if "//" in url else "https://" + url).hostname
        if not host:
            return False, "could not parse a hostname out of the URL"
        socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        return False, f"DNS lookup failed for {host}: {e}"
    except Exception as e:  # noqa: BLE001
        return False, str(e)

    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "kpi-copilot-preflight"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        # 401/403/404 all prove we got there.
        return True, f"HTTP {e.code} (host is reachable)"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


# --------------------------------------------------------------------------------------
# the checks
# --------------------------------------------------------------------------------------


def build_checks(profile: dict | None, profile_path: Path | None,
                 raw_profile: dict | None = None) -> list[Check]:
    p = profile or {}
    org = p.get("organization") or {}
    out_cfg = p.get("output") or {}
    tracker = p.get("tracker") or {}
    mode = out_cfg.get("mode", "assisted-push")
    writes_to_pms = mode in ("assisted-push", "auto-push")
    wants_sheets = out_cfg.get("workbook") == "google-sheets"

    checks: list[Check] = []
    add = checks.append

    # ---- 1. Environment -------------------------------------------------------------
    add(Check(
        "python-version", "Environment", "Python 3.9 or newer",
        "The engine, the workbook builder and the adapters are Python.",
        "Install Python 3 from python.org, or run: brew install python3",
        BLOCKING,
        PASS if sys.version_info >= (3, 9) else FAIL,
        f"found {sys.version.split()[0]}",
        _now(),
    ))

    try:
        import yaml  # noqa: F401
        yaml_state, yaml_detail = PASS, "pyyaml present"
    except ImportError:
        yaml_state, yaml_detail = FAIL, "pyyaml missing"
    add(Check(
        "python-yaml", "Environment", "PyYAML installed",
        "The profile is YAML so a person can read and edit it.",
        "pip3 install pyyaml",
        BLOCKING, yaml_state, yaml_detail, _now(),
    ))

    try:
        import openpyxl  # noqa: F401
        xl_state, xl_detail = PASS, "openpyxl present"
    except ImportError:
        xl_state, xl_detail = (FAIL if out_cfg.get("workbook") == "xlsx" else WARN), "openpyxl missing"
    add(Check(
        "python-openpyxl", "Environment", "openpyxl installed",
        "Builds the profile workbook and the Excel tracker.",
        "pip3 install openpyxl",
        BLOCKING if out_cfg.get("workbook") == "xlsx" else OPTIONAL,
        xl_state, xl_detail, _now(),
    ))

    add(Check(
        "claude-code", "Environment", "Claude Code available with an active subscription",
        "The skills, the browser control and the approval steps all run inside Claude Code.",
        "Install the Claude desktop app and sign in. If the org pays for it, ask IT for a seat.",
        BLOCKING,
        PASS if (shutil.which("claude") or os.environ.get("CLAUDE_SESSION_ID")) else MANUAL,
        "detected a Claude session" if os.environ.get("CLAUDE_SESSION_ID") else "confirm in the app",
        _now() if os.environ.get("CLAUDE_SESSION_ID") else None,
    ))

    add(Check(
        "plugin-installed", "Environment", "KPI Copilot plugin is loaded",
        "Without it the /kpi-copilot:* skills do not exist.",
        "claude plugin marketplace add \"<the KPI Copilot folder>\" then claude plugin install "
        "kpi-copilot@pm-tools. Or skip installing: start Claude with --plugin-dir pointing at this folder.",
        BLOCKING,
        PASS if (PLUGIN_ROOT / ".claude-plugin" / "plugin.json").exists() else FAIL,
        f"plugin root {PLUGIN_ROOT}",
        _now(),
    ))

    # ---- 2. Configuration -----------------------------------------------------------
    add(Check(
        "profile-exists", "Configuration", "A profile exists for you",
        "The profile is what makes the run follow your workflow instead of somebody else's.",
        "Run /kpi-copilot:kpi-setup and answer the interview.",
        BLOCKING,
        PASS if (profile_path and profile_path.exists()) else FAIL,
        str(profile_path) if profile_path else "no --profile given",
        _now(),
    ))

    required = ["owner", "organization", "tracker", "conventions", "workflow", "output"]
    missing = [k for k in required if not p.get(k)]
    add(Check(
        "profile-complete", "Configuration", "Profile has every required section",
        "A half-filled profile produces numbers nobody can defend.",
        "Re-run /kpi-copilot:kpi-setup; it resumes where it stopped.",
        BLOCKING,
        PASS if (p and not missing) else FAIL,
        "all sections present" if (p and not missing) else f"missing: {', '.join(missing) or 'the whole file'}",
        _now(),
    ))

    reg_path = PLUGIN_ROOT / "schemas" / (org.get("kpi_registry") or "kpi_registry.json")
    reg_fresh = reg_path.exists()
    reg_detail = "synced from PMS" if reg_fresh else "using the bundled fallback from Sept 2026"
    add(Check(
        "kpi-registry", "Configuration", "KPI definitions synced from PMS",
        "Ids, the default targets and any target this project sets for itself come from PMS, not from a "
        "copy that quietly went out of date.",
        "python3 scripts/kpi_registry.py --refresh  (needs a signed-in PMS session)",
        DEGRADED, PASS if reg_fresh else WARN, reg_detail, _now(),
    ))

    # A profile can cover several projects on several trackers, so check each project's
    # resolved adapter rather than assuming one. A lead on Asana and Jira finds out here that
    # one of the two is missing, not halfway through a run.
    raw = raw_profile or p
    projects = raw.get("projects") or []
    checked: list[tuple[str, str]] = []
    if projects and raw_profile is not None:
        for row in projects:
            try:
                merged, _ = resolve_profile(raw, row.get("id"))
            except SystemExit:
                continue
            checked.append((row.get("id") or "?", (merged.get("tracker") or {}).get("adapter") or ""))
    else:
        checked = [("", tracker.get("adapter") or "")]

    for pid, adapter in checked:
        adapter_dir = PLUGIN_ROOT / "adapters" / (adapter or "")
        label = f"Adapter '{adapter or 'not set'}' exists" + (f" (project {pid})" if pid else "")
        add(Check(
            f"adapter-present{('-' + pid) if pid else ''}", "Configuration", label,
            "The adapter is what turns that project's tracker into something the engine can read.",
            "Pick one of: asana, jira, csv. For anything else run /kpi-copilot:kpi-adapter to write one.",
            BLOCKING,
            PASS if (adapter and adapter_dir.is_dir()) else FAIL,
            f"adapters/{adapter}" if adapter else "tracker.adapter is empty",
            _now(),
        ))

    # ---- 3. Access ------------------------------------------------------------------
    pms_url = org.get("pms_base_url") or ""
    ok, detail = _host_reachable(pms_url) if pms_url else (False, "no PMS URL in the profile")
    add(Check(
        "pms-reachable", "Access", "PMS answers from this machine",
        "If PMS is unreachable there is nowhere to send the result.",
        "Check the VPN and the URL. If the host is right and still unreachable, ask IT.",
        BLOCKING if writes_to_pms else DEGRADED,
        PASS if ok else FAIL, detail, _now(), owner="IT" if not ok else "you",
    ))

    add(Check(
        "pms-account", "Access", "Your account can open the project's KPI page in PMS",
        "Being able to read PMS is not the same as being allowed to see this project.",
        "Open <pms>/all-projects/<id>/kpis in the browser. If it refuses, ask the PMS admin for access to that project.",
        BLOCKING, MANUAL,
        "confirm by opening the page while signed in", None, owner="PMS admin",
    ))

    if writes_to_pms:
        add(Check(
            "pms-write", "Access", "Your account may edit KPIs on that project",
            f"Output mode is '{mode}', which writes to PMS. Read access is not enough.",
            "Try editing one KPI note by hand in PMS. If the field is not editable, ask the PMS admin for the right role.",
            BLOCKING, MANUAL, "confirm once per project", None, owner="PMS admin",
        ))
        add(Check(
            "pms-periods", "Access", "The periods you will push to exist in PMS",
            "The push updates a period by id; it does not invent periods.",
            "Create the period in PMS first, then put its id in the profile or let the run read it back.",
            BLOCKING, MANUAL, "confirm per project", None,
        ))

    tracker_url = tracker.get("url") or ""
    if tracker_url:
        ok, detail = _host_reachable(tracker_url)
        add(Check(
            "tracker-reachable", "Access", "Your issue tracker answers from this machine",
            "Everything starts with reading the board.",
            "Check the URL and the network.",
            BLOCKING, PASS if ok else FAIL, detail, _now(),
        ))

    add(Check(
        "browser-signed-in", "Access", "A browser session signed in to the tracker, PMS and your document store",
        "Claude reads these pages as you. It never types credentials, so the session has to be there already.",
        "Sign in yourself in Claude's browser pane, or connect the Claude in Chrome extension on the work profile. Then re-run this check.",
        BLOCKING, MANUAL, "sign in once; the session is remembered", None,
    ))

    if adapter in ("jira",):
        add(Check(
            "tracker-api-token", "Access", "Jira API token or an authenticated session",
            "The Jira adapter reads through the REST API.",
            "Create an Atlassian API token and put it in the environment as JIRA_TOKEN. Never paste it into a chat or the profile.",
            BLOCKING, MANUAL, "confirm the token works with one request", None, owner="tracker admin",
        ))

    if wants_sheets:
        add(Check(
            "drive-connector", "Access", "Google Drive / Sheets connector enabled",
            "Needed to copy the tracker template and write the working file.",
            "Enable the Google Drive connector for your account in Claude's connector settings, on the work account.",
            BLOCKING, MANUAL, "confirm the connector is on", None,
        ))

    # ---- 4. Data sources ------------------------------------------------------------
    srcs = p.get("sources") or {}
    for label, key, why in (
        ("Agreed scope / project plan", "plan", "Scope and planned dates come from here when the tracker is not the agreed truth."),
        ("Additional effort estimates", "estimates", "Change requests and their hours come from here."),
        ("Timeline / date change log", "timeline", "Date revisions and handovers come from here."),
    ):
        block = srcs.get(key) or {}
        kind = block.get("kind")
        present = bool(kind and kind != "none" and block.get("ref"))
        add(Check(
            f"source-{key}", "Data sources", label, why,
            "Add it on the Sources tab of the profile workbook, or accept that the KPIs it feeds will say 'Not measured' and why.",
            DEGRADED, PASS if present else WARN,
            block.get("ref", "") if present else "not configured - the run will state the gap rather than guess",
            _now(),
        ))

    channels = srcs.get("evidence_channels") or []
    add(Check(
        "evidence-channels", "Data sources", "At least one evidence channel",
        "Dates, handovers and decisions are proved with links. With no channel, those cells come back empty and need filling in by hand.",
        "List your chat spaces or mail threads on the Tools tab and reference them from Sources.",
        DEGRADED, PASS if channels else WARN,
        f"{len(channels)} configured" if channels else "none configured",
        _now(),
    ))

    # ---- 5. Output targets ----------------------------------------------------------
    run_folder = Path(out_cfg.get("run_folder") or "runs")
    if not run_folder.is_absolute() and profile_path:
        run_folder = profile_path.parent / run_folder
    writable = False
    try:
        run_folder.mkdir(parents=True, exist_ok=True)
        probe = run_folder / ".preflight-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        writable = True
    except Exception as e:  # noqa: BLE001
        writable, write_detail = False, str(e)
    add(Check(
        "run-folder", "Output targets", "Run output folder is writable",
        "Each run keeps its extract, results and payload so a number can be traced back months later.",
        "Pick a folder you own in the profile's output.run_folder.",
        BLOCKING, PASS if writable else FAIL,
        str(run_folder) if writable else write_detail, _now(),
    ))

    if wants_sheets and out_cfg.get("workbook_location"):
        add(Check(
            "drive-folder", "Output targets", "You can write to the Drive folder for working files",
            "The run copies a template and edits it there.",
            "Open the folder and confirm you have Editor rights. Ask its owner if not.",
            BLOCKING, MANUAL, out_cfg.get("workbook_location", ""), None,
        ))

    if mode == "auto-push" and not out_cfg.get("unattended"):
        add(Check(
            "unattended-consistency", "Output targets", "auto-push requires unattended to be on",
            "Otherwise the run will stop and wait for a person who is not there.",
            "Either set output.unattended to yes, or change the mode to assisted-push.",
            BLOCKING, FAIL, "mode is auto-push but unattended is off", _now(),
        ))

    add(Check(
        "approval-path", "Output targets", "You know who approves a push",
        "Numbers that reach management should have had a person look at them.",
        "For assisted-push that person is you. If your team wants a second reviewer, name them on the Output tab.",
        OPTIONAL, MANUAL, "confirm once", None,
    ))

    return checks


# --------------------------------------------------------------------------------------
# state, rendering, CLI
# --------------------------------------------------------------------------------------


def merge_state(checks: list[Check], state_path: Path | None) -> list[Check]:
    """Carry forward manual answers a person already gave, unless they have gone stale."""
    if not state_path or not state_path.exists():
        return checks
    try:
        prior = {c["id"]: c for c in json.loads(state_path.read_text(encoding="utf-8")).get("checks", [])}
    except Exception:  # noqa: BLE001
        return checks
    for c in checks:
        old = prior.get(c.id)
        if not old or c.state != MANUAL:
            continue
        if old.get("state") in (PASS, FAIL, SKIP) and not _stale(old.get("checked_at")):
            c.state = old["state"]
            c.detail = old.get("detail") or c.detail
            c.checked_at = old.get("checked_at")
            c.checked_by = old.get("checked_by")
        elif old.get("state") in (PASS, FAIL) and _stale(old.get("checked_at")):
            c.detail = f"confirmed {str(old.get('checked_at'))[:10]}, worth re-checking"
    return checks


ICON = {PASS: "[x]", FAIL: "[!]", MANUAL: "[ ]", WARN: "[~]", SKIP: "[-]"}
WORD = {PASS: "ready", FAIL: "blocked", MANUAL: "needs your confirmation", WARN: "works, but limited", SKIP: "skipped"}


def to_markdown(checks: list[Check], verdict: dict) -> str:
    lines = ["# KPI Copilot - readiness checklist", ""]
    lines.append(
        f"**{verdict['headline']}**  \n"
        f"{verdict['ready']} ready, {verdict['blocked']} blocked, {verdict['manual']} to confirm, "
        f"{verdict['limited']} limited. Checked {datetime.now().strftime('%d %b %Y, %H:%M')}."
    )
    lines.append("")
    for group in ["Environment", "Configuration", "Access", "Data sources", "Output targets"]:
        rows = [c for c in checks if c.group == group]
        if not rows:
            continue
        lines += [f"## {group}", ""]
        for c in rows:
            lines.append(f"- {ICON[c.state]} **{c.label}** - {WORD[c.state]}")
            if c.detail:
                lines.append(f"  - {c.detail}")
            if c.state in (FAIL, MANUAL, WARN):
                lines.append(f"  - *Why it matters:* {c.why}")
                lines.append(f"  - *To fix:* {c.fix}" + (f" (owner: {c.owner})" if c.owner != "you" else ""))
        lines.append("")
    return "\n".join(lines)


def verdict_of(checks: list[Check]) -> dict:
    blocked = [c for c in checks if c.state == FAIL and c.severity == BLOCKING]
    manual = [c for c in checks if c.state == MANUAL and c.severity == BLOCKING]
    limited = [c for c in checks if c.state == WARN]
    ready = [c for c in checks if c.state == PASS]
    if blocked:
        headline = f"Not ready: {len(blocked)} thing{'s' if len(blocked) > 1 else ''} must be fixed first."
    elif manual:
        headline = f"Almost: {len(manual)} item{'s' if len(manual) > 1 else ''} still need your confirmation."
    elif limited:
        headline = "Ready, with some KPIs limited by missing sources."
    else:
        headline = "Ready."
    return {
        "headline": headline,
        "ready": len(ready),
        "blocked": len(blocked),
        "manual": len(manual),
        "limited": len(limited),
        "can_run": not blocked and not manual,
        "blocking_ids": [c.id for c in blocked + manual],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check that everything needed for a KPI run is in place.")
    ap.add_argument("--profile", type=Path)
    ap.add_argument("--project", help="Check readiness for one project. Omitted: every project in the profile.")
    ap.add_argument("--state", type=Path, help="Where confirmations are remembered (default: next to the profile).")
    ap.add_argument("--markdown", type=Path)
    ap.add_argument("--json", action="store_true", help="Print the full result as JSON.")
    ap.add_argument("--strict", action="store_true", help="Exit non-zero unless everything is ready.")
    ap.add_argument("--confirm", metavar="CHECK_ID", help="Record that a manual check passed.")
    ap.add_argument("--fail", metavar="CHECK_ID", help="Record that a manual check failed.")
    ap.add_argument("--skip", metavar="CHECK_ID", help="Record that a check does not apply here.")
    ap.add_argument("--by", default=os.environ.get("USER", "unknown"))
    ap.add_argument("--why", default="")
    args = ap.parse_args(argv)

    profile = _load_any(args.profile) if (args.profile and args.profile.exists()) else None
    state_path = args.state or ((args.profile.parent / "preflight.json") if args.profile else Path("preflight.json"))

    # Resolve for one project when asked; otherwise check the profile as written and every
    # project's adapter.
    resolved = profile
    if profile and args.project:
        resolved = resolve_profile(profile, args.project)[0]
    checks = merge_state(build_checks(resolved, args.profile, profile), state_path)

    for flag, new_state in ((args.confirm, PASS), (args.fail, FAIL), (args.skip, SKIP)):
        if not flag:
            continue
        hit = next((c for c in checks if c.id == flag), None)
        if not hit:
            print(f"No check called '{flag}'. Known ids: {', '.join(c.id for c in checks)}", file=sys.stderr)
            return 2
        hit.state, hit.checked_at, hit.checked_by = new_state, _now(), args.by
        if args.why:
            hit.detail = args.why

    verdict = verdict_of(checks)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"checked_at": _now(), "verdict": verdict, "checks": [c.as_dict() for c in checks]}, indent=2),
        encoding="utf-8",
    )

    if args.markdown:
        args.markdown.write_text(to_markdown(checks, verdict), encoding="utf-8")
    if args.json:
        print(json.dumps({"verdict": verdict, "checks": [c.as_dict() for c in checks]}, indent=2))
    else:
        print(to_markdown(checks, verdict))

    if args.strict and not verdict["can_run"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
