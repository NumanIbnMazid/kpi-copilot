# KPI Copilot

Prepare a project's KPIs from whatever issue tracker your team already uses — with a link
behind every judgement, notes a person can read, and nothing reaching your PMS without
someone saying yes.

Works with Asana, Jira, and — through a CSV export — any other tracker. One profile covers
several clients on several trackers.

[![tests](https://img.shields.io/badge/self--test-117%20passing-brightgreen)](plugin/kpi-copilot/scripts/selftest.py)
[![licence](https://img.shields.io/badge/licence-MIT-blue)](LICENSE)

```bash
git clone https://github.com/NumanIbnMazid/kpi-copilot.git
cd kpi-copilot && pip3 install pyyaml openpyxl jsonschema
python3 plugin/kpi-copilot/scripts/selftest.py        # 159 assertions, no setup needed
```

---

## Where this came from

It is the generalised version of a pipeline built for one project lead and used on five live
projects. The counting rules were argued out against real boards and real client deadlines,
not derived from theory.

The examples here are fictional. The real client, the people, the system identifiers and one
piece of internal tooling were removed before publishing; everything that makes the tool work
is here.

## The idea

```
your tracker  ->  adapter  ->  common format  ->  engine  ->  your output
   (varies)      (small)         (fixed)         (fixed)      (varies)
```

Supporting a new tracker is one small file. The nine KPIs, the note wording, the workbook, the
dry run, the push and the audit trail come free and behave identically for everybody — which
is the point: two leads should get the same number for the same situation.

**[docs/00-Philosophy.md](docs/00-Philosophy.md)** explains why it is built this way, and is
the document to read before changing anything.

---

## Start here

**[docs/01-Overview.md](docs/01-Overview.md)** — three minutes, and the one to send anybody.
**[docs/02-Start-Here.md](docs/02-Start-Here.md)** — install, configure and run, step by step.
**[docs/10-Setup-By-Conversation.md](docs/10-Setup-By-Conversation.md)** — what to actually say to set it up, with examples.
**[docs/00-Philosophy.md](docs/00-Philosophy.md)** — the core document, for whoever builds on this.

## What is in this folder

| | |
|---|---|
| `docs/` | Ten documents, from a three-minute overview to the architecture |
| `plugin/kpi-copilot/` | The tool itself: skills, scripts, adapters, schemas, examples |
| `templates/` | A blank KPI Profile Workbook to look at |
| `presentation/` | The deck for the CTO conversation |
| `PROMPT.md` | The brief this was built from, rewritten as a specification |

## Documentation

| Read | If you are |
|---|---|
| [00-Philosophy](docs/00-Philosophy.md) | **The core document.** Why it is built this way, and how to decide what comes next |
| [01-Overview](docs/01-Overview.md) | Anyone. Three minutes |
| [02-Start-Here](docs/02-Start-Here.md) | A lead wanting a first run — about an hour |
| [03-Prerequisites](docs/03-Prerequisites.md) | Checking what you need, and who has to grant it |
| [04-Daily-Use](docs/04-Daily-Use.md) | Using it week to week |
| [05-Adapting-To-Your-Workflow](docs/05-Adapting-To-Your-Workflow.md) | Making it fit something unusual |
| [06-Architecture](docs/06-Architecture.md) | Maintaining or arguing with it |
| [07-Extending](docs/07-Extending.md) | Adding a tracker, or editing the skills |
| [08-Rollout-Playbook](docs/08-Rollout-Playbook.md) | Deciding whether to roll it out |
| [09-FAQ](docs/09-FAQ.md) | Stuck, or sceptical about a number |
| [10-Setup-By-Conversation](docs/10-Setup-By-Conversation.md) | Setting it up by describing your work — a full worked example, and the awkward cases |
| [reference/](docs/reference/) | Looking up a specific setting — every field, area by area |

## Install

No public marketplace needed — this folder *is* a private marketplace:

```bash
claude plugin marketplace add "/path/to/KPI Copilot"
claude plugin install kpi-copilot@pm-tools
```

Then `/reload-plugins`. Or skip installing entirely with
`claude --plugin-dir "KPI Copilot/plugin/kpi-copilot"`.
Full options in [docs/02-Start-Here.md](docs/02-Start-Here.md).

**Releasing a change.** An installed plugin is a copy, so edits here reach nobody until the
version is bumped in both manifests:

```bash
python3 plugin/kpi-copilot/scripts/release.py --patch
```

It runs the self-test, bumps both files, and prints the two commands everyone else runs.
Details in [docs/07-Extending.md](docs/07-Extending.md#part-5-how-updates-reach-people).

## Try it in thirty seconds

```bash
cd plugin/kpi-copilot
pip3 install pyyaml openpyxl jsonschema
python3 scripts/kpi_engine.py --kif examples/northwind-q3/run.kif.json \
  --profile examples/northwind-q3/profile.yaml --reasons examples/northwind-q3/reasons.yaml
```

One lead, two clients, two trackers, one profile:

```bash
python3 scripts/profile_lib.py --profile examples/multi-account/profile.yaml --list
```

Then a whole run — the same engine on a completely different stack (Jira via CSV, sprints,
story points, review-only) — in one command:

```bash
python3 scripts/run.py --profile examples/acme-jira/profile.yaml \
  --project acme-identity --skip-preflight --out-dir /tmp/acme-run
```

Extract, validate, compute, workbook and payloads, in about a quarter of a second. Note what
it refuses to measure and that it says why, and note how it ends: not "go and look in chat",
but a list of the facts that are actually missing, with the tickets they belong to.

## Check the tool

```bash
python3 plugin/kpi-copilot/scripts/selftest.py
```

159 assertions, mostly about honesty rather than arithmetic.
