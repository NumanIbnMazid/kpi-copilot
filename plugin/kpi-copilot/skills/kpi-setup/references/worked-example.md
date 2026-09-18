# Worked example: the Northwind profile

The setup this was built from, and the most demanding case we have. Useful when somebody's
situation looks awkward - it probably appears here.

Full files: `examples/northwind-q3/profile.yaml` and `examples/northwind-q3/run.kif.json`.

## The shape

Asana boards, Google Chat for evidence, a project plan PDF the client signed, a separate
estimates sheet for change requests, a timeline sheet for date revisions, KPI trackers in
Google Sheets, and PMS at the end. Delivery cycles rather than sprints. Hours, not points.
Push to PMS after approval.

## The five things that made it hard

**1. Scope comes from the documents, not the board.** Task rows are every line of the plan
PDF; CR rows are every approved row of the estimates sheet. The board is matched to those,
not the other way round. `sources.hours_first: plan` says the plan wins on hours, and each
row records `hours_source` so a reader can see which number won.

**2. Feature cards are split.** One planned feature is often several cards. The children
become the rows with their own hours, and the parent becomes an excluded grouping row. Where
the QA moves happen on the parent, the children inherit delivery and status from it; where
each child is worked separately, they carry their own.

**3. Dates were agreed in chat, not in the plan.** The Q3 feature freeze of 09/11 was set on
a client call and recorded in a chat message. That is the client-expected date, and the plan's
07/29 handover is kept alongside as "Original plan". This is the case that teaches the rule:
**a plan the team revised itself is not an agreed date.**

**4. A feature freeze needs `client_check: Delivery`.** The rule was "no new features after
09/11, bug fixes allowed until 09/25", so the item's own delivery date is what counts, not the
period's handover build.

**5. Team-level effort is real work.** Bug fixing, QA support and regression are not
attributable to one item, so they go in the period's `team_hours` and the Velocity note names
them separately from item effort.

## Its custom instructions

The profile carries a `defect_phase` override - one client-reported bug landed eight days
after handover and had to be marked as escaped - with the reason recorded, so it appears in
every run summary. It also carries a commented-out `threshold_defect_rate` override as a
demonstration: uncomment it and both `profile_tool.py validate` and the engine refuse it, and
point at PMS, where a target is set per project.

## What its numbers look like

Initial Scope: 7 deliverables, 5 planned and 2 additional, handed over 08/12, 135 team hours.
Task Comprehension 71.43% (5 of 7), Delivery Commitment 85.71% — six of the seven items the
team committed to landed on time; the delivery documentation slipped, Defect Rate 42.86% with three reports named as not counted, Rework Rate 14.29% with
the first-round QA failure named as not counted.

Additional Requests 1 is still open: Escaped Defect Rate reports "Not handed over to the
client yet", the pending item is held out of the date denominators and named with its due
date, and CR Rate falls back to the project's planned scope because the cycle is only
additions.

Run it yourself:

```bash
python3 scripts/kpi_engine.py --kif examples/northwind-q3/run.kif.json \
  --profile examples/northwind-q3/profile.yaml --reasons examples/northwind-q3/reasons.yaml
```
