# Adapting it to your workflow

[Documentation](README.md) · [Field guide](16-Configuration-Field-Guide.md)

The design assumption is that your workflow is not going to change, and should not have to.
Project-specific behavior lives in the profile. Official targets come from the refreshed
PMS registry; labelled local review targets are also supported. Shared formulas and evidence
requirements keep differences visible.

This document covers what you can change, how, and where the line is.

---

## What you can change

| Tier | What it covers | How it behaves |
|---|---|---|
| **Yours** | Tracker, states, naming, sources, periods, output, house style | Change freely |
| **Yours, in the sheet** | Judgements, item types, periods, hours, dates, the Why text — and any figure, as a recorded hand-set value | Edit the yellow cell. The numbers move at once; the next run reads it back and keeps it |
| **Recorded** | Project facts the defaults get wrong | Allowed, applied, and printed in every run summary |
| **Targets** | Official project targets or labelled local review targets | Refresh the PMS registry for official targets; local targets need a reason and block submission until reconciled |
| **Fixed** | The KPI list, the ids, the counting behind each ratio | Not configurable. This is what makes two projects comparable |

The line is drawn where it is because a Defect Rate of 12% has to *mean* the same thing on two
different projects. Whether 12% is good news can reasonably differ — that is what per-project
targets in PMS are for. How you arrive at 12% cannot.

---

## Several projects, several clients, several trackers

Most leads run more than one project, often across more than one client — Northwind on Asana
and Google Chat, Acme on Jira and Slack. One profile covers all of it.

There are three levels, and each only says what differs from the one above:

| Level | What belongs there |
|---|---|
| **Profile defaults** (top of the file) | How you usually work |
| **Account** | What is true for every project on that client — tracker, chat spaces, conventions, output mode |
| **Project** | What is true for just this one |

Almost everything that varies, varies **per client**, not per project. Northwind's five
projects share one tracker and one set of conventions, so that is said once:

```yaml
accounts:
  - id: northwind
    name: Northwind
    overrides:
      tracker: {adapter: asana, key_field: TKT}
      conventions: {key_pattern: 'TKT-\d+', defect_by: title-pattern}
      sources: {evidence_channels: [chat-northwind-devqa, chat-northwind-mgmt]}

  - id: acme
    name: Acme
    overrides:
      tracker: {adapter: csv, options: {tracker_name: Jira, file: exports/acme.csv}}
      sources: {evidence_channels: [slack-acme]}
      periods: {model: Sprint}
      output:  {mode: review-only}      # this client's numbers are typed in by hand

projects:
  - {id: q3-release, account: northwind, pms_project_id: 101, tracker_ref: "1100000000000001"}
  - {id: gateway,    account: northwind, pms_project_id: 102, tracker_ref: "1100000000000002"}
  - id: acme-identity
    account: acme
    pms_project_id: 201
    velocity_unit: Story Points
```

A single-client profile can omit accounts, but still needs a projects entry. Account
inheritance changes settings, not folder nesting; see the [sample folder layout](../samples/README.md).

### Merge rules

- **Dicts merge, deeply.** Overriding `workflow.delivered_when.values` leaves
  `workflow.closed_when` alone.
- **Lists replace.** Another team's exclusion patterns are *theirs*, not yours plus theirs.
  Accumulating them is how one team's regex quietly eats another team's work.
- **`owner` and `organization` never vary.** They describe you and the company.

### The Tools registry is shared, and scoped

One registry covers everything you work on. Tag each entry with the accounts or projects it
belongs to; anything untagged is shared.

| id | kind | name | accounts | used for |
|---|---|---|---|---|
| pms | pms | PMS | *(all)* | output |
| asana | issue-tracker | Asana | northwind | scope, dates, defects |
| chat-northwind-devqa | chat | Northwind Dev-QA (Google Chat) | northwind | evidence, handover |
| jira | issue-tracker | Jira | acme | scope, dates, defects |
| slack-acme | chat | #acme-delivery (Slack) | acme | evidence, handover |

Scoping is not cosmetic. A run on Acme resolves to Acme's tools only, so it never goes
looking in Northwind's chat for a handover date — and a profile that points one client's
project at another client's chat space fails validation with that sentence, rather than
producing an empty evidence search three weeks later.

### Running one of them

Every command takes `--project`. With several projects, leaving it out is an error naming
the ones it knows, rather than a guess:

Commands below start at the repository root with its Python environment. On Windows,
use `.\.venv\Scripts\python.exe` instead of `.venv/bin/python`. Replace profile paths with
your actual private profile location.

```bash
.venv/bin/python plugin/kpi-copilot/scripts/profile_lib.py --profile profile.yaml --list
```

```
project        account     adapter  PMS    name
q3-release     northwind     asana    361    Northwind Q3 Release Items
gateway        northwind     asana    382    Northwind Gateway Integration
acme-identity  acme        csv      402    Acme Identity Platform
```

Add `--project <id> --section tracker` to see exactly what one project resolves to, which
is the fastest way to answer "why did this run use the wrong board".

### Seeing the drift

The workbook's **Overrides** tab flattens every account's and project's overrides onto one
page: scope, id, setting, value. It is the only place two projects that quietly drifted apart
become obvious. If the same override appears on several projects, it belongs on their account
instead.

A working example is in `examples/multi-account/` — one lead, two clients, two trackers, two
chat tools, two output modes, in one file.

## The profile, and its human face

`profile.yaml` is what the tools read. The **KPI Profile Workbook** is the same information
laid out for a person: one tab per topic, one row per setting, every row with a plain-language
description.

```bash
.venv/bin/python plugin/kpi-copilot/scripts/workbook.py build --profile profile.yaml --out "KPI Profile Workbook.xlsx"
.venv/bin/python plugin/kpi-copilot/scripts/workbook.py read  --xlsx "KPI Profile Workbook.xlsx" --out profile.yaml
```

The workbook is generated from the schema. Import edits explicitly with `workbook.py read`,
validate the profile, then rebuild the companion workbook. There is no continuous sync.
This Profile Workbook is separate from the KPI Tracker used to review results.

Put the workbook where your team keeps things. A profile only one person can open is a
profile that dies when they go on leave.

### The tabs

| Tab | What lives there |
|---|---|
| **Owner** | Who it belongs to |
| **Organization** | The fixed parts. Grey, not yours to edit |
| **Tools** | Where everything lives. The tab people actually use |
| **Tracker** | Which adapter, and which fields it should read |
| **Conventions** | How your team names tickets, defects and non-deliverables |
| **Workflow** | What your states mean. The most important tab |
| **Sources** | Plan, estimates, timeline, evidence channels. All optional |
| **Periods** | How you slice a project |
| **Counting Rules** | The few counting choices a team may make |
| **Output** | What happens with the results |
| **Custom Instructions** | Your own instructions |
| **Accounts** | Your clients. Most of what varies between projects varies here |
| **Projects** | One row per PMS project, pointing at its account |
| **Overrides** | Every way an account or project departs from the defaults, on one page |
| **Prerequisites** | The readiness checklist, with dates |

---

## The Tools tab

This is the one that pays for itself. Each row is a place this project's truth lives, with a
sentence saying what it is for:

| id | kind | name | url or id | description | used for |
|---|---|---|---|---|---|
| tracker | issue-tracker | Asana | app.asana.com/0/1215… | The Northwind boards. Every feature, change request and QA report is a card here, and the card history is what proves a delivery date | scope, dates, defects |
| chat-devqa | chat | Northwind Dev-QA | AAAAexampleDevQA | Day-to-day delivery chatter: builds, QA rounds, environment problems. Best source for when something reached QA | evidence, handover |
| plan-pdf | document | Project Plan | drive.google.com/… | The agreed scope and original milestone dates. When the board and the plan disagree, the plan is what the client signed | scope, estimates |

Two reasons it matters. The assistant uses it to find things without being told each time. And when
somebody new picks up the account, this table is the fastest explanation of the project that
exists — faster than a handover call.

---

## The Workflow tab

What your states mean. This is what turns "a column called In Test" into a number comparable
across the company.

```yaml
workflow:
  delivered_when:
    signal: status-entered
    values: [Ready for QA, Testing, Dev Complete]
    from_date: "2026-09-10"        # the team changed process; before this, use the fallback
    fallback_values: [Dev Complete]
  closed_when:
    values: [Closed]
    completed_flag_means: "On these boards 'complete' means merged, not accepted."
  reopened_when:
    values: [In Progress, Testing Failed]
    ignore_first_qa_fail: true
  clarification_when:
    values: [Awaiting Feedback]
    also_comments: true
    exclude_reasons: [build, environment, access]
```

Three notes worth reading twice:

- **`delivered_when` is not `closed_when`.** They may be the same only when the agreed delivery event is final closure. Choose the
  promise being measured; QA handoff is not a universal definition of delivery.
- **`ignore_first_qa_fail`** is what stops Rework Rate counting normal testing. A QA failure
  while an item is still being tested for the first time is not rework.
- **`from_date`** exists because teams change process mid-project. Without it, a change in
  September retroactively rewrites six months of delivery dates.

---

## Sources: what happens when you do not have one

All optional. If you have no plan PDF, no estimates sheet and no chat history, you still get
KPIs. The ones that depend on a missing source say **"Not measured"** and why.

```yaml
sources:
  plan: {kind: none}
  estimates: {kind: none}
  hours_first: tracker
  hours_basis: dev
```

`hours_first` decides who wins when the plan and the tracker disagree on effort — set it to
`plan` where the plan is what the client signed. `hours_basis: dev+qa` adds each item's QA
hours once that item's QA is finished, so an open cycle is not credited with QA that has not
happened.

---

## Output: how far it may go on its own

```yaml
output:
  mode: assisted-push      # review-only | dry-run | assisted-push | auto-push
  unattended: false
  workbook: google-sheets  # or xlsx, or none
  workbook_location: <Google Drive folder link or id>
  notify: chat-devqa
```

`notify` is metadata; the Python runner does not send messages. An assistant needs explicit
authorization to message a destination. `auto-push` and `unattended` are legacy compatibility settings. They do not authorize a
write. Every submission requires explicit approval of the current preview in conversation.

---

## Custom instructions

Your own instructions, which take precedence over the defaults.

```yaml
custom_instructions:
  notes_style: "Two sentences at most. Name the ticket, never the person. Dates as mm/dd."
  always:
    - "Show the previous period next to the new one so a jump is visible."
    - "Flag any KPI that moved more than 20 points since the last run."
  never:
    - "Never post to the client-facing chat space."
    - "Never push to PMS on a Friday after 5pm Dhaka time."
  glossary:
    - "Handover means the build that reached the client, not the internal release."
  escalation: "Ask me in chat. If I have not answered by the next working day, hold the run."
```

**Style is free.** Say how you want things worded and it is followed.

**The glossary explains project terminology.** It stops a note being technically correct and
still misleading, which is the failure mode nobody catches in review.

### Rule overrides

For project facts the defaults get wrong:

```yaml
  rule_overrides:
    - rule: defect_phase
      value: "Bug 41 = Post-release"
      why: "Steve reported it on 08/20, eight days after the 08/12 handover, so it escaped."
      approved_by: "A. Rahman"
```

`why` is required, because it is printed at the **top** of every run summary — before the
numbers, not in a footnote. Anybody reading those values needs to know up front that a local
rule shaped them.

Accepted rule names and actual application are distinct. The engine directly applies
`cr_denominator`, `exclude_key`, `include_key`, `defect_phase` and `velocity_team_hours`.
Other named overrides can record guidance; use the concrete workflow/source/period fields
for reliable behavior and check the reported applied/unapplied result. An `expires` date
can flag stale guidance. See [custom instructions](reference/08-custom-instructions.md).

### Project targets

Refresh the project's PMS registry to use its official targets. For review workflows that
need a separate bar, add an explicit local target and reason at profile, account or project
level:

```yaml
targets:
  defect_rate:
    value: 20
    why: "Agreed review target for this integration phase."
```

The engine and workbook use the same target and label its source as local, with PMS
unchanged. PMS submission is blocked while local targets are active: set the intended
project targets in PMS, remove the local override, refresh the registry and review again.
KPI definitions remain shared; delivery mappings, defect policy and documented exceptions
make different workflows explicit instead of hiding them in the numbers.

---

## Engine fixtures and runnable samples

Same engine, same nine KPIs, nothing in common otherwise.

| | `examples/northwind-q3` | `examples/acme-jira` |
|---|---|---|
| Tracker | Legacy prebuilt Asana KIF fixture | Jira-style CSV export |
| Chat | Google Chat | Slack |
| Plan | PDF on Drive | Confluence page |
| Periods | Delivery cycles | Sprints |
| Unit | Hours | Story points |
| Working file | Google Sheets | Local xlsx |
| Output | Push after approval | Review only, typed in by hand |

These older fixtures exercise the engine. For the complete run, folder layout and
downloadable workbooks, use the [sample pack](../samples/README.md). The command below
calculates only the first fixture:

```bash
.venv/bin/python plugin/kpi-copilot/scripts/kpi_engine.py --kif plugin/kpi-copilot/examples/northwind-q3/run.kif.json \
  --profile plugin/kpi-copilot/examples/northwind-q3/profile.yaml --reasons plugin/kpi-copilot/examples/northwind-q3/reasons.yaml
```

---

## Checking your profile

```bash
.venv/bin/python plugin/kpi-copilot/scripts/profile_tool.py validate --profile profile.yaml
.venv/bin/python plugin/kpi-copilot/scripts/profile_tool.py explain  --key workflow.delivered_when
```

`validate` checks more than the schema: a tool id referenced from Sources that does not exist
in Tools, an output mode that contradicts itself, a regex that does not compile, a
`delivered_when` with no states in it. Each one is reported as a sentence, not a stack trace.
## Grouped delivery tickets and client vocabulary

Configure `conventions.grouping.split_source_children: true` for a client that counts the
individual tickets inside an approved plan or estimate group. The parent is excluded from
ticket counts. Its approved hours are held once on an effort-only row, rather than copied
or arbitrarily divided across its members. The group budget reaches Velocity once every
member has delivery evidence. Incomplete groups retain their budget without claiming partial
completion hours that the source does not provide.

`exclude_member_patterns` omits specification/admin cards from that expansion. Description
links are ambiguous, so non-subtask membership must be recorded explicitly as
`linked_members: {DEMO-10: [DEMO-11, DEMO-12]}` at the project level. Missing members and
overlapping budgets stop the run with a repair instruction. An approved defect-fix ticket
can occur once in the delivery register and once in the defect register; defect policy still
decides whether it contributes to Defect Rate.

Set `inherit_parent_delivery: true` only when the parent's handoff covers all member work.
The child keeps its own handoff when available. A parent QA failure does not automatically
mark every child as reworked; missing individual history remains an explicit evidence gap.

`conventions.additional_request_label: Additional Request` controls the vocabulary in notes.
Internal `CR` types and PMS KPI identifiers stay stable. Workflow settings can supply a
`delivered_when.label` and `reopened_when.note` so the generated notes explain the configured
delivery and rework boundaries in ordinary language.
