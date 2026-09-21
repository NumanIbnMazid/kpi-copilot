# How the fictional events become KPIs

[Sample files](README.md) · [Field guide](../docs/16-Configuration-Field-Guide.md)

These examples describe only the supplied synthetic records. The downloadable workbooks
are first-pass drafts as of **18 September 2026**, with unresolved questions left visible.
Results below are the engine's **Computed by the run** values before further review.

## Northwind: board history, hours and release events

The [profile](workspace/clients/northwind/profile.yaml) uses the plan for development hours,
adds QA effort only after QA is complete, and records delivery at the first configured QA
handoff. The [timeline](workspace/clients/northwind/northwind-q3/inputs/timeline.csv) supplies
actual handover events. Client deadlines and actual handover are different facts.

| What happened in the sample | How it is treated | Where to inspect it |
|---|---|---|
| NW-101's recurring-booking priority was unclear; the client explained it | Client clarification affects Task Comprehension. The context note explains what was unclear | Board comments; Task Register; Initial Scope note |
| NW-105 waited because staging access was unavailable | An environment dependency is not automatically a misunderstood requirement | `workflow.clarification_when.exclude_reasons`; the board comment |
| NW-104 closed on 08/04, reopened on 08/07 after a tablet restart exposed a reset, and closed again on 08/11 | One reopening after closure counts as rework. Two other tasks failed QA before first closure and do not count as rework | Board events; Rework Rate context |
| Bug 04 says `[Exisiting]` | Tolerant reading proposes “Existing” and records the interpretation. Under `count_pre_existing: false`, an accepted existing classification is excluded from Defect Rate | Defect Register and its review evidence |
| Bug 06's duplicate email came from the test harness | The report is rejected as not a product bug; it stays in the reported population for Rejection Rate | Rejected state, comment and context note |
| Bug 08 was reported by the client after the 08/12 handover | It is a post-release report. Its closure on 08/25 is stated, but why QA missed it is not invented | Description, timeline and Escaped Defect Rate note |
| Two additions were approved after the original scope | They count as Additional Requests against the initial baseline | Estimates table and CR Rate |
| One delivered item has no required estimate | Initial Scope Velocity remains Not measured; a missing estimate does not become zero | Open Questions and the effort fields |
| Delivery documentation appears in the plan without a board card | It remains an unresolved delivery question | Plan facts and Open Questions |
| Additional Requests 1 has no recorded client handover | Escaped Defect Rate remains Not measured for that period | Timeline, Periods and Open Questions |

The first-pass Initial Scope results include Task Comprehension **88.89%**, Defect Rate
**33.33%**, Escaped Defect Rate **12.5%**, Rework Rate **12.5%**, and CR Rate **28.57%**.
These are teaching examples, not target recommendations. Review populations and open decisions
before using a draft result. Defect Rate is defects per delivered ticket; it is not the
percentage of tickets containing a bug.

Additional Requests 1 credits **62 estimated hours**: 56 development hours and 6 completed QA
hours. One item's remaining QA estimate is not credited before its closure. That explains
why `hours_basis: dev+qa` does not simply sum every QA estimate in an open period.

## How a context note was added

The [fictional reasons file](workspace/clients/northwind/northwind-q3/facts/reasons.yaml)
adds explanations to the calculated summaries. For Rework Rate, it describes the saved-filter
failure, the closed/reopened dates and the eventual closure. The number comes from the
engine; the context comes from the record of what happened.

For Escaped Defect Rate, the note identifies the export defect and closure date. The reasons
file also says the record does not establish why testing missed it; the writer moves that
missing-evidence statement into **Open Questions**, keeping the result note focused on known
events. It does not blame a person or invent “insufficient testing” as a cause. In a live
run, the assistant proposes context through the review queue or a person edits the yellow
context cell.

## Acme: what a CSV can and cannot show

The [export](workspace/clients/acme/acme-identity/inputs/board_export.csv) records current
state, resolution, story points and sprint. It does not contain status-event history,
clarification outcomes, commitment dates or client handovers.

For Sprint 14:

| Result | Why |
|---|---|
| Velocity: **24 story points** | Four delivered items carry 8, 5, 8 and 3 points; an in-progress 5-point item is not delivered |
| Defect Rate: **50%** | Two included defects divided by four delivered tickets; an improvement and rejected report are excluded |
| Defect Rejection Rate: **25%** | One rejected report out of four total reports |
| CR Rate: **25%** | One labelled addition against four initial tasks |
| Task Comprehension, Client Expectation, Delivery Commitment, Escaped Defect Rate and Rework Rate: **Not measured** | The required discussion, date, release or reopen evidence is absent |

Mapping `period: Sprint` tells the CSV reader which column groups rows. It does not create
historical evidence that is not in the export. “Done” can support the configured completed
work measure without proving when every commitment was met.

## When to change configuration instead of a row

These are hypothetical variations to try **in a copy**; they are not applied to the sample
workbooks above.

| Situation | Appropriate change | Why |
|---|---|---|
| The team renames its QA handoff column | Update `workflow.delivered_when.values`; use an agreed effective-date/fallback rule if the process changed | A repeatable workflow change belongs in the profile |
| The agreement defines delivery as client acceptance | Use the actual agreed acceptance event and review historical impact | “Delivered” must match the promise being measured |
| Only one report was incorrectly marked existing | Correct that report's yellow judgement with evidence | One fact does not justify changing every defect's policy |
| The client changes the approved defect inclusion policy | Update the project-level `policy` and record its rationale; review affected results | It changes the measured population and must be visible |
| One client uses story points while another uses hours | Set each project's `velocity_unit` appropriately | Units should not silently mix |
| A parent groups three delivery tickets under one estimate | Use the documented grouping settings and explicit membership where needed | Count the delivery tickets and retain the group estimate once |
| A lead wants a different review target | Add a local target with a reason, or refresh the official PMS target | Keep the calculated value unchanged; local targets block submission until reconciled |

For each change, ask the assistant to explain the expected effect, update only the relevant
scope, validate, rerun and compare. Never alter a calculated value merely to make a target
look met.
