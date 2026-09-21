# Fictional sample workspace and workbooks

[Documentation](../docs/README.md) · [First run](../docs/02-Start-Here.md) ·
[Field explanations](../docs/16-Configuration-Field-Guide.md)

**Everything in this folder is training data.** Client names, people, tickets, dates, values
and source records are invented. Operational links use example domains and do not point to
real projects. The workbooks were generated offline using KPI Copilot's own writers; they
are draft reviews, not approved submissions.

## Download and inspect

| File | What it demonstrates |
|---|---|
| [Northwind Profile Workbook](workbooks/Northwind%20-%20Profile%20Workbook.xlsx) | Hours, board history, mapped estimates/timeline, defect policy and field descriptions |
| [Northwind KPI Tracker](workbooks/Northwind%20-%20KPI%20Tracker.xlsx) | Two release periods, calculated results, editable inputs, example context notes and unresolved questions |
| [Acme Profile Workbook](workbooks/Acme%20-%20Profile%20Workbook.xlsx) | A simpler tracker-only CSV project using story points |
| [Acme KPI Tracker](workbooks/Acme%20-%20KPI%20Tracker.xlsx) | Sprint results and honest Not measured outcomes where an export lacks history |

GitHub may offer **Download raw file** for `.xlsx` files. Open them in Excel or a compatible
spreadsheet application with calculation enabled. Formula cells recalculate on opening;
a file preview that does not calculate Excel formulas may show blank results. KPI Summary
also includes **Computed by the run** for comparison.

The **Profile Workbook** configures a project; its sheets include a description beside each
setting. The **KPI Tracker** reviews the results. They are separate files with different
purposes. Editing a Profile Workbook requires an explicit import into `profile.yaml`.

## What the folders look like after setup

This is a supported layout with **one profile per client**. `workspace/` supplies the inputs;
running a copied sample creates the marked runtime files.

```text
KPI Work/                                      private root you choose
└── clients/
    ├── northwind/                             one fictional client
    │   ├── profile.yaml                       settings for this client's projects
    │   ├── KPI Profile Workbook.xlsx          optional configuration workbook
    │   └── northwind-q3/                      project id from the profile
    │       ├── inputs/                        chosen local source files
    │       │   ├── board.json                 offline tracker snapshot
    │       │   ├── estimates.csv              approved additions and effort
    │       │   └── timeline.csv               planned/actual delivery events
    │       ├── facts/                         durable project facts
    │       │   ├── plan.yaml                  fictional agreed scope
    │       │   ├── periods.yaml               dates, effort and period context
    │       │   └── reasons.yaml               source-grounded example explanations
    │       ├── KPI Tracker - Northwind Demo Release.xlsx   created by a run
    │       ├── ledger.json                    saved judgements, created by a run
    │       ├── sheet_state.json               review baseline, created by a run
    │       ├── next.json                      outstanding work, created by a run
    │       ├── cache/                         fetched records, created by a run
    │       ├── judge/                         batch review files, created by a run
    │       └── runs/2026-09-18/                output snapshot, created by a run
    └── acme/
        ├── profile.yaml
        └── acme-identity/
            └── inputs/board_export.csv        CSV-only starting point
```

A second project for Northwind gets a second project entry in that client's profile and a
sibling project folder. **The runner puts project folders directly beside the profile.**
It does not create client folders merely because `accounts` exists in the YAML.

Alternatively, keep one profile at your private root with several accounts/projects. Its
project folders will be siblings at that root. The account field controls inherited settings
and source scope; it is not a filesystem instruction. See
[accounts and projects](../docs/reference/02-accounts-and-projects.md).

## Inputs you can read

- [Northwind profile](workspace/clients/northwind/profile.yaml),
  [board snapshot](workspace/clients/northwind/northwind-q3/inputs/board.json),
  [estimates](workspace/clients/northwind/northwind-q3/inputs/estimates.csv),
  [timeline](workspace/clients/northwind/northwind-q3/inputs/timeline.csv).
- [Plan facts](workspace/clients/northwind/northwind-q3/facts/plan.yaml),
  [period facts](workspace/clients/northwind/northwind-q3/facts/periods.yaml),
  [example note context](workspace/clients/northwind/northwind-q3/facts/reasons.yaml).
- [Acme profile](workspace/clients/acme/profile.yaml) and
  [CSV export](workspace/clients/acme/acme-identity/inputs/board_export.csv).

The Northwind plan facts are authored training inputs, not a digest of an external PDF.
No real document or live tracker was read to create these samples.

## Try the samples

Ask your assistant:

> Copy samples/workspace to a new folder outside the repository. Use its Northwind profile
> and supplied board snapshot to prepare the offline draft as of 2026-09-18. Explain the
> open questions without inventing answers, and show me the workbook.

For an operator on macOS/Linux, from the repository root with dependencies installed:

```bash
mkdir -p "$HOME/KPI Work"
cp -R samples/workspace "$HOME/KPI Work/sample-workspace"
.venv/bin/python plugin/kpi-copilot/scripts/kpi.py run \
  --profile "$HOME/KPI Work/sample-workspace/clients/northwind/profile.yaml" \
  --project northwind-q3 \
  --board "$HOME/KPI Work/sample-workspace/clients/northwind/northwind-q3/inputs/board.json" \
  --today 2026-09-18 --offline
.venv/bin/python plugin/kpi-copilot/scripts/kpi.py run \
  --profile "$HOME/KPI Work/sample-workspace/clients/acme/profile.yaml" \
  --project acme-identity --today 2026-09-18 --offline
```

Choose a new copy destination if it already exists. On Windows, use PowerShell's `Copy-Item
-Recurse` and `.\.venv\Scripts\python.exe`; see the [Windows installation example](../docs/12-Installation.md#try-the-fictional-example).
The Northwind board is deliberately supplied with `--board`: its fictional tracker ID cannot
be fetched from a real service. Acme reads only its local CSV.

To reproduce the four downloadable workbooks without changing any source fixtures:

```bash
.venv/bin/python samples/build_samples.py --out /absolute/path/to/sample-output
```

The builder copies fixtures to temporary storage and invokes the shipped CLI in offline
mode. It preserves the review gaps rather than marking the sample approved. Its output
folder receives four workbooks only. To create your own setup, start a new private profile;
do not put real work data into this sample folder.

## Read the story behind the numbers

Continue with [the sample walkthrough](WALKTHROUGH.md): why a task was counted, why a bug was
excluded, why a note was added, and when a configuration change is appropriate.

## What was checked

The samples were rebuilt offline on 21 September 2026. Both Profile Workbooks import into
valid profiles, retaining their configured values (schema defaults can be added and empty
optional lists omitted). All 36 KPI results match the engine after LibreOffice recalculation,
with no formula errors. Workbook layouts were rendered and inspected. These checks do not
establish live tracker, Google Sheets or PMS connectivity, and the samples remain drafts.
