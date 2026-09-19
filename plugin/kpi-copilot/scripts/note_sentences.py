#!/usr/bin/env python3
"""
The notes, as sentences.

A KPI note is read by a manager, not parsed by one. The first notes were joined fragments -
"685 h across 53 items: 39 from the plan, 14 additional requests" - which is accurate and
reads like a machine wrote it. The hand-built tracker this tool replaces said the same thing
the way a person would: "The team completed 685 hours of work in this cycle, across 53
delivered items: 39 from the plan and 14 additional requests." This module writes that.

The engine still does all the counting. Each measure hands over the numbers it counted
(`say`), and this turns them into one to three sentences. Nothing here decides anything, so
the two styles can never disagree about a figure - only about how it is said. `fragments`
remains available as organization.note_style for anyone who prefers it.

The rules the sentences keep, because they are what a reader notices first:
  - a count and its noun agree ("1 item is", "3 items are"),
  - the basis is said in words ("each delivered by 09/11"), never as a tag,
  - an open period says what is still pending and until when,
  - an empty figure says which kind of empty it is.
"""

from __future__ import annotations

from typing import Any


def n(value: Any) -> str:
    if value is None:
        return ""
    v = float(value)
    return str(int(round(v))) if abs(v - round(v)) < 1e-9 else f"{v:.2f}".rstrip("0").rstrip(".")


def w(count: int, one: str, many: str | None = None) -> str:
    return one if count == 1 else (many or one + "s")


def listed(parts: list[str]) -> str:
    parts = [p for p in parts if p]
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def span(dates: list[str], own: str = "its own date") -> str:
    """'09/11', or 'its own date, between 07/23 and 07/29' when items carry different ones."""
    dates = sorted({d for d in dates if d})
    if not dates:
        return ""
    return dates[0] if len(dates) == 1 else f"{own}, between {dates[0]} and {dates[-1]}"


def until(dates: list[str]) -> str:
    dates = sorted({d for d in dates if d})
    if not dates:
        return "yet"
    return f"until {dates[0]}" if len(dates) == 1 else f"until {dates[0]} to {dates[-1]}"


def _items(count: int) -> str:
    return f"{count} {w(count, 'item')}"


SOLO = {"pre_existing": ("already in the product", "already in the product"),
        "observation": ("an observation", "observations"), "improvement": ("an improvement", "improvements"),
        "not_a_bug": ("closed as not a bug", "closed as not a bug"),
        "post_release": ("found after handover", "found after handover"),
        "other_report": ("a question rather than a defect", "questions rather than defects")}
MANY = {"pre_existing": ("that was already in the product", "that were already in the product"),
        "observation": ("observation", "observations"), "improvement": ("improvement", "improvements"),
        "not_a_bug": ("closed as not a bug", "closed as not a bug"),
        "post_release": ("found after handover", "found after handover"),
        "other_report": ("question or other report", "questions and other reports")}


def sentences(say: dict) -> list[str]:
    kpi = say.get("kpi")
    if say.get("empty"):
        text = str(say["empty"]).rstrip(".")
        return [text + "."]
    fn = {"velocity": _velocity, "task_comprehension": _comprehension, "client_expectation": _client,
          "delivery_commitment": _commitment, "defect_rate": _defects, "escaped_defect_rate": _escaped,
          "rejection_rate": _rejection, "rework_rate": _rework, "cr_rate": _cr}.get(kpi)
    return [s for s in (fn(say) if fn else []) if s]


def _velocity(s: dict) -> list[str]:
    if s.get("none"):
        return ["Nothing has been delivered in this cycle yet." if s.get("rows")
                else "Nothing has been logged against this cycle yet."]
    unit = "story points" if s["points"] else "hours of work"
    mix = [f"{s['plan']} from the plan" if s["plan"] else "",
           f"{s['cr']} additional {w(s['cr'], 'request')}" if s["cr"] else "",
           f"{s['scope']} in-scope {w(s['scope'], 'item')}" if s["scope"] else ""]
    many = sum(1 for m in mix if m) > 1
    out = [f"The team completed {n(s['total'])} {unit} in this cycle, across {s['n']} delivered "
           f"{w(s['n'], 'item')}{': ' + listed(mix) if many else ''}."]
    if not s["points"]:
        team = (f"{n(s['team'])} hours of shared work such as bug fixing, QA checks and regression" if s["team"] else "")
        if s["basis"] == "dev+qa" and (s["dev"] or s["qa"]):
            out.append(f"That is {n(s['dev'])} hours of development and {n(s['qa'])} hours of QA"
                       + (f", plus {team}" if team else "") + ".")
        elif team and s["dev"]:
            out.append(f"That is {n(s['dev'])} hours of development, plus {team}.")
        elif team:
            out.append(f"That is {team}.")
    if s["open"]:
        out.append(f"{s['open']} more {w(s['open'], 'item is', 'items are')} still in progress.")
    return out


def _pending(s: dict, noun: tuple[str, str] = ("item", "items")) -> str:
    p = s.get("pending") or 0
    if not p:
        return ""
    lead = "The other" if s.get("den") else ("The only" if p == 1 else "All")
    subject = f"{lead} {noun[0]} is" if p == 1 else f"{lead} {p} {noun[1]} are"
    return f"{subject} not due {until(s.get('pending_due') or [])}, so {w(p, 'it is', 'they are')} not counted yet."


def _comprehension(s: dict) -> list[str]:
    yes, den, pct = s["yes"], s["den"], n(s["value"])
    tail = f"without asking the client to explain the requirement ({pct}%)"
    if den == 1:
        first = (f"The team understood the one item in this cycle {tail}." if yes else
                 f"The team had to ask the client to explain the one item in this cycle ({pct}%).")
    elif yes == den:
        first = f"The team understood all {den} items {tail}."
    elif yes == 0:
        first = f"The team had to ask the client to explain the requirement on all {den} items ({pct}%)."
    else:
        first = f"The team understood {yes} of the {den} items {tail}."
    b = s.get("blank") or 0
    blank = (f"{b} more {w(b, 'item has', 'items have')} no history of {w(b, 'its', 'their')} own, so "
             f"{w(b, 'it is', 'they are')} not counted.") if b else ""
    return [first, blank]


def _client(s: dict) -> list[str]:
    yes, den, pct = s["yes"], s["den"], n(s["value"])
    by_delivery = s.get("check") == "Delivery"
    when = span(s.get("dates") or [])
    basis = ("each delivered by " if by_delivery else "handed over by ") + when if when else \
        ("counted on each item's delivery date" if by_delivery else "counted on the handover date")
    if yes == den:
        first = f"Everything the client expected arrived on time: {_items(den)}, {basis} ({pct}%)."
    elif yes == 0:
        first = (f"Nothing arrived by the date the client expected: 0 of {_items(den)}"
                 + (f", due {when}" if when else "") + f" ({pct}%).")
    else:
        first = f"{yes} of the {_items(den)} the client expected arrived on time, {basis} ({pct}%)."
    b = s.get("blank") or 0
    blank = (f"{b} more {w(b, 'item carries', 'items carry')} no date from the client, so "
             f"{w(b, 'it is', 'they are')} left out.") if b else ""
    handed = (f"The cycle was handed over on {s['handover']}." if s.get("handover")
              else "The cycle has not been handed over to the client yet.")
    return [first, _pending(s), blank, handed]


def _commitment(s: dict) -> list[str]:
    if s.get("none_committed"):
        return [f"No team commitment was recorded against any of the {_items(s['rows'])} in this cycle, so there "
                f"is nothing to measure reliability against."]
    yes, den, pct = s["yes"], s["den"], n(s["value"])
    when = span(s.get("dates") or [], "their own dates")
    by = (f" by {when}" if when else "") + f", {s['phrase']}"
    if den == 1:
        first = (f"The team met the one commitment it made, on time{by} ({pct}%)." if yes else
                 f"The team missed the one commitment it made; it was due{by.replace(' by', '', 1)} ({pct}%).")
    elif yes == den:
        first = f"The team met every commitment it made: {_items(den)} on time{by} ({pct}%)."
    elif yes == 0:
        first = f"The team met none of the {den} commitments it made; they were due{by.replace(' by', '', 1)} ({pct}%)."
    else:
        first = f"The team met {yes} of the {den} commitments it made on time{by} ({pct}%)."
    u = s.get("uncommitted") or 0
    left = (f"The team made no commitment on {u} other {w(u, 'item')}, so {w(u, 'it is', 'they are')} left out."
            if u else "")
    return [first, _pending(s, ("commitment", "commitments")), left]


def _defects(s: dict) -> list[str]:
    if s.get("none"):
        return ["Nothing has been delivered in this cycle yet, so there is nothing to measure." if s.get("rows")
                else "Nothing has been logged against this cycle yet."]
    c, den = s["counted"], s["den"]
    first = (f"No bugs were found in the {_items(den)} delivered in this cycle." if not c else
             f"{c} {w(c, 'bug was', 'bugs were')} found in the {_items(den)} delivered in this cycle ({n(s['value'])}%).")
    left = [(r, k) for r, k in (s.get("left") or []) if k]
    other = sum(k for _, k in left)
    if not left:
        return [first]
    if len(left) == 1:
        r, k = left[0]
        one, many = SOLO.get(r, (r, r))
        return [first, f"The other report was {one}." if k == 1 else f"The other {k} reports were all {many}."]
    names = [f"{k} {(MANY.get(r) or (r, r))[0 if k == 1 else 1]}" for r, k in left]
    return [first, f"Another {other} {w(other, 'report was', 'reports were')} not counted: {listed(names)}."]


def _escaped(s: dict) -> list[str]:
    den = s.get("den") or 0
    if s.get("no_handover"):
        return [f"The cycle has not been handed over yet, so none of the {den} valid {w(den, 'issue')} could have "
                f"come from the client." if den else
                "The cycle has not been handed over to the client yet, so there is nothing to measure."]
    if s.get("no_issues"):
        return ["No valid issues have been reported in this cycle yet."]
    e = s["escaped"]
    first = (f"The client found none of the {den} valid {w(den, 'issue')} after handover." if not e else
             f"The client found {e} of the {den} valid {w(den, 'issue')} after handover ({n(s['value'])}%).")
    r = s.get("rejected") or 0
    rej = (f"{r} rejected {w(r, 'report is', 'reports are')} in neither half, because "
           f"{w(r, 'it was', 'they were')} never a defect.") if r else ""
    return [first, f"The cycle was handed over on {s['handover']}.", rej]


def _rejection(s: dict) -> list[str]:
    if s.get("none_reported"):
        return ["No issues have been reported in this cycle yet."]
    r, den = s["rejected"], s["den"]
    if not r:
        return [f"None of the {den} {w(den, 'report was', 'reports were')} rejected."]
    why = [k for k in (s.get("why") or {})]
    second = (f"{w(r, 'It was', 'They were')} closed as {listed(why)}." if why else
              f"{w(r, 'It was', 'They were')} closed as invalid, working as designed, duplicate or not reproducible.")
    return [f"{r} of the {den} {w(den, 'report')} turned out not to be {w(r, 'a bug', 'bugs')} ({n(s['value'])}%).", second]


def _rework(s: dict) -> list[str]:
    if s.get("nothing_completed"):
        return ["Nothing has been completed in this cycle yet."]
    if s.get("unjudged_all"):
        k = s["unjudged_all"]
        return [f"None of the {k} completed {w(k, 'task')} records whether it was reopened after closing, so there "
                f"is nothing to measure."]
    r, den = s["reopened"], s["den"]
    first = (f"None of the {den} completed {w(den, 'task')} had to be reopened after being closed." if not r else
             f"{r} of the {den} completed {w(den, 'task')} had to be reopened after being closed ({n(s['value'])}%).")
    q = s.get("near") or 0
    near = (f"{q} {w(q, 'task')} failed QA while still being tested for the first time. That is normal testing "
            f"rather than rework, so {w(q, 'it is', 'they are')} not counted here.") if q else ""
    u = s.get("unjudged") or 0
    gap = (f"{u} completed {w(u, 'task was', 'tasks were')} left out because the history needed to judge "
           f"{w(u, 'it', 'them')} was not available.") if u else ""
    return [first, near, gap]


def _cr(s: dict) -> list[str]:
    if s.get("no_scope"):
        return ["There is no planned scope to measure additions against."]
    c, den = s["crs"], s["den"]
    first = (f"The client added no extra work to this cycle. The plan holds {den} planned {w(den, 'item')} (0%)."
             if not c else
             f"The client added {c} {w(c, 'request')} on top of the {den} planned {w(den, 'item')} ({n(s['value'])}%).")
    basis = ("This cycle is made up only of additional requests, so they are measured against the planned items "
             "of the whole project." if s.get("only_crs") else
             "They are measured against the planned items of the whole project." if s.get("project") else "")
    return [first, basis]
