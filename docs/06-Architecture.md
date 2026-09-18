# How it is built, and why

For whoever has to maintain, extend or argue with this.

---

## The one decision everything else follows from

The naive way to support a second tracker is to add a branch: `if tracker == "jira"`. Do that
twice and you have a tool where nobody can change the KPI logic without testing it against
every tracker, and where each new tracker makes the next one harder. That is not a solution;
it is the next maintenance problem.

So there is a contract in the middle:

```
   your tracker          adapter            KIF             engine          your output
   ────────────          ───────            ───             ──────          ───────────
   Asana                 asana/         ┌─ project ─┐      nine KPIs        Google Sheet
   Jira            ───▶  jira/     ───▶ │ periods   │ ───▶ notes      ───▶  xlsx
   ClickUp               csv/           │ tasks     │      statuses         copy-paste
   Linear                <yours>        │ defects   │      gaps             PMS push
   a spreadsheet                        └─ review  ─┘
   ──────────────        ────────        ─────────         ────────        ───────────
   varies                small, varies   FIXED             FIXED           varies
```

**KIF** — the KPI Interchange Format — is a JSON document with four lists: periods, tasks,
defects, and questions for review. An adapter's only job is to emit one. Nothing downstream
knows or cares which tracker it came from.

What this buys:

- Supporting a new tracker is one small file, and everything else comes free.
- The counting rules exist once, so two leads get the same number for the same situation.
- The engine is testable offline, with no tracker, no network and no browser.
- A bug in the Jira adapter cannot produce a different Defect Rate definition.

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

### 2. Adapters — tracker to KIF

`adapters/<name>/extract.py`. Contract in `adapters/_contract.md`.

The important field is `generated.capabilities`: what the adapter could **actually observe**.
A missing capability makes the KPIs that depend on it "Not measured" with a stated reason.
This is the mechanism that keeps the tool honest across trackers of wildly different quality,
and it is why the CSV adapter is a first-class citizen rather than a hack — it simply declares
less.

### 3. Engine — KIF to numbers

`scripts/kpi_engine.py`. Pure. No network, no files beyond its inputs, no tracker knowledge.

Three things it refuses to do:

1. **Guess.** Unobservable means "Not measured" with the reason.
2. **Round away the denominator.** Every value carries its numerator and denominator, and the
   note prints them.
3. **Write anywhere.** It computes. Pushing is somebody else's job.

### 3b. The sheet as a working surface

`workbook.py tracker` writes the tracker workbook; `workbook.py review` reads a person's edits
back out of it. Yellow cells are inputs and round-trip; grey cells are computed and are
regenerated. Rows are matched on their machine field names, held in a hidden row, so a
reordered or hidden column still lands in the right field.

The loop is: edit the sheet → `review` folds the edits into the extract, the reasons file and
the hand-set values → the engine reruns → the payload follows. **What reaches PMS is always
what the engine produced from the current inputs**, which is what stops the sheet and PMS
disagreeing about the same number.

Editing a computed cell does nothing, and `review` reports it rather than dropping it in
silence. The supported route for "this figure is wrong and I cannot fix the input today" is
**Set value by hand** with a reason: the value is used, the computed one is kept beside it,
the reason is printed above the numbers, and the note itself gains a sentence naming both.
A hand-set value without a reason is refused — an override a reader can see is a judgement
call, one they cannot is a discrepancy.

### 4. Delivery — numbers to wherever they go

`scripts/workbook.py` for the working file, `scripts/pms_push.py` for PMS. The dry run and
the real push read the same payload file and take the same path until the last moment, so
they cannot disagree about what was going to happen. That property is why pushing is a
separate script rather than a flag on the engine.

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
runs/2026-09-18/
├── run.kif.json      the extract
├── results.json      values, notes, statuses, gaps, overrides applied
├── results.md        the readable version
├── payloads.json     exactly what would be, or was, sent
├── tracker.xlsx      the workbook, with evidence links
└── push_log.json     what was written and whether read-back agreed
```

When two runs disagree, diff the two `run.kif.json` files. The change is in the input.

---

## Testing

```bash
python3 scripts/selftest.py
```

90 assertions across three complete example stacks (Asana/Sheets/hours/push,
Jira-CSV/Slack/points/review-only, and one lead running both). Most of them are about honesty
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
