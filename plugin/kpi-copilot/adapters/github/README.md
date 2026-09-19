# GitHub Issues and Projects

Reads a repository's issues - and, if the team uses one, a Projects board's status - through
GitHub's GraphQL API, straight to disk.

```bash
python3 scripts/kpi.py run --profile profile.yaml --project <id>          # uses this reader
python3 adapters/github/api.py --repo acme/web --out board.json            # on its own
```

| | |
|---|---|
| First read | one request per fifty issues, with labels, comments and full history attached: 150 issues in about 14 seconds |
| Every read after | a second or two - only issues updated since the cached snapshot are asked for |
| What it produces | a **board snapshot** (`scripts/board.py`). No judgement |
| What it can see | status history, comments, assignees, labels, issue type, created and closed dates, reporter, and a Project's number fields (estimate, story points) |

## What "status" means

- **With a Project** (`tracker.options.project`), status is the project's **Status** field -
  "In progress", "In review", "Done" - and every change of it is a move on the board. That
  history is what delivery dates, rework and "had to ask the client" are read from, so a team
  that works on a Projects board should name it.
- **Without one**, status is **Open**, **Closed**, or **Not planned** (GitHub's "won't fix",
  which the judging rules read as a rejected report).

Pull requests are not issues and are left out.

## Profile

```yaml
tracker:
  adapter: github
  estimate_field: Estimate             # a number field on the Project, if hours live there
  story_point_field: Story Points
  options:
    project: orgs/acme/projects/7      # optional; its Status field becomes the status
    status_field: Status
projects:
  - id: web
    tracker_ref: acme/web              # or several: "acme/web, acme/api"
conventions:
  defect_by: label                     # or issue-type, if you use GitHub's issue types
  defect_values: [bug]
  observation_values: [question, enhancement]
  tags: {pre_existing: [existing, regression-from-before], cr: [change-request]}
workflow:
  delivered_when: {signal: status-entered, values: [In review, Done]}
  closed_when:    {values: [Done, Closed]}
  reopened_when:  {values: [In progress, Open]}
```

Labels do the job title tags do elsewhere, and they are read just as tolerantly: a label
`exisiting` is read as *existing*, and the row says so.

## Signing in

`python3 scripts/kpi.py auth` shows what is connected and the best way in for this machine.

1. **GitHub's own login, `gh`** - if `gh auth status` says you are signed in, nothing more is
   needed. If not, `gh auth login --web` opens your browser; nothing is copied or pasted.
2. **A token** - fine-grained, with *Issues: read* (and *Projects: read* if you name a
   project): `python3 scripts/kpi.py auth github --route token`, typed by you, or
   `export GITHUB_TOKEN=…`. The one to use for an unattended schedule.

GitHub Enterprise Server: set `tracker.options.graphql_url` to `https://<host>/api/graphql`.
An older server without issue types or project status events is read without them, and the
run says so.
