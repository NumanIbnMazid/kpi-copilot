# Tools — where everything lives

[Documentation](../README.md) · [Field guide](../16-Configuration-Field-Guide.md)

One registry for every place your projects' truth is kept: the tracker, the chat spaces, the
plan, the estimates sheet, the folder working files go in, PMS.

This is the tab people actually open. Two reasons it earns its place:

1. **Claude uses it to find things** without being told each time. "Check the chat for a
   handover date" only works if it knows which chat.
2. **It is the fastest explanation of a project that exists.** When somebody picks up the
   account, this table tells them more in two minutes than a handover call does in thirty.

One registry covers all your clients. Entries are **scoped**, so a run on one client never
reaches into another's chat.

---

## A complete entry

```yaml
tools:
  - id: chat-northwind-mgmt
    kind: chat
    name: Northwind-Management (Google Chat)
    url_or_id: AAAAexampleMgmt
    description: >
      Weekly call summaries and client deadlines. Where an agreed date usually appears first.
    used_for: [dates, evidence]
    accounts: [northwind]
    people: [Dana Whitfield, Evan Hollis, Sasha Lindo, Stefan Barrow]
    client_facing: true
    access: Google SSO
    note: "Quiet between releases. A date agreed here beats anything in the plan."
```

## Every field

| Field | Required | What it is |
|---|---|---|
| `id` | yes | Short handle other settings refer to. Lower case, no spaces: `chat-devqa`, `plan-pdf` |
| `kind` | yes | What sort of thing it is — see the table below |
| `name` | yes | What people call it. Include the tool in the name where it helps: "#acme-delivery (Slack)" |
| `url_or_id` | | Link, space id, sheet id or folder id — whatever identifies it |
| `description` | | **One sentence: what this is and why it matters**, written for somebody who has never seen the project. The most valuable field here |
| `used_for` | | Which parts of a run read or write it. Drives which steps reach for it |
| `accounts` | | Client account ids this belongs to. Omit for something shared |
| `projects` | | Project ids, when it belongs to one project rather than a whole client |
| `people` | | Who is in it, as their names appear there |
| `client_facing` | | Is the client in here. Default no |
| `access` | | How to get in: "Google SSO", "Atlassian account". **Never a credential** |
| `note` | | Quirks, when it is quiet, what *not* to trust in it |

### `kind`

| Value | Use for |
|---|---|
| `issue-tracker` | Asana, Jira, ClickUp, Linear, Azure DevOps, a board of any kind |
| `chat` | A Google Chat space, a Slack channel, a Teams channel |
| `email` | A mailbox or a recurring thread |
| `doc-store` | A Drive folder, a SharePoint site |
| `spreadsheet` | An estimates sheet, a timeline sheet, a tracker workbook |
| `document` | A plan PDF, a signed scope document |
| `wiki` | Confluence, Notion |
| `pms` | PMS |
| `time-tracking` | A timesheet system |
| `ci` | A build system, when it is where handovers are announced |
| `other` | Anything else. Say what it is in `description` |

### `used_for`

| Value | Meaning |
|---|---|
| `scope` | What was agreed to be built |
| `estimates` | Effort figures, or approved change requests |
| `dates` | Where agreed dates are set or revised |
| `defects` | Where bugs are reported |
| `evidence` | Searched for the link behind a judgement |
| `handover` | Where a build reaching the client is announced |
| `status` | Current project status |
| `timeline` | Date revisions, change log |
| `output` | Results are written here |
| `approval` | Where sign-off happens |

---

## Chat spaces, in detail

Chat is where most of the evidence lives, so it repays a careful entry.

```yaml
  # Internal delivery chatter
  - id: chat-devqa
    kind: chat
    name: Northwind Dev-QA (Google Chat)
    url_or_id: AAAAexampleDevQA              # the id after /room/ in the URL
    description: "Builds, QA rounds, environment problems. Best source for when something was delivered."
    used_for: [evidence, handover]
    accounts: [northwind]
    client_facing: false
    access: Google SSO
    note: "Internal. Nothing agreed here counts as a client commitment."

  # Client-facing
  - id: slack-acme
    kind: chat
    name: "#acme-delivery (Slack)"
    url_or_id: C07ACMEDEL               # the channel id, not the name
    description: "Where builds are announced and QA rounds discussed."
    used_for: [evidence, handover, dates]
    accounts: [acme]
    people: [Client PM, A. Rahman, S. Ahmed]
    client_facing: true
    access: Slack SSO
```

**`client_facing` is not decoration.** A client-facing space is where agreed dates get set and
where a client-found defect first appears. Marking an internal space as client-facing makes a
team decision look like a client commitment; marking a client space as internal does the
reverse, and the second is worse — it quietly turns an agreed date into one you can move.

**`people` earns its place twice.** It tells a newcomer who to ask, and it is how a run can
tell a client-reported defect from a QA-reported one when the tracker does not record it.

Validation warns when a tool is `client_facing: true` and lists nobody, and when it lists
people who are not in `conventions.client_names` — because a defect they report would then be
counted as found by QA.

### Where to find the id

| Tool | Where |
|---|---|
| Google Chat | The part after `/room/` in the URL: `chat.google.com/room/**AAAAexampleDevQA**` |
| Slack | Channel → View channel details → the ID at the bottom, `C07ACMEDEL` |
| Teams | Channel → Get link, the `threadId` parameter |
| Google Drive / Sheets | The long id in the URL between `/d/` and `/edit` |
| Drive folder | The id after `/folders/` |
| Confluence | The page URL is fine |

---

## Scoping: one registry, several clients

An entry with no `accounts` and no `projects` is **shared** — PMS, your Drive folder, a
company wiki. Everything else is tagged.

```yaml
tools:
  - {id: pms, kind: pms, name: PMS, url_or_id: "https://pms.example.com", used_for: [output]}

  - {id: asana, kind: issue-tracker, name: Asana, accounts: [northwind], used_for: [scope, defects]}
  - {id: jira,  kind: issue-tracker, name: Jira,  accounts: [acme],    used_for: [scope, defects]}

  - {id: sheet-gateway-timeline, kind: spreadsheet, name: Gateway Timeline,
     projects: [gateway], used_for: [dates, timeline]}
```

Resolving a project narrows the registry to what that project can see. Referring to a tool
outside that set fails validation with the reason, rather than searching the wrong place.

Check what a project can see:

Commands below start at the repository root with its Python environment. On Windows,
use `.\.venv\Scripts\python.exe` instead of `.venv/bin/python`. Replace profile paths with
your actual private profile location.

```bash
.venv/bin/python plugin/kpi-copilot/scripts/profile_lib.py --profile profile.yaml --project acme-identity --section tools
```

---

## How a tool gets used

Listing a tool does not by itself make a run read it. Two things connect it:

1. `used_for` says what sort of use it is for.
2. **`sources` names the ones a run should actually read** — the plan, the estimates sheet,
   the timeline, and the evidence channels.

```yaml
sources:
  plan:      {tool_id: plan-pdf,   kind: pdf,   ref: "https://drive.google.com/file/d/1qSIZ/view"}
  estimates: {tool_id: estimates-sheet, kind: sheet, ref: 1ExampleEstimatesSheetId0000000000000000000}
  evidence_channels: [chat-devqa, chat-northwind-mgmt]
```

So the registry is the map; `sources` is the route. A tool can be in the registry purely as
documentation — that is a good reason to list it.

→ [05-sources.md](05-sources.md)

---

## Writing a description worth having

The difference between a registry people use and one they ignore is this field.

Weak:

> Asana board.

Worth having:

> The Northwind boards. Every feature, change request and QA report is a card here, and the
> card history is what proves a delivery date.

Say what it contains, and what it is *authoritative for*. The second half is what stops
somebody looking in the wrong place.

The `note` field is for the thing you would say out loud but would not write in a
description: *"Quiet between releases."* *"The dates in here are aspirational — use the
timeline sheet."* Those are the sentences a newcomer most needs and never gets.

---

## Security

`access` describes **how** to get in — an SSO provider, an account type. It never holds a
credential, a token or a password, and nothing in this tool will ask you for one. Tokens live
in environment variables; see the adapter READMEs.

---

## See also

- [reference/README.md](README.md) — the rest of the configuration
- [02-accounts-and-projects.md](02-accounts-and-projects.md) — the scoping that `accounts` and `projects` hook into
- [05-sources.md](05-sources.md) — turning a registry entry into something a run reads
- [all-fields.md](all-fields.md) — the generated, exhaustive list
