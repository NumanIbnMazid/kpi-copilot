# Writing and refreshing Google Sheets

Use `kpi.py run` to build the review workbook. Do not rebuild tabs, paste tables or upload a
replacement manually. The runner uses the same workbook model for local Excel and Google.

| Profile setting | Meaning |
|---|---|
| `output.workbook: xlsx` | Local output at `<profile folder>/<project id>/KPI Tracker - <name>.xlsx` |
| `output.workbook: google-sheets` | Local output plus connected Google delivery |
| `output.workbook_file` | The dedicated Google Sheet link or ID to update |
| `output.workbook_location` | A Drive folder for first creation; the saved destination ID pins later runs |
| `output.workbook_name` | Name used for creation/discovery; can include `{project}` |

The current runner still writes local output for legacy `workbook: none`. A Drive folder
setting does not move that local file. Use a dedicated KPI Sheet; an unrelated reference
workbook is not a safe destination.

## Connect and verify

From the plugin root, using the configured Python environment:

```bash
python3 scripts/kpi.py auth --profile /absolute/path/profile.yaml --project sample-release
python3 scripts/kpi.py doctor --profile /absolute/path/profile.yaml --project sample-release
```

The authentication command reports available routes and what each requires. For browser
sign-in, an approved OAuth client must already be configured. The person grants consent;
the assistant never handles tokens, service-account keys or consent on their behalf.
Google account access in an assistant's UI does not automatically connect the Python runner.
A supported host transport is a separate integration route, not a generic login shortcut.

## Preserve the review before writing

The runner reads supported yellow inputs before rebuilding managed tabs. User-added tabs
are retained when they do not use managed tab names. Publication validates the write and
reads it back; do not call delivery complete based only on a local file or attempted write.

When an existing Google review sheet cannot be read, it cannot safely be replaced using
an older local copy. Follow the reported stop or separate-preview path, restore access, and
rerun against the authoritative review. A local preview is not evidence of synchronization.
Do not suggest **Import → Replace spreadsheet** to work around a failed connection.

## Google connected through the assistant's host

The existing spreadsheet can be updated through a connected Google Drive/Sheets tool,
without putting credentials in the local runtime. Use the normal model and writer:

1. Read live spreadsheet metadata including conditional formats. Save its structured JSON
   response to a private `metadata.json`. Read CellData for the populated review tabs,
   including hidden row identities, and save the full structured response to `review.json`.
   Include `formattedValue,userEnteredValue,effectiveValue,effectiveFormat.numberFormat`; do not carry the grid through
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

## Common issues

| Situation | Action |
|---|---|
| 404 / cannot find sheet | Confirm the selected account can access the exact sheet or folder. |
| 403 / permission denied | Confirm editor rights for output and appropriate API access. |
| Formula/locale problem | Inspect the actual error and locale; do not change values to hide it. |
| Expected local edits did not win | Check whether the configured Google sheet is the authoritative review surface. |
| A manual tab conflicts with a managed name | Recover it from version history if needed and rename it before rerunning. |
| Push says review changed | Refresh the authoritative workbook, reconcile the changed result and review again. |

For user-facing instructions see
[Daily use](https://github.com/NumanIbnMazid/kpi-copilot/blob/main/docs/04-Daily-Use.md) and
[review preservation](https://github.com/NumanIbnMazid/kpi-copilot/blob/main/docs/15-Review-and-connected-delivery.md).
