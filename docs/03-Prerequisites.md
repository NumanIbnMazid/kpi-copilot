# Prerequisites and assistant connections

An assistant needs a runtime that can execute the shared pipeline. A browser login alone
is not an execution environment. No specific AI subscription is required by this project.

## Local setup

Use Python 3.10+ for new installations, including MCP. The CLI is also tested locally on
Python 3.9. From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Ask the assistant to follow [Start here](02-Start-Here.md). Keep the profile and generated
records in a private folder outside this repository. Begin with `review-only` output.

```bash
.venv/bin/python plugin/kpi-copilot/scripts/kpi.py auth --profile /absolute/path/profile.yaml --project my-project
.venv/bin/python plugin/kpi-copilot/scripts/kpi.py doctor --profile /absolute/path/profile.yaml --project my-project
```

`auth` lists the available connection choices, best first for the current machine. Present
those choices to the person. Reuse a supported existing login, such as GitHub's `gh`, when
available. For browser authorization, the person clicks Allow. For tokens, give them the
command to run privately; never request or read a secret in chat.

`preflight.py` provides a broader checklist and records dated confirmations. Readiness is
specific to the selected project and output: review-only needs no PMS write permission.
A saved checklist does not prove a live operation succeeded.

## Optional local MCP connection

For assistants that support local stdio MCP servers, install the optional dependencies in
a Python 3.10+ environment:

```bash
.venv/bin/python -m pip install -r requirements-mcp.txt
```

Add this server through the assistant's MCP settings. Replace all three absolute paths:

```json
{
  "mcpServers": {
    "kpi-copilot": {
      "command": "/absolute/path/to/kpi-copilot/.venv/bin/python",
      "args": ["/absolute/path/to/kpi-copilot/plugin/kpi-copilot/scripts/mcp_server.py"],
      "env": {"KPI_PROFILE": "/absolute/path/to/private/profile.yaml"}
    }
  }
}
```

Host settings formats vary; this is the common JSON shape, not an installer for every
assistant. The server exposes eight tools: projects, readiness, preparation, review,
judgements, person answers, PMS preview and approved submission. It runs the same CLI and
serializes calls within that server. Do not run multiple writers against the same profile.

Start with `projects`, then `readiness`, then `prepare_kpis`. `read_review` returns one batch
of decisions. The submission tool requires the digest of the reviewed payload, and the
assistant must obtain an explicit yes in the current conversation. A matching digest binds
the payload; it is not proof that a person approved it.

The real stdio protocol is tested. Each host still needs an installation acceptance check;
see [the audit](11-Audit.md). This server does not expose a network listener. Browser-only
assistants need a code workspace with approved exports, or a separately deployed authenticated
runtime. A hosted remote service is not included.

## Google and optional sources

Google access is needed only for named Drive sources or a Google Sheets destination.
`kpi.py auth google` explains supported OAuth and service-account setup. An administrator
may need to register an application and enable the Sheets and Drive APIs. OAuth audience
and consent requirements depend on the organization's account and deployment.

Use a dedicated output spreadsheet. Tool-owned tabs are rebuilt; yellow input cells are
read back first and unrelated tabs are preserved. Do not select a valuable manual reference
workbook as the output destination. If Google is unavailable, the run preserves the existing
review baseline and creates a separate local preview. Reconnect before merging or pushing.
Local copies of configured sources can be placed in the project's `inbox` as instructed by
NEXT. Missing or stale required source facts remain visible and prevent PMS submission.

## PMS access

Read the nine KPI definitions and project targets from your deployment. Refresh the registry
beside the private profile; no organization's target cache belongs in the installed plugin.
The bundled registry is a labelled fallback, not confirmation of current project targets.

PMS submission requires an existing period, verified project ownership, supported API access,
and explicit approval of the preview. The current CLI writer uses `PMS_TOKEN` from the
runtime environment. A signed-in browser session is not automatically available to that
writer. Production write acceptance remains separate from read-only definition verification.
Never test write permission by changing production KPIs.

Schedules may prepare drafts. They do not supply the conversation approval needed to push.
Legacy `auto-push` and `unattended` settings never waive that requirement.
