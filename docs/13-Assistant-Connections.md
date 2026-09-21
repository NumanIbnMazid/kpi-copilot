# Connect your assistant

[Documentation](README.md) · [Installation](12-Installation.md) · [First run](02-Start-Here.md)

Use the simplest route your assistant supports. Opening the repository in a local coding
assistant is enough; MCP is useful when you want a desktop chat to call the runner directly.

## Local folder: Codex, Cursor or Claude Code

Complete [installation](12-Installation.md#route-a-local-repository-folder), open the
repository as the assistant's project, and send:

> Read AGENTS.md and use this repository's Python environment to set up KPI Copilot.
> Keep my profile and results in [private folder]. Follow docs/02-Start-Here.md and begin
> with review-only output.

Check that the assistant can read the folder and execute `kpi.py --help`. Repository access,
tracker access and Google/PMS access are separate permissions. An installed Jira or Google
connector does not automatically supply credentials to the Python runner.

## Optional local MCP connection

MCP is a connection protocol between an assistant and tools. KPI Copilot's server runs on
your computer through **stdio**: the assistant starts a local process and talks to it. There
is no public URL to paste into a remote-connector form.

### Prepare the runner and profile first

From the repository root:

```bash
.venv/bin/python -m pip install -r requirements-mcp.txt
```

On Windows use `.\.venv\Scripts\python.exe` in place of `.venv/bin/python`.

The profile must already exist and be configured. Follow the
[operator setup steps](03-Prerequisites.md#operator-reference-create-a-profile-and-run-the-pipeline)
with a shell-capable assistant or administrator. The eight MCP tools do not create profiles,
launch sign-in, digest PDFs or give the assistant general filesystem access. An MCP-only
session needs help outside those tools when one of those tasks is required.

Have three **absolute paths** ready: the environment's Python executable, `mcp_server.py`,
and your private `profile.yaml`. Absolute means the full path beginning at the drive or
filesystem root, not `./...` or `~`.

### Claude Desktop

Open **Settings → Developer → Edit Config** in versions that expose local MCP configuration.
Merge the entry below into `claude_desktop_config.json`; keep any existing servers. On macOS
that file is under `~/Library/Application Support/Claude/`; on Windows it is under
`%APPDATA%\Claude\`. Restart the app after saving. The MCP project's official
[local-server guide](https://modelcontextprotocol.io/docs/develop/connect-local-servers)
describes the configuration and log locations.

```json
{
  "mcpServers": {
    "kpi-copilot": {
      "command": "/absolute/path/to/kpi-copilot/.venv/bin/python",
      "args": ["/absolute/path/to/kpi-copilot/plugin/kpi-copilot/scripts/mcp_server.py"],
      "env": {"KPI_PROFILE": "/absolute/path/to/KPI Work/profile.yaml"}
    }
  }
}
```

Replace all three paths. For Windows JSON, use escaped backslashes, for example
`C:\\Tools\\kpi-copilot\\.venv\\Scripts\\python.exe`. The script and profile paths must
also point to their actual Windows locations. Do not put tokens in this example configuration.

### Cursor

Use the same `mcpServers` JSON shape in your user-level `~/.cursor/mcp.json`, merging with
existing entries. Cursor also supports project-level `.cursor/mcp.json`; keep private
profile paths out of a shared repository. Check the server's enabled status in the client's
MCP settings. See [Cursor's MCP documentation](https://cursor.com/docs/mcp).

Cursor supports its own plugin formats, but this repository contains a Claude plugin
manifest. The local-folder or MCP route avoids assuming that a Claude plugin install is
portable to another client's marketplace.

### Codex

For a local configuration, merge this into `~/.codex/config.toml`:

```toml
[mcp_servers.kpi-copilot]
command = "/absolute/path/to/kpi-copilot/.venv/bin/python"
args = ["/absolute/path/to/kpi-copilot/plugin/kpi-copilot/scripts/mcp_server.py"]

[mcp_servers.kpi-copilot.env]
KPI_PROFILE = "/absolute/path/to/KPI Work/profile.yaml"
```

Use your real paths; TOML literal strings in single quotes can hold Windows paths without
backslash escaping. Alternatively, use the client's MCP server settings where available,
or `codex mcp add` with the same command and environment variable. See
[official OpenAI MCP documentation](https://developers.openai.com/codex/mcp) for the current
client-specific controls and configuration syntax. Restart the relevant client/server after
configuration changes.

### Verify the connection

Ask the assistant:

> Use KPI Copilot to list the projects in my configured profile, then check readiness for
> [project ID]. Explain any missing connections before preparing results.

Expected tools:

| Tool | Purpose |
|---|---|
| `projects` | List the saved project IDs |
| `readiness` | Check the selected project's connections |
| `prepare_kpis` | Read configured sources and update the workbook |
| `read_review` | Read the unresolved review queue |
| `submit_judgements` | Save the assistant's batch decisions and recompute |
| `record_person_answer` | Record an answer you supplied |
| `preview_pms` | Prepare the exact submission preview and its digest |
| `send_approved_kpis` | Send that preview only after your explicit approval |

A digest identifies the preview; it is not human approval. The bridge serializes operations
within one server. Do not run another writer against the same profile at the same time.
If tools are missing, use [connection troubleshooting](14-Troubleshooting.md).

## Browser-only assistants

A browser chat cannot start this local stdio server. If the session has a compatible Python
workspace, approved source code and exports can be uploaded and used offline, subject to
that environment's package/network limits. Otherwise use a local assistant. A hosted,
authenticated KPI Copilot service is not included in this repository.

## Existing host connections

An advanced integration can use a host's authorized browser or Google connector through
the shipped [file-backed transport](15-Review-and-connected-delivery.md#connected-host-transport).
It requires explicit host integration and an active session; installing the skill or MCP
bridge does not enable it automatically.

Host behavior was researched on 21 September 2026 using the official pages linked above.
Protocol tests and successful installation in a particular app are separate evidence; see
[the audit](11-Audit.md).
