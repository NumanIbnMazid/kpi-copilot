# Prerequisites and the readiness check

Nobody should discover halfway through a KPI run that they cannot reach PMS. So the first
thing setup does — and the first thing every run does — is check.

```bash
python3 scripts/preflight.py --profile profile.yaml --markdown readiness.md
```

Or just run `/kpi-copilot:kpi-setup`, which does it for you and walks the parts a script
cannot see.

---

## What gets checked

### Environment — a script can see all of this

| Check | Why it matters | Fix |
|---|---|---|
| Python 3.9+ | The engine, workbook and adapters are Python | `brew install python3` |
| PyYAML | The profile is YAML so a person can read it | `pip3 install pyyaml` |
| openpyxl | Builds the workbooks | `pip3 install openpyxl` |
| Claude Code, with an active subscription | The skills, browser control and approval steps run in it | Install the desktop app and sign in. If the company pays, ask IT for a seat |
| The plugin is loaded | Without it the `/kpi-copilot:*` skills do not exist | `claude plugin marketplace add "/path/to/KPI Copilot"` then `claude plugin install kpi-copilot@pm-tools`, or start with `--plugin-dir` |

### Configuration

| Check | Why it matters |
|---|---|
| A profile exists | It is what makes the run follow your workflow rather than somebody else's |
| Every required section is filled | A half-filled profile produces numbers nobody can defend |
| KPI definitions synced from PMS | Ids, targets and this project's own thresholds come from PMS, not from a copy that quietly went stale |
| The adapter exists | It is what turns your tracker into something the engine can read |

### Access — some of this only you can confirm

| Check | Who can fix it |
|---|---|
| PMS answers from this machine | IT, usually a VPN |
| **Your account can open the project's KPI page** | PMS admin. Reading PMS is not the same as being allowed to see this project |
| **Your account may edit KPIs there** | PMS admin. Only needed if you will push |
| **The periods you will push to exist in PMS** | You. The push updates periods, it does not create them |
| A browser session signed in to the tracker, PMS and your document store | You. Claude reads these pages as you and never types credentials |
| Jira API token, if you use the Jira adapter | You. Keep it in the environment, never in the profile |
| Google Drive / Sheets connector, if you work in Sheets | You, in Claude's connector settings, on the work account |

### Data sources — all optional

Plan, estimates sheet, timeline, evidence channels. Missing any of these is fine. The KPIs
that depend on them come back "Not measured" with the reason, rather than a guess. The check
marks them **limited**, not blocked.

### Output targets

The run folder must be writable, the Drive folder must accept your edits, and `auto-push`
must be paired with `unattended` — otherwise a scheduled run stops and waits for somebody who
is not there.

---

## How to read the result

```
**Almost: 2 items still need your confirmation.**
14 ready, 0 blocked, 2 to confirm, 1 limited.

## Access
- [x] PMS answers from this machine - ready
- [ ] Your account may edit KPIs on that project - needs your confirmation
      Why it matters: Output mode is 'assisted-push', which writes to PMS.
      To fix: Try editing one KPI note by hand in PMS. (owner: PMS admin)
```

| Mark | Meaning |
|---|---|
| `[x]` ready | Nothing to do |
| `[!]` blocked | Must be fixed before this can run |
| `[ ]` confirm | A person has to check it; a script cannot |
| `[~]` limited | Works, but some KPIs will be limited, and it says which |

## Recording a confirmation

Confirmations are remembered with a date, so you are not asked every month — but they expire
after 30 days, because sessions lapse and tokens rotate.

```bash
python3 scripts/preflight.py --profile profile.yaml --confirm pms-account --by "Your Name"
python3 scripts/preflight.py --profile profile.yaml --fail drive-connector --why "not enabled on the work account"
python3 scripts/preflight.py --profile profile.yaml --skip drive-folder
```

The result is written to `preflight.json` next to the profile, and appears on the
**Prerequisites** tab of the KPI Profile Workbook the next time it is built — so your whole
team can see the state of a project's setup without asking you.

## Blocking a run

```bash
python3 scripts/preflight.py --profile profile.yaml --strict
```

Non-zero means something blocking is unresolved. `/kpi-copilot:kpi-run` does this
automatically and stops rather than producing numbers from an environment that is not ready.

## What to sort out before a wider rollout

Two of these are organisational rather than technical, and they take the longest:

1. **PMS project access for each lead**, and edit rights for anyone who will push.
2. **Claude Code seats** for everyone who will use it.

Start both early. Everything else is a `pip install`.
