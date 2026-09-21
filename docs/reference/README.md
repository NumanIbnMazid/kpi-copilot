# Configuration reference

[Documentation](../README.md) · [Field guide](../16-Configuration-Field-Guide.md)

Every setting, what it does, and when you would touch it.

The narrative documents here explain **why** and **when**. [all-fields.md](all-fields.md) is
the exhaustive generated list — go there when you just want to know whether a field exists
and what it takes.

Faster than either, for one setting:

Commands below start at the repository root with its Python environment. On Windows,
use `.\.venv\Scripts\python.exe` instead of `.venv/bin/python`. Replace profile paths with
your actual private profile location.

```bash
.venv/bin/python plugin/kpi-copilot/scripts/profile_tool.py explain --key workflow.delivered_when
```

---

## The mental model

**Three levels.** Each says only what differs from the one above it:

```
profile defaults      how you usually work
  └─ account          what is true for every project on this client
       └─ project     what is true for just this one
```

A single-client profile can omit accounts, but still declares at least one project. A lead with two clients writes four or five lines per account.

**Two faces.** `profile.yaml` is what the tools read; the **KPI Profile Workbook** is the same
information laid out for a human. Generated from one schema and converted explicitly in both directions. Import workbook
edits before running; the files are not continuously synchronized.

```bash
.venv/bin/python plugin/kpi-copilot/scripts/workbook.py build --profile profile.yaml --out "KPI Profile Workbook.xlsx"
.venv/bin/python plugin/kpi-copilot/scripts/workbook.py read  --xlsx "KPI Profile Workbook.xlsx" --out profile.yaml
```

**Lost?**

```bash
.venv/bin/python plugin/kpi-copilot/scripts/where.py --profile profile.yaml
```

---

## The documents

| | Covers | Touch it when |
|---|---|---|
| [01-tools.md](01-tools.md) | Chat spaces, trackers, plans, sheets, folders — the registry of where everything lives | Adding a client, a chat space, a document |
| [02-accounts-and-projects.md](02-accounts-and-projects.md) | Clients, projects, and the override levels | Taking on a project or a client |
| [03-tracker-and-conventions.md](03-tracker-and-conventions.md) | Which adapter, ticket keys, defect and exclusion conventions | Your board's naming changes |
| [04-workflow.md](04-workflow.md) | What your states mean, and what a team commitment is | A column is renamed, or the process changes |
| [05-sources.md](05-sources.md) | Plan, estimates, timeline, evidence channels, hours | A KPI says "Not measured" and you have the source |
| [06-periods-and-counting.md](06-periods-and-counting.md) | How you slice a project, and the counting choices you may make | Moving from milestones to sprints |
| [07-output-and-files.md](07-output-and-files.md) | Modes, where the sheet goes, where every file lives | Changing how results reach PMS |
| [08-custom-instructions.md](08-custom-instructions.md) | House style, always/never, glossary, rule overrides | The wording is not how you would put it |
| [09-scan-and-source-of-truth.md](09-scan-and-source-of-truth.md) | Which places may answer a question, and how far back a run looks | A run is slower than it should be, or you want the board to be the only truth |
| [all-fields.md](all-fields.md) | Every field, generated from the schema | Looking something up |

## Sections at a glance

| Section | What it is | Overridable per account/project |
|---|---|---|
| `owner` | Who the profile belongs to | no |
| `organization` | PMS, the KPI set, the note format | no |
| `tools` | The registry of places | scoped, not overridden |
| `tracker` | Which adapter, and the fields it reads | yes |
| `conventions` | How your team names things | yes |
| `workflow` | What your states mean | yes |
| `sources` | Plan, estimates, timeline, evidence | yes |
| `scan` | How far a run looks, and how much it reads | yes |
| `periods` | How a project is sliced | yes |
| `policy` | Counting choices | yes |
| `output` | What happens with results | yes |
| `targets` | Labelled local review targets and reasons | yes |
| `custom_instructions` | Your own instructions | yes |
| `accounts` | Your clients | — |
| `projects` | Your projects | — |

## Shared definitions and target ownership

| Not here | Where |
|---|---|
| Official KPI targets | **PMS**, per project, via a registry refresh. Labelled local review targets with a reason are supported under `targets` and block submission until reconciled |
| The KPI list and their ids | PMS |
| How each KPI is counted | The engine, shared by everyone. Changing it is a conversation — see [00-Philosophy.md](../00-Philosophy.md) |

A refusal always names the alternative. If you hit one that does not, that is a bug.

## After editing

```bash
.venv/bin/python plugin/kpi-copilot/scripts/profile_tool.py validate --profile profile.yaml
.venv/bin/python plugin/kpi-copilot/scripts/profile_lib.py --profile profile.yaml --list
```

`validate` checks more than the schema: a tool id that does not exist, an output mode that
contradicts itself, a regex that will not compile, one client's project pointing at another
client's chat.
