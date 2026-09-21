# The counting rules

What each KPI measures, how it is counted, and why the awkward cases are decided the way
they are. This is the part that must be identical for every project lead - not because
uniformity is a virtue, but because a Defect Rate of 12% has to mean the same thing on two
different projects or management is reading noise.

The authoritative ids, names and targets come from PMS via `scripts/kpi_registry.py`. This
file explains the **counting**; PMS owns the definitions and the targets.

Targets are configurable per project in PMS and legitimately differ — an integration over a
legacy surface is not held to a greenfield defect rate. The engine uses this project's target
if PMS holds one, otherwise the PMS default, and records which on every measure. The counting
below does not vary, because that is what makes two projects' numbers comparable at all.

The thresholds quoted below describe the bundled September 2026 reference, not a live
query of your PMS. The runner uses the configured registry; refresh it when definitions
change. A project target can differ. A labelled local target needs a value and reason and
blocks PMS submission until reconciled.

## Contents

1. [The vocabulary](#the-vocabulary)
2. [The nine KPIs](#the-nine-kpis)
3. [Dates: agreed, not planned](#dates-agreed-not-planned)
4. [What gets excluded](#what-gets-excluded)
5. [Why "Not measured" exists](#why-not-measured-exists)
6. [Cases that come up](#cases-that-come-up)

---

## The vocabulary

**Deliverable** - a row of type Task, CR or Scope. Excluded rows never reach a denominator.

- **Task** - in the agreed plan for its period.
- **CR** - an approved addition after the plan was agreed.
- **Scope** - in-scope work that is neither, such as planned handling of client feedback.
- **Excluded** - not our deliverable: grouping cards, milestone markers, QA admin cards,
  duplicates. Kept in the workbook with a reason.

**Delivered** - the item reached the team's delivery event (`workflow.delivered_when`).
It may be development ready for testing, final closure, or another supported event. Choose
the agreed promise; the status name alone does not establish what the team committed to.

**Committed** - the team negotiated and promised something for this item, so it carries a
commitment date. An item nobody promised is not committed, and is invisible to Delivery
Commitment.

**Closed** - the item was accepted and finished (`workflow.closed_when`).

**Period** - one PMS period: a milestone, a delivery cycle, a sprint, a month, or the whole
project. PMS allows 25 characters in the name.

**Handover** - the build that reached the client. A missing handover date means the tool cannot establish that boundary; it does not prove
the client never received the build. Ask for the fact when it is needed.

**Evidence** - a link that proves a judgement: a comment, a status change, a chat message, a
row in the plan. Every Yes/No should carry one.

---

## The nine KPIs

### Velocity (higher is better, min 10, range 0-1000)

Work finished in the period, in the project's unit.

- Numerator: the effort of every **delivered** item, plus the period's team-level effort
  (bug fixing, regression, QA support) that belongs to no single item.
- `sources.hours_basis: dev` counts development hours only. `dev+qa` adds each item's QA
  hours **once that item's QA is done**, so an open cycle is not credited with QA that has
  not happened.
- `sources.hours_first` decides who wins when the plan and the tracker disagree. Where the
  plan is what the client signed, the plan wins, and `hours_source` records that on the row.
- Story-point projects count points and ignore team hours, because there is no sensible way
  to express shared effort in points.

### Task Comprehension (higher is better, min 80)

The share of items the team could build from the requirement without going back to the
client.

- Denominator: **every item worked on in the period** - plan items and approved additions
  alike. Not just the initial scope. A cycle made only of change requests gets a real
  number rather than "not applicable".
- An item with no history of its own (a component tracked on a parent card) is `null` and is
  left out of the denominator entirely.
- "Had to ask" means a question about **what the thing should do**. Going to a blocked state
  because a build was missing or an environment was down is a dependency, not a
  misunderstanding, and does not count.
- Clarifications sought *before the project started* do not count. Estimation questions are
  part of estimating.

### Client Expectation (higher is better, min 90)

The share of work delivered by the date the client expected.

- `client_check: Handover` - met when the period's handover build reached the client by the
  date. Use this normally.
- `client_check: Delivery` - met when the item itself was delivered by the date. Use this for
  a feature freeze, where the rule is "no new features after this date" and bug fixes
  legitimately continue.
- Items not yet due are **Pending**: out of the denominator, named in the note with their
  dates. An open period must never read as though it were complete.

### Delivery Commitment (higher is better, min 100)

PMS defines it as: *"Team-negotiated commitments that were delivered on time."* Formula:
task count delivered on time over total team-committed task count. Insight: **reliability of
the team**.

Two things follow, and both are easy to get wrong.

- **The denominator is the items the team committed to**, not every deliverable. An item
  nobody promised a date for is not evidence of reliability in either direction. It is left
  out and named: *"12 items the team made no commitment on are left out."* Counting the whole
  backlog here turns a measure of promises kept into a measure of how much work happened to
  finish, which is Velocity's job.
- **"Delivered on time" means whatever the team committed to deliver.** For most teams that
  is their delivery event; for others it is the handover, or completion, or something
  specific they promised. `workflow.commitment.met_when` says which, and the note says it in
  words — *"counted on the handover to the client"* — so a reader is never guessing.

A period where nothing was committed returns "Not measured", not 0% or 100%.

`workflow.commitment.scope: all-deliverables` is available for a team that commits to the
whole scope as one piece. Use it deliberately, not to make the denominator bigger.

### Defect Rate (lower is better, max 15)

Defects found in what we delivered, over what we delivered.

- Numerator: counted defects. Denominator: delivered items.
- **Rejected reports are never defects.** That is not configurable.
- Observations, improvements and pre-existing defects are counted only if
  `policy.count_*` says so. Default: no.
- Post-release defects are counted by default, because a bug is a bug wherever it was found.
- Everything not counted is **named in the note**: "Also reported but not counted: 11 that
  were already in the product, 6 observations, 2 closed as not a bug". This is the sentence
  that stops a reader assuming the number was massaged.

### Escaped Defect Rate (lower is better, max 5)

PMS: *"Defects found after release / Total defects (before + after release)."*

- **The denominator is defects, not delivered items.** The question is what share of the
  problems reached the client, not how much work was done. A cycle that found forty issues in
  QA and let one through scores well, which is the right answer.
- Rejected reports were never defects, so they are in **neither** half, and the note says how
  many were set aside.
- **A period with no handover date returns "Not measured", not 0%.** Without the release boundary,
  the tool cannot establish whether a report escaped; missing evidence is not zero.

### Defect Rejection Rate (lower is better, max 15)

Reports that turned out not to be defects, over all reports in the period.

Counted as rejected: invalid, by design, duplicate, not reproducible, not feasible. The
reasons are summarised in the note.

### Rework Rate (lower is better, max 10)

Recorded reopening events after the agreed closure boundary, over completed tasks whose
reopening outcome is known. The current engine uses `reopen_count` when available and one
event for an explicit Yes without a count. Multiple returns can exceed the number of
affected tasks; review the event count, not only the distinct-task count.

- **A QA failure while the item is still being tested for the first time is not rework.** It
  is testing working as intended. It stays in the evidence column, is named in the note as
  not counted, and does not itself create a defect report. This is the most commonly mis-scored KPI
  in the whole set.
- Items whose history could not be read are left out of the denominator and named. If none
  could be read, the KPI is "Not measured" rather than a flattering 0%.

### CR Rate (lower is better, max 20)

Approved additions against the agreed scope.

- Denominator: the period's planned items.
- A period made only of change requests has no planned items of its own, so it is measured
  against the **project's** planned scope, and the note says that is what was done.

---

## Dates: agreed, not planned

This is where most arguments happen, so the rule is worth memorising.

**Client Expected Date** - what the client expects. The planned handover, a client deadline
(a release freeze), or a date re-agreed after the client added work. Drives Client
Expectation.

**Commitment Date** - what the team itself negotiated and promised. Drives Delivery
Commitment, and its presence is what makes an item part of that KPI at all. The two are
different questions: what the client is waiting for, and what the team said it would do.

**A plan the team revised on its own is not an agreed date.** If an item moved because the
team was busy with another release, the KPI date stays where the original plan put it. Score
against the original plan and explain the revision in the remarks and the period notes. Only
a date the client set or re-agreed moves a KPI date.

That rule is the difference between a KPI that measures delivery and one that measures how
recently somebody edited the plan.

Levels, most specific first:

1. per-item override
2. rule (a date that applies to a set of items, a period or a type)
3. milestone commitment dates
4. period `client_date` / `commit_date`
5. project `client_date` / `commit_date`

The original plan dates are kept alongside, so the workbook can show "Original plan: ..."
where an agreed date differs.

---

## What gets excluded

Excluded rows stay in the document with a reason, so the workbook can answer "why is my
40-item board showing 12 items" without anybody re-reading the board.

Usual exclusions: umbrella and grouping cards, milestone markers, QA admin cards (bug
reporting, checklists, regression passes), duplicates, and work that is not our deliverable.

Plan bug-fix buckets are **not** rows: the defect KPIs already cover that work, and counting
it twice inflates Velocity.

Where a feature card is split into separate cards for the work, the children become the rows
and the parent becomes an excluded grouping row.

---

## Why "Not measured" exists

Because a wrong number is worse than a missing one. A missing number prompts a question. A
wrong number gets quoted in a review, defended, and built on.

A KPI is "Not measured" when:

- the adapter could not observe what the KPI needs (no status history, no comments),
- nothing in the period has reached the state the KPI measures (no handover, nothing
  delivered),
- or every item that could have been judged was left out for a stated reason.

The review identifies the reason without inventing a result. Missing inputs and questions
belong in Open Questions; result notes remain understandable to a manager. Unmeasured
values are not submitted as numbers. If a previously published managed KPI becomes
unmeasured, an approved push can clear its old value; inspect the exact preview.

---

## Cases that come up

**A cycle with nothing delivered yet.** Inspect each KPI separately: Velocity needs
completed effort, Defect Rate needs delivered work, and Escaped Defect Rate needs a release
boundary and reports. A period explanation may say: "Nothing to measure yet: all 6 items are still
ahead of 09/22 and the handover has not happened."

**Additional requests delivered inside the initial scope.** They stay in that period, and the
note names them: "39 planned tasks + 14 additional requests". Splitting them into a separate
period to make a cycle look cleaner is not allowed.

**A value above 100.** PMS accepts 0-100 for everything except Velocity (0-1000). The clamped
value is sent and the note carries the real figure: "PMS accepts up to 100; the real figure
is 200".

**A defect that first looked like an environment problem.** Recurrence alone does not establish
a product defect. Use the recorded diagnosis or ask for clarification before reclassifying it.

**Work tracked on another board.** It is still a deliverable. Add it as a row with its
evidence link and a remark saying where it lives.

**The team changed process mid-project.** `workflow.delivered_when.from_date` applies the new
rule from a date onward and the old one before it, so a process change does not retroactively
rewrite six months of delivery dates.
