#!/usr/bin/env python3
"""
The KPI tracker, described once, written twice.

The sheet is the product. A lead opens it, reads it, changes a yellow cell and watches the
number move - so it has to look like something a careful person built by hand, and it has to
be alive: grey cells are real formulas over the registers, not numbers pasted in.

This file describes that workbook as plain data - tabs, cells, styles, formulas, dropdowns,
conditional colours - and knows nothing about file formats. Two small writers turn the same
description into an .xlsx (sheet_xlsx.py) and into a Google Sheet updated in place
(sheet_google.py), which is why the two look the same: they are the same.

Two rules keep a live sheet honest:

  * The formulas mirror the engine's counting rules, row for row. The engine stays the
    authority - it is what reaches PMS - and the KPI Summary carries the engine's own figure
    beside each live one. When they differ, somebody has edited the sheet since the last
    run, and the row says so instead of letting two numbers quietly disagree.

  * Colour is the whole grammar. Yellow is yours and is read back at the start of the next
    run. White was read from a source. Grey is worked out.

Only functions that mean the same thing in Excel and in Google Sheets are used (COUNTIFS,
SUMIFS, INDEX/MATCH, TEXT, REPT). The one exception is the dashboard's bars, which are
SPARKLINEs in Google and fall back to a text bar everywhere else.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any
from kpi_registry import NAME_TO_KEY

MODEL_VERSION = "2.0"
LAST = 999            # formulas look down to here, so a row added by hand is still counted
SPARE = 40            # formatted, formula-filled rows past the data
MAX_PERIODS = 12      # dashboard slots
KPI_ORDER = ["Velocity", "Task Comprehension", "Client Expectation", "Delivery Commitment", "Defect Rate",
             "Escaped Defect Rate", "Defect Rejection Rate", "Rework Rate", "CR Rate"]
KPI_KEYS = ["velocity", "task_comprehension", "client_expectation", "delivery_commitment", "defect_rate",
            "escaped_defect_rate", "rejection_rate", "rework_rate", "cr_rate"]


def metric_name(name: str) -> str:
    """Formula identity follows the same registry aliases as the engine; labels stay intact."""
    key = NAME_TO_KEY.get(name.lower().strip())
    return dict(zip(KPI_KEYS, KPI_ORDER)).get(key, name)

NAVY, BAND, SOFT, YELLOW, GREY, WHITE = "1F3864", "2F5597", "D9E2F3", "FFF2CC", "F2F2F2", "FFFFFF"
LINE, MUTED, REDFILL, AMBER, TOTAL = "D9D9D9", "666666", "F8CBAD", "FFE599", "D9E1F2"

# name -> (font, fill, align).  font: b/i/size/color.  align: h/v/wrap.  box = thin border.
STYLES: dict[str, dict] = {
    "title": {"b": True, "size": 14, "color": NAVY, "v": "bottom"},
    "sub": {"i": True, "color": MUTED},
    "band": {"b": True, "size": 11, "color": WHITE, "fill": BAND},
    "soft": {"b": True, "fill": SOFT, "box": True, "v": "top", "wrap": True},
    "head": {"b": True, "color": WHITE, "fill": NAVY, "h": "center", "v": "center", "wrap": True, "box": True},
    "label": {"b": True, "fill": WHITE, "box": True, "v": "top", "wrap": True},
    "text": {"fill": WHITE, "box": True, "v": "top", "wrap": True},
    "total": {"b": True, "fill": TOTAL, "box": True},
    "bar": {"fill": WHITE, "box": True, "v": "center", "color": "38761D"},
    "note": {"i": True, "size": 9, "color": MUTED, "v": "top", "wrap": True},
}
for _role, _fill in (("in", YELLOW), ("calc", GREY), ("data", WHITE)):
    for _sfx, _h in (("", None), ("_c", "center"), ("_r", "right")):
        STYLES[_role + _sfx] = {"fill": _fill, "box": True, "v": "top", "wrap": True, **({"h": _h} if _h else {})}
STYLES["link"] = {**STYLES["data"], "color": "1155CC", "u": True}
STYLES["kpi"] = {**STYLES["data"], "b": True}

DATE = "yyyy-mm-dd"


def col(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _date(value: Any) -> Any:
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value[:10] or ""):
        try:
            return dt.date.fromisoformat(value[:10])
        except ValueError:
            return value
    return value


def _yn(v: Any) -> Any:
    return {True: "Yes", False: "No"}.get(v, v) if isinstance(v, bool) else v


_MD = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def plain(text: str | None) -> str:
    """'[the 08/12 handover](url)' -> 'the 08/12 handover'. Links sit on the words in the
    workbook where a cell can carry one; a cell full of raw markdown just looks broken."""
    return _MD.sub(r"\1", text or "")


def first_link(text: str | None) -> str | None:
    m = _MD.search(text or "")
    return m.group(2) if m else None


class Tab:
    def __init__(self, name: str, color: str = NAVY, gridlines: bool = False):
        self.name, self.color, self.gridlines = name, color, gridlines
        self.cells: dict[tuple[int, int], dict] = {}
        self.widths: dict[int, float] = {}
        self.heights: dict[int, float] = {}
        self.freeze: tuple[int, int] = (0, 0)
        self.validations: list[dict] = []
        self.cond: list[dict] = []
        self.hidden_cols: list[int] = []
        self.readback: dict | None = None
        self.append_only = False

    def put(self, r: int, c: int, v: Any = None, style: str = "text", *, f: str | None = None,
            gf: str | None = None, link: str | None = None, fmt: str | None = None) -> None:
        v = _date(_yn(v))
        if isinstance(v, (dt.date, dt.datetime)) and not fmt:
            fmt = DATE
        cell = {"style": style}
        for k, val in (("v", v), ("f", f), ("gf", gf), ("link", link), ("fmt", fmt)):
            if val not in (None, ""):
                cell[k] = val
        self.cells[(r, c)] = cell

    def row(self, r: int, values: list, style: str = "text", start: int = 1) -> None:
        for i, v in enumerate(values):
            self.put(r, start + i, v, style)

    def band(self, r: int, text: str, c1: int, c2: int, style: str = "band") -> None:
        for c in range(c1, c2 + 1):
            self.put(r, c, text if c == c1 else None, style)

    def dropdown(self, r1: int, c1: int, r2: int, c2: int, values: list[str] | None = None,
                 source: str | None = None) -> None:
        self.validations.append({"range": (r1, c1, r2, c2), "values": values, "source": source})

    def when(self, r1: int, c1: int, r2: int, c2: int, formula: str, fill: str | None = None,
             color: str | None = None) -> None:
        self.cond.append({"range": (r1, c1, r2, c2), "formula": formula, "fill": fill, "color": color})

    @property
    def size(self) -> tuple[int, int]:
        rows = max((r for r, _ in self.cells), default=1)
        cols = max(max((c for _, c in self.cells), default=1), max(self.widths, default=1))
        return rows, cols


# --------------------------------------------------------------------------------------
# registers
# --------------------------------------------------------------------------------------
# (key, header, width, role, align).  role: in = yours (read back) · data = read · calc = worked out

TASK_COLS = [
    ("n", "#", 4, "calc", "c"), ("period", "Period", 14, "in", ""), ("key", "Ticket", 11, "data", ""),
    ("link", "Link", 8, "data", ""), ("title", "Title", 48, "data", ""), ("type", "Item Type", 10, "in", ""),
    ("planned", "Planned (initial scope)?", 10, "in", ""), ("hours", "Est. Hours (counted)", 9, "calc", "r"),
    ("story_points", "Story Points", 8, "in", "r"), ("hours_source", "Hours Source", 30, "data", ""),
    ("assignee", "Assignee", 18, "data", ""), ("created", "Created", 11, "data", ""),
    ("delivered", "Delivered", 11, "in", ""), ("closed", "Closed", 11, "in", ""),
    ("status", "Status", 8, "calc", "c"), ("understood", "Understood w/o Client?", 11, "in", ""),
    ("understood_why", "Comprehension Evidence", 40, "data", ""), ("understood_link", "Comprehension Link", 9, "data", ""),
    ("client_expected", "Client-Expected?", 10, "in", ""), ("client_date", "Client Expected Date", 11, "in", ""),
    ("met_client_date", "Met Client Date?", 10, "calc", "c"), ("team_committed", "Team Committed?", 10, "in", ""),
    ("commit_date", "Commitment Date", 11, "in", ""), ("met_commitment", "Met Commitment?", 10, "calc", "c"),
    ("reopened", "Reopened after closing?", 9, "in", ""), ("rework_evidence", "Rework Evidence", 34, "data", ""),
    ("rework_link", "Rework Link", 9, "data", ""), ("remarks", "Remarks and sources", 44, "data", ""),
    ("hours_dev", "Dev Hours", 8, "in", "r"), ("hours_qa", "QA Hours", 8, "in", "r"),
    ("board_status", "Board Column", 16, "data", ""), ("check", "Check (how this row was decided)", 40, "data", ""),
    ("handover", "Period handover", 11, "calc", ""), ("client_check", "Client date check", 10, "calc", ""),
    ("item", "Row ID", 10, "calc", ""),
    ("delivery_unknown", "Delivery evidence missing", 10, "data", ""),
]
DEFECT_COLS = [
    ("n", "#", 4, "calc", "c"), ("period", "Period", 14, "in", ""), ("key", "Ticket", 11, "data", ""),
    ("link", "Link", 8, "data", ""), ("title", "Title", 52, "data", ""), ("kind", "Kind", 11, "in", ""),
    ("reported_by", "Reported By", 20, "data", ""), ("reported_on", "Reported On", 11, "data", ""),
    ("phase", "Phase", 12, "in", ""), ("pre_existing", "Pre-existing?", 10, "in", ""),
    ("rejected", "Rejected?", 9, "in", ""), ("rejection_reason", "Rejection Reason", 30, "in", ""),
    ("evidence", "Evidence", 9, "data", ""), ("final_status", "Final Status", 18, "in", ""),
    ("counts", "Counts in Defect Rate?", 11, "calc", "c"), ("remarks", "Remarks and sources", 40, "data", ""),
    ("check", "Check (how this row was decided)", 40, "data", ""), ("item", "Row ID", 10, "calc", ""),
]
PERIOD_COLS = [
    ("n", "#", 4, "calc", "c"), ("name", "Period Name (max 25)", 22, "in", ""), ("start", "Start", 12, "in", ""),
    ("end", "End", 12, "in", ""), ("description", "PMS Description (auto)", 34, "calc", ""),
    ("client_date", "Client Expected Date", 14, "in", ""), ("commit_date", "Commitment Date", 14, "in", ""),
    ("handover_date", "Handed Over On", 14, "in", ""), ("pms_period_id", "PMS Period ID", 12, "in", "c"),
    ("pushed_on", "Pushed to PMS On", 14, "data", ""), ("notes", "Notes", 70, "in", ""),
    ("plan_text", "Original Plan", 40, "in", ""), ("team_hours", "Team-level Effort (h)", 12, "in", "r"),
    ("client_check", "Client Date Check", 12, "in", ""),
]
PHASE_OUT = {"Post-release": "Post-release"}          # everything else shows as Pre-release
FINAL_OUT = {"Fixed": "Fixed / Closed", "Closed": "Fixed / Closed", "Deferred": "Deferred (moved out of scope)",
             "Rejected": "Rejected", "Open": "Open"}


def ticket(row: dict) -> str | None:
    """What a person calls the row. A card with no ticket key is known by its title, so the
    tracker's sixteen-digit id stays out of sight in the hidden Row ID column."""
    key = str(row.get("key") or "")
    if key.startswith("PLAN:"):
        return "Plan item"
    return None if re.fullmatch(r"\d{10,}", key) else key or None


def _ix(cols: list[tuple]) -> dict[str, str]:
    return {c[0]: col(i) for i, c in enumerate(cols, start=1)}


T, D, P = _ix(TASK_COLS), _ix(DEFECT_COLS), _ix(PERIOD_COLS)


def _rng(sheet: str, letter: str, first: int) -> str:
    return f"'{sheet}'!${letter}${first}:${letter}${LAST}"


def _register(tab: Tab, title: str, subtitle: str, cols: list[tuple], rows: list[dict], first: int = 4,
              freeze_cols: int = 5) -> int:
    tab.put(1, 2, title, "title")
    tab.put(2, 2, subtitle, "sub")
    hdr = first - 1
    tab.heights[hdr] = 46.5
    for i, (_, header, width, _, _) in enumerate(cols, start=1):
        tab.put(hdr, i, header, "head")
        tab.widths[i] = width
    tab.freeze = (hdr, freeze_cols)
    last = first + len(rows) + SPARE - 1
    for r in range(first, last + 1):
        rec = rows[r - first] if r - first < len(rows) else {}
        for i, (key, _, _, role, align) in enumerate(cols, start=1):
            style = role + ("_" + align if align else "")
            cell = rec.get(key)
            if isinstance(cell, dict):                      # {"f": formula} or {"v":…, "link":…}
                tab.put(r, i, cell.get("v"), cell.get("style") or style, f=cell.get("f"), link=cell.get("link"))
            else:
                tab.put(r, i, cell, style)
    return last


def build(kif: dict, results: dict, ctx: dict) -> list[Tab]:
    """ctx: profile, registry, reasons, manual, questions, sources, changes, push_log, grain,
    refreshed (ISO), tool_version."""
    LAST = max(999, len(kif.get("tasks") or []) + SPARE + 4,
               len(kif.get("defects") or []) + SPARE + 4, len(ctx.get("questions") or []) + SPARE + 4)

    def _rng(sheet: str, letter: str, first: int) -> str:
        return f"'{sheet}'!${letter}${first}:${letter}${LAST}"

    profile = ctx.get("profile") or {}
    policy = {"count_observations": False, "count_improvements": False, "count_pre_existing": False,
              "count_post_release": True, **(profile.get("policy") or {})}
    project = kif.get("project") or {}
    periods = kif.get("periods") or []
    pnames = [p.get("name") for p in periods]
    display_names = {metric_name(m["name"]): m["name"] for p in results.get("periods") or []
                     for m in p.get("measures") or []}
    display_order = [display_names.get(name, name) for name in KPI_ORDER]
    by_handover = "handover" in str(((profile.get("workflow") or {}).get("commitment") or {}).get("met_when") or "").lower()
    hours_basis = (profile.get("sources") or {}).get("hours_basis") or "dev"
    cr_den = ctx.get("cr_denominator") or "period"

    # ---- Config first: every other tab's formulas point at its cells ------------------
    cfg = Tab("Config", BAND)
    cfg.widths.update({1: 3, 2: 34, 3: 46, 4: 12, 5: 10, 6: 12, 7: 60, 8: 60, 9: 30})
    cfg.put(1, 1, "KPI Tracker - Configuration", "title")
    cfg.put(2, 1, "Yellow cells are settings the sheet's formulas read. The run reads them back: dates are kept; "
                  "a counting rule changed here is reported and asked about, never applied quietly.", "sub")
    cfg.freeze = (3, 0)
    ref: dict[str, str] = {}
    r = 3
    cfg.band(r, "PROJECT", 2, 3, "soft")
    info = [
        ("Project name", project.get("name")), ("Client", ctx.get("client") or ""),
        ("PMS project ID", project.get("pms_project_id")), ("PMS KPI page", project.get("pms_url") or ""),
        ("Issue tracker", project.get("tracker")), ("Tracker board", project.get("tracker_url")),
        ("Engagement type", ctx.get("engagement") or "Project"), ("Period type", project.get("period_type")),
        ("Sources read", ctx.get("sources_text") or plain(project.get("sources_text")) or "Issue tracker only"),
        ("Deliverables are counted as", {"plan-items": "Plan items (a card the plan splits into modules counts once per module)",
                                        "board-cards": "Board cards (one card, one deliverable)"}.get(ctx.get("grain") or "board-cards")),
        ("Calculated as of", (ctx.get("as_of") or ctx.get("refreshed") or "")[:10]), ("Prepared by", ctx.get("prepared_by") or ""),
    ]
    for label, value in info:
        r += 1
        cfg.put(r, 2, label, "label")
        link = value if isinstance(value, str) and value.startswith("http") else None
        cfg.put(r, 3, ("Open" if link else value), "link" if link else "data", link=link)
        if label == "Project name":
            ref["project_name"] = f"Config!$C${r}"
        if label == "PMS project ID":
            ref["pms_id"] = f"Config!$C${r}"
        if label == "Calculated as of":
            ref["as_of"] = f"Config!$C${r}"

    r += 2
    cfg.band(r, "COUNTING RULES", 2, 4, "soft")
    rules = [
        ("velocity_unit", "Velocity unit", project.get("velocity_unit") or "Estimated Hours",
         ["Estimated Hours", "Story Points"], "What Velocity adds up for delivered tasks and additional requests."),
        ("hours_basis", "Hours counted in Velocity", "Dev + QA" if hours_basis == "dev+qa" else "Dev only",
         ["Dev only", "Dev + QA"], "Dev + QA adds an item's QA hours once the item is closed."),
        ("count_obs", "Count observations as defects?", policy["count_observations"], ["Yes", "No"],
         "No = only Bug rows count in Defect Rate."),
        ("count_imp", "Count improvements as defects?", policy["count_improvements"], ["Yes", "No"], ""),
        ("count_pre", "Count pre-existing defects in Defect Rate?", policy["count_pre_existing"], ["Yes", "No"],
         "Pre-existing = already in the product before this work."),
        ("count_post", "Count post-release defects in Defect Rate?", policy["count_post_release"], ["Yes", "No"],
         "Post-release defects always count in Escaped Defect Rate."),
        ("commit_on", "A commitment is met on", "Handover" if by_handover else "Delivery", ["Delivery", "Handover"],
         "Delivery = the item reached its delivery event by the date. Handover = the build reached the client by it."),
        ("cr_den", "CR Rate is measured against", "Whole project" if cr_den == "project" else "This period",
         ["This period", "Whole project"], "A period made only of additional requests is always measured against the whole project."),
    ]
    for key, label, value, choices, hint in rules:
        r += 1
        cfg.put(r, 2, label, "label")
        cfg.put(r, 3, value, "in")
        cfg.put(r, 4, hint, "note")
        cfg.dropdown(r, 3, r, 3, choices)
        ref[key] = f"Config!$C${r}"

    r += 2
    cfg.band(r, "KPI TARGETS  (source and any local review override are shown beside each target)", 2, 9, "soft")
    r += 1
    for i, h in enumerate(["KPI", "Unit", "PMS KPI ID", "Type", "Target", "Formula (PMS definition)",
                           "How this sheet counts it", "Target comes from"], start=2):
        cfg.put(r, i, h, "head")
    measures = {m["name"]: m for per in results.get("periods") or [] for m in per.get("measures") or []}
    reg = {x.get("name"): x for x in (ctx.get("registry") or {}).get("kpis") or []}
    names = [n for n in KPI_ORDER if n in measures] + [n for n in measures if n not in KPI_ORDER]
    ref["kpi_first"] = r + 1
    for name in names:
        r += 1
        m, g = measures[name], reg.get(name) or {}
        cfg.put(r, 2, name, "kpi")
        cfg.put(r, 3, "Per Config" if name == "Velocity" else "%", "data_c")
        cfg.put(r, 4, m.get("pms_id"), "data_c")
        cfg.put(r, 5, "Min" if m.get("direction") == "higher-is-better" else "Max", "data_c")
        cfg.put(r, 6, m.get("threshold"), "data_c")
        cfg.put(r, 7, g.get("formula_pms") or g.get("formula") or g.get("definition") or "", "data")
        cfg.put(r, 8, HOW_COUNTED.get(metric_name(name), ""), "data")
        cfg.put(r, 9, m.get("threshold_source") or "", "data")
    ref["kpi_last"] = r
    k1, k2 = ref["kpi_first"], ref["kpi_last"]
    ref["kpi_names"], ref["kpi_ids"] = f"Config!$B${k1}:$B${k2}", f"Config!$D${k1}:$D${k2}"
    ref["kpi_types"], ref["kpi_targets"] = f"Config!$E${k1}:$E${k2}", f"Config!$F${k1}:$F${k2}"

    r += 2
    cfg.band(r, "PROJECT DATES  (used when a period or a task has no date of its own)", 2, 4, "band")
    dates = [
        ("client_date", "Client expected date", project.get("client_date"),
         "What the client expects: the planned handover, a client deadline, or a date agreed again after the client added work."),
        ("commit_date", "Team commitment date", project.get("commit_date"),
         "What the team agreed to deliver by: the milestone date or a date negotiated later."),
        ("client_check", "Client date check", project.get("client_check") or "Handover",
         "Handover = met when the build reached the client by the date. Delivery = met when the item itself was delivered by it."),
        ("dates_why", "Why these dates", plain(project.get("dates_why")), "Short reason, with where it was agreed."),
    ]
    cfg_read = {}
    for key, label, value, hint in dates:
        r += 1
        cfg.put(r, 2, label, "label")
        cfg.put(r, 3, value, "in")
        cfg.put(r, 4, hint, "note")
        ref[key] = f"Config!$C${r}"
        cfg_read[key] = (r, 3)
        if key == "client_check":
            cfg.dropdown(r, 3, r, 3, ["Handover", "Delivery"])
    cfg.readback = {"kind": "cells", "cells": cfg_read,
                    "rules": {k: (int(re.search(r"\$(\d+)$", ref[k]).group(1)), 3)
                              for k in ("velocity_unit", "hours_basis", "count_obs", "count_imp", "count_pre",
                                        "count_post", "commit_on", "cr_den")}}

    # ---- Periods ------------------------------------------------------------------------
    per = Tab("Periods", BAND)
    desc = {p["period"]: p.get("description") for p in results.get("periods") or []}
    pushed = ctx.get("pushed_on") or {}
    prow = []
    for p in periods:
        prow.append({
            "name": p.get("name"), "start": p.get("start"), "end": p.get("end"),
            "description": desc.get(p.get("name")), "client_date": p.get("client_date"),
            "commit_date": p.get("commit_date"), "handover_date": p.get("handover_date"),
            "pms_period_id": p.get("pms_period_id"), "pushed_on": pushed.get(p.get("name")),
            "notes": plain(p.get("notes")), "plan_text": plain(p.get("plan_text")),
            "team_hours": p.get("team_hours"), "client_check": p.get("client_check"),
        })
    last_p = _register(per, "Periods", "One row per KPI period. Leave a date empty to use the project date from Config.",
                       PERIOD_COLS, prow, first=5, freeze_cols=2)
    per.heights[4] = 31.5
    _fill_row_formulas(per, PERIOD_COLS, 5, last_p, {"n": '=IF(B{r}="","",ROW()-4)'})
    per.dropdown(5, 14, last_p, 14, ["Handover", "Delivery"])
    per.readback = {"kind": "table", "first": 5, "key": "name", "cols": PERIOD_COLS}
    PN, PH, PC, PM = (f"Periods!${P[k]}$5:${P[k]}$200" for k in ("name", "handover_date", "client_check", "team_hours"))

    # ---- Task Register --------------------------------------------------------------------
    tk = Tab("Task Register")
    trows = []
    for t in kif.get("tasks") or []:
        excl = t.get("type") == "Excluded"
        ulink = t.get("understood_evidence") if str(t.get("understood_evidence") or "").startswith("http") else None
        rlink = first_link(t.get("rework_evidence")) or (t.get("link") if t.get("reopened") == "Yes" else None)
        trows.append({
            "period": t.get("period"), "key": ticket(t),
            "link": {"v": "Open", "link": t["link"], "style": "link"} if t.get("link") else None,
            "title": t.get("title"), "type": t.get("type"),
            "planned": None if excl else ("Yes" if t.get("planned") else "No"),
            "story_points": t.get("story_points"), "hours_source": t.get("hours_source"),
            "assignee": t.get("assignee"), "created": t.get("created"), "delivered": t.get("delivered"),
            "closed": t.get("closed"), "understood": t.get("understood"),
            "understood_why": plain(t.get("understood_why")),
            "understood_link": {"v": "Open", "link": ulink, "style": "link"} if ulink else None,
            "client_expected": None if excl else ("Yes" if t.get("client_date") else "No"),
            "client_date": t.get("client_date"),
            "team_committed": None if excl else ("Yes" if (t.get("commit_date") or t.get("met_commitment")) else "No"),
            "commit_date": t.get("commit_date"), "reopened": t.get("reopened"),
            "rework_evidence": plain(t.get("rework_evidence")),
            "rework_link": {"v": "Open", "link": rlink, "style": "link"} if rlink and t.get("rework_evidence") else None,
            "remarks": plain(t.get("remarks")) or (t.get("exclude_reason") if excl else ""),
            "hours_dev": t.get("hours_dev"), "hours_qa": t.get("hours_qa"), "board_status": t.get("status"),
            "check": t.get("check"), "item": t.get("_row") or t.get("_item"),
            "delivery_unknown": "Yes" if (t.get("client_date") or t.get("commit_date")) and t.get("met_client_date") is None and t.get("met_commitment") is None and not t.get("delivered") else "No",
        })
    n_tasks = len(trows)
    last_t = _register(tk, f"Task Register ({n_tasks} rows)",
                       "Every planned task and additional request, plus excluded cards so nothing looks missing. "
                       "Yellow = you can change it; grey = worked out by formula; Check says how a row was decided.",
                       TASK_COLS, trows)
    tf = {
        "n": '=IF(B{r}="","",ROW()-3)',
        "hours": f'=IF(OR(B{{r}}="",AND({T["hours_dev"]}{{r}}="",{T["hours_qa"]}{{r}}="")),"",N({T["hours_dev"]}{{r}})'
                 f'+IF(AND({ref["hours_basis"]}="Dev + QA",{T["closed"]}{{r}}<>""),N({T["hours_qa"]}{{r}}),0))',
        "status": f'=IF(B{{r}}="","",IF({T["delivered"]}{{r}}<>"","Done","Open"))',
        "handover": f'=IF(B{{r}}="","",IFERROR(INDEX({PH},MATCH($B{{r}},{PN},0)),""))',
        # Matched by its words rather than by "is the cell empty", because spreadsheets disagree
        # about what an empty looked-up cell equals.
        "client_check": f'=IF(B{{r}}="","",IF(COUNTIFS({PN},$B{{r}},{PC},"Handover")>0,"Handover",'
                        f'IF(COUNTIFS({PN},$B{{r}},{PC},"Delivery")>0,"Delivery",{ref["client_check"]})))',
    }
    dl, ho = T["delivered"], T["handover"]
    done_c = f'IF({T["client_check"]}{{r}}="Delivery",{dl}{{r}},IF(OR({dl}{{r}}="",N({ho}{{r}})=0),"",MAX({dl}{{r}},{ho}{{r}})))'
    done_m = f'IF({ref["commit_on"]}="Handover",IF(OR({dl}{{r}}="",N({ho}{{r}})=0),"",MAX({dl}{{r}},{ho}{{r}})),{dl}{{r}})'

    def ontime(gate: str, due: str, done: str) -> str:
        return (f'=IF(OR(B{{r}}="",{T["type"]}{{r}}="Excluded",{gate}{{r}}<>"Yes",{due}{{r}}="",'
                f'AND({T["delivery_unknown"]}{{r}}="Yes",{dl}{{r}}="")),"",'
                f'IF({done}="",IF({ref["as_of"]}<={due}{{r}},"Pending","No"),IF({done}<={due}{{r}},"Yes","No")))')

    tf["met_client_date"] = ontime(T["client_expected"], T["client_date"], done_c)
    tf["met_commitment"] = ontime(T["team_committed"], T["commit_date"], done_m)
    _fill_row_formulas(tk, TASK_COLS, 4, last_t, tf)
    pick = f"Periods!$B$5:$B$200"
    for key, vals in (("type", ["Task", "CR", "Scope", "Excluded"]),):
        tk.dropdown(4, _n(TASK_COLS, key), last_t, _n(TASK_COLS, key), vals)
    for key in ("planned", "understood", "client_expected", "team_committed", "reopened"):
        tk.dropdown(4, _n(TASK_COLS, key), last_t, _n(TASK_COLS, key), ["Yes", "No"])
    tk.dropdown(4, 2, last_t, 2, source=pick)
    width = len(TASK_COLS)
    tk.when(4, 1, last_t, width, f'=${T["type"]}4="Excluded"', color="8C8C8C")
    for key, bad in (("understood", "No"), ("met_client_date", "No"), ("met_commitment", "No"), ("reopened", "Yes")):
        c = _n(TASK_COLS, key)
        tk.when(4, c, last_t, c, f'={col(c)}4="{bad}"', fill=REDFILL)
    cc = _n(TASK_COLS, "check")
    tk.when(4, cc, last_t, cc, f'={col(cc)}4<>""', fill=AMBER)
    tk.hidden_cols = [_n(TASK_COLS, k) for k in ("handover", "client_check", "item", "delivery_unknown")]
    tk.readback = {"kind": "table", "first": 4, "key": "item", "alt_key": "key", "cols": TASK_COLS}

    # ---- Defect Register ------------------------------------------------------------------
    df = Tab("Defect Register")
    drows = []
    for d in kif.get("defects") or []:
        drows.append({
            "period": d.get("period"), "key": ticket(d),
            "link": {"v": "Open", "link": d["link"], "style": "link"} if d.get("link") else None,
            "title": d.get("title"), "kind": d.get("kind") or "Bug", "reported_by": d.get("reported_by"),
            "reported_on": d.get("reported_on"), "phase": PHASE_OUT.get(d.get("phase"), "Pre-release"),
            "pre_existing": d.get("pre_existing"), "rejected": d.get("rejected"),
            "rejection_reason": d.get("rejection_reason"),
            "evidence": ({"v": "Open", "link": d["evidence"], "style": "link"}
                         if str(d.get("evidence") or "").startswith("http") else plain(d.get("evidence"))),
            "final_status": FINAL_OUT.get(d.get("final_status"), d.get("final_status")),
            "remarks": plain(d.get("remarks")), "check": d.get("check"), "item": d.get("_row") or d.get("_item"),
        })
    last_d = _register(df, f"Defect Register ({len(drows)} rows)",
                       "Every bug, observation or improvement reported by QA or the client, including rejected ones.",
                       DEFECT_COLS, drows)
    counts = (f'=IF(B{{r}}="","",IF(AND({D["rejected"]}{{r}}<>"Yes",OR({D["kind"]}{{r}}="Bug",'
              f'AND({D["kind"]}{{r}}="Observation",{ref["count_obs"]}="Yes"),'
              f'AND({D["kind"]}{{r}}="Improvement",{ref["count_imp"]}="Yes")),'
              f'OR({D["pre_existing"]}{{r}}<>"Yes",{ref["count_pre"]}="Yes"),'
              f'OR({D["phase"]}{{r}}<>"Post-release",{ref["count_post"]}="Yes")),"Yes","No"))')
    _fill_row_formulas(df, DEFECT_COLS, 4, last_d, {"n": '=IF(B{r}="","",ROW()-3)', "counts": counts})
    df.dropdown(4, 2, last_d, 2, source=pick)
    for key, vals in (("kind", ["Bug", "Observation", "Improvement", "Query"]), ("phase", ["Pre-release", "Post-release"]),
                      ("pre_existing", ["Yes", "No"]), ("rejected", ["Yes", "No"]),
                      ("final_status", ["Fixed / Closed", "Rejected", "Deferred (moved out of scope)", "Open"])):
        df.dropdown(4, _n(DEFECT_COLS, key), last_d, _n(DEFECT_COLS, key), vals)
    dw = len(DEFECT_COLS)
    df.when(4, 1, last_d, dw, f'=${D["rejected"]}4="Yes"', color="8C8C8C")
    df.when(4, 1, last_d, dw, f'=${D["phase"]}4="Post-release"', fill=REDFILL)
    dc = _n(DEFECT_COLS, "check")
    df.when(4, dc, last_d, dc, f'={col(dc)}4<>""', fill=AMBER)
    df.hidden_cols = [_n(DEFECT_COLS, "item")]
    df.readback = {"kind": "table", "first": 4, "key": "item", "alt_key": "key", "cols": DEFECT_COLS}

    # ---- KPI Summary ----------------------------------------------------------------------
    sm = Tab("KPI Summary")
    sm.put(1, 1, "KPI Summary", "title")
    sm.put(2, 1, "Grey numbers are formulas over the registers and move when a yellow cell changes. Write the reason in "
                 "the yellow column; the note for PMS is built from both, without links. 'Since the last run' speaks up "
                 "when the sheet no longer matches what was computed - run again before pushing.", "sub")
    heads = [("Period", 14), ("#", 4), ("KPI", 22), ("PMS KPI ID", 9), ("Numerator", 11), ("Denominator", 12),
             ("Value", 10), ("Target", 8), ("Min / Max", 7), ("Status", 16), ("Needs a reason?", 10),
             ("What the numbers say (auto)", 58), ("Why / context (you write)", 70),
             ("Note sent to PMS (auto, no links)", 70), ("Computed by the run", 11), ("Since the last run", 24),
             ("Set value by hand", 10), ("Why set by hand", 30)]
    sm.heights[3] = 31.5
    for i, (h, w) in enumerate(heads, start=1):
        sm.put(3, i, h, "head")
        sm.widths[i] = w
    sm.freeze = (3, 3)
    tP, tTy, tDl, tCl = (_rng("Task Register", T[k], 4) for k in ("period", "type", "delivered", "closed"))
    tUn, tMc, tMm, tRe = (_rng("Task Register", T[k], 4) for k in ("understood", "met_client_date", "met_commitment", "reopened"))
    tHr, tSp = _rng("Task Register", T["hours"], 4), _rng("Task Register", T["story_points"], 4)
    dP, dRj, dPh, dCt = (_rng("Defect Register", D[k], 4) for k in ("period", "rejected", "phase", "counts"))
    live = f'{tP},$A{{r}},{tTy},"<>Excluded"'
    deliv = f'COUNTIFS({live},{tDl},">0")'
    num = {
        "Velocity": f'=IF({ref["velocity_unit"]}="Story Points",SUMIFS({tSp},{live},{tDl},">0"),'
                    f'SUMIFS({tHr},{live},{tDl},">0")+N(IFERROR(INDEX({PM},MATCH($A{{r}},{PN},0)),0)))',
        "Task Comprehension": f'=COUNTIFS({live},{tUn},"Yes")',
        "Client Expectation": f'=COUNTIFS({live},{tMc},"Yes")',
        "Delivery Commitment": f'=COUNTIFS({live},{tMm},"Yes")',
        "Defect Rate": f'=COUNTIFS({dP},$A{{r}},{dCt},"Yes")',
        "Escaped Defect Rate": f'=COUNTIFS({dP},$A{{r}},{dRj},"<>Yes",{dPh},"Post-release")',
        "Defect Rejection Rate": f'=COUNTIFS({dP},$A{{r}},{dRj},"Yes")',
        "Rework Rate": f'=COUNTIFS({live},{tCl},">0",{tRe},"Yes")',
        "CR Rate": f'=COUNTIFS({tP},$A{{r}},{tTy},"CR")',
    }
    den = {
        "Task Comprehension": f'=E{{r}}+COUNTIFS({live},{tUn},"No")',
        "Client Expectation": f'=E{{r}}+COUNTIFS({live},{tMc},"No")',
        "Delivery Commitment": f'=E{{r}}+COUNTIFS({live},{tMm},"No")',
        "Defect Rate": f"={deliv}",
        "Escaped Defect Rate": f'=COUNTIFS({dP},$A{{r}},{dRj},"<>Yes")',
        "Defect Rejection Rate": f"=COUNTIFS({dP},$A{{r}})",
        "Rework Rate": f'=E{{r}}+COUNTIFS({live},{tCl},">0",{tRe},"No")',
        "CR Rate": f'=IF(OR({ref["cr_den"]}="Whole project",COUNTIFS({tP},$A{{r}},{tTy},"Task")=0),'
                   f'COUNTIFS({tTy},"Task"),COUNTIFS({tP},$A{{r}},{tTy},"Task"))',
    }
    ratio = '=IF(Q{r}<>"",Q{r},IF(N(F{r})=0,"",ROUND(E{r}/F{r}*100,2)))'
    val = {n: ratio for n in KPI_ORDER}
    dev_col = _rng("Task Register", T["hours_dev"], 4)
    qa_col = _rng("Task Register", T["hours_qa"], 4)
    missing_points = f'SUMPRODUCT(({tP}=$A{{r}})*({tTy}<>"Excluded")*({tDl}>0)*(LEN({tSp})=0))'
    missing_hours = (f'SUMPRODUCT(({tP}=$A{{r}})*({tTy}<>"Excluded")*({tDl}>0)*(LEN({dev_col})=0))+'
                     f'IF({ref["hours_basis"]}="Dev + QA",SUMPRODUCT(({tP}=$A{{r}})*({tTy}<>"Excluded")*'
                     f'({tDl}>0)*({tCl}>0)*(LEN({qa_col})=0)),0)')
    val["Velocity"] = (f'=IF(Q{{r}}<>"",Q{{r}},IF(OR({deliv}=0,IF({ref["velocity_unit"]}="Story Points",'
                       f'{missing_points},{missing_hours})>0),"",ROUND(E{{r}},2)))')
    val["Escaped Defect Rate"] = (f'=IF(Q{{r}}<>"",Q{{r}},IF(OR(N(F{{r}})=0,N(IFERROR(INDEX({PH},MATCH($A{{r}},{PN},0)),0))=0),'
                                  f'"",ROUND(E{{r}}/F{{r}}*100,2)))')
    reasons, manual = ctx.get("reasons") or {}, ctx.get("manual") or {}
    r = 3
    summary_rows = []
    for perres in results.get("periods") or []:
        for m in sorted(perres.get("measures") or [], key=lambda x: display_order.index(x["name"]) if x["name"] in display_order else 99):
            r += 1
            name, pn = m["name"], perres["period"]
            sm.heights[r] = 45
            sm.put(r, 1, pn, "data")
            sm.put(r, 2, display_order.index(name) + 1 if name in display_order else None, "calc_c")
            sm.put(r, 3, name, "kpi")
            sm.put(r, 4, None, "calc_c", f=f'=IFERROR(INDEX({ref["kpi_ids"]},MATCH($C{r},{ref["kpi_names"]},0)),"")')
            sm.put(r, 5, None, "calc_r", f=num.get(metric_name(name), "").format(r=r) or None)
            sm.put(r, 6, None, "calc_r", f=(den.get(metric_name(name)) or "").format(r=r) or None)
            sm.put(r, 7, None, "calc_r", f=val.get(metric_name(name), ratio).format(r=r))
            sm.put(r, 8, None, "calc_r", f=f'=IFERROR(INDEX({ref["kpi_targets"]},MATCH($C{r},{ref["kpi_names"]},0)),"")')
            sm.put(r, 9, None, "calc_c", f=f'=IFERROR(INDEX({ref["kpi_types"]},MATCH($C{r},{ref["kpi_names"]},0)),"")')
            sm.put(r, 10, None, "calc_c", f=f'=IF(G{r}="","Not measured",IF(H{r}="","Measured",IF(I{r}="Min",'
                                            f'IF(G{r}>=H{r},"Met","Below minimum"),IF(G{r}<=H{r},"Met","Above maximum"))))')
            sm.put(r, 11, None, "calc_c", f=f'=IF(OR(J{r}="Below minimum",J{r}="Above maximum"),"Yes","No")')
            auto = " || ".join(x for x in (m.get("note_parts") or []) if x and x.strip())
            note_text = auto + " " + plain((reasons.get(pn) or {}).get(name))
            sm.heights[r] = max(45, min(250, 15 * (len(note_text) // 65 + 2)))
            sm.put(r, 12, auto, "calc")
            man = (manual.get(pn) or {}).get(name) or {}
            sm.put(r, 13, plain((reasons.get(pn) or {}).get(name)), "in")
            sm.put(r, 14, None, "calc", f=f'=L{r}&IF(TRIM(M{r})="",""," || "&TRIM(M{r}))')
            shown = m.get("value")
            sm.put(r, 15, shown, "calc_r")
            sm.put(r, 16, None, "calc", f=f'=IF(AND(G{r}="",O{r}=""),"",IF(AND(ISNUMBER(G{r}),ISNUMBER(O{r})),'
                                          f'IF(ABS(G{r}-O{r})<0.006,"","Sheet says "&G{r}&", the run computed "&O{r}&". Run again before pushing."),'
                                          f'"Changed in the sheet since the run. Run again before pushing."))')
            sm.put(r, 17, man.get("value") if isinstance(man, dict) else None, "in")
            sm.put(r, 18, man.get("why") if isinstance(man, dict) else None, "in")
            summary_rows.append((pn, name, r))
    last_s = max(r, 4)
    sm.when(4, 10, last_s, 10, '=J4="Met"', fill="C6EFCE", color="006100")
    sm.when(4, 10, last_s, 10, '=OR(J4="Below minimum",J4="Above maximum")', fill="FFC7CE", color="9C0006")
    sm.when(4, 13, last_s, 13, '=AND(K4="Yes",M4="")', fill="FFC7CE")
    sm.when(4, 16, last_s, 16, '=P4<>""', fill=AMBER)
    sm.readback = {"kind": "summary", "first": 4, "last": last_s, "period": 1, "kpi": 3, "why": 13,
                   "manual_value": 17, "manual_why": 18}

    # ---- Dashboard ------------------------------------------------------------------------
    db = Tab("Dashboard")
    db.widths.update({1: 4, 2: 22, 3: 12, 4: 14, 5: 12, 6: 12, 7: 12, 8: 12, 9: 12, 10: 10, 11: 12, 12: 10,
                      13: 12, 14: 12, 15: 12, 16: 3, 17: 22, 18: 22})
    db.put(1, 1, None, "title", f=f'="KPI Dashboard: "&{ref["project_name"]}')
    db.put(2, 1, None, "sub", f=f'="PMS project "&{ref["pms_id"]}&"  ·  Velocity in "&{ref["velocity_unit"]}&"  ·  '
                                f'Data pulled {(ctx.get("refreshed") or "")[:10]}  ·  Everything here is calculated from the other tabs."')
    db.band(4, "Work and issues by period", 1, 18)
    hd = ["#", "Period", "Delivered", "Not delivered yet", "Planned tasks", "Additional requests", "Completed",
          "Issues reported", "Bugs counted", "Rejected", "Found after handover", "Reopened", "Client date",
          "Commit date", "Handed over", None, "Delivered (green) vs not yet (grey)", "Bugs (red) vs other issues (orange)"]
    db.heights[5] = 31.5
    for i, h in enumerate(hd, start=1):
        if h:
            db.put(5, i, h, "head")
    tPl = _rng("Task Register", T["planned"], 4)
    top, bot = 6, 6 + MAX_PERIODS - 1
    for rr in range(top, bot + 1):
        b = f"$B{rr}"
        t_live = f'{tP},{b},{tTy},"<>Excluded"'
        db.put(rr, 1, None, "calc_c", f=f'=IF({b}="","",ROW()-5)')
        db.put(rr, 2, None, "kpi", f=f'=IFERROR(INDEX(Periods!$B$5:$B$200,ROW()-5)&"","")')
        cells = [
            f'COUNTIFS({t_live},{tDl},">0")', f'COUNTIFS({t_live})-COUNTIFS({t_live},{tDl},">0")',
            f'COUNTIFS({t_live},{tPl},"Yes")',
            f'COUNTIFS({tP},{b},{tTy},"CR")',
            f'ROUND(SUMIFS(\'KPI Summary\'!$E$4:$E${LAST},\'KPI Summary\'!$A$4:$A${LAST},{b},\'KPI Summary\'!$C$4:$C${LAST},"Velocity"),2)'
            f'&IF({ref["velocity_unit"]}="Story Points"," pts"," h")',
            f"COUNTIFS({dP},{b})", f'COUNTIFS({dP},{b},{dCt},"Yes")', f'COUNTIFS({dP},{b},{dRj},"Yes")',
            f'COUNTIFS({dP},{b},{dPh},"Post-release",{dRj},"<>Yes")', f'COUNTIFS({t_live},{tCl},">0",{tRe},"Yes")',
        ]
        for i, fx in enumerate(cells, start=3):
            db.put(rr, i, None, "calc_r", f=f'=IF({b}="","",{fx})')
        for i, (rng, fallback) in enumerate(((f"Periods!${P['client_date']}$5:${P['client_date']}$200", ref["client_date"]),
                                             (f"Periods!${P['commit_date']}$5:${P['commit_date']}$200", ref["commit_date"])), start=13):
            look = f'IFERROR(INDEX({rng},MATCH({b},{PN},0)),"")'
            db.put(rr, i, None, "calc_c", f=f'=IF({b}="","",IF(N({look})>0,TEXT({look},"mm/dd/yyyy"),'
                                            f'IF(N({fallback})>0,TEXT({fallback},"mm/dd/yyyy"),"-")))')
        look = f'IFERROR(INDEX({PH},MATCH({b},{PN},0)),"")'
        db.put(rr, 15, None, "calc_c", f=f'=IF({b}="","",IF(N({look})>0,TEXT({look},"mm/dd/yyyy"),"Not yet"))')
        mx1 = f"MAX(1,$C${top}:$C${bot},$D${top}:$D${bot})"
        db.put(rr, 17, None, "bar", f=f'=IF({b}="","",REPT("█",ROUND(N(C{rr})/{mx1}*18,0))&REPT("░",ROUND(N(D{rr})/{mx1}*18,0)))',
               gf=f'=IF({b}="","",SPARKLINE({{N(C{rr}),N(D{rr})}},{{"charttype","bar";"color1","#38761d";"color2","#b7b7b7";'
                  f'"max",MAX(1,ARRAYFORMULA($C${top}:$C${bot}+$D${top}:$D${bot}))}}))')
        mx2 = f"MAX(1,$H${top}:$H${bot})"
        db.put(rr, 18, None, "bar", f=f'=IF({b}="","",REPT("█",ROUND(N(I{rr})/{mx2}*18,0))&REPT("░",ROUND((N(H{rr})-N(I{rr}))/{mx2}*18,0)))',
               gf=f'=IF({b}="","",SPARKLINE({{N(I{rr}),N(H{rr})-N(I{rr})}},{{"charttype","bar";"color1","#cc0000";"color2","#f6b26b";'
                  f'"max",MAX(1,$H${top}:$H${bot})}}))')
    tr = bot + 1
    db.put(tr, 2, "Total", "total")
    for i in (3, 4, 5, 6, 8, 9, 10, 11, 12):
        db.put(tr, i, None, "total", f=f"=SUM({col(i)}{top}:{col(i)}{bot})")

    k0 = tr + 2
    db.band(k0, "KPI results by period (the bar is green when the KPI is met, red when not)", 1, 18)
    db.heights[k0 + 1] = 31.5
    db.put(k0 + 1, 2, "KPI", "head")
    db.put(k0 + 1, 3, "Target", "head")
    slots = [(4 + 2 * i, 5 + 2 * i) for i in range(6)]
    for i, (vc, bc) in enumerate(slots):
        db.put(k0 + 1, vc, None, "head", f=f'=IF($B${top + i}="","",$B${top + i})')
        db.put(k0 + 1, bc, None, "head")
    S = "'KPI Summary'!"
    sA, sC, sG, sJ = (f"{S}${x}$4:${x}${LAST}" for x in "ACGJ")
    for j, name in enumerate(display_order):
        rr = k0 + 2 + j
        db.put(rr, 2, name, "kpi")
        db.put(rr, 3, None, "calc", f=f'=IFERROR(IF(INDEX({ref["kpi_types"]},MATCH($B{rr},{ref["kpi_names"]},0))="Min","at least ","at most ")'
                                      f'&INDEX({ref["kpi_targets"]},MATCH($B{rr},{ref["kpi_names"]},0))&IF($B{rr}="Velocity",""," %"),"")')
        vals = ",".join(f"N({col(vc)}{rr})" for vc, _ in slots)
        for vc, bc in slots:
            hdr = f"{col(vc)}${k0 + 1}"
            has = f'COUNTIFS({sA},{hdr},{sC},$B{rr},{sG},">=0")'
            db.put(rr, vc, None, "calc_r", f=f'=IF({hdr}="","",IF({has}=0,"not measured",SUMIFS({sG},{sA},{hdr},{sC},$B{rr})))')
            met = f'COUNTIFS({sA},{hdr},{sC},$B{rr},{sJ},"Met")>0'
            top_of = f'IF($B{rr}="Velocity",MAX(1,{vals}),100)'
            v = f"{col(vc)}{rr}"
            db.put(rr, bc, None, "bar", f=f'=IF(ISNUMBER({v}),REPT("█",ROUND(MIN({v},{top_of})/{top_of}*14,0)),"")',
                   gf=f'=IF(ISNUMBER({v}),SPARKLINE({v},{{"charttype","bar";"max",{top_of};"color1",IF({met},"#38761d","#cc0000")}}),"")')
            # Google Sheets refuses a conditional format that looks at another tab, so the
            # met/not-met flag sits in a hidden helper column on this one.
            flag = 20 + slots.index((vc, bc))
            db.put(rr, flag, None, "calc", f=f'=IF(ISNUMBER({v}),IF({met},1,0),"")')
            db.when(rr, bc, rr, bc, f"=${col(flag)}{rr}=0", color="CC0000")
    s0 = k0 + 2 + len(KPI_ORDER) + 1
    db.band(s0, "Status across all periods", 1, 18)
    sK, sM = f"{S}$K$4:$K${LAST}", f"{S}$M$4:$M${LAST}"
    for rr, c1, label, fx in (
            (s0 + 1, 2, "Met", f'=COUNTIF({sJ},"Met")'),
            (s0 + 1, 4, "Not met", f'=COUNTIF({sJ},"Below minimum")+COUNTIF({sJ},"Above maximum")'),
            (s0 + 2, 2, "Not measured yet", f'=COUNTIF({sJ},"Not measured")'),
            (s0 + 2, 4, "Reasons still missing", f'=SUMPRODUCT(({sK}="Yes")*(LEN({sM})=0))'),
            (s0 + 3, 2, "Rows waiting for a check", f"=COUNTIF({_rng('Task Register', T['check'], 4)},\"?*\")+COUNTIF({_rng('Defect Register', D['check'], 4)},\"?*\")"),
            (s0 + 3, 4, "Open questions", f"=SUMPRODUCT((LEN('Open Questions'!$B$4:$B${LAST})>0)*(LEN('Open Questions'!$E$4:$E${LAST})=0))")):
        db.put(rr, c1, label, "kpi")
        db.put(rr, c1 + 1, None, "calc_r", f=fx)
    db.hidden_cols = list(range(20, 26))
    ch = ctx.get("changes") or []
    c0 = s0 + 5
    db.band(c0, "What moved since the last run" + ("" if ch else ": nothing"), 1, 18)
    for i, line in enumerate(ch[:12]):
        db.put(c0 + 1 + i, 2, line, "text")

    # ---- Open Questions -----------------------------------------------------------------------
    oq = Tab("Open Questions", "BF9000")
    oq.put(1, 2, "Open Questions", "title")
    oq.put(2, 2, "What the sources on file could not answer. Type the answer in the yellow cell; the next run reads it, "
                 "keeps it, and stops asking. Nothing here was guessed - an unanswered row is left out of the numbers.", "sub")
    for i, (h, w) in enumerate([("#", 4), ("About", 26), ("Question", 70), ("If nobody answers", 40),
                                ("Your answer", 40), ("Asked on", 12), ("ID", 18)], start=1):
        oq.put(3, i, h, "head")
        oq.widths[i] = w
    oq.freeze = (3, 0)
    qs = ctx.get("questions") or []
    for i in range(max(len(qs), 1) + 12):
        rr, q = 4 + i, (qs[i] if i < len(qs) else {})
        oq.put(rr, 1, None, "calc_c", f=f'=IF(B{rr}="","",ROW()-3)')
        for c, key, style in ((2, "about", "data"), (3, "question", "data"), (4, "proposal", "data"),
                              (5, "answer", "in"), (6, "asked_on", "data"), (7, "id", "calc")):
            oq.put(rr, c, q.get(key), style)
    oq.hidden_cols = [7]
    oq.readback = {"kind": "questions", "first": 4, "id": 7, "answer": 5}

    # ---- Run Log ------------------------------------------------------------------------------
    rl = Tab("Run Log", "7F7F7F")
    rl.put(1, 2, "Run Log", "title")
    rl.put(2, 2, "What this run read, what it deliberately did not, and how long it took. A run reads the sources on this "
                 "list and nothing else; anything they could not answer is on the Open Questions tab.", "sub")
    for i, (h, w) in enumerate([("#", 4), ("Source", 22), ("State", 14), ("As of", 22), ("Note", 80)], start=1):
        rl.put(3, i, h, "head")
        rl.widths[i] = w
    rr = 3
    for s in ctx.get("sources") or []:
        rr += 1
        rl.row(rr, [rr - 3, s.get("role"), s.get("state"), s.get("as_of"), s.get("note")], "data")
    rr += 2
    rl.band(rr, "This run", 2, 5, "soft")
    for label, value in ctx.get("run_facts") or []:
        rr += 1
        rl.put(rr, 2, label, "label")
        rl.put(rr, 3, value, "data")

    # ---- PMS Push Log -----------------------------------------------------------------------------
    pl = Tab("PMS Push Log", "7F7F7F")
    pl.put(1, 2, "PMS Push Log", "title")
    pl.put(2, 2, "One line each time values are sent to PMS. Added by the push.", "sub")
    pl.heights[3] = 31.5
    for i, (h, w) in enumerate([("#", 4), ("Pushed On", 18), ("Period", 16), ("PMS Period ID", 13), ("Action", 12),
                                ("What changed", 80), ("Note or pushed by", 20), ("Result", 30)], start=1):
        pl.put(3, i, h, "head")
        pl.widths[i] = w
    log = ctx.get("push_log") or []
    for i in range(len(log) + 20):
        rr, e = 4 + i, (log[i] if i < len(log) else {})
        pl.put(rr, 1, None, "calc_c", f=f'=IF(B{rr}="","",ROW()-3)')
        for c, key in enumerate(("at", "period", "pms_period_id", "action", "changed", "by", "result"), start=2):
            pl.put(rr, c, e.get(key), "data")

    # ---- Read Me ------------------------------------------------------------------------------------
    rm = Tab("Read Me")
    rm.widths.update({1: 3, 2: 120})
    rm.put(1, 2, "KPI Tracker: how this sheet works", "title")
    rm.put(2, 2, f"Built and refreshed by KPI Copilot {ctx.get('tool_version') or ''}. Every run updates this same sheet; "
                 f"what you typed in yellow cells is read back first and kept.".replace("  ", " "), "sub")
    rr = 3
    for kind, text in README:
        rr += 1
        if kind == "h":
            rm.put(rr, 2, text, "band")
        elif text:
            rm.put(rr, 2, text, "text")

    return [rm, db, cfg, per, tk, df, sm, oq, rl, pl]


def _n(cols: list[tuple], key: str) -> int:
    return next(i for i, c in enumerate(cols, start=1) if c[0] == key)


def _fill_row_formulas(tab: Tab, cols: list[tuple], first: int, last: int, formulas: dict[str, str] | None = None) -> None:
    formulas = formulas or {}
    for r in range(first, last + 1):
        for i, (key, *_rest) in enumerate(cols, start=1):
            cell = tab.cells.get((r, i)) or {}
            fx = formulas.get(key) or (cell.get("f") if "{r}" in str(cell.get("f") or "") else None)
            if fx:
                cell = dict(cell, f=fx.format(r=r))
                cell.pop("v", None)
                tab.cells[(r, i)] = cell


HOW_COUNTED = {
    "Velocity": "Hours (or story points) of Task Register rows that are not Excluded and have a Delivered date, plus the period's team-level effort.",
    "Task Comprehension": "Rows with Understood = Yes ÷ rows with Understood = Yes or No. A row with no answer is left out.",
    "Client Expectation": "Client-expected rows that met their date ÷ client-expected rows that are due. Pending rows wait.",
    "Delivery Commitment": "Rows the team committed to that met the date ÷ committed rows that are due. Uncommitted rows are left out.",
    "Defect Rate": "Defect Register rows with Counts in Defect Rate = Yes ÷ delivered Task Register rows.",
    "Escaped Defect Rate": "Post-release reports that were not rejected ÷ all reports that were not rejected. Blank until the period is handed over.",
    "Defect Rejection Rate": "Defect Register rows with Rejected = Yes ÷ all Defect Register rows.",
    "Rework Rate": "Closed rows with Reopened = Yes ÷ closed rows with Reopened = Yes or No.",
    "CR Rate": "Rows with Item Type = CR ÷ rows with Item Type = Task (the whole project's, when the period has none).",
}

README = [
    ("h", "Tabs"),
    ("", "Dashboard: totals per period and KPI results with coloured bars. Nothing to type here."),
    ("", "Config: project details, counting rules, KPI targets, and the project dates used when a period or task has none."),
    ("", "Periods: one row per KPI period with its dates, notes and PMS period ID."),
    ("", "Task Register: every planned task and additional request, with the evidence behind each Yes/No."),
    ("", "Defect Register: every bug, observation or improvement, including rejected ones."),
    ("", "KPI Summary: the nine PMS KPIs per period, the facts behind each number, your reason, and the note that goes to PMS."),
    ("", "Open Questions: what the sources could not answer. Answer in the yellow cell; the next run keeps it."),
    ("", "Run Log: which sources this run read, which it did not, and how long it took."),
    ("", "PMS Push Log: what was sent to PMS and when."),
    ("", ""),
    ("h", "How to read and change it"),
    ("", "Yellow cells are yours: change one and every formula follows at once. The next run reads your change back and keeps it - it is never overwritten."),
    ("", "White cells were read from the tracker, the plan or the estimates. Grey cells are worked out. Editing either achieves nothing; the next run rebuilds them."),
    ("", "The Check column says how a row was decided when it was not obvious: a tag read tolerantly ('read [Exisiting] as Existing'), a loose match to the plan, a call an assistant made and why. Disagree by changing the yellow cell."),
    ("", "Dates: a date on the task wins, then the period date, then the project date in Config. Leave a cell empty to use the next level."),
    ("", "Client date check (Periods or Config): Handover = the build reached the client by the date; Delivery = the item was delivered by the date."),
    ("", "'Since the last run' on KPI Summary speaks up when the sheet's live number no longer matches what the run computed. Run again before anything goes to PMS: PMS always receives what the run computed, never what was typed."),
    ("", "To set a KPI value by hand, use 'Set value by hand' with a reason. Both figures are kept and the note says a person recorded a different one."),
    ("", ""),
    ("h", "Note format sent to PMS"),
    ("", "What the numbers say, in sentences || what was left out || why (your reason). Links never go to PMS; they live here, on the rows."),
    ("", ""),
    ("h", "Period names"),
    ("", "Initial Scope, Additional Requests 1, 2 ..., Milestone 1, 2 ..., Full Project (25 characters at most)."),
]
