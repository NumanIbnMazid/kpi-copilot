#!/usr/bin/env python3
"""
One command for a whole KPI run.

The pipeline was always seven steps, and running them as seven shell commands made the run
feel slow for a reason that has nothing to do with how long the work takes: the arithmetic
is a fraction of a second, but each command is a separate round trip, and between them
somebody - or some assistant - has to decide what comes next. This does the deterministic
part in one process and ends with the only thing that genuinely needs a person or a search:
a short, specific list of the facts the tracker could not answer.

That ordering is the point. Reading chat and mail *before* computing means hunting for
evidence the board may already hold. Computing first turns an open-ended search into a
shopping list with ticket numbers on it.

    run.py            --profile p.yaml --project acme-web      # preflight -> sheet
    run.py review     --profile p.yaml --project acme-web      # fold edits back in, recompute
    run.py push       --profile p.yaml --project acme-web --apply

Every step is the same code the individual scripts run; nothing here computes anything of
its own. `--verbose` prints each step's own output instead of folding it away.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import importlib.util
import io
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from profile_lib import load as load_profile, resolve  # noqa: E402

ADAPTERS = {"asana", "jira", "csv"}


def _module(path: Path, name: str):
    """Load a script as a module so the whole run is one process. Two adapters are both
    called extract.py, hence the explicit name."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class Steps:
    """Runs each step, keeps its output and its timing, and stops at the first real failure."""

    def __init__(self, verbose: bool) -> None:
        self.verbose = verbose
        self.timings: list[tuple[str, float]] = []
        self.output: dict[str, str] = {}

    def run(self, label: str, fn: Callable[[], int], ok: tuple[int, ...] = (0,)) -> int:
        buf = io.StringIO()
        start = time.time()
        try:
            with contextlib.redirect_stdout(buf):
                code = fn()
        except SystemExit as e:                       # argparse and friends
            code = int(e.code or 0)
        finally:
            self.timings.append((label, time.time() - start))
        text = buf.getvalue()
        self.output[label] = text
        if self.verbose and text.strip():
            print(text.rstrip())
        if code not in ok:
            print(f"\n{label} failed (exit {code}).", file=sys.stderr)
            if not self.verbose and text.strip():
                print(text.rstrip(), file=sys.stderr)
        return code


# --------------------------------------------------------------------------------------
# The shopping list: what the board could not answer, and what would answer it
# --------------------------------------------------------------------------------------

# What counts as a missing fact, per field: what it decides, where the answer usually is,
# and - the part that matters - when its absence is actually a gap.
#
# A blank `met_commitment` on an item nobody committed to is not a gap, it is the correct
# answer: Delivery Commitment measures promises kept, so an item with no promise is not
# evidence either way. Sending somebody to search chat for it wastes the hour this list
# exists to save.
def _done(task: dict) -> bool:
    return bool(task.get("delivered") or task.get("closed"))


MISSING_TASK = {
    "understood": ("Requirement Comprehension", "the ticket's own comments",
                   lambda t: t.get("type") != "Excluded"),
    "met_commitment": ("Delivery Commitment", "the commitment thread, or the plan",
                       lambda t: bool(t.get("commit_date"))),
    "met_client_date": ("the client-date check", "the client thread",
                        lambda t: bool(t.get("client_date"))),
    "reopened": ("Rework Rate", "the ticket's status history", _done),
    "hours_dev": ("Velocity and Estimation Accuracy", "the estimates sheet", _done),
}
MISSING_DEFECT = {
    "phase": ("Escaped Defect Rate", "when it was reported, against the handover date",
              lambda d: True),
    "rejected": ("Defect Rejection Rate", "the triage decision on the report",
                 lambda d: True),
}


def _count(n: int, singular: str, plural: str) -> str:
    """'1 report', not '1 reports'. Small, and the thing people notice first."""
    return f"{n} {singular if n == 1 else plural}"


def shopping_list(kif: dict, results: dict, limit: int = 12) -> list[str]:
    """Name the facts that are actually missing, with the items they belong to. A run that
    says 'look in chat' costs an hour; a run that says 'ACME-101 and ACME-102 have no
    comprehension judgement' is answered in a minute."""
    lines: list[str] = []

    for per in results.get("periods", []):
        for m in per.get("measures", []):
            for g in m.get("gaps") or []:
                lines.append(f"{per['period']} · {m['name']}: {g}")

    def group(rows: list[dict], table: dict, singular: str, plural: str) -> None:
        for field, (drives, where, applies) in table.items():
            hits = [r.get("key") or "?" for r in rows
                    if r.get(field) in (None, "") and applies(r)]
            if not hits:
                continue
            shown = ", ".join(hits[:limit]) + (f" (+{len(hits) - limit} more)"
                                               if len(hits) > limit else "")
            verb = "has" if len(hits) == 1 else "have"
            lines.append(f"{_count(len(hits), singular, plural)} {verb} no '{field}' — "
                         f"decides {drives}. Usually in {where}: {shown}")

    group(kif.get("tasks") or [], MISSING_TASK, "task", "tasks")
    group(kif.get("defects") or [], MISSING_DEFECT, "report", "reports")

    for p in kif.get("periods") or []:
        if not p.get("handover_date"):
            lines.append(f"{p.get('name')} has no handover date — decides Escaped Defect "
                         f"Rate and the client-date check. Usually in the release announcement.")
    return lines


def _measure_lines(results: dict) -> tuple[list[str], int, int, int]:
    rows, met, notmet, notmeas = [], 0, 0, 0
    for per in results.get("periods", []):
        for m in per.get("measures", []):
            status = m.get("status")
            met += status == "Met"
            notmet += status == "Not met"
            notmeas += status == "Not measured"
            mark = {"Met": "ok  ", "Not met": "MISS", "Not measured": "  ? "}.get(status, "    ")
            value = m.get("value")
            shown = "—" if value is None else (f"{value:g}" if isinstance(value, (int, float))
                                               else str(value))
            rows.append(f"  {mark} {per['period'][:22]:<22} {m['name'][:26]:<26} "
                        f"{shown:>7}{m.get('unit') or '':<2}")
    return rows, met, notmet, notmeas


def _report(steps: Steps, out_dir: Path, kif: dict, results: dict, reasons: dict) -> None:
    rows, met, notmet, notmeas = _measure_lines(results)
    print("\n".join(rows))
    print(f"\n  {met} met · {notmet} not met · {notmeas} not measured")

    needs = [f"{p['period']} · {m['name']}"
             for p in results.get("periods", []) for m in p.get("measures", [])
             if m.get("status") == "Not met" and not (reasons.get(p["period"]) or {}).get(m["name"])]
    if needs:
        print(f"\nA missed KPI without a reason is the one thing PMS will not accept. "
              f"{len(needs)} need one:")
        for n in needs[:12]:
            print(f"  · {n}")

    gaps = shopping_list(kif, results)
    if gaps:
        print(f"\nWhat the tracker could not answer ({len(gaps)}). Look these up now - and "
              f"only these:")
        for g in gaps[:20]:
            print(f"  · {g}")
        if len(gaps) > 20:
            print(f"  · ... and {len(gaps) - 20} more, in the Gaps tab")
    else:
        print("\nThe tracker answered everything. No searching needed.")

    total = sum(t for _, t in steps.timings)
    print(f"\nFiles in {out_dir}:  tracker.xlsx  results.json  report.md  payloads.json  "
          f"run.kif.json")
    print("  " + "  ".join(f"{k} {v:.2f}s" for k, v in steps.timings) + f"  = {total:.2f}s")
    print("\nNext: fill in the yellow cells in tracker.xlsx, then  run.py review  to fold "
          "them back in.")


# --------------------------------------------------------------------------------------
# the passes
# --------------------------------------------------------------------------------------

def _paths(args, prof_path: Path) -> tuple[Path, Path, Path]:
    out_dir = Path(args.out_dir) if args.out_dir else (
        prof_path.parent / "runs" / (args.date or dt.date.today().isoformat()))
    out_dir.mkdir(parents=True, exist_ok=True)
    reasons = Path(args.reasons) if args.reasons else prof_path.parent / "reasons.yaml"
    manual = Path(args.manual) if args.manual else prof_path.parent / "manual.yaml"
    return out_dir, reasons, manual


def _load_reasons(path: Path) -> dict:
    if not path.exists():
        return {}
    import yaml
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def first_pass(args) -> int:
    prof_path = Path(args.profile)
    profile = load_profile(prof_path)
    resolved, _project = resolve(profile, args.project)
    out_dir, reasons_path, manual_path = _paths(args, prof_path)
    kif_path = out_dir / "run.kif.json"
    steps = Steps(args.verbose)

    tracker = args.adapter or (resolved.get("tracker") or {}).get("adapter")
    if tracker not in ADAPTERS:
        print(f"No adapter for tracker '{tracker}'. Known: {', '.join(sorted(ADAPTERS))}. "
              f"Export the board to CSV and pass --adapter csv, or write one "
              f"(adapters/_contract.md).", file=sys.stderr)
        return 2

    if not args.skip_preflight:
        pf = _module(HERE / "preflight.py", "kpic_preflight")
        argv = ["--profile", str(prof_path)] + (["--project", args.project] if args.project else [])
        code = steps.run("preflight", lambda: pf.main(argv + (["--strict"] if args.strict else [])))
        if code != 0:
            print("\nReadiness is not there yet. The check above says what is missing; fix it, "
                  "or rerun with --skip-preflight to go ahead anyway and let the gaps show.",
                  file=sys.stderr)
            return code

    ad = _module(PLUGIN_ROOT / "adapters" / tracker / "extract.py", f"kpic_adapter_{tracker}")
    argv = ["--profile", str(prof_path), "--out", str(kif_path)]
    if args.project:
        argv += ["--project", args.project]
    if args.from_extract:
        argv += ["--from-extract", str(args.from_extract)]
    if args.file:
        argv += ["--file", str(args.file)]
    if steps.run(f"extract:{tracker}", lambda: ad.main(argv)) != 0:
        return 1

    val = _module(HERE / "validate_kif.py", "kpic_validate")
    if steps.run("validate", lambda: val.main(["--kif", str(kif_path)])) != 0:
        return 1

    return _compute_and_build(steps, args, prof_path, out_dir, kif_path,
                              reasons_path, manual_path)


def _compute_and_build(steps: Steps, args, prof_path: Path, out_dir: Path, kif_path: Path,
                       reasons_path: Path, manual_path: Path) -> int:
    eng = _module(HERE / "kpi_engine.py", "kpic_engine")
    argv = ["--kif", str(kif_path), "--profile", str(prof_path),
            "--out", str(out_dir / "results.json"),
            "--markdown", str(out_dir / "report.md"),
            "--payloads", str(out_dir / "payloads.json")]
    if args.project:
        argv += ["--project", args.project]
    if reasons_path.exists():
        argv += ["--reasons", str(reasons_path)]
    if manual_path.exists():
        argv += ["--manual", str(manual_path)]
    if steps.run("compute", lambda: eng.main(argv)) != 0:
        return 1

    wbk = _module(HERE / "workbook.py", "kpic_workbook")
    argv = ["tracker", "--results", str(out_dir / "results.json"), "--kif", str(kif_path),
            "--profile", str(prof_path), "--out", str(out_dir / "tracker.xlsx")]
    if reasons_path.exists():
        argv += ["--reasons", str(reasons_path)]
    if steps.run("workbook", lambda: wbk.main(argv)) != 0:
        return 1

    kif = json.loads(kif_path.read_text(encoding="utf-8"))
    results = json.loads((out_dir / "results.json").read_text(encoding="utf-8"))
    _report(steps, out_dir, kif, results, _load_reasons(reasons_path))
    return 0


def review_pass(args) -> int:
    """Fold the sheet's edits back into the extract, then recompute and rebuild from it -
    so the sheet, the numbers and PMS cannot end up saying different things."""
    prof_path = Path(args.profile)
    out_dir, reasons_path, manual_path = _paths(args, prof_path)
    kif_path = out_dir / "run.kif.json"
    tracker_xlsx = Path(args.tracker) if args.tracker else out_dir / "tracker.xlsx"
    if not tracker_xlsx.exists():
        print(f"No workbook at {tracker_xlsx}. Run a first pass before reviewing.",
              file=sys.stderr)
        return 2
    steps = Steps(args.verbose)

    wbk = _module(HERE / "workbook.py", "kpic_workbook")
    argv = ["review", "--tracker", str(tracker_xlsx), "--kif", str(kif_path),
            "--results", str(out_dir / "results.json"),
            "--out-kif", str(kif_path), "--out-reasons", str(reasons_path),
            "--out-manual", str(manual_path)]
    if reasons_path.exists():
        argv += ["--reasons", str(reasons_path)]
    if manual_path.exists():
        argv += ["--manual", str(manual_path)]
    if args.by:
        argv += ["--by", args.by]
    if steps.run("review", lambda: wbk.main(argv)) != 0:
        return 1
    if not args.verbose:
        print(steps.output["review"].rstrip())

    return _compute_and_build(steps, args, prof_path, out_dir, kif_path,
                              reasons_path, manual_path)


def push_pass(args) -> int:
    prof_path = Path(args.profile)
    out_dir, _, _ = _paths(args, prof_path)
    steps = Steps(True)
    push = _module(HERE / "pms_push.py", "kpic_push")
    argv = ["--payloads", str(out_dir / "payloads.json"), "--profile", str(prof_path),
            "--log", str(out_dir / "push_log.json"),
            "--apply" if args.apply else "--dry-run"]
    if args.project:
        argv += ["--project", args.project]
    return steps.run("push", lambda: push.main(argv))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", nargs="?", default="run", choices=["run", "review", "push"])
    ap.add_argument("--profile", required=True, type=Path)
    ap.add_argument("--project", help="Which project in the profile. Required when it covers several.")
    ap.add_argument("--date", help="Run folder name. Default: today.")
    ap.add_argument("--out-dir", help="Override the run folder entirely.")
    ap.add_argument("--adapter", help="Force an adapter instead of the one the profile names.")
    ap.add_argument("--from-extract", type=Path, help="Saved browser extract, for the asana adapter.")
    ap.add_argument("--file", type=Path, help="CSV export, for the csv adapter.")
    ap.add_argument("--reasons", type=Path)
    ap.add_argument("--manual", type=Path)
    ap.add_argument("--tracker", type=Path, help="The edited workbook, if it is not in the run folder.")
    ap.add_argument("--by", default="", help="Who is reviewing, recorded against hand-set values.")
    ap.add_argument("--skip-preflight", action="store_true")
    ap.add_argument("--strict", action="store_true", help="Stop unless readiness is complete.")
    ap.add_argument("--apply", action="store_true", help="push: really send it.")
    ap.add_argument("--verbose", action="store_true", help="Print each step's own output.")
    args = ap.parse_args(argv)
    return {"run": first_pass, "review": review_pass, "push": push_pass}[args.stage](args)


if __name__ == "__main__":
    raise SystemExit(main())
