#!/usr/bin/env python3
"""
Self-test: run the whole pipeline against the bundled examples and check the answers.

This exists because the expensive mistakes in a KPI tool are not crashes. They are a number
that comes out plausible and wrong - a green "Met" bought by a missing handover date, a
denominator that quietly includes work nobody could judge, a note that says "1 observations".
Those survive code review and die in a management meeting.

So the assertions here are mostly about honesty rather than arithmetic.

    python3 scripts/selftest.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml  # type: ignore

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EX = ROOT / "examples"

passed, failed = 0, 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  ok    {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}" + (f"\n          {detail}" if detail else ""))


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=ROOT)


def compute(kif: Path, profile: Path, reasons: Path | None, out: Path) -> dict:
    args = ["scripts/kpi_engine.py", "--kif", str(kif), "--profile", str(profile), "--out", str(out)]
    if reasons:
        args += ["--reasons", str(reasons)]
    r = run(args)
    if r.returncode != 0:
        raise SystemExit(f"engine failed: {r.stderr}")
    return json.loads(out.read_text())


def measure(doc: dict, period: str, name: str) -> dict:
    per = next(p for p in doc["periods"] if p["period"] == period)
    return next(m for m in per["measures"] if m["name"] == name)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="kpi-selftest-"))

    print("\nSchemas and profiles")
    for p in (EX / "northwind-q3" / "profile.yaml", EX / "acme-jira" / "profile.yaml"):
        r = run(["scripts/profile_tool.py", "validate", "--profile", str(p)])
        check(f"{p.parent.name} profile validates", r.returncode == 0, r.stdout)

    print("\nAdapter: csv (a Jira export, no history)")
    r = run(["adapters/csv/extract.py", "--profile", str(EX / "acme-jira" / "profile.yaml"),
             "--project", "acme-identity", "--out", str(tmp / "acme.kif.json")])
    check("csv adapter runs", r.returncode == 0, r.stderr)
    r = run(["scripts/validate_kif.py", "--kif", str(tmp / "acme.kif.json")])
    check("csv output is valid KIF", r.returncode == 0, r.stdout)
    acme_kif = json.loads((tmp / "acme.kif.json").read_text())
    check("csv does not claim status history it cannot see",
          "status_history" not in (acme_kif["generated"]["capabilities"]))
    check("csv splits sprints into periods", len(acme_kif["periods"]) == 2,
          str([p["name"] for p in acme_kif["periods"]]))
    check("exclusion patterns removed the two admin cards",
          sum(1 for t in acme_kif["tasks"] if t["type"] == "Excluded") == 2)
    check("every excluded row says why",
          all(t.get("exclude_reason") for t in acme_kif["tasks"] if t["type"] == "Excluded"))
    check("the change-request label was recognised",
          any(t["type"] == "CR" for t in acme_kif["tasks"]))

    print("\nEngine: honesty")
    acme = compute(tmp / "acme.kif.json", EX / "acme-jira" / "profile.yaml", None, tmp / "acme.results.json")
    m = measure(acme, "Sprint 14", "Rework Rate")
    check("rework is Not measured when no row records a reopen", m["status"] == "Not measured",
          f"got {m['status']} = {m['value']}")
    m = measure(acme, "Sprint 14", "Escaped Defect Rate")
    check("escaped defects are Not measured before handover", m["status"] == "Not measured",
          f"got {m['status']} = {m['value']}")
    for kpi in ("Task Comprehension", "Client Expectation", "Delivery Commitment"):
        m = measure(acme, "Sprint 14", kpi)
        check(f"{kpi} is Not measured with no evidence", m["status"] == "Not measured")

    print("\nEngine: arithmetic")
    sav = compute(EX / "northwind-q3" / "run.kif.json", EX / "northwind-q3" / "profile.yaml",
                  EX / "northwind-q3" / "reasons.yaml", tmp / "sav.results.json")
    m = measure(sav, "Initial Scope", "Task Comprehension")
    check("task comprehension 5/7 = 71.43%", m["value"] == 71.43 and m["numerator"] == 5 and m["denominator"] == 7,
          f"got {m['numerator']}/{m['denominator']} = {m['value']}")
    m = measure(sav, "Initial Scope", "Defect Rate")
    check("defect rate counts 3 of 6 reports on 7 delivered items",
          m["numerator"] == 3 and m["denominator"] == 7, f"got {m['numerator']}/{m['denominator']}")
    m = measure(sav, "Initial Scope", "Rework Rate")
    check("rework counts the reopen and not the first-round QA failure", m["numerator"] == 1,
          f"got numerator {m['numerator']}")
    check("the first-round QA failure is named in the note",
          "first time" in m["note"], m["note"])
    m = measure(sav, "Additional Requests 1", "Client Expectation")
    check("a pending item stays out of the denominator", m["denominator"] == 4, f"got {m['denominator']}")
    check("the pending item is named in the note", "not due until" in m["note"], m["note"])
    m = measure(sav, "Additional Requests 1", "CR Rate")
    check("a CR-only cycle falls back to the project's planned scope",
          "planned items" in m["note"], m["note"])

    print("\nDelivery Commitment means promises kept, not work finished")
    # PMS: "Team-negotiated commitments delivered on time / total team-committed tasks.
    # Insight: reliability of the team." The denominator is commitments, not deliverables.
    mix = json.loads((EX / "northwind-q3" / "run.kif.json").read_text())
    for t in mix["tasks"]:
        if t.get("key") in ("TKT-3479", "TKT-3590"):
            t["met_commitment"] = None
            t.pop("commit_date", None)
    (tmp / "mix.kif.json").write_text(json.dumps(mix))
    mixed = compute(tmp / "mix.kif.json", EX / "northwind-q3" / "profile.yaml", None, tmp / "mix.results.json")
    m = measure(mixed, "Initial Scope", "Delivery Commitment")
    check("an item with no commitment is out of the denominator", m["denominator"] == 5,
          f"got {m['denominator']}, expected 5 of 7 deliverables")
    check("...and the note says how many were left out",
          "made no commitment on" in m["note"], m["note"])
    check("the heading is about commitments, not about QA",
          "Commitments the team met on time" in m["note"] and "QA" not in m["note"], m["note"])

    none_committed = json.loads((EX / "northwind-q3" / "run.kif.json").read_text())
    for t in none_committed["tasks"]:
        t["met_commitment"] = None
        t.pop("commit_date", None)
    none_committed["project"]["commit_date"] = None
    for per in none_committed["periods"]:
        per["commit_date"] = None
    (tmp / "nc.kif.json").write_text(json.dumps(none_committed))
    nc = compute(tmp / "nc.kif.json", EX / "northwind-q3" / "profile.yaml", None, tmp / "nc.results.json")
    m = measure(nc, "Initial Scope", "Delivery Commitment")
    check("no commitments at all is Not measured, not 0%", m["status"] == "Not measured",
          f"{m['status']} = {m['value']}")
    check("...and says why, in terms of reliability",
          "nothing to measure reliability against" in m["note"], m["note"])

    allcfg = yaml.safe_load((EX / "northwind-q3" / "profile.yaml").read_text())
    allcfg["workflow"]["commitment"] = {"scope": "all-deliverables", "met_when": "handover"}
    (tmp / "allcfg.yaml").write_text(yaml.safe_dump(allcfg))
    alld = compute(tmp / "mix.kif.json", tmp / "allcfg.yaml", None, tmp / "all.results.json")
    m = measure(alld, "Initial Scope", "Delivery Commitment")
    check("a team that commits to the whole scope can say so",
          m["denominator"] == 5 and "made no commitment" not in m["note"], m["note"])
    check("what counts as meeting a commitment is configurable, and said in words",
          "counted on the handover to the client" in m["note"], m["note"])

    print("\nEscaped Defect Rate is defects over defects, not over items")
    # PMS: "Defects found after release / Total defects (before + after release)."
    m = measure(sav, "Initial Scope", "Escaped Defect Rate")
    check("the denominator is valid defects, not delivered items",
          m["denominator"] == 5, f"got {m['denominator']}, expected 5 non-rejected reports of 6")
    check("rejected reports are in neither half", "rejected report left out" in m["note"], m["note"])
    m2 = measure(sav, "Additional Requests 1", "Escaped Defect Rate")
    check("no handover still means Not measured", m2["status"] == "Not measured", m2["status"])

    print("\nThe workbook matches the live tracker's shape")
    r = run(["scripts/workbook.py", "tracker", "--results", str(tmp / "sav.results.json"),
             "--kif", str(EX / "northwind-q3" / "run.kif.json"),
             "--reasons", str(EX / "northwind-q3" / "reasons.yaml"),
             "--profile", str(EX / "northwind-q3" / "profile.yaml"),
             "--out", str(tmp / "full.xlsx")])
    check("the tracker workbook builds", r.returncode == 0, r.stderr)
    from openpyxl import load_workbook as _lwb
    fwb = _lwb(tmp / "full.xlsx")
    check("it has the eight tabs the live trackers have, plus Gaps",
          fwb.sheetnames == ["Read Me", "Dashboard", "Config", "Periods", "Task Register",
                             "Defect Register", "KPI Summary", "PMS Push Log", "Gaps"],
          str(fwb.sheetnames))
    tr = fwb["Task Register"]
    hdrs = {c.value for c in tr[3] if c.value}
    check("the register carries the gate columns the KPIs depend on",
          {"Client-Expected?", "Team Committed?", "Met Commitment?"} <= hdrs,
          str(sorted(hdrs))[:200])
    check("...and the evidence beside each judgement",
          {"Comprehension Evidence", "Comprehension Link", "Rework Evidence"} <= hdrs)
    check("columns are sized, not left at default",
          (tr.column_dimensions["E"].width or 0) > 20, str(tr.column_dimensions["E"].width))
    check("headers freeze so a wide register stays readable", tr.freeze_panes == "E4", str(tr.freeze_panes))
    check("Config explains each KPI with the PMS formula",
          any("Formula (PMS definition)" == c.value
              for row in fwb["Config"].iter_rows() for c in row), "not found")
    dash = fwb["Dashboard"]
    check("the dashboard totals work and issues per period",
          any(c.value == "Found after handover" for row in dash.iter_rows() for c in row))

    print("\nEngine: the English")
    notes = [m["note"] for p in sav["periods"] for m in p["measures"]] + \
            [m["note"] for p in acme["periods"] for m in p["measures"]]
    joined = " ".join(notes)
    for bad in ("1 observations", "1 improvements", "1 items", "1 bugs", "1 requirements were",
                "of 1 items", "all 1 items", "the 1 items"):
        check(f"no '{bad}'", bad not in joined,
              next((n for n in notes if bad in n), ""))
    check("no links reach a PMS note", "http" not in joined)
    check("every note has at least two parts", all("||" in n for n in notes if n))

    print("\nCustom instructions")
    ov = {o["rule"]: o for o in sav.get("custom_overrides", [])}
    check("a supported override is applied", ov.get("defect_phase", {}).get("status") == "applied",
          json.dumps(ov.get("defect_phase", {})))
    m = measure(sav, "Initial Scope", "Escaped Defect Rate")
    check("the override moved the number", m["numerator"] == 1, f"got {m['numerator']}")

    illegal = json.loads(json.dumps(json.loads((EX / "northwind-q3" / "run.kif.json").read_text())))
    prof = yaml.safe_load((EX / "northwind-q3" / "profile.yaml").read_text())
    prof.setdefault("custom_instructions", {}).setdefault("rule_overrides", []).append(
        {"rule": "threshold_defect_rate", "value": "25", "why": "legacy surface"})
    (tmp / "illegal.yaml").write_text(yaml.safe_dump(prof))
    (tmp / "illegal.kif.json").write_text(json.dumps(illegal))
    doc = compute(tmp / "illegal.kif.json", tmp / "illegal.yaml", None, tmp / "illegal.results.json")
    bad = next((o for o in doc["custom_overrides"] if o["rule"] == "threshold_defect_rate"), {})
    check("a local threshold is refused, and points at PMS", "in PMS" in bad.get("status", ""),
          json.dumps(bad))
    m = measure(doc, "Initial Scope", "Defect Rate")
    check("the refused override did not change the target", m["threshold"] == 15, f"got {m['threshold']}")
    r = run(["scripts/profile_tool.py", "validate", "--profile", str(tmp / "illegal.yaml")])
    check("validation also refuses it, and says where to set it",
          r.returncode != 0 and "on this project in PMS" in r.stdout, r.stdout)

    print("\nPer-project targets from PMS")
    reg = json.loads((ROOT / "schemas" / "kpi_registry.default.json").read_text())
    reg["source"], reg["synced_at"] = "pms", "2026-09-18T15:00:00+00:00"
    reg["projects"] = {"101": {"defect_rate": {"threshold": 25, "direction": "lower-is-better"},
                               "rework_rate": {"threshold": 20, "direction": "lower-is-better"}}}
    (tmp / "reg_project.json").write_text(json.dumps(reg, indent=2))
    r = run(["scripts/kpi_engine.py", "--kif", str(EX / "northwind-q3" / "run.kif.json"),
             "--profile", str(EX / "northwind-q3" / "profile.yaml"),
             "--registry", str(tmp / "reg_project.json"), "--out", str(tmp / "proj.results.json")])
    check("engine runs against a per-project registry", r.returncode == 0, r.stderr)
    proj = json.loads((tmp / "proj.results.json").read_text())
    m = measure(proj, "Initial Scope", "Defect Rate")
    check("a project's own target from PMS is used", m["threshold"] == 25, f"got {m['threshold']}")
    check("and it says the target came from that project",
          "project 101" in m.get("threshold_source", ""), m.get("threshold_source"))
    m = measure(proj, "Initial Scope", "Rework Rate")
    check("a looser project target can flip a status to Met",
          m["threshold"] == 20 and m["status"] == "Met", f"{m['threshold']} / {m['status']}")
    m = measure(proj, "Initial Scope", "Task Comprehension")
    check("a KPI the project does not override keeps the PMS default",
          m["threshold"] == 80 and "default" in m.get("threshold_source", ""),
          f"{m['threshold']} / {m.get('threshold_source')}")
    dflt = measure(sav, "Initial Scope", "Defect Rate")
    check("the bundled fallback says it is not from PMS",
          "fallback" in dflt.get("threshold_source", ""), dflt.get("threshold_source"))

    print("\nSeveral accounts, several trackers, one profile")
    sys.path.insert(0, str(ROOT / "scripts"))
    import profile_lib as pl  # noqa: E402

    multi = pl.load(EX / "multi-account" / "profile.yaml")
    r = run(["scripts/profile_tool.py", "validate", "--profile", str(EX / "multi-account" / "profile.yaml")])
    check("a multi-account profile validates", r.returncode == 0, r.stdout)

    sav_p, _ = pl.resolve(multi, "q3-release")
    acme, _ = pl.resolve(multi, "acme-identity")
    check("two projects on one profile resolve to different trackers",
          sav_p["tracker"]["adapter"] == "asana" and acme["tracker"]["adapter"] == "csv",
          f"{sav_p['tracker']['adapter']} / {acme['tracker']['adapter']}")
    check("...different chat tools",
          sav_p["sources"]["evidence_channels"] == ["chat-northwind-devqa", "chat-northwind-mgmt"]
          and acme["sources"]["evidence_channels"] == ["slack-acme"],
          f"{sav_p['sources']['evidence_channels']} / {acme['sources']['evidence_channels']}")
    check("...different output modes",
          sav_p["output"]["mode"] == "assisted-push" and acme["output"]["mode"] == "review-only",
          f"{sav_p['output']['mode']} / {acme['output']['mode']}")
    check("...different period models",
          sav_p["periods"]["model"] == "Delivery cycle" and acme["periods"]["model"] == "Sprint")
    check("...different defect conventions",
          sav_p["conventions"]["defect_by"] == "title-pattern" and acme["conventions"]["defect_by"] == "issue-type")

    gateway, _ = pl.resolve(multi, "gateway")
    check("a project inherits its account without repeating it",
          gateway["tracker"]["adapter"] == "asana" and gateway["conventions"]["key_pattern"] == r"TKT-\d+")
    check("a project override sits on top of its account",
          (gateway["sources"].get("timeline") or {}).get("tool_id") == "sheet-gateway-timeline")
    check("its sibling does not get that override",
          (sav_p["sources"].get("timeline") or {}).get("tool_id") is None)

    check("tools are scoped, so Acme cannot see Northwind's chat",
          "chat-northwind-devqa" not in {t["id"] for t in acme["tools"]}
          and "slack-acme" in {t["id"] for t in acme["tools"]},
          str(sorted(t["id"] for t in acme["tools"])))
    check("shared tools are visible to everyone",
          "pms" in {t["id"] for t in sav_p["tools"]} and "pms" in {t["id"] for t in acme["tools"]})

    deep = pl.deep_merge({"a": {"x": 1, "y": 2}, "list": [1, 2]}, {"a": {"y": 9}, "list": [3]})
    check("dicts merge deeply, lists replace",
          deep == {"a": {"x": 1, "y": 9}, "list": [3]}, str(deep))

    r = run(["adapters/csv/extract.py", "--profile", str(EX / "multi-account" / "profile.yaml"),
             "--project", "acme-identity", "--out", str(tmp / "multi.kif.json")])
    check("an adapter runs against the resolved project", r.returncode == 0, r.stderr)
    r = run(["scripts/preflight.py", "--profile", str(EX / "multi-account" / "profile.yaml"),
             "--state", str(tmp / "pf-multi.json"), "--json"])
    ids = {c["id"] for c in json.loads(r.stdout)["checks"]}
    check("preflight checks every project's adapter",
          {"adapter-present-q3-release", "adapter-present-acme-identity"} <= ids,
          str(sorted(i for i in ids if i.startswith("adapter"))))

    bad = pl.load(EX / "multi-account" / "profile.yaml")
    bad["projects"][2]["overrides"] = {"sources": {"evidence_channels": ["chat-northwind-devqa"]}}
    (tmp / "crosstalk.yaml").write_text(yaml.safe_dump(bad))
    r = run(["scripts/profile_tool.py", "validate", "--profile", str(tmp / "crosstalk.yaml")])
    check("a project reaching into another account's tools is refused",
          r.returncode != 0 and "not a tool this project can see" in r.stdout, r.stdout)

    r = run(["scripts/workbook.py", "build", "--profile", str(EX / "multi-account" / "profile.yaml"),
             "--out", str(tmp / "multi.xlsx")])
    check("a multi-account workbook builds", r.returncode == 0, r.stderr)
    r = run(["scripts/workbook.py", "read", "--xlsx", str(tmp / "multi.xlsx"), "--out", str(tmp / "multi.back.yaml")])
    back = pl.load(tmp / "multi.back.yaml")
    check("overrides survive the workbook round trip",
          back["accounts"][0]["overrides"]["conventions"]["client_names"]
          == multi["accounts"][0]["overrides"]["conventions"]["client_names"],
          str(back["accounts"][0]["overrides"]["conventions"].get("client_names")))
    check("a sentence containing a comma is not turned into a list",
          isinstance(back["accounts"][0]["overrides"]["workflow"]["closed_when"]["completed_flag_means"], str),
          repr(back["accounts"][0]["overrides"]["workflow"]["closed_when"].get("completed_flag_means")))

    print("\nCapturing settings from conversation")
    import shutil
    shutil.copy(EX / "northwind-q3" / "profile.yaml", tmp / "rm.yaml")
    r = run(["scripts/remember.py", "--profile", str(tmp / "rm.yaml"),
             "--add", "custom_instructions.never=Never push during a release freeze",
             "--why", "asked in chat", "--by", "Tester"])
    check("a setting said in chat can be written down", r.returncode == 0, r.stderr)
    got = pl.load(tmp / "rm.yaml")
    check("...and it is actually in the profile",
          "Never push during a release freeze" in got["custom_instructions"]["never"])
    check("...with the sentence it came from",
          any(e.get("why") == "asked in chat" for e in got.get("learned") or []),
          json.dumps(got.get("learned"))[:200])

    r = run(["scripts/remember.py", "--profile", str(tmp / "rm.yaml"),
             "--set", "output.mode=review-only"])
    check("a change with no reason is refused", r.returncode != 0 and "--why is required" in r.stderr)

    r = run(["scripts/remember.py", "--profile", str(tmp / "rm.yaml"),
             "--set", "output.mode=whenever", "--why", "testing"])
    check("a change that breaks the profile is rolled back", r.returncode != 0, r.stdout)
    still = pl.load(tmp / "rm.yaml")
    check("...leaving the profile loadable and unchanged",
          still["output"]["mode"] == "assisted-push", still["output"]["mode"])

    r = run(["scripts/remember.py", "--profile", str(tmp / "rm.yaml"),
             "--scope", "account:nope", "--set", "output.mode=review-only", "--why", "x"])
    check("an unknown account is refused by name", r.returncode != 0 and "Known" in r.stderr)

    r = run(["scripts/remember.py", "--profile", str(tmp / "rm.yaml"),
             "--tool", "id=slack-ops,kind=chat,name=#ops,used_for=evidence|handover",
             "--why", "named in chat"])
    check("a tool named in chat can be added", r.returncode == 0, r.stderr)
    got = pl.load(tmp / "rm.yaml")
    t = next((x for x in got["tools"] if x["id"] == "slack-ops"), None)
    check("...with its list fields parsed", t and t["used_for"] == ["evidence", "handover"], str(t))

    print("\nPush guards")
    run(["scripts/kpi_engine.py", "--kif", str(tmp / "acme.kif.json"),
         "--profile", str(EX / "acme-jira" / "profile.yaml"), "--payloads", str(tmp / "acme.payloads.json")])
    r = run(["scripts/pms_push.py", "--payloads", str(tmp / "acme.payloads.json"),
             "--profile", str(EX / "acme-jira" / "profile.yaml"), "--apply"])
    check("review-only refuses --apply", r.returncode == 2 and "Refusing to write" in r.stderr, r.stderr)
    payloads = json.loads((tmp / "acme.payloads.json").read_text())
    sent = [k["name"] for p in payloads for k in p["kpis"]]
    check("unmeasured KPIs are not sent to PMS", "Rework Rate" not in sent, str(sent))
    check("unmeasured KPIs are listed as skipped, with a reason",
          all(s.get("reason") for p in payloads for s in p["skipped"]))

    print("\nWorkbook")
    r = run(["scripts/workbook.py", "build", "--profile", str(EX / "northwind-q3" / "profile.yaml"),
             "--out", str(tmp / "profile.xlsx")])
    check("profile workbook builds", r.returncode == 0, r.stderr)
    r = run(["scripts/workbook.py", "read", "--xlsx", str(tmp / "profile.xlsx"), "--out", str(tmp / "back.yaml")])
    check("profile workbook reads back", r.returncode == 0, r.stderr)
    a = yaml.safe_load((EX / "northwind-q3" / "profile.yaml").read_text())
    b = yaml.safe_load((tmp / "back.yaml").read_text())

    def lost(orig, back, path=""):
        """Nothing the profile SAID may change or disappear. The workbook also fills in schema
        defaults the source left implicit, which is the point of showing them to a human, so
        keys that were absent and came back are not losses."""
        out = []
        if isinstance(orig, dict):
            if not isinstance(back, dict):
                return [(path, orig, back)]
            for k, v in orig.items():
                out += lost(v, back.get(k), f"{path}.{k}")
        elif orig != back:
            out.append((path, orig, back))
        return out

    missing = lost(a, b)
    check("workbook round trip loses nothing that was written",
          not missing, "; ".join(f"{p}: {o!r} -> {n!r}" for p, o, n in missing[:4]))
    r = run(["scripts/workbook.py", "tracker", "--results", str(tmp / "sav.results.json"),
             "--kif", str(EX / "northwind-q3" / "run.kif.json"), "--out", str(tmp / "tracker.xlsx")])
    check("tracker workbook builds", r.returncode == 0, r.stderr)

    print("\nEditing in the sheet, and what reaches PMS")
    from openpyxl import load_workbook as _lw  # noqa: E402
    r = run(["scripts/workbook.py", "tracker", "--results", str(tmp / "sav.results.json"),
             "--kif", str(EX / "northwind-q3" / "run.kif.json"),
             "--reasons", str(EX / "northwind-q3" / "reasons.yaml"), "--out", str(tmp / "t.xlsx")])
    check("tracker workbook builds with a Why column", r.returncode == 0, r.stderr)

    wbk = _lw(tmp / "t.xlsx")
    ws = wbk["KPI Summary"]
    keys = {c.value: c.column for c in ws[3] if c.value}
    check("the sheet offers a place to set a value by hand",
          {"why", "set_value_by_hand", "why_set_by_hand"} <= set(keys), str(sorted(keys)))
    check("the Why column is pre-filled from reasons.yaml",
          any(r_[keys["why"] - 1].value for r_ in ws.iter_rows(min_row=5)))

    # Edit: a judgement, an hour figure, a defect, a Why, and a value set by hand.
    tr = wbk["Task Register"]; tk = {c.value: c.column for c in tr[2] if c.value}
    for row in tr.iter_rows(min_row=4):
        if row[tk["key"] - 1].value == "TKT-3175":
            row[tk["understood"] - 1].value = "Yes"
            row[tk["hours_dev"] - 1].value = 30
    dr = wbk["Defect Register"]; dk = {c.value: c.column for c in dr[2] if c.value}
    for row in dr.iter_rows(min_row=4):
        if row[dk["key"] - 1].value == "Bug 7":
            row[dk["rejected"] - 1].value = "Yes"
            row[dk["rejection_reason"] - 1].value = "by design"
    for row in ws.iter_rows(min_row=5):
        if row[keys["period"] - 1].value == "Initial Scope":
            if row[keys["kpi"] - 1].value == "CR Rate":
                row[keys["set_value_by_hand"] - 1].value = 33
                row[keys["why_set_by_hand"] - 1].value = "Two items were re-scoped as plan work."
            if row[keys["kpi"] - 1].value == "Escaped Defect Rate":
                row[keys["set_value_by_hand"] - 1].value = 0      # no reason
            if row[keys["kpi"] - 1].value == "Velocity":
                row[keys["value"] - 1].value = 999                 # a computed cell
    wbk.save(tmp / "t.xlsx")

    r = run(["scripts/workbook.py", "review", "--tracker", str(tmp / "t.xlsx"),
             "--kif", str(EX / "northwind-q3" / "run.kif.json"), "--results", str(tmp / "sav.results.json"),
             "--reasons", str(EX / "northwind-q3" / "reasons.yaml"),
             "--out-kif", str(tmp / "patched.kif.json"), "--out-reasons", str(tmp / "r2.yaml"),
             "--out-manual", str(tmp / "manual.yaml"), "--by", "Tester"])
    check("review reads the edits back", r.returncode == 0, r.stderr)
    out = r.stdout
    check("a judgement edit is picked up", "understood" in out and "No -> Yes" in out, out)
    check("an hours edit is picked up", "hours_dev" in out, out)
    check("a defect edit is picked up", "rejected" in out, out)
    check("a hand-set value with a reason is kept", "set by hand" in out, out)
    check("a hand-set value with no reason is refused, and says what is missing",
          "needs a reason" in out, out)
    check("typing over a computed cell is reported, not silently dropped",
          "'Value' is computed" in out, out)

    patched = json.loads((tmp / "patched.kif.json").read_text())
    t = next(x for x in patched["tasks"] if x["key"] == "TKT-3175")
    check("the edit really landed in the extract", t["understood"] == "Yes" and t["hours_dev"] == 30.0,
          f"{t['understood']} / {t['hours_dev']}")

    r = run(["scripts/kpi_engine.py", "--kif", str(tmp / "patched.kif.json"),
             "--profile", str(EX / "northwind-q3" / "profile.yaml"),
             "--reasons", str(tmp / "r2.yaml"), "--manual", str(tmp / "manual.yaml"),
             "--out", str(tmp / "results2.json"), "--payloads", str(tmp / "pay2.json")])
    check("the engine reruns on the edited extract", r.returncode == 0, r.stderr)
    after = json.loads((tmp / "results2.json").read_text())
    before_tc = measure(sav, "Initial Scope", "Task Comprehension")["value"]
    after_tc = measure(after, "Initial Scope", "Task Comprehension")["value"]
    check("a judgement edit moves the KPI", after_tc > before_tc, f"{before_tc} -> {after_tc}")
    before_dr = measure(sav, "Initial Scope", "Defect Rate")["value"]
    after_dr = measure(after, "Initial Scope", "Defect Rate")["value"]
    check("rejecting a defect lowers the defect rate", after_dr < before_dr, f"{before_dr} -> {after_dr}")

    cr = measure(after, "Initial Scope", "CR Rate")
    check("a hand-set value is used", cr["value"] == 33.0, str(cr["value"]))
    check("...and the computed one is kept beside it", cr["computed_value"] == 40.0, str(cr.get("computed_value")))
    check("...and its note says a person set it, and why",
          "Recorded as 33%" in cr["note"] and "re-scoped" in cr["note"], cr["note"])
    edr = measure(after, "Initial Scope", "Escaped Defect Rate")
    check("a hand-set value with no reason never reaches the numbers", not edr["overridden"])

    pay = json.loads((tmp / "pay2.json").read_text())[0]
    sent = {k["name"]: k for k in pay["kpis"]}
    check("PMS gets the hand-set value, flagged, with the computed one alongside",
          sent["CR Rate"]["value"] == 33.0 and sent["CR Rate"]["overridden"]
          and sent["CR Rate"]["computed_value"] == 40.0, json.dumps(sent["CR Rate"])[:200])

    print("\nAdapter: asana bridge")
    legacy = {
        "projName": "Bridge test",
        "cfg": {"projectGid": "1", "pmsProjectId": 361},
        "projectDates": {"clientDate": "2026-09-11", "commitDate": "2026-09-11", "clientCheck": "Delivery"},
        "periodRows": [{"name": "Initial Scope", "pmsId": 723, "start": "2026-07-01", "end": "2026-08-12",
                        "releaseDate": "2026-08-12", "teamHours": 10}],
        "taskRows": [{"period": "Initial Scope", "key": "T-1", "title": "x", "type": "Task", "initial": "Yes",
                      "est": 10, "dev": 10, "qaC": 2, "created": "2026-07-01", "devdone": "2026-07-10",
                      "closed": "2026-07-20", "status": "Done", "und": "Yes", "cexp": "Yes", "commit": "Yes",
                      "reo": "No"}],
        "defectRows": [{"period": "Initial Scope", "key": "Bug 1", "title": "y", "kind": "Bug", "by": "QA",
                        "on": "2026-07-12", "phase": "Pre-release", "existing": "No", "rej": "No",
                        "fs": "Fixed / Closed"}],
        "review": [],
    }
    (tmp / "legacy.json").write_text(json.dumps(legacy))
    r = run(["adapters/asana/extract.py", "--profile", str(EX / "northwind-q3" / "profile.yaml"),
             "--project", "q3-release", "--from-extract", str(tmp / "legacy.json"),
             "--out", str(tmp / "bridge.kif.json")])
    check("asana bridge runs", r.returncode == 0, r.stderr)
    r = run(["scripts/validate_kif.py", "--kif", str(tmp / "bridge.kif.json")])
    check("asana bridge output is valid KIF", r.returncode == 0, r.stdout)
    bridged = json.loads((tmp / "bridge.kif.json").read_text())
    check("'Pre-release' becomes 'QA'", bridged["defects"][0]["phase"] == "QA")
    check("the handover date survives", bridged["periods"][0]["handover_date"] == "2026-08-12")

    print(f"\n{passed} passed, {failed} failed\n")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
