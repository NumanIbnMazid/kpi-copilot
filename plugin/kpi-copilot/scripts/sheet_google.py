#!/usr/bin/env python3
"""
The workbook model, kept as one live Google Sheet.

Every run updates the same spreadsheet - same link, same place in Drive. Which spreadsheet
is the profile's choice:

    output.workbook_file       a specific Google Sheet (link or id): update that one
    output.workbook_location   a Drive folder: find "<name>" there, or create it the first time

Each tab the tool owns is rebuilt inside a single batchUpdate, which Google applies
atomically: somebody with the sheet open sees it change once, never half-written. Tabs the
tool does not own - anything a person added - are left exactly as they are. What a person
typed into yellow cells is read back before any of this happens (sheet_readback.py), so a
rebuild never costs anybody their edits.

The requests are built by pure functions from the model, so they can be checked without a
network; only `publish()` and `read_grid()` talk to Google.
"""

from __future__ import annotations

import datetime as dt
import zlib
from typing import Any, Callable

import google_api as G
import sheet_model as M

_EPOCH = dt.date(1899, 12, 30)
META_FIELDS = ("spreadsheetUrl,properties(locale,title),"
               "sheets(properties(sheetId,title,index,gridProperties),conditionalFormats,basicFilter)")


def _rgb(hex6: str) -> dict:
    return {"red": int(hex6[0:2], 16) / 255, "green": int(hex6[2:4], 16) / 255, "blue": int(hex6[4:6], 16) / 255}


def _format(spec: dict, fmt: str | None) -> dict:
    text = {"fontFamily": "Arial", "fontSize": spec.get("size") or 10, "bold": bool(spec.get("b")),
            "italic": bool(spec.get("i")), "underline": bool(spec.get("u")),
            "foregroundColor": _rgb(spec.get("color") or "000000")}
    out: dict[str, Any] = {
        "textFormat": text,
        "verticalAlignment": {"top": "TOP", "center": "MIDDLE", "bottom": "BOTTOM"}.get(spec.get("v") or "", "BOTTOM"),
        "wrapStrategy": "WRAP" if spec.get("wrap") else "OVERFLOW_CELL",
    }
    if spec.get("h"):
        out["horizontalAlignment"] = spec["h"].upper()
    if spec.get("fill"):
        out["backgroundColor"] = _rgb(spec["fill"])
    if spec.get("box"):
        side = {"style": "SOLID", "color": _rgb(M.LINE)}
        out["borders"] = {"top": side, "bottom": side, "left": side, "right": side}
    if fmt:
        out["numberFormat"] = {"type": "DATE" if any(x in fmt.lower() for x in ("yy", "dd")) else "NUMBER", "pattern": fmt}
    return out


def _value(cell: dict) -> dict:
    if cell.get("link") and "v" in cell:
        url, label = cell["link"].replace('"', "%22"), str(cell["v"]).replace('"', '""')
        return {"userEnteredValue": {"formulaValue": f'=HYPERLINK("{url}","{label}")'}}
    fx = cell.get("gf") or cell.get("f")
    if fx:
        return {"userEnteredValue": {"formulaValue": fx}}
    v = cell.get("v")
    if v is None:
        return {}
    if isinstance(v, bool):
        return {"userEnteredValue": {"boolValue": v}}
    if isinstance(v, dt.datetime):
        v = v.date()
    if isinstance(v, dt.date):
        return {"userEnteredValue": {"numberValue": (v - _EPOCH).days}}
    if isinstance(v, (int, float)):
        return {"userEnteredValue": {"numberValue": v}}
    return {"userEnteredValue": {"stringValue": str(v)}}


def sheet_id_for(name: str) -> int:
    """Stable per tab name, so a rerun that has to re-add a tab gives it the same id."""
    return 100000 + zlib.crc32(name.encode("utf-8")) % 900000


def _grid_range(sid: int, r1: int, c1: int, r2: int, c2: int) -> dict:
    return {"sheetId": sid, "startRowIndex": r1 - 1, "endRowIndex": r2, "startColumnIndex": c1 - 1, "endColumnIndex": c2}


def tab_requests(tab: M.Tab, sid: int, index: int, existing: dict | None,
                 compact_existing: bool = False) -> list[dict]:
    """Everything needed to make one tab look like the model, whatever state it was in."""
    rows, cols = tab.size
    rows, cols = rows + 5, max(cols + 1, 8)
    reqs: list[dict] = []
    if existing is None:
        reqs.append({"addSheet": {"properties": {"sheetId": sid, "title": tab.name, "index": index,
                                                 "gridProperties": {"rowCount": rows, "columnCount": cols}}}})
    else:
        if not compact_existing:
            for i in reversed(range(len(existing.get("conditionalFormats") or []))):
                reqs.append({"deleteConditionalFormatRule": {"sheetId": sid, "index": i}})
        grid = (existing.get("properties") or {}).get("gridProperties") or {}
        rows, cols = max(rows, grid.get("rowCount") or 0), max(cols, grid.get("columnCount") or 0)
        # The tab may be one a person built by hand before pointing the tool at it, so anything
        # that would fight the new layout goes first: merged cells, a filter, old colour rules.
        if not compact_existing:
            reqs.append({"unmergeCells": {"range": {"sheetId": sid}}})
            if existing.get("basicFilter"):
                reqs.append({"clearBasicFilter": {"sheetId": sid}})
        reqs.append({"updateCells": {"range": {"sheetId": sid},
                                     "fields": ("userEnteredValue,dataValidation" if compact_existing else
                                                "userEnteredValue,userEnteredFormat,dataValidation")}})
    reqs.append({"updateSheetProperties": {
        "properties": {"sheetId": sid, "title": tab.name, "index": index, "tabColor": _rgb(tab.color),
                       "gridProperties": {"rowCount": rows, "columnCount": cols, "frozenRowCount": tab.freeze[0],
                                          "frozenColumnCount": tab.freeze[1], "hideGridlines": not tab.gridlines}},
        "fields": "title,index,tabColor,gridProperties(rowCount,columnCount,frozenRowCount,frozenColumnCount,hideGridlines)"}})
    # Expand the grid before touching dimensions outside the old bounds.
    if not compact_existing:
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 0, "endIndex": cols},
            "properties": {"hiddenByUser": False}, "fields": "hiddenByUser"}})
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 0, "endIndex": rows},
            "properties": {"hiddenByUser": False, "pixelSize": 21}, "fields": "hiddenByUser,pixelSize"}})

    last_r, last_c = tab.size
    data = [{"values": [_value(tab.cells.get((r, c)) or {}) for c in range(1, last_c + 1)]} for r in range(1, last_r + 1)]
    reqs.append({"updateCells": {"start": {"sheetId": sid, "rowIndex": 0, "columnIndex": 0},
                                 "rows": data, "fields": "userEnteredValue"}})

    # Formats as runs down each column: a register column is one style for a hundred rows,
    # so this is a few dozen requests instead of a format on every cell.
    if not compact_existing:
        for c in range(1, last_c + 1):
            run_key, run_start = None, 1
            for r in range(1, last_r + 2):
                cell = tab.cells.get((r, c)) if r <= last_r else None
                key = (cell.get("style") or "text", cell.get("fmt")) if cell else None
                if key != run_key:
                    if run_key is not None:
                        reqs.append({"repeatCell": {
                            "range": _grid_range(sid, run_start, c, r - 1, c),
                            "cell": {"userEnteredFormat": _format(M.STYLES.get(run_key[0], M.STYLES["text"]), run_key[1])},
                            "fields": "userEnteredFormat"}})
                    run_key, run_start = key, r

        for c, w in tab.widths.items():
            reqs.append({"updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": c - 1, "endIndex": c},
                "properties": {"pixelSize": int(w * 7 + 5)}, "fields": "pixelSize"}})
        for c in tab.hidden_cols:
            reqs.append({"updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": c - 1, "endIndex": c},
                "properties": {"hiddenByUser": True}, "fields": "hiddenByUser"}})
        for r, h in tab.heights.items():
            reqs.append({"updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": r - 1, "endIndex": r},
                "properties": {"pixelSize": int(h * 96 / 72)}, "fields": "pixelSize"}})
    for v in tab.validations:
        cond = ({"type": "ONE_OF_RANGE", "values": [{"userEnteredValue": "=" + v["source"]}]} if v.get("source")
                else {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": x} for x in v["values"]]})
        reqs.append({"setDataValidation": {"range": _grid_range(sid, *v["range"]),
                                           "rule": {"condition": cond, "showCustomUi": True, "strict": False}}})
    if not compact_existing:
        for i, rule in enumerate(tab.cond):
            fmt: dict[str, Any] = {}
            if rule.get("fill"):
                fmt["backgroundColor"] = _rgb(rule["fill"])
            if rule.get("color"):
                fmt["textFormat"] = {"foregroundColor": _rgb(rule["color"])}
            reqs.append({"addConditionalFormatRule": {"index": i, "rule": {
                "ranges": [_grid_range(sid, *rule["range"])],
                "booleanRule": {"condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": rule["formula"]}]},
                                "format": fmt}}}})
        for bounds in tab.merges:
            reqs.append({"mergeCells": {"range": _grid_range(sid, *bounds), "mergeType": "MERGE_ALL"}})
        if tab.filter_range:
            reqs.append({"setBasicFilter": {"filter": {"range": _grid_range(sid, *tab.filter_range)}}})
    return reqs


def resolve(s: G.Session, out_cfg: dict, name: str) -> tuple[str, bool]:
    """Which spreadsheet to write: the file named, else the one of this name in the folder
    named, else a new one. Returns (id, created)."""
    fid = G.file_id(out_cfg.get("workbook_file"))
    if fid:
        return fid, False
    folder = G.file_id(out_cfg.get("workbook_location"))
    if folder:
        hit = G.drive_find(s, folder, name)
        if hit:
            return hit["id"], False
    return G.drive_create_sheet(s, folder, name)["id"], True


def publish(tabs: list[M.Tab], out_cfg: dict, name: str, known_id: str | None = None,
            session: G.Session | None = None) -> dict:
    s = session or G.Session()
    configured = G.file_id(out_cfg.get("workbook_file"))
    if known_id and configured and configured != known_id:
        raise G.GoogleError("The configured review sheet differs from the saved destination. "
                            "Finish reviewing the current sheet before migrating the destination.")
    fid, created = (known_id, False) if known_id else resolve(s, out_cfg, name)
    meta = s.call("GET", f"{G.SHEETS}/{fid}", params={"fields": META_FIELDS})
    have = {sh["properties"]["title"]: sh for sh in meta.get("sheets") or []}
    reqs: list[dict] = []
    for i, tab in enumerate(tabs):
        ex = have.get(tab.name)
        sid = ex["properties"]["sheetId"] if ex else sheet_id_for(tab.name)
        compact = bool(ex) and G.how_signed_in() == "host-connector" and not out_cfg.get("full_refresh")
        reqs += tab_requests(tab, sid, i, ex, compact_existing=compact)
    # Sheets resolves references when a formula is entered. Create every tab first;
    # otherwise an early Dashboard formula can retain #REF! for a later Config tab.
    reqs = [r for r in reqs if "addSheet" in r] + [r for r in reqs if "addSheet" not in r]
    locale = (meta.get("properties") or {}).get("locale") or "en_US"
    warn = ""
    if created:
        # Formulas are read the way a person typing them would be, so the separators depend on
        # the spreadsheet's locale. A new file is set to one where a comma is a comma.
        reqs.insert(0, {"updateSpreadsheetProperties": {"properties": {"locale": "en_US"}, "fields": "locale"}})
    elif not locale.lower().startswith("en"):
        warn = (f"The spreadsheet's locale is {locale}. Formulas are written with comma separators; if cells show "
                f"errors, set File > Settings > Locale to United States or United Kingdom and run again.")
    if created:
        for title, sh in have.items():
            if title not in {t.name for t in tabs}:
                reqs.append({"deleteSheet": {"sheetId": sh["properties"]["sheetId"]}})
    s.call("POST", f"{G.SHEETS}/{fid}:batchUpdate", {"requests": reqs})
    return {"kind": "google", "id": fid, "url": meta.get("spreadsheetUrl") or f"https://docs.google.com/spreadsheets/d/{fid}/edit",
            "created": created, "requests": len(reqs), "as": s.identity, "warning": warn}


def read_grid(fid: str, tabs: list[str], session: G.Session | None = None) -> Callable[[str, int, int], Any]:
    """grid(tab, row, col) over the live sheet, fetched in one call. Formatted values, so a
    date comes back as the ISO text it is displayed as, whatever a person typed."""
    s = session or G.Session()
    doc = s.call("GET", f"{G.SHEETS}/{fid}/values:batchGet", params={
        "ranges": ["'" + t.replace("'", "''") + "'" for t in tabs], "valueRenderOption": "FORMATTED_VALUE"})
    if len(doc.get("valueRanges") or []) != len(tabs):
        raise G.GoogleError("Incomplete review-sheet read. Retry before replacing any cells.")
    data = {}
    for t, vr in zip(tabs, doc.get("valueRanges") or []):
        data[t] = vr.get("values") or []

    def grid(tab: str, r: int, c: int) -> Any:
        rows = data.get(tab) or []
        if r - 1 >= len(rows) or c - 1 >= len(rows[r - 1]):
            return None
        v = rows[r - 1][c - 1]
        return (v.strip() or None) if isinstance(v, str) else v

    grid.rows = lambda tab: len(data.get(tab) or [])                     # type: ignore[attr-defined]
    return grid


def connector_doc(path):
    """Unwrap a connector CellData/metadata response saved directly to disk."""
    import json
    data = json.loads(path.read_text(encoding="utf-8"))
    if "cells" in data:
        data = data["cells"]
    return data.get("structuredContent", data)


def connector_grid(path, fid):
    doc = connector_doc(path)
    if doc.get("spreadsheetId") != fid:
        raise ValueError("Review snapshot belongs to a different spreadsheet.")
    data, counts = {}, {}
    for sheet in doc.get("sheets", []):
        name = sheet["properties"]["title"]
        for block in sheet.get("data", []):
            for ri, row in enumerate(block.get("rowData", []), 1 + block.get("startRow", 0)):
                counts[name] = max(counts.get(name, 0), ri)
                for ci, cell in enumerate(row.get("values", []), 1 + block.get("startColumn", 0)):
                    effective = cell.get("effectiveValue") or {}
                    if effective.get("errorValue"):
                        raise ValueError(f"Formula error on {name}; repair the review sheet before continuing.")
                    fmt = ((cell.get("effectiveFormat") or cell.get("userEnteredFormat") or {})
                           .get("numberFormat") or {}).get("type")
                    # Preserve date text for ISO conversion; otherwise use unrounded values.
                    value = effective or cell.get("userEnteredValue") or {}
                    if fmt in ("DATE", "DATE_TIME", "TIME"):
                        data[name, ri, ci] = cell.get("formattedValue")
                    else:
                        data[name, ri, ci] = value.get("stringValue", value.get("numberValue", value.get("boolValue")))
                    if data[name, ri, ci] is None:
                        data[name, ri, ci] = cell.get("formattedValue")
    def grid(name, row, col):
        value = data.get((name, row, col))
        return None if value == "" else value
    grid.rows = lambda name: counts.get(name, 0)
    return grid
