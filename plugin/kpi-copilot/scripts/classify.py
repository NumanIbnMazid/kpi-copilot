#!/usr/bin/env python3
"""
From what the board says to what it means.

Input: a board snapshot (no judgement in it), the profile's conventions and workflow, the
project's facts (periods, plan, estimates) and its ledger. Output: KIF, plus the short list
of calls the rules could not make with confidence.

The order of authority for every judged field is fixed:

    a person's answer   (ledger, by: human)   - always wins
    an assistant's      (ledger, by: ai)      - wins while the item has not changed since
    the rules below                            - propose, with a confidence and a reason

Rules are tolerant on purpose. A literal match on "[Existing]" is correct right up to the
day somebody types "[Exisiting]", and then a bug that was already in the product is counted
against the team without anybody deciding that it should be. So a rule that nearly matches
says so: it proposes the tolerant reading, marks it, and the row carries a visible note -
"read [Exisiting] as Existing" - that a person can overrule in the sheet.

What a rule is not sure of goes to the judge queue (judge.py): one file an assistant reads
once and answers once, instead of a hundred cards opened one at a time. Its answers land in
the ledger, so the next run asks only about what is new.

Nothing here counts anything. Counting is the engine's job, and it is the same for everyone.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

import board as B

SURE = 0.75          # below this a proposal is put to the assistant rather than accepted

DEFAULT_TAGS = {
    "pre_existing": ["Existing", "Pre-existing", "Existing Issue", "Legacy", "Old Issue", "Production Issue"],
    "cr": ["CR", "Change Request", "Additional Request", "New Request"],
    "rejected": ["Rejected", "Invalid", "Not a Bug", "Won't Fix", "Wontfix", "Won't Do", "Duplicate", "By Design",
                 "As Designed", "Cannot Reproduce", "Not Reproducible", "Not Feasible", "Not Planned", "Declined"],
    "deferred": ["Deferred", "Out of Scope", "Moved Out", "Postponed", "Future"],
}
KIND_WORDS = {"Bug": ["Bug", "Defect", "Issue"], "Observation": ["Observation", "Obs"],
              "Improvement": ["Improvement", "Enhancement", "Suggestion"], "Query": ["Query", "Question"]}
PRE_EXISTING_CUES = ("already in production", "exists in production", "existing issue", "existing bug",
                     "not related to this release", "also in live", "reproducible in production",
                     "reproducible on production", "present before", "old issue", "legacy issue")
CLARIFY_CUES = ("clarif", "please confirm", "can you confirm", "could you confirm", "what should",
                "should it", "should we", "expected behaviour", "expected behavior", "need your input",
                "waiting for your", "requirement is not clear", "not clear", "which one")


def on_time(done: str | None, due: str | None, today: str) -> str | None:
    """Yes / No / Pending, or None when there was no date to be on time for. The workbook's
    live formulas mirror exactly this, so a date edited in the sheet moves the number the
    same way a rerun would."""
    if not due:
        return None
    if done:
        return "Yes" if done <= due else "No"
    return "Pending" if today <= due else "No"


def _later(a: str | None, b: str | None) -> str | None:
    return max(a, b) if a and b else None


def _similar(a: str, b: str) -> float:
    a, b = B.norm(B.strip_tags(a)), B.norm(B.strip_tags(b))
    if not a or not b:
        return 0.0
    if a == b or (len(min(a, b, key=len)) >= 12 and (a in b or b in a)):
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _rx(pattern: str | None):
    if not pattern:
        return None
    try:
        return re.compile(pattern, re.I)
    except re.error:
        return None


class Proposal(dict):
    """value + who says so + why + how sure."""

    def __init__(self, value: Any, why: str, confidence: float, by: str = "rule", flag: str = "",
                 evidence: str | None = None):
        super().__init__(value=value, why=why, confidence=confidence, by=by, flag=flag, evidence=evidence)


class Classifier:
    def __init__(self, board: dict, profile: dict, project_cfg: dict, facts: dict, ledger, today: str):
        self.board, self.profile, self.project_cfg = board, profile or {}, project_cfg or {}
        self.facts, self.ledger, self.today = facts or {}, ledger, today
        self.conv = self.profile.get("conventions") or {}
        self.wf = self.profile.get("workflow") or {}
        self.trk = self.profile.get("tracker") or {}
        self.src = self.profile.get("sources") or {}
        self.tags = {**DEFAULT_TAGS, **{k: v for k, v in (self.conv.get("tags") or {}).items() if v}}
        self.caps = set(board.get("capabilities") or [])
        self.queue: list[dict] = []
        self.questions: list[dict] = []
        self.review: list[dict] = []

        per = self.facts.get("periods") or {}
        self.periods: list[dict] = [dict(p) for p in (per.get("periods") or [])]
        self.project_dates = per.get("project") or {}
        if not self.periods:
            model = (self.profile.get("periods") or {}).get("model") or "Full project"
            self.periods = [{"name": "Full Project"}]
            self.questions.append({
                "id": "periods", "about": "the project",
                "question": f"No periods are defined for this project (facts/periods.yaml is missing). "
                            f"The profile says the period model is '{model}'. What are the periods, with "
                            f"their start and end dates?",
                "proposal": "Treat the whole project as one period called 'Full Project'."})
        self.period_names = [p["name"] for p in self.periods]

        self.plan_rows = [dict(r, _src="plan") for r in ((self.facts.get("plan") or {}).get("items") or [])]
        self.est_rows = [dict(r, _src="estimates") for r in ((self.facts.get("estimates") or {}).get("items") or [])]
        self.grain = ((self.facts.get("plan") or {}).get("grain") or self.project_cfg.get("deliverable_grain")
                      or "board-cards")
        self._matched: set[int] = set()

    # -- the ledger outranks the rules ----------------------------------------------------

    def settle(self, item: dict, field: str, prop: Proposal, question: str, options: list[str],
               context: str = "comments") -> Proposal:
        fp = B.fingerprint(item)
        kept = self.ledger.usable(item["id"], field, fp) if self.ledger else None
        if kept:
            return Proposal(kept["value"], kept.get("why") or "", 1.0, by=kept["by"],
                            flag=("the item changed after this was decided by hand"
                                  if kept["by"] == "human" and kept.get("fingerprint") not in (None, fp) else ""),
                            evidence=kept.get("evidence"))
        if prop["confidence"] < SURE or prop["flag"]:
            deferred = self.ledger.usable(item["id"], "deferred:" + field, fp) if self.ledger else None
            if deferred:
                self.questions.append({"id": f"judge:{item['id']}:{field}", "about": item.get("key") or item["title"],
                                       "question": f"{item.get('key') or item['title']}: {question} "
                                                   f"Missing context: {deferred['why']}", "options": options,
                                       "proposal": prop["value"]})
                prop["flag"] = "Waiting for a person: " + deferred["why"]
                return prop
            before = self.ledger.stale(item["id"], field, fp) if self.ledger else None
            self.queue.append({
                "item_id": item["id"], "field": field, "question": question, "options": options,
                "proposal": prop["value"], "because": prop["why"], "confidence": round(prop["confidence"], 2),
                "previously": ({"value": before["value"], "why": before.get("why"), "note":
                                "answered before the item changed"} if before else None),
                "_context": context,
            })
        return prop

    # -- matching cards to the plan and the estimates ---------------------------------------

    def match_scope(self, item: dict) -> tuple[dict | None, float]:
        best, score = None, 0.0
        for idx, row in enumerate(self.plan_rows + self.est_rows):
            rk = (row.get("board_key") or row.get("key") or "").strip()
            s = 0.0
            if rk and (rk == (item.get("key") or "") or rk == item["id"]):
                s = 1.0
            elif row.get("title"):
                s = _similar(item["title"], row["title"])
            if s > score:
                best, score = dict(row, _idx=idx), s
        return (best, score) if score >= 0.62 else (None, score)

    # -- what kind of thing is this card ----------------------------------------------------

    def nature(self, item: dict) -> tuple[Proposal, dict | None]:
        title = item.get("title") or ""
        if item.get("kind") in ("milestone", "approval", "section"):
            return Proposal("Excluded", f"an Asana {item['kind']} marker, not a deliverable", 0.95), None
        for pat in self.conv.get("exclude_patterns") or []:
            rx = _rx(pat)
            if rx and rx.search(title):
                return Proposal("Excluded", f"title matches the exclude pattern {pat}", 0.95), None

        kind = self._defect_kind(item)
        if kind:
            return kind, None

        row, score = self.match_scope(item)
        marker = _rx(self.conv.get("cr_marker"))
        cr_tag, how, raw = B.find_tag(title, self.tags["cr"])
        if not cr_tag:
            for lab in item.get("tags") or []:
                w, h = B.match_vocab(lab, self.tags["cr"])
                if w:
                    cr_tag, how, raw = w, h, lab
                    break
        if marker and marker.search(title):
            return Proposal("CR", "title carries the change-request marker", 0.95), row
        if cr_tag:
            return Proposal("CR", f"title tag [{raw}] read as {cr_tag}", 0.95 if how == "exact" else 0.8,
                            flag="" if how == "exact" else f"read [{raw}] as {cr_tag}"), row
        if row and row["_src"] == "estimates":
            sure = score >= 0.85
            return Proposal("CR", f"matches the approved addition '{row.get('title')}'",
                            0.9 if sure else 0.6, flag="" if sure else "loose title match to the estimates"), row
        if row and row["_src"] == "plan":
            sure = score >= 0.85
            return Proposal("Task", f"matches the plan item '{row.get('title')}'",
                            0.9 if sure else 0.6, flag="" if sure else "loose title match to the plan"), row
        if not self.plan_rows and not self.est_rows:
            return Proposal("Task", "no plan or estimates are on file, so every deliverable card is "
                                    "treated as planned work", 0.8), None
        return Proposal("Scope", "on the board but in neither the plan nor the approved additions", 0.4), None

    def _defect_kind(self, item: dict) -> Proposal | None:
        title, by = item.get("title") or "", self.conv.get("defect_by") or "title-pattern"
        dvals = self.conv.get("defect_values") or ["Bug"]
        ovals = self.conv.get("observation_values") or ["Observation", "Improvement"]
        hit = None
        if by == "separate-board" or (self.trk.get("options") or {}).get("defect_board"):
            hit = "Bug"
        elif by == "label":
            hit = next((t for t in item.get("tags") or [] if B.match_vocab(t, dvals + ovals)[0]), None)
        elif by in ("field", "issue-type"):
            fname = (self.trk.get("options") or {}).get("defect_field") or "Type"
            v = str((item.get("fields") or {}).get(fname) or "")
            hit = v if B.match_vocab(v, dvals + ovals)[0] else None
        else:
            rx = _rx(self.conv.get("defect_pattern"))
            m = rx.search(title) if rx else None
            hit = m.group(0) if m else None
        if not hit:
            return None
        for kind, words in KIND_WORDS.items():
            word, how = B.match_vocab(re.sub(r"[\d\s:#-]+$", "", hit), words)
            if word:
                return Proposal(kind, f"'{hit.strip()}' in the {'title' if by == 'title-pattern' else by}",
                                0.95 if how == "exact" else 0.8,
                                flag="" if how == "exact" else f"read '{hit.strip()}' as {kind}")
        return Proposal("Bug", f"'{hit}' marks it as a report, but not which kind", 0.6)

    # -- which period ----------------------------------------------------------------------

    def period_of(self, item: dict, when: str | None, scope_row: dict | None, report: bool = False) -> Proposal:
        if len(self.periods) == 1:
            return Proposal(self.period_names[0], "the project has one period", 1.0)
        if scope_row and scope_row.get("period") in self.period_names:
            return Proposal(scope_row["period"], f"the {scope_row['_src']} puts it there", 0.95)
        for rule in (self.profile.get("periods") or {}).get("by_section") or []:
            rx = _rx(rule.get("section"))
            if rx and rx.search(item.get("section") or "") and rule.get("period") in self.period_names:
                return Proposal(rule["period"], f"column '{item.get('section')}'", 0.9)
        if when:
            inside = [p for p in self.periods if (p.get("start") or "0") <= when <= (p.get("end") or "9")]
            if len(inside) == 1:
                return Proposal(inside[0]["name"], f"dated {when}, inside that period", 0.85)
            if len(inside) > 1:
                return Proposal(inside[-1]["name"], f"dated {when}, which falls in {len(inside)} overlapping "
                                                    f"periods", 0.5)
            dated = [p for p in self.periods if p.get("start")]
            before = [p for p in dated if p["start"] <= when]
            if report and before:
                # Raised after a period closed and before the next began: it is about the work
                # already handed over, not the work that has not started.
                prior = max(before, key=lambda p: p["start"])
                return Proposal(prior["name"], f"reported {when}, after {prior['name']} ended and before the "
                                               f"next period began", 0.6)
            if dated:
                near = min(dated, key=lambda p: min(abs(_days(when, p.get("start"))), abs(_days(when, p.get("end") or p.get("start")))))
                return Proposal(near["name"], f"dated {when}, outside every period; nearest is {near['name']}", 0.5)
        return Proposal(self.period_names[-1], "nothing says which period; the latest is assumed", 0.4)

    # -- rows -------------------------------------------------------------------------------

    def task_row(self, item: dict, nat: Proposal, scope_row: dict | None) -> dict:
        basis: dict[str, dict] = {}
        notes: list[str] = []

        def keep(field: str, p: Proposal) -> Any:
            basis[field] = {k: v for k, v in p.items() if k != "value" and v not in ("", None)}
            if p["flag"]:
                notes.append(p["flag"])
            elif p["by"] == "rule" and p["confidence"] < SURE:
                notes.append(f"{field.replace('_', ' ')}: {p['why']} (not confirmed)")
            return p["value"]

        ttype = keep("type", nat)
        delivered, closed = self._delivered(item), self._closed(item)
        guess = self.period_of(item, delivered or B.day(item.get("created_at")), scope_row)
        if ttype == "Excluded":
            period = guess["value"]          # it reaches no denominator, so it is not worth a question
        else:
            period = keep("period", self.settle(item, "period", guess,
                                                "Which period does this item belong to?", self.period_names))
        per = next((p for p in self.periods if p["name"] == period), self.periods[0])

        row: dict[str, Any] = {
            "period": period, "key": item.get("key") or item["id"], "link": item.get("url"),
            "title": item.get("title") or "", "type": ttype, "exclude_reason": None,
            "planned": None, "hours_dev": None, "hours_qa": None, "hours_source": None,
            "story_points": _num((item.get("fields") or {}).get(self.trk.get("story_point_field") or "Story Points")),
            "assignee": item.get("assignee"), "created": B.day(item.get("created_at")),
            "delivered": delivered, "closed": closed, "status": item.get("section"),
            "understood": None, "understood_evidence": None, "understood_why": None,
            "met_client_date": None, "client_date": None, "met_commitment": None, "commit_date": None,
            "reopened": None, "rework_evidence": None, "remarks": "", "_item": item["id"],
        }
        if ttype == "Excluded":
            row["exclude_reason"] = nat["why"]
            row["remarks"] = nat["why"][:1].upper() + nat["why"][1:]
            row["basis"], row["check"] = basis, "; ".join(notes)
            return row

        row["planned"] = ttype == "Task"
        self._hours(item, row, scope_row)

        if "status_history" in self.caps or item.get("events"):
            p = self.settle(item, "reopened", self._reopened(item, row),
                            "Was this item closed and then reopened (rework)? A QA failure while it was "
                            "still being tested for the first time is not rework.", ["Yes", "No"], "events")
            row["reopened"] = keep("reopened", p) if closed or p["value"] == "Yes" else None
            if p.get("evidence") and row["reopened"] == "Yes":
                row["rework_evidence"] = p["evidence"]
        if "comments" in self.caps or "status_history" in self.caps or item.get("comments"):
            p = self.settle(item, "understood", self._understood(item),
                            "Did the team understand this requirement without having to go back to the "
                            "client to explain WHAT to build? Waiting on a build, an environment, access or "
                            "a priority call is not a comprehension problem.", ["Yes", "No"])
            row["understood"] = keep("understood", p)
            if p["value"] == "No":
                row["understood_evidence"], row["understood_why"] = p.get("evidence") or item.get("url"), p["why"]

        # Dates: the item's own, then the period's, then the project's.
        client = (scope_row or {}).get("client_date") or per.get("client_date") or self.project_dates.get("client_date")
        commit = (scope_row or {}).get("commit_date") or per.get("commit_date") or self.project_dates.get("commit_date")
        check = per.get("client_check") or self.project_dates.get("client_check") or \
            (self.profile.get("periods") or {}).get("client_check_default") or "Handover"
        handover = per.get("handover_date")
        row["client_date"], row["commit_date"] = client, commit
        row["met_client_date"] = on_time(delivered if check == "Delivery" else _later(delivered, handover),
                                         client, self.today)
        cm = self.wf.get("commitment") or {}
        if commit or cm.get("scope") == "all-deliverables":
            by_handover = "handover" in str(cm.get("met_when") or "").lower()
            row["met_commitment"] = on_time(_later(delivered, handover) if by_handover else delivered,
                                            commit, self.today) if commit else None

        remarks = []
        if scope_row and scope_row.get("milestone"):
            remarks.append(f"Plan: {scope_row['milestone']}")
        if scope_row and scope_row.get("approved_on"):
            remarks.append(f"Approved {_md(scope_row['approved_on'])}")
        if per.get("plan_commit_date") and per.get("plan_commit_date") != commit:
            remarks.append(f"Original plan: {_md(per['plan_commit_date'])}")
        row["remarks"] = ". ".join(remarks)
        row["basis"], row["check"] = basis, "; ".join(dict.fromkeys(notes))
        return row

    def _hours(self, item: dict, row: dict, scope_row: dict | None) -> None:
        est = _num((item.get("fields") or {}).get(self.trk.get("estimate_field") or "Estimated Time"))
        planned = scope_row and (scope_row.get("dev_hours") is not None or scope_row.get("qa_hours") is not None)
        first = self.src.get("hours_first") or "plan"
        if planned and (first == "plan" or est is None):
            dev, qa = _num(scope_row.get("dev_hours")), _num(scope_row.get("qa_hours"))
            label = "Project plan" if scope_row["_src"] == "plan" else "Estimates sheet"
            row["hours_dev"], row["hours_qa"] = dev, qa
            row["hours_source"] = f"{label}: dev {_g(dev)}" + (f" + QA {_g(qa)}" if qa else "")
        elif est is not None:
            row["hours_dev"], row["hours_source"] = est, "Tracker estimate"

    def _delivered(self, item: dict) -> str | None:
        cfg = self.wf.get("delivered_when") or {}
        signal, states = cfg.get("signal") or "status-entered", cfg.get("values") or []
        if signal == "closed" or not states:
            return self._closed(item)
        since = cfg.get("from_date")
        hit = B.first_entered(item, states)
        if since and hit and hit < since:
            hit = B.first_entered(item, cfg.get("fallback_values") or states) or hit
        if not hit and B._in(item.get("section"), states):
            # It is sitting in a delivered column but the move itself was not seen (a card
            # created there, or history not read). The completion date is the nearest fact.
            hit = B.day(item.get("completed_at"))
        return hit

    def _closed(self, item: dict) -> str | None:
        states = (self.wf.get("closed_when") or {}).get("values") or []
        if not states:
            return B.day(item.get("completed_at")) if item.get("completed") else None
        if not B._in(item.get("section"), states):
            return None
        return B.last_entered(item, states) or B.day(item.get("completed_at")) or B.day(item.get("modified_at"))

    def _reopened(self, item: dict, row: dict) -> Proposal:
        cfg = self.wf.get("reopened_when") or {}
        closed_states = (self.wf.get("closed_when") or {}).get("values") or []
        back = cfg.get("values") or []
        hit = B.entered_after(item, closed_states, back) if closed_states and back else None
        if not hit and any(e.get("kind") == "reopened" for e in item.get("events") or []) and not closed_states:
            hit = next(e for e in item["events"] if e.get("kind") == "reopened")
        if hit:
            closed_on = B.first_entered(item, closed_states) or "earlier"
            return Proposal("Yes", f"closed {_md(closed_on)}, then moved back to '{hit.get('to') or 'open'}' on "
                                   f"{_md(B.day(hit.get('at')))}", 0.85,
                            evidence=f"Closed on {_md(closed_on)} and reopened on {_md(B.day(hit.get('at')))}")
        first_close = B.first_entered(item, closed_states) if closed_states else None
        fails = [e for e in B.ever_in(item, back) if "fail" in B.norm(e.get("to") or "")
                 and (not first_close or (B.day(e.get("at")) or "") <= first_close)]
        if fails and cfg.get("ignore_first_qa_fail", True):
            when = _md(B.day(fails[0].get("at")))
            row["rework_evidence"] = (f"Failed QA on {when} while still being tested for the first time, so it "
                                      f"is not counted as rework (the task was never closed and reopened)")
        return Proposal("No", "never moved back after being closed", 0.9)

    def _understood(self, item: dict) -> Proposal:
        cfg = self.wf.get("clarification_when") or {}
        waits = B.ever_in(item, cfg.get("values") or [])
        excuses = [w.lower() for w in (cfg.get("exclude_reasons") or ["build", "environment", "access"])]
        clients = [c.lower() for c in (self.conv.get("client_names") or [])]
        if waits:
            at = waits[0].get("at") or ""
            near = [c for c in item.get("comments") or [] if abs(_days(B.day(c.get("at")), B.day(at))) <= 3]
            text = " ".join((c.get("text") or "").lower() for c in near)
            excuse = next((w for w in excuses if w in text), None)
            if excuse and not any(cue in text for cue in CLARIFY_CUES):
                return Proposal("Yes", f"waited in '{waits[0].get('to')}' on {_md(B.day(at))}, but for "
                                       f"{excuse}, not for the requirement", 0.7)
            return Proposal("No", f"went to '{waits[0].get('to')}' on {_md(B.day(at))}", 0.55,
                            evidence=(near[0].get("url") if near else item.get("url")))
        if cfg.get("also_comments", True):
            for c in item.get("comments") or []:
                text = (c.get("text") or "").lower()
                if any(cue in text for cue in CLARIFY_CUES) and (not clients or any(n in text for n in clients)):
                    return Proposal("Yes", "a comment asks the client something; it may or may not be about "
                                           "the requirement", 0.6, evidence=c.get("url"))
        return Proposal("Yes", "no sign of a question to the client in its history", 0.85)

    def defect_row(self, item: dict, nat: Proposal) -> dict:
        basis: dict[str, dict] = {}
        notes: list[str] = []

        def keep(field: str, p: Proposal) -> Any:
            basis[field] = {k: v for k, v in p.items() if k != "value" and v not in ("", None)}
            if p["flag"]:
                notes.append(p["flag"])
            elif p["by"] == "rule" and p["confidence"] < SURE:
                notes.append(f"{field.replace('_', ' ')}: {p['why']} (not confirmed)")
            return p["value"]

        kind = keep("kind", nat)
        reported = B.day(item.get("created_at"))
        period = keep("period", self.settle(item, "period", self.period_of(item, reported, None, report=True),
                                            "Which period was this reported against?", self.period_names))
        per = next((p for p in self.periods if p["name"] == period), self.periods[0])
        title = item.get("title") or ""

        word, how, raw = B.find_tag(title, self.tags["pre_existing"])
        if not word:                                   # trackers with real labels use those instead of title tags
            for lab in item.get("tags") or []:
                w, h = B.match_vocab(lab, self.tags["pre_existing"])
                if w:
                    word, how, raw = w, h, lab
                    break
        text = ((item.get("description") or "") + " " + " ".join(c.get("text") or "" for c in item.get("comments") or [])).lower()
        if word:
            pre = Proposal("Yes", f"title tag [{raw}] read as {word}", 0.95 if how == "exact" else 0.8,
                           flag="" if how == "exact" else f"read [{raw}] as {word}")
        elif any(cue in text for cue in PRE_EXISTING_CUES):
            cue = next(c for c in PRE_EXISTING_CUES if c in text)
            pre = Proposal("Yes", f"its description or comments say '{cue}'", 0.55)
        else:
            pre = Proposal("No", "no sign it was in the product before this work", 0.85)
        pre = self.settle(item, "pre_existing", pre,
                          "Was this problem already in the product before this project's work touched it?",
                          ["Yes", "No"])

        rej_word, rhow, rraw = B.find_tag(title, self.tags["rejected"])
        sect_word, shhow = B.match_vocab(item.get("section") or "", self.tags["rejected"])
        # Jira records why an issue was closed as a resolution; GitHub as a label.
        res = str((item.get("fields") or {}).get("Resolution") or "")
        res_word, _ = B.match_vocab(res, self.tags["rejected"])
        lab_word = next((w for w in (B.match_vocab(t, self.tags["rejected"])[0] for t in item.get("tags") or []) if w), None)
        if res_word or lab_word:
            sect_word = sect_word or res_word or lab_word
            rej = Proposal("Yes", f"resolved as '{res}'" if res_word else f"labelled '{lab_word}'", 0.9)
        elif sect_word:
            rej = Proposal("Yes", f"sits in the '{item.get('section')}' column", 0.9 if shhow == "exact" else 0.75,
                           flag="" if shhow == "exact" else f"read column '{item.get('section')}' as {sect_word}")
        elif rej_word:
            rej = Proposal("Yes", f"title tag [{rraw}] read as {rej_word}", 0.9 if rhow == "exact" else 0.75,
                           flag="" if rhow == "exact" else f"read [{rraw}] as {rej_word}")
        else:
            rej = Proposal("No", "nothing marks it as rejected", 0.9)
        rej = self.settle(item, "rejected", rej,
                          "Was this report rejected - invalid, by design, duplicate, not reproducible?", ["Yes", "No"])

        handover = per.get("handover_date")
        clients = [c.lower() for c in (self.conv.get("client_names") or [])]
        by_client = bool(item.get("created_by")) and any(n in (item.get("created_by") or "").lower() for n in clients)
        if handover and reported and reported > handover and by_client:
            phase = Proposal("Post-release", f"reported by the client on {_md(reported)}, after the "
                                             f"{_md(handover)} handover", 0.85)
        elif handover and reported and reported > handover:
            phase = Proposal("QA", f"reported {_md(reported)}, after the {_md(handover)} handover, but by the "
                                   f"team rather than the client", 0.7,
                             flag="reported after handover by the team's own QA; counted as found before release")
        else:
            phase = Proposal("QA", "reported before the handover", 0.9)
        phase = self.settle(item, "phase", phase,
                            "Who found this, and when: the team before the handover (QA), or the client or "
                            "users after it (Post-release)?", ["QA", "Post-release", "UAT", "Development"], "none")

        closed_states = (self.wf.get("closed_when") or {}).get("values") or []
        dword, _ = B.match_vocab(item.get("section") or "", self.tags["deferred"])
        if rej["value"] == "Yes":
            final = "Rejected"
        elif dword:
            final = "Deferred"
        elif B._in(item.get("section"), closed_states) or (not closed_states and item.get("completed")):
            final = "Fixed"
        else:
            final = "Open"

        return {
            "period": period, "key": item.get("key") or _defect_key(title) or item["id"],
            "link": item.get("url"), "title": title, "kind": kind,
            "reported_by": item.get("created_by"), "reported_on": reported,
            "phase": keep("phase", phase), "pre_existing": keep("pre_existing", pre),
            "rejected": keep("rejected", rej),
            "rejection_reason": (rej_word or sect_word) if rej["value"] == "Yes" else None,
            "evidence": item.get("url"), "final_status": final, "against_task": None,
            "remarks": "", "basis": basis, "check": "; ".join(dict.fromkeys(notes)), "_item": item["id"],
        }

    # -- the whole board ----------------------------------------------------------------------

    def run(self) -> dict:
        tasks, defects = [], []
        by_id = {i["id"]: i for i in self.board.get("items") or []}
        include_sub = bool((self.trk.get("options") or {}).get("include_subtasks"))
        for item in self.board.get("items") or []:
            if item.get("parent") and not include_sub:
                continue
            nat, scope_row = self.nature(item)
            nat = self.settle(item, "nature", nat,
                              "What is this card? Task = in the agreed plan. CR = an approved addition. Scope = "
                              "in-scope work that is neither. Excluded = not a deliverable (admin, grouping, "
                              "duplicate). Bug / Observation / Improvement / Query = a report against the work.",
                              ["Task", "CR", "Scope", "Excluded", "Bug", "Observation", "Improvement", "Query"],
                              "description")
            if scope_row is not None:
                self._matched.add(scope_row["_idx"])
            if nat["value"] in ("Bug", "Observation", "Improvement", "Query", "Other"):
                row = self.defect_row(item, nat)
                if item.get("parent") and by_id.get(item["parent"]):
                    row["against_task"] = by_id[item["parent"]].get("key")
                defects.append(row)
            else:
                tasks.append(self.task_row(item, nat, scope_row))

        for row in tasks + defects:
            self._overlay(row)
        for row in tasks + defects:
            row["_row"] = row["_item"]
        tasks = self._plan_only_rows(tasks)
        extra = self.facts.get("extra_rows") or {}
        for kind, rows in (("tasks", tasks), ("defects", defects)):
            for x in extra.get(kind) or []:
                rows.append(self._hand_row(kind, x))
        if self.grain == "plan-items":
            tasks = self._explode(tasks)
        self._attach_context()
        self._period_questions(defects)
        return {"tasks": tasks, "defects": defects}

    def _overlay(self, row: dict) -> None:
        """A value a person typed over in the sheet - a date, an hours figure - outranks what
        the board says, and the dependent Yes/No is worked out again from it."""
        if not self.ledger or not row.get("_item"):
            return
        mine = ((self.ledger.data["items"].get(row["_item"]) or {}).get("judgements") or {})
        sets = {f[4:]: j["value"] for f, j in mine.items() if f.startswith("set:")}
        if not sets:
            return
        for k, v in sets.items():
            if k == "client_expected":
                if v == "No":
                    row["client_date"] = None
            elif k == "team_committed":
                if v == "No":
                    row["commit_date"] = None
            elif k == "planned":
                row["planned"] = v == "Yes"
            elif k in ("hours_dev", "hours_qa", "story_points"):
                row[k] = _num(v)
            elif k in row:
                row[k] = v or None
        if "type" in row and row.get("type") != "Excluded":
            per = next((p for p in self.periods if p["name"] == row["period"]), self.periods[0])
            check = per.get("client_check") or self.project_dates.get("client_check") or "Handover"
            ho, dl = per.get("handover_date"), row.get("delivered")
            by_handover = "handover" in str((self.wf.get("commitment") or {}).get("met_when") or "").lower()
            row["met_client_date"] = on_time(dl if check == "Delivery" else _later(dl, ho), row.get("client_date"), self.today)
            row["met_commitment"] = on_time(_later(dl, ho) if by_handover else dl, row.get("commit_date"), self.today)
        note = "set by hand in the sheet: " + ", ".join(k.replace("_", " ") for k in sets)
        row["check"] = "; ".join(x for x in (row.get("check"), note) if x)

    def _hand_row(self, kind: str, x: dict) -> dict:
        per = x.get("period") if x.get("period") in self.period_names else self.period_names[-1]
        base = {"period": per, "key": str(x.get("key") or x.get("title") or "row")[:60], "link": None,
                "title": x.get("title") or "", "remarks": "", "basis": {}, "_item": None, "_row": None,
                "check": "added by hand in the sheet"}
        if kind == "defects":
            return {**base, "kind": x.get("kind") or "Bug", "reported_by": None, "reported_on": None,
                    "phase": PHASE_IN_HAND.get(x.get("phase"), "QA"), "pre_existing": x.get("pre_existing") or "No",
                    "rejected": x.get("rejected") or "No", "rejection_reason": x.get("rejection_reason"),
                    "evidence": None, "final_status": None, "against_task": None}
        p = next(q for q in self.periods if q["name"] == per)
        client = x.get("client_date") or p.get("client_date") or self.project_dates.get("client_date")
        commit = x.get("commit_date") or p.get("commit_date") or self.project_dates.get("commit_date")
        return {**base, "type": x.get("type") or "Task", "exclude_reason": None, "planned": x.get("planned") != "No",
                "hours_dev": _num(x.get("hours_dev")), "hours_qa": _num(x.get("hours_qa")), "hours_source": "Typed in the sheet",
                "story_points": _num(x.get("story_points")), "assignee": None, "created": None,
                "delivered": x.get("delivered"), "closed": x.get("closed"), "status": None,
                "understood": x.get("understood"), "understood_evidence": None, "understood_why": None,
                "met_client_date": on_time(x.get("delivered"), client, self.today), "client_date": client,
                "met_commitment": on_time(x.get("delivered"), commit, self.today) if commit else None,
                "commit_date": commit, "reopened": x.get("reopened"), "rework_evidence": None}

    def _plan_only_rows(self, tasks: list[dict]) -> list[dict]:
        """A plan item with no card of its own is still work the team agreed to. It gets a row,
        so the denominators match the plan, and a question, because nobody can see from the
        board whether it was done."""
        for idx, r in enumerate(self.plan_rows + self.est_rows):
            if idx in self._matched or r.get("board_key") or not r.get("title"):
                continue
            qid = f"scope:{B.norm(r['title'])[:40]}"
            ans = (self.ledger.answer(qid) if self.ledger else None) or {}
            per = r.get("period") if r.get("period") in self.period_names else self.period_names[0]
            p = next(x for x in self.periods if x["name"] == per)
            delivered = ans.get("delivered") or r.get("delivered")
            known = bool(delivered or ans)      # somebody has said something about it
            commit = r.get("commit_date") or p.get("commit_date") or self.project_dates.get("commit_date")
            client = r.get("client_date") or p.get("client_date") or self.project_dates.get("client_date")
            tasks.append({
                "period": per, "key": f"PLAN: {r['title']}"[:60], "link": None, "title": r["title"],
                "type": "Task" if r["_src"] == "plan" else "CR", "exclude_reason": None,
                "planned": r["_src"] == "plan", "hours_dev": _num(r.get("dev_hours")),
                "hours_qa": _num(r.get("qa_hours")),
                "hours_source": "Project plan" if r["_src"] == "plan" else "Estimates sheet",
                "story_points": None, "assignee": None, "created": None, "delivered": delivered,
                "closed": ans.get("closed") or delivered, "status": "Done" if delivered else "Not on the board",
                "understood": None, "understood_evidence": None, "understood_why": None,
                # Until somebody says whether it was delivered, it is left out of the on-time
                # measures rather than counted as late: unknown is not the same as missed.
                "met_client_date": on_time(delivered, client, self.today) if known else None, "client_date": client,
                "met_commitment": on_time(delivered, commit, self.today) if (commit and known) else None,
                "commit_date": commit, "reopened": None, "rework_evidence": None,
                "remarks": "In the plan with no card of its own on the board", "basis": {},
                "check": "" if known else "no card on the board; delivery date not known", "_item": None,
                "_row": f"plan:{B.norm(r['title'])[:40]}",
            })
            if not known:
                self.questions.append({
                    "id": qid, "about": r["title"],
                    "question": f"'{r['title']}' is in the {r['_src']} but has no card on the board. Was it "
                                f"delivered, and on what date?",
                    "proposal": "Leave it as not delivered.", "answer_shape": {"delivered": "YYYY-MM-DD"}})
        return tasks

    def _explode(self, tasks: list[dict]) -> list[dict]:
        """Deliverable grain = plan items. One board card that the plan breaks into modules
        becomes one row per module, each inheriting the card's history and verdicts, so the
        denominators match the plan's own breakdown rather than the way the board was cut."""
        mods = {(r.get("board_key") or B.norm(r.get("title") or "")): r for r in self.plan_rows if r.get("modules")}
        out, n = [], 0
        for t in tasks:
            spec = mods.get(t["key"]) or mods.get(B.norm(t["title"]))
            if not spec or t["type"] != "Task":
                out.append(t)
                continue
            for i, m in enumerate(spec["modules"]):
                n += 1
                r = dict(t)
                r["key"], r["title"] = f"PLAN-{n:02d}", f"{t['title']} - {m.get('name')}"
                r["_row"] = f"{t.get('_item')}#{i + 1}"
                r["hours_dev"] = _num(m.get("dev_hours"))
                r["hours_qa"] = _num(spec.get("qa_hours")) if i == 0 else 0.0   # QA is planned per feature
                r["hours_source"] = "Project plan"
                r["remarks"] = (f"Plan item under {t['key']}, which the board tracks as one card"
                                + (f". {t['remarks']}" if t.get("remarks") else ""))
                out.append(r)
        return out

    def _attach_context(self) -> None:
        """Give each queued question only what is needed to answer it. The assistant reads one
        file; it should not have to open the board."""
        by_id = {i["id"]: i for i in self.board.get("items") or []}
        for q in self.queue:
            it = by_id[q["item_id"]]
            want = q.pop("_context", "comments")
            q["item"] = {"key": it.get("key"), "title": it.get("title"), "url": it.get("url"),
                         "column": it.get("section"), "created": B.day(it.get("created_at")),
                         "created_by": it.get("created_by"), "tags": B.tags_of(it.get("title") or "")}
            if want in ("description", "comments"):
                q["item"]["description"] = (it.get("description") or "")[:600]
            if want in ("events", "comments"):
                q["item"]["history"] = " -> ".join(
                    f"{e.get('to') or e.get('kind')} {_md(B.day(e.get('at')))}" for e in B.moves(it)[-10:])
            if want == "comments":
                q["item"]["comments"] = [
                    {"at": B.day(c.get("at")), "by": c.get("by"), "text": (c.get("text") or "")[:400],
                     "url": c.get("url")} for c in (it.get("comments") or [])[-6:]]

    def _period_questions(self, defects: list[dict]) -> None:
        for p in self.periods:
            late = [d for d in defects if d["period"] == p["name"] and (d.get("reported_on") or "") > (p.get("end") or "9")]
            if not p.get("handover_date") and p.get("end") and p["end"] < self.today:
                self.questions.append({
                    "id": f"handover:{p['name']}", "about": p["name"],
                    "question": f"{p['name']} ended on {_md(p['end'])} but has no handover date. When did its "
                                f"build reach the client? It decides Escaped Defect Rate and the client-date "
                                f"check.", "proposal": "Leave it as not handed over yet.",
                    "answer_shape": {"handover_date": "YYYY-MM-DD"},
                    "where": "facts/periods.yaml, or the Periods tab"})
            if late and len(late) > 3:
                self.review.append({"kind": "date", "subject": p["name"],
                                    "question": f"{len(late)} reports are dated after {p['name']} ended.",
                                    "proposal": "Keep them in this period.", "link": None})


PHASE_IN_HAND = {"Pre-release": "QA", "Post-release": "Post-release"}


def _days(a: str | None, b: str | None) -> int:
    from datetime import date
    try:
        return (date.fromisoformat(a[:10]) - date.fromisoformat(b[:10])).days  # type: ignore[index]
    except (TypeError, ValueError):
        return 10 ** 6


def _md(value: str | None) -> str:
    return f"{value[5:7]}/{value[8:10]}" if value and len(value) >= 10 else (value or "")


def _num(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "", "-") else None
    except (TypeError, ValueError):
        m = re.search(r"\d+(?:\.\d+)?", str(value))
        return float(m.group(0)) if m else None


def _g(value: float | None) -> str:
    return f"{value:g}" if value is not None else "0"


def _defect_key(title: str) -> str | None:
    m = re.search(r"\b(Bug|Observation|Improvement|Obs)\s?#?\d+", title or "", re.I)
    return m.group(0) if m else None


def to_kif(board: dict, profile: dict, project_cfg: dict, facts: dict, ledger, today: str) -> tuple[dict, dict]:
    """Returns (kif, work) where work holds what needs a brain or a person: the judge queue,
    the questions only a person can answer, and counts for the report."""
    c = Classifier(board, profile, project_cfg, facts, ledger, today)
    rows = c.run()
    per_facts = facts.get("periods") or {}
    proj = per_facts.get("project") or {}
    kif = {
        "kif_version": "1.0",
        "generated": {
            "adapter": board.get("adapter") or board.get("tracker") or "board",
            "adapter_version": board.get("adapter_version") or "2.0.0", "at": B.now_iso(),
            "source_url": board.get("url") or "", "capabilities": board.get("capabilities") or [],
            "warnings": [],
        },
        "project": {
            "name": project_cfg.get("name") or board.get("project_name") or "",
            "tracker": (board.get("tracker") or "").title(), "tracker_url": board.get("url") or "",
            "pms_project_id": project_cfg.get("pms_project_id"),
            "period_type": project_cfg.get("period_model") or (profile.get("periods") or {}).get("model")
            or "Delivery cycle",
            "velocity_unit": project_cfg.get("velocity_unit") or (profile.get("periods") or {}).get("velocity_unit")
                             or "Estimated Hours",
            "client_date": proj.get("client_date"), "commit_date": proj.get("commit_date"),
            "client_check": proj.get("client_check") or (profile.get("periods") or {}).get("client_check_default")
            or "Handover",
            "dates_why": proj.get("dates_why") or "", "sources_text": proj.get("sources_text") or "",
        },
        "periods": [{k: v for k, v in p.items() if not k.startswith("_")} for p in c.periods],
        "tasks": rows["tasks"], "defects": rows["defects"], "review": c.review[:40],
    }
    # Period names are join keys. Truncating only the period loses every attached task.
    # PMS limits are checked at the delivery boundary instead.
    work = {"queue": c.queue, "questions": c.questions, "grain": c.grain,
            "counts": {"cards": len(board.get("items") or []), "tasks": len(rows["tasks"]),
                       "defects": len(rows["defects"]), "to_judge": len(c.queue)}}
    return kif, work
