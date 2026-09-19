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

# A per-project tracker workbook, from a real run
python3 scripts/kpi_engine.py --kif examples/northwind-q3/run.kif.json \
  --profile examples/northwind-q3/profile.yaml \
  --reasons examples/northwind-q3/reasons.yaml --out /tmp/results.json
python3 scripts/workbook.py tracker --results /tmp/results.json \
  --kif examples/northwind-q3/run.kif.json \
  --reasons examples/northwind-q3/reasons.yaml \
  --profile examples/northwind-q3/profile.yaml \
  --out "../../templates/KPI Tracker (editable example).xlsx"
```

The tracker workbook is a working surface, not a report: yellow cells come back through
`workbook.py review`. See [docs/04-Daily-Use.md](../docs/04-Daily-Use.md).
