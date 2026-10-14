# Writing the notes

Management reads the notes, not the spreadsheet. A number without a note is a number nobody
can act on, and a note that reads like machine output gets skimmed and then distrusted.

**Must have: write for a decision maker who has no project background.** A reader must be
able to understand the result, what work is involved, what happened, and how it affects the
delivery or decision without asking the project team to translate it. Describe work before
using ticket references. State a nonstandard measurement boundary when it affects the result.
Never turn an estimate row into a claimed ticket count, or a high defect ratio into a
percentage of faulty features. Use the client's configured name for additional work.

PMS readers may have no access to the KPI workbook. Every note must stand alone: include
the relevant agreement, dates, decision and practical scope instead of saying "see
Decisions", "see Team Review" or referring to an internal sheet. Assume readers know the
standard KPIs and story points. State the unit where needed, such as defects per 100 SP;
do not teach basic definitions. Distinguish a scoped zero from an absence of all problems.

Keep each note to the result or basis plus the material cause, exception or delivery fact.
Usually two to four clauses separated by ` || ` suffice. Preserve enough work and event
context for an unfamiliar reader; do not shorten notes into unexplained fragments. Include
the formula and substituted numbers when the measurement differs from the usual KPI
interpretation. Keep only qualifications that change interpretation. Avoid generic inclusion rules,
review-process narration, or "under the project lead's instruction" wording. Retain
reviewer and authorization details in the audit rather than management notes.
Use natural sentences: explain what happened, then how it produced the number. A formula
supports the work context; it should not replace it or become a repeated "Formula:" heading.
For added scope, name the work and approved hours when supported by the approval source,
then identify the team's internal SP estimate and compare it with the original scope.
Do not say the client approved SP or an internal hours estimate unless the source says so.
Explain any shared estimate or unestimated request that affects the result.
For PI, distinguish the eligible resource count from the hours-per-person-day conversion.

When PMS caps a known or explicitly reviewed result, send its maximum and state the
actual result and cap in the note. Retain the actual value in the workbook and downstream
calculations. A reviewed publication decision keeps `value` as the actual result and sets
`pms_value` to the ceiling. A missing measurement is not a reason to send the maximum.
For cumulative measures, say "since project start" rather than "project-to-date".

The queue requests review of every KPI note, including Met and Not measured. Read the
complete generated note with its evidence and earlier explanation, rewrite the explanation
where needed, and return its `review_signature`. An empty explanation is acceptable when
the generated text already answers the reader's questions. An unknown cause stays unknown.
The review is reused only while the evidence, generated wording and explanation still match.

## The format

```
what the numbers say, in sentences || what was left out || why
```

`||` reads as a line break in the PMS note field. Everything before the last part is
generated initially, as whole sentences a person might have written. Both **Result summary**
and **Why / context** are editable yellow columns in KPI Summary. Edits are kept in the
project's `facts/reasons.yaml`. Every push rereads the configured Google Sheet (or the local
workbook when that is the configured destination); it never substitutes an older local copy.
Changed figures require renewed review of an edited summary.

Example:

> 24 SP completed across 8 accepted items || Calendar sync excluded pending QA acceptance.

For a less familiar unit:

> 5 defects per 100 SP (2/40 × 100), since project start through 08/14 || Calendar sync and kiosk
> sign-in faults; both corrections accepted by QA.

The older style - a heading, then joined fragments ("Work finished in this cycle || 685 h
across 53 items: ...") - is still available as `organization.note_style: fragments`. The
style changes the wording only; the self-test checks that it never changes a figure.

## The one rule for the "why"

**It adds only new information.** Everything else follows from that.

It must not:

- **repeat what the sentence before it said.** After "The team met every commitment it
  made", a reason starting "We met all our commitments" says nothing. Delete the sentence;
  that is almost always the whole fix.
- **restate a count the sheet already printed.** The reader has just read it.
- **open with the same words as the part before it.** "This cycle is ... || This cycle is ..."
  is the most obvious tell that nobody read the output.

It should say the thing a reader would otherwise have to ask: why the number is what it is,
what happened, what was decided and by whom.

## Things that make a note sound machine-written

**A bracketed tag instead of words.** Write "counted on the handover date", never
"[Handover]". The basis belongs in the sentence.

**Plurals and arithmetic that do not agree.** "1 item ... is", "3 items ... are". A reason
that names items - "4 of 13 were on time: A, B, C" - has to name all four. A count and a
list that disagree is the first thing a reader notices, and no automated check will catch it.
Read it.

**An open period written as though it were finished.** Keep the running ratio and name what
is still pending, with dates: "5 more items are not due until 09/22 to 09/24, so they are not
in this figure."

**A bare zero or an unsupported claim.** Explain a measured zero with its actual scope.
When a KPI needs more information, leave it unmeasured and add an actionable question to
Open Questions. Missing evidence, unavailable history and requests to confirm dates belong
there, not in PMS notes. Do not replace a gap with a plausible number or invented cause.

**Filler.** No "it should be noted that", no "in order to", no em dashes.

## Links

**No links in a PMS note.** PMS shows plain text; a URL there is noise, and the push strips
any that slip through.

Links belong in the workbook, on the words they support: write `[the 08/12 handover](https://tracker.example.com/release/demo)`,
not a bare URL at the end of a sentence. The workbook is where somebody goes to check a
number; PMS is where somebody goes to read the result.

## Voice

Short sentences. Plain words. Dates as mm/dd. Say what happened and why.

Describe the task, not the person. "The calendar sync needed more work than estimated"
rather than naming who estimated it. Effort overruns name the work.

## Before the dry run

Read every note for the period side by side, as a reader, not as an author. Duplicates and
repetition only show up when they are next to each other. Where a run is updating existing
values, pull the current notes back from PMS and read the old and new together.

If a note makes you pause, it will make a manager pause. Fix it before anyone sees it.

## What the generated part already says

Knowing this helps you spot a reason that repeats it. For each KPI the generated sentences
state the count and the percentage, the date it was measured against and on what basis
("each delivered by 09/11", "counted on the handover to the client"), what was left out and
why (items not yet due, items with no history, reports that were already in the product,
observations, rejected reports), and whether the cycle has been handed over. A first-round QA
failure is named as normal testing, not rework. A figure over 100 says PMS stores 100.

So the reason never needs any of that. It says what happened.
