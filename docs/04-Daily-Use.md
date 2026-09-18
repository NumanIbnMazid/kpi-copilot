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

1. **Readiness check.** Stops if something blocking is unresolved, rather than producing
   numbers from an environment that is not ready. With several projects it checks each one's
   adapter, so a missing one surfaces now rather than mid-run.
0. **Resolve.** Your defaults, then the project's client account, then the project. This is
   what makes one profile cover Asana for one client and Jira for another.
2. **KPI definitions and targets refreshed from PMS**, including any target this project sets
   for itself, so you are never scored against a stale or borrowed bar.
3. **Extract.** Your adapter reads the tracker.
4. **Compute.** The nine KPIs, with notes.
5. **Review.** Your part. One round of questions.
6. **Workbook.** The audit trail, with a link behind every judgement.
7. **Deliver.** According to your output mode.
8. **Log.** Everything kept under `runs/<date>/`.

Machine time is a few minutes. The review is the part that needs you, and that is the right
place for your time to go.

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
| KPI Summary | Nine rows per period: value, target, where the target came from, status, numerator, denominator, the note |
| Task Register | Every deliverable, with hours, dates, the Yes/No judgements and their evidence links |
| Defect Register | Every report, including the ones not counted and why |
| Periods | Dates, handover, team effort, the period's story |
| Gaps | What could not be measured, and why |

This is what you open when somebody questions a number in three months.

### Editing in the sheet

The workbook is a working surface, not a read-only report. **Yellow cells come back; grey
cells are computed and regenerated.**

Change a Yes/No, an hours figure, a date, a defect's rejection, a period's handover date, or
the **Why** text — then:

```bash
python3 scripts/workbook.py review --tracker runs/<date>/tracker.xlsx \
  --kif runs/<date>/run.kif.json --results runs/<date>/results.json \
  --reasons reasons.yaml --out-kif runs/<date>/run.kif.json \
  --out-reasons reasons.yaml --out-manual manual.yaml --by "Your Name"
```

It prints every edit it found, and every one it did not apply with the reason. Rerun the
engine and the values and notes follow.

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
