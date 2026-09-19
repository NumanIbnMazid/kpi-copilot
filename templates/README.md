# Templates

The workbooks are **generated**, not committed — a binary in git goes stale the moment the
schema changes, and these are rebuilt from the schema every time.

```bash
cd plugin/kpi-copilot

# A blank profile workbook, to fill in by hand
python3 scripts/profile_tool.py init --out /tmp/blank.yaml
python3 scripts/workbook.py build --profile /tmp/blank.yaml \
  --out "../../templates/KPI Profile Workbook (blank).xlsx"

# The same thing, filled in from an example
python3 scripts/workbook.py build --profile examples/northwind-q3/profile.yaml \
  --out "../../templates/KPI Profile Workbook (filled example).xlsx"

# One lead, two clients, two trackers
python3 scripts/workbook.py build --profile examples/multi-account/profile.yaml \
  --out "../../templates/KPI Profile Workbook (two clients).xlsx"

# The board as the only source of truth, with a bounded scan
python3 scripts/workbook.py build --profile examples/tracker-only/profile.yaml \
  --out "../../templates/KPI Profile Workbook (tracker only).xlsx"

# The KPI tracker sheet, from a whole run on the example board (offline, no credentials)
cp -r examples/northwind-board /tmp/nw
python3 scripts/kpi.py run --profile /tmp/nw/profile.yaml --project northwind-q3 \
  --board /tmp/nw/board.json --today 2026-09-18
open "/tmp/nw/northwind-q3/KPI Tracker - Northwind Q3 Release Items.xlsx"
```

The tracker sheet is a working surface, not a report: grey cells are live formulas, and
whatever is typed into yellow cells is read back by the next run and kept. The same
description is written to a Google Sheet, updated in place, when the profile asks for one.
See [docs/04-Daily-Use.md](../docs/04-Daily-Use.md).
