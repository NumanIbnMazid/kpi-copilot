# Fixed-interval KPI pilot

Opt in per project. Other projects keep their existing cycle and count rules. Keep real profiles, contacts and evidence outside the repository.

## Configure once

```yaml
periods:
  cadence: {anchor: '2026-10-03', days: 14}
policy:
  refine_item_types: true
  measurement_review: true # Reviewed pilot formulas; leave off for legacy rules.
  velocity: {mode: total, completion: closed, effective_from: '2026-10-03'}
  productivity_index: {enabled: true}
  measurement_units:
    defect_rate: story_points
    rework_rate: story_points
    task_comprehension: story_points
    client_expectation: story_points
    delivery_commitment: story_points
    cr_rate: story_points
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

**Velocity = total completed story points in the reporting period. Productivity Index (PI) = completed story points / productive project person-days.** These are separate fields in results, workbooks and Google Sheets. Until the PMS registry provides a PI field, its reviewed note accompanies Velocity; Velocity's numeric value stays the total. When the registry supplies a PI field ID, the note fallback stops automatically. PI does not borrow Velocity's target or its units. Existing hour-based projects retain their output total, but PI remains unmeasured until story points are available.

Closed requires reviewed implementation and QA acceptance. A finding closed without implementation is excluded. Group estimates count once when all delivery children finish; missing estimates or unresolved acceptance withhold the full output total. Missing productive effort withholds PI without suppressing a confirmed Velocity total. For shared defaults across projects, set `policy.productivity_index.enabled` in the profile root; project overrides remain explicit. The older `per_resource_day` Velocity mode is supported only when separate PI is disabled.

Choose the capacity source per project. With `basis: pms_timelog`, only recorded billable Dev/QA hours on this project count. Divide those hours by `hours_per_day`; do not deduct leave again or assume full allocation. PMS returns weekly data, so the reader fetches each week and checks every reporting date. Capacity shows each person’s hours, whether they counted and why. Missing entries need review. Recent totals remain provisional until the configured entry delay passes; passing that delay does not prove that everyone logged their work.

With `basis: calendar`, capacity uses membership dates, working days, holidays, leave and configured allocation. Overlapping absences count once. Worklogs can support a review, but they do not establish scheduled availability.

The eligible resource count is separate from `hours_per_day`. For example, three
eligible resources recording 120 project hours contribute 15 person-days at eight
hours per day. Divide completed points by 15; do not divide by three again.

A lead can confirm a person's time entries are complete for an explicit date range with
`sources.capacity.completion_confirmations` (`resource_id`, `start`, `end`, `confirmed_on`,
`by`, `why`). This permits an actual zero in a fully covered window; it never invents
hours, removes the participant, or confirms future windows.

Record a project agreement with `periods.cadence.agreed_delivery_date`, `delivery_date_context` and `decision_recorded_on`. It appears in Decisions and the dependent date KPIs. A future commitment is “Not due yet”, rather than a failure or a data question. Keep actual handover separate from the agreed date.

Windows include both boundary dates. Completion, decided reports and newly approved requests use their relevant window. The reviewed pilot records quality history against the original work or release: defect density and affected rework scope are project-to-date snapshots at each cutoff. Return dates remain visible; a late bug is not divided by unrelated work completed that fortnight. Retain commitments due later as pending. Do not copy milestone handovers into every window or treat CR creation as approval. An unfinished window is a preview. Keep earlier totals in their original units.

Select alternate bases independently with `policy.measurement_units`: `count` (default), `story_points`, or `hours`.

| KPI | Reviewed pilot calculation |
|---|---|
| Defect Rate | Confirmed unique defects linked to completed work / original estimate of that completed work × 100 |
| Comprehension and delivery/date outcomes | Effort meeting the criterion / assessed effort × 100 |
| Rework | Original estimate of reviewed work with a valid return / original estimate of all reviewed work after the agreed boundary × 100; each affected item once |
| Rejected defects | Confirmed rejected reports / confirmed accepted or rejected reports × 100; pending decisions shown separately |
| Escaped defects | Confirmed post-release defects / confirmed pre- and post-release defects from that same release × 100 |
| CR Rate | Newly approved additional effort / reviewed project baseline × 100 |

Rework shows affected scope, not correction time. Repeated returns stay in the notes. To measure actual corrective effort in an FTE sprint, divide separately recorded correction hours by all recorded team hours in that sprint, including correction hours. No lifetime budget is required. That hours method needs explicit time attribution and is not inferred from original estimates.

Keep rejection and escape count-based under `measurement_review`. Invalid reports need no fictional fix estimate. Retain the agreed rejection reasons, naming duplicates separately. Defects must link to implementation, not a grouping or testing card. Mixed group outcomes need member estimates. Changed requirements need a separate incremental estimate; the pilot withholds the rate rather than using a replacement feature's full estimate. Exposure, approval and other evidence requirements still apply.

Missing implementation links and approval dates enter the normal judgement queue with
source context. Review and retain those inputs instead of overriding the resulting rate.
Independent member story points remain usable even when hours belong to a shared group.
An entire group approved in one window uses its agreed group estimate once; a shared
budget cannot be split across approval windows without agreed member estimates.

“Per 100” is a scale, not a minimum: 2 defects against 20 SP means 10 defects/100 SP. Show the actual count and effort; small scopes can swing sharply. Compare consistent windows within a project, since teams can use different SP scales.

Local review goals use `policy.pilot_targets`. Velocity can use `{strategy: previous_velocity_median, minimum_periods: 3, why: 'Comparison baseline'}`. It needs three preceding completed, fully measured windows; otherwise the target remains unset. A fixed quality goal can use `{value: 0, why: 'Provisional zero-valid-defect goal'}`. These are provisional choices. New units/ranges/targets need PMS alignment before `measurement_targets_aligned` is enabled; this never authorizes a PMS write.

When changing Velocity from a rate to a total, review existing targets in their original units. Never reuse a per-day target as a total-point target or compare totals with historical rates.

## Run and review

1. Run `kpi.py run --profile <private-profile> --project <id>`; add `--run-mode unattended` for a schedule.
2. Follow NEXT. Judge only `judge/queue.json`, record answers with reasons, and run `judge`. For a partial rework decision, supply accepted candidate `event_dates` and `reopen_count`.
3. Dev and QA enter separate feedback in Team Review. A final call needs justification, reviewer and date: `Approved` for a KPI, `Yes`/`No` for an item. Feedback alone changes no number; changed evidence makes approval stale.
4. Dashboard opens the selected period’s review, questions, hours and calculations. Team Review brings together disputed decisions and missing information; a check may need the project lead rather than Dev or QA. Ticket titles carry source links. Open Questions has one answer per row, an Active questions view and retained answer history. A valid measured zero stays zero. Missing evidence stays unmeasured with the required next step. Final team decisions enter the relevant KPI notes.
5. Run `kpi.py verify` after each Sheet update. PMS submission still requires the person's approval of concrete results.

For a person-approved estimate CSV, use `scripts/import_story_points.py --profile <private-profile> --project <id> --file <private-csv> --evidence <source-url> --why <approval-context>`. The dry run checks every ticket key and estimate before any change. Add `--apply` to record the estimates in the judgement ledger and retain the source and prior ledger privately, then run the normal pipeline. CSV status labels never establish delivery or acceptance.

Additional requests add deliverables; change requests alter agreed requirements. The assistant reviews that distinction from the request and scope, and asks when the evidence is missing. Bug reports remain separate from the work that fixes them; a bug in an older release is not automatically an escaped defect of the current project.

### Publishing a reviewed explanation without a score

When the person explicitly requests notes for an unresolved measurement, record a
`notes_only` publication decision rather than inventing a number or changing PMS targets.
`scripts/publication_decisions.py --profile <private-profile> --project <id>
--decisions <private-json>` validates a dry run; `--apply` records the decisions locally.
Each decision names the period, KPI, current measurement basis, published note, rationale,
reviewer and user authorization. Question dispositions identify the notes-only measurements
that address them. They do not change unknown dates or item judgements into facts.

Then use the normal run, note review and PMS push. The Sheet shows a blank numeric result,
the explanation and a row in Decisions; the original computed figure remains in the audit.
Any changed measurement invalidates its publication decision and blocks submission until
reviewed again. Source, sheet-readback, approval and PMS read-back checks remain in place.

An explicitly authorized `reviewed_value` decision additionally records the actual
numeric `value`. It does not replace unknown source facts. If that result exceeds
the PMS range, explicitly set `pms_value` to the ceiling and explain both figures in
the note. The actual value remains in the Sheet and the audit; a missing measurement
cannot be replaced with the ceiling. Decisions expire when their measurement basis changes.

## Schedule and notify

Choose one active host: Claude, Codex or another configured assistant. A Saturday wakeup checks whether a new fortnight finished Friday, stays quiet on off weeks, and retries failures. Store prepared-period and delivery receipts privately to avoid duplicates.

`status.json`/`status.md` give any host the status, Sheet link and actions. Configuring the tool does not install schedules in other applications. Local routines require an awake, connected computer; cloud routines also need private inputs and authenticated source connections available remotely. Connection failures are blockers, not permission to reuse stale data.

Configure `output.notifications.channels` and recipients privately. Email supports TLS SMTP, or `email.route: host_gmail` with `from`/`to` through a verified host Gmail connector. Phone delivery needs a supported HTTPS webhook gateway and recipients. Secrets stay in environment variables. Missing connections remain visible as questions.

`run` prepares notifications; it does not send them. `notify` previews SMTP/webhook delivery, and `--apply` sends through configured channels. Host Gmail delivery uses the host connector. A prepared Sheet and a delivered notification are separate states. Native routine results provide the selected host's notification; PMS approval remains separate.
