# KPI Copilot

Ask your assistant to prepare a project's KPIs. It reads your tracker and the sources you
choose, calculates nine measures, explains the results, and updates an editable review
workbook. You decide whether to enter the results yourself or approve sending them to PMS.

**Scripts move data. The assistant judges. A person decides.**

[![Verify KPI Copilot](https://github.com/NumanIbnMazid/kpi-copilot/actions/workflows/test.yml/badge.svg)](https://github.com/NumanIbnMazid/kpi-copilot/actions/workflows/test.yml)
[Project board](https://github.com/users/NumanIbnMazid/projects/18) ·
[Start here](docs/02-Start-Here.md) · [Audit and evidence](docs/11-Audit.md)

## What it does

- Reads Asana, Jira Cloud/Server/Data Center, GitHub Issues with optional Project fields,
  or a CSV export. Tracker access is read-only.
- Supports several projects and clients in one profile, including hours or story points,
  release cycles or recurring periods, and project-specific delivery and defect policies.
- Reads only the plan, estimates and timeline you name. Mail and chat are outside a normal
  run; you can explicitly authorize a focused search for unresolved questions.
- Keeps judgements with their reasons. Changed evidence reopens an assistant's judgement;
  a person's correction takes precedence.
- Writes one formatted `.xlsx`, or updates one Google Sheet. Formulas, frozen headings,
  editable yellow cells, evidence links, a dashboard and open questions support review.
- Preserves edits to both the result summary and context, reads the authoritative sheet
  again before every push, and keeps measurement follow-ups in Open Questions. See
  [review and connected delivery](docs/15-Review-and-connected-delivery.md).
- Reports missing data as **Not measured**. A first draft may contain flagged proposals;
  resolve the review queue before sending values to PMS.

The nine KPIs are Velocity, Task Comprehension, Client Expectation, Delivery Commitment,
Defect Rate, Escaped Defect Rate, Defect Rejection Rate, Rework Rate and CR Rate. PMS targets
can vary by project. Local review targets are supported and clearly labelled; they do not
change PMS. See [workflow settings](docs/05-Adapting-To-Your-Workflow.md).

## Use it in your assistant

The shared Python engine is the product; skills and the optional MCP connection are ways
for an assistant to drive it. No particular AI vendor is required.

| Environment | Route |
|---|---|
| Assistant with command and file access | Open this repository; follow `AGENTS.md` and ask for setup or a run |
| Desktop assistant supporting local MCP | Connect `scripts/mcp_server.py` to a configured profile; [instructions](docs/03-Prerequisites.md) |
| Browser assistant with a Python/code workspace | Upload a repository archive and approved source exports; run the same offline pipeline |
| Browser chat without execution or a runtime connection | Can discuss/review results; cannot execute this tool by itself |

The MCP bridge uses local stdio. A hosted, authenticated remote service for browser-only
clients is not shipped. The [audit](docs/11-Audit.md) separates protocol tests from individual
host and live-service acceptance.

## Try the fictional example

The assistant can do this setup for you. From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp -r plugin/kpi-copilot/examples/northwind-board /tmp/kpi-demo
.venv/bin/python plugin/kpi-copilot/scripts/kpi.py run \
  --profile /tmp/kpi-demo/profile.yaml --project northwind-q3 \
  --board /tmp/kpi-demo/board.json --today 2026-09-18 --offline
```

Open the workbook printed by the command. **NEXT** names the remaining assistant judgements,
person questions, or source repairs. A normal run is one command; judgement is one batch.
Every run prints measured timings. First reads, provider rate limits, document digestion and
human review take longer than a cached calculation; no fixed completion time is promised.

For your own project, say:

> Set up KPI Copilot for my project. Inspect the available tracker, propose the delivery
> states and defect policy, and ask me only what you cannot determine. Start with a review
> workbook. Do not read mail or chat unless I ask.

Setup starts from a small profile. A second project adds a row and only the settings that
actually differ. You normally work with **the profile and the review workbook**; the tool
maintains its cache and evidence files.

## Optional Claude plugin

```bash
claude plugin marketplace add /absolute/path/to/kpi-copilot
claude plugin install kpi-copilot@pm-tools
```

Other assistants can read the same three Markdown skills under `plugin/kpi-copilot/skills`.
A plugin install is a cached copy; see [releasing changes](docs/07-Extending.md).

## Documentation

[Overview](docs/01-Overview.md) · [Setup](docs/02-Start-Here.md) ·
[Prerequisites and MCP](docs/03-Prerequisites.md) · [Daily use](docs/04-Daily-Use.md) ·
[Workflow settings](docs/05-Adapting-To-Your-Workflow.md) ·
[Architecture](docs/06-Architecture.md) · [Extending](docs/07-Extending.md) ·
[Rollout](docs/08-Rollout-Playbook.md) · [FAQ](docs/09-FAQ.md) ·
[Setup conversation](docs/10-Setup-By-Conversation.md) · [Audit](docs/11-Audit.md) ·
[Philosophy](docs/00-Philosophy.md)

## Verify changes

```bash
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python plugin/kpi-copilot/scripts/selftest.py
```

The suite includes full formula evaluation and failure-path regressions; missing formula
dependencies fail the check. For the optional MCP bridge, use Python 3.10+ and also run:

```bash
python -m pip install -r requirements-mcp.txt
python plugin/kpi-copilot/tests/verify_mcp.py
```

Examples are fictional. Profiles, source exports, credentials and generated project records
belong in private workspaces, outside the published repository.
