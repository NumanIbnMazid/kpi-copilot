# Custom instructions

Your own instructions, which take precedence over the tool's defaults.

```yaml
custom_instructions:
  notes_style: "Two sentences at most. Name the ticket, never the person. Dates as mm/dd."
  always:
    - "Show the previous period next to the new one so a jump is visible."
    - "Flag any KPI that moved more than 20 points since the last run."
  never:
    - "Never post to the client-facing chat space."
    - "Never push to PMS on a Friday after 5pm Dhaka time."
  glossary:
    - "Handover means the build that reached the client, not the internal release."
    - "MK = the PartnerSync integration."
  escalation: "Ask me in chat. If I have not answered by the next working day, hold the run."
  rule_overrides:
    - rule: defect_phase
      value: "Bug 41 = Post-release"
      why: "Reported eight days after the 08/12 handover, so it escaped."
      approved_by: "A. Rahman"
```

| Field | What it is |
|---|---|
| `notes_style` | How you want the "why" text to read. Free text, followed when notes are written |
| `always` | Things to do on every run |
| `never` | Things never to do |
| `glossary` | Words your team uses that an outsider would misread |
| `escalation` | What to do when a decision is needed and you are not there |
| `rule_overrides` | Project facts the defaults get wrong. Applied, and printed above the numbers |

**The glossary is more useful than it looks.** It stops a note being technically correct and
still misleading — the failure mode nobody catches in review.

## Rule overrides

For a project fact the defaults get wrong. Each is applied and then printed at the **top** of
every run summary, before the numbers.

| Rule | Value looks like |
|---|---|
| `delivered_signal` | `In Review` |
| `client_date_source` | `the Confluence plan` |
| `commit_date_source` | `the sprint commitment` |
| `cr_denominator` | `period` or `project` |
| `exclude_key` | `TKT-3333` |
| `include_key` | `TKT-3401 = CR` |
| `defect_phase` | `Bug 41 = Post-release` |
| `hours_source` | `plan` |
| `period_of_key` | `TKT-3653 = Additional Requests 1` |
| `velocity_team_hours` | `Initial Scope = 135` |

`why` is **required** — it appears in the run summary, so write it for somebody who was not
in the room. `expires` makes a run warn when an override has gone stale.

An unsupported rule is reported, not silently dropped.

## What does not go here

**Targets.** They are configurable per project in PMS, which is the right place. Setting one
here is refused, and the refusal says where to set it instead — a target in two places is how
the workbook ends up saying "Met" while PMS says "Not met".

**Counting rules.** What delivered, defect and rework mean is shared by everyone. Changing
one is a conversation, because it moves every project's numbers at once.

## Letting it learn

Most of this never gets typed. Say it in chat — *"always show me the previous period"*,
*"save the sheets in this folder"*, *"never push on a Friday"* — and Claude will offer to
write it down:

```bash
python3 scripts/remember.py --profile profile.yaml \
  --add custom_instructions.always="Show the previous period" --why "asked in chat"
```

Three things always hold: it asks first, `--why` records the sentence you said, and a change
that would break the profile is rolled back.

```bash
python3 scripts/remember.py --profile profile.yaml --history
```

shows everything captured that way, with its reason and date — which is the answer to "why is
this set like this" six months later.

Settings that apply to one client go on `--scope account:<id>`, not the profile.
