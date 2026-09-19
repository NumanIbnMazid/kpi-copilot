# Output, and where every file lives

What a run produces, how far it may go on its own, and where everything ends up.

---

## `output`

```yaml
output:
  mode: assisted-push          # review-only | dry-run | assisted-push | auto-push
  unattended: false
  workbook: google-sheets      # xlsx (default) | google-sheets | none
  workbook_location: https://drive.google.com/drive/folders/1ExampleDriveFolderId000000000000
  # workbook_file: https://docs.google.com/spreadsheets/d/1ExampleSheetId/edit   (instead: update exactly this one)
  # workbook_name: "[KPI Tracker] {project}"
  notify: chat-devqa
```

| Field | What it is |
|---|---|
| `mode` | How far a run may go. See below |
| `unattended` | Allow a scheduled run to push with nobody watching. Only meaningful with `auto-push` |
| `workbook` | `xlsx` (the default): the sheet is written locally. `google-sheets`: a live Google Sheet is **also** kept, updated in place on every run. `none`: results are printed and nothing is written |
| `workbook_location` | A **Drive folder** (link or id). The first run creates the Google Sheet there; later runs find it by name and update it |
| `workbook_file` | A **specific Google Sheet** (link or id) to update in place, instead of creating one. Wins over `workbook_location` |
| `workbook_name` | The name of a sheet the tool creates. `{project}` is replaced. Default `[KPI Tracker] {project}` |
| `notify` | A tool id to post a summary to, or blank |

### The four modes

| Mode | What happens |
|---|---|
| `review-only` | Builds the workbook and a copy-paste block. **Physically cannot write to PMS** |
| `dry-run` | Also computes the payload and shows a field-by-field diff. Still never writes |
| `assisted-push` | The diff, then a question, then the push on an explicit yes |
| `auto-push` | Pushes without asking. Honoured **only** with `unattended: true`; the push script refuses the contradictory combination |

Approval is per run. A yes for one period never carries to the next.

Mode is an account-level override, so one client can be pushed and another typed in by hand.

### Where the sheet goes

**Locally, always.** `<project>/KPI Tracker - <name>.xlsx`, beside the profile, rewritten on
every run, plus a dated copy in the run folder. This is the default and needs no setup.

**And in Google Sheets, if you ask.** Say it once - *"keep the KPI sheet in this Drive
folder"* or *"update this sheet"* - and the profile gets `workbook: google-sheets` with a
folder or a file:

```
https://drive.google.com/drive/folders/1ExampleDriveFolderId000000000000     a folder
https://docs.google.com/spreadsheets/d/1ExampleSheetId0000000000000/edit      one sheet
```

A full link or the bare id both work. Every run then updates **the same Google Sheet, in
place**, in one atomic update - the link never changes, and somebody with it open sees it
change once. The tabs the tool owns (Read Me, Dashboard, Config, Periods, Task Register,
Defect Register, KPI Summary, Open Questions, Run Log, PMS Push Log) are rebuilt; tabs you
add are left alone. Whatever you typed into yellow cells is read back first and kept.

Both are written from one description, so they look the same: navy headers, yellow for what
is yours, grey live formulas, the dashboard with its bars.

It needs Google connected once, by you: `python3 scripts/kpi.py auth google`
([03-Prerequisites](../03-Prerequisites.md)). You need Editor rights on the folder or file.
Without a connection the run still writes the local workbook and says how to put it over
the same Google Sheet by hand: **File > Import > Upload > Replace spreadsheet**.

---

## Where every file lives

```bash
python3 scripts/where.py --profile profile.yaml
```

It prints the resolved path of each file, whether it exists, and the commands to change
something. The layout:

```
<your profile folder>/
├── profile.yaml                    what the tools read
├── KPI Profile Workbook.xlsx       the same thing, for a human
├── preflight.json                  the readiness checklist, with dates
├── kpi_registry.json               KPI definitions and targets, as read from PMS
└── <project id>/                   one folder per project: its memory and its output
    ├── KPI Tracker - <name>.xlsx   the sheet, rewritten every run
    ├── facts/
    │   ├── periods.yaml            the periods: dates, handover, PMS ids, team hours, the story
    │   ├── plan.yaml               the agreed scope: items, hours, milestones (digested once)
    │   ├── estimates.yaml          approved additions
    │   └── reasons.yaml            the "why" text for each note
    ├── manual.yaml                 values set by hand, with their reasons
    ├── ledger.json                 every judgement: the value, who decided, why
    ├── inbox/                      drop an export of a source here when it cannot be fetched
    ├── judge/queue.json            what is waiting for the assistant, if anything
    ├── next.json                   what the last run said comes next
    ├── sheet_state.json            what was written into the yellow cells, for the read-back
    ├── cache/                      the board as last read, and the fetched sources
    └── runs/
        └── 2026-09-19/
            ├── run.kif.json        the judged extract
            ├── results.json        values, notes, statuses, gaps
            ├── report.md           the readable version
            ├── payloads.json       exactly what would be, or was, sent
            ├── tracker.xlsx        that day's copy of the sheet
            └── push_log.json       what was written, and whether read-back agreed
```

`facts/` is plain YAML on purpose - it is the part of a project you actually know, and the
sheet's yellow cells are the same facts seen from the other side. `ledger.json` and `cache/`
are the tool's own; change a judgement in the sheet, not in the file.

Credentials are **never** in this folder. They live in `~/.config/kpi-copilot/`, readable
only by you.

The plugin itself lives separately — `~/.claude/plugins/cache/pm-tools/kpi-copilot/<version>/`
when installed, or wherever you cloned it when running with `--plugin-dir`. **Your
configuration is never inside the plugin**, so updating the plugin never touches it.

### Keeping the run folder

Every run is kept. When two runs disagree, diff the two `run.kif.json` files — the change is
in the input, not in the engine. That is what makes a number questioned in three months
answerable.

### Where to keep the profile

Somewhere your team can read it: a Drive folder, a repo, a shared drive. A profile only one
person can open is a profile that dies when they go on leave.

## `notify`

A tool id from the registry. A run posts its summary there. Leave it blank if you would
rather it said nothing — and note that `custom_instructions.never` can forbid posting to a
client-facing space.
