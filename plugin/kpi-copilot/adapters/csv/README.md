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
| Rework Rate | Says "Not measured" unless the export records reopens |
| Task Comprehension | Says "Not measured" unless the export records clarifications |

The other six work normally. The adapter declares this, the engine reports it, and the notes
say it in plain English. Nothing is guessed.

Some trackers can export a "date moved to <status>" column. If yours can, map it to
`delivered` and the delivery half starts working. Delivery Commitment also needs to know
which items the team committed to - export a commitment-date column if you have one, or set
`workflow.commitment.scope: all-deliverables` if the team commits to the whole scope.

## Dates

Recognises `YYYY-MM-DD`, `DD/MM/YYYY`, `MM/DD/YYYY`, `DD-Mon-YYYY` and the usual ISO
timestamps. Anything it cannot parse becomes null rather than a wrong date.

## When to move to a native adapter

When the manual export becomes annoying, or when the three history-based KPIs matter enough
to justify the work. Not before. `/kpi-copilot:kpi-adapter` walks it.
