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
import hashlib
from pathlib import Path
from typing import Any

import board as B

RUBRIC_VERSION = "1.2"

RUBRIC = {
    'against_task': 'Select the implementation whose requirement or changed code caused this confirmed defect. Use explicit references, the described failure and the candidate scope. A grouping card or the defect-fix card itself is not an implementation link. Similar words alone do not prove causation. If the supplied evidence cannot establish the link, answer null.',
    'approved_on': 'Select the date the client explicitly authorized this additional deliverable. A dated client instruction to implement it is approval; an internal estimate, card creation or a clarification question alone is not. If approval is pending or its date cannot be established, answer null. Explain the specific authorization evidence.',
    'request_kind': 'Additional request adds a new deliverable beyond the agreed scope. Change request changes an already agreed requirement or deliverable. Approval or an estimate alone does not distinguish these. Use the request description and approved scope; if that comparison is absent, answer null and ask for it.',
    'delivery': 'Yes only when the Closed item represents completed implementation accepted by Dev and QA. No for a finding closed without implementation, an unreproducible or invalid report, duplicate, administration, or cancellation. Closure alone is not evidence of delivered output. If the comments do not establish which occurred, answer null and ask for implementation/acceptance evidence.',
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
        "Yes only if the item was closed and afterwards put back in play because its own work was at fault. "
        "'Closed' is the project's own boundary in workflow.reopened_when (closed_values and note): where "
        "handing work to QA is the close, a QA failure after that hand-off IS rework, first QA round "
        "included, when this item's work caused it. Only where closing means QA acceptance is a failure "
        "during the first round of testing normal testing rather than rework. A card moved by mistake and moved straight back is not rework. Neither is a move back "
        "caused by something else: another item's bug, a build, deployment or environment problem, test "
        "data, a question or a priority change, or a card QA later closed with no change to this item. "
        "Read the comments around each move back. When only some moves back were real rework, answer Yes "
        "and add field 'reopen_count' with how many were."),
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
        "MUST: read the complete KPI note as a decision maker who knows standard KPIs but has no project "
        "background or access to the internal workbook. Write natural sentences explaining the actual work "
        "or event, then how it produced the result and any material exclusion or limit. Use two to four clauses separated "
        "by ||. Preserve enough work and event context for an unfamiliar reader; do not reduce the note "
        "to unexplained fragments. For a nonstandard measurement, include its formula and substituted "
        "numbers. State units where needed. Remove basic definitions and reviewer or "
        "authorization boilerplate. Keep material measurement limits in the note; put requests for "
        "missing evidence in review questions. Do not refer readers to Decisions, Team Review or the workbook. "
        "For CR, distinguish client approval of work and estimated hours from the team's internal story points. "
        "Never say the client approved story points unless the source explicitly says that. "
        "Do not describe an internal estimate as approved hours. For PI, label the hours-per-person-day "
        "conversion and the eligible resource count separately. "
        "Every sentence must identify the relevant work, event or outcome. Name the feature areas "
        "instead of saying only planned changes or accepted items. Say QA completed testing or "
        "confirmed the fix when supported by evidence. For rejection, describe how many bug reports "
        "were reviewed, how many were rejected, and the actual rejection reasons; do not say decided "
        "bug reports. Use the reporter's role only when established. Tell a short factual story, then "
        "show the calculation. Remove arithmetic asides such as not divided by the resource count again. "
        "Use familiar words, explain project-specific terms, and describe the "
        "work before referring to a ticket number. Do not infer a cause from a high ratio or a status change. "
        "Review Met and Not measured notes as carefully as missed KPIs. The 'why' is one to three plain "
        "sentences that tell a manager what they would otherwise "
        "have to ask - why the number is what it is, what happened, what was decided and by whom. It adds "
        "only new information: never repeat the count the note already printed, never restate the heading. "
        "Describe the work, not the person. Dates as mm/dd. No links, no em dashes, no filler. Use only the "
        "context given; if it does not explain the number, return a review question instead of inventing a cause."),
}

FIELDS = {
    'against_task': None, 'approved_on': None,
    'request_kind': ['Additional request','Change request'],
    'delivery': ['Yes','No'],
    "nature": ["Task", "CR", "Scope", "Excluded", "Bug", "Observation", "Improvement", "Query"],
    "period": None, "understood": ["Yes", "No"], "reopened": ["Yes", "No"],
    "reopen_count": [str(n) for n in range(0, 21)],
    "pre_existing": ["Yes", "No"], "rejected": ["Yes", "No"],
    "phase": ["QA", "Post-release", "UAT", "Development"],
}


def build_queue(work: dict, results: dict | None, facts: dict, project_dir: Path, period_names: list[str],
                kif: dict | None = None, profile: dict | None = None) -> dict:
    grouped: dict[str, dict] = {}
    for q in work.get("queue") or []:
        g = grouped.setdefault(q["item_id"], {"item_id": q["item_id"], "item": q.get("item") or {}, "asks": []})
        # The richest context any question on this item asked for.
        for k, v in (q.get("item") or {}).items():
            g["item"].setdefault(k, v)
        g["asks"].append({k: q[k] for k in ("field", "question", "options", "proposal", "because",
                                            "confidence", "previously", "candidate_event_dates") if q.get(k) is not None})
    notes = [n for n in _notes_needed(results, facts, review=True, kif=kif, profile=profile)
             if f"{n['period']}|{n['kpi']}" not in ((facts.get("reasons") or {}).get("_questions") or {})] if results else []
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
        "note_instructions": (profile or {}).get("custom_instructions") or {},
        "workflow": (profile or {}).get("workflow") or {},
        "periods": period_names,
        "answer_file": str(answers),
        "answer_shape": {
            "answers": [{"item_id": "<from items[]>", "field": "<from asks[]>", "value": "<one of options>",
                         "why": "<one sentence>", "evidence": "<url from the context, or null>",
                         "event_dates": "<optional for reopened Yes: accepted dates from candidate_event_dates; also set reopen_count when only some events count>"}],
            "reasons": [{"period": "<period>", "kpi": "<kpi name>", "why": "<1-3 sentences; empty if no extra context is needed; null if evidence is missing>",
                         "review_signature": "<from notes[]; confirms the COMPLETE note was reviewed for an uninvolved reader>",
                         "use_computed_summary": "<true only to replace an outdated edited summary with the reviewed current figures; old text is retained in history>",
                         "addendum": "<optional dated evidence update; preserves existing human context>",
                         "missing": "<when why is null, what the person needs to explain>"}]},
        "items": list(grouped.values()),
        "notes": notes,
    }


def _counts_as_defect(d: dict, profile: dict | None) -> bool:
    """The report types Defect Rejection Rate covers: the ones that can count as defects."""
    policy = (profile or {}).get("policy") or {}
    kind = d.get("kind") or "Bug"
    return (kind == "Bug" or (kind == "Observation" and bool(policy.get("count_observations")))
            or (kind == "Improvement" and bool(policy.get("count_improvements"))))


def _notes_needed(results: dict, facts: dict, review: bool = False, kif: dict | None = None,
                  profile: dict | None = None) -> list[dict]:
    """Return missing causes, or every note whose complete narrative needs renewed review.
    Review state is bound to counts, evidence, workflow and wording, never merely a KPI name.
    """
    reasons = facts.get("reasons") or {}
    periods = {p.get("name"): p for p in ((facts.get("periods") or {}).get("periods") or [])}
    periods.update({p['name']:p for p in (kif or {}).get('periods',[])})
    log = (facts.get("periods") or {}).get("log") or []
    out = []
    for per in results.get("periods") or []:
        name = per["period"]
        if periods.get(name,{}).get('upcoming'):continue
        for m in per.get("measures") or []:
            if m.get('availability')=='Not due yet':continue
            import note_policy
            if review and (reasons.get("_human_reviews") or {}).get(f"{name}|{m['name']}") == note_policy.basis(m):
                continue
            if not review and (m.get("status") != "Not met" or (reasons.get(name) or {}).get(m["name"])):
                continue
            p = periods.get(name) or {}
            entry = {
                "period": name, "kpi": m["name"], "status": m["status"], "value": m.get("value"),
                "target": m.get("threshold"), "the_note_already_says": " || ".join(x for x in m.get("note_parts") or [] if x),
                "counted": (m.get("counted_keys") or [])[:15], "review_items": m.get("review_items") or [],
                "review_item_details": {d: items for d in m.get("review_items") or []
                                        if (items := note_policy.items_for(m, d))},
                "context": {"period_story": p.get("notes") or "", "original_plan": p.get("plan_text") or "",
                            'agreed_project_dates':{k:(kif or {}).get('project',{}).get(k) for k in ('client_date','commit_date','dates_why')},
                            "dates": {k: p.get(k) or ({} if p.get('reporting_window') else ((facts.get("periods") or {}).get("project") or {})).get(k)
                                      for k in ("client_date", "commit_date", "handover_date", "client_check")},
                            "log": [e for e in log if e.get("period") in (name, None, "")
                                    and (not p.get('as_of') or not e.get('date') or e['date']<=p['as_of'])][:12]},
            }
            if review:
                tasks = [t for t in (kif or {}).get("tasks") or [] if t.get("period") == name]
                source=(kif or {}).get('project',{}).get('measurement_source') or kif or {}
                if m.get('key') in ('velocity','productivity_index','task_comprehension'):
                    output=next((x for x in per.get('measures',[]) if x.get('key')=='velocity'),m)
                    keys=set(output.get('counted_keys') or [])
                    # The output population is already selected by the engine. Supply
                    # its work context, never infer completion from a title or status.
                    entry['context']['completed_work']=[
                        {k:t.get(k) for k in ('key','title','story_points','hours_dev','hours_qa',
                                              'delivered','closed','delivery_evidence','understood','understood_why')}
                        for t in tasks if t.get('key') in keys]
                if m.get('key')=='productivity_index':
                    cap=p.get('capacity') or {}
                    entry['context']['project_effort']={k:cap.get(k) for k in
                        ('basis','hours_per_day','resource_days','billable_count','provisional','missing_entry_resources')}
                if m.get('key') in ('defect_rate','escaped_defect_rate','rejection_rate'):
                    counted=set(m.get('counted_keys') or [])
                    reports=source.get('defects',[]) if m.get('key')=='defect_rate' else (kif or {}).get('defects',[])
                    entry['context']['bug_report_outcomes']=[
                        {**{k:d.get(k) for k in ('key','title','kind','reported_on','phase','pre_existing',
                                                'rejected','rejection_reason','against_task','final_status')},
                         'counted':d.get('key') in counted,
                         'rejection_evidence':((d.get('basis') or {}).get('rejected') or {}).get('why')}
                        for d in reports if (d.get('key') in counted if m.get('key')=='defect_rate'
                                             else d.get('period')==name)]
                if m.get('measurement_method') and m.get('key')=='rework_rate':
                    source=(kif or {}).get('project',{}).get('measurement_source') or kif or {}
                    tasks=[t for t in source.get('tasks',[]) if t.get('key') in (m.get('counted_keys') or [])]
                entry["context"]["groups"] = [
                    {"key": t["key"], "title": t["title"], "members": [
                        x["key"] for x in tasks if x.get("effort_group") == t.get("_item")]}
                    for t in tasks if t.get("effort_only")]
                entry["context"]["item_evidence"] = [
                    {k: t.get(k) for k in ("key", "title", "rework_evidence", "rework_dates", "understood_why", "remarks")}
                    for t in tasks if t.get("type") != "Excluded" and
                    (t.get("understood") == "No" if m.get("key") == "task_comprehension" else
                     t.get("reopened") == "Yes" if m.get("key") == "rework_rate" else False)]
                entry["context"]["approved_additions"] = [
                    {k: x.get(k) for k in ("title", "approved_on", "dev_hours", "qa_hours")}
                    for x in (facts.get("estimates") or {}).get("items") or [] if x.get("period") == name]
                if m.get('key')=='cr_rate' and p.get('reporting_window'):
                    source=(kif or {}).get('project',{}).get('measurement_source') or kif or {}
                    entry['context']['approved_scope']=[
                        {k:t.get(k) for k in ('key','title','approved_on','story_points','hours_dev','hours_qa','effort_group','effort_only')}
                        for t in source.get('tasks',[]) if (t.get('type')=='CR' or t.get('effort_only')) and
                        p.get('start','')<=str(t.get('approved_on') or '')[:10]<=(p.get('as_of') or p.get('end',''))]
                if m.get("key") == "rejection_rate":
                    entry["context"]["rejected_reports"] = [
                        {"key": d.get("key"), "title": d.get("title"),
                         "why": d.get("rejection_reason") or ((d.get("basis") or {}).get("rejected") or {}).get("why")}
                        for d in (kif or {}).get("defects") or [] if d.get("period") == name and d.get("rejected") == "Yes"
                        and _counts_as_defect(d, profile)]
                entry["result_summary"] = m.get("summary_note")
                entry["computed_summary"] = m.get("generated_note")
                if (reasons.get("_addenda") or {}).get(f"{name}|{m['name']}"):
                    entry["evidence_addendum"] = reasons["_addenda"][f"{name}|{m['name']}"]
                # Which items a review question lists is supporting detail, not the note itself.
                signed = {k: v for k, v in entry.items() if k != "review_item_details"}
                signature = hashlib.sha256(json.dumps({"note": signed, "version": RUBRIC_VERSION,
                    "style": (profile or {}).get("custom_instructions"),
                    "workflow": (profile or {}).get("workflow")}, sort_keys=True, default=str).encode()).hexdigest()
                tag = f"{name}|{m['name']}"
                prior = (reasons.get(name) or {}).get(m["name"], "")
                saved = (reasons.get("_reviews") or {}).get(tag) or {}
                if saved.get("signature") == signature and saved.get("text") == prior:
                    continue
                entry.update(review_signature=signature, previous_reason=prior,
                             reason_author=(reasons.get("_authors") or {}).get(tag),
                             complete_note=(m.get('unmeasured_note') or m.get('note')) if m.get('value') is None else m.get('note'))
            out.append(entry)
    return out


def write_queue(queue: dict, project_dir: Path) -> Path:
    path = project_dir / "judge" / "queue.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(queue, indent=1, ensure_ascii=False), encoding="utf-8")
    return path


def apply_answers(answers_path: Path, board: dict, ledger, facts: dict, period_names: list[str],
                  by: str = "ai", who: str = "", context_change_reason: str = "") -> dict[str, Any]:
    """Fold answers into the ledger. Returns what was applied and what was refused, with the
    reason - a silently dropped answer is worse than a refused one."""
    try:
        doc = json.loads(answers_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return {"applied": [], "refused": [f"{answers_path} could not be read: {e}"], "reasons": 0, "unsure": []}
    items = {i["id"]: i for i in board.get("items") or []}
    queued=json.loads((answers_path.parent/'queue.json').read_text()) if (answers_path.parent/'queue.json').exists() else {}
    applied, refused, unsure = [], [], []
    for a in doc.get("answers") or []:
        iid, field, value = str(a.get("item_id") or ""), a.get("field"), a.get("value")
        if field == "reopen_count" and isinstance(value, int):
            value = str(value)
        it = items.get(iid)
        label = (it or {}).get("key") or ((it or {}).get("title") or iid)[:40]
        if not it:
            refused.append(f"{iid}: not a card on this board")
            continue
        if field not in FIELDS:
            refused.append(f"{label}: '{field}' is not a field that can be judged")
            continue
        if value is None:
            why = (a.get("why") or "").strip()
            if not why:
                refused.append(f"{label} · {field}: an undecidable answer also needs a 'why'")
                continue
            ledger.set(iid, "deferred:" + field, why, by, why, fingerprint=B.fingerprint(it),
                       key=it.get("key"), title=it.get("title"))
            unsure.append(f"{label} · {field}: {why}")
            continue
        allowed = period_names if field == "period" else FIELDS[field]
        if field in ('against_task','approved_on'):
            allowed=next((c.get('options',[]) for g in queued.get('items',[]) if g['item_id']==iid
                          for c in g['asks'] if c['field']==field),[])
        if value not in allowed:
            refused.append(f"{label} · {field}: '{value}' is not one of {', '.join(allowed)}")
            continue
        if not (a.get("why") or "").strip():
            refused.append(f"{label} · {field}: no 'why' given. A judgement that cannot say why is a guess")
            continue
        accepted=a.get('event_dates')
        if accepted is not None:
            ask=next((c for g in queued.get('items',[]) if g['item_id']==iid for c in g['asks'] if c['field']==field),{})
            if field!='reopened' or value!='Yes' or not isinstance(accepted,list) or not accepted or any(d not in (ask.get('candidate_event_dates') or []) for d in accepted):
                refused.append(f'{label}: accepted rework dates must come from the queued candidate events');continue
        ok = ledger.set(iid, field, value, by, a["why"].strip(), evidence=a.get("evidence"),
                        fingerprint=B.fingerprint(it), key=it.get("key"), title=it.get("title"), who=who)
        if ok:
            ledger.forget(iid, "deferred:" + field)
            if accepted is not None:
                ledger.set(iid,'reopen_dates',accepted,by,a['why'].strip(),fingerprint=B.fingerprint(it),evidence=a.get('evidence'),who=who)
        (applied if ok else refused).append(
            f"{label} · {field} = {value}" if ok else f"{label} · {field}: a person already answered this; left alone")

    reasons = facts.setdefault("reasons", {})
    authors = reasons.setdefault("_authors", {})
    n = 0
    queue_path = answers_path.parent / "queue.json"
    queued = json.loads(queue_path.read_text()) if queue_path.exists() else {}
    note_queue = {f"{x['period']}|{x['kpi']}": x for x in queued.get("notes") or []}
    for r in doc.get("reasons") or []:
        per, kpi, why = r.get("period"), r.get("kpi"), (r.get("why") or "").strip()
        if per in period_names and kpi and r.get("why") is None and r.get("missing"):
            reasons.setdefault("_questions", {})[f"{per}|{kpi}"] = str(r['missing']).strip()
            unsure.append(f"{per} · {kpi}: {r['missing']}")
            continue
        tag = f"{per}|{kpi}"
        reviewed = bool(r.get("review_signature") and
                        r["review_signature"] == (note_queue.get(tag) or {}).get("review_signature"))
        if r.get("review_signature") and not reviewed:
            refused.append(f"reason for {per} · {kpi}: review signature is stale; read the current queue")
            continue
        if per not in period_names or not kpi or (not why and not reviewed):
            refused.append(f"reason for {per} · {kpi}: needs a known period, a KPI name and some text")
            continue
        changing_human=authors.get(tag)=='human' and by!='human' and why!=(reasons.get(per) or {}).get(kpi)
        if changing_human and not context_change_reason:
            refused.append(f"reason for {per} · {kpi}: a person wrote this one; left alone")
            continue
        if changing_human:
            reasons.setdefault('_context_history',{}).setdefault(tag,[]).append({'text':(reasons.get(per) or {}).get(kpi),'author':'human','changed_by':by,'request':context_change_reason})
            authors[tag]=by
        reasons.setdefault(per, {})[kpi] = why
        reasons.setdefault("_questions", {}).pop(tag, None)
        if authors.get(tag) != "human" or by == "human":
            authors[tag] = by
        if reviewed:
            reasons.setdefault("_reviews", {})[tag] = {"signature": r["review_signature"], "text": why, "by": by}
            if r.get("addendum"):
                reasons.setdefault("_addenda", {})[tag] = str(r["addendum"]).strip()
                reasons.setdefault("_addendum_authors", {})[tag] = by
            if r.get("use_computed_summary"):
                # Keep the edited wording for audit, while explicitly refreshing only the
                # factual summary. Context written by a person stays protected above.
                old = reasons.setdefault("_summaries", {}).pop(tag, None)
                if old is not None:
                    reasons.setdefault("_summary_history", {}).setdefault(tag, []).append({
                        "text": old, "basis": reasons.setdefault("_summary_bases", {}).pop(tag, None),
                        "by": by, "review_signature": r["review_signature"],
                    })
        n += 1
    return {"applied": applied, "refused": refused, "reasons": n, "unsure": unsure}
