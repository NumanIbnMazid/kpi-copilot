# Adapter contract

An adapter has exactly one job: turn one team's issue tracker into a valid KIF document
(`schemas/kif.schema.json`). It does not compute KPIs, write notes, touch spreadsheets or talk
to PMS. If you find yourself doing any of that in an adapter, it belongs somewhere else.

This is what makes the tool portable. Writing support for a new tracker means writing one
file that produces the same JSON, and every downstream behaviour - the nine KPIs, the note
wording, the workbook, the dry run, the push - comes for free and behaves identically.

## Interface

```
adapters/<name>/
├── extract.py      # required: the adapter itself
├── README.md       # required: what it needs, what it can and cannot see
└── ...             # anything else it needs
```

```bash
python3 adapters/<name>/extract.py \
    --profile profile.yaml \
    --project <project id from the profile> \
    --out runs/<date>/run.kif.json \
    [--since YYYY-MM-DD] [--period "Milestone 2"]
```

Exit 0 on success. Exit non-zero with a plain-English message on stderr when the tracker
cannot be read. Never exit 0 with a partial document and no warning.

## Rules

**1. Declare what you could see.** `generated.capabilities` lists what the adapter actually
observed. The engine turns a missing capability into "Not measured" with a stated reason
rather than a wrong number. Do not claim `status_history` because the API has an endpoint;
claim it because you read it.

| Capability | Without it |
|---|---|
| `status_history` | Delivery Commitment, Rework Rate and Task Comprehension fall back to whatever was filled in by hand |
| `comments` | Rejection reasons and clarification evidence have to come from the person |
| `estimates` | Velocity has only team-level hours |
| `story_points` | Velocity in points is unavailable |
| `issue_type` / `labels` | Defects must be recognised from the title instead |
| `reporter` | A client-found defect cannot be told from a QA-found one |

**2. Never guess.** An unknown value is `null`. `understood: null` means "no history of its
own" and is left out of the denominator; `understood: "Yes"` means you have evidence. The
difference is the whole honesty story of this tool.

**3. Put judgement calls in `review[]`, with a proposal.** Anything you cannot decide goes
there with a suggested answer, so the run can ask one round of questions instead of ten.
An adapter that silently picks is worse than one that asks.

**4. Keep excluded work in the document.** A card that is not a deliverable stays as
`type: "Excluded"` with an `exclude_reason`. It never reaches a denominator, but the
workbook shows it, and "why is my 40-item board showing 12 items" is the first question
anyone asks.

**5. Evidence on every judgement.** Where a Yes/No came from a comment or a status move,
put the link in the matching `*_evidence` field. A judgement with no evidence is flagged in
review.

**6. Read the profile; do not hardcode.** Column names, key patterns, defect conventions and
exclusion patterns all come from `profile.conventions` and `profile.workflow`. An adapter
with a team's column name in it is a bug.

**7. Apply the adapter-side custom rules.** `profile.custom_instructions.rule_overrides`
includes rules the engine hands to you: `delivered_signal`, `client_date_source`,
`commit_date_source`, `hours_source`, `period_of_key`. Apply them and note them in
`generated.warnings` so they appear in the run summary.

**8. Read-only.** An adapter never writes to the tracker. Not a label, not a comment.

## Writing a new one

Start from `adapters/csv/extract.py`. It is the simplest complete example and it already
handles the mapping, the classification and the review list; a native adapter mostly
replaces "read a CSV" with "call an API" and keeps the rest.

`scripts/validate_kif.py` checks your output against the schema and against the softer rules
(a period referenced by a task that does not exist, an Excluded row with no reason, a date
in the wrong format). Run it before you trust anything.

Then run the engine against a period whose answer you already know. Matching a number you
can verify by hand is the only test that means anything here.

The `/kpi-copilot:kpi-adapter` skill walks all of this interactively.

## Ready-made adapters

| Adapter | Reads | Needs | Notes |
|---|---|---|---|
| `csv` | A CSV export from any tracker | Nothing but the file | The day-one answer for any tracker. Column mapping lives in the profile |
| `jira` | Jira Cloud REST API | `JIRA_TOKEN` in the environment | Full history through the changelog |
| `asana` | Asana REST API | `ASANA_TOKEN`, or the in-browser route | The browser route needs no token and uses the signed-in session |

A team on ClickUp, Linear, Azure DevOps, GitHub Issues, Monday or Trello starts with `csv`
on day one and gets a native adapter later if the export ever becomes annoying. That order
matters: nobody should wait on engineering to get their first KPI run.
