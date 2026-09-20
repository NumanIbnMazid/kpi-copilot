# Setup prompts you can adapt

Begin with [Your first KPI run](02-Start-Here.md) if you have not connected the tool yet.
These are fictional examples, not required forms. Describe only the sources and rules your
team actually uses. The assistant proposes a profile and asks about gaps.

## A small tracker-only project

> Set up KPI Copilot for Northwind's booking project. We use Jira, project NW, two-week
> sprints and story points. Accepted tickets count as delivered. The board is the source
> of truth; do not search chat or email. Start with a local workbook that I can review.
> Check access and show me the proposed counting rules before the first run.

The assistant should check the selected tracker, explain what it considers delivered, and
identify any missing period or handover dates. You do not need a plan PDF if the board
already records the agreed scope.

## A project with a plan, estimates and changing dates

> Set up the booking release using this Asana project [link], this plan [file], this
> estimates sheet [link], and this timeline [link]. We measure hours, including estimated
> QA effort. Count each separately estimated deliverable once, even when several share
> a delivery card. Exclude observations, improvements and bugs that already existed.
>
> Development complete and client handover are separate events. Show me how the profile
> will use the feature-freeze date, delivery deadline and actual handover. If sources
> disagree, bring me the specific conflict. Save the output in this dedicated folder
> [link] and update the same KPI Sheet on later runs.

Expect a proposal about which source supplies hours, dates and approval, plus a check that
parent cards and their breakdown are not counted twice. An outdated source can receive a
scoped correction with your reason; the assistant should not silently accept all pending
estimates because one was approved.

## Ongoing engagement rather than a fixed project

> We provide ongoing support for Northwind. There is no final project handover. Report
> monthly, use hours, and count work accepted during that month. Proposed requests stay
> outside approved scope. Help me define the monthly baseline for CR Rate; if there is
> no defensible baseline, show it as Not measured. Do not invent client deadlines.

A recurring engagement still needs an agreed reporting period and counting basis. “No
formal commitment” is a valid answer; it should not produce an invented 100% result.

## Several projects with different rules

> Add a second project to my profile. It uses the same Asana connection and defect policy,
> but velocity uses story points. Its workbook belongs in a different folder [link].
> Keep the first project's hours-based reporting unchanged and show me the differences.

You should only have to explain what differs. Ask to see the resolved configuration if
an inherited setting produces an unexpected result.

## An existing browser login

> I am already signed in to the tracker in [browser and profile]. Check whether this
> assistant can use that session for the supported export route. If it cannot, explain
> the available connection choices. Do not ask me to paste a password or token here.

The assistant must verify access. Having a connector in one AI tool does not necessarily
connect another tool or the local runner. Exports are an alternative when they contain
sufficient history for the KPIs you need.

## A focused exception to the source list

> For the unresolved delivery-date question only, check [specific email thread or chat
> space]. Record the agreed date and evidence. Do not broaden the search to other channels.

This is an exception for that question, not permission to search all communications on
every run. If you want a source read routinely, ask to add it to the saved profile.

## Correcting a result without repeating setup

> This report describes an existing bug. Exclude it from the project's defect count,
> keep its evidence visible, and refresh the workbook.

> The estimate is approved; the source status is outdated. Save that correction for this
> estimate only, with my explanation, then recompute.

> That period's handover was [date]. The deadline did not change. Record the actual date
> without moving the target to make the KPI look better.

The assistant records the answer and recalculates; it should not start a fresh interview
or re-read every board card. For direct workbook edits, use the yellow cells and ask for
refresh. See [Daily use](04-Daily-Use.md).

## If a run is taking too long

> Show the draft and all remaining questions together. Tell me whether the delay is source
> access, processing, judgement or publishing. Reuse unchanged data and decisions. Do not
> open cards individually or search extra sources to fill gaps without asking.

Read failures and missing facts should produce a specific next step. They should not
turn into repeated blind retries or a half-hour tour of the tracker.

Technical field names and examples belong in the [profile reference](reference/README.md).
The assistant's installation and command sequence is in [Technical setup](03-Prerequisites.md).
