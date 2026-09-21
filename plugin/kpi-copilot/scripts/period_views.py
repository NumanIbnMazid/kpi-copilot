"""Compact navigation over an arbitrarily long continuing KPI workbook."""
import sheet_model as M


def build(periods, names, ctx, last):
    dashboard = M.Tab("Dashboard")
    dashboard.widths = {1: 29, 2: 19, 3: 22, 4: 25, 5: 18, 8: 12}
    dashboard.hidden_cols = [8]
    dashboard.merges = [(1, 1, 1, 5), (2, 1, 2, 5), (4, 2, 4, 5), (19, 1, 19, 5), (22, 1, 22, 5)]
    dashboard.put(1, 1, "KPI Dashboard", "title")
    dashboard.put(2, 1, "Choose a period below. Compare periods in Period Overview; filter the registers for the evidence.", "sub")
    dashboard.heights.update({1: 25, 2: 24, 3: 8, 4: 26, 5: 8, 6: 8, 7: 26, 19: 32, 22: 32})
    labels = [p["name"] for p in periods]
    selected = (ctx.get("view") or {}).get("period")
    if selected not in labels:
        selected = labels[-1] if labels else ""
    dashboard.put(4, 1, "Reporting period", "label")
    dashboard.put(4, 2, selected, "in")
    dashboard.dropdown(4, 2, 4, 2, source=f"Periods!$B$5:$B${max(5, len(periods)+4)}")
    dashboard.readback = {"kind": "cells", "cells": {"period": (4, 2)}}
    dashboard.freeze = (0, 0)
    for c, label in enumerate(["KPI", "Value", "Target", "Status", "Result"], 1):
        dashboard.put(7, c, label, "head")
    for i, name in enumerate(names, 8):
        dashboard.heights[i] = 22
        dashboard.put(i, 1, name, "kpi")
        dashboard.put(i, 8, None, "calc", f=f'=IF($B$4="","",MATCH($B$4&"|"&A{i},\'KPI Summary\'!$S$4:$S${last},0))')
        def lookup(c):
            return f"INDEX('KPI Summary'!${c}$4:${c}${last},$H{i})"
        dashboard.put(i, 2, None, "calc_r", f=f'=IF($B$4="","",IF({lookup("G")}="","Not measured",{lookup("G")}))',
                      fmt='0.00' if M.metric_name(name) == "Velocity" else '0.00"%"')
        dashboard.put(i, 3, None, "calc", f=f'=IF($B$4="","",IF({lookup("H")}="","Not set",IF({lookup("I")}="Min","At least ","At most ")&{lookup("H")}'
                      + ('&""' if M.metric_name(name) == "Velocity" else '&"%"') + '))')
        dashboard.put(i, 4, None, "calc", f=f'=IF($B$4="","",{lookup("J")} )')
        dashboard.put(i, 5, None, "bar", f=f'=IF(ISNUMBER(B{i}),REPT("█",ROUND(MIN(B{i},100)/100*12,0)),"")',
                      gf=f'=IF(ISNUMBER(B{i}),SPARKLINE(B{i},{{"charttype","bar";"max",MAX(100,B{i});"color1",IF(D{i}="Met","#38761d","#cc0000")}}),"")')
    dashboard.when(8, 4, 16, 4, '=D8="Met"', fill="C6EFCE", color="006100")
    dashboard.when(8, 4, 16, 4, '=OR(D8="Above maximum",D8="Below minimum")', fill="FFC7CE", color="9C0006")
    dashboard.put(19, 1, "KPI Summary contains the calculation and notes. Yellow cells there and in the registers remain editable.", "note")
    dashboard.put(21, 1, "Periods retained", "label")
    dashboard.put(21, 2, len(periods), "data_r")
    dashboard.put(22, 1, "Earlier periods retain their last computed result. Refresh a period to recompute it from its sources.", "note")

    overview = M.Tab("Period Overview")
    overview.put(1, 1, "KPI results by period", "title")
    overview.put(2, 1, "Newest first. Filter the Period column to narrow the history. Blank evidence stays Not measured; rates are not added together.", "sub")
    overview.merges = []
    overview.heights.update({1: 28, 2: 32, 4: 50})
    columns = ["Period", *names, "Computed as of"]
    for c, label in enumerate(columns, 1):
        overview.put(4, c, label, "head")
        overview.widths[c] = 31 if c == 1 else 15
        if M.metric_name(label) == "Task Comprehension":
            overview.widths[c] = 18
    overview.freeze = (4, 1)
    for row, p in enumerate(reversed(periods), 5):
        overview.heights[row] = 26
        overview.put(row, 1, p["name"], "kpi")
        for c, name in enumerate(names, 2):
            pos = f'MATCH($A{row}&"|"&{M.col(c)}$4,\'KPI Summary\'!$S$4:$S${last},0)'
            value = f"INDEX('KPI Summary'!$G$4:$G${last},{pos})"
            overview.put(row, c, None, "calc_r", f=f'=IF({value}="","Not measured",{value})',
                         fmt='0.00' if M.metric_name(name) == "Velocity" else '0.00"%"')
            helper = c + len(columns)
            overview.put(row, helper, None, "calc", f=f"=INDEX('KPI Summary'!$J$4:$J${last},{pos})")
            overview.when(row, c, row, c, f'=${M.col(helper)}{row}="Met"', fill="C6EFCE", color="006100")
            overview.when(row, c, row, c, f'=OR(${M.col(helper)}{row}="Above maximum",${M.col(helper)}{row}="Below minimum")', fill="FFC7CE", color="9C0006")
            if helper not in overview.hidden_cols:
                overview.hidden_cols.append(helper)
        overview.put(row, len(columns), (ctx.get("period_as_of") or {}).get(p["name"], ""), "data")
    overview.filter_range = (4, 1, max(5, len(periods)+4), len(columns))
    return dashboard, overview
