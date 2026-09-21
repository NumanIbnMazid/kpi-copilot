# csv adapter

Turns a CSV export from any issue tracker into KIF. This is the day-one answer for any team,
and the permanent answer for plenty of them.

## What it needs

A CSV. That is all - no token, no API, no network.

```yaml
tracker:
  adapter: csv
  options:
    file: exports/board.csv
    tracker_name: ClickUp        # just for the record
    columns:                     # only what could not be guessed
      period: Sprint
```

Column names are guessed from the header row, so the `columns` block is usually empty or
nearly so. It recognises the common spellings of key, title, type, status, assignee,
reporter, created, resolved, estimate, story points, sprint, labels, url and resolution.

## What it can see

`created_date`, `closed_date`, and - when the export carries the column - `assignee`,
`estimates`, `story_points`, `issue_type`, `labels`, `reporter`.

## What it cannot see, and what that costs

**No status history.** A CSV is a snapshot. That means:

| KPI | Effect |
|---|---|
| Delivery Commitment | Needs a commitment date and a delivery date per item, or it says "Not measured" |
| Rework Rate | Native status history is unavailable; a documented review answer or another supported input is needed |
| Task Comprehension | Comment/history evidence is unavailable; do not treat an absent clarification as false |

There is no guaranteed count of measurable KPIs. Client Expectation needs an agreed date,
Escaped Defect Rate needs release evidence, and Velocity needs usable estimates. The
[fictional CSV sample](https://github.com/NumanIbnMazid/kpi-copilot/tree/main/samples) shows
four measured KPIs and five gaps for its supplied inputs.

Some trackers can export a "date moved to <status>" column. If yours can, map it to
`delivered` and the delivery half starts working. Delivery Commitment also needs to know
which items the team committed to - record the commitment in supported period/item facts or review inputs, or set
`workflow.commitment.scope: all-deliverables` if the team commits to the whole scope.

## Dates

Prefer unambiguous `YYYY-MM-DD`. The parser also tries day/month/year before month/day/year,
so `03/04/2026` is ambiguous and can be interpreted differently from the export source.
Normalize the export date format before running. Unparseable dates become null.

## When to move to a native adapter

When the manual export becomes annoying, or when the missing history/evidence matter enough
to justify the work. Not before. `/kpi-copilot:kpi-adapter` walks it.
