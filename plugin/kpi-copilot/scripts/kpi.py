#!/usr/bin/env python3
"""
KPI Copilot, as one command.

    kpi.py run    --profile p.yaml --project acme-web     everything, to an updated sheet
    kpi.py judge  --profile p.yaml --project acme-web     fold the assistant's answers in, recompute
    kpi.py answer --profile p.yaml --project acme-web --id handover:Sprint\\ 14 --value 2026-08-12
    kpi.py status --profile p.yaml --project acme-web     what is on file, what is waiting - no network
    kpi.py push   --profile p.yaml --project acme-web [--apply]
    kpi.py auth   [asana|jira|github|google]               what needs connecting, and the best way to do it
    kpi.py doctor --profile p.yaml --project acme-web     can it reach what it needs?

It is built to be driven by an assistant - Claude, Cursor, Codex, anything that can run a
command and read a file - and the division of labour is the design:

    scripts move data      the board, the sources and the sheet go API-to-disk-to-API.
                           Nothing bulky ever passes through an assistant's context.
    the assistant judges   only the calls the rules were unsure of, all at once, from one
                           file (judge/queue.json), answered into one file.
    a person decides       what nobody can know from outside - asked once, on the Open
                           Questions tab, and remembered.

`run` always finishes with a sheet, even on the first pass with nothing judged yet: rows the
rules were unsure of are counted the way the rules proposed and marked in the Check column,
so nothing blocks on anybody. Each run ends with NEXT: the one thing, if any, that would
make the numbers better, and the exact command that follows it.

What a run reads is bounded by the profile: the tracker, plus the plan, estimates and
timeline named under `sources`. It does not search chat or mail. If those cannot answer
something, it asks.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import getpass
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import board as B                      # noqa: E402
import classify                        # noqa: E402
import google_api as G                 # noqa: E402
import judge as J                      # noqa: E402
import sources as S                    # noqa: E402
from ledger import Ledger, all_facts, save_facts   # noqa: E402
from profile_lib import load as load_profile, resolve   # noqa: E402

import connect                         # noqa: E402

CONVERTERS = {"csv"}                   # produce finished KIF themselves; there is no board to read


def _module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _version() -> str:
    try:
        return json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")).get("version", "")
    except (OSError, json.JSONDecodeError):
        return ""


class Clock:
    def __init__(self) -> None:
        self.marks: list[tuple[str, float]] = []
        self._t = time.time()

    def lap(self, label: str) -> None:
        now = time.time()
        self.marks.append((label, now - self._t))
        self._t = now

    def line(self) -> str:
        total = sum(t for _, t in self.marks)
        return "  ".join(f"{k} {v:.1f}s" for k, v in self.marks) + f"  = {total:.1f}s"


def _quiet(fn, argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            code = fn(argv)
    except SystemExit as e:
        code = int(e.code or 0)
    return code, buf.getvalue()


class Workspace:
    """Where one project's memory and output live: <folder of the profile>/<project id>/."""

    def __init__(self, args) -> None:
        prof = args.profile or os.environ.get("KPI_PROFILE") or "profile.yaml"
        self.profile_path = Path(prof).expanduser().resolve()
        if not self.profile_path.exists():
            raise SystemExit(f"No profile at {self.profile_path}. Pass --profile, or set KPI_PROFILE. "
                             f"No profile yet? The kpi-setup skill (or docs/02-Start-Here.md) makes one.")
        self.raw = load_profile(self.profile_path)
        from profile_tool import validate
        code, validation = _quiet(validate, self.profile_path)
        if code:
            raise SystemExit("Profile needs correction before running:\n" + validation)
        self.profile, self.project = resolve(self.raw, args.project)
        self.pid = self.project.get("id") or args.project or "project"
        self.base = self.profile_path.parent
        from kpi_registry import resolve_path
        self.registry_path = resolve_path(self.profile_path, self.profile)
        if Path(self.pid).name != self.pid or self.pid in (".", ".."):
            raise SystemExit("Project id must be a single folder name, not a path.")
        self.dir = self.base / self.pid
        self.dir.mkdir(parents=True, exist_ok=True)
        self.ledger = Ledger(self.dir / "ledger.json")
        self.facts = all_facts(self.dir)
        self.facts["extra_rows"] = _yaml_load(self.dir / "facts" / "extra_rows.yaml")
        self.manual = _yaml_load(self.dir / "manual.yaml")
        self._adopt_old_reasons()
        self.today = getattr(args, "today", None) or dt.date.today().isoformat()
        run_label = getattr(args, "date", None) or self.today
        if Path(run_label).name != run_label or run_label in (".", ".."):
            raise SystemExit("Run date must be a single folder label, not a path.")
        self.run_dir = self.dir / "runs" / run_label
        self.preserve_sheet = False
        self.previous_sheet_state = None

    def _adopt_old_reasons(self) -> None:
        """Earlier versions kept reasons, and sometimes a hand-made plan breakdown, beside the
        profile. Pick them up once, so nobody has to redo work they already did."""
        if not self.facts.get("reasons"):
            for cand in (self.project.get("reasons_ref"), "reasons.yaml"):
                p = self.base / cand if cand else None
                if p and p.is_file():
                    self.facts["reasons"] = _yaml_load(p)
                    break
        ref = self.project.get("plan_items_ref")
        if ref and not (self.facts.get("plan") or {}).get("items") and (self.base / ref).is_file():
            old = _yaml_load(self.base / ref)
            rows = old.get("items") or old.get("features") or []
            if rows:
                self.facts["plan"] = {"source": {"id": "plan", "fingerprint": None, "as_of": None,
                                                 "note": f"adopted from {ref}"},
                                      "grain": self.project.get("deliverable_grain") or "board-cards",
                                      "items": rows}

    @property
    def name(self) -> str:
        return self.project.get("name") or self.pid

    def save(self) -> None:
        self.ledger.save()
        for k in ("periods", "plan", "estimates", "reasons"):
            if self.facts.get(k):
                save_facts(self.dir, k, self.facts[k])
        if (self.facts.get("extra_rows") or {}).get("tasks") or (self.facts.get("extra_rows") or {}).get("defects"):
            save_facts(self.dir, "extra_rows", self.facts["extra_rows"])
        if self.manual:
            _yaml_dump(self.dir / "manual.yaml", self.manual)


def _yaml_load(path: Path) -> dict:
    if not path.exists():
        return {}
    import yaml
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _yaml_dump(path: Path, data: dict) -> None:
    import yaml
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")


# --------------------------------------------------------------------------------------
# steps
# --------------------------------------------------------------------------------------

def read_back(ws: Workspace, board_items: dict, args) -> list[str]:
    """Whatever a person typed into the last sheet, filed before anything is rebuilt."""
    import sheet_readback as R
    state = R.load_state(ws.dir / "sheet_state.json")
    ws.previous_sheet_state = state
    if not state:
        return []
    dest = state.get("destination") or {}
    try:
        if dest.get("kind") == "google":
            if args.offline or not G.how_signed_in():
                ws.preserve_sheet = True
                return ["The Google review sheet could not be read. Its link and edit baseline are preserved; "
                        "this run writes a separate local preview. Reconnect Google and run again to merge edits."]
            import sheet_google
            grid = sheet_google.read_grid(dest["id"], list(state["values"]))
        elif dest.get("path") and Path(dest["path"]).exists():
            import sheet_xlsx
            grid = sheet_xlsx.read_grid(Path(dest["path"]))
        else:
            raise ValueError("the previous review workbook is missing")
        return R.fold(state, grid, ws.ledger, ws.facts, ws.manual, board_items, who=args.by or "")
    except Exception as e:
        raise SystemExit(f"The review sheet could not be read ({e}). Nothing will overwrite it. "
                         "Restore access or repair the workbook, then run again.") from e


def reader_for(adapter: str):
    """A tracker's reader: adapters/<name>/api.py, with read() and, optionally, from_raw()."""
    path = PLUGIN_ROOT / "adapters" / adapter / "api.py"
    if not path.exists():
        have = sorted(p.parent.name for p in (PLUGIN_ROOT / "adapters").glob("*/api.py"))
        raise SystemExit(f"No reader for tracker '{adapter}'. Readers: {', '.join(have)}. For anything else, export "
                         f"the board to CSV and use adapter: csv today, or write a reader - it is one small file "
                         f"(adapters/_contract.md; the kpi-adapter skill walks through it).")
    return _module(path, f"kpic_reader_{adapter}")


def get_board(ws: Workspace, args, say) -> dict | None:
    cache = ws.dir / "cache" / "board.json"
    if args.board:
        snap = B.load(Path(args.board))
        if not snap:
            raise SystemExit(f"{args.board} is not a board snapshot.")
        B.save(cache, snap)
        return snap
    trk = ws.profile.get("tracker") or {}
    adapter = args.adapter or trk.get("adapter") or "asana"
    if adapter in CONVERTERS:
        return None
    if args.offline:
        snap = B.load(cache)
        if not snap:
            raise SystemExit("--offline, but no board has been read yet. Run once without it.")
        say("using the board read on " + (snap.get("fetched_at") or "?")[:10])
        return snap
    api = reader_for(adapter)
    conv, scan = ws.profile.get("conventions") or {}, ws.profile.get("scan") or {}
    try:
        if args.from_raw:
            raw = json.loads(Path(args.from_raw).expanduser().read_text(encoding="utf-8"))
            if not hasattr(api, "from_raw"):
                raise SystemExit(f"The {adapter} reader has no signed-in-tab route, so --from-raw does not apply.")
            snap = (api.from_raw(raw, conv.get("key_pattern"), scan.get("comments") or "on-demand", trk.get("key_field"),
                                 (trk.get("options") or {}).get("linked_tasks") or [])
                    if adapter == "asana" else api.from_raw(raw, ws.profile, ws.project))
            expected = str(ws.project.get("tracker_ref") or trk.get("project_ref") or "")
            if expected and str(snap.get("project_ref") or "") != expected:
                raise B.ReaderError("This export belongs to a different tracker project. Export the configured "
                                    "project before running; the previous snapshot has been preserved.")
            if adapter == "asana" and (trk.get("options") or {}).get("include_subtasks") and not snap.get("subtasks_expanded"):
                raise B.ReaderError("This profile includes subtasks, but the export did not expand them. "
                                    "Run kpiSnapshot(projectId, {includeSubtasks: true}) and import the new export.")
            if adapter == "asana":
                wanted = {str(gid) for gid in (trk.get("options") or {}).get("linked_tasks") or []}
                present = {str(item.get("id")) for item in snap.get("items") or []}
                if wanted - present:
                    raise B.ReaderError("The export omits configured linked tasks. Include tracker.options.linked_tasks "
                                        "as linkedTaskIds in kpiSnapshot and import the complete export.")
        else:
            project = dict(ws.project)
            if scan.get("tracker_scope") == "touched-since":
                starts = [p.get("start") for p in (ws.facts.get("periods") or {}).get("periods") or [] if p.get("start")]
                project["_touched_since"] = min(starts) if starts else None
            snap = api.read(project, ws.profile, B.load(cache), say)
    except B.ReaderError as e:
        raise SystemExit(str(e))
    B.save(cache, snap)
    return snap


def legacy_kif(ws: Workspace, args, kif_path: Path) -> int:
    adapter = args.adapter or (ws.profile.get("tracker") or {}).get("adapter")
    mod = _module(PLUGIN_ROOT / "adapters" / adapter / "extract.py", f"kpic_adapter_{adapter}")
    argv = ["--profile", str(ws.profile_path), "--out", str(kif_path), "--project", ws.pid]
    if args.file:
        argv += ["--file", str(args.file)]
    code, text = _quiet(mod.main, argv)
    if code != 0:
        print(text, file=sys.stderr)
    return code


def compute(ws: Workspace, kif_path: Path) -> dict:
    ws.run_dir.mkdir(parents=True, exist_ok=True)
    reasons_path = ws.run_dir / "reasons.used.yaml"
    _yaml_dump(reasons_path, {k: v for k, v in (ws.facts.get("reasons") or {}).items() if not k.startswith("_")})
    val = _module(HERE / "validate_kif.py", "kpic_validate")
    code, text = _quiet(val.main, ["--kif", str(kif_path)])
    if code != 0:
        print(text.rstrip(), file=sys.stderr)
        raise SystemExit("The extract did not validate, so nothing was computed from it.")
    eng = _module(HERE / "kpi_engine.py", "kpic_engine")
    argv = ["--kif", str(kif_path), "--profile", str(ws.profile_path), "--project", ws.pid,
            "--out", str(ws.run_dir / "results.json"), "--markdown", str(ws.run_dir / "report.md"),
            "--payloads", str(ws.run_dir / "payloads.json"), "--reasons", str(reasons_path)]
    argv += ["--registry", str(ws.registry_path)]
    if ws.manual:
        _yaml_dump(ws.dir / "manual.yaml", ws.manual)
        argv += ["--manual", str(ws.dir / "manual.yaml")]
    code, text = _quiet(eng.main, argv)
    if code != 0:
        print(text.rstrip(), file=sys.stderr)
        raise SystemExit("The engine stopped.")
    ws.engine_said = text
    return json.loads((ws.run_dir / "results.json").read_text(encoding="utf-8"))


def what_moved(ws: Workspace, results: dict) -> tuple[list[str], dict]:
    now = {p["period"]: {m["name"]: m.get("value") for m in p.get("measures") or []} for p in results.get("periods") or []}
    last = (ws.ledger.last_run() or {}).get("values") or {}
    lines = []
    for per, kpis in now.items():
        for name, v in kpis.items():
            old = (last.get(per) or {}).get(name, "absent") if last else "absent"
            if last and old != v and old != "absent":
                lines.append(f"{per} · {name}: {_show(old)} -> {_show(v)}")
            elif last and old == "absent":
                lines.append(f"{per} · {name}: new, {_show(v)}")
    return lines, now


def _show(v: Any) -> str:
    return "not measured" if v is None else f"{v:g}" if isinstance(v, (int, float)) else str(v)


def publish(ws: Workspace, kif: dict, results: dict, ctx: dict, args) -> tuple[dict, list[str]]:
    import sheet_model
    import sheet_readback as R
    import sheet_xlsx
    said: list[str] = []
    tabs = sheet_model.build(kif, results, ctx)
    out_cfg = ws.profile.get("output") or {}
    safe = "".join(ch if ch.isalnum() or ch in " -_()[]" else " " for ch in ws.name).strip()
    title = (out_cfg.get("workbook_name") or "[KPI Tracker] {project}").replace("{project}", ws.name)
    local = ws.dir / f"KPI Tracker - {safe}.xlsx"
    if ws.preserve_sheet:
        local = ws.run_dir / f"Preview - {safe}.xlsx"
    try:
        sheet_xlsx.write(tabs, local)
    except PermissionError:
        local = ws.run_dir / local.name
        sheet_xlsx.write(tabs, local)
        said.append(f"The workbook is open in another program, so this run's copy is at {local}.")
    ws.run_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(local, ws.run_dir / "tracker.xlsx")
    dest: dict = {"kind": "xlsx", "path": str(local)}

    wants_google = (out_cfg.get("workbook") == "google-sheets" or out_cfg.get("workbook_file")
                    or out_cfg.get("workbook_location")) and out_cfg.get("workbook") != "xlsx"
    if wants_google and not args.no_publish and not args.offline and not ws.preserve_sheet:
        if not G.how_signed_in():
            said.append("Google Sheet not updated: " + G.NOT_SIGNED_IN +
                        " The local workbook is ready for review. Connect Google or choose local workbook output.")
        else:
            try:
                import sheet_google
                prev = (ws.previous_sheet_state or {}).get("destination") or {}
                g = sheet_google.publish(tabs, out_cfg, title, prev.get("id") if prev.get("kind") == "google" else None)
                dest = {**g, "path": str(local)}
                said.append(("Created" if g["created"] else "Updated") + f" the Google Sheet as {g['as']}: {g['url']}")
                if g.get("warning"):
                    said.append(g["warning"])
            except G.GoogleError as e:
                said.append(f"Google Sheet not updated: {e}")
    previous_dest = (ws.previous_sheet_state or {}).get("destination") or {}
    if not ws.preserve_sheet and not (previous_dest.get("kind") == "google" and dest.get("kind") != "google"):
        R.save_state(ws.dir / "sheet_state.json", R.snapshot(tabs, dest))
    return dest, said


def push_history(ws: Workspace) -> tuple[list[dict], dict]:
    log, pushed = [], {}
    for p in sorted((ws.dir / "runs").glob("*/push_log.json")):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        log_at = doc.get("at") or "" if isinstance(doc, dict) else ""
        for e in doc if isinstance(doc, list) else doc.get("entries") or doc.get("results") or []:
            if e.get("dry_run"):
                continue
            log.append({"at": (e.get("at") or log_at)[:16].replace("T", " "), "period": e.get("period"),
                        "pms_period_id": e.get("pms_period_id") or e.get("periodId"), "action": e.get("action") or "PMS update",
                        "changed": e.get("changed") or e.get("summary"), "by": e.get("by"), "result": e.get("result")})
            if e.get("period") and e.get("result") == "verified":
                pushed[e["period"]] = (e.get("at") or log_at)[:10]
    return log, pushed


# --------------------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------------------

def cmd_run(args) -> int:
    clock = Clock()
    ws = Workspace(args)
    notes: list[str] = []
    say = (lambda m: print(f"  {m}")) if args.verbose else (lambda m: None)
    print(f"KPI run · {ws.name} · {ws.today}")

    # 1. the board ------------------------------------------------------------------------
    if args.rejudge_only:
        # After `judge`: the board has not changed in the last minute, so it is not read again.
        snap = B.load(ws.dir / "cache" / "board.json")
        if snap is None and ((ws.profile.get("tracker") or {}).get("adapter") or "asana") not in CONVERTERS:
            raise SystemExit("No board on file yet. Run `kpi.py run` first.")
    else:
        snap = get_board(ws, args, say)
    items = {i["id"]: i for i in (snap or {}).get("items") or []}
    clock.lap("board")

    # 2. what a person typed into the last sheet -----------------------------------------
    edits = read_back(ws, items, args)
    clock.lap("read-back")

    # 3. the sources on the list, and nothing else -----------------------------------------
    statuses: list[dict] = []
    mode = (ws.profile.get("sources") or {}).get("mode") or "tracker-first"
    if mode != "tracker-only":
        statuses = S.pull(ws.profile, ws.dir, ws.base, offline=args.offline or args.rejudge_only, project=ws.project)
        for st in statuses:
            notes += S.facts_from_mapping(st, (ws.profile.get("sources") or {}).get(st["role"]) or {}, ws.facts)
        notes += S.staleness(statuses, ws.facts)
        notes += [f"{st['role']}: {st['note']}" for st in statuses if st["state"] == "missing"]
    clock.lap("sources")
    active_facts, ws.source_blockers = S.usable_facts(statuses, ws.facts)

    # 4. judge what the rules can, queue what they cannot ------------------------------------
    ws.run_dir.mkdir(parents=True, exist_ok=True)
    kif_path = ws.run_dir / "run.kif.json"
    work: dict = {"queue": [], "questions": [], "counts": {}, "grain": "board-cards"}
    if snap is None:
        if legacy_kif(ws, args, kif_path) != 0:
            return 1
        kif = json.loads(kif_path.read_text(encoding="utf-8"))
    else:
        kif, work = classify.to_kif(snap, ws.profile, ws.project, active_facts, ws.ledger, ws.today)
        kif_path.write_text(json.dumps(kif, indent=1, ensure_ascii=False), encoding="utf-8")
    clock.lap("classify")

    # 5. count -------------------------------------------------------------------------------
    results = compute(ws, kif_path)
    for note in J._notes_needed(results, ws.facts):
        tag = f"{note['period']}|{note['kpi']}"
        missing = ((ws.facts.get("reasons") or {}).get("_questions") or {}).get(tag)
        if missing:
            work["questions"].append({"id": "reason:" + tag, "about": note["period"],
                                      "question": f"{note['period']} · {note['kpi']}: {missing}"})
    moved, values = what_moved(ws, results)
    clock.lap("compute")

    # 6. the sheet -----------------------------------------------------------------------------
    questions = [dict(q, asked_on=ws.today, answer=_answer_text(ws.ledger.answer(q["id"]))) for q in work["questions"]]
    log, pushed = push_history(ws)
    registry = _registry(ws)
    ctx = {
        "profile": ws.profile, "registry": registry, "reasons": ws.facts.get("reasons") or {}, "manual": ws.manual,
        "questions": [q for q in questions if not q["answer"]] + [q for q in questions if q["answer"]],
        "changes": moved, "push_log": log, "pushed_on": pushed, "grain": work.get("grain"),
        "as_of": ws.today, "refreshed": (snap or {}).get("fetched_at") or B.now_iso(), "tool_version": _version(),
        "prepared_by": (ws.raw.get("owner") or {}).get("name") or args.by or "",
        "client": (ws.project.get("client") or (ws.profile.get("account") or {}).get("name") or ""),
        "sources_text": ", ".join(["Issue tracker"] + [s["role"].title() for s in statuses if s["state"] != "missing"]),
        "sources": [{"role": "issue tracker", "state": "read" if snap else "adapter", "as_of": (snap or {}).get("fetched_at"),
                     "note": _board_note(snap)}] +
                   [{"role": s["role"], "state": s["state"], "as_of": s.get("fingerprint"), "note": s.get("note")} for s in statuses] +
                   [{"role": "chat, mail, other documents", "state": "not read", "as_of": "",
                     "note": "Outside this run's sources. Add one to the profile, or ask for a deep run, to include it."}],
        "run_facts": [("Run on", ws.today), ("Tool version", _version()), ("Source-of-truth mode", mode),
                      ("Cards read", len(items)), ("Judged by an assistant or a person (kept)", _kept(ws.ledger)),
                      ("Waiting for an assistant", len(work["queue"])), ("Waiting for a person", len([q for q in questions if not q["answer"]]))],
    }
    dest, said = publish(ws, kif, results, ctx, args)
    clock.lap("sheet")

    # 7. what needs a brain --------------------------------------------------------------------
    queue = J.build_queue(work, results, ws.facts, ws.dir, [p.get("name") for p in kif.get("periods") or []])
    qpath = J.write_queue(queue, ws.dir) if (queue["items"] or queue["notes"]) else None
    if not qpath and (ws.dir / "judge" / "queue.json").exists():
        (ws.dir / "judge" / "queue.json").unlink()
    ws.ledger.record_run(values, {"cards": len(items), "to_judge": len(queue["items"])})
    ws.save()
    clock.lap("save")

    report(ws, results, kif, work, queue, qpath, questions, edits, notes, said, moved, dest, clock, args)
    return 0


def _answer_text(a: Any) -> str:
    if isinstance(a, dict):
        return ", ".join(f"{k} {v}" for k, v in a.items())
    return "" if a is None else str(a)


def _kept(ledger: Ledger) -> int:
    return sum(len(v.get("judgements") or {}) for v in ledger.data["items"].values())


def _board_note(snap: dict | None) -> str:
    if not snap:
        return "read by the tracker's own adapter"
    st = snap.get("stats") or {}
    return (f"{len(snap.get('items') or [])} cards; history refreshed for {st.get('refreshed', 0)}, reused for "
            f"{st.get('reused', 0)} unchanged")


def _registry(ws: Workspace) -> dict:
    return json.loads(ws.registry_path.read_text(encoding="utf-8"))


def report(ws, results, kif, work, queue, qpath, questions, edits, notes, said, moved, dest, clock, args) -> None:
    met = notmet = unmeasured = 0
    print()
    for per in results.get("periods") or []:
        for m in per.get("measures") or []:
            st = m.get("status")
            met, notmet, unmeasured = met + (st == "Met"), notmet + (st == "Not met"), unmeasured + (st == "Not measured")
            mark = {"Met": "ok  ", "Not met": "MISS", "Not measured": "  ? "}.get(st, "    ")
            print(f"  {mark} {per['period'][:22]:<22} {m['name'][:24]:<24} {_show(m.get('value')):>12}")
    c = work.get("counts") or {}
    if c.get("skipped_subtasks"):
        notes.append(f"{c['skipped_subtasks']} subtasks were excluded by tracker.options.include_subtasks. "
                     "Enable it if those cards are deliverables or defect reports.")
    print(f"\n  {met} met · {notmet} not met · {unmeasured} not measured"
          + (f"   ({c.get('cards')} cards -> {c.get('tasks')} task rows, {c.get('defects')} reports)" if c else ""))

    for title, lines in (("Read back from the sheet", edits), ("Moved since the last run", moved), ("Notes", notes + said)):
        if lines:
            print(f"\n{title}:")
            for ln in lines[:15]:
                print(f"  · {ln}")
            if len(lines) > 15:
                print(f"  · ... and {len(lines) - 15} more")

    print(f"\nSheet: {dest.get('url') or dest.get('path')}")
    if dest.get("url"):
        print(f"Local copy: {dest.get('path')}")
    print(f"Run folder: {ws.run_dir}")
    print("  " + clock.line())

    open_q = [q for q in questions if not q["answer"]]
    output = ws.profile.get("output") or {}
    wants_google = (output.get("workbook") == "google-sheets" or output.get("workbook_file")
                    or output.get("workbook_location")) and output.get("workbook") != "xlsx"
    sheet_pending = ws.preserve_sheet or (bool(wants_google) and dest.get("kind") != "google")
    print("\nNEXT")
    if sheet_pending:
        print("  Publishing: the local workbook is ready, but the configured Google Sheet has not been updated. "
              "Resolve the connection or explicitly choose local workbook output, then rerun.")
    for problem in getattr(ws, "source_blockers", []):
        print(f"  Source needs attention: {problem}")
    if qpath:
        n_i, n_n = len(queue["items"]), len(queue["notes"])
        what = " and ".join(x for x in (f"{n_i} card{'s' if n_i != 1 else ''} to judge" if n_i else "",
                                        f"{n_n} missed KPI{'s' if n_n != 1 else ''} needing a reason" if n_n else "") if x)
        print(f"  Assistant: {what}. Read {qpath} once, write {ws.dir / 'judge' / 'answers.json'} in the shape it shows,\n"
              f"  then run:  python3 {Path(__file__).name} judge --profile {ws.profile_path} --project {ws.pid}\n"
              f"  Do not open the board or search anywhere else - everything needed is in that file.")
    if open_q:
        print(f"  Person: {len(open_q)} question{'s' if len(open_q) != 1 else ''} only you can answer "
              f"(Open Questions tab, or tell the assistant):")
        for q in open_q[:6]:
            print(f"    - [{q['id']}] {q['question']}")
    if args.deep and (ws.profile.get("sources") or {}).get("evidence_channels"):
        ch = ", ".join((ws.profile.get("sources") or {}).get("evidence_channels") or [])
        print(f"  Deep run asked for: the open questions above may also be looked up in {ch} - those, and only for "
              f"those questions. Record what you find with `answer`, with the link.")
    if not qpath and not open_q and not getattr(ws, "source_blockers", []) and not sheet_pending:
        print("  Nothing. The sheet is up to date." + ("" if (ws.profile.get("output") or {}).get("mode") in (None, "review-only")
                                                       else f"  To send it:  python3 {Path(__file__).name} push --profile {ws.profile_path} --project {ws.pid}"))
    (ws.dir / "next.json").write_text(json.dumps({
        "sheet": dest.get("url") or dest.get("path"), "queue": str(qpath) if qpath else None,
        "to_judge": len(queue["items"]), "notes_needed": len(queue["notes"]),
        "questions": [{"id": q["id"], "question": q["question"]} for q in open_q],
        "source_blockers": getattr(ws, "source_blockers", []),
        "sheet_pending": sheet_pending,
        "payloads": str(ws.run_dir / "payloads.json"),
        "input_digest": input_digest(ws),
        "payload_digest": hashlib.sha256((ws.run_dir / "payloads.json").read_bytes()).hexdigest(),
        "met": met, "not_met": notmet, "not_measured": unmeasured}, indent=1), encoding="utf-8")


# --------------------------------------------------------------------------------------
# the other commands
# --------------------------------------------------------------------------------------

def cmd_judge(args) -> int:
    ws = Workspace(args)
    snap = B.load(ws.dir / "cache" / "board.json") or {"items": []}
    path = Path(args.answers) if args.answers else ws.dir / "judge" / "answers.json"
    if not path.exists():
        print(f"No answers at {path}. Read {ws.dir / 'judge' / 'queue.json'} and write them first.", file=sys.stderr)
        return 2
    names = [p.get("name") for p in (ws.facts.get("periods") or {}).get("periods") or []] or ["Full Project"]
    out = J.apply_answers(path, snap, ws.ledger, ws.facts, names, by="human" if args.human else "ai", who=args.by or "")
    ws.save()
    print(f"Applied {len(out['applied'])} judgement{'s' if len(out['applied']) != 1 else ''} and {out['reasons']} reason(s).")
    for title, lines in (("Refused", out["refused"]), ("Could not decide - these become questions for a person", out["unsure"])):
        if lines:
            print(f"\n{title}:")
            for ln in lines:
                print(f"  · {ln}")
    if out["applied"] or out["reasons"] or out["unsure"]:
        path.rename(ws.dir / "judge" / f"answers.{dt.datetime.now():%Y%m%d-%H%M%S}.json")
    if args.no_rerun:
        return 0
    print()
    args.rejudge_only, args.offline_keep = True, True
    return cmd_run(args)


def cmd_answer(args) -> int:
    ws = Workspace(args)
    import sheet_readback as R
    R._file_answer(args.id, args.value, ws.ledger, ws.facts)
    if args.why:
        ws.ledger.data["answers"].setdefault(args.id, {})["why"] = args.why
        ws.ledger.dirty = True
    ws.save()
    print(f"Kept: {args.id} = {args.value}. It will be used from the next run on.")
    return 0


def cmd_status(args) -> int:
    ws = Workspace(args)
    snap = B.load(ws.dir / "cache" / "board.json")
    print(f"{ws.name}  ({ws.dir})")
    print(f"  board:      " + (f"{len(snap['items'])} cards, read {snap.get('fetched_at', '')[:16]}" if snap else "not read yet"))
    for role in S.ROLES:
        cfg = (ws.profile.get("sources") or {}).get(role) or {}
        f = ws.facts.get(role if role != "timeline" else "periods") or {}
        n = len(f.get("items") or f.get("periods") or [])
        where = f"{cfg.get('kind')} {str(cfg.get('ref'))[:50]}" if cfg.get("ref") else "no source declared"
        print(f"  {role + ':':<11} {where} -> {n} rows on file in facts/")
    print(f"  judgements kept: {_kept(ws.ledger)}   ·   Google: {G.how_signed_in() or 'not connected'}")
    nxt = ws.dir / "next.json"
    if nxt.exists():
        n = json.loads(nxt.read_text(encoding="utf-8"))
        print(f"  waiting: {n.get('to_judge', 0)} to judge, {n.get('notes_needed', 0)} reasons, {len(n.get('questions') or [])} questions")
        print(f"  sheet:   {n.get('sheet')}")
    return 0


def cmd_auth(args) -> int:
    """Connect a service - or, with no service named, say what this profile needs, what is
    already connected, and which way of signing in to suggest for each."""
    if not args.what:
        services = ["asana", "jira", "github", "google"]
        try:
            ws = Workspace(args)
            services = connect.needed(ws.profile, ws.project) or services
        except SystemExit:
            pass
        print(connect.advise(services, unattended=args.unattended))
        print("\nTo connect one:  python3 scripts/kpi.py auth <service> [--route browser|token]"
              "\nA browser sign-in can be completed in your own browser or in your assistant's built-in one "
              "(add --no-open and open the printed link there). A token is typed by you in a terminal, never in a chat.")
        return 0
    service = args.what
    st = connect.status(service)
    route = args.route or next((r["id"] for r in connect.recommend(service, args.unattended) if r["ready_now"]), "token")
    try:
        if route == "browser":
            print(f"Connected. Saved to {connect.sign_in_browser(service, open_browser=not args.no_open)} (readable only by you).")
        elif route == "cli":
            if st["via"] == "cli":
                print("GitHub is already connected through `gh`. Nothing to do.")
            else:
                print("Run this yourself - it opens your browser, and nothing is copied or pasted:\n  gh auth login --web"
                      + ("" if st["ready"]["cli"] else "\n(GitHub CLI is not installed: https://cli.github.com - or use "
                                                       "`--route token`.)"))
        elif route == "token":
            print(f"Saved to {connect.sign_in_token(service)} (readable only by you).")
        else:
            print(connect.advise([service], args.unattended))
    except connect.ConnectError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


def cmd_doctor(args) -> int:
    ws = Workspace(args)
    ok = True

    def line(good: bool | None, what: str, fix: str = "") -> None:
        nonlocal ok
        ok = ok and good is not False
        print(f"  {'[x]' if good else '[~]' if good is None else '[!]'} {what}"
              + ("\n        " + fix.replace("\n", "\n        ") if fix and not good else ""))

    print(f"{ws.name}")
    trk = ws.profile.get("tracker") or {}
    adapter = trk.get("adapter") or "asana"
    if adapter in connect.ROUTES:
        st = connect.status(adapter)
        line(st["connected"], f"{adapter} connected" + (f" ({st['via']})" if st["via"] else ""), connect.advise([adapter]))
        line(bool(ws.project.get("tracker_ref") or trk.get("project_ref") or (trk.get("options") or {}).get("jql")),
             "the project names its board (tracker_ref)", "Add tracker_ref to the project in the profile.")
        if st["connected"] and not args.offline:
            try:
                snap = reader_for(adapter).read(dict(ws.project, _probe=True), ws.profile,
                                                B.load(ws.dir / "cache" / "board.json"), None)
                line(True, f"the board answers: {len(snap.get('items') or [])} items")
                B.save(ws.dir / "cache" / "board.json", snap)
            except (B.ReaderError, SystemExit) as e:
                line(False, "the board answers", str(e))
    elif adapter in CONVERTERS:
        line(True, f"tracker is read from an export ({adapter}); nothing to connect")
    if "google" in connect.needed(ws.profile, ws.project):
        st = connect.status("google")
        line(st["connected"] or None, "Google connected" + (f" ({st['via']})" if st["via"] else ""),
             connect.advise(["google"]) + "\nNot blocking: without it, sources are taken from <project>/inbox/ "
                                         "and the sheet is a local file.")
        if st["connected"] and not args.offline:
            try:
                G.Session().token()
                line(True, "Google sign-in still valid")
            except G.GoogleError as e:
                line(False, "Google sign-in still valid", str(e))
    for role in ("periods", "plan", "estimates"):
        f = ws.facts.get(role) or {}
        have = len(f.get("periods") or f.get("items") or [])
        declared = role == "periods" or any(x["role"] == role for x in S.declared(ws.profile, ws.project))
        if declared:
            line(bool(have) or None, f"facts/{role}.yaml: {have} rows",
                 f"Empty. The first run will say what to read and where to write it ({ws.dir / 'facts'}).")
    print("\nReady." if ok else "\nNot ready: fix the [!] lines above.")
    return 0 if ok else 1


def input_digest(ws: Workspace) -> str:
    paths = [ws.profile_path, ws.registry_path, ws.dir / "ledger.json", ws.dir / "manual.yaml",
             ws.dir / "cache" / "board.json", *sorted((ws.dir / "facts").glob("*.yaml"))]
    h = hashlib.sha256()
    for path in paths:
        h.update(str(path).encode())
        h.update(path.read_bytes() if path.exists() else b"<missing>")
    return h.hexdigest()


def cmd_push(args) -> int:
    ws = Workspace(args)
    runs = sorted((ws.dir / "runs").glob("*/payloads.json"))
    if not runs:
        print("Nothing to push yet. Run first.", file=sys.stderr)
        return 2
    nxt = ws.dir / "next.json"
    n = json.loads(nxt.read_text(encoding="utf-8")) if nxt.exists() else {}
    payload = Path(n.get("payloads") or runs[-1])
    if args.apply:
        if args.offline:
            raise SystemExit("Cannot send to PMS with --offline. Prepare a dry run, review it and explicitly approve online delivery.")
        if not n.get("input_digest") or n["input_digest"] != input_digest(ws):
            raise SystemExit("Inputs changed or the run predates review checks. Run again and review the refreshed sheet before sending.")
        if n.get("payload_digest") != hashlib.sha256(payload.read_bytes()).hexdigest():
            raise SystemExit("The payload changed after the run. Recompute and review before sending.")
        if any(n.get(k) for k in ("notes_needed", "to_judge", "questions", "source_blockers", "sheet_pending")):
            raise SystemExit("This run still needs review: resolve NEXT, refresh the sheet, then approve sending to PMS.")
        snap = B.load(ws.dir / "cache" / "board.json") or {}
        edits = read_back(ws, {i["id"]: i for i in snap.get("items") or []}, args)
        if edits or ws.preserve_sheet:
            ws.save()
            raise SystemExit("The review sheet changed or cannot be read. Run again, review the updated values, then approve sending.")
    push = _module(HERE / "pms_push.py", "kpic_push")
    argv = ["--payloads", str(payload), "--profile", str(ws.profile_path), "--project", ws.pid,
            "--log", str(payload.parent / "push_log.json"), "--apply" if args.apply else "--dry-run"]
    return push.main(argv)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    def common(p, project: bool = True):
        p.add_argument("--profile", help="profile.yaml. Default: $KPI_PROFILE, else ./profile.yaml.")
        if project:
            p.add_argument("--project", help="Which project in the profile. Required when it covers several.")
        p.add_argument("--offline", action="store_true", help="Touch no network: reuse what is already on disk.")
        p.add_argument("--by", default="", help="Who is running this, recorded against edits and hand-set values.")
        p.add_argument("--today", help="Pretend it is this date (YYYY-MM-DD). For reproducing a past run.")
        p.add_argument("--date", help="Run folder name. Default: today.")
        p.add_argument("--verbose", action="store_true")
        return p

    r = common(sub.add_parser("run", help="Read, judge, count and update the sheet."))
    r.add_argument("--deep", action="store_true", help="Allow the open questions to be looked up in the profile's evidence channels.")
    r.add_argument("--adapter", help="Force a tracker adapter (asana, jira, github, csv).")
    r.add_argument("--from-raw", help="Raw responses downloaded by the tracker's browser_snapshot.js (no credential needed).")
    r.add_argument("--board", help="A board snapshot file, instead of reading the tracker.")
    r.add_argument("--file", help="CSV export, for --adapter csv.")
    r.add_argument("--no-publish", action="store_true", help="Write the local workbook only.")
    j = common(sub.add_parser("judge", help="Fold judge/answers.json into the ledger and recompute."))
    j.add_argument("--answers", help="Default: <project>/judge/answers.json")
    j.add_argument("--human", action="store_true", help="These answers are a person's, not an assistant's.")
    j.add_argument("--no-rerun", action="store_true")
    a = common(sub.add_parser("answer", help="Record a person's answer to an open question."))
    a.add_argument("--id", required=True)
    a.add_argument("--value", required=True)
    a.add_argument("--why", default="")
    common(sub.add_parser("status", help="What is on file and what is waiting. No network."))
    common(sub.add_parser("doctor", help="Can it reach what it needs?"))
    p = common(sub.add_parser("push", help="Send the last run to PMS (dry run unless --apply)."))
    p.add_argument("--apply", action="store_true")
    au = common(sub.add_parser("auth", help="Connect a service - or, with none named, see what needs connecting and how."))
    au.add_argument("what", nargs="?", choices=["asana", "jira", "github", "google"])
    au.add_argument("--route", choices=["browser", "token", "cli"], help="Default: the best one available on this machine.")
    au.add_argument("--no-open", action="store_true", help="Print the sign-in link instead of opening a browser "
                                                           "(to open it in an assistant's built-in browser).")
    au.add_argument("--unattended", action="store_true", help="Only routes that work with nobody there (a schedule).")

    args = ap.parse_args(argv)
    if not args.cmd:
        ap.print_help()
        return 2
    for k, v in (("rejudge_only", False), ("deep", False), ("adapter", None), ("from_raw", None), ("board", None),
                 ("file", None), ("no_publish", False), ("date", None), ("today", None), ("verbose", False)):
        if not hasattr(args, k):
            setattr(args, k, v)
    return {"run": cmd_run, "judge": cmd_judge, "answer": cmd_answer, "status": cmd_status,
            "doctor": cmd_doctor, "push": cmd_push, "auth": cmd_auth}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
