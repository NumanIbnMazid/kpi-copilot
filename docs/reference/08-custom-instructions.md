# Custom instructions

[Documentation](../README.md) · [Field guide](../16-Configuration-Field-Guide.md)

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

For recorded project exceptions. The engine directly applies `cr_denominator`,
`exclude_key`, `include_key`, `defect_phase` and `velocity_team_hours`. Other accepted names
can describe guidance rather than alter the current pipeline; use concrete workflow/source
fields and verify the applied/unapplied report. Do not assume free text executes a rule.

| Rule | Value looks like |
|---|---|
| `delivered_signal` | `In Review` |
| `client_date_source` | `the Confluence plan` |
| `commit_date_source` | `the sprint commitment` |
| `cr_denominator` | `period` or `project` |
| `exclude_key` | `NW-233` |
| `include_key` | `TKT-3401 = CR` |
| `defect_phase` | `Bug 41 = Post-release` |
| `hours_source` | `plan` |
| `period_of_key` | `TKT-3653 = Additional Requests 1` |
| `velocity_team_hours` | `Initial Scope = 135` |

`why` is **required** — it appears in the run summary, so write it for somebody who was not
in the room. `expires` makes a run warn when an override has gone stale.

An unsupported rule is reported, not silently dropped.

## What does not go here

**Targets do not belong inside rule_overrides.** Use official PMS project targets via a
registry refresh, or `targets.<kpi>.value` and `why` for a labelled local review target.
Local targets block PMS submission until reconciled.

**Counting rules.** What delivered, defect and rework mean is shared by everyone. Changing
one is a conversation, because it moves every project's numbers at once.

## Letting it learn

Most of this never gets typed. Say it in chat — *"always show me the previous period"*,
*"save the sheets in this folder"*, *"never push on a Friday"* — and the assistant can
write it down:

Commands below start at the repository root with its Python environment. On Windows,
use `.\.venv\Scripts\python.exe` instead of `.venv/bin/python`. Replace profile paths with
your actual private profile location.

```bash
.venv/bin/python plugin/kpi-copilot/scripts/remember.py --profile profile.yaml \
  --add custom_instructions.always="Show the previous period" --why "asked in chat"
```

A requested lasting change authorizes saving that change; otherwise the assistant offers
to save it. `--why` records the reason, and invalid changes are rolled back.

```bash
.venv/bin/python plugin/kpi-copilot/scripts/remember.py --profile profile.yaml --history
```

shows everything captured that way, with its reason and date — which is the answer to "why is
this set like this" six months later.

Settings that apply to one client go on `--scope account:<id>`, not the profile.
