#!/usr/bin/env python3
"""
Where the assistant's judgement goes in, once, and is kept.

The assistant is the brain of a run, not its plumbing. It should never page through a board,
carry a spreadsheet through its context, or decide the same thing twice. So everything the
rules could not settle is written to ONE file, with exactly the context each call needs and
the definition it is to be judged by:

    <project>/judge/queue.json      read this
    <project>/judge/answers.json    write this, in the shape the queue file shows

and `kpi.py judge` folds the answers into the ledger. Each answer needs a `why`, because a
judgement that cannot say why is a guess, and a guess is how a number ends up wrong in a
way nobody can trace. The next run reuses every answer whose item has not changed, so the
queue shrinks to whatever is genuinely new.

The rubric below is the fixed part. Two assistants, or the same one on two days, must reach
the same verdict on the same card - that is the whole point of the tool - so the definitions
live here, in one place, and travel inside every queue file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import board as B

RUBRIC_VERSION = "1.0"

RUBRIC = {
    "nature": (
        "What the card is. Task: work in the agreed plan. CR: an approved addition after the plan was "
        "agreed (the client asked for more, and it was estimated or approved). Scope: in-scope work that is "
        "neither, such as planned feedback handling. Excluded: not a deliverable at all - QA admin, "
        "checklists, grouping or umbrella cards, milestones, duplicates, meeting notes. Bug: something that "
        "does not work as specified. Observation: a tester's remark that is not a failure. Improvement: a "
        "suggestion beyond the requirement. Query: a question raised as a card. Read the title's tags "
        "generously - '[Exisiting]', '[CRs]' and '(bug)' are typing, not new categories. When the title and "
        "the description disagree, the description wins."),
    "period": (
        "The KPI period the item belongs to. A planned item belongs to the period that planned it, an "
        "addition to the period it was approved for, and a report to the period whose work it was raised "
        "against - which is usually, but not always, the period it was dated in."),
    "understood": (
        "Yes if the team could build it without going back to the client to learn WHAT was wanted. No only "
        "when the requirement itself had to be explained or settled by the client after work began. Waiting "
        "on a build, an environment, access, test data, a priority call or a sign-off is NOT a comprehension "
        "problem. A developer asking a teammate is not either. Quote or link the message that shows it."),
    "reopened": (
        "Yes only if the item was closed (accepted as done) and afterwards put back in play. Failing QA while "
        "it is still being tested for the first time is normal testing, not rework. A card moved by mistake "
        "and moved straight back is not rework."),
    "pre_existing": (
        "Yes if the problem was already in the product before this project's work touched it - the team found "
        "it, but did not cause it. Signs: a tag like [Existing] (however it is spelled), 'also happens in "
        "production', 'not related to this release', reproducible on the old version. No if it is in code "
        "this project wrote or changed."),
    "rejected": (
        "Yes if the report was closed as not a defect: invalid, working as designed, duplicate, cannot "
        "reproduce, not feasible. A bug that was fixed, deferred or is still open is not rejected."),
    "phase": (
        "QA: found by the team before the build reached the client. Post-release: found by the client or by "
        "users after the handover. What decides it is who found it and whether the client already had the "
        "build - not the calendar alone. The team's own QA finding something after a handover is still QA."),
    "reasons": (
        "The 'why' of a KPI note: one to three plain sentences that tell a manager what they would otherwise "
        "have to ask - why the number is what it is, what happened, what was decided and by whom. It adds "
        "only new information: never repeat the count the note already printed, never restate the heading. "
        "Describe the work, not the person. Dates as mm/dd. No links, no em dashes, no filler. Use only the "
        "context given; if it does not explain the number, say what is missing instead of inventing a cause."),
}

FIELDS = {
    "nature": ["Task", "CR", "Scope", "Excluded", "Bug", "Observation", "Improvement", "Query"],
    "period": None, "understood": ["Yes", "No"], "reopened": ["Yes", "No"],
    "pre_existing": ["Yes", "No"], "rejected": ["Yes", "No"],
    "phase": ["QA", "Post-release", "UAT", "Development"],
}


def build_queue(work: dict, results: dict | None, facts: dict, project_dir: Path, period_names: list[str]) -> dict:
    grouped: dict[str, dict] = {}
    for q in work.get("queue") or []:
        g = grouped.setdefault(q["item_id"], {"item_id": q["item_id"], "item": q.get("item") or {}, "asks": []})
        # The richest context any question on this item asked for.
        for k, v in (q.get("item") or {}).items():
            g["item"].setdefault(k, v)
        g["asks"].append({k: q[k] for k in ("field", "question", "options", "proposal", "because",
                                            "confidence", "previously") if q.get(k) is not None})
    notes = _notes_needed(results, facts) if results else []
    used = sorted({a["field"] for g in grouped.values() for a in g["asks"]} | ({"reasons"} if notes else set()))
    answers = project_dir / "judge" / "answers.json"
    return {
        "what_this_is": (
            "Calls the rules could not make with confidence. Judge each one by the rubric, using only the "
            "context given here - do not open the board or search anywhere. Write your answers to "
            "answer_file in answer_shape, then run:  python3 scripts/kpi.py judge --project <id>. "
            "Every answer needs a one-sentence 'why'. If the context is not enough to decide, answer with "
            "\"value\": null and say what is missing; it will be put to a person instead of guessed."),
        "rubric_version": RUBRIC_VERSION,
        "rubric": {k: RUBRIC[k] for k in used},
        "periods": period_names,
        "answer_file": str(answers),
        "answer_shape": {
            "answers": [{"item_id": "<from items[]>", "field": "<from asks[]>", "value": "<one of options>",
                         "why": "<one sentence>", "evidence": "<url from the context, or null>"}],
            "reasons": [{"period": "<period>", "kpi": "<kpi name>", "why": "<the note's why, 1-3 sentences>"}]},
        "items": list(grouped.values()),
        "notes": notes,
    }


def _notes_needed(results: dict, facts: dict) -> list[dict]:
    """A missed KPI without a reason is the one thing PMS will not accept, so those are asked
    for. A met KPI is left alone unless the period has a story worth telling."""
    reasons = facts.get("reasons") or {}
    periods = {p.get("name"): p for p in ((facts.get("periods") or {}).get("periods") or [])}
    log = (facts.get("periods") or {}).get("log") or []
    out = []
    for per in results.get("periods") or []:
        name = per["period"]
        for m in per.get("measures") or []:
            if m.get("status") != "Not met" or (reasons.get(name) or {}).get(m["name"]):
                continue
            p = periods.get(name) or {}
            out.append({
                "period": name, "kpi": m["name"], "status": m["status"], "value": m.get("value"),
                "target": m.get("threshold"), "the_note_already_says": " || ".join(x for x in m.get("note_parts") or [] if x),
                "counted": (m.get("counted_keys") or [])[:15],
                "context": {"period_story": p.get("notes") or "", "original_plan": p.get("plan_text") or "",
                            "log": [e for e in log if e.get("period") in (name, None, "")][:12]},
            })
    return out


def write_queue(queue: dict, project_dir: Path) -> Path:
    path = project_dir / "judge" / "queue.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(queue, indent=1, ensure_ascii=False), encoding="utf-8")
    return path


def apply_answers(answers_path: Path, board: dict, ledger, facts: dict, period_names: list[str],
                  by: str = "ai", who: str = "") -> dict[str, Any]:
    """Fold answers into the ledger. Returns what was applied and what was refused, with the
    reason - a silently dropped answer is worse than a refused one."""
    try:
        doc = json.loads(answers_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return {"applied": [], "refused": [f"{answers_path} could not be read: {e}"], "reasons": 0, "unsure": []}
    items = {i["id"]: i for i in board.get("items") or []}
    applied, refused, unsure = [], [], []
    for a in doc.get("answers") or []:
        iid, field, value = str(a.get("item_id") or ""), a.get("field"), a.get("value")
        it = items.get(iid)
        label = (it or {}).get("key") or ((it or {}).get("title") or iid)[:40]
        if not it:
            refused.append(f"{iid}: not a card on this board")
            continue
        if field not in FIELDS:
            refused.append(f"{label}: '{field}' is not a field that can be judged")
            continue
        if value is None:
            unsure.append(f"{label} · {field}: {a.get('why') or 'not enough to decide'}")
            continue
        allowed = period_names if field == "period" else FIELDS[field]
        if value not in allowed:
            refused.append(f"{label} · {field}: '{value}' is not one of {', '.join(allowed)}")
            continue
        if not (a.get("why") or "").strip():
            refused.append(f"{label} · {field}: no 'why' given. A judgement that cannot say why is a guess")
            continue
        ok = ledger.set(iid, field, value, by, a["why"].strip(), evidence=a.get("evidence"),
                        fingerprint=B.fingerprint(it), key=it.get("key"), title=it.get("title"), who=who)
        (applied if ok else refused).append(
            f"{label} · {field} = {value}" if ok else f"{label} · {field}: a person already answered this; left alone")

    reasons = facts.setdefault("reasons", {})
    authors = reasons.setdefault("_authors", {})
    n = 0
    for r in doc.get("reasons") or []:
        per, kpi, why = r.get("period"), r.get("kpi"), (r.get("why") or "").strip()
        if per not in period_names or not kpi or not why:
            refused.append(f"reason for {per} · {kpi}: needs a known period, a KPI name and some text")
            continue
        tag = f"{per}|{kpi}"
        if authors.get(tag) == "human" and by != "human":
            refused.append(f"reason for {per} · {kpi}: a person wrote this one; left alone")
            continue
        reasons.setdefault(per, {})[kpi] = why
        authors[tag] = by
        n += 1
    return {"applied": applied, "refused": refused, "reasons": n, "unsure": unsure}
