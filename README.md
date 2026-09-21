# KPI Copilot

Prepare project KPIs by asking your AI assistant. KPI Copilot reads the task tracker and
sources you choose, calculates nine measures, and creates a workbook with explanations,
evidence links and questions for your review.

**New here? Start with [Your first KPI run](docs/02-Start-Here.md).** It explains what to
install, what to have ready, and what to say to your assistant.

[Documentation](docs/README.md) · [Installation](docs/12-Installation.md) ·
[Fictional sample files](samples/README.md) · [Field guide](docs/16-Configuration-Field-Guide.md) · [Help](docs/14-Troubleshooting.md)

## Is it a skill, a plugin, or a repository?

KPI Copilot is a Python tool with three **skills**: instructions that teach an assistant how
to set it up, prepare KPIs, and add tracker support. A **plugin** bundles those instructions
with the code. This **repository** is the complete source folder, including documentation,
examples and tests.

You choose one way to use it:

| Your assistant | How to start | Clone the repository yourself? |
|---|---|---|
| Codex, Cursor, Claude Code, or another assistant that can run local commands | Open a local copy and ask it to set up KPI Copilot | Yes, or download and extract the ZIP |
| Claude Code with plugin installation available | Install `kpi-copilot` from this repository's `pm-tools` marketplace | No; the installer downloads the plugin. Python setup is still needed |
| Claude Desktop or another assistant with local MCP support | Connect the local runner after creating a project profile | Yes, or use a local ZIP copy |
| Browser chat | Use an approved Python/file workspace with exports, if available | Upload the source archive; ordinary chat alone cannot run it |

**You do not need all these routes.** A plugin does not install Python or sign in to your
accounts. MCP is an optional connection that lets an assistant call the same tool; the
repository does not ship a hosted service. Follow the [installation guide](docs/12-Installation.md)
for exact steps and client limitations.

## What you need

- One supported AI assistant with permission to run the tool or use its local connection.
- Python and the small dependency set, installed once by you, your assistant or IT.
- A project in Asana, Jira or GitHub, or a CSV export from another tracker.
- A reporting period and agreement on what your team considers delivered.
- A private folder for your saved settings and results.

A plan, estimates sheet, Google account and PMS access are needed only for the features you
choose. **PMS** means your organization's project-management system where results may be
submitted; a local review workbook works without a PMS connection.

## Your first request

After [installation](docs/12-Installation.md), send:

> Set up KPI Copilot for my project [name]. My tracker is [link or export], and I want KPIs
> for [period]. We estimate in [hours or story points]. Propose the counting rules in plain
> English and ask me about anything you cannot determine. Save my profile outside the
> repository. Start with a local review workbook and do not submit to PMS.

The assistant saves your **profile**—the settings for your projects—and prepares a
**KPI Tracker workbook**. Correct its proposal, answer any open questions, and review the
values and notes. Next time, ask it to refresh the same project using that profile.

## What the results include

Velocity, Task Comprehension, Client Expectation, Delivery Commitment, Defect Rate, Escaped
Defect Rate, Defect Rejection Rate, Rework Rate and CR Rate. See the [plain-language
explanation](docs/01-Overview.md) of each.

The workbook includes a dashboard, task and defect registers, KPI notes and Open Questions.
Yellow cells accept review edits. Output is a local Excel file by default; a dedicated Google
Sheet can be updated at the same link when configured and connected.

Missing evidence is **Not measured**, with a reason. Normal runs read only your tracker and
named sources. Tracker access is read-only. Sending to PMS requires your explicit approval
of the current preview in the conversation.

## Try it before connecting your project

Open the [sample pack](samples/README.md) for ready-made workbooks, a client/project folder
layout, and an explanation of how fictional events become KPI values and notes.

Ask your assistant to run the [fictional offline example](docs/12-Installation.md#try-the-fictional-example).
It needs no tracker, Google or PMS login. It produces a draft with example questions so you
can see the review process before supplying real work data.

## For maintainers

Read the [assistant instructions](AGENTS.md), [design principles](docs/00-Philosophy.md),
[architecture](docs/06-Architecture.md) and [contributor guide](docs/07-Extending.md).
[Validation evidence](docs/11-Audit.md) distinguishes local tests from live-service and client
acceptance. Keep private profiles, exports, screenshots and generated records outside this
repository. Examples are fictional.

**Scripts move data. The assistant judges. A person decides.**
