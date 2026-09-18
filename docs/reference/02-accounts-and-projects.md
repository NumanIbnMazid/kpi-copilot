# Accounts and projects

One profile covers everything you work on. Most of what varies between two projects actually
varies between two **clients**, so say it once per client.

---

## The three levels

```
profile defaults      how you usually work
  └─ account          what is true for every project on this client
       └─ project     what is true for just this one
```

```yaml
accounts:
  - id: northwind
    name: Northwind
    notes: "Asana and Google Chat. Plans are PDFs; change requests come from an estimates sheet."
    overrides:
      tracker: {adapter: asana, key_field: TKT}
      conventions: {key_pattern: 'TKT-\d+', defect_by: title-pattern}
      sources: {evidence_channels: [chat-devqa, chat-mgmt], hours_first: plan}

  - id: acme
    name: Acme
    overrides:
      tracker: {adapter: csv, options: {tracker_name: Jira, file: exports/acme.csv}}
      sources: {evidence_channels: [slack-acme]}
      periods: {model: Sprint}
      output:  {mode: review-only}

projects:
  - {id: q3-release,    account: northwind, pms_project_id: 101, tracker_ref: "1100000000000001"}
  - {id: gateway,       account: northwind, pms_project_id: 102, tracker_ref: "1100000000000002"}
  - id: acme-identity
    account: acme
    pms_project_id: 201
    velocity_unit: Story Points
```

## Merge rules

- **Dicts merge, deeply.** Overriding `workflow.delivered_when.values` leaves
  `workflow.closed_when` untouched.
- **Lists replace.** Another team's exclusion patterns are *theirs*, not yours plus theirs.
  Accumulating them is how one team's regex quietly eats another team's work.
- **`owner` and `organization` never vary.**
- **`tools` is scoped, not overridden** — see [01-tools.md](01-tools.md).

## Account fields

| Field | What it is |
|---|---|
| `id` | Short handle projects point at: `northwind`, `acme` |
| `name` | What people call the client |
| `notes` | What a newcomer to this account should know |
| `overrides` | Any of: `tracker`, `conventions`, `workflow`, `sources`, `periods`, `policy`, `output`, `custom_instructions` |

## Project fields

| Field | What it is |
|---|---|
| `id` | Short handle. Every command takes `--project <id>` |
| `name` | Full name, used in reports |
| `account` | The client it belongs to. Inherits that account's overrides |
| `pms_project_id` | The number in the PMS URL. Required to push |
| `tracker_ref` | Board id or project key, when it differs from the account default |
| `workbook_ref` | This project's tracker workbook, if it has a fixed one |
| `plan_ref`, `estimates_ref` | Shorthand for `sources.plan.ref` / `sources.estimates.ref` |
| `period_model`, `velocity_unit` | Shorthand for the matching `periods` settings |
| `notes` | Anything worth knowing: a freeze date, an unusual arrangement |
| `overrides` | Same sections as an account. Usually empty |

**If the same override appears on several projects, it belongs on their account.** The
Overrides tab of the workbook shows every one on a page, which is how you notice.

## Adding one

**A project on a client you already have** — one row:

```yaml
  - {id: northwind-admin, account: northwind, pms_project_id: 388, tracker_ref: "1216999000000000"}
```

**A new client** — an account block with what differs, tools tagged with it, then the
projects. `/kpi-copilot:kpi-setup` will walk it and read the board for you.

## Checking it

```bash
python3 scripts/profile_lib.py --profile profile.yaml --list
```

```
project        account     adapter  PMS    name
q3-release     northwind     asana    361    Northwind Q3 Release Items
gateway        northwind     asana    382    Northwind Gateway Integration
acme-identity  acme        csv      402    Acme Identity Platform
```

It also prints every override, by scope. To see one project fully resolved:

```bash
python3 scripts/profile_lib.py --profile profile.yaml --project acme-identity --section tracker
```

With several projects, omitting `--project` is an error that lists the ones it knows — a
deliberate choice over guessing which you meant.

## See also

- [01-tools.md](01-tools.md) · [07-output-and-files.md](07-output-and-files.md)
- [../05-Adapting-To-Your-Workflow.md](../05-Adapting-To-Your-Workflow.md) — the narrative version
