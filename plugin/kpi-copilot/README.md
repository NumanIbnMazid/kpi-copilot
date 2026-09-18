# KPI Copilot

Prepare Enosis PMS project KPIs from whatever issue tracker a team already uses, with a link
behind every judgement and notes a person can read, then push to PMS after approval.

Full documentation is one level up, in `KPI Copilot/docs/`. Start with `01-Overview.md`.

## Install

No public marketplace, and none needed. From the parent folder, which carries a private
marketplace manifest:

```bash
claude plugin marketplace add "/path/to/KPI Copilot"
claude plugin install kpi-copilot@enosis
```

Or without installing: `claude --plugin-dir ./plugin/kpi-copilot`.
Or auto-loading for one person: copy this folder to `~/.claude/skills/kpi-copilot/`.

```bash
pip3 install pyyaml openpyxl jsonschema
```

## Skills

| Skill | Use it to |
|---|---|
| `/kpi-copilot:kpi-setup` | Check prerequisites, interview, write the profile and the workbook |
| `/kpi-copilot:kpi-run` | Prepare, review and deliver KPIs for a project (review in chat or in the sheet) |
| `/kpi-copilot:kpi-adapter` | Add support for a tracker that has none |

## Layout

```
kpi-copilot/
├── skills/         kpi-setup, kpi-run (+references), kpi-adapter
├── scripts/        preflight, kpi_engine, workbook, pms_push, kpi_registry,
│                   profile_tool, profile_lib, validate_kif, release, selftest
├── adapters/       asana, jira, csv, _contract.md
├── schemas/        kif.schema.json, profile.schema.json, kpi_registry.default.json
└── examples/       northwind-q3   Asana, hours, push after approval
                    acme-jira    Jira via CSV, story points, review-only
                    multi-account  one lead, two clients, two trackers, one profile
```

## The shape of a run

```
tracker -> adapter -> KIF -> engine -> workbook + notes -> PMS
(varies)  (small)   (fixed) (fixed)      (varies)        (gated)
```

Only the ends vary. The counting rules live in one place so two leads get the same number for
the same situation.

## Try it without any setup

```bash
python3 scripts/kpi_engine.py --kif examples/northwind-q3/run.kif.json \
  --profile examples/northwind-q3/profile.yaml --reasons examples/northwind-q3/reasons.yaml

python3 adapters/csv/extract.py --profile examples/acme-jira/profile.yaml \
  --project acme-identity --out /tmp/acme.kif.json
python3 scripts/kpi_engine.py --kif /tmp/acme.kif.json --profile examples/acme-jira/profile.yaml
```

Two different stacks, one engine.

## Check the tool itself

```bash
python3 scripts/selftest.py
```
