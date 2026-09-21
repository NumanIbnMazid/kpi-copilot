# Introduce KPI Copilot to a team

[Documentation](README.md) · [Overview](01-Overview.md) · [First run](02-Start-Here.md)

Use a small pilot to check whether people can install, configure, review and repeat a KPI
run with their actual tools. The [fictional sample pack](../samples/README.md) is a useful
first demonstration. It does not prove that a company's accounts or workflows are connected.

## Agree on ownership first

| Decision | What to agree |
|---|---|
| Owner | Who maintains the tool, resolves setup problems and reviews updates? |
| Counting rules | Which delivery, closure, defect and scope definitions does the team approve? |
| Targets | Who maintains PMS targets and checks that the cached registry is current? |
| Assistant | Which approved assistant can run local Python or connect to the local MCP server? |
| Access | Who grants tracker access, optional Google access and optional PMS editing rights? |
| Storage | Where do private profiles, source documents, review workbooks and backups live? |
| Delivery | Start with local review files; enable Google Sheets or PMS only when needed. |

Use the assistant people already have where it meets the prerequisites. This repository
ships a Claude Code plugin and a local runner usable by other assistants; it does not
require one vendor's subscription. API access, OAuth registration and organizational
approval can take longer than installing Python dependencies.

## Run a pilot

1. **Show a fictional result.** Open the sample Profile Workbook and KPI Tracker. Explain
   which one holds settings and which one holds results. Walk through a missing value and
   its Open Question as well as a measured value.
2. **Choose representative projects.** Include a workflow with date changes or approved
   additions, and a CSV workflow if anyone depends on exports. Start with one known period.
3. **Set up with the project lead.** Use the [first-run guide](02-Start-Here.md). Ask the lead
   to confirm delivery, scope, estimates and commitments; do not infer agreement from a label.
4. **Compare with a reviewed calculation.** Resolve differences in inputs or interpretation.
   Do not adjust numbers to match expectations. Check the notes, including Met results.
5. **Refresh and correct.** Edit a yellow review cell, rerun, and verify the correction
   survives. If using Google Sheets, verify the same sheet and its current edits are retained.
6. **Practice delivery.** Review a PMS preview if PMS is in scope. Submit only after explicit
   approval, and check read-back. A local-only pilot can finish without PMS access.
7. **Hand over.** A second person should be able to find the private profile, read its
   workbook, and repeat the run with the agreed assistant.

Set your own time budget for the pilot. API speed, source size, missing evidence and review
work affect elapsed time; the repository does not guarantee a fixed setup or run duration.

## Decide whether to expand

Track the time from the first request to a reviewed workbook, not just script execution.
Record setup blockers, incorrect mappings, unanswered questions, notes needing revision,
manual export effort and whether a second lead could repeat the process. Confirm the
review workbook is readable and useful to its intended audience.

Expand to one client account before a wider rollout. A profile may hold several projects;
use separate client folders and profiles when that makes access and handover clearer. See
the [sample folder layout](../samples/README.md#what-the-folders-look-like-after-setup).

## Problems to expect

| Situation | Response |
|---|---|
| Values differ from a familiar report | Compare the included rows, dates, estimates and denominators. Record the agreed rule. |
| Several values are Not measured | Inspect the missing evidence. Native adapters can expose more history, but cannot supply an agreement nobody recorded. |
| No native adapter exists | Start with a mapped CSV export; measure its actual coverage before promising a KPI set. |
| A project needs a different target | Use its PMS target, or a labelled local review target with a reason. Local overrides block PMS submission until reconciled. |
| Targets changed in PMS | Refresh and review the registry; the normal run does not synchronize it automatically. |
| A schedule is requested | Schedule draft preparation only. PMS submission still requires conversation approval. |
| Only one person can operate it | Resolve access, storage, documentation and ownership before expanding. |

Budget for assistant licensing where applicable, setup support, provider permissions,
maintenance and review time. The [audit](11-Audit.md) is historical evidence, not a claim
that every current client or live provider has passed acceptance.
