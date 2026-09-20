# Writing the notes

Management reads the notes, not the spreadsheet. A number without a note is a number nobody
can act on, and a note that reads like machine output gets skimmed and then distrusted.

## The format

```
what the numbers say, in sentences || what was left out || why
```

`||` reads as a line break in the PMS note field. Everything before the last part is
generated, as whole sentences a person might have written. The last part - the **why** - is
the only part a person (or the assistant, from `judge/queue.json`) writes, and it lives in the
project's `facts/reasons.yaml` and in the yellow column of KPI Summary.

Example:

> The team completed 685 hours of work in this cycle, across 53 delivered items: 39 from the
> plan and 14 additional requests. || That is 432 hours of development and 118 hours of QA,
> plus 135 hours of shared work such as bug fixing, QA checks and regression. || The hours for
> the additional requests come from the Additional Effort Estimates sheet, which Northwind
> approved on 07/31 and 08/12.

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

**A bare zero or a bare blank.** Say why: "Nothing to measure yet: all 6 items are still
ahead of 09/22 and the handover has not happened." "Not handed over to the client yet, so
there is nothing to measure."

**Filler.** No "it should be noted that", no "in order to", no em dashes.

## Links

**No links in a PMS note.** PMS shows plain text; a URL there is noise, and the push strips
any that slip through.

Links belong in the workbook, on the words they support: write `[the 08/12 handover](url)`,
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
