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
import re


def terminology(text: str, profile: dict) -> str:
    """Apply the client's public vocabulary without changing internal KPI IDs or types."""
    label = (profile.get("conventions") or {}).get("additional_request_label")
    if not label:
        return text
    return re.sub(r"\b(?:(?:additional|change)\s+)?requests?\b|\bCRs?\b",
                  lambda m: label + ("s" if m.group().lower().endswith("s") else ""), text, flags=re.I)


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
        return ["No completed delivery is recorded for this cycle yet." if s.get("rows")
                else "Nothing has been logged against this cycle yet."]
    unit = "story points" if s["points"] else "estimated hours"
    mix = [f"{s['plan']} from the plan" if s["plan"] else "",
           f"{s['cr']} additional {w(s['cr'], 'request')}" if s["cr"] else "",
           f"{s['scope']} in-scope {w(s['scope'], 'item')}" if s["scope"] else ""]
    many = sum(1 for m in mix if m) > 1
    out = [f"Delivered work represents {n(s['total'])} {unit} in this cycle, across {s['n']} delivered "
           f"{w(s['n'], 'item')}{': ' + listed(mix) if many else ''}."]
    if not s["points"]:
        team = (f"{n(s['team'])} hours of shared work such as bug fixing, QA checks and regression" if s["team"] else "")
        if s["basis"] == "dev+qa" and (s["dev"] or s["qa"]):
            out.append(f"That is {n(s['dev'])} {w(s['dev'], 'hour')} of development and {n(s['qa'])} {w(s['qa'], 'hour')} of QA"
                       + (f", plus {team}" if team else "") + ".")
        elif team and s["dev"]:
            out.append(f"That is {n(s['dev'])} hours of development, plus {team}.")
        elif team:
            out.append(f"That is {team}.")
    if s["open"]:
        out.append(f"{s['open']} more {w(s['open'], 'item is', 'items are')} still in progress.")
    if s.get("grouped"):
        out.append("Tickets inside a grouped feature are counted separately. Each group's estimate is included once.")
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
    if b:
        first = first.replace("one item in this cycle", "one assessed item").replace(
            f"{den} items", f"{den} assessed items")
    blank = (f"{b} other {w(b, 'item could', 'items could')} not be assessed because individual discussion "
             "history was unavailable.") if b else ""
    return [first, blank]


def _client(s: dict) -> list[str]:
    yes, den, pct = s["yes"], s["den"], n(s["value"])
    by_delivery = s.get("check") == "Delivery"
    when = span(s.get("dates") or [])
    basis = ((s.get("delivery_label") or "each delivered") + " by " if by_delivery else "handed over by ") + when if when else \
        ("counted on each item's delivery date" if by_delivery else "counted on the handover date")
    if yes == den:
        first = f"All {_items(den)} met the client's agreed deadline, {basis} ({pct}%)."
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
        first = (f"The one assessed item met its recorded commitment date{by} ({pct}%)." if yes else
                 f"The one assessed item missed its recorded commitment date{by.replace(' by', '', 1)} ({pct}%).")
    elif yes == den:
        first = f"All {den} assessed items met their recorded commitment dates{by} ({pct}%)."
    elif yes == 0:
        first = f"None of the {den} assessed items met their recorded commitment dates{by} ({pct}%)."
    else:
        first = f"{yes} of the {den} assessed items met their recorded commitment dates{by} ({pct}%)."
    u = s.get("uncommitted") or 0
    left = (f"No commitment date is recorded for {u} other {w(u, 'item')}, so {w(u, 'it is', 'they are')} left out."
            if u else "")
    return [first, _pending(s, ("commitment", "commitments")), left]


def _defects(s: dict) -> list[str]:
    if s.get("none"):
        return ["No completed delivery is recorded for this cycle yet, so this rate cannot be measured." if s.get("rows")
                else "Nothing has been logged against this cycle yet."]
    c, den = s["counted"], s["den"]
    first = (f"No qualifying defects were reported against the {_items(den)} delivered in this cycle." if not c else
             f"{c} {w(c, 'defect was', 'defects were')} reported against {den} delivered {w(den, 'ticket')}. "
             f"That is {n(s['value'])} defects per 100 delivered tickets ({n(s['value'])}%). "
             "One ticket can have several defects, so this is not the percentage of tickets with a problem.")
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
        return ["A client handover has not been recorded, so defects found after handover cannot be measured yet."]
    if s.get("no_issues"):
        return ["No valid issues have been reported in this cycle yet."]
    e = s["escaped"]
    first = (f"No issues found by the client after handover are recorded among the {den} valid {w(den, 'issue')}." if not e else
             f"The client found {e} of the {den} valid {w(den, 'issue')} after handover ({n(s['value'])}%).")
    r = s.get("rejected") or 0
    rej = (f"{r} rejected {w(r, 'report is', 'reports are')} excluded from both counts because "
           f"{w(r, 'it was', 'they were')} not accepted as a defect.") if r else ""
    return [first, f"The cycle was handed over on {s['handover']}.", rej]


def _rejection(s: dict) -> list[str]:
    if s.get("none_reported"):
        return ["No issues have been reported in this cycle yet."]
    r, den = s["rejected"], s["den"]
    if not r:
        return [f"None of the {den} {w(den, 'report was', 'reports were')} rejected."]
    why = [k for k in (s.get("why") or {})]
    second = (f"{w(r, 'It was', 'They were')} closed as {listed(why)}." if why else
              "Rejected reports are excluded from defect counts.")
    return [f"{r} of the {den} {w(den, 'report')} turned out not to be {w(r, 'a bug', 'bugs')} ({n(s['value'])}%).", second]


def _rework(s: dict) -> list[str]:
    if s.get("nothing_completed"):
        return ["No completed work is recorded for this cycle yet."]
    if s.get("unjudged_all"):
        k = s["unjudged_all"]
        return [f"None of the {k} completed {w(k, 'task')} records whether it was reopened after closing, so there "
                f"is nothing to measure."]
    r, den = s["reopened"], s["den"]
    group = f"{den} assessed completed {w(den, 'task')}" if s.get("unjudged") else f"{den} completed {w(den, 'task')}"
    first = (("The one assessed completed task was not reopened after closing." if den == 1 else
              f"None of the {group} had to be reopened after being closed.") if not r else
             f"{r} of the {group} had to be reopened after being closed ({n(s['value'])}%).")
    q = s.get("near") or 0
    near = (f"{q} {w(q, 'task')} failed QA while still being tested for the first time. That is normal testing "
            f"rather than rework, so {w(q, 'it is', 'they are')} not counted here.") if q else ""
    u = s.get("unjudged") or 0
    gap = (f"{u} completed {w(u, 'task was', 'tasks were')} left out because the history needed to judge "
           f"{w(u, 'it', 'them')} was not available.") if u else ""
    return [first, s.get("close_explanation") or "", near, gap,
            "Each affected ticket counts once, even if it returned for changes several times."]


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
