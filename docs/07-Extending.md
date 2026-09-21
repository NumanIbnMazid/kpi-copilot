# Contributing and releases

[Documentation](README.md) · [Architecture](06-Architecture.md) · [Design principles](00-Philosophy.md)

Read [AGENTS.md](../AGENTS.md) and the design principles before changing behavior. Keep
source acquisition, judgement, calculations and output separate. Real project data belongs
outside the repository, including in examples, screenshots, logs, commit messages and issues.
Use the configured Git author and do not add assistant attribution or co-author trailers.

Commands below run from the repository root with its Python environment. On Windows use
`.\.venv\Scripts\python.exe` in place of `.venv/bin/python`.

## Adding a tracker

First determine whether CSV is enough. It provides a useful offline route; the measurable
KPIs depend on the export's evidence, not a fixed count. A native reader is justified when
required history is missing or repeated exports are burdensome.

Implement a reader using the [adapter contract](../plugin/kpi-copilot/adapters/_contract.md).
The current [Asana](../plugin/kpi-copilot/adapters/asana/api.py),
[Jira](../plugin/kpi-copilot/adapters/jira/api.py) and
[GitHub](../plugin/kpi-copilot/adapters/github/api.py) readers are working references.

A reader fetches records, fields, comments and available history to a board snapshot. It
must not decide what counts as a defect or write KPI notes. Declare only the capabilities
actually observed, follow all pagination and reconcile removed/moved records. Cache only
where the source supports it without hiding changed evidence. Add supported authentication
choices to `connect.py`; never carry secrets through chat.

The older CSV converter emits KIF, the common KPI input format, directly. That path remains
supported. Document field/unit mappings, missing capabilities and available sign-in routes.
Use small synthetic fixtures to test missing history, pagination, incomplete exports,
changed membership and date/estimate conversion. Then validate against an authorized known
period privately, keeping public reports generic.

## Changing rules

Shared calculation changes affect every project. Agree on the intended meaning first, then
update the engine, the [KPI rules reference](../plugin/kpi-copilot/skills/kpi-run/references/kpi-rules.md)
and meaningful regression coverage together. Preserve visible units, denominators,
exclusions and missing evidence. A local workflow mapping is usually a profile change.

## Editing skills

Skills live under `plugin/kpi-copilot/skills/<name>/SKILL.md`. The three entry points are
`kpi-setup`, `kpi-run` and `kpi-adapter`. Keep the main instructions short and load detailed
references only when needed. Test discovery with realistic setup, run and explanation prompts.

The portable [Agent Skills specification](https://agentskills.io/specification) defines
names, descriptions and resource layout. Client-specific frontmatter, tools, invocation
names and reload behavior depend on the host; consult the current
[Claude Code skill documentation](https://code.claude.com/docs/en/skills) before using them.
A skill supplies instructions, not a Python runtime or account permissions.

For local Claude Code development:

```bash
claude --plugin-dir ./plugin/kpi-copilot
```

Use the client's supported reload/restart behavior after edits. This loads the source folder;
installed marketplace plugins use a separate cached copy. Do not assume a cache path is the
same across clients.

## Validation

```bash
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python plugin/kpi-copilot/scripts/selftest.py
```

The required suite includes formula evaluation and audit regressions. A missing formula
library fails validation. When checking MCP, use Python 3.10+:

```bash
.venv/bin/python -m pip install -r requirements-mcp.txt
.venv/bin/python plugin/kpi-copilot/tests/verify_mcp.py
```

This checks a real local stdio session with fictional data. It does not establish live
provider access or installation in every host. Report local, CI and live evidence separately.

## Documentation and samples

Use [docs/README.md](README.md) as the reading map. Keep one initial guide, link technical
details, define jargon before using it, and distinguish implemented behavior from goals.
Retain existing filenames/anchors where feasible. Run runnable examples from their stated
folder and check relative links and heading anchors.

Field descriptions are owned by the profile schema. Update its descriptions and workbook
hints, then regenerate the field reference:

```bash
.venv/bin/python plugin/kpi-copilot/scripts/gen_reference.py --out docs/reference/all-fields.md
```

Rebuild the [fictional workbook pack](../samples/README.md) through the shipped writers:

```bash
.venv/bin/python samples/build_samples.py --out samples/workbooks
```

The builder uses a temporary copy, explicit fixtures and offline mode. Review workbooks,
metadata and URLs before publishing. Only the four named synthetic workbook files are
allowlisted in Git; generated files elsewhere remain ignored. Do not run real profiles or
place private exports in the sample workspace.

## Packaging

The repository root has `.claude-plugin/marketplace.json`, named `pm-tools`. It points to
`plugin/kpi-copilot`, whose manifest is `.claude-plugin/plugin.json`. The plugin contains its
skills, scripts, adapters, schemas and examples. The full documentation and dependency files
live at the repository root and are not automatically part of the installed plugin copy.
The plugin README therefore links to the canonical online documentation.

Only the Claude Code manifest is shipped here. Other assistants use the repository or the
optional MCP bridge unless a separately maintained package is available. See the
[official Claude plugin guide](https://code.claude.com/docs/en/discover-plugins).

## Releases

Keep the plugin and marketplace versions in agreement. From the repository root:

```bash
.venv/bin/python plugin/kpi-copilot/scripts/release.py --check
.venv/bin/python plugin/kpi-copilot/scripts/release.py --patch
```

The release helper runs the required self-test before bumping both versions. Inspect the
exact diff and messages for private data before staging or publishing. Do not bump solely
for local experimentation.

Users update the marketplace and installed plugin:

```bash
claude plugin marketplace update pm-tools
claude plugin update kpi-copilot@pm-tools
```

Then reload/restart the client. For a marketplace registered from a local clone, update that
clone first. Direct repository users update the source and dependencies; MCP users keep
absolute paths aligned with that installation. Profiles remain outside the install folder.

Explain calculation changes in release notes and ask users to refresh/review affected
results. Record validation limits rather than claiming that local tests certify production.
