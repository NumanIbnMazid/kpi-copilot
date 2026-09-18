# Periods and counting rules

How a project is sliced for PMS, and the few counting choices a team may make.

---

## `periods`

```yaml
periods:
  model: Delivery cycle       # Milestone | Delivery cycle | Sprint | Month | Quarter | Full project
  naming: "Initial Scope, Additional Requests N"
  client_check_default: Handover
```

| Field | What it is |
|---|---|
| `model` | How you slice a project. Sets the default period type |
| `naming` | The convention. **PMS allows 25 characters** in a period name |
| `client_check_default` | `Handover` = the client date is met when the period's build reached the client by the date. `Delivery` = met when the item itself was delivered |

**`client_check` matters more than it looks.** Use `Delivery` for a feature freeze — where
the rule is "no new features after this date" and bug fixes legitimately continue. Use
`Handover` normally.

Periods themselves are not configured here: they come from the extract, and their dates and
notes are edited on the Periods tab of the tracker workbook.

## `policy` — the counting choices you may make

```yaml
policy:
  count_observations: false
  count_improvements: false
  count_pre_existing: false
  count_post_release: true
```

| Choice | Default | Effect |
|---|---|---|
| `count_observations` | no | Count observations as defects in Defect Rate |
| `count_improvements` | no | Count improvements as defects |
| `count_pre_existing` | no | Count defects that were already in the product |
| `count_post_release` | yes | Count defects found after handover in Defect Rate. They always count in Escaped Defect Rate |

**Rejected reports are never defects.** That one is not a choice.

Everything not listed here is fixed by the engine, deliberately — see
[../00-Philosophy.md](../00-Philosophy.md). Whatever is excluded is **named in the note**:
*"Also reported but not counted: 11 that were already in the product, 6 observations, 2
closed as not a bug."* Nothing is quietly dropped.

## Where the counting rules are written down

`skills/kpi-run/references/kpi-rules.md` holds all nine, with the PMS formula for each and
the reasoning behind the awkward cases. Read it before arguing with a number.

Two that surprise people, both correct:

- **Delivery Commitment counts only items the team committed to.** PMS measures reliability
  of promises, not volume of work. Items with no commitment are left out and named.
- **Escaped Defect Rate divides by defects, not by items.** *Defects found after release /
  total defects, before and after.* The question is what share of the problems reached the
  client.
