#!/usr/bin/env python3
"""
Send computed KPIs to PMS - or, much more often, show exactly what sending them would do.

The dry run and the real push read the same payload file and take the same code path up to
the last moment, so they cannot disagree about what was going to happen. That property is
the reason this is a separate script rather than a flag on the engine.

Four guards, and none of them can be turned off from a config file alone:

  1. The profile's output mode decides what is allowed. `review-only` cannot push at all.
  2. `--apply` on a profile set to `auto-push` still requires `output.unattended: true`.
  3. Anything outside the KPI's PMS range is clamped, and the note says the real figure.
  4. After a write, every value, note and name is read back and compared. A mismatch is
     reported as a failure, not smoothed over.

Usage:
    python3 pms_push.py --payloads payloads.json --profile profile.yaml --dry-run
    python3 pms_push.py --payloads payloads.json --profile profile.yaml --apply
    python3 pms_push.py --payloads payloads.json --profile profile.yaml --clipboard
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MODES_THAT_MAY_WRITE = {"assisted-push", "auto-push"}

sys.path.insert(0, str(Path(__file__).resolve().parent))
from profile_lib import load as load_profile, resolve as resolve_profile  # noqa: E402



def _load(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        import yaml  # type: ignore
        return yaml.safe_load(text)
    return json.loads(text)


def _num(v) -> str:
    """24, not 24.0. A report that prints 24.0 looks like it came out of a machine that was
    not being read by anyone."""
    if v is None:
        return ""
    if isinstance(v, (int, float)) and abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def _clean(note: str) -> str:
    """PMS notes are plain text. Anything that slipped through with a URL gets it removed
    here as a last line of defence."""
    note = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", note or "")
    note = re.sub(r"https?://\S+", "", note)
    return re.sub(r"\s{2,}", " ", note).strip()


def _api(base: str, path: str, method: str = "GET", body: dict | None = None,
         token: str | None = None, extra: dict | None = None) -> Any:
    url = base.rstrip("/") + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Accept": "application/json", "Content-Type": "application/json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for k, v in (extra or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}


def read_current(base: str, project_id: int, token: str | None) -> dict:
    """What PMS holds right now, so the diff is against reality rather than against the last
    thing we sent."""
    try:
        data = _api(base, f"/api/projects/{project_id}/kpis?numberOfPeriodToTake=12&includePeriods=true",
                    token=token)
    except Exception as e:  # noqa: BLE001
        print(f"Could not read current values from PMS ({type(e).__name__}). "
              f"The diff below shows what would be sent, not what would change.", file=sys.stderr)
        return {}
    current: dict = {}
    for kpi in (data.get("kpis") or data.get("data") or []):
        for per in (kpi.get("periods") or []):
            pid = per.get("periodId") or (per.get("period") or {}).get("id")
            val = per.get("periodKpiValue") or {}
            current.setdefault(pid, {})[kpi.get("name")] = {
                "value": val.get("value"), "note": val.get("note"),
            }
    return current


def diff_lines(payload: dict, current: dict) -> list[str]:
    pid = payload.get("periodId")
    have = current.get(pid, {})
    out = []
    for k in payload.get("kpis", []):
        old = have.get(k["name"])
        if old is None:
            out.append(f"  {k['name']:<22} (new)        -> {_num(k['value'])}")
        elif old.get("value") != k["value"]:
            out.append(f"  {k['name']:<22} {_num(old.get('value'))} -> {_num(k['value'])}")
        elif _clean(old.get("note") or "") != _clean(k["note"]):
            out.append(f"  {k['name']:<22} {_num(k['value'])} (same); note changed")
        else:
            out.append(f"  {k['name']:<22} {_num(k['value'])} (no change)")
    for s in payload.get("skipped", []):
        out.append(f"  {s['name']:<22} not sent: {s['reason'][:80]}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Show or send KPI values to PMS.")
    ap.add_argument("--payloads", required=True, type=Path)
    ap.add_argument("--profile", required=True, type=Path)
    ap.add_argument("--project", help="Which project in the profile. Its account may set a different output mode.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--clipboard", action="store_true",
                    help="Print a block to paste into PMS by hand. The review-only path.")
    ap.add_argument("--log", type=Path)
    a = ap.parse_args(argv)

    payloads = _load(a.payloads)
    # Resolve for the project: an account can set a different output mode, so pushing for
    # one client and reviewing by hand for another is a profile setting, not two profiles.
    profile = resolve_profile(load_profile(a.profile), a.project)[0]
    out_cfg = profile.get("output") or {}
    mode = out_cfg.get("mode", "assisted-push")
    base = (profile.get("organization") or {}).get("pms_base_url", "")
    token = os.environ.get("PMS_TOKEN")

    for p in payloads:
        for k in p.get("kpis", []):
            k["note"] = _clean(k["note"])
        p["description"] = _clean(p.get("description", ""))

    # -- the copy-paste path: no network at all --------------------------------------
    if a.clipboard or (mode == "review-only" and not a.apply):
        print(f"Output mode is '{mode}'. Nothing will be sent to PMS.\n")
        for p in payloads:
            print(f"=== {p['name']}  (PMS project {p.get('projectId')}, period {p.get('periodId') or 'not set'}) ===")
            print(f"Description: {p['description']}\n")
            for k in p.get("kpis", []):
                print(f"{k['name']}: {_num(k['value'])}")
                print(f"  {k['note']}\n")
            for s in p.get("skipped", []):
                print(f"{s['name']}: leave blank - {s['reason'][:120]}\n")
            print()
        return 0

    # -- diff ------------------------------------------------------------------------
    project_id = next((p.get("projectId") for p in payloads if p.get("projectId")), None)
    current = read_current(base, project_id, token) if project_id else {}

    print(f"PMS {base}   project {project_id}   mode '{mode}'\n")
    blocked = False
    for p in payloads:
        print(f"=== {p['name']}  (period {p.get('periodId') or 'MISSING'}) ===")
        if not p.get("periodId"):
            print("  This period has no PMS period id, so it cannot be updated. Create the period in PMS "
                  "first, then put its id in the profile.")
            blocked = True
        print("\n".join(diff_lines(p, current)) or "  nothing to send")
        print()

    if not a.apply:
        print("Dry run. Nothing was sent.")
        return 0

    # -- guards ----------------------------------------------------------------------
    if mode not in MODES_THAT_MAY_WRITE:
        print(f"Refusing to write: output mode is '{mode}'. Change it in the profile if that is what you want.",
              file=sys.stderr)
        return 2
    if mode == "auto-push" and not out_cfg.get("unattended"):
        print("Refusing to write: mode is 'auto-push' but output.unattended is off, so nobody has approved this.",
              file=sys.stderr)
        return 2
    if blocked:
        print("Refusing to write: at least one period has no PMS period id.", file=sys.stderr)
        return 2
    if not token:
        print("No PMS_TOKEN in the environment, so this script cannot write. Two options: set a token, or let "
              "the run push through the signed-in browser session, which is what most people do.", file=sys.stderr)
        return 2

    # -- write, then read back --------------------------------------------------------
    results, failures = [], 0
    for p in payloads:
        pid = p["periodId"]
        try:
            period = _api(base, f"/api/periods/{pid}", token=token)
            last_modified = period.get("updatedAt")
            body = {
                "name": p["name"],
                "description": p["description"],
                "kpis": [{"kpiId": k["kpiId"], "value": k["value"], "note": k["note"]} for k in p["kpis"]],
            }
            _api(base, f"/api/periods/{pid}/kpis", method="PUT", body=body, token=token,
                 extra={"Last-Modified": last_modified} if last_modified else None)
        except Exception as e:  # noqa: BLE001
            print(f"  {p['name']}: write failed ({type(e).__name__}: {e})", file=sys.stderr)
            failures += 1
            results.append({"period": p["name"], "periodId": pid, "result": f"failed: {e}"})
            continue

        after = read_current(base, p.get("projectId"), token).get(pid, {})
        mismatched = [
            k["name"] for k in p["kpis"]
            if after.get(k["name"], {}).get("value") != k["value"]
            or _clean(after.get(k["name"], {}).get("note") or "") != k["note"]
        ]
        if mismatched:
            print(f"  {p['name']}: written, but read-back disagrees on {', '.join(mismatched)}", file=sys.stderr)
            failures += 1
        else:
            print(f"  {p['name']}: {len(p['kpis'])} KPIs written and verified")
        results.append({
            "period": p["name"], "periodId": pid,
            "result": "verified" if not mismatched else f"mismatch: {', '.join(mismatched)}",
            "kpis": [{"name": k["name"], "value": k["value"]} for k in p["kpis"]],
        })

    log = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "pms": base, "project": project_id, "mode": mode, "results": results}
    (a.log or a.payloads.with_name("push_log.json")).write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(f"\nLog: {a.log or a.payloads.with_name('push_log.json')}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
