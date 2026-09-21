# Your first KPI run

[Documentation](README.md) · [Install](12-Installation.md) · [Help](14-Troubleshooting.md)

**Use this guide first.** KPI Copilot helps an AI assistant turn your project records into
KPIs—key performance indicators—with explanations you can review. You talk to the assistant;
it runs the tool and maintains the workbook.

For example, you can ask it to prepare September's KPIs for a Jira project, review what it
counted, answer a missing handover date, and refresh the same workbook next month.

## 1. Understand what you are installing

| Term | In everyday language |
|---|---|
| **Repository** | The complete project folder on GitHub: code, instructions, examples and tests. Cloning means downloading a working copy that can receive updates |
| **Plugin** | An installable package containing KPI Copilot's code and skills. This repository includes a Claude Code plugin |
| **Skill** | Instructions for your assistant. `kpi-setup` handles setup, `kpi-run` prepares and reviews KPIs, and `kpi-adapter` helps add tracker support |
| **Python** | The program that runs the calculations and creates the workbook. It must be available wherever the tool runs |
| **MCP connection** | An optional way for an assistant to call the local tool. It is useful for desktop chat that cannot run commands directly |
| **Profile** | Your saved project settings: tracker, sources, rules and output destination. The assistant creates this file for you |
| **PMS** | Your organization's project-management system where reviewed KPIs may be recorded. Connecting it is optional for local review |

Installing only a skill does not connect your accounts or install the calculation tool.
You need the code, Python and a way for your assistant to run it.

## 2. Choose one installation route

| You use | Choose this route |
|---|---|
| Codex, Cursor, Claude Code, or another assistant with local file and command access | **Local folder:** clone or download this repository, install its dependencies, then open it in your assistant |
| Claude Code and want reusable plugin skills | **Claude Code plugin:** install from the repository marketplace. You do not need to clone it manually; Python and dependencies are still required |
| Claude Desktop with local MCP support | **Local connection:** install the repository, create your profile with a shell-capable assistant or IT, then connect MCP |
| An assistant that only runs in a browser | A Python/file workspace may run uploaded code and exports. Plain chat without that capability cannot run KPI Copilot; use a local route |

Follow [Install KPI Copilot](12-Installation.md) for the exact clone, ZIP and plugin steps.
Then use [Connect your assistant](13-Assistant-Connections.md) if needed. You do not have to
install a plugin as well as opening the repository.

If your assistant can already run local commands, send:

> Help me install KPI Copilot from https://github.com/NumanIbnMazid/kpi-copilot.
> Follow its installation guide, check Python and dependencies, and run the fictional
> offline example. Tell me where the tool and demo workbook are saved.

**Ready to continue when:** the assistant can run the example and show its workbook.
A plugin appearing in a menu alone does not prove the runner works.

## 3. Bring the minimum information

Choose one project and, preferably, a finished period you know well.

| Have ready | Example |
|---|---|
| Project and tracker | “Northwind Booking, Jira project NW” and its link, or an exported CSV |
| Reporting period | “Sprint 14, 1–14 September” or “the Q3 release” |
| Estimate unit | Hours or story points; say if estimates are unavailable |
| Meaning of delivered | “Accepted by QA” or “the build reached the client”; ask for a proposal if unsure |
| Sources you want read | The board alone, or specific plan, estimates and timeline files |
| Output choice | Start with a local Excel workbook, or name a dedicated Google Sheet/folder |

You need read access to the chosen tracker or export. Google access is needed only for
Google sources or output. You can start without PMS, a plan PDF, or an estimates sheet;
measures without enough evidence will say **Not measured**. The full
[prerequisite checklist](03-Prerequisites.md) explains the optional connections.

Your private profile and results must live outside the tool's repository or installed plugin.
For example, keep them in a separate `KPI Work` folder in Documents. The
[fictional sample pack](../samples/README.md) shows a root → client → project layout and
includes ready-to-open configuration and KPI workbooks.

## 4. Ask the assistant to set up your project

Copy this and replace the bracketed parts. Omit sources you do not use.

> Set up KPI Copilot for [project name]. The tracker is [link or export], and the first
> reporting period is [name and dates]. We estimate in [hours/story points].
>
> Use [the board only / these specific plan, estimates and timeline files]. Start with a
> local review workbook. Check access, explain my connection choices, and propose the
> delivery states, defect exclusions and counting rules in plain English. Show how parent
> tasks, subtasks and approved additions will be counted once.
>
> Save my profile in [private folder]. Ask me only about gaps or decisions I need to make.
> Do not search email or chat, and do not submit to PMS.

The assistant checks the available evidence and proposes settings for you to correct.
Use the [field guide](16-Configuration-Field-Guide.md) to understand a setting or the
[sample walkthrough](../samples/WALKTHROUGH.md) to see why a rule or note was chosen.
For example: “Accepted tickets count as delivered. Velocity uses their story points.
Pre-existing bugs are listed but excluded from Defect Rate. Client handover is a separate date.”

Being signed in to an AI app does not automatically connect its local runner to Jira, Asana,
Google or PMS. If needed, the assistant offers supported sign-in choices. You handle browser
consent or enter a token privately; never paste passwords or tokens into chat.

**Ready to continue when:** you have agreed on the proposal, the connection check succeeds
or an export is available, and the assistant gives you the saved profile's location.

## 5. Prepare and review the workbook

> Prepare KPIs for [project and period] using my saved profile. Update the review workbook,
> explain the results from the evidence, and show all remaining questions together.

The assistant prepares the draft and reviews uncertain classifications in a batch. It asks
you for facts the records cannot establish, such as whether a date was agreed or when the
client received the build. A first draft with questions is expected.

Open these tabs in order:

1. **Dashboard and KPI Summary:** values, targets and explanations.
2. **Open Questions:** facts or decisions still needed.
3. **Task Register and Defect Register:** what counted, what was excluded and the evidence.

Answer in chat or edit the yellow input cells, then ask the assistant to refresh. It reads
those edits before rebuilding. Grey cells are formulas; correct the inputs that feed them.
Review notes for every KPI, including “Met” and “Not measured,” so someone unfamiliar with
the project can understand what happened. Reasons must come from evidence.

For example, “42 of 50 planned story points were delivered” states the result. “The export
feature moved after the client changed its format” adds useful context **only if the sources
support it**. The assistant should ask when the cause is unknown.

**The first run is complete when:** you have reviewed the workbook against the known period,
understand unresolved limits, and know where the profile and output are saved.

## 6. Decide how to use the results

You can keep the workbook, copy reviewed results into PMS yourself, or use a dedicated Google
Sheet that the tool updates in place. Google output needs a connection and edit access; use a
separate output sheet so the original reference workbook is preserved.

To submit through the assistant, first ask:

> Show the exact values and notes you would send to PMS for [project and period].

After checking the preview, explicitly approve it in the conversation. The assistant must
verify the saved results after sending. A local workbook does not prove Google Sheets or
PMS was updated. See [daily use](04-Daily-Use.md) for corrections and delivery details.

## 7. Next time, ask for a refresh

> Refresh KPIs for [project and period] using the profile at [saved location]. Update the
> same workbook and show what changed or still needs my answer.

You do not repeat the setup interview. The tool reuses decisions while their evidence remains
valid. A new period, changed board structure or different source may need an update.

For other workflows, use the [setup examples](10-Setup-By-Conversation.md). If a step fails,
start with [troubleshooting](14-Troubleshooting.md). Routine runs are designed to be short;
connection setup, source changes, provider limits and review can add time.
