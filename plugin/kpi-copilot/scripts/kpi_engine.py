#!/usr/bin/env python3
"""
KPI Copilot engine.

Takes a KIF document (whatever tracker it came from), a profile, and the KPI registry
read from PMS, and produces per-period KPI values, a status against each threshold, and
the note that goes to PMS.

Nothing in here knows what Asana or Jira is. That is the whole point: the counting rules
live in one place so two project leads on two different trackers get the same number for
the same situation.

Counting is fixed; targets are not. PMS sets thresholds per project, so the bar can and
should differ between a greenfield build and an integration over a legacy surface. The
engine reads whatever PMS holds for this project, falls back to the PMS default, and records
on every measure which of the two it used - so a reader comparing two projects can see that
the bar differed, and that PMS is what made it differ.

Three things this deliberately refuses to do:

  1. Guess. If the adapter could not observe something, the KPI comes back "Not measured"
     with the reason attached. A wrong number is worse than a missing one, because a wrong
     one gets defended in a meeting.
  2. Round away the denominator. Every value carries its numerator and denominator so a
     reader can check the arithmetic, and the note prints them.
  3. Write anywhere. This module computes. Pushing is somebody else's job.

Usage:
    python3 kpi_engine.py --kif run.kif.json --profile profile.yaml \
        [--reasons reasons.yaml] [--registry kpi_registry.json] \
        [--out results.json] [--markdown results.md]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import note_sentences  # noqa: E402

# One resolver for every script, so they cannot disagree about what a project's settings are.
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
from profile_lib import load as load_profile, resolve as resolve_profile  # noqa: E402


# --------------------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------------------


def _load_any(path: Path) -> Any:
    """Read JSON, or YAML when PyYAML is around. Profiles are nicer as YAML but we do not
    want a hard dependency for people who only ever touch JSON."""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except ImportError:
            raise SystemExit(
                f"{path.name} is YAML but PyYAML is not installed.\n"
                f"Either 'pip install pyyaml' or convert the file to JSON."
            )
        return yaml.safe_load(text)
    return json.loads(text)


def _d(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _md(value: str | None) -> str:
    """Dates in notes are mm/dd, the way the team says them out loud."""
    d = _d(value)
    return d.strftime("%m/%d") if d else ""


def _pct(num: float, den: float) -> float | None:
    if not den:
        return None
    return round(num * 100.0 / den, 2)


def _n(value: float | None) -> str:
    """Numbers as a person would write them: 685 not 685.0, 52.83 not 52.8300000001."""
    if value is None:
        return ""
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return singular if count == 1 else (plural or singular + "s")


def _items_word(count: int) -> str:
    return f"{count} {_plural(count, 'item')}"


# How each "reported but not counted" bucket reads, singular and plural. Kept as data
# because "1 observations" is exactly the kind of thing a reader notices and no hash check
# ever catches.
DROP_WORDS: dict[str, tuple[str, str]] = {
    "pre_existing": ("that was already in the product", "that were already in the product"),
    "observation": ("observation", "observations"),
    "improvement": ("improvement", "improvements"),
    "not_a_bug": ("closed as not a bug", "closed as not a bug"),
    "post_release": ("found after handover", "found after handover"),
    "other_report": ("question or other report", "questions and other reports"),
}


def _drop_phrase(reason: str, count: int) -> str:
    single, many = DROP_WORDS.get(reason, (reason, reason))
    return f"{count} {single if count == 1 else many}"


def _strip_links(text: str) -> str:
    """PMS shows notes as plain text and links only add noise there, so '[words](url)'
    collapses to 'words' and a bare URL is dropped. Links stay in the workbook, on the
    words they support."""
    text = re.sub(r"\[([^\]]+)\]\((?:[^)]+)\)", r"\1", text or "")
    text = re.sub(r"https?://\S+", "", text)
    return re.sub(r"\s{2,}", " ", text).strip(" ,;")


# --------------------------------------------------------------------------------------
# results
# --------------------------------------------------------------------------------------


@dataclass
class Measure:
    key: str
    name: str
    pms_id: int | None
    value: float | None
    unit: str
    threshold: float | None
    threshold_source: str  # which PMS setting this target came from
    direction: str
    status: str  # Met | Not met | Not measured
    numerator: float | None = None
    denominator: float | None = None
    counted_keys: list[str] = field(default_factory=list)
    note: str = ""
    note_parts: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    pms_value: float | None = None  # after clamping to the PMS range
    clamped: bool = False
    # A person can set any value or note by hand. When they do, both are kept: what the data
    # said and what the person said, so nothing disagrees quietly.
    overridden: bool = False
    override_reason: str = ""
    override_by: str = ""
    computed_value: float | None = None
    computed_note: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class PeriodResult:
    period: str
    measures: list[Measure]
    facts: dict
    description: str = ""

    def as_dict(self) -> dict:
        return {
            "period": self.period,
            "description": self.description,
            "facts": self.facts,
            "measures": [m.as_dict() for m in self.measures],
        }


# --------------------------------------------------------------------------------------
# engine
# --------------------------------------------------------------------------------------


class Engine:
    def __init__(self, kif: dict, profile: dict, registry: dict, reasons: dict | None = None,
                 manual: dict | None = None):
        self.kif = kif
        self.profile = profile or {}
        self.registry = registry
        self.reasons = reasons or {}
        self.manual = manual or {}
        self.manual_report: list[dict] = []
        self.reg_by_key = {k["key"]: k for k in registry.get("kpis", [])}
        self.capabilities = set((kif.get("generated") or {}).get("capabilities") or [])
        # How the notes are worded. It changes no figure.
        self.note_style = str((self.profile.get("organization") or {}).get("note_style") or "sentences").lower()
        self.policy = {
            "count_observations": False,
            "count_improvements": False,
            "count_pre_existing": False,
            "count_post_release": True,
            "count_rejected": False,
            **(self.profile.get("policy") or {}),
        }
        self.sources = self.profile.get("sources") or {}
        self.thresholds = self._resolve_thresholds()
        self.overrides_report: list[dict] = []
        self._apply_overrides()

    # -- thresholds --------------------------------------------------------------------

    def _resolve_thresholds(self) -> dict[str, tuple[float | None, str, str]]:
        """PMS sets thresholds per project, so two projects can legitimately have different
        targets for the same KPI - an integration on a legacy surface is not held to the same
        defect rate as a greenfield build.

        So the target for a KPI is whatever PMS holds *for this project*, falling back to the
        PMS default when the project has no setting of its own. Each one records where it came
        from, because a reader comparing two projects needs to see that the bar differed and
        that it differed by PMS's decision, not ours.

        Returns {kpi_key: (threshold, direction, source)}.
        """
        pid = (self.kif.get("project") or {}).get("pms_project_id")
        per_project = ((self.registry.get("projects") or {}).get(str(pid)) or {}) if pid else {}
        fallback = self.registry.get("source") == "bundled-fallback"

        out: dict[str, tuple[float | None, str, str]] = {}
        for k in self.registry.get("kpis", []):
            key = k["key"]
            threshold, direction = k.get("threshold"), k.get("direction", "higher-is-better")
            if fallback:
                source = "bundled fallback, not read from PMS"
            else:
                source = "PMS default for all projects"
            hit = per_project.get(key)
            if hit and hit.get("threshold") is not None:
                threshold = hit["threshold"]
                direction = hit.get("direction", direction)
                source = f"set in PMS for project {pid}"
            local = (self.profile.get("targets") or {}).get(key)
            if local:
                threshold = local["value"]
                source = f"Local review target (PMS unchanged): {local['why']}"
            out[key] = (threshold, direction, source)
        return out

    # -- custom instructions -----------------------------------------------------------

    # Rules this module can act on. Anything else either belongs to the adapter (it shapes
    # the extract, not the arithmetic) or is owned by PMS.
    #
    # PMS-owned is not the same as immutable. Thresholds are configurable in PMS and vary by
    # project and team, which is right - an integration on a legacy surface should not be held
    # to a greenfield defect rate. What cannot happen is a threshold living in a local config
    # file, because then the workbook says "Met" and PMS says "Not met" for the same number,
    # and the person who has to explain that gap is the lead. Change it in PMS; the next run
    # reads it. What genuinely is fixed is the *counting*: what delivered, defect and rework
    # mean, since PMS does not define those and they are the reason two projects' numbers can
    # be compared at all.
    ENGINE_RULES = {"cr_denominator", "exclude_key", "include_key", "defect_phase", "velocity_team_hours"}
    ADAPTER_RULES = {"delivered_signal", "client_date_source", "commit_date_source", "hours_source", "period_of_key"}

    @staticmethod
    def _split_value(value: str) -> tuple[str, str]:
        """'TKT-123 = Post-release' -> ('TKT-123', 'Post-release'). No '=' means the whole
        string is the value and there is no subject."""
        if "=" in value:
            left, right = value.split("=", 1)
            return left.strip(), right.strip()
        return "", value.strip()

    def _apply_overrides(self) -> None:
        ci = self.profile.get("custom_instructions") or {}
        self.cr_denominator = "period"
        for ov in ci.get("rule_overrides") or []:
            rule, value, why = ov.get("rule", ""), str(ov.get("value", "")), ov.get("why", "")
            entry = {"rule": rule, "value": value, "why": why,
                     "approved_by": ov.get("approved_by"), "expires": ov.get("expires"), "status": ""}
            if not why:
                entry["status"] = "rejected: every override needs a reason, because it is printed in the summary"
                self.overrides_report.append(entry)
                continue
            if rule in self.ADAPTER_RULES:
                entry["status"] = "handled by the adapter before this point"
                self.overrides_report.append(entry)
                continue
            if rule not in self.ENGINE_RULES:
                if rule.startswith("threshold"):
                    entry["status"] = (
                        "not supported here - thresholds are set per project in PMS. Change it on this "
                        "project in PMS and the next run picks it up; a threshold kept in this file would "
                        "make the workbook and PMS disagree about the same number"
                    )
                else:
                    entry["status"] = (
                        "not supported - KPI ids and the definition of each ratio come from PMS and the "
                        "shared counting rules"
                    )
                self.overrides_report.append(entry)
                continue

            subject, val = self._split_value(value)
            hit = False
            if rule == "exclude_key":
                for t in self.kif["tasks"]:
                    if t.get("key") == (subject or val):
                        t["type"], t["exclude_reason"], hit = "Excluded", why, True
            elif rule == "include_key":
                for t in self.kif["tasks"]:
                    if t.get("key") == (subject or val):
                        t["type"] = val if val in ("Task", "CR", "Scope") else "Task"
                        t.pop("exclude_reason", None)
                        hit = True
            elif rule == "defect_phase":
                for d in self.kif["defects"]:
                    if d.get("key") == subject:
                        d["phase"], hit = val, True
            elif rule == "velocity_team_hours":
                for p in self.kif["periods"]:
                    if p.get("name") == subject:
                        try:
                            p["team_hours"], hit = float(val), True
                        except ValueError:
                            entry["status"] = f"rejected: '{val}' is not a number"
            elif rule == "cr_denominator":
                if val in ("period", "project"):
                    self.cr_denominator, hit = val, True
                else:
                    entry["status"] = "rejected: expected 'period' or 'project'"

            if not entry["status"]:
                entry["status"] = "applied" if hit else "applied to nothing - check the key or period name"
            self.overrides_report.append(entry)

    # -- selection ---------------------------------------------------------------------

    def tasks_in(self, period: str) -> list[dict]:
        return [t for t in self.kif["tasks"] if t.get("period") == period]

    def deliverables_in(self, period: str) -> list[dict]:
        """Everything that is actually ours to deliver: plan items, approved additions and
        in-scope work. Excluded rows stay in the KIF so the workbook can show what was left
        out, but they never reach a denominator."""
        return [t for t in self.tasks_in(period) if t.get("type") in ("Task", "CR", "Scope")]

    def delivered_in(self, period: str) -> list[dict]:
        return [t for t in self.deliverables_in(period) if t.get("delivered")]

    def defects_in(self, period: str) -> list[dict]:
        return [d for d in self.kif["defects"] if d.get("period") == period]

    def counted_defects(self, period: str) -> tuple[list[dict], list[tuple[str, list[dict]]]]:
        """Returns (counted, [(why it was left out, rows), ...]). The 'left out' list is what
        makes the third part of the note, and it is the part reviewers actually read."""
        counted, buckets = [], {}

        def drop(reason: str, row: dict) -> None:
            buckets.setdefault(reason, []).append(row)

        for d in self.defects_in(period):
            kind = d.get("kind") or "Bug"
            if d.get("rejected") == "Yes":
                drop("not_a_bug", d)
                continue
            if kind == "Observation" and not self.policy["count_observations"]:
                drop("observation", d)
                continue
            if kind == "Improvement" and not self.policy["count_improvements"]:
                drop("improvement", d)
                continue
            if kind in ("Query", "Other"):
                drop("other_report", d)
                continue
            if d.get("pre_existing") == "Yes" and not self.policy["count_pre_existing"]:
                drop("pre_existing", d)
                continue
            if d.get("phase") == "Post-release" and not self.policy["count_post_release"]:
                drop("post_release", d)
                continue
            counted.append(d)

        order = ["pre_existing", "observation", "improvement", "not_a_bug", "post_release", "other_report"]
        left_out = [(r, buckets[r]) for r in order if r in buckets]
        return counted, left_out

    # -- the nine ----------------------------------------------------------------------

    def _measure(self, key: str, **kw) -> Measure:
        r = self.reg_by_key.get(key, {})
        lo, hi = (r.get("range") or [0, 100])
        threshold, direction, source = self.thresholds.get(
            key, (r.get("threshold"), r.get("direction", "higher-is-better"), "unknown")
        )
        m = Measure(
            key=key,
            name=r.get("name", key),
            pms_id=r.get("pms_id"),
            unit=kw.pop("unit", r.get("unit", "%")),
            threshold=threshold,
            threshold_source=source,
            direction=direction,
            value=kw.pop("value", None),
            status="Not measured",
            **kw,
        )
        # status
        if m.value is None:
            m.status = "Not measured"
        elif m.threshold is None:
            m.status = "Measured"
        elif m.direction == "higher-is-better":
            m.status = "Met" if m.value >= m.threshold else "Not met"
        else:
            m.status = "Met" if m.value <= m.threshold else "Not met"
        # PMS clamps everything except Velocity to 0-100. Send the ceiling, keep the truth
        # in the note - a silently truncated number is how a report loses its meaning.
        if m.value is not None:
            m.pms_value = max(lo, min(hi, m.value))
            m.clamped = m.pms_value != m.value
        return m

    def velocity(self, period: dict) -> Measure:
        name = period["name"]
        unit = (self.kif["project"].get("velocity_unit") or "Estimated Hours")
        by_points = unit == "Story Points"
        delivered = self.delivered_in(name)
        basis = (self.sources.get("hours_basis") or "dev")

        missing = [t for t in delivered if
                   (t.get("story_points") is None if by_points else
                    t.get("hours_dev") is None or
                    (basis == "dev+qa" and t.get("closed") and t.get("hours_qa") is None))]
        if missing:
            why = (f"Velocity is not measured in {'story points' if by_points else 'hours'}: "
                   f"{len(missing)} of {len(delivered)} delivered items lack the required estimate. "
                   "Fill the missing estimates; blank does not mean zero.")
            m = self._measure("velocity", value=None, unit=unit, numerator=None, denominator=None, gaps=[why])
            m.note_parts = [self._heading("velocity", period), why, ""]
            m._say = {"kpi": "velocity", "empty": why}
            return m

        def effort(t: dict) -> float:
            if by_points:
                return float(t.get("story_points") or 0)
            dev = float(t.get("hours_dev") or 0)
            qa = float(t.get("hours_qa") or 0) if basis == "dev+qa" and t.get("closed") else 0.0
            return dev + qa

        item_total = sum(effort(t) for t in delivered)
        team_hours = float(period.get("team_hours") or 0) if not by_points else 0.0
        total = item_total + team_hours

        gaps: list[str] = []
        if not by_points and not any(t.get("hours_dev") for t in delivered) and delivered:
            gaps.append(
                "No effort figures were available for the delivered items, so Velocity counts only team-level effort."
            )

        if not delivered:
            numbers = self._nothing_yet(period, name)
            m = self._measure("velocity", value=None, unit=unit, numerator=0, denominator=0, gaps=gaps)
            m.note_parts = [self._heading("velocity", period), numbers, ""]
            m._say = {"kpi": "velocity", "none": True, "rows": len(self.deliverables_in(name))}
            return m

        n_plan = sum(1 for t in delivered if t.get("type") == "Task")
        n_cr = sum(1 for t in delivered if t.get("type") == "CR")
        n_scope = sum(1 for t in delivered if t.get("type") == "Scope")
        mix = []
        if n_plan:
            mix.append(f"{n_plan} from the plan")
        if n_cr:
            mix.append(f"{n_cr} additional {_plural(n_cr, 'request')}")
        if n_scope:
            mix.append(f"{n_scope} in-scope {_plural(n_scope, 'item')}")

        unit_word = "story points" if by_points else "h"
        head = f"{_n(total)} {unit_word} across {_items_word(len(delivered))}"
        numbers = head + (": " + ", ".join(mix) if mix and len(mix) > 1 else "")

        detail = []
        if not by_points and basis == "dev+qa":
            dev = sum(float(t.get("hours_dev") or 0) for t in delivered)
            qa = sum(float(t.get("hours_qa") or 0) for t in delivered if t.get("closed"))
            if dev or qa:
                detail.append(f"{_n(dev)} h of development and {_n(qa)} h of QA")
        if team_hours:
            detail.append(
                f"plus {_n(team_hours)} h of shared work such as bug fixing, QA checks and regression"
            )
        not_yet = [t for t in self.deliverables_in(name) if not t.get("delivered")]
        if not_yet:
            detail.append(f"{len(not_yet)} more {_plural(len(not_yet), 'item is', 'items are')} still in progress")

        m = self._measure(
            "velocity",
            value=round(total, 2),
            unit=unit,
            numerator=round(total, 2),
            denominator=None,
            counted_keys=[t["key"] for t in delivered],
            gaps=gaps,
        )
        m.note_parts = [self._heading("velocity", period), numbers, ", ".join(detail)]
        m._say = {"kpi": "velocity", "total": total, "points": by_points, "n": len(delivered), "plan": n_plan,
                  "cr": n_cr, "scope": n_scope, "basis": basis, "team": team_hours, "open": len(not_yet),
                  "dev": sum(float(t.get("hours_dev") or 0) for t in delivered),
                  "qa": sum(float(t.get("hours_qa") or 0) for t in delivered if t.get("closed"))}
        return m

    def _ratio_measure(
        self,
        key: str,
        period: dict,
        rows: list[dict],
        field_name: str,
        yes_word: str | tuple[str, str],
        pending_note: str | None = None,
    ) -> Measure:
        """Task Comprehension, Client Expectation and Delivery Commitment are the same
        shape: Yes over Yes+No, with Pending held out of the denominator and named."""
        name = period["name"]
        yes = [t for t in rows if t.get(field_name) == "Yes"]
        no = [t for t in rows if t.get(field_name) == "No"]
        pending = [t for t in rows if t.get(field_name) == "Pending"]
        blank = [t for t in rows if t.get(field_name) in (None, "")]
        den = len(yes) + len(no)

        gaps: list[str] = []
        need = self.reg_by_key.get(key, {}).get("requires") or []
        missing = [c for c in need if c not in self.capabilities and self.capabilities]
        if missing:
            gaps.append(
                f"The tracker adapter could not read {', '.join(missing).replace('_', ' ')}, "
                f"so this is based only on what was filled in by hand."
            )

        if den == 0:
            m = self._measure(key, value=None, numerator=0, denominator=0, gaps=gaps)
            m.note_parts = [
                self._heading(key, period),
                self._why_empty(period, name, pending=pending, blank=blank),
                "",
            ]
            m._say = {"kpi": key, "empty": m.note_parts[1]}
            return m

        value = _pct(len(yes), den)
        # The tail agrees with the denominator: "0 of 1 requirement was", "5 of 7 requirements were".
        tail = (yes_word[0] if den == 1 else yes_word[1]) if isinstance(yes_word, tuple) else yes_word
        numbers = f"{len(yes)} of {den} {tail}"
        if value is not None:
            numbers += f" ({_n(value)}%)"

        left_out = []
        if pending:
            due = sorted({_md(t.get("client_date") or t.get("commit_date")) for t in pending if (t.get("client_date") or t.get("commit_date"))})
            due = [d for d in due if d]
            when = f" until {due[0]} to {due[-1]}" if len(due) > 1 else (f" until {due[0]}" if due else "")
            one = len(pending) == 1
            left_out.append(
                f"{len(pending)} more {'item is' if one else 'items are'} not due{when}, "
                f"so {'it is' if one else 'they are'} not in this figure"
            )
        if blank:
            one = len(blank) == 1
            left_out.append(
                f"{len(blank)} {'item with no history of its own is' if one else 'items with no history of their own are'} "
                f"left out of the count"
            )
        if pending_note:
            left_out.append(pending_note)

        m = self._measure(
            key,
            value=value,
            numerator=len(yes),
            denominator=den,
            counted_keys=[t["key"] for t in yes + no],
            gaps=gaps,
        )
        m.note_parts = [self._heading(key, period), numbers, "; ".join(left_out)]
        date_field = "client_date" if key == "client_expectation" else "commit_date"
        m._say = {"kpi": key, "yes": len(yes), "den": den, "value": value, "pending": len(pending),
                  "pending_due": [_md(t.get("client_date") or t.get("commit_date")) for t in pending],
                  # An item with no date from the client was never expected by one; that is
                  # worth saying for Client Expectation and is simply not applicable elsewhere.
                  "blank": len(blank) if key != "client_expectation" else len([t for t in blank if not t.get("client_date")]),
                  # A row with no date of its own is held to the period's, then the project's.
                  "dates": [_md(t.get(date_field) or period.get(date_field) or self.kif["project"].get(date_field))
                            for t in yes + no],
                  "check": period.get("client_check") or self.kif["project"].get("client_check") or "Handover",
                  "handover": _md(period.get("handover_date"))}
        return m

    def task_comprehension(self, period: dict) -> Measure:
        rows = self.deliverables_in(period["name"])
        return self._ratio_measure(
            "task_comprehension", period, rows, "understood",
            ("requirement was clear enough to build without going back to the client",
             "requirements were clear enough to build without going back to the client"),
        )

    def client_expectation(self, period: dict) -> Measure:
        rows = self.deliverables_in(period["name"])
        return self._ratio_measure(
            "client_expectation", period, rows, "met_client_date",
            ("item was delivered by that date", "items were delivered by that date"),
        )

    def delivery_commitment(self, period: dict) -> Measure:
        """PMS: "Team-negotiated commitments that were delivered on time." Formula: tasks
        delivered on time over total team-committed tasks. Insight: reliability of the team.

        Two things follow, and an earlier version of this got both wrong.

        The denominator is **the items the team committed to**, not every deliverable. An item
        nobody promised a date for is not evidence of reliability in either direction, so it is
        left out and named. Counting the whole backlog here turns a measure of promises kept
        into a measure of how much work happened to finish, which is Velocity's job.

        And "delivered on time" means whatever the team committed to deliver. For most teams
        that is their delivery event; for others it is the handover, or completion, or
        something they promised specifically. The profile says which, and the note says it in
        words so a reader is never guessing.
        """
        name = period["name"]
        cfg = (self.profile.get("workflow") or {}).get("commitment") or {}
        rows = self.deliverables_in(name)

        if cfg.get("scope") == "all-deliverables":
            committed, uncommitted = rows, []
        else:
            committed = [t for t in rows if self._has_commitment(t)]
            uncommitted = [t for t in rows if t not in committed]

        yes = [t for t in committed if t.get("met_commitment") == "Yes"]
        no = [t for t in committed if t.get("met_commitment") == "No"]
        pending = [t for t in committed if t.get("met_commitment") == "Pending"]
        den = len(yes) + len(no)

        gaps: list[str] = []
        if "status_history" not in self.capabilities and self.capabilities:
            gaps.append(
                "The tracker adapter could not read status history, so whether a commitment was met "
                "is based only on what was filled in by hand."
            )

        if den == 0:
            m = self._measure("delivery_commitment", value=None, numerator=0, denominator=0, gaps=gaps)
            if not committed:
                why = (f"No team commitment was recorded against any of the {len(rows)} items in this "
                       f"cycle, so there is nothing to measure reliability against")
            else:
                why = self._why_empty(period, name, pending=pending, blank=[])
            m.note_parts = [self._heading("delivery_commitment", period), why, ""]
            m._say = ({"kpi": "delivery_commitment", "none_committed": True, "rows": len(rows)} if not committed
                      else {"kpi": "delivery_commitment", "empty": why})
            return m

        value = _pct(len(yes), den)
        one = den == 1
        numbers = (f"{len(yes)} of {den} team {'commitment was' if one else 'commitments were'} "
                   f"met on time ({_n(value)}%)")

        left = []
        if pending:
            due = sorted({_md(t.get("commit_date")) for t in pending if t.get("commit_date")})
            due = [d for d in due if d]
            p_one = len(pending) == 1
            when = f" until {due[0]}" if len(due) == 1 else (f" until {due[0]} to {due[-1]}" if due else "")
            left.append(f"{len(pending)} more {'commitment is' if p_one else 'commitments are'} not due"
                        f"{when}, so {'it is' if p_one else 'they are'} not in this figure")
        if uncommitted:
            u_one = len(uncommitted) == 1
            left.append(f"{len(uncommitted)} {'item' if u_one else 'items'} the team made no commitment "
                        f"on {'is' if u_one else 'are'} left out")

        m = self._measure(
            "delivery_commitment", value=value, numerator=len(yes), denominator=den,
            counted_keys=[t["key"] for t in yes + no], gaps=gaps,
        )
        m.note_parts = [self._heading("delivery_commitment", period), numbers, "; ".join(left)]
        met = str(cfg.get("met_when") or "delivery").strip()
        m._say = {"kpi": "delivery_commitment", "yes": len(yes), "den": den, "value": value,
                  "pending": len(pending), "pending_due": [_md(t.get("commit_date")) for t in pending],
                  "uncommitted": len(uncommitted),
                  "dates": [_md(t.get("commit_date") or period.get("commit_date") or self.kif["project"].get("commit_date"))
                            for t in yes + no],
                  "phrase": {"delivery": "counted on each item's delivery date",
                             "handover": "counted on the handover to the client",
                             "completion": "counted on the date each item was completed"}.get(met.lower(), f"counted on {met}")}
        return m

    @staticmethod
    def _has_commitment(task: dict) -> bool:
        """The team negotiated something for this item: either a date was recorded against it,
        or somebody judged whether the commitment was met."""
        return bool(task.get("commit_date")) or task.get("met_commitment") in ("Yes", "No", "Pending")

    def defect_rate(self, period: dict) -> Measure:
        name = period["name"]
        delivered = self.delivered_in(name)
        counted, left_out = self.counted_defects(name)
        den = len(delivered)

        if den == 0:
            m = self._measure("defect_rate", value=None, numerator=len(counted), denominator=0)
            m.note_parts = [self._heading("defect_rate", period), self._nothing_yet(period, name), ""]
            m._say = {"kpi": "defect_rate", "none": True, "rows": len(self.deliverables_in(name))}
            return m

        value = _pct(len(counted), den)
        numbers = f"{len(counted)} {_plural(len(counted), 'bug')} on {_items_word(den)} ({_n(value)}%)"
        extra = ", ".join(_drop_phrase(why, len(rows)) for why, rows in left_out)
        third = f"Also reported but not counted: {extra}" if extra else ""

        m = self._measure(
            "defect_rate", value=value, numerator=len(counted), denominator=den,
            counted_keys=[d["key"] for d in counted],
        )
        m.note_parts = [self._heading("defect_rate", period), numbers, third]
        m._say = {"kpi": "defect_rate", "counted": len(counted), "den": den, "value": value,
                  "left": [(why, len(rows)) for why, rows in left_out]}
        return m

    def escaped_defect_rate(self, period: dict) -> Measure:
        """PMS: "Defects found after release / Total defects (before + after release)."

        The denominator is **defects, not delivered items**. The question this KPI asks is
        what share of the problems reached the client, not how much work was done - so a
        period that found forty issues in QA and let one through scores well, which is the
        right answer.
        """
        name = period["name"]
        reports = self.defects_in(name)
        # Rejected reports were never defects, so they belong in neither half.
        valid = [d for d in reports if d.get("rejected") != "Yes"]
        escaped = [d for d in valid if d.get("phase") == "Post-release"]
        den = len(valid)

        # Nothing can escape from a cycle the client has never seen. Reporting 0% here would
        # be a green "Met" bought by the absence of exposure.
        if not period.get("handover_date"):
            m = self._measure(
                "escaped_defect_rate", value=None, numerator=0, denominator=den,
                gaps=["Not handed over to the client yet, so nothing can have escaped."],
            )
            m.note_parts = [
                self._heading("escaped_defect_rate", period),
                "Not handed over to the client yet, so there is nothing to measure",
                "",
            ]
            m._say = {"kpi": "escaped_defect_rate", "no_handover": True, "den": den}
            return m

        if den == 0:
            m = self._measure("escaped_defect_rate", value=None, numerator=0, denominator=0)
            m.note_parts = [
                self._heading("escaped_defect_rate", period),
                "No valid issues were reported in this cycle",
                "",
            ]
            m._say = {"kpi": "escaped_defect_rate", "no_issues": True}
            return m

        value = _pct(len(escaped), den)
        one = den == 1
        if not escaped:
            numbers = (f"The client found none of the {den} valid {'issue' if one else 'issues'} "
                       f"reported in this cycle (0%)")
        else:
            numbers = (f"{len(escaped)} of {den} valid {'issue' if one else 'issues'} reached the "
                       f"client after handover ({_n(value)}%)")

        left = []
        rejected = len(reports) - den
        if rejected:
            left.append(f"{rejected} rejected {_plural(rejected, 'report')} left out of both halves")
        left.append(f"Counted from the handover on {_md(period['handover_date'])}")

        m = self._measure(
            "escaped_defect_rate", value=value, numerator=len(escaped), denominator=den,
            counted_keys=[d["key"] for d in escaped],
        )
        m.note_parts = [self._heading("escaped_defect_rate", period), numbers, "; ".join(left)]
        m._say = {"kpi": "escaped_defect_rate", "escaped": len(escaped), "den": den, "value": value,
                  "rejected": rejected, "handover": _md(period["handover_date"])}
        return m

    def rejection_rate(self, period: dict) -> Measure:
        name = period["name"]
        reports = self.defects_in(name)
        rejected = [d for d in reports if d.get("rejected") == "Yes"]
        den = len(reports)

        if den == 0:
            m = self._measure("rejection_rate", value=None, numerator=0, denominator=0)
            m.note_parts = [
                self._heading("rejection_rate", period),
                "No issues were reported in this cycle",
                "",
            ]
            m._say = {"kpi": "rejection_rate", "none_reported": True}
            return m

        value = _pct(len(rejected), den)
        numbers = (
            f"{len(rejected)} of {den} {_plural(den, 'report')} ({_n(value)}%)"
            if rejected
            else f"None of the {den} {_plural(den, 'report')} was rejected (0%)"
        )
        why = {}
        for d in rejected:
            r = (d.get("rejection_reason") or "").strip().lower()
            if r:
                why[r] = why.get(r, 0) + 1
        third = ""
        if why:
            third = "Reasons: " + ", ".join(f"{v} {k}" for k, v in sorted(why.items(), key=lambda x: -x[1]))

        m = self._measure(
            "rejection_rate", value=value, numerator=len(rejected), denominator=den,
            counted_keys=[d["key"] for d in rejected],
        )
        m.note_parts = [self._heading("rejection_rate", period), numbers, third]
        m._say = {"kpi": "rejection_rate", "rejected": len(rejected), "den": den, "value": value, "why": why}
        return m

    def rework_rate(self, period: dict) -> Measure:
        name = period["name"]
        completed = [t for t in self.deliverables_in(name) if t.get("closed")]
        reopened = [t for t in completed if t.get("reopened") == "Yes"]
        judged = [t for t in completed if t.get("reopened") in ("Yes", "No")]
        den = len(completed)

        gaps = []
        if "status_history" not in self.capabilities and self.capabilities:
            gaps.append(
                "The adapter cannot see status history, so a reopen is only detected where it was recorded by hand."
            )

        # Nothing was actually judged. Reporting 0% here would be a green "Met" bought with
        # ignorance - the same trap as an escaped-defect rate on a cycle nobody has seen.
        if den and not judged:
            m = self._measure("rework_rate", value=None, numerator=0, denominator=den, gaps=gaps)
            m.note_parts = [
                self._heading("rework_rate", period),
                f"Nothing to measure: none of the {den} completed {_plural(den, 'task')} records whether it was "
                f"reopened after closing",
                "",
            ]
            m._say = {"kpi": "rework_rate", "unjudged_all": den}
            return m

        if den == 0:
            m = self._measure("rework_rate", value=None, numerator=0, denominator=0, gaps=gaps)
            m.note_parts = [
                self._heading("rework_rate", period),
                "Nothing has been completed in this cycle yet",
                "",
            ]
            m._say = {"kpi": "rework_rate", "nothing_completed": True}
            return m

        # Judged, not merely completed: an item nobody could assess is not evidence of no rework.
        den = len(judged)
        value = _pct(len(reopened), den)
        numbers = (
            f"{len(reopened)} of {den} completed {_plural(den, 'task')} ({_n(value)}%)"
            if reopened
            else f"None of the {den} completed {_plural(den, 'task')} was reopened (0%)"
        )
        # A QA fail during the first test round is normal testing. Naming it is what stops
        # the reader assuming we hid something.
        near = [t for t in completed if t.get("reopened") == "No" and t.get("rework_evidence")]
        unjudged = len(completed) - den
        left = []
        if near:
            left.append(
                f"{len(near)} {_plural(len(near), 'item')} failed QA while still being tested "
                f"for the first time, which is normal testing and is not counted as rework"
            )
        if unjudged:
            left.append(
                f"{unjudged} completed {_plural(unjudged, 'task')} left out because the history needed to judge "
                f"{'it' if unjudged == 1 else 'them'} was not available"
            )
        third = "; ".join(left)

        m = self._measure(
            "rework_rate", value=value, numerator=len(reopened), denominator=den,
            counted_keys=[t["key"] for t in reopened], gaps=gaps,
        )
        m.note_parts = [self._heading("rework_rate", period), numbers, third]
        m._say = {"kpi": "rework_rate", "reopened": len(reopened), "den": den, "value": value,
                  "near": len(near), "unjudged": unjudged}
        return m

    def cr_rate(self, period: dict) -> Measure:
        name = period["name"]
        rows = self.deliverables_in(name)
        crs = [t for t in rows if t.get("type") == "CR"]
        planned = [t for t in rows if t.get("type") == "Task"]

        third = ""
        den = len(planned)
        if self.cr_denominator == "project":
            den = sum(1 for t in self.kif["tasks"] if t.get("type") == "Task")
            third = "Measured against the project's planned items"
        if den == 0:
            # A cycle made only of change requests still means something: measure it against
            # the whole project's planned scope and say that is what we did.
            den = sum(1 for t in self.kif["tasks"] if t.get("type") == "Task")
            if den:
                third = "Measured against the project's planned items, because this cycle is only additional requests"

        if den == 0:
            m = self._measure("cr_rate", value=None, numerator=len(crs), denominator=0)
            m.note_parts = [
                self._heading("cr_rate", period),
                "There is no planned scope to measure additions against",
                "",
            ]
            m._say = {"kpi": "cr_rate", "no_scope": True}
            return m

        value = _pct(len(crs), den)
        numbers = (
            f"{len(crs)} additional {_plural(len(crs), 'request')} against {den} planned {_plural(den, 'item')} ({_n(value)}%)"
            if crs
            else f"No additional requests against {den} planned {_plural(den, 'item')} (0%)"
        )

        m = self._measure(
            "cr_rate", value=value, numerator=len(crs), denominator=den,
            counted_keys=[t["key"] for t in crs],
        )
        m.note_parts = [self._heading("cr_rate", period), numbers, third]
        m._say = {"kpi": "cr_rate", "crs": len(crs), "den": den, "value": value,
                  "only_crs": "because this cycle is only" in third, "project": bool(third)}
        return m

    # -- note assembly -----------------------------------------------------------------

    def _heading(self, key: str, period: dict) -> str:
        reg = self.reg_by_key.get(key, {})
        head = reg.get("heading") or reg.get("name", key)
        if "{date}" in head:
            if key == "client_expectation":
                d = period.get("client_date") or self.kif["project"].get("client_date")
                head = head.replace("{date}", _md(d) or "the agreed date")
                check = (period.get("client_check") or self.kif["project"].get("client_check") or "Handover")
                # Say the basis in words. A bracketed tag reads like machine output.
                head += ", counted on each item's delivery date" if check == "Delivery" else ", counted on the handover date"
            else:
                d = period.get("commit_date") or self.kif["project"].get("commit_date")
                head = head.replace("{date}", _md(d) or "the agreed date")
        if key == "delivery_commitment":
            cfg = (self.profile.get("workflow") or {}).get("commitment") or {}
            met = str(cfg.get("met_when") or "delivery").strip()
            phrase = {
                "delivery": "counted on each item's delivery date",
                "handover": "counted on the handover to the client",
                "completion": "counted on the date each item was completed",
            }.get(met.lower(), f"counted on {met}")
            d = period.get("commit_date") or self.kif["project"].get("commit_date")
            head += f", against the date agreed for each, {phrase}" if not d else \
                    f" by {_md(d)}, {phrase}"
        return head

    def _nothing_yet(self, period: dict, name: str) -> str:
        rows = self.deliverables_in(name)
        if not rows:
            return "Nothing has been logged against this cycle yet"
        return f"Nothing to measure yet across {_items_word(len(rows))}"

    def _why_empty(self, period: dict, name: str, pending: list[dict], blank: list[dict]) -> str:
        """An empty ratio has to say *which* emptiness this is, or a reader assumes the run
        failed. There are three quite different reasons and they need different sentences."""
        rows = self.deliverables_in(name)
        if not rows:
            return "Nothing has been logged against this cycle yet"
        n = len(rows)
        if blank and len(blank) == n:
            subject = "the only item does not carry" if n == 1 else f"none of the {n} items carries"
            return f"Nothing to measure: {subject} the evidence this needs, so nothing could be judged either way"
        if pending and len(pending) == n:
            due = sorted({_md(t.get("client_date") or t.get("commit_date")) for t in pending})
            due = [d for d in due if d]
            subject = "the only item is" if n == 1 else f"all {n} items are"
            when = f" still ahead of {due[0]}" if due else " not due yet"
            tail = " and the handover has not happened" if not period.get("handover_date") else ""
            return f"Nothing to measure yet: {subject}{when}{tail}"
        return f"Nothing to measure yet across {_items_word(len(rows))}"

    def _reason_for(self, period_name: str, kpi_name: str) -> str:
        block = (self.reasons.get(period_name) or {})
        return (block.get(kpi_name) or block.get(kpi_name.lower()) or "").strip()

    def finish_note(self, m: Measure, period_name: str) -> None:
        """Glue the parts. The reason is the only part a human writes, and its job is to add
        what the numbers cannot say - never to repeat them.

        Two styles, one set of numbers. `sentences` (the default) says each part the way a
        person would; `fragments` is the older "heading || numbers || what was left out".
        The counting is identical - only the wording differs (note_sentences.py)."""
        sentences = self.note_style == "sentences" and getattr(m, "_say", None)
        if sentences:
            m.note_parts = note_sentences.sentences(m._say)
        parts = [p for p in (m.note_parts + [self._reason_for(period_name, m.name)]) if p and p.strip()]
        cleaned: list[str] = []
        for p in parts:
            p = _strip_links(p).strip().rstrip(".")
            if not p:
                continue
            # Drop a reason that opens with the same words as the part before it - that
            # repetition is the single most common thing that makes a note read like a machine.
            if cleaned and p.lower()[:28] == cleaned[-1].lower()[:28]:
                continue
            cleaned.append(p + ("." if sentences else ""))
        m.note = " || ".join(cleaned)
        if m.clamped and m.value is not None:
            m.note += (f" || There is more here than PMS can hold: it stores {_n(m.pms_value)}, and the real figure "
                       f"is {_n(m.value)}." if sentences else
                       f" || PMS accepts up to {_n(m.pms_value)}; the real figure is {_n(m.value)}")

    def apply_manual(self, m: Measure, period_name: str) -> None:
        """Let a person state a different value or note than the data supports.

        Sometimes they are right and the extract is not - the board was missing three items,
        or a defect was miscategorised and fixing it properly would take an hour they do not
        have. Refusing that outright just means they edit the number in PMS afterwards, where
        nobody can see that they did.

        So: allowed, and recorded. The computed figure is kept beside the one they set, the
        reason is required, and both the run summary and the workbook print it. An override
        that a reader can see is a judgement call; one they cannot is a discrepancy.
        """
        entry = (self.manual.get(period_name) or {}).get(m.name)
        if not entry:
            return
        has_value = entry.get("value") is not None and str(entry.get("value")).strip() != ""
        has_note = bool(str(entry.get("note") or "").strip())
        if not (has_value or has_note):
            # A reason with nothing to apply is not an override. The 'why' text belongs in
            # reasons.yaml, which is where the fourth part of the note comes from anyway.
            return

        why = str(entry.get("why") or "").strip()
        if not why:
            self.manual_report.append({
                "period": period_name, "kpi": m.name, "status": "not applied",
                "detail": "a hand-set value needs a reason, because it is printed with the numbers",
            })
            return

        m.computed_value, m.computed_note = m.value, m.note
        if has_value:
            try:
                m.value = float(entry["value"])
            except (TypeError, ValueError):
                self.manual_report.append({
                    "period": period_name, "kpi": m.name, "status": "not applied",
                    "detail": f"'{entry['value']}' is not a number",
                })
                m.computed_value, m.computed_note = None, ""
                return
            lo, hi = (self.reg_by_key.get(m.key, {}).get("range") or [0, 100])
            m.pms_value = max(lo, min(hi, m.value))
            m.clamped = m.pms_value != m.value
            if m.threshold is None:
                m.status = "Measured"
            elif m.direction == "higher-is-better":
                m.status = "Met" if m.value >= m.threshold else "Not met"
            else:
                m.status = "Met" if m.value <= m.threshold else "Not met"
        if has_note:
            m.note = _strip_links(str(entry["note"]))
        elif has_value and m.computed_value != m.value:
            # The note still describes what the data said. Leaving it beside a different value
            # is the one genuinely dishonest outcome here, so the note gains a final part
            # naming the figure a person recorded and why. Both readings stay visible.
            who = f" by {entry.get('by')}" if entry.get("by") else ""
            m.note += (f" || Recorded as {_n(m.value)}{'%' if m.unit == '%' else ''}{who} rather than "
                       f"the {_n(m.computed_value)}{'%' if m.unit == '%' else ''} above: {_strip_links(why).rstrip('.')}"
                       + ("." if self.note_style == "sentences" else ""))

        m.overridden = True
        m.override_reason = why
        m.override_by = str(entry.get("by") or "")
        self.manual_report.append({
            "period": period_name, "kpi": m.name, "status": "applied",
            "computed": m.computed_value, "set_to": m.value,
            "note_changed": has_note, "why": why, "by": m.override_by,
        })

    # -- period description ------------------------------------------------------------

    def period_description(self, period: dict) -> str:
        name = period["name"]
        rows = self.deliverables_in(name)
        n_plan = sum(1 for t in rows if t.get("type") == "Task")
        n_cr = sum(1 for t in rows if t.get("type") == "CR")
        bits = []
        if period.get("start") and period.get("end"):
            bits.append(f"{_md(period['start'])} to {_md(period['end'])}")
        mix = []
        if n_plan:
            mix.append(f"{n_plan} planned {_plural(n_plan, 'task')}")
        if n_cr:
            mix.append(f"{n_cr} additional {_plural(n_cr, 'request')}")
        if mix:
            bits.append(" + ".join(mix))
        if period.get("handover_date"):
            bits.append(f"handed over {_md(period['handover_date'])}")
        return ", ".join(bits)

    # -- run ---------------------------------------------------------------------------

    def run(self) -> list[PeriodResult]:
        out: list[PeriodResult] = []
        for period in self.kif["periods"]:
            name = period["name"]
            measures = [
                self.velocity(period),
                self.task_comprehension(period),
                self.client_expectation(period),
                self.delivery_commitment(period),
                self.defect_rate(period),
                self.escaped_defect_rate(period),
                self.rejection_rate(period),
                self.rework_rate(period),
                self.cr_rate(period),
            ]
            for m in measures:
                self.finish_note(m, name)
                self.apply_manual(m, name)
            rows = self.deliverables_in(name)
            facts = {
                "deliverables": len(rows),
                "delivered": len(self.delivered_in(name)),
                "not_delivered": len([t for t in rows if not t.get("delivered")]),
                "planned": sum(1 for t in rows if t.get("type") == "Task"),
                "additional_requests": sum(1 for t in rows if t.get("type") == "CR"),
                "excluded": sum(1 for t in self.tasks_in(name) if t.get("type") == "Excluded"),
                "reports": len(self.defects_in(name)),
                "defects_counted": len(self.counted_defects(name)[0]),
                "client_date": period.get("client_date") or self.kif["project"].get("client_date"),
                "commit_date": period.get("commit_date") or self.kif["project"].get("commit_date"),
                "handover_date": period.get("handover_date"),
                "pms_period_id": period.get("pms_period_id"),
            }
            out.append(
                PeriodResult(
                    period=name,
                    measures=measures,
                    facts=facts,
                    description=self.period_description(period),
                )
            )
        return out


# --------------------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------------------


def to_markdown(results: list[PeriodResult], kif: dict, overrides: list[dict] | None = None,
                manual: list[dict] | None = None) -> str:
    p = kif["project"]
    lines = [f"# KPI results - {p.get('name', 'project')}", ""]
    gen = kif.get("generated") or {}
    if gen:
        lines.append(
            f"Source: {gen.get('adapter', 'unknown')} adapter, read {gen.get('at', 'unknown time')}. "
            f"PMS project {p.get('pms_project_id') or 'not set'}."
        )
        lines.append("")
    if overrides:
        # Printed before the numbers, not in a footnote. Somebody reading these values needs
        # to know up front that a local rule shaped them.
        lines += ["## Local rules applied to this run", ""]
        for o in overrides:
            lines.append(f"- **{o['rule']}** = `{o['value']}` - {o['why']} *({o['status']})*")
        lines.append("")
    if manual:
        lines += ["## Values set by hand", ""]
        for o in manual:
            if o.get("status") == "applied":
                moved = (f"{_n(o.get('computed'))} -> {_n(o.get('set_to'))}"
                         if o.get("computed") != o.get("set_to") else "note rewritten")
                who = f", by {o['by']}" if o.get("by") else ""
                lines.append(f"- **{o['period']} / {o['kpi']}**: {moved}{who} - {o['why']}")
            else:
                lines.append(f"- **{o['period']} / {o['kpi']}**: not applied - {o['detail']}")
        lines.append("")
    for r in results:
        lines += [f"## {r.period}", "", f"*{r.description}*" if r.description else "", ""]
        lines.append("| KPI | Value | Target | Status |")
        lines.append("|---|---|---|---|")
        for m in r.measures:
            val = f"{_n(m.value)}{'' if m.unit != '%' else '%'}" if m.value is not None else "-"
            tgt = "" if m.threshold is None else (
                f"min {_n(m.threshold)}" if m.direction == "higher-is-better" else f"max {_n(m.threshold)}"
            )
            # A target this project sets for itself is marked, so nobody comparing two
            # projects assumes they were held to the same bar.
            if "for project" in (m.threshold_source or ""):
                tgt += " \\*"
            if m.overridden:
                val += " (set by hand)"
            lines.append(f"| {m.name} | {val} | {tgt} | {m.status} |")
        lines.append("")
        own = sorted({m.threshold_source for m in r.measures if "for project" in (m.threshold_source or "")})
        if own:
            lines.append(f"\\* Target {own[0]}, not the PMS default.")
            lines.append("")
        lines.append("**Notes that would go to PMS**")
        lines.append("")
        for m in r.measures:
            lines.append(f"- **{m.name}** - {m.note}")
        gaps = [g for m in r.measures for g in m.gaps]
        if gaps:
            lines += ["", "**Gaps**", ""] + [f"- {g}" for g in dict.fromkeys(gaps)]
        lines.append("")
    return "\n".join(lines)


def to_pms_payloads(results: list[PeriodResult], kif: dict) -> list[dict]:
    """What a push would send. Building it here, away from any network code, means the
    dry run and the real push can never disagree about what was going to happen."""
    out = []
    for r in results:
        out.append(
            {
                "projectId": kif["project"].get("pms_project_id"),
                "periodId": r.facts.get("pms_period_id"),
                "name": r.period,
                "description": _strip_links(r.description),
                "kpis": [
                    {
                        "kpiId": m.pms_id,
                        "name": m.name,
                        "value": m.pms_value,
                        "note": m.note,
                        "overridden": m.overridden,
                        "override_reason": m.override_reason,
                        "computed_value": m.computed_value,
                    }
                    for m in r.measures
                    if m.value is not None and m.pms_id is not None
                ],
                "skipped": [
                    {"name": m.name, "reason": m.note or "Not measured"}
                    for m in r.measures
                    if m.value is None
                ],
            }
        )
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compute PMS KPIs from a KIF document.")
    ap.add_argument("--kif", required=True, type=Path)
    ap.add_argument("--profile", type=Path)
    ap.add_argument("--project", help="Which project in the profile. Required when it covers several.")
    ap.add_argument("--reasons", type=Path, help="Per-period, per-KPI 'why' text written by a human.")
    ap.add_argument("--manual", type=Path,
                    help="Values or notes set by hand, each with a reason. Written by "
                         "'workbook.py review' when somebody edits a computed cell in the sheet.")
    ap.add_argument("--registry", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--markdown", type=Path)
    ap.add_argument("--payloads", type=Path)
    args = ap.parse_args(argv)

    kif = _load_any(args.kif)
    # Resolve for this project: profile defaults, then its account, then the project itself.
    profile = resolve_profile(load_profile(args.profile), args.project)[0] if args.profile else {}
    reasons = _load_any(args.reasons) if args.reasons else {}
    manual = _load_any(args.manual) if (args.manual and args.manual.exists()) else {}
    from kpi_registry import resolve_path
    reg_path = resolve_path(args.profile, profile, args.registry)
    registry = _load_any(reg_path)

    engine = Engine(kif, profile, registry, reasons, manual)
    results = engine.run()

    doc = {
        "project": kif["project"],
        "generated": kif.get("generated"),
        "registry_source": registry.get("source"),
        "registry_synced_at": registry.get("synced_at"),
        "custom_overrides": engine.overrides_report,
        "manual_values": engine.manual_report,
        "periods": [r.as_dict() for r in results],
    }
    if args.out:
        args.out.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    if args.markdown:
        args.markdown.write_text(
            to_markdown(results, kif, engine.overrides_report, engine.manual_report), encoding="utf-8")
    if args.payloads:
        args.payloads.write_text(json.dumps(to_pms_payloads(results, kif), indent=2), encoding="utf-8")
    if not (args.out or args.markdown or args.payloads):
        print(to_markdown(results, kif, engine.overrides_report, engine.manual_report))

    if registry.get("source") == "bundled-fallback":
        print(
            "\nNote: KPI definitions came from the bundled fallback, not from PMS. "
            "Run scripts/kpi_registry.py --refresh before a run that matters.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
