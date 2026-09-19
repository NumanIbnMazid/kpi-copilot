# How it is built, and why

For whoever has to maintain, extend or argue with this.

---

## The one decision everything else follows from

The naive way to support a second tracker is to add a branch: `if tracker == "jira"`. Do that
twice and you have a tool where nobody can change the KPI logic without testing it against
every tracker, and where each new tracker makes the next one harder. That is not a solution;
it is the next maintenance problem.

So there are two contracts in the middle, and nothing on the right of either knows which
tracker it came from:

```
 your tracker     reader           board           classify          KIF           engine      the sheet
 ────────────     ──────           ─────           ────────          ───           ──────      ─────────
 Asana            asana/api     ┌─ cards    ─┐     rules propose   ┌─ periods ─┐   nine KPIs   .xlsx, and one
 Jira        ──▶  jira/api   ──▶│  moves     │ ──▶ the assistant ─▶│  tasks    │─▶ notes    ─▶ Google Sheet
 GitHub           github/api    │  comments  │     judges, once    │  defects  │   statuses    updated in place
 <yours>          <yours>/api   └────────────┘     a person        └───────────┘   payloads    PMS push (gated)
 a CSV export     csv/ ─────────(straight to KIF)─ overrules ────────────▲
 ────────────     ──────           ─────           ─────────         ───           ──────      ─────────
 varies           small            FIXED           FIXED             FIXED         FIXED       one description,
                  no judgement                                                                 two writers
```

**The board snapshot** (`scripts/board.py`) is what a tracker *says*: cards, fields, status
moves, comments. No judgement in it. It is also the cache - each card carries `modified_at`,
so a rerun re-reads only what changed.

**KIF** - the KPI Interchange Format - is what the board *means*: periods, tasks, defects,
each row already judged (is it a change request, was it rework, was the bug already in the
product). `scripts/classify.py` gets from one to the other, the same way for every tracker.
The `jira` and `csv` adapters predate the snapshot and still produce KIF directly; both
shapes are supported (`adapters/_contract.md`).

What this buys:

- Supporting a new tracker is one small file that fetches and judges nothing.
- The counting rules **and the judging rules** exist once, so two leads - or two assistants -
  get the same number for the same situation.
- Everything after the reader is testable offline, with no tracker, no network, no browser.
- A bug in one tracker's reader cannot produce a different definition of rework.

Schema: `schemas/kif.schema.json`.

---

## The layers

### 1. Profile — what varies between people

`profile.yaml`, and the KPI Profile Workbook as its human face. Tracker, conventions, workflow
states, sources, periods, output mode, custom instructions, accounts, projects.

Generated from `schemas/profile.schema.json`, which carries `x-workbook` annotations telling
the workbook builder where each setting goes. One source of truth for the schema, the
validator and the spreadsheet — so the file and the workbook cannot disagree.

**Resolution is three-layered**, in `scripts/profile_lib.py`: profile defaults, then the
project's client account, then the project. A lead running Northwind on Asana and Acme on Jira
keeps one profile; each account says what is true for its projects and each project says only
what differs from its account. Dicts merge deeply, lists replace — accumulating another
team's exclusion patterns onto yours is how one regex quietly eats another team's work.

Every script that reads a profile goes through `resolve()`, so the engine, the adapters, the
push and the readiness check cannot disagree about what a project's settings are. The returned
value is a full profile of the same shape, which is why adding accounts meant no change to the
engine at all.

`tools` is one registry, scoped: entries tagged with an account or project are visible only
there, untagged ones to everything. A run on Acme therefore cannot reach into Northwind's chat
for a handover date, and a profile that tries is refused by the validator.

### 2. Readers — tracker to disk

`adapters/asana/api.py`, `adapters/jira/api.py` (Cloud, Server, Data Center) and
`adapters/github/api.py` (Issues, and a Projects board's status). Contract in
`adapters/_contract.md`: one function, `read(project, profile, cache)`, found by the adapter's
name - adding a tracker edits nothing else.

A reader goes API to disk and makes no judgements. One paged call lists the board; each
card's history is fetched in parallel, and only for cards whose `modified_at` moved since the
cached snapshot. 150 cards is about fifteen seconds cold and two or three warm. The token
comes from the environment or `~/.config/kpi-copilot/`, never from a chat.

This layer exists because of what happened without it. The first Asana adapter converted the
output of an extractor nobody shipped, so an assistant scraped the board by hand on every
run and carried it back through the conversation. That - not the arithmetic - was the half
hour (see the Philosophy's "The assistant was the pipeline").

The important field is `capabilities`: what the reader could **actually observe**. A missing
capability makes the KPIs that depend on it "Not measured" with a stated reason. This is what
keeps the tool honest across trackers of wildly different quality, and why the CSV adapter is
a first-class citizen rather than a hack - it simply declares less.

### 2a. Signing in — every route, and which to suggest

`scripts/connect.py`. People differ: some will paste a token into a terminal, most would
rather click Allow in a browser they are already signed in to, and some are not allowed
tokens at all. So each service has several routes - an existing CLI login (GitHub's `gh`), a
browser sign-in (OAuth with PKCE, redirected to localhost, so it works in the person's own
browser or an assistant's built-in one), a token typed by the person, and, for Asana and
Jira, a snippet that downloads the board from an already signed-in tab with no credential at
all. `kpi.py auth` works out what the profile needs, finds what is already connected without
touching the network, and lists the rest best-first for that machine with what each costs;
readers just ask `connect.credential()` for whatever works. A secret is never requested in,
echoed to, or stored anywhere an assistant can see.

### 2b. Sources — the plan, the estimates, the timeline

`scripts/sources.py`. The profile's `sources:` block is an **allowlist**: a run reads these
and nothing else. No chat, no mail, unless a person asks for a deep run, and then only for
the open questions.

Each source is fetched straight to disk and only when it has changed (Drive's modified time,
or a file hash). What is inside is never re-read for the same facts: a tabular source is read
through a **column mapping** written once at setup; a document that is not a table (a PDF
plan) is **digested once** by the assistant into `facts/plan.yaml`, which records the
fingerprint of what it was written from - so the run can say "the plan changed since this was
written" instead of trusting a stale copy in silence. No credential? A file dropped in
`<project>/inbox/` is picked up.

### 2c. Classify, judge, remember

`scripts/classify.py`, `scripts/judge.py`, `scripts/ledger.py`.

For every judged field the order of authority is fixed: **a person > the assistant > a
rule.** Rules propose, with a confidence and a reason, and they read tolerantly - a tag one
or two letters off the team's vocabulary (`[Exisiting]`) is read as the word, and the row's
Check column says so. Anything under the confidence bar goes to `judge/queue.json`: every
open call, the context needed to make it, and the rubric to make it by. The assistant reads
that one file and answers into one file; `kpi.py judge` validates each answer (allowed value,
a stated why) and stores it in the project's **ledger** with who decided, why, and a
fingerprint of the card at the time.

An assistant's answer is reused until the card changes; then it is asked again and shown what
it said before. A person's answer stands until a person changes it. So the first run on a
board asks about a few dozen cards, and the runs after it ask about whatever is new.

The project's memory sits beside its profile as plain files: `ledger.json`, and
`facts/periods.yaml`, `plan.yaml`, `estimates.yaml`, `reasons.yaml`. The sheet's yellow cells
are the same facts seen from the other side.

### 3. Engine — KIF to numbers

`scripts/kpi_engine.py`. Pure. No network, no files beyond its inputs, no tracker knowledge.

Three things it refuses to do:

1. **Guess.** Unobservable means "Not measured" with the reason.
2. **Round away the denominator.** Every value carries its numerator and denominator, and the
   note prints them.
3. **Write anywhere.** It computes. Pushing is somebody else's job.

### 3b. The sheet — described once, written twice

`scripts/sheet_model.py` describes the tracker workbook as plain data: tabs, cells, styles,
live formulas, dropdowns, colour rules. `sheet_xlsx.py` writes it as an .xlsx; `sheet_google.py`
writes the same description into a Google Sheet through the Sheets API, in one atomic
`batchUpdate`, **in place** - the file named in `output.workbook_file`, or one found by name
(created the first time) in `output.workbook_location`. Tabs the tool owns are rebuilt; tabs a
person added are left alone. The two outputs look the same because they are the same.

**Grey cells are live formulas** over the registers, written only with functions that mean
the same in Excel and in Google Sheets. They mirror the engine's counting rules row for row,
and the self-test evaluates them and checks that every one gives the engine's number. The
engine stays the authority - it is what reaches PMS - so KPI Summary carries the engine's own
figure beside each live one, and a "Since the last run" column that speaks up when they
differ. That is how a live sheet avoids being a second, silent source of numbers.

**Reading back.** `sheet_readback.py` records what was written into every yellow cell
(`sheet_state.json`). The next run reads the sheet - the .xlsx, or the live Google Sheet -
*before* rebuilding it, and files each difference where that kind of fact lives: a Yes/No or
a type becomes a person's judgement in the ledger; a date on the Periods tab goes to
`facts/periods.yaml`; a reason to `facts/reasons.yaml`; a hand-set value, with its required
why, to `manual.yaml`; an answer on Open Questions to the ledger's answers; a row typed in by
hand is kept. One thing is reported and **not** applied: a counting rule changed on the Config
tab, because that changes how the project compares with every other.

**What reaches PMS is always what the engine produced from the current inputs.** A hand-set
value is used, with the computed one kept beside it and the note saying so; one without a
reason is refused.

### 4. Delivery — numbers to wherever they go

`scripts/pms_push.py`. The dry run and the real push read the same payload file and take the
same path until the last moment, so they cannot disagree about what was going to happen.
`kpi.py push --apply` refuses while a missed KPI still has no reason.

### 4b. The orchestrator — one command, and NEXT

`scripts/kpi.py run` does the whole chain in one process - board, read-back, sources,
classify, compute, sheet - and ends with **NEXT**: the queue file for the assistant, if there
is anything to judge; the questions for the person, if there are any; or "nothing". It always
finishes with a sheet, even before anything is judged, so nothing blocks on anybody.

It is shaped this way because of two measurements. The deterministic chain takes a fraction
of a second, so seven commands was seven round trips for nothing. And an assistant left to
find evidence will search without limit; so a run reads only what the profile names, and what
that cannot answer is asked, not hunted. Every run prints its own timings, so "was that slow?"
is answerable rather than a feeling. `scripts/run.py` is the earlier orchestrator, kept for
the converter-style adapters and its tests.

### 5. Skills — the part a person talks to

Three: `kpi-setup`, `kpi-run`, `kpi-adapter`. They orchestrate; they do not compute. Anything
deterministic lives in a script, because a script gives the same answer twice.

---

## Where the KPI definitions come from

Not from our code. `scripts/kpi_registry.py --refresh` reads them from PMS: ids, names,
official descriptions, the default targets, and **the targets each project sets for itself**.
We keep only the note headings and the counting basis, which are wording choices rather than
company definitions.

Targets are per project in PMS, and should be — an integration over a legacy surface is not
held to a greenfield defect rate. So the engine resolves each threshold as *this project's
setting, else the PMS default*, and records which on every measure (`threshold_source`). The
markdown marks a project's own target with an asterisk and footnotes it; the workbook has a
"Target set by" column. Someone comparing two projects can see the bar differed and that PMS
is what made it differ.

A target is never stored in a profile. If it were, the workbook could say "Met" while PMS said
"Not met" for the same number, and the lead would be the one explaining the gap.

If PMS raises a threshold, the next refresh picks it up. If PMS adds a KPI we do not know how
to count, the registry keeps it and flags it rather than silently dropping it — a project's
KPI set should never change shape without somebody deciding that.

The bundled fallback (September 2026) is used when PMS is unreachable, and the engine says so
in its output every time. It never passes silently.

---

## Honesty mechanisms

These are deliberate, and the self-test asserts each one. They exist because the expensive
failure of a KPI tool is not a crash — it is a number that is plausible and wrong.

| Mechanism | What it prevents |
|---|---|
| Capabilities on every extract | A tracker that cannot show history producing a confident Rework Rate |
| "Not measured" instead of 0% | A green Met bought by an absence of data |
| No handover ⇒ Escaped Defect Rate is unmeasured | The most flattering possible lie: 0% escaped on a cycle the client has never seen |
| Rework needs at least one judged item | 0% rework because nobody could tell |
| Pending held out of denominators, and named | An open period reading as though it were complete |
| Excluded rows kept with a reason | "Why is my 40-item board showing 12?" |
| Numerator and denominator on every value | A percentage nobody can check |
| Overrides printed above the numbers | A local rule shaping a figure without the reader knowing |
| Targets read per project from PMS, and their source printed | A project's own bar being mistaken for the company default, or a target drifting between the workbook and PMS |
| Hand-set values kept beside the computed one, with a required reason | A number changed in a way nobody can account for later |
| Edits to computed cells reported, never silently dropped | A person believing an edit took effect when it did not |
| Read-back after every push | A write that silently did not land |

---

## Approval

Output mode decides how far a run may go: `review-only`, `dry-run`, `assisted-push`,
`auto-push`. `auto-push` is honoured only with `unattended: true`, and `pms_push.py` refuses
the contradictory combination rather than hanging.

Approval is per run. A yes for one period does not carry to the next, and nothing in a config
file can substitute for a person saying yes in the conversation.

---

## What each run leaves behind

```
<folder of the profile>/<project id>/
├── KPI Tracker - <name>.xlsx   the sheet, rewritten every run
├── ledger.json                 every judgement: value, who, why, the card's fingerprint
├── facts/                      periods, plan, estimates, reasons - plain YAML, yours to read
├── judge/queue.json            what is waiting for the assistant, if anything
├── next.json                   the run's NEXT, for a tool to read
├── sheet_state.json            what was written into the yellow cells, for the read-back
├── cache/                      the board snapshot and the fetched sources
└── runs/2026-09-18/
    ├── run.kif.json            the judged extract
    ├── results.json            values, notes, statuses, gaps, overrides applied
    ├── report.md               the readable version
    ├── payloads.json           exactly what would be, or was, sent
    ├── tracker.xlsx            that day's copy of the sheet
    └── push_log.json           what was written and whether read-back agreed
```

When two runs disagree, diff the two `run.kif.json` files. The change is in the input.

---

## Testing

```bash
python3 scripts/selftest.py
```

About 230 assertions across five complete example stacks (Asana/Sheets/hours/push,
Jira-CSV/Slack/points/review-only, one lead running both, tracker-only, and a whole board-to-sheet
run with an assistant's answers and a person's edits). Most of them are about honesty
rather than arithmetic:
that unmeasurable things come back unmeasured, that locked settings are refused, that
`review-only` will not push, that no note says "1 observations".

The English assertions are there because generated text drifts. A note that says "1 items"
tells a reader nobody is looking at the output, and once they think that, they stop trusting
the numbers too.

---

## Deliberate limits

- **No Asana API adapter.** Asana is read through the signed-in browser, reusing a script
  proven on five live projects. Rewriting that logic in Python would mean rediscovering, by
  hand, everything it already knows about real boards.
- **Dates are not extracted.** Client and commitment dates are an agreement, not a field. The
  adapters leave them null and the run settles them from the plan and the evidence channels.
- **No web UI.** The workbook is the interface. People already have spreadsheets open.
- **Google Sheets writing lives in the skill, not a script.** It needs a signed-in browser and
  fights back in ways best handled conversationally; the mechanics are documented in
  `skills/kpi-run/references/sheets-writer.md`.

---

## Extending it

Adding a tracker: `adapters/_contract.md`, then `/kpi-copilot:kpi-adapter`.

Changing a counting rule: `scripts/kpi_engine.py` plus `skills/kpi-run/references/kpi-rules.md`
plus a self-test case — and a conversation first, because it changes every project's numbers
at once. That friction is intentional. Changing a *target* is not a code change at all: set it
on the project in PMS and refresh.

Adding a KPI: it starts in PMS. Refresh the registry, then teach the engine to count it.
