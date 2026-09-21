#!/usr/bin/env python3
"""
Asana, read directly.

The first Asana adapter converted the output of a browser extractor that this repository
never shipped. In practice that meant an assistant wrote a scraper, ran it in a tab, and
carried fifty kilobytes of JSON back through a chat window - on every run. That, not the
arithmetic, was the half hour.

This reads the board through Asana's REST API in a few seconds and keeps what it read:

  * one paged call lists every task on the board with the fields that matter,
  * each task's history (section moves, completions, comments) is fetched in parallel,
  * and only for tasks whose `modified_at` moved since the cached snapshot.

A 150-card board is ~15 seconds cold and 2-3 seconds warm. It makes no judgements: the
result is a board snapshot (scripts/board.py), and everything that needs a rule or a brain
happens afterwards, the same way for every tracker.

Token: a personal access token (Asana > Settings > Apps > Developer apps > Personal access
tokens), read from $ASANA_TOKEN or ~/.config/kpi-copilot/credentials.json. It is read-only
in practice - this file only ever issues GET. Nobody should paste a token into a chat: the
person puts it in the environment or the file themselves.

No token and no way to get one? `browser_snapshot.js` beside this file collects the same raw
responses from a signed-in tab and downloads them as a file; `--from-raw` reads it.

    python3 api.py --project 1200000000000001 --out board.json [--cache board.json]
    python3 api.py --from-raw asana-raw.json --out board.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
import board as B  # noqa: E402
import connect     # noqa: E402
import host_transport  # noqa: E402

API = "https://app.asana.com/api/1.0"
ADAPTER, VERSION = "asana", "2.0.0"

TASK_FIELDS = ",".join([
    "name", "notes", "completed", "completed_at", "created_at", "modified_at", "due_on",
    "start_on", "assignee.name", "created_by.name", "memberships.project.gid",
    "memberships.section.name", "tags.name", "custom_fields.name",
    "custom_fields.display_value", "custom_fields.number_value",
    "custom_fields.enum_value.name", "parent.gid", "num_subtasks", "permalink_url",
    "resource_subtype",
])
STORY_FIELDS = ",".join([
    "created_at", "created_by.name", "resource_subtype", "type", "text",
    "old_section.name", "new_section.name", "custom_field.name",
    "old_enum_value.name", "new_enum_value.name", "old_text_value", "new_text_value",
])
CAPABILITIES = ["status_history", "comments", "assignee", "estimates", "story_points",
                "labels", "created_date", "closed_date", "reporter"]

_MOVED = re.compile(r'moved (?:this \w+ )?from "?(.+?)"? to "?(.+?)"?(?: in .+)?$', re.I)


class AsanaError(RuntimeError):
    pass


def find_token(env_name: str | None = None) -> str | None:
    """A personal access token, or the access token of a browser sign-in - whichever is there."""
    cred = connect.credential("asana", env_name)
    return cred["bearer"] if cred else None


NO_TOKEN = "Asana is not connected.\n" + connect.advise(["asana"]) + \
    "\nDo not paste a token into a chat: the person saves it themselves."


class Client:
    def __init__(self, token: str, timeout: float = 30.0):
        self.token, self.timeout = token, timeout
        self.requests = 0

    def get(self, path: str, params: dict | None = None) -> dict:
        if host_transport.enabled("asana"):
            self.requests += 1
            try:
                return host_transport.call("asana", "GET", API + path, params=params)
            except host_transport.TransportError as e:
                raise AsanaError(str(e)) from e
        url = f"{API}{path}" + (("?" + urllib.parse.urlencode(params)) if params else "")
        for attempt in range(6):
            req = urllib.request.Request(url, headers={
                "Authorization": f"Bearer {self.token}", "Accept": "application/json"})
            try:
                self.requests += 1
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 429 or e.code >= 500:
                    wait = float(e.headers.get("Retry-After") or (2 ** attempt))
                    time.sleep(min(wait, 60))
                    continue
                body = e.read().decode("utf-8", "replace")[:300]
                if e.code == 401:
                    raise AsanaError("Asana rejected the token (401). It may have been revoked; make a new one.") from e
                if e.code in (403, 404):
                    raise AsanaError(f"Asana says {e.code} for {path}. Check the project id, and that this "
                                     f"account can open the board.") from e
                raise AsanaError(f"Asana {e.code} on {path}: {body}") from e
            except urllib.error.URLError as e:
                if attempt == 5:
                    raise AsanaError(f"Could not reach Asana: {e.reason}") from e
                time.sleep(2 ** attempt)
        raise AsanaError(f"Asana kept rate-limiting {path}; try again in a minute.")

    def pages(self, path: str, params: dict) -> list[dict]:
        out: list[dict] = []
        params = dict(params, limit=100)
        while True:
            doc = self.get(path, params)
            out.extend(doc.get("data") or [])
            nxt = (doc.get("next_page") or {}).get("offset")
            if not nxt:
                return out
            params["offset"] = nxt


# --------------------------------------------------------------------------------------
# raw Asana -> board snapshot
# --------------------------------------------------------------------------------------

def _field_value(f: dict) -> Any:
    if f.get("number_value") is not None:
        return f["number_value"]
    if (f.get("enum_value") or {}).get("name"):
        return f["enum_value"]["name"]
    return f.get("display_value")


def _section(task: dict, project_gid: str) -> str | None:
    """A card can live in several projects. Only this project's section is its status."""
    for m in task.get("memberships") or []:
        if (m.get("project") or {}).get("gid") == project_gid and m.get("section"):
            return m["section"].get("name")
    return None


def item_from_task(task: dict, project_gid: str, key_pattern: str | None,
                   key_field: str | None = None, linked: bool = False) -> dict:
    title = task.get("name") or ""
    key = None
    if key_pattern:
        m = re.search(key_pattern, title)
        key = m.group(0) if m else None
    fields = {f.get("name"): _field_value(f) for f in (task.get("custom_fields") or []) if f.get("name")}
    if key_field and fields.get(key_field) not in (None, ""):
        key = str(fields[key_field]).strip()
    section = _section(task, project_gid)
    if linked and not section:
        other_sections = {m['section']['name'] for m in task.get('memberships') or []
                          if (m.get('section') or {}).get('name')}
        if len(other_sections) == 1:
            section = next(iter(other_sections))
    return {
        "id": task.get("gid"), "key": key,
        "url": task.get("permalink_url") or f"https://app.asana.com/0/{project_gid}/{task.get('gid')}",
        "title": title, "description": (task.get("notes") or "")[:4000],
        "section": section, "completed": bool(task.get("completed")),
        "created_at": task.get("created_at"), "created_by": (task.get("created_by") or {}).get("name"),
        "completed_at": task.get("completed_at"), "modified_at": task.get("modified_at"),
        "due_on": task.get("due_on"), "start_on": task.get("start_on"),
        "assignee": (task.get("assignee") or {}).get("name"),
        "tags": [t.get("name") for t in (task.get("tags") or []) if t.get("name")],
        "fields": {k: v for k, v in fields.items() if v not in (None, "")},
        "parent": (task.get("parent") or {}).get("gid"),
        "subtasks": task.get("num_subtasks") or 0,
        "kind": task.get("resource_subtype") or "default_task",
        "events": [], "comments": [], "history_at": None,
    }


def history_from_stories(stories: list[dict], task_gid: str, project_gid: str,
                         sections: set[str], keep_comments: bool) -> tuple[list[dict], list[dict]]:
    events, comments = [], []
    known = {B.norm(s) for s in sections}
    for s in stories:
        sub, at = s.get("resource_subtype") or "", s.get("created_at")
        by = (s.get("created_by") or {}).get("name")
        if sub == "section_changed":
            old, new = (s.get("old_section") or {}).get("name"), (s.get("new_section") or {}).get("name")
            if not new:
                m = _MOVED.search(s.get("text") or "")
                old, new = (m.group(1), m.group(2)) if m else (None, None)
            # The same card can move in another project too; only this board's columns count.
            if new and (not known or B.norm(new) in known):
                events.append({"at": at, "kind": "section", "from": old, "to": new, "by": by})
        elif sub == "marked_complete":
            events.append({"at": at, "kind": "completed", "by": by})
        elif sub == "marked_incomplete":
            events.append({"at": at, "kind": "reopened", "by": by})
        elif sub == "enum_custom_field_changed":
            events.append({"at": at, "kind": "field", "field": (s.get("custom_field") or {}).get("name"),
                           "from": (s.get("old_enum_value") or {}).get("name"),
                           "to": (s.get("new_enum_value") or {}).get("name"), "by": by})
        elif sub == "comment_added" and keep_comments:
            comments.append({"at": at, "by": by, "text": (s.get("text") or "")[:1500],
                             "url": f"https://app.asana.com/0/{project_gid}/{task_gid}/{s.get('gid')}/f"})
    events.sort(key=lambda e: e.get("at") or "")
    return events, comments


def snapshot(project_gid: str, token: str, cache: dict | None = None, *, key_pattern: str | None = None,
             key_field: str | None = None,
             comments: str = "on-demand", touched_since: str | None = None, workers: int = 8,
             progress=None, include_subtasks: bool = False, linked_tasks: list[str] | None = None) -> dict:
    """Read the board. `cache` is the previous snapshot; an item whose modified_at has not
    moved keeps the history already read for it, which is what makes the second run fast."""
    say = progress or (lambda *_: None)
    c = Client(token)
    project = c.get(f"/projects/{project_gid}", {"opt_fields": "name,permalink_url"}).get("data") or {}
    sections = [s.get("name") for s in c.pages(f"/projects/{project_gid}/sections", {"opt_fields": "name"})]
    tasks = c.pages("/tasks", {"project": project_gid, "opt_fields": TASK_FIELDS})
    if include_subtasks:
        tasks = expand_subtasks(c, tasks, workers)
    tasks = add_linked_tasks(c, tasks, linked_tasks or [], workers)
    say(f"{len(tasks)} cards listed")

    old = {i["id"]: i for i in ((cache or {}).get("items") or [])
           if (cache or {}).get("project_ref") == project_gid
           and (comments == "never" or "comments" in (cache or {}).get("capabilities", []))}
    items, stale = [], []
    for t in tasks:
        it = item_from_task(t, project_gid, key_pattern, key_field,
                            linked=str(t.get("gid")) in {str(gid) for gid in linked_tasks or []})
        prev = old.get(it["id"])
        if prev and prev.get("history_at") and prev.get("modified_at") == it["modified_at"]:
            it["events"], it["comments"], it["history_at"] = prev["events"], prev["comments"], prev["history_at"]
        elif touched_since and (it["modified_at"] or "") < touched_since and prev:
            it["events"], it["comments"], it["history_at"] = prev.get("events", []), prev.get("comments", []), prev.get("history_at")
        else:
            stale.append(it)
        items.append(it)

    keep_comments = comments != "never"
    sec = set(sections)

    def fill(it: dict) -> None:
        stories = c.pages(f"/tasks/{it['id']}/stories", {"opt_fields": STORY_FIELDS})
        it["events"], it["comments"] = history_from_stories(stories, it["id"], project_gid, sec, keep_comments)
        it["history_at"] = B.now_iso()

    if stale:
        say(f"reading history for {len(stale)} changed card{'s' if len(stale) != 1 else ''} "
            f"({len(items) - len(stale)} unchanged, reused)")
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            list(pool.map(fill, stale))

    return {
        "board_version": B.BOARD_VERSION, "tracker": "asana", "adapter": ADAPTER,
        "adapter_version": VERSION, "project_ref": project_gid,
        "project_name": project.get("name") or "", "url": project.get("permalink_url")
        or f"https://app.asana.com/0/{project_gid}", "fetched_at": B.now_iso(),
        "capabilities": CAPABILITIES if keep_comments else [x for x in CAPABILITIES if x != "comments"],
        "sections": sections, "items": items, "subtasks_expanded": include_subtasks,
        "stats": {"requests": c.requests, "refreshed": len(stale), "reused": len(items) - len(stale)},
    }


def add_linked_tasks(client, tasks: list[dict], linked: list[str], workers: int = 8) -> list[dict]:
    """Read only explicitly configured tasks elsewhere; never scan their other projects."""
    if not isinstance(linked, list) or any(not re.fullmatch(r"[0-9]+", str(gid)) for gid in linked):
        raise AsanaError("tracker.options.linked_tasks must be a list of Asana task IDs.")
    seen = {t["gid"]: t for t in tasks}
    missing = sorted({str(gid) for gid in linked} - set(seen))
    def read_one(gid):
        task = client.get(f"/tasks/{gid}", {"opt_fields": TASK_FIELDS}).get("data") or {}
        if str(task.get("gid")) != gid:
            raise AsanaError("The linked task response did not match the requested task.")
        return task
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for task in pool.map(read_one, missing):
            seen[task["gid"]] = task
    return list(seen.values())


def expand_subtasks(client, tasks: list[dict], workers: int = 8) -> list[dict]:
    """Subtasks need not belong directly to their parent's project. Read each once."""
    seen = {t["gid"]: t for t in tasks}
    pending = [t for t in tasks if t.get("num_subtasks")]
    visited = set()
    while pending:
        batch = [t for t in pending if t["gid"] not in visited]
        visited.update(t["gid"] for t in batch)
        pending = []
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            children = list(pool.map(lambda t: client.pages(f"/tasks/{t['gid']}/subtasks",
                                                           {"opt_fields": TASK_FIELDS}), batch))
        for rows in children:
            for child in rows:
                seen[child["gid"]] = child
                if child.get("num_subtasks") and child["gid"] not in visited:
                    pending.append(child)
        if len(seen) > 10000:
            raise AsanaError("Subtask expansion exceeds 10000 cards; narrow the project scope before retrying.")
    return list(seen.values())


def read(project: dict, profile: dict, cache: dict | None, progress=None) -> dict:
    """The entry point every reader has: this project's board, as a snapshot."""
    trk, conv, scan = profile.get("tracker") or {}, profile.get("conventions") or {}, profile.get("scan") or {}
    gid = str(project.get("tracker_ref") or trk.get("project_ref") or "")
    if not gid:
        raise B.ReaderError("The project has no tracker_ref - the long number in the Asana board's URL.")
    token = "host-session" if host_transport.enabled("asana") else find_token((trk.get("options") or {}).get("token_env"))
    if not token:
        raise B.ReaderError(NO_TOKEN)
    try:
        return snapshot(gid, token, cache, key_pattern=conv.get("key_pattern"), key_field=trk.get("key_field"),
                        comments=scan.get("comments") or "on-demand",
                        include_subtasks=bool((trk.get("options") or {}).get("include_subtasks")),
                        linked_tasks=(trk.get("options") or {}).get("linked_tasks") or [],
                        touched_since=project.get("_touched_since"), progress=progress)
    except AsanaError as e:
        raise B.ReaderError(str(e)) from e


def from_raw(raw: dict, key_pattern: str | None = None, comments: str = "on-demand",
             key_field: str | None = None, linked_tasks: list[str] | None = None) -> dict:
    """The same snapshot from a file of raw API responses - what browser_snapshot.js downloads,
    or anything else that saved {project, sections, tasks, stories:{gid:[...]}}."""
    gid = str((raw.get("project") or {}).get("gid") or raw.get("project_gid") or "")
    sections = [s.get("name") for s in raw.get("sections") or []]
    items = []
    for t in raw.get("tasks") or []:
        it = item_from_task(t, gid, key_pattern, key_field,
                            linked=str(t.get("gid")) in {str(gid) for gid in linked_tasks or []})
        stories = (raw.get("stories") or {}).get(it["id"])
        if not isinstance(stories, list):
            raise B.ReaderError("The Asana export is missing task history. Export the complete board again "
                                "with browser_snapshot.js; incomplete history cannot prove KPI values.")
        if stories is not None:
            it["events"], it["comments"] = history_from_stories(stories, it["id"], gid, set(sections),
                                                                comments != "never")
            it["history_at"] = raw.get("fetched_at") or B.now_iso()
        items.append(it)
    return {
        "board_version": B.BOARD_VERSION, "tracker": "asana", "adapter": ADAPTER,
        "adapter_version": VERSION, "project_ref": gid,
        "project_name": (raw.get("project") or {}).get("name") or "",
        "url": (raw.get("project") or {}).get("permalink_url") or f"https://app.asana.com/0/{gid}",
        "fetched_at": raw.get("fetched_at") or B.now_iso(),
        "capabilities": CAPABILITIES if comments != "never" else [x for x in CAPABILITIES if x != "comments"],
        "sections": sections, "items": items, "subtasks_expanded": bool(raw.get("subtasks_expanded")),
        "stats": {"requests": 0, "refreshed": len(items), "reused": 0},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Read an Asana board into a board snapshot.")
    ap.add_argument("--project", help="Asana project gid.")
    ap.add_argument("--from-raw", type=Path, help="Raw responses saved by browser_snapshot.js.")
    ap.add_argument("--cache", type=Path, help="Previous snapshot, to reuse unchanged history.")
    ap.add_argument("--key-pattern", help="Regex that finds the ticket key in a title.")
    ap.add_argument("--key-field", help="Custom field containing the ticket key; takes precedence over the title.")
    ap.add_argument("--include-subtasks", action="store_true", help="Read descendant tasks, including those not directly on the project.")
    ap.add_argument("--linked-task", action="append", default=[], help="An explicitly selected task from another board; repeat for each task.")
    ap.add_argument("--comments", default="on-demand", choices=["always", "on-demand", "never"])
    ap.add_argument("--token-env", help="Environment variable holding the token.")
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args(argv)

    started = time.time()
    try:
        if a.from_raw:
            snap = from_raw(json.loads(a.from_raw.read_text(encoding="utf-8")), a.key_pattern, a.comments,
                            a.key_field, a.linked_task)
        else:
            if not a.project:
                print("Need --project <gid> or --from-raw <file>.", file=sys.stderr)
                return 2
            token = find_token(a.token_env)
            if not token:
                print(NO_TOKEN, file=sys.stderr)
                return 3
            snap = snapshot(a.project, token, B.load(a.cache or a.out), key_pattern=a.key_pattern,
                            key_field=a.key_field, comments=a.comments, include_subtasks=a.include_subtasks,
                            linked_tasks=a.linked_task,
                            progress=lambda m: print(f"  {m}"))
    except (AsanaError, B.ReaderError) as e:
        print(str(e), file=sys.stderr)
        return 1
    B.save(a.out, snap)
    s = snap["stats"]
    print(f"Wrote {a.out}: {len(snap['items'])} cards, history refreshed for {s['refreshed']}, "
          f"reused for {s['reused']}, {s['requests']} requests, {time.time() - started:.1f}s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
