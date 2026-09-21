# Writing and refreshing Google Sheets

Use `kpi.py run` to build the review workbook. Do not rebuild tabs, paste tables or upload a
replacement manually. The runner uses the same workbook model for local Excel and Google.

| Profile setting | Meaning |
|---|---|
| `output.workbook: xlsx` | Local output at `<profile folder>/<project id>/KPI Tracker - <name>.xlsx` |
| `output.workbook: google-sheets` | Local output plus connected Google delivery |
| `output.workbook_file` | The dedicated Google Sheet link or ID to update |
| `output.workbook_location` | A Drive folder for creation/discovery of the named KPI Sheet |
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
