#!/usr/bin/env python3
"""
Jira, read directly - Cloud, Server and Data Center.

One search brings back a hundred issues at a time with their changelog attached, so a
project of a few hundred issues is a handful of requests; an issue with an unusually long
history or comment thread gets one more each. On a rerun only issues updated since the cached
snapshot are asked for.

Status is the issue's workflow status, and every status change in the changelog becomes a
move on the board - which is what delivery dates, rework and "had to ask the client" are read
from. The issue type, resolution, labels, estimate and story points arrive as fields and
tags. No judgement is made here: whether "Bug" means a defect, or "Won't Do" a rejected
report, is decided afterwards by the profile's conventions, the same way as for every tracker.

    tracker: {adapter: jira, url: https://acme.atlassian.net, story_point_field: Story Points}
    projects: [{id: identity, tracker_ref: ACME}]            # the project key, or
    tracker: {options: {jql: "project = ACME AND fixVersion = 4.2"}}

Signing in (scripts/connect.py): an API token with your email (Cloud), a personal access
token (Server / Data Center), or a browser sign-in when the company has registered an
Atlassian OAuth app. No credential at all? browser_snapshot.js beside this file downloads the
same responses from a signed-in tab; pass the file with --from-raw.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
import board as B          # noqa: E402
import connect             # noqa: E402

SERVICE, ADAPTER, VERSION = "jira", "jira", "2.0.0"
CAPABILITIES = ["status_history", "comments", "assignee", "estimates", "story_points", "issue_links",
                "labels", "issue_type", "created_date", "closed_date", "reporter"]
FIELDS = ["summary", "description", "status", "issuetype", "created", "updated", "resolutiondate", "resolution",
          "assignee", "reporter", "creator", "labels", "parent", "comment", "timeoriginalestimate", "priority",
          "fixVersions", "duedate"]

NO_LOGIN = "Jira is not connected.\n" + connect.advise(["jira"])


def adf_text(node: Any) -> str:
    """Jira Cloud sends rich text as a document tree. A judgement only needs the words."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(adf_text(n) for n in node)
    text = node.get("text") or ""
    if node.get("type") == "mention":
        text = (node.get("attrs") or {}).get("text") or ""
    inner = adf_text(node.get("content"))
    return text + inner + ("\n" if node.get("type") in ("paragraph", "heading", "listItem", "hardBreak") else "")


class Client:
    def __init__(self, site: str, cred: dict):
        self.site, self.cred, self.requests = site.rstrip("/"), cred, 0
        self.base = self.site
        if cred.get("cloud"):                          # a browser sign-in talks to Atlassian's gateway
            sites = self._call("GET", "https://api.atlassian.com/oauth/token/accessible-resources")
            hit = next((s for s in sites if s.get("url", "").rstrip("/") == self.site), None)
            if not hit:
                raise B.ReaderError("The browser sign-in did not grant access to any Jira site. Sign in again and pick the site.")
            self.base = f"https://api.atlassian.com/ex/jira/{hit['id']}"

    def _call(self, method: str, url: str, body: dict | None = None) -> Any:
        auth = f"Basic {self.cred['basic']}" if self.cred.get("basic") else f"Bearer {self.cred['bearer']}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        for attempt in range(6):
            req = urllib.request.Request(url, data=data, method=method, headers={
                "Authorization": auth, "Accept": "application/json", "Content-Type": "application/json"})
            try:
                self.requests += 1
                with urllib.request.urlopen(req, timeout=60) as r:
                    return json.loads(r.read().decode("utf-8") or "null")
            except urllib.error.HTTPError as e:
                if e.code in (429, 502, 503) and attempt < 5:
                    time.sleep(min(float(e.headers.get("Retry-After") or 2 ** attempt), 60))
                    continue
                if e.code in (404, 405, 410):
                    raise _NotHere(url) from e
                text = e.read().decode("utf-8", "replace")[:300]
                if e.code == 401:
                    raise B.ReaderError("Jira rejected the sign-in (401). The token may have expired; make a new one, "
                                        "or sign in again.") from e
                if e.code == 403:
                    raise B.ReaderError("Jira says this account may not see that project (403).") from e
                raise B.ReaderError(f"Jira {e.code}: {text}") from e
            except urllib.error.URLError as e:
                if attempt == 5:
                    raise B.ReaderError(f"Could not reach Jira at {self.site}: {e.reason}") from e
                time.sleep(2 ** attempt)
        raise B.ReaderError("Jira kept asking to slow down; try again in a few minutes.")

    def search(self, jql: str, fields: list[str]) -> list[dict]:
        """Cloud's current search first; the classic one for Server / Data Center."""
        out: list[dict] = []
        try:
            token = None
            while True:
                body = {"jql": jql, "fields": fields, "expand": "changelog", "maxResults": 100}
                if token:
                    body["nextPageToken"] = token
                doc = self._call("POST", f"{self.base}/rest/api/3/search/jql", body)
                out += doc.get("issues") or []
                token = doc.get("nextPageToken")
                if not token:
                    return out
        except _NotHere:
            start = 0
            while True:
                q = urllib.parse.urlencode({"jql": jql, "fields": ",".join(fields), "expand": "changelog",
                                            "maxResults": 100, "startAt": start})
                doc = self._call("GET", f"{self.base}/rest/api/2/search?{q}")
                got = doc.get("issues") or []
                out += got
                start += len(got)
                if not got or start >= int(doc.get("total") or 0):
                    return out

    def rest(self, key: str, what: str) -> list[dict]:
        """The whole changelog or comment thread of one issue, when the search cut it short."""
        out, start = [], 0
        while True:
            try:
                doc = self._call("GET", f"{self.base}/rest/api/3/issue/{key}/{what}?startAt={start}&maxResults=100")
            except _NotHere:
                doc = self._call("GET", f"{self.base}/rest/api/2/issue/{key}/{what}?startAt={start}&maxResults=100")
            got = doc.get("values") or doc.get("comments") or doc.get("histories") or []
            out += got
            start += len(got)
            if not got or start >= int(doc.get("total") or 0):
                return out

    def field_id(self, name: str) -> str | None:
        try:
            fields = self._call("GET", f"{self.base}/rest/api/3/field")
        except _NotHere:
            fields = self._call("GET", f"{self.base}/rest/api/2/field")
        return next((f["id"] for f in fields or [] if B.norm(f.get("name") or "") == B.norm(name)), None)


class _NotHere(Exception):
    pass


def _who(node: dict | None) -> str | None:
    return (node or {}).get("displayName") or (node or {}).get("name")


def item_from_issue(issue: dict, site: str, sp_field: str | None, sp_name: str, est_name: str) -> dict:
    f = issue.get("fields") or {}
    histories = issue.get("_histories") if "_histories" in issue else (issue.get("changelog") or {}).get("histories") or []
    events = []
    for h in histories:
        for ch in h.get("items") or []:
            if ch.get("field") == "status":
                events.append({"at": h.get("created"), "kind": "section", "from": ch.get("fromString"),
                               "to": ch.get("toString"), "by": _who(h.get("author"))})
            elif ch.get("field") == "resolution" and ch.get("toString"):
                events.append({"at": h.get("created"), "kind": "field", "field": "Resolution",
                               "from": ch.get("fromString"), "to": ch.get("toString"), "by": _who(h.get("author"))})
    events.sort(key=lambda e: e.get("at") or "")
    comments = issue.get("_comments") or (f.get("comment") or {}).get("comments") or []
    itype = f.get("issuetype") or {}
    est = f.get("timeoriginalestimate")
    fields = {"Type": itype.get("name"), "Resolution": (f.get("resolution") or {}).get("name"),
              "Priority": (f.get("priority") or {}).get("name"),
              est_name: round(est / 3600, 2) if isinstance(est, (int, float)) else None,
              sp_name: f.get(sp_field) if sp_field else None,
              "Epic": ((f.get("parent") or {}).get("key") if not itype.get("subtask") else None),
              "Fix version": ", ".join(v.get("name", "") for v in f.get("fixVersions") or []) or None}
    key = issue.get("key")
    return {
        "id": str(issue.get("id")), "key": key, "url": f"{site.rstrip('/')}/browse/{key}",
        "title": f.get("summary") or "", "description": adf_text(f.get("description"))[:4000],
        "section": (f.get("status") or {}).get("name"),
        "completed": ((f.get("status") or {}).get("statusCategory") or {}).get("key") == "done",
        "created_at": f.get("created"), "created_by": _who(f.get("reporter") or f.get("creator")),
        "completed_at": f.get("resolutiondate"), "modified_at": f.get("updated"), "due_on": f.get("duedate"),
        "start_on": None, "assignee": _who(f.get("assignee")), "tags": list(f.get("labels") or []),
        "fields": {k: v for k, v in fields.items() if v not in (None, "")},
        # Only a sub-task hangs off its parent. A story under an epic is a deliverable of its own.
        "parent": str((f.get("parent") or {}).get("id")) if itype.get("subtask") and f.get("parent") else None,
        "subtasks": 0, "kind": "issue", "events": events,
        "comments": [{"at": c.get("created"), "by": _who(c.get("author")), "text": adf_text(c.get("body"))[:1500],
                      "url": f"{site.rstrip('/')}/browse/{key}?focusedCommentId={c.get('id')}"} for c in comments],
        "history_at": B.now_iso(),
    }


def _board(items: list[dict], ref: str, site: str, name: str, stats: dict) -> dict:
    return {"board_version": B.BOARD_VERSION, "tracker": "jira", "adapter": ADAPTER, "adapter_version": VERSION,
            "project_ref": ref, "project_name": name, "url": site, "fetched_at": B.now_iso(),
            "capabilities": CAPABILITIES, "sections": sorted({i["section"] for i in items if i.get("section")}),
            "items": items, "stats": stats}


def read(project: dict, profile: dict, cache: dict | None, progress=None) -> dict:
    say = progress or (lambda *_: None)
    trk = profile.get("tracker") or {}
    opts = trk.get("options") or {}
    site = (trk.get("url") or "").rstrip("/")
    ref = str(project.get("tracker_ref") or trk.get("project_ref") or "")
    jql = opts.get("jql") or (f'project = "{ref}"' if ref else "")
    if not site or not jql:
        raise B.ReaderError("Jira needs tracker.url (https://yourcompany.atlassian.net) and the project's "
                            "tracker_ref (its project key), or tracker.options.jql.")
    cred = connect.credential("jira")
    if not cred:
        raise B.ReaderError(NO_LOGIN)
    client = Client(site, cred)
    sp_name, est_name = trk.get("story_point_field") or "Story Points", trk.get("estimate_field") or "Original Estimate"
    sp_field = client.field_id(sp_name)

    old = {i["id"]: i for i in (cache or {}).get("items") or []} if (cache or {}).get("project_ref") == (opts.get("jql") or ref) else {}
    # Reconcile current membership: a deleted issue or an issue moved out of the JQL result
    # cannot be removed from a cache by a modified-since query alone.
    issues = client.search(jql + " ORDER BY updated DESC", FIELDS + ([sp_field] if sp_field else []))
    fresh = {}
    for issue in issues:
        log = issue.get("changelog") or {}
        if int(log.get("total") or 0) > len(log.get("histories") or []):
            issue["_histories"] = client.rest(issue["key"], "changelog")
        thread = (issue.get("fields") or {}).get("comment") or {}
        if int(thread.get("total") or 0) > len(thread.get("comments") or []):
            issue["_comments"] = client.rest(issue["key"], "comment")
        it = item_from_issue(issue, site, sp_field, sp_name, est_name)
        fresh[it["id"]] = it
    items = list(fresh.values())
    say(f"{len(items)} issues; {len(fresh)} read now, {len(items) - len(fresh)} unchanged and reused")
    return _board(items, opts.get("jql") or ref, site, project.get("name") or ref,
                  {"requests": client.requests, "refreshed": len(fresh), "reused": len(items) - len(fresh)})


def from_raw(raw: dict, profile: dict, project: dict) -> dict:
    """The same snapshot from what browser_snapshot.js downloaded: {site, issues[], fields[]}."""
    trk = profile.get("tracker") or {}
    sp_name, est_name = trk.get("story_point_field") or "Story Points", trk.get("estimate_field") or "Original Estimate"
    sp_field = next((f["id"] for f in raw.get("fields") or [] if B.norm(f.get("name") or "") == B.norm(sp_name)), None)
    site = raw.get("site") or trk.get("url") or ""
    items = [item_from_issue(i, site, sp_field, sp_name, est_name) for i in raw.get("issues") or []]
    ref = str(project.get("tracker_ref") or raw.get("project") or "")
    return _board(items, ref, site, project.get("name") or ref, {"requests": 0, "refreshed": len(items), "reused": 0})
