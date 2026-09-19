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
| An assistant that can run commands | Claude Code, Cursor, Codex - anything that reads `AGENTS.md`, runs a command and reads a file. The `/kpi-copilot:*` skills are a convenience on Claude, not a requirement | Whatever your company provides |
| The plugin is loaded (Claude only) | Without it the `/kpi-copilot:*` skills do not exist; everything else still works through `AGENTS.md` | `claude plugin marketplace add "/path/to/KPI Copilot"` then `claude plugin install kpi-copilot@pm-tools`, or start with `--plugin-dir` |

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
| **Your tracker is connected** (Asana, Jira, GitHub) | You, and you choose how: a login the machine already has (GitHub's `gh`), a browser sign-in (click Allow), a token you type in a terminal, or - with no credential at all - a tab you are already signed in to. `python3 scripts/kpi.py auth` lists them for your machine, best first. A token never goes through a chat |
| A browser session signed in to PMS | You, and only if you will push. The assistant never types credentials |
| Google connected, if sources live in Drive or you want the sheet in Google Sheets | You, once: `python3 scripts/kpi.py auth google`. It needs an OAuth client file - see below. **Not blocking**: without it the sheet is written locally and sources are taken from `<project>/inbox/` |

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

## Browser sign-in for Asana and Jira - what the company sets up once

A token works today with no setup beyond the person's own minute. If your leads would rather
click **Allow** in a browser, register one small app per service, once for everybody:

| Service | Where | What to set | Save as |
|---|---|---|---|
| Asana | app.asana.com/0/my-apps > Create new app | Redirect URL `http://localhost:8765/callback` | `~/.config/kpi-copilot/asana_client.json` - `{"client_id": "…", "client_secret": "…"}` |
| Jira Cloud | developer.atlassian.com > Console > Create > OAuth 2.0 integration | Jira API with `read:jira-work` and `read:jira-user`; callback URL `http://localhost:8765/callback` | `~/.config/kpi-copilot/atlassian_client.json` - same shape |

Hand the file to each lead. They run `python3 scripts/kpi.py auth asana --route browser` (or
`jira`), click Allow, and the sign-in is remembered and refreshed by itself. Both apps are
read-only as used here. GitHub needs none of this: its own `gh` login is already a browser
sign-in.

## Connecting Google - what the company sets up once

Sources in Drive are fetched straight to disk, and the KPI sheet is updated in place, through
Google's own API. An assistant's Drive connector cannot do this: it can only pass file
contents through the conversation, which is slow, and it cannot update an existing file at
all.

Somebody with access to Google Cloud does this **once for the whole company** (ten minutes):

1. Create a project in Google Cloud console; enable the **Google Sheets API** and the
   **Google Drive API**.
2. OAuth consent screen: user type **Internal**. (Internal apps need no Google review.)
3. Credentials > Create credentials > OAuth client ID > **Desktop app**. Download the JSON.
4. Hand that file to each lead. They save it as `~/.config/kpi-copilot/google_client.json`
   and run `python3 scripts/kpi.py auth google` once. A desktop client's "secret" is not a
   secret in the usual sense; what matters is the refresh token, which never leaves the
   lead's machine.

Each lead then reads and writes **as themselves**, with exactly their own Drive permissions.

For a scheduled, unattended run, use a **service account** instead: create one in the same
project, save its key as `~/.config/kpi-copilot/google_service_account.json` on that machine,
and share the Drive folder with the account's address.

Until any of that exists, nothing is blocked: drop an export of each source into
`<project>/inbox/` (`plan.pdf`, `estimates.xlsx`, `timeline.xlsx`) and import the local
workbook over the Google Sheet by hand (File > Import > Replace spreadsheet).

## What to sort out before a wider rollout

Two of these are organisational rather than technical, and they take the longest:

1. **PMS project access for each lead**, and edit rights for anyone who will push.
2. **Claude Code seats** for everyone who will use it.

Start both early. Everything else is a `pip install`.
