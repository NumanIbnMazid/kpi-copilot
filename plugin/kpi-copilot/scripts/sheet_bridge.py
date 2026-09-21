"""File-backed Google connector publishing using the same workbook writer.

No credentials or workbook contents need to pass through the assistant's context.
Save connector metadata/CellData responses to disk, run with --review-file first,
then relay the generated batch requests and verify the resulting CellData on disk.
"""
import argparse
import hashlib
import json
from pathlib import Path

import sheet_google as G
import sheet_model as M
import sheet_readback as R
import workbook_history as H


def import_period(project_dir, review):
    """Recover live review fields from an older per-period workbook during migration.

    Source registers must match saved engine row identities. Unexpected additions or
    missing rows stop the migration rather than silently dropping somebody's work.
    """
    doc = G.connector_doc(review)
    grid = G.connector_grid(review, doc["spreadsheetId"])
    history = H.load(project_dir)
    entries = history["periods"]
    imported = []
    for r in range(5, grid.rows("Periods")+1):
        name = grid("Periods", r, 2)
        if not name:
            continue
        period = {"name": name, "start": R._iso(grid("Periods",r,3)), "end": R._iso(grid("Periods",r,4))}
        key = H.period_key(period)
        if key not in entries:
            raise ValueError("A source period has no saved engine run. Recover that run before consolidating.")
        e = entries[key]
        old_name = e["period"]["name"]
        e["period"].update(period)
        for c, (field, _, _, role, _) in enumerate(M.PERIOD_COLS,1):
            if role == 'in':
                e['period'][field] = R._iso(grid('Periods',r,c))
        e['result']['period'] = name
        for kind, tab, cols in [('tasks','Task Register',M.TASK_COLS),('defects','Defect Register',M.DEFECT_COLS)]:
            headers = {grid(tab,3,c):c for c in range(1,60) if grid(tab,3,c)}
            ids = headers.get('Row ID')
            if not ids:
                raise ValueError("Source register has no row identities.")
            rows = {str(grid(tab,rr,ids)):rr for rr in range(4,grid.rows(tab)+1) if grid(tab,rr,2)==name}
            expected = {str(x.get('_row') or x.get('_item')) for x in e[kind]}
            if set(rows) != expected:
                raise ValueError("Source register membership changed. Refresh that period before consolidating.")
            for item in e[kind]:
                rr = rows[str(item.get('_row') or item.get('_item'))]
                item['period'] = name
                for field, label, _, role, _ in cols:
                    if role != 'in' or label not in headers or field in ('client_expected','team_committed'):
                        continue
                    value = R._iso(grid(tab,rr,headers[label]))
                    if field == 'planned': value = value == 'Yes'
                    elif field == 'phase': value = R.PHASE_IN.get(value,value)
                    elif field == 'final_status': value = R.FINAL_IN.get(value,value)
                    elif field in ('story_points','hours_dev','hours_qa') and value is not None: value = float(value)
                    item[field] = value
        e['questions'] = []
        for rr in range(4,grid.rows('Open Questions')+1):
            if grid('Open Questions',rr,2)==name:
                e['questions'].append({k:grid('Open Questions',rr,c) for k,c in
                    [('about',2),('question',3),('proposal',4),('answer',5),('asked_on',6),('id',7)]})
        for rr in range(4,grid.rows('KPI Summary')+1):
            if grid('KPI Summary',rr,1)!=name: continue
            metric=grid('KPI Summary',rr,3)
            e.setdefault('reasons',{})[metric]=grid('KPI Summary',rr,13) or ''
            manual=grid('KPI Summary',rr,17)
            if manual is not None:
                e.setdefault('manual',{})[metric]={'value':float(manual),'why':grid('KPI Summary',rr,18) or ''}
        e['as_of'] = next((grid('Config',rr,3) for rr in range(1,grid.rows('Config')+1)
                           if grid('Config',rr,2)=='Calculated as of'), e.get('as_of'))
        imported.append(name)
    if not imported:
        raise ValueError('No source periods were found.')
    H.save(project_dir/'workbook_history.json',history)
    return {'imported_periods':imported,'source':doc['spreadsheetId']}


def prepare(project_dir, metadata, review, out):
    model_path = project_dir / "workbook_model.json"
    model = json.loads(model_path.read_text())
    if model.get("review_digest") != hashlib.sha256(review.read_bytes()).hexdigest():
        raise ValueError("Run kpi.py run --review-file with this fresh review snapshot before preparing a write.")
    meta = G.connector_doc(metadata)
    fid = meta["spreadsheetId"]
    configured = G.G.file_id(model["ctx"]["profile"].get("output", {}).get("workbook_file"))
    if configured != fid:
        raise ValueError("Metadata does not match the configured continuing workbook.")
    G.connector_grid(review, fid)
    tabs = M.build(model["kif"], model["results"], model["ctx"])
    have = {s["properties"]["title"]: s for s in meta["sheets"]}
    requests = []
    for i, tab in enumerate(tabs):
        ex = have.get(tab.name)
        sid = ex["properties"]["sheetId"] if ex else G.sheet_id_for(tab.name)
        requests.extend(G.tab_requests(tab, sid, i, ex))
    requests = [r for r in requests if "addSheet" in r] + [r for r in requests if "addSheet" not in r]
    dest = {"kind": "google", "id": fid, "url": meta["spreadsheetUrl"]}
    state = R.snapshot(tabs, dest)
    # One atomic batch prevents an early dashboard from referencing tabs not yet added.
    H.save(out, {"spreadsheet_id": fid, "requests": requests})
    H.save(out.with_suffix(".state.json"), state)
    H.save(out.with_suffix(".model.json"), model)
    return {"request_file": str(out), "periods": len(model["kif"]["periods"]), "requests": len(requests)}


def accept(project_dir, plan, verified):
    state = json.loads(plan.with_suffix(".state.json").read_text())
    model = json.loads(plan.with_suffix(".model.json").read_text())
    fid = state["destination"]["id"]
    grid = G.connector_grid(verified, fid)
    for tab, spec in state["spec"].items():
        actual = R._read(tab, spec, grid)
        if actual != state["values"][tab]:
            # Connector numbers may be formatted strings. Compare using readback's
            # normalized equality at the leaves, retaining blank versus zero.
            def same(a, b):
                if isinstance(a, dict) and isinstance(b, dict):
                    return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
                return equivalent(a, b)
            if not same(actual, state["values"][tab]):
                raise ValueError(f"Written review inputs differ on {tab}; baseline not accepted.")
    doc = G.connector_doc(verified)
    for sh in doc["sheets"]:
        for block in sh.get("data", []):
            for row in block.get("rowData", []):
                for cell in row.get("values", []):
                    if (cell.get("effectiveValue") or {}).get("errorValue"):
                        raise ValueError(f"Formula error on {sh['properties']['title']}; baseline not accepted.")
    # Verify every displayed summary value against the model's expected engine result.
    expected = {(p["period"], m["name"]): m.get("value") for p in model["results"]["periods"] for m in p["measures"]}
    seen = set()
    for row in range(4, grid.rows("KPI Summary") + 1):
        key = (grid("KPI Summary", row, 1), grid("KPI Summary", row, 3))
        if key not in expected:
            continue
        if key in seen:
            raise ValueError("Duplicate period/KPI in published workbook.")
        seen.add(key)
        if not equivalent(grid("KPI Summary", row, 7), expected[key]):
            raise ValueError(f"Published result differs for {key}; baseline not accepted.")
    if seen != set(expected):
        raise ValueError("Verification did not include every period/KPI.")
    R.save_state(project_dir / "sheet_state.json", state)
    H.save(project_dir / "workbook_destination.json", state["destination"])
    next_path = project_dir / "next.json"
    if next_path.exists():
        next_info = json.loads(next_path.read_text())
        next_info.update(sheet=state["destination"]["url"], sheet_pending=False)
        H.save(next_path, next_info)
    return {"verified": True, "periods": len(model["kif"]["periods"]), "url": state["destination"]["url"]}


def equivalent(a, b):
    if a in (None, "") or b in (None, ""):
        return a in (None, "") and b in (None, "")
    return R._same(a, b)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    imp = sub.add_parser("import-period")
    imp.add_argument("--project-dir", type=Path, required=True)
    imp.add_argument("--review", type=Path, required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--project-dir", type=Path, required=True)
    prep.add_argument("--metadata", type=Path, required=True)
    prep.add_argument("--review", type=Path, required=True)
    prep.add_argument("--out", type=Path, required=True)
    done = sub.add_parser("accept")
    done.add_argument("--project-dir", type=Path, required=True)
    done.add_argument("--plan", type=Path, required=True)
    done.add_argument("--verified", type=Path, required=True)
    args = vars(p.parse_args())
    command = args.pop("command")
    print(json.dumps({"prepare":prepare,"accept":accept,"import-period":import_period}[command](**args)))


if __name__ == "__main__":
    main()
