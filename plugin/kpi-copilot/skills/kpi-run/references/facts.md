# The facts files

A project's memory lives beside its profile, in `<project id>/facts/`. They are plain YAML on
purpose: this is the part of a project a lead actually knows. The workbook's yellow cells
show the same facts, and whatever is typed there is read back into these files.

Write one when the run asks ("facts/plan.yaml is empty …"), from the file the run points
at. Read the document **once**; the run will not ask again until it changes.

Rules for all of them: dates as `YYYY-MM-DD`; never invent a row, an hour or a date - leave
it out and let the run ask; keep `source.fingerprint` equal to the value the run printed, so
it can tell when the document has moved on.

## facts/periods.yaml - the periods

Usually written at setup, from the timeline or from what the lead says.

```yaml
project:                         # used when a period or an item has no date of its own
  client_date: 2026-09-11        # what the client expects
  commit_date: 2026-09-11        # what the team committed to
  client_check: Delivery         # Delivery = each item by the date · Handover = the build by the date
  dates_why: Northwind's Q3 feature freeze is 09/11; bug fixes are allowed until 09/25.
periods:
  - name: Initial Scope          # 25 characters at most (PMS)
    start: 2026-07-01
    end: 2026-08-12
    pms_period_id: 501           # leave out until the period exists in PMS
    handover_date: 2026-08-12    # when the build reached the client; leave out if it has not
    team_hours: 40               # shared effort not on any one item: bug fixing, regression
    client_date:                 # only when this period differs from the project's
    commit_date:
    notes: The planned work plus the additions approved on 07/31, handed over together.
    plan_text: Build to QA 07/20, handover 07/29 (plan).
```

A timeline source with a column mapping fills `handover_date` by itself, and keeps a `log:`
of KPI-relevant entries as context for the notes. Anything a person typed wins over it.

## facts/plan.yaml - the agreed scope

One item per deliverable the plan names. `board_key` ties it to a card; without one the
title is matched, tolerantly. A plan item with no card at all still gets a row, and a
question about whether it was delivered.

```yaml
source: {id: plan, fingerprint: "<printed by the run>", as_of: 2026-07-01}
grain: board-cards               # or plan-items - see below
items:
  - board_key: NW-101
    title: Booking rules for shared rooms
    period: Initial Scope
    dev_hours: 26.5
    qa_hours: 8
    milestone: Milestone 1
    modules:                     # only needed for grain: plan-items
      - {name: Database, dev_hours: 1.5}
      - {name: Tablet app, dev_hours: 7}
  - title: Delivery documentation   # in the plan, no card of its own
    period: Initial Scope
    dev_hours: 6
```

`grain` decides what one deliverable is. `board-cards`: one card, one deliverable.
`plan-items`: a card the plan splits into modules counts once per module, inheriting the
card's history - use it when the plan's breakdown is what was agreed with the client and
the board is coarser. It changes every denominator, so it is printed on the Config tab. It
is the lead's choice; do not switch it to improve a number.

## facts/estimates.yaml - approved additions

```yaml
source: {id: estimates, fingerprint: "<printed by the run>", as_of: 2026-08-28}
items:
  - board_key: NW-140
    title: Single sign-on fix
    period: Initial Scope        # the period it was approved for
    dev_hours: 10
    qa_hours: 4
    approved_on: 2026-07-31
```

A card that matches a row here is a change request even when nobody tagged it `[CR]`.
An estimates *sheet* is normally read through a column mapping instead, with no file to
write:

```yaml
sources:
  estimates:
    kind: sheet
    ref: <Drive link>
    map:
      tab: Estimates             # optional; the first tab with these headers is used
      columns: {board_key: Ticket, title: Item, dev_hours: "Dev (h)", qa_hours: "QA (h)",
                approved_on: Approved, period: Period}
```

## facts/reasons.yaml - the "why" of each note

Written by `judge` from your `reasons[]`, or by the person on the KPI Summary tab. A reason
a person wrote is never overwritten by an assistant.

```yaml
Initial Scope:
  CR Rate: Both additions were small fixes the client asked for during testing.
```

## What is not a facts file

`ledger.json` (every judgement, who made it, why), `cache/` (the board and the fetched
sources), `sheet_state.json` and `runs/` are the tool's own. Do not edit them by hand; change
a judgement with `judge` or in the sheet.
