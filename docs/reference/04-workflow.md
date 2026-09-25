# Workflow — what your states mean

[Documentation](../README.md) · [Field guide](../16-Configuration-Field-Guide.md)

The most important section in the profile. It is what turns "a column called In Test" into a
number comparable across the company.

```yaml
workflow:
  delivered_when:
    signal: status-entered
    values: [Ready for QA, Testing, Dev Complete]
    from_date: "2026-09-10"
    fallback_values: [Dev Complete]
  closed_when:
    values: [Closed]
    completed_flag_means: "On these boards 'complete' means merged, not accepted."
  reopened_when:
    values: [In Progress, Testing Failed]
    ignore_first_qa_fail: true
  clarification_when:
    values: [Awaiting Feedback]
    also_comments: true
    exclude_reasons: [build, environment, access]
  commitment:
    scope: committed-only
    met_when: delivery
```

---

## `delivered_when` — your delivery event

When an item counts as delivered. **Velocity** counts what reached it, and it is the default
meaning of "delivered on time" for a commitment.

| Field | What it is |
|---|---|
| `signal` | `status-entered` (usual), `label-added`, `field-set`, `closed`, `manual` |
| `values` | Your state names. The **first** entry into any of them |
| `from_date` | Apply this rule only from a date onward, when the process changed mid-project |
| `fallback_values` | The rule before `from_date` |

**Use the event actually promised.** Delivery might mean QA handoff, final acceptance or
client handover. The closed state is appropriate only when closure fulfills that agreement.
Choosing a later event changes dates; it does not inherently improve the score.

`from_date` exists because teams change process mid-project. Without it, a change in
September retroactively rewrites six months of delivery dates.

## `closed_when`

| Field | What it is |
|---|---|
| `values` | States meaning accepted and finished |
| `completed_flag_means` | What your tracker's own "complete" flag means here |

That second field looks like a comment and is not. On some boards "complete" means merged;
on others, accepted by QA. Getting it wrong shifts every delivery date, quietly.

## `reopened_when` — what counts as rework

Rework Rate is **closed, then reopened**.

| Field | What it is |
|---|---|
| `values` | States meaning "back in play after being closed" |
| `ignore_first_qa_fail` | Default yes. A QA failure while the item is still being tested for the first time is normal testing, not rework |
| `no_history` | `unknown` (default) leaves a completed task with no reopen on record out of the rate. `not-reopened` counts it as not reopened, and the note says so. A ticket inside a group that was reopened is never assumed: the reopen is on record, just not which ticket needed the change |

Leave `ignore_first_qa_fail` on unless you have a specific reason. Turning it off is the most
common way a Rework Rate comes out far too high — and it is named in the note as not counted,
so nothing is hidden by leaving it on.

## `clarification_when` — Task Comprehension

Did the team have to go back to the client about **what the thing should do**.

| Field | What it is |
|---|---|
| `values` | States meaning "waiting on the client" |
| `also_comments` | Also treat a comment asking the client to clarify behaviour as "had to ask" |
| `exclude_reasons` | Words meaning the block was a dependency, not a misunderstanding. Default: build, environment, access |

Going to a blocked state because a build was missing is a dependency, not a comprehension
problem. That distinction is what `exclude_reasons` is for.

## `commitment` — what your team promises

PMS defines Delivery Commitment as *"team-negotiated commitments that were delivered on
time"*, over *total team-committed task count*, with the insight *reliability of the team*.

So two things need saying, because teams differ on both.

| Field | Default | What it is |
|---|---|---|
| `scope` | `committed-only` | `committed-only` counts just the items the team negotiated a date for — what PMS asks for. `all-deliverables` treats every item as committed, for a team that commits to the whole scope as one piece |
| `met_when` | `delivery` | What keeping a commitment means, as a phrase that goes into the note. `delivery` uses your delivery event; `handover` means the build reached the client; `completion` means the item was closed. Other wording is descriptive; it does not add a new event detector |

```yaml
# A team that promises dates per item, delivered to QA
commitment: {scope: committed-only, met_when: delivery}

# A team that promises the client a release date for the whole cycle
commitment: {scope: all-deliverables, met_when: handover}

# A team that promised something specific
commitment: {scope: committed-only, met_when: "the demo environment was updated"}
```

Items with no commitment are **left out and named** in the note — an item nobody promised is
not evidence of reliability either way. A period where nothing was committed comes back "Not
measured", not 0%.

---

## Getting this wrong

| Symptom | Usually |
|---|---|
| Delivery Commitment differs from the agreement | The configured event or commitment date does not match the actual promise |
| Rework Rate is far too high | `ignore_first_qa_fail` is off, or `reopened_when` includes a state reached before closing |
| Task Comprehension is too low | `clarification_when` is catching build and environment blocks — check `exclude_reasons` |
| Delivery Commitment counts fewer items than expected | Correct. It counts commitments, not deliverables |
| Every delivery date is a day out | A timezone or a `from_date` boundary |

## See also

- [KPI rules](../../plugin/kpi-copilot/skills/kpi-run/references/kpi-rules.md) — the counting rules in full
- [03-tracker-and-conventions.md](03-tracker-and-conventions.md) · [all-fields.md](all-fields.md)

`reopened_when.closed_values` can set a separate rework closure boundary. Keep that
meaning explicit in the notes; see the [field guide](../16-Configuration-Field-Guide.md).
