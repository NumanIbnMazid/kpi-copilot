# Investigate a result or a slow run

Start with the run's **NEXT**, Open Questions and register evidence. Do not refetch individual
cards in a browser. The project folder is `<profile folder>/<project id>/`; its `ledger.json`
records judgements, authors and reasons. It is not directly beside the profile.

## Correct a decision

Change the supported yellow cell and refresh, or write the documented answer shape to
`<project>/judge/answers.json` and run `kpi.py judge --human`. Read the queue's answer schema;
it is a JSON document, not a line of arbitrary prose. Human decisions take precedence over
assistant decisions, which take precedence over rules.

## Read timing evidence

The runner prints stage timings. Separate data collection and workbook writing from the
time spent obtaining answers and reviewing notes. Provider latency, pagination, rate limits
and board size vary; a fixed seconds-per-run promise is not justified.

Asana can reuse unchanged item histories. Jira and GitHub refresh membership so removed or
out-of-scope items do not persist merely because they were cached. Do not assume every
adapter fetches only changed cards. Diagnose a slow `board`, `sources` or `sheet` stage from
its error/progress output and cache permissions before narrowing scope. A narrower scan must
still contain the evidence needed for the selected period.

## Compare inputs with the agreed rule

| Symptom | What to inspect |
|---|---|
| Delivery dates or Velocity look wrong | `workflow.delivered_when` and recorded events. Closed is valid if it is the actual promise; otherwise choose the agreed event. |
| Too few tasks | Excluded rows and the exact title/assignee filter. Broad patterns can remove real work. |
| Commitment or expectation differs | Item, milestone, period and project dates; only an agreed revision changes the promise. |
| Effort differs | `sources.hours_first`, units, grouped scope and QA completion. A missing estimate is not zero. |
| Rework is high | Closure boundary and reopen events. A first testing failure before closure is not reopening. |
| Values are Not measured | The missing capability, evidence or eligible population named by the run. Native history helps only when the underlying facts exist. |

A missing handover date may mean it is unknown or that handover has not happened. Ask; do
not claim that the client never received the release solely because the date is blank.

## Other cases

- **A result exceeds 100%.** Inspect the numerator and denominator. Preserve the true result;
  PMS numeric limits and any clamping must be visible in the reviewed preview and notes.
- **Missing PMS period.** Preview first. The CLI can create missing periods with
  `push --apply --create-periods` only after explicit approval of submission and creation.
  The MCP submission tool does not expose the creation flag.
- **Period name rejected.** Check the PMS limit (the runner enforces 25 characters) and
  resolve the intended period without silently changing the reporting scope.
- **Values changed.** Compare the run's change report and retained inputs. Same-date runs
  can replace files in `<project>/runs/<date>/`; use distinct run labels or private backups
  when retaining approved history.
- **The same assistant question returns.** A changed card can invalidate its prior decision.
  Human answers are durable; uncertain assistant answers should remain null with a reason.
- **Plan facts empty or stale.** Follow [facts.md](facts.md), digest only the named source,
  and set the supplied fingerprint. Never fabricate plan facts to silence the question.
- **Wrong period or item type.** Correct the supported register field, refresh and inspect
  affected results. Preserve the reason for the decision.
- **Target differs.** Inspect its source. Refresh the PMS registry when needed. A local
  target requires value and reason, is labelled as local, and blocks PMS submission until
  reconciled; it is not a covert replacement for the PMS target.

For setup failures, see the repository's
[user troubleshooting guide](https://github.com/NumanIbnMazid/kpi-copilot/blob/main/docs/14-Troubleshooting.md).
