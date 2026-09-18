# Working in Google Sheets

`scripts/workbook.py` produces an xlsx, which suits most teams. A team that lives in Google
Sheets wants the same content in a live sheet instead. That is supported, and Sheets fights
back in a few specific ways that are worth knowing before you start.

## The approach

Copy a template sheet per project (Drive `copy_file`), then write the tabs from a signed-in
browser tab. Build every tab in one pass rather than cell by cell.

Order matters: insert all the `#` columns first. Inserting a column later shifts formulas on
tabs already written.

## The things that will surprise you

**A hidden tab stops saving.** Chrome throttles a tab hidden for a few minutes, and Sheets
then silently stops persisting scripted edits. Reload the tab immediately before a long
write, keep it visible, and verify after the first section that the edit actually saved
rather than assuming it did.

**Pasting in Google's own clipboard format drops links.** A paste carrying
`data-sheets-root` keeps colours, borders and number formats but strips every `<a>`. To keep
links on the words, write those cells again as plain web HTML - links survive, the cell
background does not - and then restore the formatting with Paste special > Format only from a
scratch cell.

**A re-pasted cell falls out of conditional formatting.** Paste the rules back with Paste
special > "Conditional formatting only" from a cell that still has them, and then check the
rule ranges. A rule that reads `M21:M1000` when it should read `M5:M1000` means the current
rows lost it.

**Numbers can turn into dates.** Carry an explicit number format on each pasted cell.
Without it, 685 becomes a date.

**Sheets substitutes its own last clipboard content** when the pasted plain text matches it.
Append an invisible unique mark to the text to defeat that.

**Data validation must be rebuilt each run** from the current lists, or the sheet fills with
"Input must be an item on the specified list" warnings.

**Reads are rate-limited.** The CSV export endpoint returns 429 under repeated use. Keep
reads few and back off rather than treating a 429 as a failure.

**Charts cannot be pasted.** Write the chart data to a fixed range and have the person insert
the charts once by hand; they update themselves afterwards.

## Layout

Keep every tracker looking the same, whoever built it: a `#` counter in column A of each
list, dark blue headers, one thin border, wrapped text, yellow for cells a person edits and
grey for formulas. A reader who has seen one project's tracker should be able to read
anybody's.
