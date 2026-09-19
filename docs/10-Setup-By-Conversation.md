# Setting it up by describing your work

You do not fill in a form. You describe how your team actually works, in your own words, and
the setup skill turns that into a profile, shows you what it understood, and asks about the
handful of things it could not infer.

This document is the worked example of that: **a realistic setup message, annotated with what
each part becomes**, followed by shorter variants and the awkward cases that come up in
practice.

> All names, links and ids below are invented. Replace them with yours.

---

## 1. The shape of a good setup message

Four things make a setup message work. Everything else is optional.

1. **Where the work lives** — the tracker, and the documents that are actually the record:
   the plan, the estimates sheet, a timeline or project tracker. **A run reads those and
   nothing else.** Chat spaces are worth naming too, but only as places a *deep* run may look
   when you ask it to; a normal run never searches them.
2. **Who is who** — which names are your side and which are the client's. This is how a date
   agreed by the client is told apart from one your team set itself.
3. **What your words mean** — what "delivered" means, what counts as a defect, what you do not
   count at all.
4. **What you want out** — a sheet to read, or a push to PMS — and **where the sheet should
   live**: a local file (the default), a Google Drive folder, or one specific Google Sheet
   that every run should keep updating.

Everything else the setup skill reads off your board.

---

## 2. A full example

Paste something like this after `/kpi-copilot:kpi-setup`. It is long, but you write it once.

```text
Set up my profile for the Northwind account. I will add my other client later.

WHERE THINGS LIVE
Drive root for the account: https://drive.google.com/drive/folders/<ROOT_FOLDER_ID>
  - "General" holds most day-to-day work; "Management" is leads only.
  - "Client-Shared (shortcut)" is shared with the client. Everyone on their side can read it.
  - "Templates" holds the sheet templates. New trackers get copied from there.
  - "Projects" is the main one: a numbered folder per project, each with Plan,
    Requirements and similar subfolders.
  - The old KPI sheet sits in each project's Plan folder. Going forward I want a
    dedicated KPI folder per project, at the same level as Plan.

Issue tracker: Asana. One board per project. Boards all use the same columns.

CHAT SPACES (most specific first, and say who is in each)
  <SPACE_ID_1>  Client satisfaction. Our CTO and COO are in it.
  <SPACE_ID_2>  Operations. Schedule and end-date changes are announced here.
  <SPACE_ID_3>  General: all devs, QA, managers and leads.
  <SPACE_ID_4>  Management only.
  <SPACE_ID_5>  Client PM + our 2 devs, 2 QA, dev lead, QA lead and me. CLIENT-FACING.
  <SPACE_ID_6>  Leads only, with the client PM. CLIENT-FACING.
  <SPACE_ID_7>  Me, my manager and the dev manager.
  <SPACE_ID_8>  All dev, QA and leads. Highest traffic - most delivery chatter is here.
  <SPACE_ID_9>  Main shared channel with the client. CLIENT-FACING. Important.

KEY DOCUMENTS
  Weekly client call agenda doc: <DOC_ID>. Status goes here every week.
  Daily scrum sheet: <SHEET_ID>.
  Per project, in the Plan folder:
    - Project Plan (PDF): the plan we actually follow.
    - Project Proposal: the original proposal. We share the plan and the proposal with
      the client and get approval before starting.
    - Additional Effort sheet: every change request / extra ask, with hours.
    - [Project Tracker] sheet: major updates and timeline per project. Very important.
  Client's quarterly plan docs: <DOC_ID>, <DOC_ID>.
  Internal team improvement sheet: <SHEET_ID> (leads and managers only).
  Email: everything is under the nested label Projects/Northwind.
  Weekly call transcripts and notes are attached to the Thursday calendar event.

PEOPLE
  Client side: Dana Whitfield (Technical Product Manager, my main contact),
    Evan Hollis (Lead Software Engineer), Sasha Lindo (QA),
    Marisa Cole (Project Manager), Jordan Clarke (Support & Implementation Lead,
    checks builds before they reach their customers), Stefan Barrow (Owner).
  My side: A. Rahman - Project Lead (me). T. Islam - Project Manager, my manager.
    M. Hasan - QA Manager. N. Shahriar - Software Development Manager.
    S. Mahmood - Technical Lead. A. Alam - Dev Lead. (Tech lead and dev lead are
    the same kind of role here.) S. Rahman - QA Lead.

HOW WE WORK
  Velocity should count work whose DEVELOPMENT is finished, before it reaches QA.
  Actual delivery is the handover to the client - the point where their feedback
    starts, or the target date for handing the build over.
  Client Expectation is measured against the date the CLIENT expected delivery.
  Delivery Commitment is measured against the date WE negotiated for a deliverable,
    and whether we met it.
  Defects: cards titled "Bug N" count. "Observation N" and "Improvement N" are
    reported but do not count.
  Do not count grouping cards: anything titled Milestone, Checklist, Bug Reporting,
    Regression Testing, or tagged [Duplicate].
  Change requests are tagged [CR] in the title and are also logged in the Additional
    Effort sheet, which is the source of truth for their hours.
  We slice projects into delivery cycles: "Initial Scope", then "Additional
    Requests 1, 2, ...".
  Measure in hours, not story points.

WHAT I WANT
  A tracker sheet per project in the new KPI folder, then push to PMS after I approve.
  When you prepare KPIs, check the chats, docs, sheets and board comments and write
    proper notes with evidence links.
  If you find something worth recording in the [Project Tracker] sheet, do that too.
```

### What that message becomes

| What you wrote | Where it lands |
|---|---|
| Each chat space, with who is in it | A row in `tools` with `kind: chat`, `people`, and `client_facing: true` on the ones you marked |
| "CLIENT-FACING" | `client_facing: true` — this is how a client-agreed date outranks an internal one |
| "highest traffic, most delivery chatter" | That space is listed first in `sources.evidence_channels` — consulted only on a deep run, and only for the questions a normal run could not answer |
| Drive folders, plan, proposal, effort sheet, tracker sheet | `tools` rows plus `sources.plan`, `sources.estimates`, `sources.timeline` — the allowlist of what a run reads. Sheets get a column mapping; a PDF plan is digested once into `facts/plan.yaml` |
| "a dedicated KPI folder per project" | `output.workbook: google-sheets` and `output.workbook_location: <that folder>` on the project — the sheet is created there once and updated in place after that |
| "Asana, one board per project, same columns" | `tracker.adapter: asana` on the **account**, so every project inherits it |
| "Velocity counts development finished" | `workflow.delivered_when` |
| "Actual delivery is the handover to the client" | `periods.client_check_default: Handover` |
| "Bug N counts, Observation and Improvement do not" | `conventions.defect_pattern`, `policy.count_observations: false` |
| "Do not count Milestone, Checklist, …" | `conventions.exclude_patterns` |
| "[CR] in the title, hours in the effort sheet" | `conventions.cr_marker` and `sources.estimates` |
| "delivery cycles, Initial Scope then Additional Requests N" | `periods.model` and `periods.naming` |
| "hours, not story points" | `velocity_unit: Estimated Hours` |
| "push after I approve" | `output.mode: assisted-push` |
| "write proper notes with evidence links" | `organization.evidence_required: true` |
| "also update the [Project Tracker] sheet" | `custom_instructions.always` |
| Client and internal names | `conventions.client_names`, and the rest for the Tools tab |

Anything it could not infer — your PMS URL, which projects to start with, which of two
columns really means delivered — comes back as a short round of questions. Everything it *did*
infer comes back as statements to correct, not questions to answer.

---

## 3. Shorter versions

### The smallest thing that works

```text
Set up KPI Copilot. Jira, project key ACME, two-week sprints, story points.
Board is the only thing I trust - do not read chat or email.
Give me a sheet; I will type the numbers into PMS myself.
```

That is a complete profile: `tracker.adapter: jira`, `periods.model: Sprint`,
`velocity_unit: Story Points`, `sources.mode: tracker-only`, `output.mode: review-only`.
Everything else takes its default and can be corrected later.

### Board only, and keep it fast

```text
The board is the source of truth. Dev Complete, QA Ready and Closed are always
moved properly, so do not go looking in Slack or email - it is slower and it will
not tell you anything the board does not. Only look at cards touched in the period
being measured. Do not read ticket comments unless you actually need one.
```

```yaml
sources: {mode: tracker-only}
scan:    {window: period+grace, tracker_scope: touched-since, comments: on-demand}
```

This is the single biggest lever on how long a run takes. → [reference/09-scan-and-source-of-truth.md](reference/09-scan-and-source-of-truth.md)

### Two clients, one profile

```text
I run two clients. Northwind is on Asana with Google Chat, and I push to PMS after
approving. Acme is on Jira, we export to CSV, they talk in Slack, and their numbers
get typed in by hand - never push for Acme.
```

One profile, two accounts. The tools are tagged by account, so a run on Acme cannot read
Northwind's chat — the validator refuses a profile that tries.
→ [reference/02-accounts-and-projects.md](reference/02-accounts-and-projects.md)

---

## 4. The awkward cases

These are the ones that actually decide whether the numbers are right.

### What counts as the client-expected date

The most common source of a wrong KPI. Say which of these you mean:

```text
The client-expected date is the handover date in the signed plan. If the client
later agrees a new date in the weekly call, that new date wins. If we moved the
date ourselves because we were late, the ORIGINAL date still stands - score
against it and explain the slip in the note.
```

The rule the tool follows, and will follow unless you say otherwise: **a plan the team revised
on its own is not an agreed date.** Only a date the client set or re-agreed moves the KPI date.

Other shapes people have:

```text
# A release train
There is no per-item client date. The client date is the release feature freeze,
and it is the same for every item in the period. No new features after it; bug
fixes may continue. Use Delivery, not Handover.
```
```yaml
periods: {client_check_default: Delivery}
custom_instructions:
  rule_overrides:
    - rule: client_date_source
      value: "the quarterly release feature freeze"
      why: "One date for the whole period; bug fixes after it are expected."
```

```text
# Only some items are promised to the client
Only the items in the signed scope have a client date. Anything we picked up
mid-cycle has none, and should be left out of Client Expectation rather than
counted as on time.
```

Items with no client date are left out of the denominator and **named in the note**. An item
with no promise cannot break a promise, and counting it as a success is flattery.

### What a team commitment is

Delivery Commitment is *team-negotiated commitments delivered on time ÷ total team-committed
tasks*. The denominator is only items that carry a commitment. Say what yours are:

```text
We commit per milestone, not per ticket. The commitment is the milestone date we
gave the client in the weekly call, and it is met when every item in that
milestone has been handed over by that date.
```
```yaml
workflow:
  commitment:
    scope: committed-only      # only items that carry a commitment
    met_when: handover         # met when the build reached the client
custom_instructions:
  rule_overrides:
    - rule: commit_date_source
      value: "the milestone date given in the weekly call"
      why: "We commit per milestone, not per ticket."
```

`scope` takes `committed-only` — the PMS reading, where only promised items are in the
denominator — or `all-deliverables`, where every item counts as promised. What the milestone
date actually *is* comes from `commit_date_source`.

```text
# Per sprint
What we commit to is the sprint scope, agreed at sprint planning. Met means the
item was accepted - not merged, accepted.
```
```yaml
workflow:
  commitment: {scope: all-deliverables, met_when: accepted}
```

`all-deliverables` is right here because the team commits to the sprint scope as a whole, so
every item in it carries the commitment. `met_when` is free text and reaches the note as
written, so "accepted" says exactly what you mean instead of being forced into "delivered".

```text
# Nothing is formally committed
We do not promise dates per item. Leave Delivery Commitment unmeasured rather
than inventing a denominator.
```

"Not measured", with the reason, is a correct answer. A made-up 100% is not.

### Things you do not do, or do not count

Say them plainly. They become `policy`, `conventions.exclude_patterns`, or
`custom_instructions.never`.

```text
We do not count observations or improvements as defects - only cards titled "Bug".
We do not count defects that were already in the product before our work; they are
tagged [Existing].
We do not do formal UAT on this project, so do not look for one.
Cards titled "Sprint Goal", "QA Checklist" or "Environment Setup" are grouping
cards, not deliverables.
Never post anything to the client-facing chat space.
Never push to PMS on a Friday after 5pm.
Ignore the Support board entirely - it is not part of this project.
```

```yaml
policy:
  count_observations: false
  count_improvements: false
  count_pre_existing: false
conventions:
  exclude_patterns: ['^Sprint Goal', '^QA Checklist', '^Environment Setup']
custom_instructions:
  never:
    - "Never post to the client-facing chat space."
    - "Never push to PMS on a Friday after 5pm."
  glossary:
    - "We do not run formal UAT on this project."
```

Whatever is excluded is **named in the note** — *"Also reported but not counted: 11 that were
already in the product, 6 observations, 2 closed as not a bug."* Nothing is dropped quietly.

### One-off facts the defaults get wrong

For a single ticket or a single period, not a standing rule:

```text
Bug 41 should count as post-release. The client reported it on 08/20, eight days
after the 08/12 handover.
TKT-3333 is not ours - it was logged against the wrong board.
Team-level effort for Initial Scope was 135 hours of bug fixing and regression
that belongs to no single ticket.
```

```yaml
custom_instructions:
  rule_overrides:
    - rule: defect_phase
      value: "Bug 41 = Post-release"
      why: "Client reported it on 08/20, eight days after the 08/12 handover."
    - rule: exclude_key
      value: "TKT-3333"
      why: "Logged against the wrong board."
    - rule: velocity_team_hours
      value: "Initial Scope = 135"
      why: "Bug fixing and regression belonging to no single ticket."
```

`why` is required, and every override is printed **above the numbers** in the run summary. An
adjustment a reader cannot see is not an adjustment, it is a fudge.

### Two columns could mean "delivered"

Boards often have both a "Dev Complete" and a "Ready for QA" column. They are different
events and they give different numbers. Say which is which:

```text
Velocity should count work whose development is finished - that is Dev Complete.
Delivery to the client is a separate thing: the handover, which is a date per
period, not a column.
```

This is worth getting right before the first run rather than after. It shifts every delivery
date on the board.

### What the tracker's own "complete" flag means

```text
Asana's own complete checkbox means merged on our boards, not accepted. Use the
Closed column for accepted.
```
```yaml
workflow:
  closed_when:
    values: [Closed]
    completed_flag_means: "Asana's complete means merged, not accepted."
```

Teams differ on this, and getting it wrong quietly shifts every completion date.

---

## 5. Saying it later instead

Nothing above has to be in the first message. Most of it gets said months later, in passing,
while looking at a number that is wrong:

> "Save the KPI sheets in the Northwind folder."
> "Always show me the previous period next to the new one."
> "For Acme we just type the numbers in ourselves."
> "MK means the PartnerSync integration."
> "Never push on a Friday."

Each of those is a setting. Claude will offer to write it down, with the sentence you said
kept beside it as the reason:

```bash
python3 scripts/remember.py --profile profile.yaml \
  --add custom_instructions.always="Show the previous period" \
  --why "asked in chat while reviewing the August run"

python3 scripts/remember.py --profile profile.yaml --scope account:acme \
  --set output.mode=review-only --why "Acme's numbers are entered by hand"
```

Three rules hold: **it asks first**, `--why` records what you actually said, and a change that
would break the profile is rolled back. `remember.py --history` prints everything captured
that way, which is the answer to "why is this set like this" six months later.

→ [reference/08-custom-instructions.md](reference/08-custom-instructions.md)

---

## 6. After the interview

The setup skill finishes by proving it on a period you already know the answer to:

```bash
python3 scripts/profile_lib.py --profile profile.yaml --list
```

Read that back — it prints every project with the tracker, account and PMS id it resolves to.
Then run one real period in `review-only` and answer one question: *does anything here
disagree with what you know to be true?*

When something is off it is nearly always one of four things, in this order: the
delivered-when mapping, an exclusion pattern eating real work, a date level, or the hours
source. Two or three rounds is normal.

→ [02-Start-Here.md](02-Start-Here.md) · [05-Adapting-To-Your-Workflow.md](05-Adapting-To-Your-Workflow.md)
