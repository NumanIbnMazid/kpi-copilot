# Using it week to week

Once you are set up, a cycle is one sentence to your assistant:

> "Do the KPI run for the Q3 release."

You do not run anything in a terminal. Whichever assistant you use - Claude, Cursor, Codex -
runs one command, reads what it prints, and comes back to you with the sheet and, only if
needed, a short list of questions. In Claude that is also `/kpi-copilot:kpi-run <project>`.

Name the project. If your profile covers several, leaving it out is an error listing the ones
it knows rather than a guess about which you meant.

---

## What happens

```bash
python3 scripts/kpi.py run --profile profile.yaml --project <id>
```

1. **The board.** Read through the tracker's API, straight to disk. Cards that have not
   changed since last time keep the history already read, so a rerun takes seconds.
2. **Your edits.** Whatever you typed into the sheet's yellow cells since the last run is
   read back first, and kept. Nothing you change is ever overwritten.
3. **The sources on your list.** The plan, the estimates, the timeline - the ones named in
   your profile, and nothing else. Each is fetched only if it changed.
4. **Judge.** Every card is classified by the shared rules: what it is, which period, what
   was delivered when, whether it was rework, whether the client had to explain it. Rules read
   what people actually typed - `[Exisiting]` is read as *Existing*, and the row says so.
5. **Count.** The nine KPIs, with notes, the same way for everybody.
6. **The sheet.** Rebuilt locally, and - if you keep it in Google Sheets - the same
   Google Sheet updated in place. Same link every time.
7. **NEXT.** One short block: what, if anything, would make the numbers better.

That is a few seconds. Then, only when there is something to do:

8. **The assistant judges** what the rules were unsure of - all at once, from one file, by
   written definitions. Its answers are kept, with the reason; next time it is asked only
   about what is new.
9. **You answer** what nobody can know from outside: when the build reached the client,
   whether a plan item with no card was delivered. Once. On the **Open Questions** tab, or
   by telling the assistant.
10. **Deliver.** According to your output mode. Nothing reaches PMS without your yes.

Everything is kept under `<project>/runs/<date>/`.

### What a run reads - and what it does not

The tracker, plus the sources your profile names. **It does not search chat, mail or
Drive.** If those sources cannot answer something, you are asked; that is the right outcome,
not a failure, and it is what keeps a run to minutes.

Reaching further is yours to ask for, per run - *"also check the client chat for the
handover date"* - or for good, by listing places under `sources.evidence_channels` and
asking for a deep run (`--deep`). Even then only the open questions are looked up, only
there.

### If a run feels slow

The last line of every run says where the time went:

```
  board 2.1s  read-back 0.4s  sources 0.9s  classify 0.1s  compute 0.1s  sheet 3.2s  = 6.8s
```

If that total is small and the run took half an hour, the time went on something the
assistant did around it - reading the board in a browser, carrying a sheet through the
conversation, searching for a fact. None of that is needed, and `AGENTS.md` tells it so. Say
"just run the command and read NEXT".

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
| Open Questions | What the sources could not answer. Type the answer; the next run keeps it and stops asking |
| Run Log | Which sources this run read, which it deliberately did not, and how long it took |

This is what you open when somebody questions a number in three months.

### Reading it

Colour is the whole grammar, and it tells you the truth about what the tool will accept:

| Colour | Meaning |
|---|---|
| **Yellow** | Yours. The numbers move at once, and the next run reads it back and keeps it |
| **White** | Read from your tracker or your profile. True, but not yours to change here |
| **Grey** | Computed. Editing it achieves nothing; the next run rebuilds it |

**Grey cells are live formulas**, not pasted numbers: change a yellow cell and the KPI, the
dashboard bar and the note for PMS all move at once, in Excel and in Google Sheets alike. The
formulas mirror the engine's counting rules exactly, and the self-test checks that they give
the same number.

Dates are real dates, so the date columns sort and filter as dates. The judgement columns
have dropdowns. Red marks a missed date, a reopen, a client-found defect and a missed KPI with
no reason yet. The **Check** column is empty when a row was obvious and says how it was
decided when it was not - *"read [Exisiting] as Existing"*, *"loose title match to the plan"*.
Formatting and formulas carry on past the last row, so a line you add by hand still counts.

### Editing in the sheet

The workbook is a working surface, not a read-only report. Change a Yes/No, an item type, a
period, an hours figure, a date, a period's handover date, or the **Why** text. The numbers
follow immediately.

**The next run reads your edits back before it rebuilds anything**, files each one as your
decision - which outranks the assistant's and the rules' - and tells you what it read:

```
Read back from the sheet:
  · Defect Register · Bug 02 · pre existing -> Yes
  · Periods · Additional Requests 1 · handover date -> 2026-09-16
  · Initial Scope · CR Rate: reason taken from the sheet
```

So the sheet, the numbers and PMS cannot end up saying different things, and you never
re-enter anything.

Two things worth knowing:

- **KPI Summary has a "Since the last run" column.** If it says anything, the sheet was
  edited after the run computed. Run again before pushing: PMS always receives what the run
  computed, never what was typed.
- **A counting rule changed on the Config tab is not applied.** The live numbers follow it,
  which is handy for seeing what it would do, but a counting rule changes how your project
  compares with every other. The run reports it and says where to change it properly.

**If a computed figure is wrong and you cannot fix the input in time**, put the right number
in **Set value by hand** and a reason in **Why set by hand**. It is used - and the computed
figure stays beside it, the note gains a sentence saying a person recorded a different figure
and why, and the PMS payload carries both. A hand-set value with no reason is refused,
because that is the one that becomes a discrepancy nobody can explain later.

### Where the sheet lives

By default, beside your profile: `<project>/KPI Tracker - <name>.xlsx`, rewritten each run.

To keep it in Google Sheets, say so once - *"keep the KPI sheet in this Drive folder"*, or
*"update this sheet: <link>"*:

```yaml
output:
  workbook: google-sheets
  workbook_location: <Drive folder link>     # created there on the first run, then found by name
  # or
  workbook_file: <Google Sheet link>         # update exactly this one
```

Every run then updates the same Google Sheet in place, atomically, and the link never
changes. Tabs you add yourself are left alone. It needs Google connected once
(`python3 scripts/kpi.py auth google` - you run that, not the assistant); until then the run
writes the local file and tells you how to import it over the same sheet (File > Import >
Replace spreadsheet), which also keeps the link.

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
