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
| `output.workbook_location: <folder link or id>` | The first run creates `[KPI Tracker] <project>` there; later runs find it by name |
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

## Google not connected?

Nothing breaks. The run writes the local workbook and says so. To get it into the same
Google Sheet without any credential:

> Open the Google Sheet > **File > Import > Upload** the .xlsx > **Replace spreadsheet**.

The link stays the same, and the dashboard's bars come alive: they are written the way
Google itself exports a SPARKLINE, so Excel shows a text bar and Google shows the real one.

## If something looks wrong

| What you see | Why, and what to do |
|---|---|
| `#ERROR!` or `#NAME?` in grey cells of an existing sheet | The spreadsheet's locale uses `;` between arguments. File > Settings > Locale > United States (or UK), run again. A sheet the tool creates is set correctly |
| "Google cannot find that file (404)" | Signed in as a service account that the file is not shared with. Share the file or folder with its address |
| "may not do that (403)" | Viewer rights only. Ask the owner for Editor |
| A tab the person built is gone | It had the same name as one the tool owns (Dashboard, Config, Periods, Task Register, Defect Register, KPI Summary, Open Questions, Run Log, PMS Push Log, Read Me). Version history has it; rename theirs |
| "Since the last run" says the sheet changed | Somebody edited a yellow cell after the run. Run again before pushing |
