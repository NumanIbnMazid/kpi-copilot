#!/usr/bin/env python3
"""
The KPI Profile Workbook, and the per-project tracker workbook.

The profile workbook is the human face of profile.yaml: one tab per section, one row per
setting, and every row carrying a plain-language description of what it is for. It is
generated from schemas/profile.schema.json and read back into the same YAML, so the thing a
person edits and the thing the tools read can never drift apart.

Why bother, when the YAML already exists: because the person who needs to know which chat
space matters, or where the plan lives, is usually not the person who wrote the YAML. The
Tools tab is the one people actually open - it is a map of the project's truth.

Commands:
    workbook.py build   --profile profile.yaml --out "KPI Profile Workbook.xlsx"
    workbook.py read    --xlsx "KPI Profile Workbook.xlsx" --out profile.yaml
    workbook.py tracker --results results.json --kif run.kif.json --out tracker.xlsx
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent
SCHEMA = PLUGIN_ROOT / "schemas" / "profile.schema.json"

sys.path.insert(0, str(HERE))
from profile_lib import describe_overrides, unflatten  # noqa: E402

try:
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
except ImportError:  # pragma: no cover
    print("openpyxl is needed for the workbook. Run: pip3 install openpyxl", file=sys.stderr)
    raise SystemExit(2)

# One look everywhere, so every team's workbook is recognisable as the same thing.
HEAD = PatternFill("solid", fgColor="1F3864")
HEAD_FONT = Font(color="FFFFFF", bold=True, size=11)
INPUT = PatternFill("solid", fgColor="FFF2CC")   # yellow = you edit this
LOCKED = PatternFill("solid", fgColor="EDEDED")  # grey  = do not edit
TITLE_FONT = Font(bold=True, size=14, color="1F3864")
HINT_FONT = Font(italic=True, size=9, color="666666")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(vertical="top", wrap_text=True)


def _load_any(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        import yaml  # type: ignore
        return yaml.safe_load(text)
    return json.loads(text)


def _dump_yaml(data: Any, path: Path) -> None:
    import yaml  # type: ignore
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8"
    )


def _flatten(value: Any) -> str:
    """Lists become one-per-line so a person can edit them without learning YAML."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return "\n".join(_flatten(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _unflatten(text: str, spec: dict) -> Any:
    """The inverse, guided by the schema so 'Yes' becomes True only where a boolean belongs."""
    text = (text or "").strip()
    # A schema type can be a list ("integer" or null), so normalise before matching -
    # otherwise a PMS project id comes back as the string "361" and every later comparison
    # against PMS quietly fails.
    t = spec.get("type")
    types = set(t) if isinstance(t, list) else {t}
    if "boolean" in types:
        # An empty cell means "not set", not False. Otherwise every optional flag comes back
        # explicitly false and the round trip reports differences that are not differences.
        if not text:
            return None
        return text.lower() in ("yes", "true", "1", "on")
    if "array" in types:
        return [line.strip() for line in text.splitlines() if line.strip()] if text else []
    if "integer" in types and text:
        try:
            return int(float(text))
        except ValueError:
            return None
    if "number" in types and text:
        try:
            return float(text)
        except ValueError:
            return None
    if "object" in types and text:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}
    return text or None


def _enum_of(spec: dict) -> list[str] | None:
    if "enum" in spec:
        return [str(v) for v in spec["enum"] if v is not None]
    if spec.get("type") == "boolean":
        return ["Yes", "No"]
    return None


# --------------------------------------------------------------------------------------
# build: schema + profile -> xlsx
# --------------------------------------------------------------------------------------


def _style_header(ws, row: int, headers: list[str], widths: list[int]) -> None:
    for i, (h, w) in enumerate(zip(headers, widths), start=1):
        c = ws.cell(row=row, column=i, value=h)
        c.fill, c.font, c.border, c.alignment = HEAD, HEAD_FONT, BORDER, WRAP
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = ws.cell(row=row + 1, column=1)


def build(profile_path: Path | None, out: Path) -> None:
    schema = _load_any(SCHEMA)
    profile = _load_any(profile_path) if profile_path and profile_path.exists() else {}
    wb = Workbook()
    wb.remove(wb.active)

    # --- Read Me -------------------------------------------------------------------
    ws = wb.create_sheet("Read Me")
    ws.column_dimensions["A"].width = 110
    lines = [
        ("KPI Profile Workbook", "title"),
        ("", ""),
        ("This workbook is the configuration for KPI Copilot. It is the same information as profile.yaml, "
         "shown so a person can read it. Edit either one; the tools convert between them.", ""),
        ("", ""),
        ("Yellow cells are yours to change. Grey cells are not edited here: they are read from PMS or fixed "
         "for the company. Targets are the common case - a threshold is configurable per project in PMS, so if "
         "yours needs a different bar, set it there and the next run reads it. What does not vary is the "
         "counting behind each number, because that is what lets two projects be compared at all.", ""),
        ("", ""),
        ("Tabs", "h"),
        ("Owner - who this profile belongs to.", ""),
        ("Organization - PMS, the KPI set and the note format. Targets live in PMS, per project.", ""),
        ("Tools - where everything lives. The tab people actually use: tracker, chat spaces, plan, sheets.", ""),
        ("Tracker - which adapter reads your board, and the fields it should look at.", ""),
        ("Conventions - how your team names tickets, defects and the things that are not deliverables.", ""),
        ("Workflow - what your states mean. The most important tab: it turns 'a column called In Test' into "
         "a number management can compare across projects.", ""),
        ("Sources - where the plan, the estimates and the timeline live. All optional.", ""),
        ("Periods - how you slice a project for PMS.", ""),
        ("Counting Rules - the few counting choices a team is allowed to make.", ""),
        ("Custom Instructions - your house style, always/never rules, glossary and rule overrides.", ""),
        ("Output - what the run produces, and how far it may go on its own.", ""),
        ("Accounts - your client accounts. Most of what varies between two projects actually varies "
         "between two clients, so say it once here.", ""),
        ("Projects - one row per PMS project. A project inherits its account and only says what differs.", ""),
        ("Overrides - every way an account or project departs from the defaults, on one page.", ""),
        ("Prerequisites - the readiness checklist, refreshed by scripts/preflight.py.", ""),
        ("", ""),
        ("After editing", "h"),
        ("python3 scripts/workbook.py read --xlsx \"KPI Profile Workbook.xlsx\" --out profile.yaml", "code"),
        ("python3 scripts/preflight.py --profile profile.yaml", "code"),
    ]
    r = 1
    for text, kind in lines:
        c = ws.cell(row=r, column=1, value=text)
        c.alignment = WRAP
        if kind == "title":
            c.font = TITLE_FONT
        elif kind == "h":
            c.font = Font(bold=True, size=11, color="1F3864")
        elif kind == "code":
            c.font = Font(name="Menlo", size=9)
            c.fill = LOCKED
        r += 1

    # --- one tab per schema section -------------------------------------------------
    for key, spec in schema.get("properties", {}).items():
        xw = spec.get("x-workbook") or {}
        tab = xw.get("tab")
        if not tab:
            continue
        ws = wb.create_sheet(tab[:31])
        ws.cell(row=1, column=1, value=xw.get("title", tab)).font = TITLE_FONT
        if xw.get("readonly_hint"):
            c = ws.cell(row=2, column=1, value=xw["readonly_hint"])
            c.font = HINT_FONT
            c.alignment = WRAP

        if xw.get("as_table"):
            _build_table_tab(ws, key, spec, xw, profile.get(key) or [])
        else:
            _build_settings_tab(ws, key, spec, profile.get(key) or {})

    # --- Overrides -------------------------------------------------------------------
    # Flattened so a person can see, on one page, every way a project or account departs
    # from the defaults. Two projects that drifted apart for a reason nobody remembers show
    # up here and nowhere else.
    over_rows = describe_overrides(profile)
    ws = wb.create_sheet("Overrides")
    ws.cell(row=1, column=1, value="What each account and project changes").font = TITLE_FONT
    c = ws.cell(row=2, column=1,
                value="The top level of this workbook is your default way of working. An account says what is "
                      "true for every project on that client; a project says what is true for just itself. "
                      "Most rows here belong on an account - if the same override appears on several projects, "
                      "move it up.")
    c.font, c.alignment = HINT_FONT, WRAP
    ws.row_dimensions[2].height = 42
    _style_header(ws, 4, ["#", "Scope", "Account / project", "Setting", "Value"],
                  [5, 12, 24, 40, 70])
    for i, row in enumerate(over_rows, start=1):
        for ci, v in enumerate([i, row["scope"], row["id"], row["setting"], row["value"]], start=1):
            cell = ws.cell(row=4 + i, column=ci, value=v)
            cell.border, cell.alignment = BORDER, WRAP
            if ci == 5:
                cell.fill = INPUT
    if not over_rows:
        ws.cell(row=5, column=2,
                value="None. Every project uses the defaults above.").font = HINT_FONT
    ws.cell(row=3, column=9, value="_overrides").font = Font(size=8, color="FFFFFF")

    # --- Prerequisites --------------------------------------------------------------
    ws = wb.create_sheet("Prerequisites")
    ws.cell(row=1, column=1, value="Readiness checklist").font = TITLE_FONT
    c = ws.cell(row=2, column=1,
                value="Refreshed by: python3 scripts/preflight.py --profile profile.yaml. "
                      "Do not edit by hand - confirmations are recorded with the command, so they carry a date.")
    c.font, c.alignment = HINT_FONT, WRAP
    _style_header(ws, 4, ["#", "Group", "Check", "State", "Why it matters", "How to fix", "Who owns it", "Checked"],
                  [5, 16, 42, 14, 50, 50, 14, 20])
    state = _read_preflight(profile_path)
    for i, chk in enumerate(state, start=1):
        row = 4 + i
        vals = [i, chk.get("group"), chk.get("label"),
                {"pass": "Ready", "fail": "Blocked", "manual": "Confirm", "warn": "Limited", "skip": "N/A"}
                .get(chk.get("state"), chk.get("state")),
                chk.get("why"), chk.get("fix"), chk.get("owner"), (chk.get("checked_at") or "")[:10]]
        for ci, v in enumerate(vals, start=1):
            cell = ws.cell(row=row, column=ci, value=v)
            cell.border, cell.alignment = BORDER, WRAP
            if ci == 4:
                cell.fill = {"Ready": PatternFill("solid", fgColor="D9EAD3"),
                             "Blocked": PatternFill("solid", fgColor="F4CCCC"),
                             "Limited": PatternFill("solid", fgColor="FFF2CC"),
                             "Confirm": PatternFill("solid", fgColor="FFF2CC")}.get(v, LOCKED)
    if not state:
        ws.cell(row=5, column=3, value="Not run yet. Run preflight.py and rebuild this workbook.").font = HINT_FONT

    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    print(f"Wrote {out}")


def _read_preflight(profile_path: Path | None) -> list[dict]:
    if not profile_path:
        return []
    p = profile_path.parent / "preflight.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("checks", [])
    except Exception:  # noqa: BLE001
        return []


def _build_settings_tab(ws, section: str, spec: dict, values: dict) -> None:
    _style_header(ws, 4, ["Setting", "Value", "What it means", "Allowed"], [34, 42, 62, 26])
    row = 5
    deferred_tables: list[tuple[str, dict]] = []
    for prop, pspec in (spec.get("properties") or {}).items():
        pxw = pspec.get("x-workbook") or {}
        label = pxw.get("label", prop.replace("_", " ").capitalize())
        meaning = pxw.get("hint") or pspec.get("description", "")
        if pspec.get("type") == "array" and (pxw.get("as_table") or (pspec.get("items") or {}).get("properties")):
            # An array of objects inside a settings tab (rule overrides) gets its own small
            # table under the settings, rather than one unreadable JSON cell.
            deferred_tables.append((prop, pspec))
            continue
        if pspec.get("type") == "object" and pspec.get("properties"):
            # A nested block (delivered_when, plan, ...) gets one row per leaf so nobody has
            # to hand-write JSON in a spreadsheet cell.
            ws.cell(row=row, column=1, value=label).font = Font(bold=True, size=11)
            ws.cell(row=row, column=3, value=meaning).alignment = WRAP
            ws.cell(row=row, column=3).font = HINT_FONT
            row += 1
            for sub, sspec in pspec["properties"].items():
                sval = (values.get(prop) or {}).get(sub)
                row = _write_setting(ws, row, f"{prop}.{sub}", f"    {sub.replace('_', ' ')}",
                                     sval, sspec, sspec.get("description", ""))
            continue
        row = _write_setting(ws, row, prop, label, values.get(prop), pspec, meaning)

    for prop, pspec in deferred_tables:
        pxw = pspec.get("x-workbook") or {}
        cols = pxw.get("columns") or list(((pspec.get("items") or {}).get("properties") or {}).keys())
        item_props = ((pspec.get("items") or {}).get("properties")) or {}
        row += 2
        t = ws.cell(row=row, column=1, value=prop.replace("_", " ").title())
        t.font = Font(bold=True, size=12, color="1F3864")
        row += 1
        d = ws.cell(row=row, column=1, value=pspec.get("description", ""))
        d.font, d.alignment = HINT_FONT, WRAP
        ws.row_dimensions[row].height = 46
        row += 1
        for ci, c in enumerate(cols, start=1):
            h = ws.cell(row=row, column=ci, value=c.replace("_", " ").title())
            h.fill, h.font, h.border, h.alignment = HEAD, HEAD_FONT, BORDER, WRAP
        marker = ws.cell(row=row, column=9, value=f"_subtable:{prop}:{','.join(cols)}")
        marker.font = Font(size=8, color="CCCCCC")
        row += 1
        for ci, c in enumerate(cols, start=1):
            m = ws.cell(row=row, column=ci, value=(item_props.get(c) or {}).get("description", ""))
            m.font, m.alignment, m.border = HINT_FONT, WRAP, BORDER
        ws.row_dimensions[row].height = 40
        row += 1
        existing = values.get(prop) or []
        for item in list(existing) + [{}] * 6:
            for ci, c in enumerate(cols, start=1):
                cell = ws.cell(row=row, column=ci, value=_flatten(item.get(c)))
                cell.fill, cell.border, cell.alignment = INPUT, BORDER, WRAP
            ws.row_dimensions[row].height = 28
            row += 1


def _write_setting(ws, row: int, key: str, label: str, value: Any, spec: dict, meaning: str) -> int:
    ws.cell(row=row, column=1, value=label).alignment = WRAP
    ws.cell(row=row, column=1).border = BORDER
    v = ws.cell(row=row, column=2, value=_flatten(value if value is not None else spec.get("default")))
    v.fill, v.border, v.alignment = INPUT, BORDER, WRAP
    m = ws.cell(row=row, column=3, value=meaning)
    m.border, m.alignment, m.font = BORDER, WRAP, Font(size=9, color="444444")
    enum = _enum_of(spec)
    a = ws.cell(row=row, column=4, value=" | ".join(enum) if enum else "")
    a.border, a.alignment, a.font = BORDER, WRAP, HINT_FONT
    if enum and len(" ".join(enum)) < 240:
        dv = DataValidation(type="list", formula1='"' + ",".join(enum) + '"', allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(v)
    # The machine key, kept so 'read' can find its way back without guessing from the label.
    k = ws.cell(row=row, column=9, value=key)
    k.font = Font(size=8, color="CCCCCC")
    ws.column_dimensions["I"].hidden = True
    ws.row_dimensions[row].height = 30
    return row + 1


def _build_table_tab(ws, section: str, spec: dict, xw: dict, rows: list[dict]) -> None:
    cols = xw.get("columns") or []
    item_props = ((spec.get("items") or {}).get("properties")) or {}
    headers = [c.replace("_", " ").title() for c in cols]
    _style_header(ws, 4, headers, [16, 16, 24, 34, 54, 26, 18, 18, 18, 30][: len(cols)])
    # Column meanings go on row 3 so the table itself stays clean.
    for i, c in enumerate(cols, start=1):
        d = (item_props.get(c) or {}).get("description", "")
        cell = ws.cell(row=3, column=i, value=d)
        cell.font, cell.alignment = HINT_FONT, WRAP
    ws.row_dimensions[3].height = 42
    for ri, item in enumerate(rows, start=1):
        for ci, c in enumerate(cols, start=1):
            cell = ws.cell(row=4 + ri, column=ci, value=_flatten(item.get(c)))
            cell.fill, cell.border, cell.alignment = INPUT, BORDER, WRAP
        ws.row_dimensions[4 + ri].height = 30
    for extra in range(len(rows) + 1, len(rows) + 9):  # blank rows, ready to fill
        for ci in range(1, len(cols) + 1):
            cell = ws.cell(row=4 + extra, column=ci)
            cell.fill, cell.border = INPUT, BORDER
    ws.cell(row=2, column=1, value="_table:" + section).font = Font(size=8, color="FFFFFF")


# --------------------------------------------------------------------------------------
# read: xlsx -> profile
# --------------------------------------------------------------------------------------


def read(xlsx: Path, out: Path) -> None:
    schema = _load_any(SCHEMA)
    wb = load_workbook(xlsx, data_only=True)
    profile: dict = {"profile_version": "1.0"}

    for key, spec in schema.get("properties", {}).items():
        xw = spec.get("x-workbook") or {}
        tab = xw.get("tab")
        if not tab or tab[:31] not in wb.sheetnames:
            continue
        ws = wb[tab[:31]]
        if xw.get("as_table"):
            rows = _read_table(ws, spec, xw)
            # An empty tab means the section is absent, not present-and-empty. A profile with
            # no accounts should read back with no accounts key, or the round trip reports a
            # difference that is not one.
            if rows:
                profile[key] = rows
        else:
            profile[key] = _read_settings(ws, spec)

    # Fold the Overrides tab back onto the accounts and projects it belongs to.
    if "Overrides" in wb.sheetnames:
        ws = wb["Overrides"]
        rows = []
        for r in ws.iter_rows(min_row=5, max_col=5):
            scope, rid, setting, value = (r[1].value, r[2].value, r[3].value, r[4].value)
            if rid and setting:
                rows.append({"scope": scope or "project", "id": str(rid),
                             "setting": str(setting), "value": value})
        folded = unflatten(rows, schema)
        for (scope, rid), block in folded.items():
            bucket = "accounts" if scope == "account" else "projects"
            target = next((x for x in profile.get(bucket) or [] if x.get("id") == rid), None)
            if target is not None:
                target["overrides"] = block

    _dump_yaml(profile, out)
    print(f"Wrote {out}")


def _read_settings(ws, spec: dict) -> dict:
    props = spec.get("properties") or {}
    result: dict = {}
    sub_start: tuple[str, list[str], int] | None = None
    for row in ws.iter_rows(min_row=5, max_col=9):
        key = row[8].value
        if key and str(key).startswith("_subtable:"):
            _, prop, cols = str(key).split(":", 2)
            sub_start = (prop, cols.split(","), row[0].row + 2)  # +1 header meanings, +1 first data row
            continue
        if not key:
            continue
        raw = row[1].value
        if "." in str(key):
            parent, child = str(key).split(".", 1)
            pspec = ((props.get(parent) or {}).get("properties") or {}).get(child, {})
            val = _unflatten(str(raw) if raw is not None else "", pspec)
            if val not in (None, "", []):
                result.setdefault(parent, {})[child] = val
        else:
            val = _unflatten(str(raw) if raw is not None else "", props.get(str(key), {}))
            if val not in (None, "", []):
                result[str(key)] = val

    if sub_start:
        prop, cols, first = sub_start
        item_props = ((props.get(prop) or {}).get("items") or {}).get("properties") or {}
        rows = []
        for r in ws.iter_rows(min_row=first, max_col=len(cols)):
            item = {}
            for ci, c in enumerate(cols):
                raw = r[ci].value if ci < len(r) else None
                v = _unflatten(str(raw) if raw is not None else "", item_props.get(c, {}))
                if v not in (None, "", []):
                    item[c] = v
            if item:
                rows.append(item)
        if rows:
            result[prop] = rows
    return result


def _read_table(ws, spec: dict, xw: dict) -> list[dict]:
    cols = xw.get("columns") or []
    item_props = ((spec.get("items") or {}).get("properties")) or {}
    out = []
    for row in ws.iter_rows(min_row=5, max_col=len(cols)):
        values = {}
        for ci, c in enumerate(cols):
            raw = row[ci].value if ci < len(row) else None
            v = _unflatten(str(raw) if raw is not None else "", item_props.get(c, {}))
            if v not in (None, "", []):
                values[c] = v
        if values.get("id") or values.get("name"):
            out.append(values)
    return out


# --------------------------------------------------------------------------------------
# tracker workbook: the per-run audit trail
# --------------------------------------------------------------------------------------


# Which columns a person may edit, per tab. Everything else is computed and comes back
# regenerated on the next run, so editing it would be lost work at best and a note that
# disagrees with its own number at worst.
EDITABLE = {
    "Task Register": {"item_type", "type", "planned", "hours_dev", "hours_qa", "understood",
                      "understood_evidence", "understood_link", "client_expected", "client_date",
                      "met_client_date", "team_committed", "commit_date", "met_commitment",
                      "reopened", "rework_evidence", "rework_link", "exclude_reason", "remarks"},
    "Defect Register": {"kind", "phase", "pre_existing", "rejected", "rejection_reason",
                        "evidence", "final_status", "remarks"},
    "Periods": {"client_date", "commit_date", "client_check", "handover_date", "team_hours",
                "notes", "plan_text"},
    "KPI Summary": {"why", "set_value_by_hand", "set_note_by_hand", "why_set_by_hand"},
}

# Row 2 of every register holds the machine field name, hidden, so read-back survives somebody
# reordering or hiding columns - which they will.
KEYROW = 2

GREEN = PatternFill("solid", fgColor="D9EAD3")
RED = PatternFill("solid", fgColor="F4CCCC")
AMBER = PatternFill("solid", fgColor="FFF2CC")
BAND = PatternFill("solid", fgColor="F7F7F4")
SECTION_FONT = Font(bold=True, size=11, color="FFFFFF")
SECTION_FILL = PatternFill("solid", fgColor="4A6FA5")


def _cell(value):
    """Numbers go into the sheet as numbers, not text: a numeric column sorts, filters and
    totals, and 685 reads better than '685.0'. Everything else flattens to a string."""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float)):
        return int(value) if float(value).is_integer() else round(float(value), 2)
    return _flatten(value)


def _yn(v) -> str:
    if v is None or v == "":
        return ""
    if isinstance(v, bool):
        return "Yes" if v else "No"
    return str(v)


def _is_link(v) -> bool:
    return isinstance(v, str) and v.startswith("http")


def _status_fill(v):
    return {"Met": GREEN, "Not met": RED, "Above maximum": RED,
            "Below minimum": RED, "Not measured": LOCKED}.get(v, LOCKED)


def _sheet(wb, title: str, subtitle: str = "") -> Any:
    ws = wb.create_sheet(title)
    ws.cell(row=1, column=2, value=title).font = TITLE_FONT
    if subtitle:
        c = ws.cell(row=2, column=2, value=subtitle)
        c.font, c.alignment = HINT_FONT, WRAP
        ws.row_dimensions[2].height = 28
    ws.column_dimensions["A"].width = 4
    ws.sheet_view.showGridLines = False
    return ws


def _register(wb, title: str, subtitle: str, cols: list[tuple[str, str, int]],
              rows: list[dict], freeze: str | None = None):
    """cols = [(machine key, header, width)]. Row 2 carries the machine keys, hidden."""
    ws = wb.create_sheet(title)
    editable = EDITABLE.get(title, set())
    ws.sheet_view.showGridLines = False
    ws.cell(row=1, column=2, value=f"{title} ({len(rows)} rows)").font = TITLE_FONT
    c = ws.cell(row=1, column=6, value=subtitle)
    c.font, c.alignment = HINT_FONT, WRAP

    ws.column_dimensions["A"].width = 4
    for i, (key, header, width) in enumerate(cols, start=2):
        ws.cell(row=KEYROW, column=i, value=key).font = Font(size=8, color="FFFFFF")
        h = ws.cell(row=3, column=i, value=header)
        h.fill, h.font, h.border, h.alignment = HEAD, HEAD_FONT, BORDER, WRAP
        ws.column_dimensions[get_column_letter(i)].width = width
    hdr = ws.cell(row=3, column=1, value="#")
    hdr.fill, hdr.font, hdr.border, hdr.alignment = HEAD, HEAD_FONT, BORDER, WRAP
    ws.row_dimensions[KEYROW].hidden = True
    ws.row_dimensions[3].height = 34
    ws.freeze_panes = freeze or "B4"

    for i, row in enumerate(rows, start=1):
        r = 3 + i
        n = ws.cell(row=r, column=1, value=i)
        n.border, n.alignment = BORDER, Alignment(vertical="top", horizontal="center")
        for ci, (key, _h, _w) in enumerate(cols, start=2):
            value = row.get(key)
            cell = ws.cell(row=r, column=ci, value=_cell(value))
            cell.border, cell.alignment = BORDER, WRAP
            cell.fill = INPUT if key in editable else (BAND if i % 2 == 0 else LOCKED)
            if _is_link(value):
                cell.hyperlink, cell.value = value, "Open"
                cell.font = Font(color="1155CC", underline="single")
        ws.row_dimensions[r].height = 30
    ws.auto_filter.ref = f"A3:{get_column_letter(len(cols) + 1)}{3 + max(len(rows), 1)}"
    return ws


def tracker(results_path: Path, kif_path: Path, out: Path, reasons_path: Path | None = None,
            profile_path: Path | None = None) -> None:
    """Build the working file: eight tabs laid out the way the live trackers are, so anybody
    who has seen one project's tracker can read anybody else's.

    Yellow is an input and comes back through `review`; grey is computed and is regenerated.
    Widths, freezes and wrapping are set deliberately - a sheet whose columns you have to drag
    before you can read it does not get read.
    """
    results = _load_any(results_path)
    kif = _load_any(kif_path)
    reasons = _load_any(reasons_path) if reasons_path and reasons_path.exists() else {}
    profile = _load_any(profile_path) if profile_path and profile_path.exists() else {}
    proj = kif.get("project") or {}
    periods = kif.get("periods") or []
    wb = Workbook()
    wb.remove(wb.active)

    reg = _load_any(PLUGIN_ROOT / "schemas" / "kpi_registry.json") \
        if (PLUGIN_ROOT / "schemas" / "kpi_registry.json").exists() \
        else _load_any(PLUGIN_ROOT / "schemas" / "kpi_registry.default.json")
    reg_by_name = {k["name"]: k for k in reg.get("kpis", [])}

    # ---------------------------------------------------------------- Read Me
    ws = wb.create_sheet("Read Me")
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 120
    lines = [
        (f"KPI Tracker: {proj.get('name', '')}", "title"),
        ("Built and refreshed by KPI Copilot. Yellow cells are yours; grey cells are computed and "
         "are rebuilt on the next run.", "hint"),
        ("", ""),
        ("Tabs", "h"),
        ("Dashboard: totals per period, KPI results with coloured bars, and how many are met.", ""),
        ("Config: project details, counting rules, KPI targets with the PMS formula behind each, "
         "and the project dates.", ""),
        ("Periods: one row per KPI period with its dates, notes and PMS period id.", ""),
        ("Task Register: every planned task and additional request, with the evidence behind each "
         "judgement.", ""),
        ("Defect Register: every bug, observation or improvement, including the ones that are "
         "reported but not counted.", ""),
        ("KPI Summary: the nine PMS KPIs per period, the facts behind each, your reason, and the "
         "note that goes to PMS.", ""),
        ("PMS Push Log: what was sent to PMS and when.", ""),
        ("Gaps: anything this run could not measure, and why.", ""),
        ("", ""),
        ("How to read and change it", "h"),
        ("Yellow cells are inputs. Change them, then run workbook.py review to read them back, and "
         "rerun the engine: the values and notes follow from your edits.", ""),
        ("If a computed figure is wrong and you cannot fix the input, put the right one in "
         "'Set value by hand' on KPI Summary with a reason. It is used, the computed figure is kept "
         "beside it, and the note says a person recorded a different figure.", ""),
        ("Dates: a date on the task wins, then the period date, then the project date.", ""),
        ("Client date check: Handover = the period's build reached the client by the date. "
         "Delivery = the item itself was delivered by the date.", ""),
        ("Delivery Commitment counts only the items the team committed to. Items with no commitment "
         "are left out and named - the KPI measures reliability of promises, not volume of work.", ""),
        ("Links sit on the words in notes and remarks. The note sent to PMS never contains a link.", ""),
        ("", ""),
        ("Note format sent to PMS", "h"),
        ("what is measured || the numbers || what was left out || why", "code"),
        ("", ""),
        ("Period names", "h"),
        ("Initial Scope, Additional Requests 1, 2 ..., Milestone 1, 2 ..., Full Project. "
         "PMS allows 25 characters.", ""),
    ]
    r = 1
    for text, kind in lines:
        cell = ws.cell(row=r, column=2, value=text)
        cell.alignment = WRAP
        if kind == "title":
            cell.font = TITLE_FONT
        elif kind == "h":
            cell.font = Font(bold=True, size=11, color="1F3864")
        elif kind == "hint":
            cell.font = HINT_FONT
        elif kind == "code":
            cell.font = Font(name="Menlo", size=10)
            cell.fill = LOCKED
        if text and kind == "":
            ws.row_dimensions[r].height = 30
        r += 1

    # ---------------------------------------------------------------- Dashboard
    ws = _sheet(wb, "Dashboard",
                f"PMS project {proj.get('pms_project_id') or 'not set'}  ·  "
                f"Velocity in {proj.get('velocity_unit', 'Estimated Hours')}")
    ws.cell(row=4, column=1, value="Work and issues by period").font = Font(bold=True, size=12, color="1F3864")
    dash_cols = ["Period", "Delivered", "Not delivered yet", "Planned tasks", "Additional requests",
                 "Completed", "Issues reported", "Bugs counted", "Rejected", "Found after handover",
                 "Client date", "Commit date", "Handed over"]
    widths = [24, 11, 16, 13, 18, 12, 14, 13, 10, 18, 13, 13, 13]
    ws.cell(row=5, column=1, value="#").fill = HEAD
    ws.cell(row=5, column=1).font = HEAD_FONT
    for i, (h, w) in enumerate(zip(dash_cols, widths), start=2):
        c = ws.cell(row=5, column=i, value=h)
        c.fill, c.font, c.border, c.alignment = HEAD, HEAD_FONT, BORDER, WRAP
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[5].height = 32
    ws.freeze_panes = "B6"

    unit = "h" if proj.get("velocity_unit") != "Story Points" else "pts"
    totals = [0] * 9
    r = 6
    for i, per in enumerate(results["periods"], start=1):
        f = per["facts"]
        vel = next((m for m in per["measures"] if m["name"] == "Velocity"), {})
        esc = next((m for m in per["measures"] if m["name"] == "Escaped Defect Rate"), {})
        rej = next((m for m in per["measures"] if m["name"] == "Defect Rejection Rate"), {})
        vals = [i, per["period"], f["delivered"], f["not_delivered"], f["planned"],
                f["additional_requests"],
                f"{vel.get('value') or 0:g} {unit}" if vel.get("value") is not None else "-",
                f["reports"], f["defects_counted"], rej.get("numerator") or 0,
                esc.get("numerator") or 0,
                f.get("client_date") or "", f.get("commit_date") or "", f.get("handover_date") or "Not yet"]
        for ci, v in enumerate(vals, start=1):
            c = ws.cell(row=r, column=ci, value=v)
            c.border, c.alignment = BORDER, Alignment(vertical="center", wrap_text=True)
            if i % 2 == 0:
                c.fill = BAND
        for j, key in enumerate(["delivered", "not_delivered", "planned", "additional_requests"]):
            totals[j] += f[key] or 0
        totals[4] += f["reports"] or 0
        totals[5] += f["defects_counted"] or 0
        totals[6] += rej.get("numerator") or 0
        totals[7] += esc.get("numerator") or 0
        r += 1
    tr = r
    ws.cell(row=tr, column=2, value="Total").font = Font(bold=True)
    for ci, v in zip((3, 4, 5, 6, 8, 9, 10, 11), totals[:8]):
        c = ws.cell(row=tr, column=ci, value=v)
        c.font, c.border = Font(bold=True), BORDER

    # KPI matrix
    r = tr + 3
    ws.cell(row=r, column=1,
            value="KPI results by period  (green = met, red = not met, grey = not measured)"
            ).font = Font(bold=True, size=12, color="1F3864")
    r += 1
    ws.cell(row=r, column=2, value="KPI").fill = HEAD
    ws.cell(row=r, column=2).font = HEAD_FONT
    ws.cell(row=r, column=3, value="Target").fill = HEAD
    ws.cell(row=r, column=3).font = HEAD_FONT
    for j, per in enumerate(results["periods"]):
        c = ws.cell(row=r, column=4 + j, value=per["period"])
        c.fill, c.font, c.border, c.alignment = HEAD, HEAD_FONT, BORDER, WRAP
        ws.column_dimensions[get_column_letter(4 + j)].width = 22
    matrix_head = r
    names = [m["name"] for m in results["periods"][0]["measures"]] if results["periods"] else []
    met = notmet = notmeasured = noreason = 0
    for k, name in enumerate(names, start=1):
        rr = matrix_head + k
        ws.cell(row=rr, column=2, value=name).border = BORDER
        first = next((m for m in results["periods"][0]["measures"] if m["name"] == name), {})
        tgt = ("" if first.get("threshold") is None else
               (f"at least {_flatten(first['threshold'])}" if first.get("direction") == "higher-is-better"
                else f"at most {_flatten(first['threshold'])}") + (" %" if first.get("unit") == "%" else ""))
        ws.cell(row=rr, column=3, value=tgt).border = BORDER
        for j, per in enumerate(results["periods"]):
            m = next((x for x in per["measures"] if x["name"] == name), {})
            c = ws.cell(row=rr, column=4 + j,
                        value=m.get("value") if m.get("value") is not None else "-")
            c.border, c.fill = BORDER, _status_fill(m.get("status"))
            if m.get("overridden"):
                c.comment = None
                c.font = Font(italic=True)
            st = m.get("status")
            met += st == "Met"
            notmet += st == "Not met"
            notmeasured += st == "Not measured"
            if st == "Not met" and not (reasons.get(per["period"]) or {}).get(name):
                noreason += 1

    r = matrix_head + len(names) + 2
    ws.cell(row=r, column=1, value="Status across all periods").font = Font(bold=True, size=12, color="1F3864")
    for j, (label, val, fill) in enumerate([("Met", met, GREEN), ("Not met", notmet, RED),
                                            ("Not measured", notmeasured, LOCKED),
                                            ("Reasons still missing", noreason, AMBER)]):
        rr = r + 1 + (j // 2)
        col = 2 + (j % 2) * 2
        ws.cell(row=rr, column=col, value=label).font = Font(bold=True)
        c = ws.cell(row=rr, column=col + 1, value=val)
        c.fill, c.border = fill, BORDER

    # ---------------------------------------------------------------- Config
    ws = _sheet(wb, "Config", "Yellow cells are settings. Targets come from PMS and are shown here "
                              "for reference; change them in PMS, not here.")
    ws.column_dimensions["B"].width = 34
    ws.column_dimensions["C"].width = 46
    ws.column_dimensions["D"].width = 12
    ws.column_dimensions["E"].width = 10
    ws.column_dimensions["F"].width = 11
    ws.column_dimensions["G"].width = 58
    ws.column_dimensions["H"].width = 58

    def section(row: int, label: str) -> None:
        c = ws.cell(row=row, column=2, value=label)
        c.fill, c.font = SECTION_FILL, SECTION_FONT
        for col in range(3, 9):
            ws.cell(row=row, column=col).fill = SECTION_FILL

    def kv(row: int, label: str, value, hint: str = "", editable: bool = False) -> None:
        ws.cell(row=row, column=2, value=label).border = BORDER
        c = ws.cell(row=row, column=3, value=_flatten(value))
        c.border, c.alignment, c.fill = BORDER, WRAP, (INPUT if editable else LOCKED)
        if hint:
            h = ws.cell(row=row, column=4, value=hint)
            h.font, h.alignment = HINT_FONT, WRAP

    out_cfg = (profile.get("output") or {})
    src = (profile.get("sources") or {})
    section(4, "PROJECT")
    rows = [
        ("Project name", proj.get("name")), ("Client", (profile.get("_account") or {}).get("name")
                                             or (profile.get("owner") or {}).get("account")),
        ("PMS project ID", proj.get("pms_project_id")),
        ("PMS KPI page", f"{(profile.get('organization') or {}).get('pms_base_url','')}"
                         f"/all-projects/{proj.get('pms_project_id')}/kpis"
         if proj.get("pms_project_id") else ""),
        ("Issue tracker", proj.get("tracker")), ("Tracker board", proj.get("tracker_url")),
        ("Period type", proj.get("period_type")),
        ("Plan / estimate sources", proj.get("sources_text")),
        ("Data pulled on", (kif.get("generated") or {}).get("at", "")[:10]),
        ("Adapter", (kif.get("generated") or {}).get("adapter")),
    ]
    for i, (k, v) in enumerate(rows):
        kv(5 + i, k, v)

    r = 5 + len(rows) + 1
    section(r, "COUNTING RULES")
    pol = profile.get("policy") or {}
    crules = [
        ("Velocity unit", proj.get("velocity_unit"), "What Velocity adds up for delivered items."),
        ("Velocity counts", src.get("hours_basis", "dev"),
         "dev = development hours only. dev+qa adds each item's QA hours once its QA is done."),
        ("Count observations as defects?", _yn(pol.get("count_observations", False)),
         "No = only Bug rows count in Defect Rate."),
        ("Count improvements as defects?", _yn(pol.get("count_improvements", False)), ""),
        ("Count pre-existing defects?", _yn(pol.get("count_pre_existing", False)),
         "Pre-existing = already in the product before this work."),
        ("Count post-release defects in Defect Rate?", _yn(pol.get("count_post_release", True)),
         "Post-release defects always count in Escaped Defect Rate."),
        ("When plan and tracker disagree on hours, trust", src.get("hours_first", "tracker"), ""),
    ]
    for i, (k, v, h) in enumerate(crules):
        kv(r + 1 + i, k, v, h, editable=True)

    r = r + len(crules) + 2
    section(r, "KPI TARGETS  (read from PMS; change them on the project in PMS, not here)")
    hdr = ["KPI", "Unit", "PMS KPI ID", "Type", "Target", "Formula (PMS definition)",
           "How this sheet counts it"]
    for i, h in enumerate(hdr, start=2):
        c = ws.cell(row=r + 1, column=i, value=h)
        c.fill, c.font, c.border, c.alignment = HEAD, HEAD_FONT, BORDER, WRAP
    ws.row_dimensions[r + 1].height = 30
    first_period = results["periods"][0]["measures"] if results["periods"] else []
    for i, m in enumerate(first_period):
        rr = r + 2 + i
        meta = reg_by_name.get(m["name"], {})
        vals = [m["name"], m.get("unit"), m.get("pms_id"),
                "Min" if m.get("direction") == "higher-is-better" else "Max",
                m.get("threshold"), meta.get("formula_pms", ""), meta.get("basis", "")]
        for ci, v in enumerate(vals, start=2):
            c = ws.cell(row=rr, column=ci, value=_flatten(v))
            c.border, c.alignment, c.fill = BORDER, WRAP, LOCKED
        ws.row_dimensions[rr].height = 46
        if "for project" in (m.get("threshold_source") or ""):
            ws.cell(row=rr, column=6).fill = AMBER
            ws.cell(row=rr, column=6).comment = None

    r = r + len(first_period) + 3
    section(r, "PROJECT DATES  (used when a period or a task has no date of its own)")
    dates = [
        ("Client expected date", proj.get("client_date"),
         "What the client expects: the planned handover, or a client deadline."),
        ("Team commitment date", proj.get("commit_date"),
         "What the team negotiated and promised."),
        ("Client date check", proj.get("client_check"),
         "Handover = met when the build reached the client by the date. "
         "Delivery = met when the item itself was delivered."),
        ("What a commitment means", ((profile.get("workflow") or {}).get("commitment") or {})
         .get("met_when", "delivery"),
         "What counts as keeping a team commitment. Printed in the note."),
        ("Why these dates", proj.get("dates_why"), "Short reason, with the source on the words."),
    ]
    for i, (k, v, h) in enumerate(dates):
        kv(r + 1 + i, k, v, h, editable=True)

    # ---------------------------------------------------------------- Periods
    _register(wb, "Periods",
              "One row per KPI period. Leave a date empty to fall back to the project date.",
              [("name", "Period Name (max 25)", 22), ("start", "Start", 12), ("end", "End", 12),
               ("description", "PMS Description (auto)", 26),
               ("client_date", "Client Expected Date", 16), ("commit_date", "Commitment Date", 16),
               ("handover_date", "Handed Over On", 15), ("pms_period_id", "PMS Period ID", 13),
               ("pushed_on", "Pushed to PMS On", 15), ("notes", "Notes", 70),
               ("plan_text", "Original Plan", 50), ("team_hours", "Team-level Effort (h)", 13),
               ("client_check", "Client Date Check", 15)],
              [dict(p, description=next((x["description"] for x in results["periods"]
                                         if x["period"] == p.get("name")), ""))
               for p in periods],
              freeze="C4")

    # ---------------------------------------------------------------- Task Register
    tasks = []
    for t in kif["tasks"]:
        tasks.append(dict(
            t,
            item_type=t.get("type"),
            planned=_yn(t.get("planned")),
            hours_total=(t.get("hours_dev") or 0) + (t.get("hours_qa") or 0) or None,
            understood_link=t.get("understood_evidence") if _is_link(t.get("understood_evidence")) else None,
            understood_evidence=t.get("understood_why") or (
                "" if _is_link(t.get("understood_evidence")) else t.get("understood_evidence")),
            client_expected=_yn("Yes" if t.get("met_client_date") else ""),
            team_committed=_yn("Yes" if (t.get("commit_date") or t.get("met_commitment")) else ""),
            rework_link=t.get("rework_evidence") if _is_link(t.get("rework_evidence")) else None,
            rework_evidence=None if _is_link(t.get("rework_evidence")) else t.get("rework_evidence"),
        ))
    _register(wb, "Task Register",
              "Every planned task and additional request, with the evidence behind each judgement.",
              [("period", "Period", 14), ("key", "Ticket", 12), ("link", "Link", 8),
               ("title", "Title", 48), ("item_type", "Item Type", 10),
               ("planned", "Planned (initial scope)?", 11),
               ("hours_total", "Est. Hours (dev + QA)", 10), ("story_points", "Story Points", 9),
               ("hours_source", "Hours Source", 22), ("assignee", "Assignee", 18),
               ("created", "Created", 11), ("delivered", "Delivered", 11), ("closed", "Closed", 11),
               ("status", "Status", 10),
               ("understood", "Understood w/o Client?", 11),
               ("understood_evidence", "Comprehension Evidence", 40),
               ("understood_link", "Comprehension Link", 9),
               ("client_expected", "Client-Expected?", 10),
               ("client_date", "Client Expected Date", 13),
               ("met_client_date", "Met Client Date?", 11),
               ("team_committed", "Team Committed?", 10),
               ("commit_date", "Commitment Date", 13),
               ("met_commitment", "Met Commitment?", 11),
               ("reopened", "Reopened after closing?", 11),
               ("rework_evidence", "Rework Evidence", 34), ("rework_link", "Rework Link", 9),
               ("exclude_reason", "Why excluded", 30),
               ("remarks", "Remarks and sources", 44),
               ("hours_dev", "Dev Hours", 9), ("hours_qa", "QA Hours (counted)", 10)],
              tasks, freeze="E4")

    # ---------------------------------------------------------------- Defect Register
    counted_keys = set()
    for per in results["periods"]:
        for m in per["measures"]:
            if m["name"] == "Defect Rate":
                counted_keys |= set(m.get("counted_keys") or [])
    defects = [dict(d, counts=_yn("Yes" if d.get("key") in counted_keys else "No"))
               for d in kif["defects"]]
    _register(wb, "Defect Register",
              "Every bug, observation or improvement reported, including the ones not counted.",
              [("period", "Period", 14), ("key", "Ticket", 12), ("link", "Link", 8),
               ("title", "Title", 52), ("kind", "Kind", 11), ("reported_by", "Reported By", 20),
               ("reported_on", "Reported On", 12), ("phase", "Phase", 12),
               ("pre_existing", "Pre-existing?", 10), ("rejected", "Rejected?", 9),
               ("rejection_reason", "Rejection Reason", 36), ("evidence", "Evidence", 30),
               ("final_status", "Final Status", 16),
               ("counts", "Counts in Defect Rate?", 11),
               ("against_task", "Against Task", 13),
               ("remarks", "Remarks and sources", 40)],
              defects, freeze="E4")

    # ---------------------------------------------------------------- KPI Summary
    ws = _sheet(wb, "KPI Summary",
                "Grey cells are computed and rebuilt on the next run. Yellow is yours: 'Why' is the "
                "fourth part of every note. If a computed figure is wrong and you cannot fix the "
                "input, put the right one in 'Set value by hand' with a reason - it is used, and the "
                "computed figure is kept beside it.")
    cols = [("period", "Period", 20), ("kpi", "KPI", 22), ("pms_id", "PMS KPI ID", 9),
            ("numerator", "Numerator", 10), ("denominator", "Denominator", 11),
            ("value", "Value", 9), ("target", "Target", 9), ("min_max", "Min / Max", 9),
            ("target_set_by", "Target set by", 24), ("status", "Status", 13),
            ("needs_reason", "Needs a reason?", 11),
            ("note_facts", "What the numbers say (auto)", 58),
            ("why", "Why / context (you write; links on words)", 60),
            ("note_sent_to_pms", "Note sent to PMS (auto, no links)", 80),
            ("set_value_by_hand", "Set value by hand", 13),
            ("set_note_by_hand", "Set note by hand", 50),
            ("why_set_by_hand", "Why set by hand", 50)]
    ws.cell(row=4, column=1, value="#").fill = HEAD
    ws.cell(row=4, column=1).font = HEAD_FONT
    for i, (key, header, width) in enumerate(cols, start=2):
        ws.cell(row=3, column=i, value=key).font = Font(size=8, color="FFFFFF")
        c = ws.cell(row=4, column=i, value=header)
        c.fill, c.font, c.border, c.alignment = HEAD, HEAD_FONT, BORDER, WRAP
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.row_dimensions[3].hidden = True
    ws.row_dimensions[4].height = 34
    ws.freeze_panes = "C5"

    editable = EDITABLE["KPI Summary"]
    r, n = 5, 0
    for per in results["periods"]:
        for m in per["measures"]:
            n += 1
            why = ((reasons.get(per["period"]) or {}).get(m["name"]) or "")
            shown = m.get("computed_value") if m.get("overridden") else m["value"]
            facts = (m.get("note_parts") or ["", "", ""])
            row = {
                "period": per["period"], "kpi": m["name"], "pms_id": m.get("pms_id"),
                "numerator": m.get("numerator"), "denominator": m.get("denominator"),
                "value": shown if shown is not None else "-",
                "target": m.get("threshold"),
                "min_max": "Min" if m.get("direction") == "higher-is-better" else "Max",
                "target_set_by": m.get("threshold_source", ""),
                "status": m["status"],
                "needs_reason": "Yes" if (m["status"] == "Not met" and not why) else "No",
                "note_facts": " || ".join(x for x in facts[:3] if x),
                "why": why, "note_sent_to_pms": m["note"],
                "set_value_by_hand": m["value"] if m.get("overridden") else "",
                "set_note_by_hand": m["note"] if (m.get("overridden")
                                                  and m.get("computed_note") != m["note"]) else "",
                "why_set_by_hand": m.get("override_reason", ""),
            }
            c = ws.cell(row=r, column=1, value=n)
            c.border, c.alignment = BORDER, Alignment(vertical="top", horizontal="center")
            for ci, (key, _h, _w) in enumerate(cols, start=2):
                cell = ws.cell(row=r, column=ci, value=_cell(row.get(key)))
                cell.border, cell.alignment = BORDER, WRAP
                if key == "status":
                    cell.fill = _status_fill(row["status"])
                elif key == "needs_reason":
                    cell.fill = AMBER if row["needs_reason"] == "Yes" else LOCKED
                elif key in editable:
                    cell.fill = INPUT
                else:
                    cell.fill = LOCKED
            ws.row_dimensions[r].height = 48
            r += 1
    ws.auto_filter.ref = f"A4:{get_column_letter(len(cols) + 1)}{max(r - 1, 5)}"

    # ---------------------------------------------------------------- PMS Push Log
    log_path = results_path.parent / "push_log.json"
    log_rows: list[dict] = []
    if log_path.exists():
        try:
            for res in (_load_any(log_path).get("results") or []):
                log_rows.append({
                    "pushed_on": _load_any(log_path).get("at", "")[:16].replace("T", " "),
                    "period": res.get("period"), "pms_period_id": res.get("periodId"),
                    "action": "Update",
                    "changed": "; ".join(f"{k['name']}: {k['value']}" for k in res.get("kpis") or []),
                    "by": "", "result": res.get("result"),
                })
        except Exception:  # noqa: BLE001
            pass
    _register(wb, "PMS Push Log",
              "One line each time values are sent to PMS. Added automatically after a push.",
              [("pushed_on", "Pushed On", 18), ("period", "Period", 18),
               ("pms_period_id", "PMS Period ID", 13), ("action", "Action", 11),
               ("changed", "What changed", 80), ("by", "Note or pushed by", 20),
               ("result", "Result", 30)],
              log_rows)

    # ---------------------------------------------------------------- Gaps
    ws = _sheet(wb, "Gaps", "What this run could not measure, and why. An empty tab is a good sign.")
    for i, (h, w) in enumerate(zip(["Period", "KPI", "Reason"], [24, 24, 100]), start=2):
        c = ws.cell(row=4, column=i, value=h)
        c.fill, c.font, c.border, c.alignment = HEAD, HEAD_FONT, BORDER, WRAP
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.cell(row=4, column=1, value="#").fill = HEAD
    ws.cell(row=4, column=1).font = HEAD_FONT
    r, n = 5, 0
    for per in results["periods"]:
        for m in per["measures"]:
            for g in m.get("gaps") or []:
                n += 1
                for ci, v in enumerate([n, per["period"], m["name"], g], start=1):
                    c = ws.cell(row=r, column=ci, value=v)
                    c.border, c.alignment = BORDER, WRAP
                ws.row_dimensions[r].height = 30
                r += 1
    if n == 0:
        ws.cell(row=5, column=2,
                value="Nothing. Every KPI was measurable from the sources available."
                ).font = HINT_FONT

    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    print(f"Wrote {out} ({len(wb.sheetnames)} tabs: {', '.join(wb.sheetnames)})")


# --------------------------------------------------------------------------------------
# review: read a person's edits back out of the tracker workbook
# --------------------------------------------------------------------------------------


# Some workbook columns are a friendlier view of a KIF field, or two of them. Mapping them
# back explicitly beats letting the names drift apart silently.
WB_TO_KIF = {
    "Task Register": {"item_type": "type"},
    "Defect Register": {},
    "Periods": {},
}


# Columns that are a view of something else, or are computed. The direct loop skips them:
# the fold handles the first kind and nothing should write the second.
VIEW_COLUMNS = {"understood_link", "rework_link", "client_expected", "team_committed",
                "hours_total", "counts", "description", "pushed_on",
                "understood_evidence", "rework_evidence"}


def _fold_task_row(row: dict, hit: dict, note) -> set[str]:
    """Columns that are a view rather than a field: the evidence/link pair, and the two gate
    columns that say whether an item was client-expected or team-committed at all."""
    ev, link = row.get("understood_evidence"), row.get("understood_link")
    if ev is not None or link is not None:
        merged = " ".join(str(x) for x in (ev, link) if x and str(x).strip() and str(x) != "Open")
        if merged and merged != (hit.get("understood_evidence") or ""):
            hit["understood_evidence"] = merged
    rev, rlink = row.get("rework_evidence"), row.get("rework_link")
    if rev is not None or rlink is not None:
        merged = " ".join(str(x) for x in (rev, rlink) if x and str(x).strip() and str(x) != "Open")
        if merged and merged != (hit.get("rework_evidence") or ""):
            hit["rework_evidence"] = merged

    # "Client-Expected?" and "Team Committed?" are gates. Turning one off takes the item out
    # of that KPI entirely, which is a real and useful edit - an item nobody promised should
    # not be counted against the team's reliability.
    locked: set[str] = set()
    for gate, judged, dated in (("client_expected", "met_client_date", "client_date"),
                                ("team_committed", "met_commitment", "commit_date")):
        val = str(row.get(gate) or "").strip().lower()
        if not val:
            continue
        if val in ("no", "false"):
            if hit.get(judged) is not None or hit.get(dated):
                hit[judged], hit[dated] = None, None
                note(f"{row.get('key')}: {gate} set to No, so it is out of that KPI")
        elif val in ("yes", "true") and hit.get(judged) is None:
            hit[judged] = "Pending"
            note(f"{row.get('key')}: {gate} set to Yes, now Pending until judged")
        if val in ("no", "false"):
            # The gate wins: do not let the raw judged/date columns put it back.
            locked.update({judged, dated})
    return locked


def _read_register(ws, keyrow: int, first_data_row: int) -> list[dict]:
    """Rows keyed by the hidden machine names, so a reordered or hidden column still lands in
    the right field."""
    cols = {}
    for cell in ws[keyrow]:
        if cell.value:
            cols[cell.column] = str(cell.value)
    out = []
    for row in ws.iter_rows(min_row=first_data_row):
        values = {cols[c.column]: c.value for c in row if c.column in cols}
        if any(v not in (None, "") for v in values.values()):
            out.append(values)
    return out


def _norm(v: Any) -> str:
    """One spelling for comparison. A whole number is '100' whether it arrived as 100, 100.0
    or the string '100.0' - otherwise an untouched cell reads as an edit."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, (int, float)):
        return str(int(v)) if float(v).is_integer() else f"{float(v):.2f}".rstrip("0").rstrip(".")
    text = str(v).strip()
    try:
        f = float(text)
    except ValueError:
        return text
    return str(int(f)) if f.is_integer() else f"{f:.2f}".rstrip("0").rstrip(".")


def review(tracker_path: Path, kif_path: Path, out_kif: Path, out_reasons: Path,
           reasons_path: Path | None = None, out_manual: Path | None = None,
           manual_path: Path | None = None, by: str = "",
           results_path: Path | None = None) -> int:
    """Fold a person's edits in the tracker workbook back into the KIF and the reasons file.

    The point is that the sheet is a working surface, not a report you read and then retype
    somewhere else. Edit a Yes/No, a date, an hour figure or the 'Why' text, run this, rerun
    the engine, and the numbers and the notes follow. What you cannot do is edit the computed
    note itself - that would make the sheet and PMS say different things about the same
    number, so those edits are reported and dropped, with the reason.
    """
    wb = load_workbook(tracker_path, data_only=True)
    kif = _load_any(kif_path)
    reasons = _load_any(reasons_path) if reasons_path and reasons_path.exists() else {}
    manual = _load_any(manual_path) if manual_path and manual_path.exists() else {}
    # What the sheet said when it was built, so an edit to a computed cell can be spotted and
    # pointed at the column that would actually have worked.
    computed: dict[tuple[str, str], dict] = {}
    if results_path and results_path.exists():
        for per in (_load_any(results_path).get("periods") or []):
            for m in per.get("measures") or []:
                computed[(per["period"], m["name"])] = m

    changes: list[str] = []
    refused: list[str] = []

    def apply(rows: list[dict], target: list[dict], key_fields: tuple[str, ...], tab: str) -> None:
        editable = EDITABLE[tab]
        index = {tuple(_norm(t.get(k)) for k in key_fields): t for t in target}
        for row in rows:
            hit = index.get(tuple(_norm(row.get(k)) for k in key_fields))
            if hit is None:
                refused.append(f"{tab}: no row in the extract matches "
                               f"{' / '.join(_norm(row.get(k)) for k in key_fields)}. "
                               f"Rows cannot be added here - add them in the tracker or the profile.")
                continue
            handled: set[str] = set()
            if tab == "Task Register":
                handled = _fold_task_row(row, hit, changes.append)
            mapping = WB_TO_KIF.get(tab, {})
            for field, new in row.items():
                field = mapping.get(field, field)
                if field in VIEW_COLUMNS or field in handled:
                    continue          # a view of another field, folded above, or computed
                if field not in editable and mapping.get(field, field) not in editable:
                    if _norm(new) != _norm(hit.get(field)):
                        refused.append(f"{tab} {_norm(row.get(key_fields[-1]))}: '{field}' is computed, "
                                       f"so the edit was ignored. Change the input and rerun.")
                    continue
                old = hit.get(field)
                if _norm(new) == _norm(old):
                    continue
                if field == "type" and str(new).strip() not in ("Task", "CR", "Scope", "Excluded"):
                    refused.append(f"{tab} {_norm(row.get(key_fields[-1]))}: item type "
                                   f"'{new}' is not Task, CR, Scope or Excluded.")
                    continue
                if field in ("hours_dev", "hours_qa", "team_hours", "story_points"):
                    try:
                        new = float(new) if _norm(new) else None
                    except (TypeError, ValueError):
                        refused.append(f"{tab} {_norm(row.get(key_fields[-1]))}: '{new}' is not a number.")
                        continue
                elif field == "planned":
                    new = _norm(new).lower() in ("yes", "true")
                else:
                    new = _norm(new) or None
                changes.append(f"{tab:<16} {_norm(row.get(key_fields[-1])):<22} {field:<22} "
                               f"{_norm(old) or '(blank)'} -> {_norm(new) or '(blank)'}")
                hit[field] = new

    if "Task Register" in wb.sheetnames:
        apply(_read_register(wb["Task Register"], KEYROW, 4), kif["tasks"], ("period", "key"), "Task Register")
    if "Defect Register" in wb.sheetnames:
        apply(_read_register(wb["Defect Register"], KEYROW, 4), kif["defects"], ("period", "key"), "Defect Register")
    if "Periods" in wb.sheetnames:
        apply(_read_register(wb["Periods"], KEYROW, 4), kif["periods"], ("name",), "Periods")

    # The 'Why' column, which is the only free text a person owns.
    if "KPI Summary" in wb.sheetnames:
        ws = wb["KPI Summary"]
        for row in _read_register(ws, 3, 5):
            period, kpi, why = _norm(row.get("period")), _norm(row.get("kpi")), _norm(row.get("why"))
            if not (period and kpi):
                continue
            old = _norm((reasons.get(period) or {}).get(kpi))
            if why != old:
                changes.append(f"{'KPI Summary':<16} {period + ' / ' + kpi:<22} {'why':<22} "
                               f"{(old[:40] + '...') if len(old) > 40 else (old or '(blank)')} -> "
                               f"{(why[:40] + '...') if len(why) > 40 else (why or '(blank)')}")
                reasons.setdefault(period, {})[kpi] = why
            # A hand-set value or note. Allowed, and recorded with its reason - the engine
            # refuses one without a reason, because it prints these above the numbers.
            # Somebody typed over a grey cell. It would be regenerated on the next run, so
            # say what they should have done rather than losing the edit in silence.
            was = computed.get((period, kpi))
            if was is not None:
                shown = was.get("computed_value") if was.get("overridden") else was.get("value")
                expected = _norm(shown) if shown is not None else "-"
                if _norm(row.get("value")) != expected:
                    refused.append(
                        f"KPI Summary {period} / {kpi}: 'Value' is computed, so the edit was not kept. "
                        f"If the figure really is wrong, put it in 'Set value by hand' with a reason, "
                        f"or fix the register rows and rerun.")
                if _norm(row.get("note_sent_to_pms")) != _norm(was.get("note")):
                    refused.append(
                        f"KPI Summary {period} / {kpi}: 'Note sent to PMS' is assembled from the numbers "
                        f"and your 'Why', so the edit was not kept. Put wording in 'Why', or the whole "
                        f"note in 'Set note by hand' with a reason.")

            set_value = _norm(row.get("set_value_by_hand"))
            set_note = _norm(row.get("set_note_by_hand"))
            set_why = _norm(row.get("why_set_by_hand"))
            if set_value or set_note:
                if not set_why:
                    refused.append(f"KPI Summary {period} / {kpi}: a hand-set value needs a reason in "
                                   f"'Why set by hand'. It is printed with the numbers, so a reader can "
                                   f"see a person set it.")
                else:
                    entry: dict = {"why": set_why}
                    if set_value:
                        entry["value"] = set_value
                    if set_note:
                        entry["note"] = set_note
                    if by:
                        entry["by"] = by
                    manual.setdefault(period, {})[kpi] = entry
                    changes.append(f"{'KPI Summary':<16} {period + ' / ' + kpi:<22} "
                                   f"{'set by hand':<22} {set_value or 'note only'}")
            elif (manual.get(period) or {}).pop(kpi, None) is not None:
                changes.append(f"{'KPI Summary':<16} {period + ' / ' + kpi:<22} "
                               f"{'hand-set value':<22} cleared")

    out_kif.parent.mkdir(parents=True, exist_ok=True)
    out_kif.write_text(json.dumps(kif, indent=2), encoding="utf-8")
    _dump_yaml(reasons, out_reasons)
    if out_manual is not None:
        _dump_yaml({k: v for k, v in manual.items() if v}, out_manual)

    if changes:
        print(f"{len(changes)} edit(s) read back from {tracker_path.name}:\n")
        for c in changes:
            print("  " + c)
    else:
        print(f"No edits found in {tracker_path.name}.")
    if refused:
        print(f"\n{len(refused)} edit(s) not applied:\n")
        for c in dict.fromkeys(refused):
            print("  " + c)
    tail = f", {out_manual}" if out_manual is not None else ""
    print(f"\nWrote {out_kif}, {out_reasons}{tail}.")
    print("Now rerun the engine against the patched extract; the notes and values follow from it,\n"
          "which is what keeps the sheet and PMS saying the same thing.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build and read the KPI Copilot workbooks.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="Profile -> KPI Profile Workbook")
    b.add_argument("--profile", type=Path)
    b.add_argument("--out", type=Path, required=True)

    r = sub.add_parser("read", help="KPI Profile Workbook -> profile.yaml")
    r.add_argument("--xlsx", type=Path, required=True)
    r.add_argument("--out", type=Path, required=True)

    t = sub.add_parser("tracker", help="Results + KIF -> per-project tracker workbook")
    t.add_argument("--results", type=Path, required=True)
    t.add_argument("--kif", type=Path, required=True)
    t.add_argument("--profile", type=Path)
    t.add_argument("--reasons", type=Path, help="Pre-fill the Why column.")
    t.add_argument("--out", type=Path, required=True)

    v2 = sub.add_parser("review", help="Read a person's edits back out of a tracker workbook")
    v2.add_argument("--tracker", type=Path, required=True)
    v2.add_argument("--kif", type=Path, required=True)
    v2.add_argument("--results", type=Path, help="The run's results.json, so edits to computed cells are spotted.")
    v2.add_argument("--reasons", type=Path)
    v2.add_argument("--manual", type=Path)
    v2.add_argument("--out-kif", type=Path, required=True)
    v2.add_argument("--out-reasons", type=Path, required=True)
    v2.add_argument("--out-manual", type=Path)
    v2.add_argument("--by", default="", help="Who made the edits, recorded with any hand-set value.")

    a = ap.parse_args(argv)
    if a.cmd == "build":
        build(a.profile, a.out)
    elif a.cmd == "read":
        read(a.xlsx, a.out)
    elif a.cmd == "review":
        return review(a.tracker, a.kif, a.out_kif, a.out_reasons, a.reasons,
                      a.out_manual, a.manual, a.by, a.results)
    else:
        tracker(a.results, a.kif, a.out, a.reasons, a.profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
