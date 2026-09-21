# Sources — where the plan and the numbers come from

[Documentation](../README.md) · [Field guide](../16-Configuration-Field-Guide.md)

Where scope, hours and dates come from when the tracker is not the agreed truth.

**This list is an allowlist.** A run reads the tracker and the sources named here, and
nothing else - no chat, no mail, no wandering through Drive. What they cannot answer becomes
a question on the Open Questions tab, asked once. That is what keeps a run to minutes.

**All of it is optional.** A team with no plan document and no estimates sheet still gets
KPIs - the ones that depend on a missing source say "Not measured" and why, rather than
guessing. `mode: tracker-only` says the issue tracker is the agreed record and nothing else
should be opened: a choice, not a limitation, and the readiness check treats it as one.

```yaml
sources:
  mode: tracker-first
  plan:
    kind: pdf
    ref: "https://drive.google.com/file/d/1ExamplePlan/view"   # a Drive link or id, a URL, or a local path
  estimates:
    kind: sheet
    ref: 1ExampleEstimatesSheetId0000000000000000000
    map:                                   # read through a column mapping - no re-reading, no digest
      tab: Estimates
      columns: {board_key: Ticket, title: Item, dev_hours: "Dev (h)", qa_hours: "QA (h)",
                approved_on: Approved, period: Period}
  timeline:
    kind: sheet
    ref: 1ExampleTimelineSheetId0000000
    map:
      events: {tab: Plan, columns: {event: Event, period: Period, type: Type, baseline: Baseline,
                                    actual: Actual, state: State}, handover_types: [Handover]}
      log:    {tab: Log, columns: {date: Date, type: Type, period: Period, what: "What happened",
                                   why: "Why", kpi: KPI}}
  evidence_channels: []                    # only ever used by a deep run
  hours_first: plan
  hours_basis: dev+qa
```

## How a source is read

**Fetched straight to disk, and only when it changed.** Drive says when a file was last
modified; if that has not moved since the cached copy, nothing is downloaded. The plan PDF is
reused until its source changes. This needs Google connected
([03-Prerequisites](../03-Prerequisites.md)); without it, drop an export in
`<project>/inbox/plan.pdf` (or `estimates.xlsx`, `timeline.xlsx`) and it is picked up.

**Never re-read for the same facts.**

- A **table** (estimates sheet, timeline, a plan kept as a sheet) is read through `map`: the
  column headers that hold each field, written once at setup. Later runs use that mapping. The header row is found by itself, and a header may carry a suffix in the
  sheet ("Actual (auto)").
- A **document** (a PDF plan) is digested **once** by the assistant into
  `<project>/facts/plan.yaml` - the items, their hours, their milestones. The digest records
  the fingerprint of what it was written from, so when the plan changes the run says so
  instead of trusting the old copy.

From a mapped timeline the run takes each period's handover date (the latest *done* event of
a handover type) and keeps the KPI-flagged log entries as context for writing notes. Anything
a person typed in the sheet or the facts file wins over what the mapping found.

→ [Facts file shapes](../../plugin/kpi-copilot/skills/kpi-run/references/facts.md)

| Field | What it is |
|---|---|
| `mode` | Which sources may answer at all: `tracker-only`, `tracker-first` (default) or `multi-source`. The biggest single lever on how long a run takes — see [09-scan-and-source-of-truth.md](09-scan-and-source-of-truth.md) |
| `plan` | The agreed scope. When the board and the plan disagree, the plan is what the client signed |
| `estimates` | Approved change requests and their hours. The source of truth for CR Rate |
| `timeline` | Date revisions and the change log. Shows which dates moved and why |
| `evidence_channels` | Places a **deep run** may look up the open questions. A normal run never searches them |
| `hours_first` | `plan` or `tracker` — who wins when they disagree on effort |
| `hours_basis` | `dev` counts development hours only; `dev+qa` adds each item's QA hours **once that item's QA is done** |

Each of `plan`, `estimates` and `timeline` takes `{tool_id, kind, ref, note}`. `tool_id`
points at the Tools registry; `ref` is the actual link or id; `kind` is `pdf`, `sheet`,
`wiki`, `tracker` or `none`.

## What each one unlocks

| Missing | Effect |
|---|---|
| `plan` | Scope comes from the board alone. Fine for many teams; a problem when the board and the signed scope differ |
| `estimates` | CR Rate depends on the tracker's CR marker instead. Without approval/baseline evidence, review the gap rather than assuming no changes |
| `timeline` | Handover dates are typed once on the Periods tab instead |
| `evidence_channels` | Nothing. Open questions go to a person, which is the default anyway |

An unconfigured optional source is not required. A configured source that is missing, stale
or invalid is a repair task, can withhold affected facts, and can block PMS submission.
Open Questions and NEXT make those gaps visible.

## `hours_first`

Set it to `plan` where the plan is what the client signed — then the plan's hours win over
whatever the tracker holds, and each row records `hours_source` so a reader can see which
number was used.

## `hours_basis: dev+qa`

Adds each item's QA hours to Velocity, but only once that item's QA is finished. An open
cycle is therefore not credited with QA that has not happened — which is the point.

Team-level effort that belongs to no single item (bug fixing, regression, QA support) goes
on the period as `team_hours`, and the Velocity note names it separately.

## Evidence channels, and deep runs

A normal run does not search chat or mail, whatever is listed here. When a person asks for
more - `kpi.py run --deep`, or "also check the client chat" - the assistant may look up **the
open questions only**, in **the places listed here** (or the ones just named), and records
each answer with its link. They are **scoped**: a project can only name tools its account can
see, and pointing at another client's channel fails validation rather than searching the
wrong place.

→ [01-tools.md](01-tools.md)

For actual column mappings and their outcomes, see the
[fictional source files](../../samples/README.md) and [walkthrough](../../samples/WALKTHROUGH.md).
