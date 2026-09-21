# What KPI Copilot measures

[Documentation](README.md) · [Your first KPI run](02-Start-Here.md)

KPI Copilot prepares project delivery measures from records your team already keeps. It
works through an AI assistant and produces an editable review workbook. You can keep the
workbook, update a dedicated Google Sheet, or approve sending reviewed results to PMS.

The code is distributed as a repository and a Claude Code plugin containing three skills.
See [Start here](02-Start-Here.md) for the difference and the installation route to choose.

## The nine KPIs, in everyday language

| KPI | What it asks | Example evidence needed |
|---|---|---|
| Velocity | How much estimated work was delivered? | Delivered items and estimates in hours or story points |
| Task Comprehension | What share of assessed tasks were understood without client clarification? | Relevant history/comments or a recorded clarification outcome |
| Client Expectation | Were client-prioritized tasks delivered by the agreed expected dates? | Client expectation dates and delivery or handover evidence |
| Delivery Commitment | What share of the team's assessed commitments were kept on time? | A genuine commitment, its date, and the event that fulfills it |
| Defect Rate | How many included defects were found relative to delivered work? | Delivered task population and agreed defect exclusions |
| Escaped Defect Rate | What share of non-rejected defects appeared after release? | Release/handover boundary and report timing |
| Defect Rejection Rate | What share of reported defects were rejected? | All reports and recorded rejection decisions |
| Rework Rate | How many reopening events occurred relative to completed work? | Closure and later reopening history |
| CR Rate | How much did the task scope change relative to the initial task baseline? | Original scope and approved change requests/additions |

CR means change request. Your notes can use “Additional Request” when that is your team's
term. The [counting rules](../plugin/kpi-copilot/skills/kpi-run/references/kpi-rules.md)
explain exact populations, unknown outcomes and exceptions; this table is an introduction.

## What you receive

A dashboard, task and defect registers, one KPI Summary per period, explanations, evidence
links and Open Questions. Yellow cells hold review inputs; grey cells contain calculations.
The tool reads supported edits back before rebuilding the workbook.

The [sample files](../samples/README.md) show this output using fictional data. Their
walkthrough connects particular events to calculations, notes and configuration choices.

## What varies between projects

Your tracker, estimate unit, workflow states, reporting periods, sources, defect inclusion
policy and output destination can differ. Shared calculation logic and evidence requirements
keep those differences visible. A local review target needs a reason and is labelled; it
must be reconciled with PMS before submission. A registry refresh reads current PMS targets.

## What to expect from a run

The tool reads approved sources into files and computes the workbook. The assistant reviews
uncertain decisions in one batch. You answer questions the available evidence cannot settle.
Decisions are reused while valid, and your corrections take precedence.

Missing evidence produces **Not measured**, not a guessed zero. A normal run reads the tracker
and named plan/estimate/timeline sources. Mail and chat require an explicitly scoped follow-up.
No KPI reaches PMS without approval of the current preview in the conversation.

Setup and elapsed time depend on connections, source quality, board size and review. The
runner prints its processing timings; those exclude time spent installing, answering
questions and reviewing. The [audit](11-Audit.md) records specific validation evidence.

Continue with [Your first KPI run](02-Start-Here.md), or use the
[rollout playbook](08-Rollout-Playbook.md) to plan a team pilot.
