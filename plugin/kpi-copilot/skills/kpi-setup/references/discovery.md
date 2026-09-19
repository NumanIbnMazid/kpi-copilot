# Discovery: what to read off a board before asking anything

The setup interview should feel like a conversation with someone who already looked. Spend
five minutes reading their tracker first, then present what you found as statements to
correct.

## What you are trying to learn

| Profile field | What to look for |
|---|---|
| `conventions.key_pattern` | Open ten issues. What do their identifiers look like? `TKT-3175`, `ACME-101`, a bare number? |
| `workflow.*.values` | The board's columns or statuses, in order. Which one means "dev is finished and QA can start"? |
| `conventions.defect_by` | Are defects an issue type, a label, a title pattern, or a separate board? |
| `conventions.exclude_patterns` | Scan titles for things that are not deliverables: "Sprint Goal", "QA Checklist", "Milestone 2", "[Duplicate]", umbrella cards |
| `conventions.cr_marker` | How is an approved addition marked? A label, a `[CR]` prefix, a field, or only in an estimates sheet? |
| `tracker.estimate_field` | Which field holds effort, and in what unit |
| `periods.model` | Sprints? Fix versions? Milestone cards? Nothing at all? |
| `conventions.client_names` | Who on the board is on the client side |

## Per tracker

**Asana.** Sections are the workflow states. The ticket key is usually a custom field.
Delivery is the first move into a QA-ish section. Asana's own "complete" flag often means
merged rather than accepted, so ask. Story history is on the task.

**Jira.** Statuses and the workflow scheme. The changelog gives full history. `issuetype`
distinguishes Bug from Story. Sprints are a custom field (`customfield_100xx`), and fix
versions are an alternative period model. Estimates come back in **seconds**.

**ClickUp / Linear / Monday / Azure DevOps.** All have statuses and some form of history.
Check whether history is on the list endpoint or needs a call per item - that decides whether
a native adapter is worth writing at all.

**Trello / GitHub Issues / a spreadsheet.** Usually no usable history. Start with `csv` and
be straight about which three KPIs will say "Not measured".

## Present it as statements, not questions

> Here is what I read off your board. Correct anything wrong.
>
> - Your columns: Backlog, In Progress, **In Test**, Testing Failed, **Done**.
> - **Delivered** = first time an item reaches *In Test* (your delivery event).
> - **Closed** = *Done*.
> - **Reopened** = out of *Done* back into *In Progress*.
> - **Defects** = issue type *Bug*. *Improvement* is reported, not counted.
> - **Keys** look like `NW-1234`.
> - **Not deliverables**: 4 cards titled "Sprint Goal" or "QA Checklist".

## What is genuinely worth asking

Only the things the board cannot tell you:

1. When two states both look like "delivered", which one is it really?
2. What does the team commit to, and what counts as keeping that commitment? Does every item
   carry a commitment, or only some?
2. Does the tracker's "complete" flag mean merged, or accepted?
3. Where does the agreed scope live, if not on the board?
4. When the plan says one date and the client said another, which is the agreed one?
5. What should happen at the end: a sheet they type in, or a push they approve?

Five questions, one round. Everything else you can read or default.
