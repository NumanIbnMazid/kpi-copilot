#!/usr/bin/env python3
"""
GitHub Issues, and Projects, read directly.

One GraphQL query per fifty issues brings back everything a run needs - the issue, its
labels, its comments, and its history (closed, reopened, labelled, and every status change on
a Project board) - so a repository of a few hundred issues is read in a handful of requests.
On a rerun only issues updated since the cached snapshot are asked for.

What "status" means depends on how the team works:

  * With a **Project** (tracker.options.project, e.g. "orgs/acme/projects/7"), status is the
    project's Status field - "In progress", "In review", "Done" - and its changes are the
    history that delivery, rework and comprehension are read from.
  * Without one, status is simply Open, Closed, or Not planned (GitHub's "won't fix").

It makes no judgements. Labels arrive as tags, the issue type as a field; what counts as a
defect or a change request is decided afterwards by the profile's conventions, the same way
as for every other tracker.

Signing in: if GitHub's own `gh` command is signed in, nothing is needed - that is a browser
login with nothing to copy. Otherwise a token in $GITHUB_TOKEN, or `kpi.py auth github`.

    tracker: {adapter: github, options: {project: "orgs/acme/projects/7", status_field: Status}}
    projects: [{id: web, tracker_ref: "acme/web"}]          # one repository, or several: "acme/web, acme/api"
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
import board as B          # noqa: E402
import connect             # noqa: E402

SERVICE, ADAPTER, VERSION = "github", "github", "1.0.0"
CAPABILITIES = ["status_history", "comments", "assignee", "labels", "issue_type", "created_date",
                "closed_date", "reporter", "estimates", "story_points"]

_ISSUE = """
id number title body url state stateReason createdAt updatedAt closedAt
author{login} assignees(first:5){nodes{login}} labels(first:30){nodes{name}} milestone{title} %(type)s
projectItems(first:5){nodes{project{number title} fieldValues(first:30){nodes{__typename
  ... on ProjectV2ItemFieldSingleSelectValue{name field{... on ProjectV2SingleSelectField{name}}}
  ... on ProjectV2ItemFieldNumberValue{number field{... on ProjectV2Field{name}}}}}}}
comments(first:50){totalCount nodes{createdAt author{login} bodyText url}}
timelineItems(first:100,itemTypes:[CLOSED_EVENT,REOPENED_EVENT,LABELED_EVENT,UNLABELED_EVENT%(status_enum)s]){nodes{__typename
  ... on ClosedEvent{createdAt actor{login} stateReason}
  ... on ReopenedEvent{createdAt actor{login}}
  ... on LabeledEvent{createdAt actor{login} label{name}}
  ... on UnlabeledEvent{createdAt actor{login} label{name}}
  %(status_event)s}}
"""
_QUERY = """query($owner:String!,$name:String!,$cursor:String,$since:DateTime){repository(owner:$owner,name:$name){
  issues(first:50,after:$cursor,orderBy:{field:UPDATED_AT,direction:DESC},filterBy:{since:$since}){
    pageInfo{hasNextPage endCursor} nodes{%s}}}}"""
_FULL = {"type": "issueType{name}", "status_enum": ",PROJECT_V2_ITEM_STATUS_CHANGED_EVENT",
         "status_event": "... on ProjectV2ItemStatusChangedEvent{createdAt actor{login} previousStatus status}"}
_PLAIN = {"type": "", "status_enum": "", "status_event": ""}

NO_LOGIN = "GitHub is not connected.\n" + connect.advise(["github"])


class Client:
    def __init__(self, token: str, api: str = "https://api.github.com/graphql"):
        self.token, self.api, self.requests = token, api, 0

    def query(self, query: str, variables: dict) -> dict:
        body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
        for attempt in range(6):
            req = urllib.request.Request(self.api, data=body, headers={
                "Authorization": f"Bearer {self.token}", "Content-Type": "application/json",
                "User-Agent": "kpi-copilot"})
            try:
                self.requests += 1
                with urllib.request.urlopen(req, timeout=60) as r:
                    doc = json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code in (403, 429, 502, 503) and attempt < 5:
                    time.sleep(min(float(e.headers.get("Retry-After") or 2 ** attempt), 60))
                    continue
                if e.code == 401:
                    raise B.ReaderError("GitHub rejected the sign-in (401). Run `gh auth login --web`, or make a new token.") from e
                raise B.ReaderError(f"GitHub {e.code}: {e.read().decode('utf-8', 'replace')[:300]}") from e
            except urllib.error.URLError as e:
                if attempt == 5:
                    raise B.ReaderError(f"Could not reach GitHub: {e.reason}") from e
                time.sleep(2 ** attempt)
                continue
            if doc.get("errors") and not doc.get("data"):
                raise _QueryError("; ".join(str(x.get("message")) for x in doc["errors"])[:400])
            return doc.get("data") or {}
        raise B.ReaderError("GitHub kept asking to slow down; try again in a few minutes.")


class _QueryError(B.ReaderError):
    pass


def _status_of(node: dict, project_no: int | None, field: str) -> str | None:
    for pi in ((node.get("projectItems") or {}).get("nodes") or []):
        if project_no and (pi.get("project") or {}).get("number") != project_no:
            continue
        for fv in ((pi.get("fieldValues") or {}).get("nodes") or []):
            if fv.get("__typename") == "ProjectV2ItemFieldSingleSelectValue" and \
                    B.norm((fv.get("field") or {}).get("name") or "") == B.norm(field):
                return fv.get("name")
    return None


def item_from_issue(node: dict, repo: str, many: bool, project_no: int | None, status_field: str) -> dict:
    closed_as = {"NOT_PLANNED": "Not planned", "DUPLICATE": "Not planned"}.get(node.get("stateReason") or "", "Closed")
    state = "Open" if node.get("state") == "OPEN" else closed_as
    status = _status_of(node, project_no, status_field)
    fields = {"Milestone": (node.get("milestone") or {}).get("title"), "Type": (node.get("issueType") or {}).get("name")}
    for pi in ((node.get("projectItems") or {}).get("nodes") or []):
        for fv in ((pi.get("fieldValues") or {}).get("nodes") or []):
            if fv.get("__typename") == "ProjectV2ItemFieldNumberValue" and (fv.get("field") or {}).get("name"):
                fields[fv["field"]["name"]] = fv.get("number")
    events = []
    for t in ((node.get("timelineItems") or {}).get("nodes") or []):
        kind, at, by = t.get("__typename"), t.get("createdAt"), (t.get("actor") or {}).get("login")
        if kind == "ProjectV2ItemStatusChangedEvent" and t.get("status"):
            events.append({"at": at, "kind": "section", "from": t.get("previousStatus"), "to": t.get("status"), "by": by})
        elif kind == "ClosedEvent" and not status:
            to = {"NOT_PLANNED": "Not planned", "DUPLICATE": "Not planned"}.get(t.get("stateReason") or "", "Closed")
            events.append({"at": at, "kind": "section", "from": "Open", "to": to, "by": by})
        elif kind == "ReopenedEvent" and not status:
            events.append({"at": at, "kind": "section", "from": "Closed", "to": "Open", "by": by})
        elif kind == "ClosedEvent":
            events.append({"at": at, "kind": "completed", "by": by})
        elif kind == "ReopenedEvent":
            events.append({"at": at, "kind": "reopened", "by": by})
        elif kind in ("LabeledEvent", "UnlabeledEvent"):
            events.append({"at": at, "kind": "label", "to": (t.get("label") or {}).get("name"),
                           "added": kind == "LabeledEvent", "by": by})
    events.sort(key=lambda e: e.get("at") or "")
    return {
        "id": node["id"], "key": f"{repo.split('/')[-1]}#{node['number']}" if many else f"#{node['number']}",
        "url": node.get("url"), "title": node.get("title") or "", "description": (node.get("body") or "")[:4000],
        "section": status or state, "completed": node.get("state") != "OPEN",
        "created_at": node.get("createdAt"), "created_by": (node.get("author") or {}).get("login"),
        "completed_at": node.get("closedAt"), "modified_at": node.get("updatedAt"), "due_on": None, "start_on": None,
        "assignee": ", ".join(a["login"] for a in ((node.get("assignees") or {}).get("nodes") or [])) or None,
        "tags": [l["name"] for l in ((node.get("labels") or {}).get("nodes") or [])],
        "fields": {k: v for k, v in fields.items() if v not in (None, "")}, "parent": None, "subtasks": 0,
        "kind": "issue", "events": events,
        "comments": [{"at": c.get("createdAt"), "by": (c.get("author") or {}).get("login"),
                      "text": (c.get("bodyText") or "")[:1500], "url": c.get("url")}
                     for c in ((node.get("comments") or {}).get("nodes") or [])],
        "history_at": B.now_iso(),
    }


def _project_number(ref: str | None) -> int | None:
    digits = "".join(ch if ch.isdigit() else " " for ch in str(ref or "")).split()
    return int(digits[-1]) if digits else None


def read(project: dict, profile: dict, cache: dict | None, progress=None, max_items: int | None = None) -> dict:
    say = progress or (lambda *_: None)
    trk = profile.get("tracker") or {}
    opts = trk.get("options") or {}
    repos = [r.strip() for r in str(project.get("tracker_ref") or trk.get("project_ref") or "").split(",") if "/" in r]
    if not repos:
        raise B.ReaderError("The project needs tracker_ref: \"owner/repository\" (several, separated by commas, are fine).")
    cred = connect.credential("github", opts.get("token_env"))
    if not cred:
        raise B.ReaderError(NO_LOGIN)
    client = Client(cred["bearer"], opts.get("graphql_url") or "https://api.github.com/graphql")
    project_no, status_field = _project_number(opts.get("project")), opts.get("status_field") or "Status"
    ref = ",".join(repos)
    old = {i["id"]: i for i in (cache or {}).get("items") or []} if (cache or {}).get("project_ref") == ref else {}
    since = None
    if old and (cache or {}).get("fetched_at"):
        since = (datetime.fromisoformat(cache["fetched_at"]) - timedelta(minutes=5)).astimezone(timezone.utc) \
            .strftime("%Y-%m-%dT%H:%M:%SZ")
    cap = max_items or opts.get("max_items")

    fresh: dict[str, dict] = {}
    shape = _FULL
    for repo in repos:
        owner, name = repo.split("/", 1)
        cursor = None
        while True:
            try:
                data = client.query(_QUERY % (_ISSUE % shape), {"owner": owner, "name": name, "cursor": cursor, "since": since})
            except _QueryError as e:
                if shape is _FULL:                   # an older GitHub Enterprise without issue types / status events
                    shape = _PLAIN
                    say("this GitHub does not expose issue types or project status history; reading without them")
                    continue
                raise B.ReaderError(f"GitHub could not answer: {e}") from e
            if not data.get("repository"):
                raise B.ReaderError(f"GitHub has no repository {repo}, or this account cannot see it.")
            page = data["repository"]["issues"]
            for node in page["nodes"]:
                it = item_from_issue(node, repo, len(repos) > 1, project_no, status_field)
                fresh[it["id"]] = it
            cursor = page["pageInfo"]["endCursor"]
            if not page["pageInfo"]["hasNextPage"] or (cap and len(fresh) >= cap):
                break
    items = list({**old, **fresh}.values())
    say(f"{len(items)} issues; {len(fresh)} read now, {len(items) - len(fresh)} unchanged and reused")
    statuses = sorted({i["section"] for i in items if i.get("section")} | {"Open", "Closed", "Not planned"})
    caps = [c for c in CAPABILITIES if shape is _FULL or c != "issue_type"]
    return {
        "board_version": B.BOARD_VERSION, "tracker": "github", "adapter": ADAPTER, "adapter_version": VERSION,
        "project_ref": ref, "project_name": project.get("name") or ref, "url": f"https://github.com/{repos[0]}/issues",
        "fetched_at": B.now_iso(), "capabilities": caps, "sections": statuses, "items": items,
        "stats": {"requests": client.requests, "refreshed": len(fresh), "reused": len(items) - len(fresh)},
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Read GitHub issues into a board snapshot.")
    ap.add_argument("--repo", required=True, help="owner/repository (several: comma separated)")
    ap.add_argument("--project", help="A Projects (v2) board whose Status field is the status, e.g. orgs/acme/projects/7")
    ap.add_argument("--max-items", type=int)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args(argv)
    started = time.time()
    try:
        snap = read({"tracker_ref": a.repo}, {"tracker": {"options": {"project": a.project}}}, B.load(a.out),
                    lambda m: print(f"  {m}"), a.max_items)
    except B.ReaderError as e:
        print(str(e), file=sys.stderr)
        return 1
    B.save(a.out, snap)
    print(f"Wrote {a.out}: {len(snap['items'])} issues, {snap['stats']['requests']} requests, {time.time() - started:.1f}s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
