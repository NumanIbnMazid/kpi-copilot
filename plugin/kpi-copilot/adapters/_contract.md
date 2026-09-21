# Adapter contract

An adapter has exactly one job: get one team's issue tracker onto disk. It does not compute
KPIs, write notes, touch spreadsheets or talk to PMS. If you find yourself doing any of that
in an adapter, it belongs somewhere else.

This is what makes the tool portable. Writing support for a new tracker means writing one
file, and every downstream behaviour - the judging, the nine KPIs, the note wording, the
workbook, the dry run, the push - comes for free and behaves identically.

There are two shapes an adapter can produce. **Prefer the first.**

## A reader: tracker -> board snapshot (preferred)

A reader reports what the board says and judges nothing: cards, their fields, their status
moves, their comments (`scripts/board.py` documents the shape; `adapters/asana/api.py` is the
worked example). `scripts/classify.py` then decides what is a defect, what is rework, which
period a card belongs to - by the profile's conventions, tolerantly, the same way for every
tracker - and queues whatever it is unsure of for the assistant, once.

```
board.json
  tracker, project_ref, project_name, url, fetched_at, capabilities[], sections[]
  items[]: id, key, url, title, description, section, completed, created_at, created_by,
           completed_at, modified_at, assignee, tags[], fields{}, parent,
           events[]   {at, kind: section|field|completed|reopened, from, to, by}
           comments[] {at, by, text, url}
           history_at
```

Rules for a reader:

- **Straight to disk.** API to file. A board must never travel through an assistant's
  context; that is what turns a run of seconds into one of half an hour.
- **Cache without losing membership changes.** Reuse unchanged history where reliable,
  but refresh membership or reconcile removals so deleted or out-of-scope records disappear.
  Verify provider semantics before relying on modified timestamps.
- **No judgement, no team-specific names.** A regex for "[Existing]" inside a reader is a
  rule nobody else's project gets, and it will miss "[Exisiting]".
- **Declare capabilities honestly**, follow paging to the end, read-only, plain-English
  errors, and never ask for a credential in a chat - read it from the environment or
  `~/.config/kpi-copilot/`.

The interface is one function in `adapters/<name>/api.py`, and nothing else needs editing -
`kpi.py run` finds a reader by the adapter's name:

```python
def read(project: dict, profile: dict, cache: dict | None, progress=None) -> dict:
    """This project's board as a snapshot. `cache` is the previous snapshot, or None.
    Raise board.ReaderError with a message a person can act on."""

def from_raw(raw: dict, profile: dict, project: dict) -> dict:     # optional
    """The same snapshot from a file downloaded by a signed-in tab (browser_snapshot.js)."""
```

Credentials come from `scripts/connect.py` (`connect.credential("<service>")`), which knows
every way a person can sign in - browser, an existing CLI login, a token, a signed-in tab -
and which to suggest. Add your service's routes there, so `kpi.py auth` and the readiness
check can explain them. `adapters/github/api.py` (paginated GraphQL with nested-page checks) and
`adapters/jira/api.py` are the other two worked examples.

## A converter: tracker -> KIF directly

The legacy Jira converter and current CSV adapter do this: they produce a finished KIF document
(`schemas/kif.schema.json`), making the judgement calls themselves. It remains supported -
a CSV export has no history to judge from anyway - and the rules below are for this shape.

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
