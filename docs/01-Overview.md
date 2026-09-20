# KPI Copilot, in three minutes

**Read this one first.** Everything else is optional depth.

---

## What it is

A tool that prepares a project's PMS KPIs from whatever issue tracker the team already uses,
with a link behind every judgement and notes written in English, and then either hands the
project lead a sheet to review or pushes to PMS after they approve it.

It reads Asana, Jira and GitHub (Issues and Projects) directly today, and — through a CSV
export — any other tracker in the company.

## The problem it solves

Preparing KPIs by hand is a day of work per project, per cycle. Worse, it is a day of
*judgement* work: deciding what counts as delivered, which QA failure was rework, whether a
bug was already in the product etc.

## What changes

**The judgement is written down once and applied identically.** What counts as delivered, as
a defect, as rework, as a change request — one implementation, used by everyone. A Defect
Rate of 12% means the same thing on two different projects.

**The workflow stays yours.** Your tracker, your column names, your ticket format, your chat
tool, your period model, your spreadsheet. None of that has to change, and none of it is
hardcoded anywhere.

**One lead, several clients, one profile.** Northwind on Asana and Google Chat, Acme on Jira and
Slack, pushed for one and typed in by hand for the other — all in one file. Say what is true
for a client once and every project on it inherits.

**The time goes where it belongs.** A run is seconds of machine time: the board is read
through its API straight to disk, and only what changed since last time. The remaining effort
is a handful of genuine judgement calls - which is the part that actually needs a brain.

**You talk to it; you do not operate it.** You ask your assistant - Claude, Cursor, Codex -
for the KPI run. It runs one command, makes in one batch the calls the rules were unsure of,
and comes back with the sheet and, at most, a few questions only you can answer. Every call
is kept, with who made it and why, so the next run asks only about what is new.

**The sheet is worth opening.** It looks like something a careful person built by hand, and it
is alive: grey cells are formulas, so changing a yellow cell moves the KPI, the dashboard and
the PMS note at once. It is written locally every run and - if you want - to one Google
Sheet, updated in place, same link every time. What you type in it is read back and kept.

**Nothing reaches PMS without a human saying yes** in the current conversation, including a draft prepared on a schedule.

## The idea that makes it work

A contract in the middle, and a clear division of labour around it:

```
tracker ─▶ reader ─▶ board, as it is ─▶ judged ─▶ engine ─▶ the sheet, and PMS after a yes
 (varies)  (small)                      (fixed)   (fixed)
                     rules propose · the assistant judges what they were unsure of, once
                     · a person overrules · all of it kept
```

**Scripts move data, the assistant judges, a person decides.** Supporting a new tracker means
writing one small file that fetches a board and judges nothing. Everything downstream - the
judging rules, the nine KPIs, the note wording, the sheet, the dry run, the push, the audit
trail - comes free and behaves identically for everybody.

That is the difference between a tool that scales across the company and one that becomes a
maintenance problem the first time someone asks for Linear.

## What it will not do

**It will not guess.** If a team's tracker cannot show whether an item was reopened after
closing, Rework Rate comes back *"Not measured"* with that sentence attached — not a
flattering 0%. A wrong number is worse than a missing one, because a wrong one gets defended
in a meeting.

**It will not keep a second copy of your targets.** Thresholds are configurable per project in
PMS, and they should be — an integration over a legacy surface is not held to a greenfield
defect rate. So the run reads whatever PMS holds for *this* project, marks any target the
project sets for itself, and refuses to store one locally. A target living in a config file is
how a workbook ends up saying "Met" while PMS says "Not met".

**It will not let the counting vary.** What counts as delivered, as a defect, as rework — that
is our interpretation, not PMS's, and it is the reason two projects' numbers can be compared at
all. A team that wants it changed changes it for everybody.

**It will not go looking where you did not send it.** A run reads your tracker and the sources
you named - the plan, the estimates, the timeline. It does not search chat or mail. What those
cannot answer, it asks you, once. You can always send it further, for one run or for good.

**It will not trust a regex over a reader.** People type `[Exisiting]`. The rules read it as
*Existing*, and the row says that they did, so you can disagree.

**It will not invent evidence.** Every Yes/No carries a link to the comment, message or
status change behind it. A number questioned in three months can be traced to what justified
it.

## What adopting it costs a project lead

| | |
|---|---|
| Setup, once | About an hour, mostly answering questions about their own board |
| Per cycle, after that | Minutes of machine time, plus reviewing the judgement calls |
| New tools to learn | None. It reads what they already have |
| Changes to their workflow | None required |

Setup is an interview, not a form. The tool reads their board first and proposes the mapping;
they correct what it got wrong.

## What we are asking for

A pilot: three leads, on three different trackers, one cycle. Then a decision.

Details in [08-Rollout-Playbook.md](08-Rollout-Playbook.md).

---

## Where to go next

| You are | Read |
|---|---|
| Wanting to know why it is built this way | [00-Philosophy.md](00-Philosophy.md) — the core document |
| A lead who wants to try it | [02-Start-Here.md](02-Start-Here.md) — install, configure, first run |
| Checking what you need first | [03-Prerequisites.md](03-Prerequisites.md) |
| Using it week to week | [04-Daily-Use.md](04-Daily-Use.md) |
| Making it fit an unusual workflow | [05-Adapting-To-Your-Workflow.md](05-Adapting-To-Your-Workflow.md) |
| Wondering how it is built | [06-Architecture.md](06-Architecture.md) |
| Adding a tracker, or editing the skills | [07-Extending.md](07-Extending.md) |
| Deciding whether to roll it out | [08-Rollout-Playbook.md](08-Rollout-Playbook.md) |
| Looking up a specific setting | [reference/](reference/) — every field, area by area |
| Stuck, or sceptical about a number | [09-FAQ.md](09-FAQ.md) |
