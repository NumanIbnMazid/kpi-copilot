# The brief

What this project has to do, written as a specification rather than a wish list. It is the
contract the work is measured against; [docs/00-Philosophy.md](docs/00-Philosophy.md) is the
reasoning behind how it was met.

---

## 1. The problem

Preparing a project's KPIs for PMS is a day of work per project, per cycle. Most of that day
is not arithmetic — it is judgement. Deciding what counts as delivered. Whether a QA failure
was rework or normal testing. Whether a bug was already in the product. Whether a date was
agreed with the client or merely planned by the team.

Two careful project leads, applying their own judgement to the same board, will reach
different numbers and both be able to defend their answer. The rules live in people's heads,
so they diverge — which means the figures management compares across projects are not
actually comparable.

Any solution has to fix the comparability problem. Saving the day is necessary but secondary.

---

## 2. What must be identical for everyone

If these vary between people, the exercise is theatre.

- **PMS is the destination.** KPIs are recorded against a PMS project and period.
- **The KPI set is fixed** — the nine PMS KPIs, their IDs and their direction. Definitions and
  targets are read *from PMS itself*, never copied into code, so the tool cannot drift from
  what the company measures. Targets are configurable per project in PMS and legitimately
  differ; what must not differ is the counting behind the number.
- **How each KPI is counted** — what counts as delivered, as a defect, as rework, as a change
  request. Same situation, same number, whoever runs it.
- **The note format** — `what the numbers say, in sentences || what was left out || why` —
  and the requirement that notes read as though a person wrote them.
- **Evidence or it does not go in.** Every judgement and every date traces to a link.
- **Nothing reaches PMS without a human saying yes** in the current conversation. A scheduled draft still needs review.

## 3. What must be free to vary

Everything else, and not only the examples below.

| Dimension | Range that has to be supported |
|---|---|
| Issue tracker | Asana, Jira, ClickUp, Linear, Azure DevOps, GitHub Issues, Trello, a spreadsheet |
| Workflow states | "Ready for QA" vs "In Test" vs a status field vs a label |
| Ticket key convention | `TKT-1234`, `PROJ-99`, a numeric id, a custom field, none at all |
| Defect convention | Cards named "Bug 12", an issue type, a label, a separate QA board |
| What is out of scope | Grouping cards, milestone markers, QA admin cards, duplicates |
| Where the plan lives | A PDF, a sheet, Confluence, Notion, an epic, nowhere written down |
| Where status and timeline live | One sheet per project, a tracker dashboard, a database, email |
| Where the team talks | Google Chat, Slack, Teams, email threads |
| Period model | Milestones, delivery cycles, sprints, monthly, one "Full Project" |
| Velocity unit | Estimated hours, story points |
| Where working files go | Google Sheets, local Excel, a Drive folder, SharePoint |
| How results reach PMS | Automatic push, dry run then approve, or a review sheet typed in by hand |
| Scale | One lead may run several projects, across several clients, on several trackers at once |

## 4. How it must feel to adopt

- **Interview, do not interrogate.** Inspect what the person already has, propose a mapping,
  ask them to correct it. Detect first, ask second. A new lead should have a real KPI set for
  a real project inside an hour, not be filling in a forty-field form.
- **One place holds the configuration**, readable by somebody who has never seen the code: a
  workbook where every row is a tool or a rule with a plain-language description — *this is
  the tracker and here is the board; this is the chat space where we talk to the client; this
  is the folder the working file goes in; this is what "delivered" means on our board*.
- **Machine-readable and human-readable stay in sync.** The workbook and the config file are
  two views of one thing, and neither can silently drift from the other.
- **Nothing is mandatory that a team does not have.** No plan document, no estimates sheet, no
  chat history — the tool degrades to "Not measured, and here is why" rather than guessing.
- **Easy by default, deep when wanted.** Sensible behaviour with almost no configuration, and
  a route to change anything that genuinely varies, without editing code.

## 4b. How it must feel to use

Added after the first real runs took over half an hour and produced a sheet nobody wanted to
open. These are requirements, not polish.

- **It is driven by an assistant, not from a terminal** - Claude, Cursor, Codex, whatever the
  lead has. So it must not depend on any one of them, and the assistant's instructions must
  be short enough to be followed.
- **A run is minutes, and a rerun is seconds.** Nothing bulky - a board, a spreadsheet, a PDF
  - may travel through the assistant's context. Data goes API to disk to API.
- **A run reads what it was configured to read, and nothing else**: the issue tracker, and
  the plan, estimates and project-tracker documents named in the profile. What they cannot
  answer becomes a question, asked once. Looking further - a chat space, five chat spaces -
  happens only because a person configured it or said so in the request.
- **Use the brain where a brain is needed, and only there.** Identifying what a card is,
  reading a mistyped tag (`[Exisiting]`), writing the reason behind a missed KPI: judgement,
  by written definitions, made once and kept. Fetching, reshaping, formatting: never.
- **The sheet is the product.** It follows the look of a good hand-built tracker - its tabs,
  columns, colours, live formulas and dashboard - and adds what this tool knows: how each
  unobvious row was decided, the open questions, what was and was not read, what moved since
  last time.
- **Two homes for the sheet.** Locally by default. Or, when the lead names a Google Drive
  folder or a specific Google Sheet - at setup or any time after - that same Google Sheet is
  updated on every run, in place. The local one looks the same.
- **What a person types in the sheet is kept**, and outranks everything else.

## 5. What has to exist

1. **The solution itself**, in whatever form is genuinely easiest to install, use and hand to
   the next person. Versioned, shareable, and updatable without a public marketplace.
2. **Documentation in layers.** A page that a CTO or a new lead can read in three minutes.
   Then a step-by-step start guide. Then day-to-day use. Then field-level configuration
   reference. Then the deep material for whoever has to extend it.
3. **A philosophy document** that records why the design is what it is, so the next person can
   make a decision the same way without asking anyone.
4. **A presentation** for the rollout conversation: the problem, what it changes, how it
   rolls out, what it risks.
5. **This brief.**

## 6. How it must be built

Research before designing — including how a Claude skill is actually meant to be written, how
plugins are packaged and distributed to a team, and what an existing working pipeline already
knows that must not be lost.

Think past the obvious answer. The naive version of tracker support is an if-statement per
tracker, and that is not a solution, it is the next maintenance problem.

Prefer a refusal that names its alternative over a restriction that gets routed around.
Prefer an honest gap over a plausible number.

---

## 7. Success test

A project lead who has never seen this repository, who uses Jira and Slack and keeps their
plan in Confluence, and who also runs two projects for a second client on a different tracker,
can:

1. install it,
2. answer a short interview,
3. get a KPI set for one of their real projects, with evidence links and readable notes,
4. choose whether the numbers go to PMS automatically or whether they enter them by hand,
5. correct anything that is wrong, in a spreadsheet, and have the corrections flow through,
6. ask for the run again next month, in one sentence, from whichever assistant they use, and
   have an updated sheet at the same link within a couple of minutes - without the assistant
   ever opening the board, re-reading the plan, or asking again what it was told last time,

and the numbers they produce are counted by exactly the same rules as everybody else's.
