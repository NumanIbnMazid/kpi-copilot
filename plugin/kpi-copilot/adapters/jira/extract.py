#!/usr/bin/env python3
"""
Jira adapter.

Reads a Jira Cloud project through the REST API, including each issue's changelog, and emits
KIF. The changelog is what makes this adapter better than a CSV export: it can tell when an
item was genuinely delivered, when it was reopened after closing, and when somebody had to
stop and ask the client - the three things that drive Delivery Commitment, Rework Rate and
Task Comprehension.

Authentication: set JIRA_EMAIL and JIRA_TOKEN in the environment (an Atlassian API token).
The token is never written into the profile, never printed, and never sent anywhere but your
own Jira site.

    export JIRA_EMAIL="you@example.com"
    export JIRA_TOKEN="..."      # from id.atlassian.com/manage-profile/security/api-tokens

Usage:
    python3 extract.py --profile profile.yaml --project acme-identity --out run.kif.json
    python3 extract.py --profile profile.yaml --project acme-identity --jql "project = ACME AND sprint = 14"
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
from profile_lib import load as load_profile, resolve as resolve_profile  # noqa: E402

ADAPTER = "jira"
VERSION = "1.0.0"

REJECT_WORDS = ("invalid", "duplicate", "won't do", "wont do", "cannot reproduce",
                "cannot be reproduced", "not reproducible", "by design", "not a bug",
                "works as designed", "declined")


def _load(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        import yaml  # type: ignore
        return yaml.safe_load(text)
    return json.loads(text)


def _date(value: str | None) -> str | None:
    return str(value)[:10] if value else None


class Jira:
    def __init__(self, base: str, email: str, token: str):
        self.base = base.rstrip("/")
        raw = f"{email}:{token}".encode()
        self.auth = "Basic " + base64.b64encode(raw).decode()

    def get(self, path: str, params: dict | None = None) -> Any:
        url = self.base + path + ("?" + urllib.parse.urlencode(params) if params else "")
        req = urllib.request.Request(url, headers={"Accept": "application/json", "Authorization": self.auth})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))

    def search(self, jql: str, fields: list[str]) -> list[dict]:
        """Paged search with the changelog expanded, so one pass gives issues and history."""
        out, start = [], 0
        while True:
            page = self.get("/rest/api/3/search", {
                "jql": jql, "startAt": start, "maxResults": 100,
                "fields": ",".join(fields), "expand": "changelog",
            })
            issues = page.get("issues", [])
            out.extend(issues)
            start += len(issues)
            if start >= page.get("total", 0) or not issues:
                return out


def transitions(issue: dict) -> list[tuple[str, str, str]]:
    """(when, from, to) for every status change, oldest first."""
    moves = []
    for entry in (issue.get("changelog") or {}).get("histories") or []:
        when = entry.get("created", "")
        for item in entry.get("items") or []:
            if item.get("field") == "status":
                moves.append((when, item.get("fromString") or "", item.get("toString") or ""))
    return sorted(moves)


def first_entry_into(moves: list[tuple[str, str, str]], states: list[str]) -> str | None:
    wanted = {s.lower() for s in states}
    for when, _, to in moves:
        if to.lower() in wanted:
            return _date(when)
    return None


def was_reopened(moves: list[tuple[str, str, str]], closed_states: list[str],
                 reopen_states: list[str], ignore_first_qa_fail: bool) -> tuple[str | None, str]:
    """Rework is closed-then-reopened. A QA failure while the item is still being tested for
    the first time is normal testing: it is reported in the evidence column and not counted.
    Getting this wrong is the single most common way a Rework Rate comes out too high."""
    closed = {s.lower() for s in closed_states}
    reopen = {s.lower() for s in reopen_states}
    has_closed, evidence = False, ""
    for when, frm, to in moves:
        if to.lower() in closed:
            has_closed = True
            continue
        if frm.lower() in closed and (not reopen or to.lower() in reopen) and has_closed:
            return "Yes", f"Moved out of {frm} into {to} on {_date(when)}"
        if not has_closed and to.lower() in reopen and ignore_first_qa_fail:
            evidence = evidence or f"Moved to {to} on {_date(when)} while still in first-round testing"
    return ("No" if moves else None), evidence


def had_to_ask(issue: dict, moves: list[tuple[str, str, str]], wf: dict) -> tuple[str | None, str]:
    """Task Comprehension: did the team need the client to explain the requirement.
    Going to a blocked state for a build or an environment problem does not count - that is a
    dependency, not a misunderstanding."""
    cfg = wf.get("clarification_when") or {}
    states = {s.lower() for s in (cfg.get("values") or [])}
    excuses = [w.lower() for w in (cfg.get("exclude_reasons") or ["build", "environment", "access"])]
    if not states:
        return None, ""
    created = _date(issue["fields"].get("created"))
    for when, _, to in moves:
        if to.lower() not in states:
            continue
        if created and _date(when) and _date(when) < created:
            continue
        context = " ".join(
            str(c.get("body", "")) for c in ((issue["fields"].get("comment") or {}).get("comments") or [])
        ).lower()
        if any(x in context for x in excuses):
            return "Yes", f"Went to {to} on {_date(when)}, for a build or environment dependency rather than the requirement"
        return "No", f"Went to {to} on {_date(when)}"
    return "Yes", ""


def classify(issue: dict, conv: dict) -> tuple[str, str | None]:
    f = issue["fields"]
    title = f.get("summary") or ""
    labels = " ".join(f.get("labels") or [])
    itype = (f.get("issuetype") or {}).get("name") or ""

    for pattern in conv.get("exclude_patterns") or []:
        try:
            if re.search(pattern, title, re.I):
                return "Excluded", f"Title matches the team's 'not a deliverable' rule ({pattern})"
        except re.error:
            continue
    marker = conv.get("cr_marker")
    if marker:
        try:
            if re.search(marker, f"{title} {labels} {itype}", re.I):
                return "CR", None
        except re.error:
            pass
    return "Task", None


def is_defect(issue: dict, conv: dict) -> tuple[bool, str]:
    f = issue["fields"]
    title = f.get("summary") or ""
    itype = ((f.get("issuetype") or {}).get("name") or "").lower()
    labels = [str(x).lower() for x in (f.get("labels") or [])]
    by = conv.get("defect_by", "issue-type")
    defect_values = [v.lower() for v in (conv.get("defect_values") or ["bug"])]
    obs_values = [v.lower() for v in (conv.get("observation_values") or ["observation", "improvement"])]

    if by == "title-pattern" and conv.get("defect_pattern"):
        mo = re.match(conv["defect_pattern"], title, re.I)
        if mo:
            word = (mo.group(1) if mo.groups() else "Bug").title()
            return True, word if word in ("Bug", "Observation", "Improvement") else "Bug"
        return False, ""
    pool = labels if by == "label" else [itype]
    for v in obs_values:
        if v in pool:
            return True, "Improvement" if "improve" in v else "Observation"
    for v in defect_values:
        if v in pool:
            return True, "Bug"
    return False, ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Read a Jira project into KIF.")
    ap.add_argument("--profile", required=True, type=Path)
    ap.add_argument("--project", help="Project id from the profile's projects list.")
    ap.add_argument("--jql", help="Override the query. Useful for one sprint or one date range.")
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args(argv)

    profile, proj = resolve_profile(load_profile(a.profile), a.project)
    tracker = profile.get("tracker") or {}
    conv = profile.get("conventions") or {}
    wf = profile.get("workflow") or {}

    email, token = os.environ.get("JIRA_EMAIL"), os.environ.get("JIRA_TOKEN")
    if not (email and token):
        print(
            "JIRA_EMAIL and JIRA_TOKEN are not set, so this adapter cannot reach Jira.\n"
            "Create a token at id.atlassian.com/manage-profile/security/api-tokens and export both.\n"
            "No token to hand? Export the board to CSV and use the csv adapter - it produces the same\n"
            "KIF, minus the history-based KPIs, and it says which ones those are.",
            file=sys.stderr,
        )
        return 2

    base = tracker.get("url") or ""
    key = proj.get("tracker_ref") or tracker.get("project_ref") or ""
    jql = a.jql or f"project = {key} ORDER BY created ASC"

    jira = Jira(base, email, token)
    fields = ["summary", "issuetype", "status", "assignee", "reporter", "created", "resolutiondate",
              "resolution", "labels", "timeoriginalestimate", "comment", "parent", "fixVersions"]
    sprint_field = (tracker.get("options") or {}).get("sprint_field")
    points_field = tracker.get("story_point_field")
    for extra in (sprint_field, points_field):
        if extra:
            fields.append(extra)

    try:
        issues = jira.search(jql, fields)
    except urllib.error.HTTPError as e:
        print(f"Jira answered {e.code} for `{jql}`. A 400 usually means the JQL is wrong; "
              f"a 401 means the token is not valid for this site.", file=sys.stderr)
        return 3
    except Exception as e:  # noqa: BLE001
        print(f"Could not reach Jira ({type(e).__name__}: {e}).", file=sys.stderr)
        return 3

    if not issues:
        print(f"No issues matched `{jql}`.", file=sys.stderr)
        return 2

    delivered_states = (wf.get("delivered_when") or {}).get("values") or []
    closed_states = (wf.get("closed_when") or {}).get("values") or ["Done", "Closed"]
    reopen_states = (wf.get("reopened_when") or {}).get("values") or []
    ignore_first = (wf.get("reopened_when") or {}).get("ignore_first_qa_fail", True)
    client_names = [c.lower() for c in (conv.get("client_names") or [])]

    def period_of(issue: dict) -> str:
        f = issue["fields"]
        if sprint_field and f.get(sprint_field):
            sprints = f[sprint_field]
            if isinstance(sprints, list) and sprints:
                last = sprints[-1]
                return str(last.get("name") if isinstance(last, dict) else last)[:25]
        versions = f.get("fixVersions") or []
        if versions:
            return str(versions[-1].get("name"))[:25]
        return "Full Project"

    periods: dict[str, dict] = {}
    tasks, defects, review = [], [], []

    for issue in issues:
        f = issue["fields"]
        key_ = issue["key"]
        moves = transitions(issue)
        period = period_of(issue)
        periods.setdefault(period, {"name": period})
        link = f"{base.rstrip('/')}/browse/{key_}"

        defect, kind = is_defect(issue, conv)
        if defect:
            reporter = ((f.get("reporter") or {}).get("displayName") or "")
            resolution = ((f.get("resolution") or {}).get("name") or "")
            rejected = "Yes" if any(w in resolution.lower() for w in REJECT_WORDS) else ("No" if resolution else None)
            status_name = ((f.get("status") or {}).get("name") or "")
            final = ("Rejected" if rejected == "Yes"
                     else "Fixed" if f.get("resolutiondate")
                     else "Open" if status_name.lower() not in [s.lower() for s in closed_states]
                     else "Closed")
            defects.append({
                "period": period, "key": key_, "link": link,
                "title": f.get("summary") or "", "kind": kind,
                "reported_by": reporter or None, "reported_on": _date(f.get("created")),
                "phase": "Post-release" if reporter.lower() in client_names else "QA",
                "pre_existing": None,
                "rejected": rejected, "rejection_reason": resolution or None,
                "evidence": link, "final_status": final,
                "against_task": ((f.get("parent") or {}).get("key")),
                "remarks": "",
            })
            if rejected is None:
                review.append({
                    "kind": "rejection", "subject": key_,
                    "question": f"{key_} has no resolution set. Was it a real defect?",
                    "proposal": "Treat it as a real defect", "link": link,
                })
            continue

        ttype, reason = classify(issue, conv)
        delivered = first_entry_into(moves, delivered_states) if delivered_states else None
        closed = _date(f.get("resolutiondate")) or first_entry_into(moves, closed_states)
        if not delivered and closed:
            delivered = closed
            review.append({
                "kind": "date", "subject": key_,
                "question": f"{key_} never entered {', '.join(delivered_states) or 'a delivery state'}. "
                            f"Count the closed date {closed} as the delivery?",
                "proposal": f"Use {closed}", "link": link,
            })
        reopened, rework_ev = was_reopened(moves, closed_states, reopen_states, ignore_first)
        understood, und_ev = had_to_ask(issue, moves, wf)
        seconds = f.get("timeoriginalestimate")

        tasks.append({
            "period": period, "key": key_, "link": link,
            "title": f.get("summary") or "", "type": ttype, "exclude_reason": reason,
            "planned": ttype == "Task",
            "hours_dev": round(seconds / 3600, 2) if seconds else None,
            "hours_qa": None,
            "hours_source": "Tracker estimate" if seconds else None,
            "story_points": f.get(points_field) if points_field else None,
            "assignee": ((f.get("assignee") or {}).get("displayName")),
            "created": _date(f.get("created")),
            "delivered": delivered,
            "closed": closed,
            "status": ((f.get("status") or {}).get("name")),
            "understood": understood, "understood_evidence": und_ev or None,
            # Dates are an agreement, not a field. The run settles them from the plan and the
            # evidence channels; leaving them null here keeps the adapter honest.
            "met_client_date": None, "met_commitment": None,
            "reopened": reopened, "rework_evidence": rework_ev or None,
            "remarks": "",
        })

    kif = {
        "kif_version": "1.0",
        "generated": {
            "adapter": ADAPTER, "adapter_version": VERSION,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_url": f"{base}/browse/{key}",
            "capabilities": ["status_history", "comments", "assignee", "estimates", "issue_type",
                             "labels", "created_date", "closed_date", "reporter"]
                            + (["story_points"] if points_field else []),
            "warnings": [
                "Client and commitment dates are left blank here: they are an agreement, not a Jira field. "
                "The run settles them from the plan and the evidence channels.",
            ],
        },
        "project": {
            "name": proj.get("name") or key,
            "tracker": "Jira", "tracker_url": base,
            "pms_project_id": proj.get("pms_project_id"),
            "period_type": proj.get("period_model") or (profile.get("periods") or {}).get("model") or "Sprint",
            "velocity_unit": proj.get("velocity_unit") or ("Story Points" if points_field else "Estimated Hours"),
            "client_check": (profile.get("periods") or {}).get("client_check_default", "Handover"),
        },
        "periods": list(periods.values()),
        "tasks": tasks, "defects": defects, "review": review[:40],
    }

    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(kif, indent=2), encoding="utf-8")
    print(f"Wrote {a.out}: {len(tasks)} task rows, {len(defects)} defect rows, "
          f"{len(kif['periods'])} period(s), {len(review)} question(s) for review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
