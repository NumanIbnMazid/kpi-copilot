# jira adapter

Reads a Jira Cloud project through the REST API, including each issue's changelog.

## What it needs

An Atlassian API token, in the environment - never in the profile, never pasted into a chat:

```bash
export JIRA_EMAIL="you@example.com"
export JIRA_TOKEN="..."   # id.atlassian.com/manage-profile/security/api-tokens
```

```yaml
tracker:
  adapter: jira
  url: https://example.atlassian.net
  project_ref: ACME
  story_point_field: customfield_10016
  options:
    sprint_field: customfield_10020
```

Find the custom field ids at `/rest/api/3/field` on your site; they differ per site.

## What it can see

Everything the contract lists, including `status_history` - which is what makes Delivery
Commitment, Rework Rate and Task Comprehension real numbers rather than gaps.

- **Delivered** - the first transition into any state in `workflow.delivered_when.values`.
- **Reopened** - a transition *out of* a closed state after the issue had been closed. A
  move into a failure state before it was ever closed is first-round testing and is recorded
  as evidence, not counted.
- **Had to ask** - a transition into a state in `workflow.clarification_when.values` after
  the issue was created, unless the comments point at a build, environment or access
  dependency.
- **Periods** - the last sprint on the issue, or the last fix version, or "Full Project".

## What it leaves blank on purpose

Client and commitment dates. Those are an agreement, not a Jira field. The run settles them
from the plan and the evidence channels.

## Quirks worth knowing

- `timeoriginalestimate` comes back in **seconds**. Converted to hours here.
- Search pages at 100; the adapter follows it to the end.
- `expand=changelog` returns the history with the issue, so one pass gets both.
- A 400 usually means the JQL is wrong, not that the adapter is broken.

## Narrowing a run

```bash
python3 extract.py --profile profile.yaml --project acme-identity \
  --jql "project = ACME AND sprint = 14" --out run.kif.json
```
