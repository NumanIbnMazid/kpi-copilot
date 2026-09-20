# The KPI sheet in Google Sheets

The run writes the workbook itself, in both places. You never paste into a sheet, build a
tab or fix formatting by hand; if you find yourself doing that, stop and read this.

## How it works

`scripts/sheet_model.py` describes the workbook once - tabs, cells, styles, live formulas,
dropdowns, colour rules. Two writers render the same description:

- `sheet_xlsx.py` - always, to `<project>/KPI Tracker - <name>.xlsx`
- `sheet_google.py` - when `output.workbook` is `google-sheets`, straight through the Sheets
  API, in one atomic update. Same spreadsheet every run, so the link never changes:

| Profile setting | What happens |
|---|---|
| `output.workbook_file: <link or id>` | That Google Sheet is updated in place |
| `output.workbook_location: <folder link or id>` | The first run creates `[KPI Tracker] <project>` there; the saved destination ID pins later runs to it |
| neither | Local workbook only |

Tabs the tool owns are rebuilt; tabs a person added are left alone. Whatever was typed into
yellow cells is read back **before** the rebuild and kept.

## Connecting Google (once, by the person)

```bash
python3 scripts/kpi.py auth google
```

It opens a consent page and stores a refresh token in `~/.config/kpi-copilot/`, readable
only by them. It needs an OAuth client of type *Desktop app* saved as
`~/.config/kpi-copilot/google_client.json` - one client is enough for a whole company, and
an internal (Workspace) app needs no review. For a scheduled, unattended run use a service
account instead: put its key at `~/.config/kpi-copilot/google_service_account.json` and
share the Drive folder with the account's address.

`python3 scripts/kpi.py doctor --profile … --project …` says whether Google is connected.
Never handle the token or key yourself.

## Google connected through the assistant's host

The existing spreadsheet can be updated through a connected Google Drive/Sheets tool,
without putting credentials in the local runtime. Use the normal model and writer:

1. Read live spreadsheet metadata including conditional formats. Save its structured JSON
   response to a private `metadata.json`. Read CellData for the populated review tabs,
   including hidden row identities, and save the full structured response to `review.json`.
   Include `formattedValue,userEnteredValue,effectiveValue`; do not carry the grid through
   the assistant's conversation. Use the existing sheet baseline to determine the bounds.
2. Run `kpi.py run --profile … --project … --review-file review.json --no-publish` with
   the source arguments for the requested period. This consumes the live edits first.
3. Run `sheet_bridge.py prepare --project-dir <private project folder> --metadata metadata.json
   --review review.json --out update.json`. It refuses a snapshot not consumed by that run.
4. Relay `update.json` unchanged to the host's Sheets batch-update tool. It contains one
   atomic update built by `sheet_google.py`, targeting the configured permanent file ID.
5. Read all written review inputs and every period's KPI Summary as CellData, with effective
   values/errors, into `verified.json`. Run `sheet_bridge.py accept --project-dir …
   --plan update.json --verified verified.json`. It verifies inputs, all KPI results and
   formula errors before saving the Google destination and edit baseline.

When consolidating older per-period workbooks, `sheet_bridge.py import-period --project-dir …
--review <source CellData JSON>` retains their live inputs/questions alongside saved engine
runs. It refuses changed register membership. Preserve source workbooks in an archive until
the combined workbook is verified. Never replace the entire spreadsheet through File Import:
that can remove tabs added by the person.

## Continuing history

`workbook_history.json` retains period inputs/results separately from individual run payloads.
A refresh replaces the matching start/end date pair; a new period is added once. Dashboard
shows one chosen period; Period Overview has one filterable row per period, newest first.
Register and summary filters expose the evidence without a separate set of tabs each week.
Historical review edits stay scoped to that period. Refresh the historical period from its
sources to recompute its saved result. Include the year when labels would otherwise repeat.

## If something looks wrong

| What you see | Why, and what to do |
|---|---|
| `#ERROR!` or `#NAME?` in grey cells of an existing sheet | The spreadsheet's locale uses `;` between arguments. File > Settings > Locale > United States (or UK), run again. A sheet the tool creates is set correctly |
| "Google cannot find that file (404)" | Signed in as a service account that the file is not shared with. Share the file or folder with its address |
| "may not do that (403)" | Viewer rights only. Ask the owner for Editor |
| A tab the person built is gone | It had the same name as one the tool owns (Dashboard, Config, Periods, Task Register, Defect Register, KPI Summary, Open Questions, Run Log, PMS Push Log, Read Me). Version history has it; rename theirs |
| "Since the last run" says the sheet changed | Somebody edited a yellow cell after the run. Run again before pushing |
