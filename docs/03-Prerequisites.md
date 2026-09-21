# Prerequisites and account access

[Documentation](README.md) · [First run](02-Start-Here.md) · [Installation](12-Installation.md)

A local review workbook needs fewer connections than live Google output or PMS submission.
Start with the column that matches your intended use.

## Checklist

| Requirement | Local review | Additional requirement for connected use |
|---|---|---|
| AI assistant | Permission to run local commands, or a configured local MCP connection | Your organization must allow the selected client and integrations |
| Python and packages | Install once using the [installation guide](12-Installation.md) | Python 3.10+ and `requirements-mcp.txt` for MCP |
| Tracker data | Read access to Asana, Jira or GitHub, or a CSV export | A supported connection available to the runner, not just a browser login |
| Project settings | Project ID/name, period, estimate unit and agreed workflow mapping | PMS project and period IDs when submitting |
| Private storage | A writable folder outside the repository/plugin | The runner must also be able to read any selected local sources |
| Spreadsheet viewer | Excel or another compatible viewer to inspect the `.xlsx`; not needed to generate it | Google edit access for a live Google Sheet |
| Plan, estimates, timeline | Optional; identify specific files if used | Google access for Drive files, or local exports |
| PMS | Not required to generate a local workbook | Deployment access, verified targets and a supported write route for submission |

The tool includes a fallback KPI definition registry. Its targets are labelled as defaults;
they are not proof of your project's current PMS targets. Missing evidence remains visible
as Not measured or an Open Question.

## Which tracker route fits?

| Tracker | Supported input | Important limitation |
|---|---|---|
| Asana | API, shipped signed-in-tab export, or integrated host transport | Readable history and configured fields determine what can be measured |
| Jira Cloud | API token, registered OAuth app, or shipped signed-in-tab export | Permissions and changelog availability matter |
| Jira Server/Data Center | Supported API token/PAT or signed-in-tab export | Server versions and available fields differ |
| GitHub Issues / Projects | Existing `gh` login or a token | Name the Project if its status/estimate fields are needed |
| Other trackers | CSV export | A snapshot may lack delivery history, clarification or reopen evidence; no fixed number of measurable KPIs is guaranteed |

See the [adapter reference](reference/03-tracker-and-conventions.md) for field mappings.
The fictional [sample workspace](../samples/README.md) shows both a board-based project and
a CSV project without connecting a real service.

## Offer sign-in choices

After a starter profile identifies the project, the assistant runs `auth` with that profile
and project. It lists the supported routes and recommends one for the current machine.
Present those choices before initiating a new sign-in.

- **Existing login:** for example, GitHub's `gh` login may already be usable.
- **Browser authorization:** available for supported services after any required application
  registration. The assistant starts the flow; you sign in and accept consent yourself.
- **Token:** you enter it privately using the printed terminal command. The assistant never
  asks for it in chat, reads it back, or places it in a profile.
- **Signed-in-tab export:** Asana and Jira can use their shipped export scripts when the
  assistant has a supported browser connection. The download needs your authorization.

For a schedule, ask `auth --unattended` which routes work without an active person or host
session. Preparing a scheduled draft never authorizes a PMS submission.

## Google and optional sources

Google is needed only for named Drive sources or Google Sheets output. Ask the assistant to
show `kpi.py auth google` options. Browser OAuth may need an administrator to register an
application and enable the Drive and Sheets APIs. A service account is another supported
route; its access must be granted to the selected files/folder.

Use a **dedicated output spreadsheet**. Tool-owned tabs are rebuilt after yellow-cell edits
are read back; unrelated tabs are preserved. Do not choose the manual reference workbook as
the output. If the authoritative Google sheet cannot be read, stop or use the separate local
preview indicated by the runner. Reconnect and reconcile before publishing or pushing; do
not replace the spreadsheet manually to bypass a failed read.

Local exports of configured sources can go in the project's `inbox` when NEXT requests them.
Tables need column mappings. A plan PDF needs one assistant digest per changed document;
see the [source reference](reference/05-sources.md).

## PMS access

PMS is optional for review-only work. Before submission, verify the deployment's KPI
definitions, targets and project/period ownership. Refresh the registry beside the private
profile with the supported registry tool; it is not automatically refreshed by every run.
A missing default cache uses the bundled fallback; an explicitly configured missing custom
registry is an error.

The CLI writer supports `PMS_TOKEN` in the runtime environment and the configured host
transport. A browser login alone does not connect it. Existing periods can be updated;
creating missing periods additionally requires explicit authorization and the CLI's
`--create-periods` option. The MCP submission tool does not expose that creation option.

Every write requires approval of the current preview and is read back. Do not test access by
changing production KPIs. The [audit](11-Audit.md) separates implemented safeguards from
live-service acceptance.

## Optional local MCP connection

The full instructions now live in [Connect your assistant](13-Assistant-Connections.md#optional-local-mcp-connection),
including the different Claude Desktop, Cursor and Codex configuration formats. MCP uses
an existing profile; it is not a setup wizard or a hosted service.

## Operator reference: create a profile and run the pipeline

For the assistant or administrator. Commands below start in the repository root; on Windows
replace `.venv/bin/python` with `.\.venv\Scripts\python.exe`. Replace the private path and
project ID. A starter template is incomplete until the workflow conversation fills it in.

```bash
.venv/bin/python plugin/kpi-copilot/scripts/profile_tool.py init --out "/absolute/path/to/KPI Work/profile.yaml"
```

Configure the tracker/export, project, states, period facts and approved sources. Then:

```bash
.venv/bin/python plugin/kpi-copilot/scripts/profile_tool.py validate --profile "/absolute/path/to/KPI Work/profile.yaml"
.venv/bin/python plugin/kpi-copilot/scripts/kpi.py auth --profile "/absolute/path/to/KPI Work/profile.yaml" --project my-project
.venv/bin/python plugin/kpi-copilot/scripts/kpi.py doctor --profile "/absolute/path/to/KPI Work/profile.yaml" --project my-project
.venv/bin/python plugin/kpi-copilot/scripts/where.py --profile "/absolute/path/to/KPI Work/profile.yaml" --project my-project
.venv/bin/python plugin/kpi-copilot/scripts/kpi.py run --profile "/absolute/path/to/KPI Work/profile.yaml" --project my-project
```

`doctor` checks current connections; `preflight.py` provides a broader checklist with dated
manual confirmations. Neither a saved checklist nor a successful login proves delivery.

Follow **NEXT**. If there is assistant work, read the one `judge/queue.json`, write its
specified `answers.json`, and run `kpi.py judge` with the same profile and project. It uses
the existing snapshot. Ask remaining person questions together and record them with `answer`.
Do not collect cards or build workbooks manually.

The [field guide](16-Configuration-Field-Guide.md) explains common settings and provides
worked decisions. [All fields](reference/all-fields.md) is generated from the schema.
