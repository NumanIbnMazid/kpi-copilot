# When a number looks wrong

Almost every wrong number has one of six causes. Work down the list; it is roughly ordered by
how often each one turns out to be it.

## 1. The delivered-when mapping

**Symptom:** Delivery Commitment is suspiciously high or low; Velocity counts things that are
not finished, or misses things that are.

**Cause:** `workflow.delivered_when.values` names the wrong state. Using the closed state
here is the classic error - it flatters every delivery figure, because closed comes later
than the point at which the work was actually delivered.

**Check:** open three items you know the delivery date of and compare with the `delivered`
field in the KIF.

## 2. An exclusion pattern eating real work

**Symptom:** the item count is lower than the board, denominators look small, CR Rate is odd.

**Cause:** a regex in `conventions.exclude_patterns` is broader than intended. `^Bug` will
happily remove "Bug tracking dashboard" and also "Bugfix: client login".

**Check:** the Gaps and Task Register tabs of the tracker workbook list every excluded row
with its reason. Read them.

## 3. The date level

**Symptom:** Client Expectation or Delivery Commitment disagrees with what the team believes.

**Cause:** the wrong date is winning. Most specific wins: item override > rule > milestone >
period > project.

**Check:** the Periods tab shows the dates in force. Remember the rule - a plan the team
revised on its own does not move a KPI date.

## 4. The hours source

**Symptom:** Velocity is well off.

**Cause:** `sources.hours_first` is pointing at the tracker when the plan is the agreed
source, or `hours_basis: dev+qa` is crediting QA hours for work whose QA has not finished.

**Check:** `hours_source` on each row in the Task Register says which number won.

## 5. Rework counting first-round QA failures

**Symptom:** Rework Rate is much higher than the team recognises.

**Cause:** `reopened_when.ignore_first_qa_fail` is off, or the adapter is treating any move
into a failure state as a reopen. Rework is **closed, then reopened**. A QA failure while the
item is still being tested for the first time is normal testing.

## 6. The adapter could not see something

**Symptom:** several KPIs say "Not measured".

**Cause:** working as designed. The adapter declared it cannot read status history or
comments, so the engine refuses to guess.

**Fix:** either accept it - and tell management which KPIs are limited and why - or move from
the `csv` adapter to a native one. The Gaps tab lists each one with its reason.

---

## Other things that happen

**"Not measured" on Escaped Defect Rate.** The period has no handover date. This is correct:
nothing can escape from a cycle the client has never seen. Set the handover date once the
build goes out.

**A value over 100.** Real, and sent to PMS clamped, with the true figure in the note. Usually
it means a small denominator - a cycle with two delivered items and five bugs.

**PMS rejects a period name.** 25 characters maximum.

**The push says a period id is missing.** Create the period in PMS first; the push updates
periods, it does not create them.

**Numbers changed since last run and nobody knows why.** Each run keeps its extract, results
and payload under `runs/<date>/`. Diff the two KIF files - the change is in the input, not in
the engine.

**Delivery Commitment counts more or fewer items than you expect.** Its denominator is the
items the team *committed to*, not every deliverable - that is what PMS asks for, because the
KPI measures reliability of promises rather than volume of work. Items with no commitment
date are left out and named in the note. If your team commits to the whole scope as one
piece, set `workflow.commitment.scope: all-deliverables`.

**Delivery Commitment says "Not measured".** No item in the period carried a commitment date.
Record what the team promised, or say the scope is committed as a whole.

**A target looks wrong for this kind of project.** Change it on the project in PMS — targets
are configurable per project, and that is the right place. Refresh the registry and the next
run uses it, marked as this project's own. A target set in the profile instead is refused, so
the workbook and PMS cannot disagree about the same number.

**A target is not the one you expected.** Check `threshold_source` on the measure, or the
"Target set by" column in the workbook. It says whether the bar came from this project's PMS
setting, the PMS default, or the bundled fallback because PMS was unreachable.
