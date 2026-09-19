# Adapting it to your workflow

The design assumption is that your workflow is not going to change, and should not have to.
Everything that differs between two project leads lives in one profile. Targets live in PMS,
where they are configurable per project. Only the counting is fixed.

This document covers what you can change, how, and where the line is.

---

## The four tiers

| Tier | What it covers | How it behaves |
|---|---|---|
| **Yours** | Tracker, states, naming, sources, periods, output, house style | Change freely |
| **Yours, in the sheet** | Judgements, hours, dates, the Why text — and any figure, as a recorded hand-set value | Edit, run `workbook.py review`, rerun |
| **Recorded** | Project facts the defaults get wrong | Allowed, applied, and printed in every run summary |
| **Set in PMS** | The targets for each KPI, per project | Change them in PMS; the next run reads them and marks them as this project's own |
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

A lead with one client and one tracker writes neither block and never notices this exists.

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

```bash
python3 scripts/profile_lib.py --profile profile.yaml --list
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
python3 scripts/workbook.py build --profile profile.yaml --out "KPI Profile Workbook.xlsx"
python3 scripts/workbook.py read  --xlsx "KPI Profile Workbook.xlsx" --out profile.yaml
```

The workbook is generated from the schema, so the two views cannot drift. Edit whichever you
prefer.

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

Two reasons it matters. Claude uses it to find things without being told each time. And when
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

- **`delivered_when` is not `closed_when`.** Using the closed state here flatters every
  delivery figure, because closed is later than handed-to-QA.
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
  workbook_location: <drive folder id, SharePoint path, or a local folder>
  notify: chat-devqa
```

`auto-push` is only honoured with `unattended: true`, and the push script refuses the
combination rather than hanging. Nobody gets an unattended push by accident.

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

**The glossary is more useful than it looks.** It stops a note being technically correct and
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

Supported rules: `delivered_signal`, `client_date_source`, `commit_date_source`,
`cr_denominator`, `exclude_key`, `include_key`, `defect_phase`, `hours_source`,
`period_of_key`, `velocity_team_hours`. An `expires` date makes a run warn when an override
has gone stale.

### What the overrides cannot touch

### Targets: change them in PMS, not here

Your project may well need a different bar, and PMS supports that — a threshold is configurable
per project. Set it there. The next run reads it, scores against it, marks it with an asterisk
and prints "Target set in PMS for project 101, not the PMS default", so anyone comparing two
projects can see the bar differed and that PMS is what made it differ.

What the profile will not do is hold a second copy. Try it and you get this, from both the
validator and the engine:

> set `threshold_defect_rate` on this project in PMS instead. Targets are configurable per
> project there, and the next run reads whatever PMS holds and marks it as this project's own. A
> target kept in this file would make the workbook and PMS disagree.

The refusal is reported, never silent. A silently-ignored instruction is worse than a refused
one, because you go on believing it took effect.

---

## Two complete examples

Same engine, same nine KPIs, nothing in common otherwise.

| | `examples/northwind-q3` | `examples/acme-jira` |
|---|---|---|
| Tracker | Asana, read in the browser | Jira, via CSV export |
| Chat | Google Chat | Slack |
| Plan | PDF on Drive | Confluence page |
| Periods | Delivery cycles | Sprints |
| Unit | Hours | Story points |
| Working file | Google Sheets | Local xlsx |
| Output | Push after approval | Review only, typed in by hand |

Run either:

```bash
python3 scripts/kpi_engine.py --kif examples/northwind-q3/run.kif.json \
  --profile examples/northwind-q3/profile.yaml --reasons examples/northwind-q3/reasons.yaml
```

---

## Checking your profile

```bash
python3 scripts/profile_tool.py validate --profile profile.yaml
python3 scripts/profile_tool.py explain  --key workflow.delivered_when
```

`validate` checks more than the schema: a tool id referenced from Sources that does not exist
in Tools, an output mode that contradicts itself, a regex that does not compile, a
`delivered_when` with no states in it. Each one is reported as a sentence, not a stack trace.
