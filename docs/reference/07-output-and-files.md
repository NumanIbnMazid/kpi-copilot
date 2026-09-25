# Output and file locations

[Documentation](../README.md) · [Configuration reference](README.md) · [Sample folders](../../samples/README.md)

## Output settings

```yaml
output:
  mode: review-only
  workbook: google-sheets
  workbook_file: https://docs.google.com/spreadsheets/d/EXAMPLE_OUTPUT_ID/edit
```

The link above is a placeholder. Use an approved dedicated output sheet in a private profile.

| Field | Current behavior |
|---|---|
| `mode` | `review-only` prevents PMS writes; `dry-run` previews; `assisted-push` allows a separate explicitly approved write. Legacy `auto-push` still needs approval |
| `unattended` | Legacy compatibility field; never supplies approval |
| `workbook` | `xlsx` writes locally; `google-sheets` also publishes when connected. The current `kpi.py` always writes a local workbook, even with legacy `none` |
| `workbook_file` | Specific Google Sheet to update; takes priority over folder creation |
| `workbook_location` | Google Drive folder link/ID for creating the output. Does not change local storage or implement SharePoint publishing |
| `workbook_name` | Created Google Sheet's name; default `[KPI Tracker] {project}` |
| `archive` | Folder beside the live Google Sheet (for example `Archived`). Before the sheet is updated, a dated copy is kept there, at most one a day, so the folder shows each earlier state while the live sheet keeps its link |
| `notify` | Preferred notification destination metadata. The Python runner does not send messages; an assistant integration needs explicit authorization |
| `workbook_template` | Legacy metadata; current writers use the shared sheet model rather than copying an arbitrary workbook |
| `run_folder` | Legacy runner setting. Current `kpi.py` uses the profile/project layout below |

`run` prepares results. `push` is a separate preview; `push --apply` requires the person's
explicit approval of the current result. A profile mode cannot provide that approval.

## Local and Google workbooks

The local tracker is `<profile folder>/<project id>/KPI Tracker - <name>.xlsx`, with a
`tracker.xlsx` copy in the dated run folder. The filename is sanitized by the writer; use
the printed path instead of reconstructing it from a name with punctuation.

Google output reuses the saved spreadsheet ID or configured file. Tool-owned tabs are
rebuilt; supported yellow edits are read first, and unrelated tabs are preserved. The API
batch is atomic, but it does not lock out collaborators between read and write. Finish
editing before refreshing.

When Google is authoritative but cannot be read, the tool preserves the previous review
baseline and stops or writes a separate local preview according to the run mode. A preview
is not a substitute for the unavailable review. Reconnect and reconcile before publication
or PMS submission. Do not use “Replace spreadsheet” to bypass this boundary.

See [Google access](../03-Prerequisites.md#google-and-optional-sources) and
[review behavior](../15-Review-and-connected-delivery.md).

## Private project layout

```text
<profile folder>/
├── profile.yaml
├── KPI Profile Workbook.xlsx       optional; imported/exported explicitly
├── preflight.json                  dated readiness confirmations
├── kpi_registry.json               optional private PMS definition/target cache
└── <project id>/
    ├── KPI Tracker - <name>.xlsx
    ├── facts/                      period, plan, estimate and note facts
    ├── manual.yaml                 recorded manual values with reasons
    ├── ledger.json                 saved judgements
    ├── inbox/                      configured source exports when needed
    ├── judge/queue.json             assistant's batch of unresolved calls
    ├── next.json                    work still needed
    ├── sheet_state.json             review read-back baseline
    ├── cache/                      board and source snapshots
    └── runs/<date>/                 results, report, payloads, tracker and push log
```

The [sample workspace](../../samples/README.md) places one profile inside each client folder
to get `root → client → project` organization. A single multi-account profile instead creates
sibling project folders beside that one profile. The `account` field does not change paths.

From the repository root:

Commands below start at the repository root with its Python environment. On Windows,
use `.\.venv\Scripts\python.exe` instead of `.venv/bin/python`. Replace profile paths with
your actual private profile location.

```bash
.venv/bin/python plugin/kpi-copilot/scripts/where.py --profile /absolute/private/path/profile.yaml --project my-project
```

Credentials live separately in the runner's environment or supported credential store,
including `~/.config/kpi-copilot/`. Do not put secrets in profiles or shared workbooks.
Keep all real configuration, source records and generated results outside the published
repository and installed plugin cache.

## Retention and handover

Same-day runs reuse the daily folder. Use a distinct `--date` label to retain separate
snapshots; `--today` controls the calculation date and is a different option. Preserve
reviewed files under your organization's retention policy. These are working records,
not an immutable audit archive.

To hand over a project, securely transfer the private profile, source mappings, project facts
and needed review state. Reconnect accounts under the authorized operator. Do not copy
credentials into the handover workbook.
