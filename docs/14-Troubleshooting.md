# Troubleshooting installation and runs

[Documentation](README.md) · [Installation](12-Installation.md) · [FAQ](09-FAQ.md)

Tell your assistant which step failed and share the error text after removing private data.
Never include tokens, credentials or a real source export in a public issue.

| What you see | What to do |
|---|---|
| “Python not found,” or a version below 3.10 | Install an approved modern Python and recreate the environment with that executable |
| A package such as `yaml`, `openpyxl`, `jsonschema` or `mcp` is missing | Install the appropriate requirements with the **same Python executable** used by the runner or MCP server |
| `requirements.txt` or `scripts/kpi.py` cannot be found | Check the working folder. Repository commands start beside README.md and use `plugin/kpi-copilot/scripts/...` |
| `git` is unavailable | Install Git or use Code → Download ZIP on the repository page |
| Git/Python reports an Xcode license or developer-tools error on macOS | Ask the machine owner/IT to complete Apple's setup, or use an already approved standalone installation. The assistant must not accept license terms for you |
| Plugin installed, but skills do not appear | Check the marketplace/plugin name, installed scope and enabled status. Reload/restart the client. Do not place the whole plugin under a skills directory |
| MCP tools do not appear | Check absolute paths, JSON/TOML syntax, environment dependencies and client logs; restart the server |
| MCP says `KPI_PROFILE` is missing or the profile cannot be read | Point it to an existing configured profile. MCP does not create one; use the [operator setup](03-Prerequisites.md#operator-reference-create-a-profile-and-run-the-pipeline) |
| “Unknown project” or a choice of projects | Use the project's saved `id`, not its display name. Ask the assistant to list projects |
| Tracker access fails although you are signed in to the AI app | Run `auth`/`doctor` for the selected profile. The runner and AI connector may use different connections |
| Google cannot find a file or denies access | Check the selected account and file sharing. Live output needs edit access; a service account must be granted access explicitly |
| The sheet was not updated but a local preview exists | Follow the publishing warning. Restore the authoritative connection before refreshing/submitting; do not overwrite Google from the preview |
| Source needs digesting, or a digest is stale | The assistant reads the specified local document once and records facts with the printed fingerprint |
| CSV run cannot find the export | Use a valid profile-relative source path or an absolute private path. Check the mapped column names |
| A KPI says Not measured | Read its reason and Open Questions. Add the missing evidence or keep the limitation visible; do not substitute zero |
| Submission is refused | Resolve review/source gaps, reconcile local targets, verify the mode and period ownership, then generate a fresh preview |

## A safe diagnostic request

> Check readiness for [project] using [profile location]. Explain the specific failing
> requirement and supported fixes. Keep the current workbook and review edits intact.
> Do not read extra sources or submit anything to PMS.

## When a result seems wrong

Start with the relevant register row and evidence. Common causes are the wrong delivery
state, an overly broad exclusion, the wrong estimate source, a missing agreed date, or an
incorrect closure boundary for rework. Ask the assistant to explain which inputs produced
the result before changing them.

See [worked configuration decisions](16-Configuration-Field-Guide.md), the
[counting rules](../plugin/kpi-copilot/skills/kpi-run/references/kpi-rules.md), and the
[assistant troubleshooting reference](../plugin/kpi-copilot/skills/kpi-run/references/troubleshooting.md).

## Reporting a tool defect

Describe the generic symptom, expected result, version, Python version and a small fictional
reproduction. Use the sample workspace as a starting point. Keep real profiles, client names,
URLs, tickets, workbooks and screenshots outside the repository and public discussions.
Distinguish a local test result from a successful live-service operation.
