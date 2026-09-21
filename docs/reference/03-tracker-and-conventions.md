# Tracker and conventions

[Documentation](../README.md) · [Field guide](../16-Configuration-Field-Guide.md)

Which adapter reads your board, and how your team names things.

---

## `tracker`

```yaml
tracker:
  adapter: asana                  # asana | jira | github | csv
  project_ref: "1100000000000001" # board id / project key
  url: https://app.asana.com
  estimate_field: Estimated Time
  story_point_field: Story Points
  key_field: TKT
  options: {}                     # adapter-specific; see each reader README
```

| Field | What it is |
|---|---|
| `adapter` | Which adapter turns your tracker into the common format |
| `project_ref` | Asana: the number after `/project/`. Jira: the project key. Usually set per project as `tracker_ref` instead |
| `url` | The tracker's base URL |
| `estimate_field` | The field holding effort hours |
| `story_point_field` | The field holding points. Blank if you measure in hours |
| `key_field` | The field holding the ticket key. Blank uses the tracker's own id |
| `options` | Adapter-specific. See the adapter's README |

### Choosing an adapter

| Adapter | Reads | Signing in | Gives you |
|---|---|---|---|
| `asana` | Board and readable task history, cached where supported | token, browser authorization, signed-in export or integrated host transport | Available fields/events; missing evidence remains visible |
| `jira` | Jira Cloud, Server or Data Center through the REST API, changelog included | an API token, a browser sign-in (Cloud), or a signed-in tab | Available fields and paginated history; account permissions still apply |
| `github` | A repository's issues - and a Projects board's Status, if you name one - through GraphQL | GitHub's own `gh` login, or a token | Available fields and paginated history; account permissions still apply |
| `csv` | An export from **any** tracker | Nothing | Results depend on exported fields; unsupported measures say Not measured |

`.venv/bin/python plugin/kpi-copilot/scripts/kpi.py auth` lists the ways to sign in for your profile and machine, best
first, with what each costs to set up and how fast it is. A token never passes through the
assistant, whichever you choose.

**Start with `csv` if you are on anything else.** It works this afternoon. A reader of your
own buys status history and no manual export step, and is one small file that fetches a board
and judges nothing - `/kpi-copilot:kpi-adapter` writes one, and the judging, the ledger, the
sheet and the sign-in help all come free.

### Tracker options

| Adapter | `tracker.options` |
|---|---|
| `asana` | `include_subtasks` (count subtasks as rows), `token_env` (another variable name for the token) |
| `jira` | `jql` (read this query instead of the whole project) |
| `github` | `project` (a Projects board, e.g. `orgs/acme/projects/7`: its Status field becomes the status), `status_field`, `graphql_url` (GitHub Enterprise Server), `max_items` |

A project names its board with `tracker_ref`: the long number in an Asana board's URL, a Jira
project key, or `owner/repository` on GitHub (several, comma-separated, are fine).

### CSV options

```yaml
tracker:
  adapter: csv
  options:
    file: exports/board.csv
    tracker_name: ClickUp          # for the record
    columns:                       # only what could not be guessed
      period: Sprint
      delivered: "Ready for QA date"
```

Column names are guessed from the header row, so `columns` is usually empty or nearly so.
→ [CSV adapter](../../plugin/kpi-copilot/adapters/csv/README.md)

---

## `conventions`

How your team names things. The setup interview proposes these by reading your board; you
correct what it got wrong.

```yaml
conventions:
  key_pattern: 'TKT-\d+'
  defect_by: title-pattern
  defect_pattern: '^(Bug|Observation|Improvement) ?\d+'
  defect_values: [Bug]
  observation_values: [Observation, Improvement]
  exclude_patterns:
    - '^Milestone\b'
    - '^QA Checklist'
    - '^\[Duplicate\]'
  cr_marker: '\[CR\]'
  client_names: [Dana Whitfield, Stefan Barrow]
```

| Field | What it is |
|---|---|
| `key_pattern` | Regex matching a ticket key. Blank uses the tracker id |
| `defect_by` | How defects are marked: `title-pattern`, `issue-type`, `label`, `separate-board`, `field` |
| `defect_pattern` | Regex on the title, when marked by title |
| `defect_values` | Values meaning "defect" — `[Bug]`, `[Bug, Defect]` |
| `observation_values` | Reported, but not counted as defects by default |
| `exclude_patterns` | Titles that are **not deliverables**: grouping cards, milestone markers, QA admin, duplicates |
| `cr_marker` | How an approved addition is marked. Blank if CRs come from the estimates sheet |
| `client_names` | Client-side people, exactly as the tracker spells them. Tells a client-found defect from a QA-found one |

### Exclusion patterns: the one to be careful with

The most common cause of "why is my item count lower than my board" — and of a silently wrong
denominator.

```yaml
exclude_patterns:
  - '^Bug'           # BAD: also removes "Bugfix: client login"
  - '^Bug Reporting$' # good: anchored both ends
```

Anchor them. `^...$` where you can. Then check the Task Register — every excluded row is
listed with its reason.

### Defects marked four different ways

```yaml
# By issue type (Jira, most trackers)
conventions: {defect_by: issue-type, defect_values: [Bug]}

# By title pattern (boards without types)
conventions: {defect_by: title-pattern, defect_pattern: '^(Bug|Observation) ?\d+'}

# By label
conventions: {defect_by: label, defect_values: [bug, defect]}

# On a separate QA board
conventions: {defect_by: separate-board}   # plus the board in tracker.options
```

### Regexes

Python syntax, case-insensitive where it makes sense. In YAML, wrap them in single quotes so
backslashes survive: `'TKT-\d+'`, not `"TKT-\d+"`.

`profile_tool.py validate` compiles every one and tells you which fails, with the error.

## See also

- [04-workflow.md](04-workflow.md) — what your states mean, which matters more than naming
- [Adapter contract](../../plugin/kpi-copilot/adapters/_contract.md) — writing an adapter
- [all-fields.md](all-fields.md)

## Scoped and grouped work

`conventions.assignee_include` restricts a mixed board to explicitly named assignees,
case-insensitively. Excluded and unassigned rows stay visible.

For delivery tickets grouped under one estimate, see
[grouped delivery settings](../05-Adapting-To-Your-Workflow.md#grouped-delivery-tickets-and-client-vocabulary).
Count the members and hold the shared estimate once; do not duplicate parent effort.

Some accepted defect signals and source options require adapter-specific support.
Read the implementation notes before relying on `separate-board` or arbitrary field signals.
