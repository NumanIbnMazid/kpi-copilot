---
name: kpi-adapter
description: "Write or fix a KPI Copilot tracker adapter, so a team on a tracker with no built-in support can produce KPIs. Use when someone's issue tracker is not Asana, Jira or a CSV export, when they ask to add support for ClickUp, Linear, Azure DevOps, GitHub Issues, Monday, Trello, Redmine, YouTrack or any other tracker, when an existing adapter is returning wrong or missing fields, or when a KPI is coming back 'Not measured' because the adapter cannot see something."
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, WebFetch, AskUserQuestion
---

# KPI Copilot: write an adapter

An adapter gets one tracker onto disk. Nothing else. If you are writing KPI maths, note
wording or spreadsheet code in an adapter, it belongs somewhere else and will drift from
everyone else's.

Read `adapters/_contract.md` first. It is short and it is the actual specification.

**Write a reader, not a judge.** The preferred shape is a *reader*: tracker -> board snapshot
(`scripts/board.py`), with no judgement in it - `adapters/asana/api.py` is the worked example,
about two hundred lines. `scripts/classify.py` then decides what is a defect, what is rework
and which period a card belongs to, tolerantly and the same way for every tracker, and the
ledger, the assistant's judge queue, the live sheet and the read-back all come free. The
older shape - a *converter* that produces finished KIF itself, like `jira` and `csv` - is
still supported, and the mapping section below is about that shape.

Two things a reader must get right, because they are what make a run take seconds rather
than half an hour:

- **API to disk.** The board must never travel through an assistant's context.
- **Cache by `modified_at`.** Take the previous snapshot; re-read history only for cards that
  changed.

## Before writing anything: is an adapter even needed?

Usually not, and saying so saves a week.

The `csv` adapter works with an export from any tracker on earth. A team can be producing
real KPIs this afternoon with it. A native adapter buys exactly two things:

1. **Status history**, which is what lets Delivery Commitment, Rework Rate and Task
   Comprehension be computed instead of reported as "Not measured".
2. **No manual export step** each cycle.

So ask: how often will they run this, and do they need the three history-based KPIs? A team
running monthly who are content with six of nine KPIs should use `csv` and move on. Say that
plainly rather than building something to be helpful.

## If it is needed

### 1. Find out what the tracker can actually tell you

Before designing, answer these against the real API, not the marketing page:

- Can you list issues for a project, with paging?
- Is there a **changelog or history** endpoint? This is the make-or-break question. Without
  it the adapter is a CSV adapter that fetches its own CSV.
- Are comments readable, and do they carry an author and a timestamp?
- Is there an estimate field, and what unit is it in? (Jira gives seconds. That has bitten
  people.)
- How are sprints, milestones or versions expressed?
- What does authentication need, and can it be an environment variable rather than something
  a person has to paste?

`WebFetch` the API docs. Write down what you found in the adapter's README, including the
things that are *not* available - the next person needs that more than they need the happy
path.

### 2. Map their world onto KIF

Work through `schemas/kif.schema.json` field by field and decide where each one comes from.
The four that need real thought:

| KIF field | The question to answer |
|---|---|
| `delivered` | Which status transition means "we handed this to QA"? Not "closed" - that is later, and using it flatters every delivery number |
| `reopened` | Closed, then moved back. A QA failure during the first test round is **not** rework. Getting this wrong is the most common adapter bug |
| `understood` | Did they have to go back to the client about the requirement? A blocked-on-build is not a comprehension problem |
| `type` | Task, CR, Scope or Excluded. Excluded rows stay in the document with a reason |

Anything you cannot determine is `null`. Not a default, not a guess. The engine reports
"Not measured" with the reason, which is the honest answer and the whole point.

### 3. Write it

```bash
cp -r adapters/csv adapters/<name>
```

Start from `csv` rather than `jira`: it is the simplest complete example and it already
handles the classification, the review list and the profile plumbing. A native adapter
mostly replaces "read a file" with "call an API".

Then:
- Declare `generated.capabilities` honestly. Claim `status_history` only if you read it.
- Put every judgement call you could not make into `review[]`, **with a proposal**.
- Read conventions and workflow states from the profile. An adapter with a team's column
  name hardcoded in it is a bug, and it will be copied by the next person.
- Apply the adapter-side custom rules (`delivered_signal`, `client_date_source`,
  `commit_date_source`, `hours_source`, `period_of_key`) and record them in
  `generated.warnings`.
- Never write to the tracker. Not a label, not a comment.

### 4. Prove it

```bash
python3 adapters/<name>/extract.py --profile <profile> --project <id> --out /tmp/test.kif.json
python3 scripts/validate_kif.py --kif /tmp/test.kif.json
python3 scripts/kpi_engine.py --kif /tmp/test.kif.json --profile <profile>
```

Then the test that matters: **run it against a period whose answer somebody already knows**,
and sit with them while they read the nine numbers. Matching a figure a human can verify by
hand is worth more than any amount of schema validation. Expect two or three rounds.

Add a case to `scripts/selftest.py` so the next change does not quietly break it.

### 5. Write the README

`adapters/<name>/README.md`, covering: what it needs to authenticate, which capabilities it
provides, **which it does not and what that costs**, the profile options it reads, and any
quirk of the API that surprised you. That last section is the one people actually come back
for.

## Things that will bite you

- **Estimate units.** Jira returns seconds. Some trackers return a string like "3d 4h".
  Convert to hours and record `hours_source` so a reader can see which number won.
- **Paging.** Almost every tracker pages, and almost every first draft forgets. A silently
  truncated board produces a confident, wrong Velocity.
- **"Complete" is ambiguous.** On some boards it means merged; on others, accepted by QA.
  Ask, and put the answer in `workflow.closed_when.completed_flag_means`.
- **Rate limits.** Back off and retry rather than failing the run. A 429 is not a reason to
  lose a five-minute extraction.
- **Time zones.** Take dates as `YYYY-MM-DD` in the team's zone. An off-by-one date on a
  milestone boundary moves a KPI and is very hard to spot afterwards.
- **Sub-tasks and parents.** Decide whether a parent is a deliverable or a grouping row.
  Usually grouping, so it becomes `Excluded` with a reason and its children are the rows.
- **Credentials.** Environment variables only. Never in the profile, never printed, never
  echoed back to the person.

## Where this fits

Once the adapter emits valid KIF, everything else already works: the engine, the notes, the
workbook, the dry run, the push, the audit trail. That is the deal the contract buys you, and
it is why the adapter should stay small and boring.
