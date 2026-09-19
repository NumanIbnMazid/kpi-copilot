# Jira - Cloud, Server and Data Center

Reads a Jira project through the REST API, changelog included, straight to disk.

```bash
python3 scripts/kpi.py run --profile profile.yaml --project <id>          # uses this reader (api.py)
```

| | |
|---|---|
| First read | a hundred issues per request with their changelog attached; an unusually long history or comment thread costs one more request |
| Every read after | only issues updated since the cached snapshot |
| What it produces | a **board snapshot** (`scripts/board.py`). No judgement |
| What it can see | status history, comments, assignee, original estimate (as hours), story points, labels, issue type, resolution, created and resolved dates, reporter |

Status is the workflow status, and every status change in the changelog is a move on the
board - which is what delivery dates, rework and "had to ask the client" are read from. The
issue type, the resolution, labels, the estimate and story points arrive as fields and tags;
what they *mean* is decided afterwards by the profile's conventions, the same way as for
every tracker. A story under an epic is a deliverable of its own; only a true sub-task hangs
off its parent.

## Profile

```yaml
tracker:
  adapter: jira
  url: https://acme.atlassian.net
  story_point_field: Story Points      # looked up by name; no custom-field id needed
  options:
    jql: 'project = ACME AND fixVersion = "4.2"'     # optional; default is the whole project
projects:
  - id: identity
    tracker_ref: ACME                  # the project key
conventions:
  defect_by: issue-type
  defect_values: [Bug]
  observation_values: [Improvement]
workflow:
  delivered_when: {signal: status-entered, values: [In Test, Done]}
  closed_when:    {values: [Done]}
  reopened_when:  {values: [In Progress, Reopened]}
  clarification_when: {values: [Blocked - Client, Awaiting Feedback]}
```

A resolution such as *Won't Do*, *Duplicate* or *Cannot Reproduce* is read as a rejected
report. Put your own words under `conventions.tags.rejected` if they differ.

## Signing in

`python3 scripts/kpi.py auth` shows what is connected and the best way in for this machine.

1. **An API token** (Cloud: id.atlassian.com > Security > API tokens; Server / Data Center: a
   personal access token) - `python3 scripts/kpi.py auth jira --route token`, typed by you
   in a terminal, or `export JIRA_EMAIL=… JIRA_TOKEN=…` (Server/DC: `JIRA_PAT`). A minute to
   set up, the fastest at run time, and the one for an unattended schedule.
2. **Sign in in your browser** (Cloud) - `python3 scripts/kpi.py auth jira --route browser`;
   click Accept. Needs an Atlassian OAuth app your company registers once
   (`docs/03-Prerequisites.md`).
3. **No credential at all** - in a signed-in Jira tab (yours, or your assistant's built-in
   browser), run `browser_snapshot.js`, then `kpiSnapshot('project = ACME')`. It *downloads*
   `jira-raw.json`; pass it with `kpi.py run … --from-raw ~/Downloads/jira-raw.json`. Slower,
   and somebody has to be there, but it works where tokens are forbidden.

All three end in the same snapshot through the same code, so they cannot disagree.

## The older converter

`extract.py` still turns Jira straight into KIF, judging as it goes, and is kept for anyone
calling it directly. `kpi.py run` uses `api.py`: the judging then happens in
`scripts/classify.py`, tolerantly and the same way as for every other tracker, with the
ledger, the assistant's one-batch queue and the live sheet.
