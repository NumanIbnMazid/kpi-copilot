# Sources — where the plan and the numbers come from

Where scope, hours, dates and evidence come from when the tracker is not the agreed truth.

**All of it is optional.** A team with no plan document, no estimates sheet and no chat
history still gets KPIs — the ones that depend on a missing source say "Not measured" and
why, rather than guessing.

And all of it can be switched off deliberately. `mode: tracker-only` says the issue tracker is
the agreed record and nothing else should be opened, which is the fastest and most
reproducible way to run. That is a choice, not a limitation, and the readiness check treats it
as one.

```yaml
sources:
  mode: tracker-first
  plan:      {tool_id: plan-pdf,        kind: pdf,   ref: "https://drive.google.com/file/d/1qSIZ/view"}
  estimates: {tool_id: estimates-sheet, kind: sheet, ref: 1ExampleEstimatesSheetId0000000000000000000}
  timeline:  {tool_id: timeline-sheet,  kind: sheet, ref: 1ExampleTimelineSheetId0000000}
  evidence_channels: [chat-devqa, chat-mgmt]
  hours_first: plan
  hours_basis: dev+qa
```

| Field | What it is |
|---|---|
| `mode` | Which sources may answer at all: `tracker-only`, `tracker-first` (default) or `multi-source`. The biggest single lever on how long a run takes — see [09-scan-and-source-of-truth.md](09-scan-and-source-of-truth.md) |
| `plan` | The agreed scope. When the board and the plan disagree, the plan is what the client signed |
| `estimates` | Approved change requests and their hours. The source of truth for CR Rate |
| `timeline` | Date revisions and the change log. Shows which dates moved and why |
| `evidence_channels` | Tool ids searched for handovers, agreed dates and decisions |
| `hours_first` | `plan` or `tracker` — who wins when they disagree on effort |
| `hours_basis` | `dev` counts development hours only; `dev+qa` adds each item's QA hours **once that item's QA is done** |

Each of `plan`, `estimates` and `timeline` takes `{tool_id, kind, ref, note}`. `tool_id`
points at the Tools registry; `ref` is the actual link or id; `kind` is `pdf`, `sheet`,
`wiki`, `tracker` or `none`.

## What each one unlocks

| Missing | Effect |
|---|---|
| `plan` | Scope comes from the board alone. Fine for many teams; a problem when the board and the signed scope differ |
| `estimates` | CR Rate depends on the tracker's CR marker instead. If there is none, CRs go uncounted |
| `timeline` | Date revisions have to be found in chat, or set by hand |
| `evidence_channels` | Handover dates and agreed dates must be entered by hand. Several judgements lose their evidence links |

None of these stops a run. They change what can be measured, and the Gaps tab says so.

## `hours_first`

Set it to `plan` where the plan is what the client signed — then the plan's hours win over
whatever the tracker holds, and each row records `hours_source` so a reader can see which
number was used.

## `hours_basis: dev+qa`

Adds each item's QA hours to Velocity, but only once that item's QA is finished. An open
cycle is therefore not credited with QA that has not happened — which is the point.

Team-level effort that belongs to no single item (bug fixing, regression, QA support) goes
on the period as `team_hours`, and the Velocity note names it separately.

## Evidence channels

The tool ids of the chat spaces or mail threads a run searches. They are **scoped**: a
project can only name tools its account can see, and pointing at another client's channel
fails validation rather than searching the wrong place.

Mark client-facing spaces as such in the Tools registry — that is how a date agreed in a
client call is told apart from an internal decision.

→ [01-tools.md](01-tools.md)
