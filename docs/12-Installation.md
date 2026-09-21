# Install KPI Copilot

[Documentation](README.md) · [First KPI run](02-Start-Here.md) · [Troubleshooting](14-Troubleshooting.md)

This is a one-time setup. Your assistant or IT colleague can do most of it. Afterward,
you prepare KPIs by asking the assistant. Choose **one** route below.

## Before installing

You need an AI tool allowed to execute local programs, or a desktop app that supports local
MCP servers. Install Python **3.10 or later**; Python 3.12 matches a version in the repository's
test configuration. Use the [official Python installer](https://www.python.org/downloads/)
or your organization's approved distribution. The core runner also has historical Python
3.9 test coverage, but the optional MCP dependency requires 3.10+.

A virtual environment is a private set of Python packages for this tool. It avoids changing
packages used by other software. The commands below call that environment directly, so
activation is not required. See [Python's venv documentation](https://docs.python.org/3/library/venv.html).

Install [Git](https://git-scm.com/downloads) if you choose cloning. Git is not needed for a
ZIP download. You need network access to download the tool and its Python packages; the
fictional example can then run offline.

## Route A: local repository folder

Recommended for Codex, Cursor and other assistants with command and file access. It is
also the starting point for the MCP route. Open Terminal on macOS/Linux or PowerShell on
Windows, or ask your assistant to run the commands.

### Get a copy

Run this in the folder where you keep tools or projects:

```bash
git clone https://github.com/NumanIbnMazid/kpi-copilot.git
cd kpi-copilot
```

This creates a `kpi-copilot` folder. The **repository root** means this folder—the one
containing `README.md`, `requirements.txt`, `docs` and `plugin`. You do not need a GitHub
account to clone a public repository. See [GitHub's cloning guide](https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository).

**Without Git:** open the [repository](https://github.com/NumanIbnMazid/kpi-copilot), choose
**Code → Download ZIP**, and extract it. Open the extracted folder, usually `kpi-copilot-main`.
It contains the same source files; updates require a new download. See
[GitHub's archive guide](https://docs.github.com/en/repositories/working-with-files/using-files/downloading-source-code-archives).

### Install the Python packages

Run these from the repository root.

**macOS / Linux:**

```bash
python3 --version
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python plugin/kpi-copilot/scripts/kpi.py --help
```

**Windows PowerShell:**

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe plugin/kpi-copilot/scripts/kpi.py --help
```

Check the reported Python version before creating the environment. If the command starts
an older Python, use the installed 3.10+ executable instead. Windows installations exposing
`py` can use `py -3.12 -m venv .venv` when 3.12 is installed.

The last command should list `run`, `judge`, `answer`, `status`, `doctor`, `push` and `auth`.
That verifies the runner starts; it does not verify your tracker connection yet.

### Open it in your assistant

Open or add the repository folder as a project/workspace in Codex, Cursor or Claude Code.
Allow the assistant to use the Python environment and your chosen private output folder.
Ask it to read `AGENTS.md` and follow [Your first KPI run](02-Start-Here.md).

No separate skill or plugin installation is necessary for this route. The assistant can
read the bundled skill instructions from the repository. For Claude Desktop chat, continue
with [Route C](#route-c-local-mcp-connection) after the example.

## Try the fictional example

Use a new demo destination so you do not overwrite a previous demo's review edits. These
commands copy the fixture outside the checkout and generate a draft with no network access.
Run from the repository root after installing dependencies.

**macOS / Linux:**

```bash
mkdir -p "$HOME/KPI Work"
cp -R samples/workspace "$HOME/KPI Work/demo"
.venv/bin/python plugin/kpi-copilot/scripts/kpi.py run \
  --profile "$HOME/KPI Work/demo/clients/northwind/profile.yaml" --project northwind-q3 \
  --board "$HOME/KPI Work/demo/clients/northwind/northwind-q3/inputs/board.json" --today 2026-09-18 --offline
```

**Windows PowerShell:**

```powershell
New-Item -ItemType Directory -Force "$HOME\KPI Work"
Copy-Item -Recurse samples/workspace "$HOME\KPI Work\demo"
.\.venv\Scripts\python.exe plugin/kpi-copilot/scripts/kpi.py run --profile "$HOME\KPI Work\demo\clients\northwind\profile.yaml" --project northwind-q3 --board "$HOME\KPI Work\demo\clients\northwind\northwind-q3\inputs\board.json" --today 2026-09-18 --offline
```

Open `KPI Work/demo/clients/northwind/northwind-q3/KPI Tracker - Northwind Demo Release.xlsx`, or use the
path printed by the run. Expect a dashboard, registers, KPI Summary and Open Questions.
**NEXT** tells the assistant what needs review. Questions in this fictional draft are
expected; a successful draft is not approval to publish anything.

For a second demo run, reuse the copied files and run only the final command. Do not copy the
fixture over your edited demo. For your real project, have the assistant create a separate
profile following [Start here](02-Start-Here.md#4-ask-the-assistant-to-set-up-your-project).

## Route B: Claude Code plugin

This repository ships a Claude Code marketplace manifest named `pm-tools` and a plugin named
`kpi-copilot`. The installer downloads them, so **you do not need to clone manually**.
It does not install Python, Python packages or account connections.

In a Claude Code session that supports `/plugin`, enter:

```text
/plugin marketplace add NumanIbnMazid/kpi-copilot
/plugin install kpi-copilot@pm-tools
```

Or use these commands in a terminal with the Claude Code CLI installed:

```bash
claude plugin marketplace add NumanIbnMazid/kpi-copilot
claude plugin install kpi-copilot@pm-tools
```

If you already cloned the repository, you can add its absolute folder path instead of the
GitHub name. These are Claude Code instructions, not commands for ordinary Claude Desktop
chat. See the official [plugin installation guide](https://code.claude.com/docs/en/discover-plugins).

### Give the plugin a Python environment

Keep the environment outside the installed plugin cache, which can be replaced on update.
The assistant can create one with these core dependencies, matching `requirements.txt`:

**macOS / Linux:**

```bash
python3 -m venv "$HOME/KPI Work/runtime"
"$HOME/KPI Work/runtime/bin/python" -m pip install 'PyYAML>=6.0,<7' 'openpyxl>=3.1,<4' 'jsonschema>=4.23,<5'
```

**Windows PowerShell:**

```powershell
python -m venv "$HOME\KPI Work\runtime"
& "$HOME\KPI Work\runtime\Scripts\python.exe" -m pip install 'PyYAML>=6.0,<7' 'openpyxl>=3.1,<4' 'jsonschema>=4.23,<5'
```

Then ask:

> Use the installed KPI Copilot plugin. Find its folder containing scripts/kpi.py and use
> the Python environment in my KPI Work/runtime folder. Check that it starts, copy the
> northwind-board example to a new private demo folder, and run the offline example.

The installed plugin includes its own smaller `northwind-board` fixture. The full
[client/project sample pack](../samples/README.md) lives in the repository.

The skills are `/kpi-copilot:kpi-setup`, `/kpi-copilot:kpi-run` and
`/kpi-copilot:kpi-adapter`. Natural-language requests work too when skill discovery is enabled.
If skills are missing, check the installed plugin and restart or reload Claude Code.

Do not copy the whole plugin into a `skills` directory: its root is not an individual skill,
and copying only `SKILL.md` loses the referenced scripts. Other clients may support plugins,
but this repository does not ship their native manifests; use Route A or C for those clients.

## Route C: local MCP connection

MCP lets a compatible assistant call the local runner as tools. Complete Route A, then:

1. Install `requirements-mcp.txt` in the same Python 3.10+ environment.
2. Have a shell-capable assistant or administrator create and validate your real profile,
   including tracker/export settings and agreed workflow rules.
3. Add the server with the absolute Python, script and profile paths in the
   [assistant connection guide](13-Assistant-Connections.md#optional-local-mcp-connection).
4. Check that the assistant can list your projects and run a readiness check.

The MCP bridge operates an existing profile. It does **not** provide profile creation,
account sign-in, arbitrary file editing or PDF digestion tools. Those tasks need separate
local file/command capabilities or help from the person maintaining the setup.

## Updates

For a clone, ask the assistant to check for local edits, then use `git pull --ff-only` from
the repository root and reinstall the applicable requirements. Do not overwrite local
changes to force an update. For a ZIP, extract the new version into a separate folder,
recreate its environment, and update assistant/MCP paths.

For the Claude plugin, use:

```bash
claude plugin marketplace update pm-tools
claude plugin update kpi-copilot@pm-tools
```

Reload or restart the client. A plugin install is a cached copy; editing a clone does not
update it. See [releases](07-Extending.md#releases) for maintainer steps.

Keep profiles and project records outside both the repository and plugin cache. Record the
version used when comparing results across updates. The [audit](11-Audit.md) lists evidence
and acceptance limits; these instructions are not a claim that every host/OS was tested.
