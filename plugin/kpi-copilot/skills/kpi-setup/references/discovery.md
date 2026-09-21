# Discover the workflow before proposing settings

Use the configured adapter to collect a board snapshot on disk. Follow the setup skill and
read its compact outputs; do not browse cards one by one or pass the whole board through
conversation. For an unsupported tracker, start with a CSV export or the adapter skill.

## What to establish

| Setting | Evidence needed |
|---|---|
| `conventions.key_pattern` | The identifier convention in the collected records |
| `workflow.*.values` | Observed states, plus the person's agreement on what delivery and closure mean |
| `conventions.defect_by` | The field, issue type, label or title pattern actually used for reports |
| `conventions.exclude_patterns` | Explicit patterns for grouping and administrative records; inspect excluded results |
| `conventions.cr_marker` | The agreed marker for approved additional scope, not every request for a change |
| Estimate fields and units | The tracker or named source carrying the approved hours or story points |
| `periods.model` | The reporting groups and their known boundaries |
| `conventions.client_names` | Confirmed client-side participants; ask if roles are not established |

An observed state name is evidence of a workflow, not proof of a promise. Do not assume that
Ready for QA, Done or Closed is always the right delivery event.

## What the shipped readers can contribute

- **Asana:** fields, sections/status changes, completions and comments, subject to access and
  the selected options. Unchanged history may be reused from cache.
- **Jira:** workflow history, comments, types, resolution and estimates. The reader converts
  native original-estimate seconds to hours. Confirm configured point fields and scope.
- **GitHub:** issue history and, when configured and available, Projects status/number fields.
  Do not treat it as inherently history-free. Unsupported history must be reported.
- **CSV:** fields present in the export, without native event history or comments. An explicit
  delivered column can help with dates, but does not recreate all missing evidence.

Consult each adapter README for limits. There is no guaranteed number of measurable KPIs
for an arbitrary export.

## Propose a mapping for correction

For a fictional example:

> The collected records use Backlog, In Progress, In Test and Done. I propose In Test as
> delivery and Done as final closure, if the team's promise is to hand completed development
> to QA. Bugs are issue type Bug; Improvements remain visible but do not count as defects.
> Sprint Goal records are excluded. Please correct the delivery promise or any mapping.

Distinguish observations from assumptions. Ask one grouped set of questions about unresolved
agreement: the promised outcome, scope source, who agreed dates, client handover, missing
estimates and output destination. Keep proposed rules reviewable before saving the profile.
Use [the fictional worked example](worked-example.md) for a complete configuration story.
