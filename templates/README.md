# Workbooks and templates

[Documentation](../docs/README.md) · [Sample pack](../samples/README.md)

For ready-to-open examples, use the [four fictional workbooks](../samples/README.md#download-and-inspect).
They include two configuration workbooks and two KPI Tracker workbooks, with a matching
client/project folder layout and an explanation of the sample results.

- **KPI Profile Workbook:** editable settings for the tool. After editing it, ask the
  assistant to import and validate it; the YAML profile is what a run actually reads.
- **KPI Tracker:** calculated results and review inputs for one project. Yellow review
  cells are read back during the next run. Grey formula cells are calculated.

## Generate a fresh profile workbook

These are optional commands for the assistant or a maintainer. Run from the repository
root after [installation](../docs/12-Installation.md). On Windows, replace `.venv/bin/python`
with `.\.venv\Scripts\python.exe`. Replace `/private/kpi-work` with a real private folder
outside this repository, and create that folder first.

```bash
.venv/bin/python plugin/kpi-copilot/scripts/profile_tool.py init --out /private/kpi-work/profile.yaml
.venv/bin/python plugin/kpi-copilot/scripts/workbook.py build --profile /private/kpi-work/profile.yaml --out "/private/kpi-work/KPI Profile Workbook.xlsx"
```

The starter is a setup scaffold; fill it with your actual project settings before a run.
Build from an existing private profile to get its filled-in workbook instead.

## Regenerate the committed samples

```bash
.venv/bin/python samples/build_samples.py --out samples/workbooks
```

This uses only synthetic local inputs and the shipped workbook writers. It rebuilds the
four files in `samples/workbooks/`. See the [sample README](../samples/README.md) for copying
the fictional workspace and running it yourself without an account connection.

Create live KPI Trackers with `kpi.py run`; do not assemble or upload their tabs manually.
The [daily-use guide](../docs/04-Daily-Use.md) explains review edits and Google output.
