# Using it week to week

Once you are set up, a cycle is one command and a review.

```
/kpi-copilot:kpi-run <project>
```

Name the project. If your profile covers several, every script takes `--project`, and leaving
it out is an error listing the ones it knows rather than a guess about which you meant.

```bash
python3 scripts/profile_lib.py --profile profile.yaml --list
```

---

## What happens

One command does the whole deterministic chain in one process:

```bash
python3 scripts/run.py --profile profile.yaml --project <id>
```

1. **Readiness check.** Stops if something blocking is unresolved, rather than producing
   numbers from an environment that is not ready. With several projects it checks each one's
   adapter, so a missing one surfaces now rather than mid-run.
2. **Resolve.** Your defaults, then the project's client account, then the project. This is
   what makes one profile cover Asana for one client and Jira for another.
3. **Extract.** Your adapter reads the tracker.
4. **Validate.** The extract is checked against the interchange format before anything counts it.
5. **Compute.** The nine KPIs, with notes.
6. **Workbook.** The audit trail, with a link behind every judgement.
7. **The list.** What the tracker could not answer, naming the tickets.

That takes under a second. Then:

8. **Look up what the list named** - and only that.
9. **Review.** Your part. One round of questions.
10. **Fold it back in.** `run.py review` re-reads the sheet, recomputes, and rebuilds
    everything from the result.
11. **Deliver.** According to your output mode.

Everything is kept under `runs/<date>/`.

### Why the order matters

The slow part of a KPI run was never the arithmetic - the whole chain is a fraction of a
second. It was searching chat, mail and plan documents *before* computing, which means
hunting for evidence the board may already hold, across a space with no edges.

Computing first turns that into a short list with ticket numbers on it:

```
7 tasks have no 'understood' - decides Requirement Comprehension.
  Usually in the ticket's own comments: ACME-101, ACME-102, ACME-103, ...
Sprint 14 has no handover date - decides Escaped Defect Rate and the client-date check.
  Usually in the release announcement.
```

The list is already filtered down to facts that would actually change a number. An item
nobody committed to does not appear on it, because Delivery Commitment measures promises
kept - a blank there is the correct answer, not a gap.

If a run still feels slow, the timing line at the bottom of every pass says which part was:

```
  preflight 0.06s  extract:jira 1.21s  validate 0.05s  compute 0.01s  workbook 0.20s  = 1.53s
```

If that total is small and the run took half an hour, the time went on searching. Bound it:
`sources.mode` and the `scan` block in your profile decide how far a run reaches, and
`docs/reference/09-scan-and-source-of-truth.md` covers both.

## The review

You get:

- the nine values per period, with Met / Not met / **Not measured**,
- every "Not measured" with its one-line reason,
- the judgement calls the adapter could not settle, each with a proposed answer,
- anything that moved a lot since last time,
- the notes, to read as English.

Answer the questions. Your answers are written into the project's config, so the next run
gives the same result without asking again. That is the compounding part: the third cycle is
much quieter than the first.

### Read the notes as a reader

The generated text is good but not automatic. Four things to watch for:

- A reason that repeats the heading or a count already printed. Cut the sentence.
- Plurals and arithmetic — "1 item ... is", "3 items ... are". A reason that names items
  ("4 of 13 were on time: ...") has to name all four.
- An open period written as though it were finished. It must name what is still pending, with
  dates.
- Links. They belong in the workbook, never in a PMS note.

Full guidance: `skills/kpi-run/references/note-style.md`.

## Writing the "why"

The fourth part of each note is yours, in the project's `reasons.yaml`:

```yaml
Initial Scope:
  Velocity: "The hours for the additional requests come from the Additional Effort Estimates
    sheet; Northwind approved them on 07/31 and 08/12."
  Delivery Commitment: "Only the delivery documentation slipped; it went out with the 08/12
    handover."
  # Delivery Commitment counts the items the team committed to, not every deliverable.
```

Its job is to add what the numbers cannot say. If it repeats the count, delete it.

You do not need a reason for every KPI. Write them for anything that is not "Met" or "Not
measured" — those are the ones a manager will ask about.

## The output modes

| Mode | What you get |
|---|---|
| `review-only` | Workbook plus a copy-paste block per period. You enter it in PMS |
| `dry-run` | Also the exact PMS diff. Still never writes |
| `assisted-push` | The diff, then a question, then the push |
| `auto-push` | Pushes without asking. Scheduled runs only, and only with `unattended` on |

Switching is one line in the profile, or one sentence to Claude.

Even on `assisted-push`, approval is per run. A yes for one period never carries to the next.

## The workbook

Every run produces a tracker workbook:

| Tab | What it holds |
|---|---|
| Read Me | What the colours mean and what each tab is for |
| Dashboard | Totals per period, the nine KPIs as a grid with colour, and links to everything the project uses |
| Config | Project details, the counting rules, and every KPI with the PMS formula behind it |
| Periods | Dates, handover, team effort, the period's story |
| Task Register | Every deliverable, with hours, dates, the Yes/No judgements and the evidence beside each |
| Defect Register | Every report, including the ones not counted and why |
| KPI Summary | Nine rows per period: value, target, where the target came from, status, numerator, denominator, the note |
| PMS Push Log | What was sent to PMS and when |
| Gaps | What could not be measured, and why |

This is what you open when somebody questions a number in three months.

### Reading it

Colour is the whole grammar, and it tells you the truth about what the tool will accept:

| Colour | Meaning |
|---|---|
| **Yellow** | Yours. Change it and `run.py review` reads it back into the numbers |
| **White** | Read from your tracker or your profile. True, but not yours to change here |
| **Grey** | Computed. Editing it achieves nothing; the next run rebuilds it |

Dates are real dates, so the date columns sort and filter as dates. The judgement columns
have dropdowns taken from the interchange format itself, so the sheet cannot offer a value
the tool would reject. Red marks a missed commitment, a reopen, a rejected report and a
missed KPI with no reason yet. Formatting carries on past the last row, so a line you add by
hand still fits. Registers print landscape, one page wide, with the header repeated.

### Editing in the sheet

The workbook is a working surface, not a read-only report. **Yellow cells come back; grey
cells are computed and regenerated.**

Change a Yes/No, an hours figure, a date, a defect's rejection, a period's handover date, or
the **Why** text — then:

```bash
python3 scripts/run.py review --profile profile.yaml --project <id> --by "Your Name"
```

That re-reads the sheet, folds the edits into the extract, recomputes, and rebuilds the
workbook and the payloads from the result — so the sheet, the numbers and PMS cannot end up
saying different things. It prints every edit it found, and every one it did not apply with
the reason.

**If a computed figure is wrong and you cannot fix the input in time**, put the right number
in **Set value by hand** and a reason in **Why set by hand**. It is used — and the computed
figure stays beside it, the reason is printed above the numbers, the note gains a sentence
saying a person recorded a different figure and why, and the PMS payload carries both. A
hand-set value with no reason is refused, because that is the one that becomes a discrepancy
nobody can explain later.

Typing over the grey Value or Note column does nothing, and `review` tells you so and points
at the column that would have worked.

## When a number looks wrong

Do not adjust the value. Change the input or the mapping and rerun — a number that was edited
to look right cannot be defended the second time it is questioned.

The usual causes, in order of how often they turn out to be it:

1. The delivered-when mapping names the wrong state.
2. An exclusion pattern is eating real work.
3. The wrong date level is winning.
4. The hours source is pointing at the wrong place.
5. Rework is counting first-round QA failures.
6. The adapter genuinely could not see something — working as designed.

Full list with symptoms: `skills/kpi-run/references/troubleshooting.md`.

## When your board changes

A renamed column is a one-line profile edit, not a rebuild. Tell Claude what changed, or edit
the Workflow tab of the workbook.

A new project is a row on the Projects tab.

## Running it on a schedule

```
/schedule create "Prepare KPIs for Acme every second Friday at 9am"
```

A scheduled run in `assisted-push` prepares everything and waits for you. Only `auto-push`
with `unattended: true` writes on its own — and it still logs every change and reads back
every value.

## Where the evidence lives

`runs/<date>/` holds the extract, the results, the payload and the push log for every run.
When two runs disagree, diff the two extracts: the change is in the input, not in the engine.
