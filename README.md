# KPI Copilot

Prepare a project's KPIs from whatever issue tracker your team already uses — with a link
behind every judgement, notes a person can read, a sheet that looks hand-built, and nothing
reaching your PMS without someone saying yes.

You do not run it from a terminal. You ask your assistant — Claude, Cursor, Codex, anything
that can run a command — *"do the KPI run for the Q3 release"*, and a minute later there is
an updated sheet and, at most, a short list of questions.

Reads Asana, Jira (Cloud, Server, Data Center) and GitHub Issues/Projects directly, and —
through a CSV export — any other tracker. One profile covers several clients on several
trackers. Sign in however you prefer: a login you already have, your browser, a token, or a
tab you are already signed in to.

[![tests](https://img.shields.io/badge/self--test-260%2B%20passing-brightgreen)](plugin/kpi-copilot/scripts/selftest.py)
[![licence](https://img.shields.io/badge/licence-MIT-blue)](LICENSE)

```bash
git clone https://github.com/NumanIbnMazid/kpi-copilot.git
cd kpi-copilot && pip3 install pyyaml openpyxl jsonschema
python3 plugin/kpi-copilot/scripts/selftest.py        # 260+ assertions, no setup needed
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

**Scripts move data. The assistant judges. A person decides.**

```
tracker ─▶ reader ─▶ board ─▶ rules propose ─▶ judged ─▶ engine ─▶ the sheet (.xlsx + Google Sheet, in place)
 (varies)  (small)   (as is)   assistant judges  extract   (fixed)   PMS, after an explicit yes
                               a person overrules
                               └── kept in a ledger, asked once ──┘
```

- **The board goes API to disk in seconds**, and only changed cards are re-read. Nothing
  bulky ever travels through a chat window - that, not arithmetic, is what makes a run slow.
- **A run reads what your profile names** - the tracker, the plan, the estimates, the
  timeline - and nothing else. What those cannot answer is asked, once, not hunted for.
- **Rules read what people actually type.** `[Exisiting]` is read as *Existing*, and the row
  says so. What a rule is unsure of goes to the assistant in one batch, by written
  definitions; the answer is kept with its reason, so the next run asks only what is new.
- **The sheet is the product**: navy headers, yellow for what is yours, grey *live* formulas,
  a dashboard with bars. Written locally every run, and - if you want - to one Google Sheet
  updated in place. Whatever you type in it is read back and kept.
- **The counting is the same for everyone**, which is the point: two leads, or two
  assistants, should get the same number for the same situation.

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
| `AGENTS.md` | How any assistant drives a run. Cursor and Codex read it by themselves |
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

**Cursor, Codex, or anything else:** there is nothing to install. Clone the repository, open
it, and ask. [`AGENTS.md`](AGENTS.md) tells the assistant how to drive a run; the three
skills under `plugin/kpi-copilot/skills/` are plain Markdown it can read.

**Releasing a change.** An installed plugin is a copy, so edits here reach nobody until the
version is bumped in both manifests:

```bash
python3 plugin/kpi-copilot/scripts/release.py --patch
```

It runs the self-test, bumps both files, and prints the two commands everyone else runs.
Details in [docs/07-Extending.md](docs/07-Extending.md#part-5-how-updates-reach-people).

## Try it in thirty seconds

A whole run on a fictional board - offline, no credentials:

```bash
cd plugin/kpi-copilot
pip3 install pyyaml openpyxl jsonschema
cp -r examples/northwind-board /tmp/nw
python3 scripts/kpi.py run --profile /tmp/nw/profile.yaml --project northwind-q3 \
  --board /tmp/nw/board.json --today 2026-09-18
```

Twenty-five cards become fifteen task rows and eleven reports, nine KPIs for two periods, and
a workbook, in a third of a second. Look at how it ends: **NEXT** names six cards for the
assistant to judge - one of them a bug tagged `[Exisiting]` - and one question only a person
can answer. Open the workbook, change a yellow cell, and watch the grey ones move.

On a real board the same command reads Asana, Jira or GitHub through its API:

```bash
python3 scripts/kpi.py auth --profile profile.yaml --project <id>   # what needs connecting, and the best way for this machine
python3 scripts/kpi.py run  --profile profile.yaml --project <id>
```

Against a live GitHub repository that is 150 issues with their full history in about
fourteen seconds, and under two on the next run.

One lead, two clients, two trackers, one profile:

```bash
python3 scripts/profile_lib.py --profile examples/multi-account/profile.yaml --list
```

## Check the tool

```bash
python3 plugin/kpi-copilot/scripts/selftest.py
```

260+ assertions, mostly about honesty rather than arithmetic - including that every live
formula in the sheet gives the engine's number, and that an assistant cannot overrule a person.
