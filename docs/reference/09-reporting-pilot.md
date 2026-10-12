# Fixed-interval KPI pilot

Opt in per project. Other projects keep their existing cycle and count rules. Keep real profiles, contacts and evidence outside the repository.

## Configure once

```yaml
periods:
  cadence: {anchor: '2026-10-03', days: 14}
policy:
  refine_item_types: true
  velocity: {mode: per_resource_day, completion: closed, effective_from: '2026-10-03'}
  measurement_units: {defect_rate: story_points}
  measurement_targets_aligned: false
sources:
  capacity:
    kind: pms
    weekdays: [0, 1, 2, 3, 4] # Monday–Friday
    allocations: {} # PMS member ID -> fraction, e.g. '42': 0.5
    basis: pms_timelog # Use calendar for planned availability instead.
    hours_per_day: 8
    eligible_resource_ids: [42, 43] # Billable Dev and QA members.
    timesheet_crosscheck: false
    timesheet_weeks: 2
    timesheet_entry_lag_days: 7
output:
  layout: simple
  team_review: true
  notifications: {host: claude, channels: [host]}
```

The main Sheet has a dashboard, evidence registers, Team Review and Open Questions. Yellow inputs survive in-place updates. `archive-pilot` moves the original Sheet into Archived and creates the continuing pilot copy; run it once.

To replace milestone reporting for the whole project, add `start`, `end`, and `replace_existing: true` to `periods.cadence`. The anchor fixes the cutoff; project boundaries clip the opening/closing windows. Past windows are recomputed, the current one is a preview, and future ones stay unmeasured. Superseded periods leave the continuing Sheet; their private audit history is retained.

Comprehension is assessed with completed work. Client and team promises belong to their due window; an earlier delivery remains evidence without earning velocity twice.

## Read the numbers

**Velocity = completed SP or estimated hours / billable resource working days.** Closed requires reviewed implementation and QA acceptance. A finding closed without implementation is excluded. Group estimates count once when all delivery children finish; missing estimates withhold the rate.

Choose the capacity source per project. With `basis: pms_timelog`, only recorded billable Dev/QA hours on this project count. Divide those hours by `hours_per_day`; do not deduct leave again or assume full allocation. PMS returns weekly data, so the reader fetches each week and checks every reporting date. Capacity shows each person’s hours, whether they counted and why. Missing entries need review. Recent totals remain provisional until the configured entry delay passes; passing that delay does not prove that everyone logged their work.

With `basis: calendar`, capacity uses membership dates, working days, holidays, leave and configured allocation. Overlapping absences count once. Worklogs can support a review, but they do not establish scheduled availability.

Record a project agreement with `periods.cadence.agreed_delivery_date`, `delivery_date_context` and `decision_recorded_on`. It appears in Decisions and the dependent date KPIs. A future commitment is “Not due yet”, rather than a failure or a data question. Keep actual handover separate from the agreed date.

Windows include both boundary dates. Count completion, defect reports and valid rework events in their own window, through the as-of date. Retain commitments due later in that window as pending. Do not copy milestone handovers into every window or treat CR creation as approval. An unfinished window is a preview. Keep earlier totals in their original units.

Select alternate bases independently with `policy.measurement_units`: `count` (default), `story_points`, or `hours`.

| KPI | Effort-based calculation |
|---|---|
| Defect Rate | Valid defects / completed effort × 100 |
| Comprehension and delivery/date outcomes | Effort meeting the criterion / assessed effort × 100 |
| Rework | Effort of valid return events / assessed completed effort × 100 |
| Rejected/escaped defects | Effort on qualifying reports / eligible report effort × 100 |
| CR Rate | Newly approved additional effort / reviewed project baseline × 100 |

Reports need their own estimates; never assign every bug its feature's full estimate. Mixed group outcomes need member estimates. Exposure, approval and other evidence requirements still apply.

“Per 100” is a scale, not a minimum: 2 defects against 20 SP means 10 defects/100 SP. Show the actual count and effort; small scopes can swing sharply. Compare consistent windows within a project, since teams can use different SP scales.

Local review goals use `policy.pilot_targets`. Velocity can use `{strategy: previous_velocity_median, minimum_periods: 3, why: 'Comparison baseline'}`. It needs three preceding completed, fully measured windows; otherwise the target remains unset. A fixed quality goal can use `{value: 0, why: 'Provisional zero-valid-defect goal'}`. These are provisional choices. New units/ranges/targets need PMS alignment before `measurement_targets_aligned` is enabled; this never authorizes a PMS write.

## Run and review

1. Run `kpi.py run --profile <private-profile> --project <id>`; add `--run-mode unattended` for a schedule.
2. Follow NEXT. Judge only `judge/queue.json`, record answers with reasons, and run `judge`. For a partial rework decision, supply accepted candidate `event_dates` and `reopen_count`.
3. Dev and QA enter separate feedback in Team Review. A final call needs justification, reviewer and date: `Approved` for a KPI, `Yes`/`No` for an item. Feedback alone changes no number; changed evidence makes approval stale.
4. Dashboard opens the selected period’s review, questions, hours and calculations. Team Review brings together disputed decisions and missing information; a check may need the project lead rather than Dev or QA. Ticket titles carry source links. Open Questions has one answer per row, an Active questions view and retained answer history. A valid measured zero stays zero. Missing evidence stays unmeasured with the required next step. Final team decisions enter the relevant KPI notes.
5. Run `kpi.py verify` after each Sheet update. PMS submission still requires the person's approval of concrete results.

Additional requests add deliverables; change requests alter agreed requirements. The assistant reviews that distinction from the request and scope, and asks when the evidence is missing. Bug reports remain separate from the work that fixes them; a bug in an older release is not automatically an escaped defect of the current project.

## Schedule and notify

Choose one active host: Claude, Codex or another configured assistant. A Saturday wakeup checks whether a new fortnight finished Friday, stays quiet on off weeks, and retries failures. Store prepared-period and delivery receipts privately to avoid duplicates.

`status.json`/`status.md` give any host the status, Sheet link and actions. Configuring the tool does not install schedules in other applications. Local routines require an awake, connected computer; cloud routines also need private inputs and authenticated source connections available remotely. Connection failures are blockers, not permission to reuse stale data.

Configure `output.notifications.channels` and recipients privately. Email supports TLS SMTP, or `email.route: host_gmail` with `from`/`to` through a verified host Gmail connector. Phone delivery needs a supported HTTPS webhook gateway and recipients. Secrets stay in environment variables. Missing connections remain visible as questions.

`run` prepares notifications; it does not send them. `notify` previews SMTP/webhook delivery, and `--apply` sends through configured channels. Host Gmail delivery uses the host connector. A prepared Sheet and a delivered notification are separate states. Native routine results provide the selected host's notification; PMS approval remains separate.
