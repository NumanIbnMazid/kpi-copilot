# Output, and where every file lives

What a run produces, how far it may go on its own, and where everything ends up.

---

## `output`

```yaml
output:
  mode: assisted-push          # review-only | dry-run | assisted-push | auto-push
  unattended: false
  workbook: google-sheets      # google-sheets | xlsx | none
  workbook_location: 1ExampleDriveFolderId000000000000
  workbook_template: 1ExampleTemplateSheetId00000000000000000000
  run_folder: runs
  notify: chat-devqa
```

| Field | What it is |
|---|---|
| `mode` | How far a run may go. See below |
| `unattended` | Allow a scheduled run to push with nobody watching. Only meaningful with `auto-push` |
| `workbook` | `google-sheets`, `xlsx`, or `none` |
| `workbook_location` | **Where the sheet goes**: a Drive folder id, a SharePoint path, or a local folder |
| `workbook_template` | A sheet to copy. Blank builds a fresh one |
| `run_folder` | Where each run's files are kept |
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

### Where to put the sheet

**Google Sheets** — `workbook_location` is the Drive folder id, the part after `/folders/`
in the URL:

```
https://drive.google.com/drive/folders/1ExampleDriveFolderId000000000000
                                        └──────── this ────────┘
```

The run copies `workbook_template` into that folder, or builds a fresh sheet there. You need
Editor rights on the folder — the readiness check asks you to confirm it.

**Excel** — `workbook_location` is a folder path, absolute or relative to the profile.
Relative is usually what you want, so the profile stays portable.

**Neither** — `workbook: none` prints results and writes nothing.

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
├── reasons.yaml                    the "why" text for each note
├── manual.yaml                     values set by hand, with their reasons
└── runs/
    └── 2026-09-19/
        ├── run.kif.json            the extract
        ├── results.json            values, notes, statuses, gaps
        ├── results.md              the readable version
        ├── payloads.json           exactly what would be, or was, sent
        ├── tracker.xlsx            the working file
        └── push_log.json           what was written, and whether read-back agreed
```

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
