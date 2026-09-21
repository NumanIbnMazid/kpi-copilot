# Using KPI Copilot week to week

[Documentation](README.md) · [First run](02-Start-Here.md) · [Help](14-Troubleshooting.md)

After setup, start with:

> Refresh KPIs for [project and period] using my saved profile at [location]. Update the
> same workbook, explain what changed, and show any questions that still need my answer.

Name the project and profile, especially when you manage several clients. A reporting period
comes from the project's configured grouping and saved facts; asking for a new period may
require the assistant to add those facts. There is no universal `--period` run option.

## What happens

The runner reads the tracker/export and named sources, reads supported review edits,
classifies the records, computes KPIs and writes the workbook. It prints **NEXT** with any
assistant decisions, person questions, source repairs or publishing problems.

The assistant answers uncertain classifications and reviews notes together. You answer facts
that cannot be established from the sources. Changed evidence can reopen a decision; a
person's correction outranks the assistant and the rules.

Normal runs do not search chat or email. To resolve a specific gap, say:

> Check [named channel] only for the handover date of [period]. Record the answer and its
> evidence link. Ask me if it does not establish the date.

A deep run allows that bounded follow-up; it does not add a general-purpose chat crawler.

## Review the workbook

| Tab | What to use it for |
|---|---|
| Read Me | Understand colors and review instructions |
| Dashboard | Compare periods and see overall results |
| Config | Check the applied settings and KPI definitions |
| Periods | Review dates, handover, shared effort and period context |
| Task Register | Inspect work, estimates, delivery, exclusions and evidence |
| Defect Register | Inspect reports, rejection and inclusion decisions |
| KPI Summary | Review values, targets, statuses, summary and context |
| Open Questions | Answer missing facts and decisions |
| Run Log | Check source coverage and processing time |
| PMS Push Log | See recorded submissions and read-back results |

See the [fictional KPI workbooks](../samples/README.md) and
[field guide](16-Configuration-Field-Guide.md) for examples of individual columns.

Read all notes, including Met and Not measured results. They should explain the result,
relevant events and delivery impact for a person unfamiliar with the project. Unknown causes
become questions; do not add a plausible explanation just to finish the report.

## Correct a fact or judgement

Edit the relevant **yellow** cell, or tell the assistant:

> Ticket [key] was already in the product. Exclude it under our existing defect policy.
> The evidence is [source]. Refresh the workbook and show the effect.

Supported inputs include classifications, periods, estimates, dates, defect decisions,
period facts and note text. Grey formula cells are regenerated; editing them is not a saved
correction. Formula results update in a calculating spreadsheet app, but ask for a refresh
before treating changed results as ready to submit.

KPI Summary keeps the computed and live values visible. If an exceptional manual value is
needed, use **Set value by hand** and **Why set by hand**. The computed figure and reason stay
visible. Prefer fixing the underlying input when possible.

Both note summary and context can be edited. Changed facts or figures require renewed review.
Finish editing before a refresh; concurrent writers to the same profile are not supported.

## Change a recurring setting

> For this project's next run, use [new workflow state] as delivery. Explain how it changes
> the result, then save the agreed setting in my profile.

The **KPI Profile Workbook** is optional configuration, separate from the **KPI Tracker**
review workbook. It can be imported into the profile with `workbook.py read`; it is not
continuously synchronized. Ask the assistant to import, validate and rebuild it after edits.
Changing Config cells in the KPI Tracker is not a substitute for changing the profile.

For sources, grouping, date boundaries and targets, see
[workflow settings](05-Adapting-To-Your-Workflow.md).

## Output and submission

| Mode | Meaning |
|---|---|
| `review-only` | Prepare a workbook; automatic PMS writes are blocked |
| `dry-run` | Prepare/preview submission without writing |
| `assisted-push` | Allow a separate approved submission after review |
| `auto-push` | Legacy setting; still requires explicit conversation approval |

`run` prepares results. A separate `push` command previews them; only `push --apply` sends.
The assistant must show the values and notes and get your explicit approval of that preview.
It reads the configured review sheet again before sending and verifies results afterward.
Creating a missing PMS period needs specific authorization too.

If Google Sheets is configured, its current edits are authoritative. A local preview does
not replace an unavailable Google review. Reconnect before publishing/submitting. Unrelated
Google tabs are preserved; tool-owned tabs are regenerated. Do not manually replace the
whole spreadsheet as a connection workaround.

## Where your files are kept

By default, each project has a folder beside its profile. It contains the KPI Tracker,
facts, saved judgements, cache and dated run folders. The assistant can locate everything
with `where.py`. The [sample workspace](../samples/README.md) shows a client/project layout.

Same-day runs reuse a run folder. Keep separately labelled snapshots when your retention
policy needs every reviewed version; this working folder is not an immutable audit archive.
See [output and files](reference/07-output-and-files.md).

## If a run is slow or incomplete

Ask for source-read, calculation, assistant-review and publication status separately. The
printed command timings cover processing only. API limits, changed documents and unresolved
questions can extend the work. Follow [troubleshooting](14-Troubleshooting.md); avoid repeated
full reads just to apply judgements to an existing snapshot.

## Scheduled drafts

Ask your assistant's scheduler to prepare a review draft for a named profile/project and
report meaningful changes or failures. Scheduling support and persistent credentials depend
on the host. Keep only one writer active. A schedule cannot approve a PMS submission.
