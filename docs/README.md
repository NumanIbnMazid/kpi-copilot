# Documentation

Start with [Your first KPI run](02-Start-Here.md). You do not need to read every page or
learn the commands to prepare KPIs. The installation and connection pages are also written
for the assistant or IT colleague helping you.

## Get started

| Read this | When you need it |
|---|---|
| [Your first KPI run](02-Start-Here.md) | One path from choosing an installation route to reviewing your first results |
| [What KPI Copilot measures](01-Overview.md) | Understand the product and the nine KPIs |
| [Install KPI Copilot](12-Installation.md) | Clone or download, install Python dependencies, or use the Claude Code plugin |
| [Prerequisites and account access](03-Prerequisites.md) | Check what is required, connect a tracker, and choose optional sources and output |
| [Connect your assistant](13-Assistant-Connections.md) | Open the local folder or configure Claude Desktop, Cursor or Codex with MCP |
| [Setup examples](10-Setup-By-Conversation.md) | Copy a prompt for your kind of project |

## Use and customize

| Read this | When you need it |
|---|---|
| [Daily use](04-Daily-Use.md) | Refresh, correct, review and deliver KPIs |
| [Troubleshooting](14-Troubleshooting.md) | Fix an installation, connection or first-run problem |
| [FAQ](09-FAQ.md) | Answer a specific product or calculation question |
| [Adapt the workflow](05-Adapting-To-Your-Workflow.md) | Change delivery rules, periods, sources, grouping or project settings |
| [Configuration reference](reference/README.md) | Look up a setting and its limits |
| [Review and connected delivery](15-Review-and-connected-delivery.md) | Understand note review, PMS creation and the optional host transport |
| [Fictional sample pack](../samples/README.md) | Download four workbooks, inspect a client/project layout, and follow worked results |
| [Configuration field guide](16-Configuration-Field-Guide.md) | Understand each common setting, workbook field and configuration example |
| [Workbook templates](../templates/README.md) | Generate a fresh profile workbook or rebuild samples |

## Maintain or introduce the tool

| Read this | When you need it |
|---|---|
| [Design principles](00-Philosophy.md) | Understand the binding design decisions |
| [Architecture](06-Architecture.md) | Find the code responsible for each part |
| [Contributing and releases](07-Extending.md) | Add an adapter, edit a skill, test or release |
| [Rollout playbook](08-Rollout-Playbook.md) | Plan a pilot and decide who owns it |
| [Audit and validation evidence](11-Audit.md) | Separate historical checks from outstanding acceptance |
| [Product brief](../PROMPT.md) | Read the requirements, including goals not guaranteed by a release |
| [Assistant playbook](../AGENTS.md) | Drive a KPI run without manually collecting or formatting records |

Existing numbered filenames are retained so earlier links keep working. The tables above
are the reading order; the numbers are not required steps.

## How to read the examples

All projects, people, IDs and work data in examples are fictional. Replace placeholders such
as `[project name]` or `/absolute/path/...` with your own details in a private workspace.
A YAML fragment illustrates settings; it is not necessarily a complete runnable profile.

User guides lead with things to say to your assistant. Technical command blocks state their
working folder. Repository-level examples use `.venv/bin/python` on macOS/Linux; on Windows
use `.\.venv\Scripts\python.exe` for the documented `.venv` setup. Plugin-internal references
use `python` from the configured environment, with `plugin/kpi-copilot` as the working folder.

Installation research was checked against official client, Python and GitHub documentation
on **21 September 2026**. Sources are linked alongside the relevant instructions. Client
interfaces and organization policies may vary; a documented setup path still needs a check
in the client where you will use it.
