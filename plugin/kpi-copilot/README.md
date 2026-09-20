# KPI Copilot

Prepare PMS project KPIs from whatever issue tracker a team already uses, with a link
behind every judgement, notes a person can read and a sheet that looks hand-built - then push
to PMS after approval. Driven by an assistant (Claude, Cursor, Codex): one command, one batch
of judgement calls, never any data carried through the conversation. `AGENTS.md` one level up
is the assistant's playbook.

Full documentation is one level up, in `KPI Copilot/docs/`. Start with `01-Overview.md`.

## Install

No public marketplace, and none needed. From the parent folder, which carries a private
marketplace manifest:

```bash
claude plugin marketplace add "/path/to/KPI Copilot"
claude plugin install kpi-copilot@pm-tools
```

Or without installing: `claude --plugin-dir ./plugin/kpi-copilot`.
Or auto-loading for one person: copy this folder to `~/.claude/skills/kpi-copilot/`.

```bash
pip3 install pyyaml openpyxl jsonschema
```

## Skills

| Skill | Use it to |
|---|---|
| `/kpi-copilot:kpi-setup` | Check prerequisites, interview, write the profile and the workbook |
| `/kpi-copilot:kpi-run` | Prepare, review and deliver KPIs for a project (review in chat or in the sheet) |
| `/kpi-copilot:kpi-adapter` | Add support for a tracker that has none |

## Layout

```
kpi-copilot/
├── skills/         kpi-setup, kpi-run (+references), kpi-adapter
├── scripts/        kpi            the one command: run · judge · answer · status · doctor · push · auth
│                   board, classify, ledger, judge      what the board says -> what it means, kept
│                   sources, google_api                 the plan, estimates, timeline; Drive and Sheets
│                   connect                             every way to sign in, and which to suggest
│                   sheet_model, sheet_xlsx,            the tracker sheet, described once, written twice,
│                   sheet_google, sheet_readback        and read back before it is rebuilt
│                   kpi_engine, validate_kif            the nine KPIs, the same for everyone
│                   pms_push, kpi_registry              PMS: gated push, definitions and targets
│                   preflight, profile_tool, profile_lib, remember, workbook, where, release, selftest
├── adapters/       asana, jira, github   readers: API to disk, cached (asana and jira also have a no-credential tab route)
│                   csv                   an export from any other tracker; _contract.md to write a reader
├── schemas/        kif.schema.json, profile.schema.json, kpi_registry.default.json
└── examples/       northwind-board  a whole run, offline: board -> judged -> sheet
                    northwind-q3     Asana, hours, push after approval
                    acme-jira        Jira via CSV, story points, review-only
                    multi-account    one lead, two clients, two trackers, one profile
                    tracker-only     the board is the only source of truth, and bounded
```

## The shape of a run

```
tracker -> reader -> board -> classify + judge -> KIF -> engine -> the sheet -> PMS
(varies)  (small)   (as is)   (fixed, kept)      (fixed) (fixed)  (xlsx + Google) (gated)
```

Scripts move data, the assistant judges what the rules were unsure of, a person decides what
nobody can see from outside - and every call is kept, so it is made once. The counting rules
live in one place so two leads get the same number for the same situation.

```bash
python3 scripts/kpi.py run   --profile profile.yaml --project <id>    # everything, to an updated sheet
python3 scripts/kpi.py judge --profile profile.yaml --project <id>    # after writing judge/answers.json
```

## Try it without any setup

A whole run on a fictional board, offline:

```bash
cp -r examples/northwind-board /tmp/nw
python3 scripts/kpi.py run --profile /tmp/nw/profile.yaml --project northwind-q3 \
  --board /tmp/nw/board.json --today 2026-09-18
```

The engine on its own, from two different stacks:

```bash
python3 scripts/kpi_engine.py --kif examples/northwind-q3/run.kif.json \
  --profile examples/northwind-q3/profile.yaml --reasons examples/northwind-q3/reasons.yaml

python3 adapters/csv/extract.py --profile examples/acme-jira/profile.yaml \
  --project acme-identity --out /tmp/acme.kif.json
python3 scripts/kpi_engine.py --kif /tmp/acme.kif.json --profile examples/acme-jira/profile.yaml
```

The cheapest way to run, for a team whose board is the record:

```bash
python3 scripts/preflight.py --profile examples/tracker-only/profile.yaml --project atlas
```

No run ever searches chat or mail; on a tracker-only profile the plan and estimates are not
opened either, and the readiness check says "not needed" rather than reporting them as gaps.

Two different stacks, one engine.

## Check the tool itself

```bash
python3 scripts/selftest.py
```
