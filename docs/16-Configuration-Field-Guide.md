# Configuration fields explained

[Documentation](README.md) · [Sample workspace](../samples/README.md) ·
[Full field reference](reference/all-fields.md)

You can describe changes to your assistant without editing YAML. This guide helps you
understand its proposal and read the sample profiles. The schema-generated
[full reference](reference/all-fields.md) lists every accepted field; the topic references
explain adapter limits and advanced settings.

## The three kinds of information

| Information | Where it belongs | Example |
|---|---|---|
| A repeating project rule | `profile.yaml` | “Ready for QA means delivered” |
| A fact about one period or item | Project facts or a yellow review cell | “This release reached the client on 12 August” |
| A calculation | The shared engine and grey formula cells | Delivered estimates summed for Velocity |

An exceptional manually recorded KPI value belongs in the dedicated override fields with
a reason. Do not replace a grey formula or change the rule to obtain a better score.

## Basic profile fields

These are configuration examples, not real project details.

| Field | Meaning and example | How to configure it |
|---|---|---|
| `profile_version` | The configuration format, currently `"1.0"` | Leave the template value |
| `owner.name` | Who owns the setup, e.g. `Sample Lead` | Use the responsible lead in your private profile |
| `owner.timezone` | The profile's stated local timezone | Agree the reporting date convention; verify adapter date handling at boundaries |
| `organization.pms_base_url` | PMS deployment address | Leave blank for a review-only start without PMS |
| `organization.kpi_registry` | Path to the definition/target cache | Default `kpi_registry.json` sits beside the profile; refresh from authorized PMS data when available |
| `projects[].id` | Stable short project handle, e.g. `northwind-q3` | Use it with `--project`; it also names the project folder |
| `projects[].name` | Display name in the workbook | Use a clear project name |
| `projects[].tracker_ref` | Actual board ID, Jira key or GitHub repository | Copy from the selected tracker during setup; sample IDs are not live |
| `projects[].pms_project_id` | PMS destination project number | Needed for submission, not a local draft |
| `projects[].velocity_unit` | `Estimated Hours` or `Story Points` | Choose the unit of the agreed estimates |
| `projects[].account` | Account/client entry to inherit from | Optional; it does not create a client folder |
| `projects[].overrides` | Settings different for this project | Put only differences here |

A private `profile.yaml` can live anywhere readable by the runner. Relative source/cache
paths resolve against that profile's folder where supported. Use `where.py` and the resolved
project view to check paths instead of assuming they are under the installed plugin.

## Tracker and naming

| Field | Meaning | Example or caution |
|---|---|---|
| `tracker.adapter` | Which reader to use | `asana`, `jira`, `github`, or `csv` |
| `tracker.url` | Tracker base address | Required for Jira's selected deployment; not a ticket URL |
| `tracker.estimate_field` | Field holding estimated effort | `Estimated Time`; confirm the adapter's units |
| `tracker.story_point_field` | Field holding points | `Story Points` |
| `tracker.options.file` | CSV input location | `acme-identity/inputs/board_export.csv` relative to the profile |
| `tracker.options.columns` | Explicit export-column mappings | `period: Sprint` maps the CSV's Sprint header |
| `conventions.defect_by` | How defect records are identified | For example `issue-type` with `defect_values: [Bug]`; check adapter support |
| `conventions.exclude_patterns` | Title patterns for non-delivery records | Anchor narrowly; `^QA Checklist` is safer than a broad `^Bug` exclusion |
| `conventions.cr_marker` | Marker for approved additions | `change-request` in the CSV example; a marker still needs the team's agreed meaning |
| `conventions.client_names` | Names identifying client-side reporters | Must match the approved tracker evidence; never infer a person's role from a guess |
| `conventions.assignee_include` | Restrict a mixed board to named assignees | Explicit case-insensitive display-name list; excluded and unassigned rows stay visible |
| `conventions.additional_request_label` | Wording for changes in notes | `Additional Request`; the internal KPI identifiers remain unchanged |

See [tracker and conventions](reference/03-tracker-and-conventions.md) and the relevant adapter
README before using less common options. A field's presence in the schema does not establish
support in every reader.

## Workflow: explain the promise before choosing a state

```yaml
workflow:
  delivered_when:
    signal: status-entered
    values: [Ready for QA]
  closed_when:
    values: [Closed]
  reopened_when:
    values: [In Progress, Testing Failed]
    ignore_first_qa_fail: true
  clarification_when:
    values: [Awaiting Feedback]
    also_comments: true
    exclude_reasons: [build, environment, access]
  commitment:
    scope: committed-only
    met_when: delivery
```

| Field | What it means |
|---|---|
| `delivered_when` | The observed event that counts as delivery. Choose your team's actual agreement, not a universally prescribed column |
| `closed_when` | The event considered finished for relevant closure/QA checks; it may differ from delivery |
| `reopened_when.values` | States indicating work resumed after the agreed closure boundary |
| `reopened_when.closed_values` | Optional separate closure boundary for rework, when different from final completion |
| `ignore_first_qa_fail` | Keeps ordinary testing before closure distinct from reopening after closure |
| `clarification_when` | Evidence that the client had to explain requirements; an access/environment block alone is not that |
| `commitment.scope` | `committed-only` counts actual commitments; choose `all-deliverables` only if the team committed to that whole scope |
| `commitment.met_when` | The configured promise wording/meaning; named delivery, handover and completion behavior needs matching evidence. Arbitrary prose does not create a new event detector |

An effective-date mapping (`from_date` and `fallback_values`) can distinguish an old process
from a new one. Check its impact on a known period. See [workflow reference](reference/04-workflow.md).

## Sources and effort

| Field | Meaning | Example |
|---|---|---|
| `sources.mode` | Source policy | `tracker-only` avoids external documents; `tracker-first` uses the named supporting sources |
| `sources.plan` | Agreed baseline source | A named PDF, mapped table, local file, or `kind: none` |
| `sources.estimates` | Approved addition estimates | The Northwind CSV maps ticket, title, development/QA hours and approval date |
| `sources.timeline` | Planned/actual date events | A mapped table with event type, period, actual date and state |
| `map.columns` | Source column names for tool fields | `dev_hours: "Dev (h)"` reads the column headed Dev (h) |
| `sources.hours_first` | Which effort source wins | `plan` for signed plan estimates; `tracker` for a board-only workflow |
| `sources.hours_basis` | Whether to add QA effort | `dev+qa` credits item QA only when its completion is evidenced |
| `sources.team_hours_when` | When shared period effort is credited | Optional `handover` when that is the agreed boundary |
| `sources.evidence_channels` | Allowed places for requested gap follow-up | A list of scoped tool IDs; normal runs do not search them |
| `scan` | Limits and preferences for supported readers/follow-up | Read the [implementation limits](reference/09-scan-and-source-of-truth.md); not every field is an API filter |

A tool entry describes a source; listing it does not grant access or trigger a read. A PDF's
digest needs the fingerprint printed by the runner. The sample's plan facts are explicitly
fictional; no external PDF is required to reproduce them.

## Periods, defect policy and output

| Field | Meaning | How to decide |
|---|---|---|
| `periods.model` | Reporting grouping such as Sprint, Month or Delivery cycle | Match how the team actually reports; naming alone does not create missing dates |
| `periods.by_ancestor` | Map parent-container titles to periods | Useful when milestone calendars overlap |
| `periods.client_check_default` | `Delivery` or `Handover` | Match what the client expected by the recorded date |
| `policy.count_observations` | Include observations in Defect Rate | Default false; record a different agreed policy explicitly |
| `policy.count_improvements` | Include improvements in Defect Rate | Default false |
| `policy.count_pre_existing` | Include defects already in the product | Default false; excluded reports remain visible |
| `policy.count_post_release` | Include post-release defects in Defect Rate | Default true; release-based measures still need release evidence |
| `output.mode` | Review or submission workflow | Start with `review-only` |
| `output.workbook` | Local `xlsx` or additional `google-sheets` output | The current runner always writes a local workbook, including legacy `none` |
| `output.workbook_file` | Dedicated Google Sheet to update | Use its approved link/ID; do not use a valuable reference workbook |
| `output.workbook_location` | Google Drive folder for sheet creation | It does not relocate the local project folder or connect SharePoint |
| `output.workbook_name` | Name for a created Google Sheet | Can contain `{project}` |
| `targets.<kpi>.value` and `.why` | Labelled local review target and rationale | Reconcile/remove before PMS submission |
| `custom_instructions.notes_style` | Instructions for readable notes | For example, explain delivery impact and do not name individuals |

Shared defaults are overridden first by the account and then by the project. Dictionaries
merge; lists replace. Use `profile_lib.py` to view the resolved result. The
[full reference](reference/all-fields.md) also identifies legacy settings whose current
runtime behavior differs from their older intent.

## Facts and workbook fields

| Field or column | Meaning | Where to change it |
|---|---|---|
| Period start/end | Reporting boundaries | Periods tab or agreed `facts/periods.yaml` |
| Client expected date | A date agreed with the client | Record the evidence; do not substitute an internal plan revision |
| Team committed date | Date the team actually promised | Only records in the commitment population should receive one |
| Handover date | When the client received the release | Periods tab or a mapped completed timeline event |
| Development / QA estimate | Estimated work in the agreed unit | Source correction or supported yellow override |
| Understood / reopened / existing / rejected | Evidence-based judgements | Register yellow cells or the assistant's review queue |
| Numerator / denominator | The actual population behind a ratio | Computed; inspect inputs rather than typing over it |
| Value / target / status | Result, comparison bar and outcome | Computed; target source must remain visible |
| Result summary | What was measured and what the result means | Editable yellow summary; renewed review if facts change |
| Why / context | Relevant events, causes and delivery impact supported by evidence | Editable yellow context or `facts/reasons.yaml` |
| Set value by hand / Why set by hand | Exceptional recorded result with justification | Dedicated yellow override fields |
| Open Questions answer | Your missing fact or decision | Answer in chat or the yellow answer cell, then refresh |

An empty input means unknown unless that field explicitly defines another meaning. Zero
means an observed zero. “Not measured” preserves that difference. See the
[sample walkthrough](../samples/WALKTHROUGH.md) for events mapped to results and notes.

## Make a change safely

Ask the assistant to show the current value, proposed value, reason and expected effect.
Change one fact or the narrowest profile scope, validate the profile, rerun and inspect the
comparison. For a Profile Workbook edit, explicitly import it before running. For a KPI
Tracker edit, ask for a refresh so its supported yellow cells are read back.
