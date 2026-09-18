# Tracker and conventions

Which adapter reads your board, and how your team names things.

---

## `tracker`

```yaml
tracker:
  adapter: asana                  # asana | jira | csv
  project_ref: "1100000000000001" # board id / project key
  url: https://app.asana.com
  estimate_field: Estimated Time
  story_point_field: Story Points
  key_field: TKT
  options: {}                     # adapter-specific
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

| Adapter | Reads | Needs | Gives you |
|---|---|---|---|
| `asana` | A signed-in Asana tab | No token | Everything, including history |
| `jira` | Jira Cloud REST API | `JIRA_EMAIL` + `JIRA_TOKEN` in the environment | Everything, including history |
| `csv` | An export from **any** tracker | Nothing | Six of nine KPIs; the three needing history say "Not measured" and why |

**Start with `csv` if you are not on Asana or Jira.** It works this afternoon. A native
adapter buys status history and no manual export step, and is worth writing when the export
becomes tiring — not before. `/kpi-copilot:kpi-adapter` writes one.

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
→ `adapters/csv/README.md`

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
- `adapters/_contract.md` — writing an adapter
- [all-fields.md](all-fields.md)
