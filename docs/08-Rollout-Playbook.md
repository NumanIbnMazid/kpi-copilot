# Rollout playbook

For the CTO and whoever ends up owning this. What to decide, in what order, and what to watch
for.

---

## What is being proposed

Make KPI preparation a shared capability rather than something each project lead reinvents:
one implementation of the counting rules, adapters for whatever tracker each team already
uses, and a human approval step before anything reaches PMS.

## The case, in four lines

1. **Comparability.** Today, two careful leads reach different numbers for the same
   situation, because the rules live in their heads. One implementation fixes that.
2. **Time.** A day per project per cycle becomes minutes of machine time plus a focused
   review.
3. **Traceability.** Every judgement carries a link. A number questioned in three months can
   be traced to the comment that justified it.
4. **No workflow churn.** Nobody has to move to a different tracker, spreadsheet or chat tool.

## What it is not

Not a replacement for judgement — it concentrates a lead's attention on the handful of calls
that genuinely need a person. Not a surveillance tool — it measures delivery against agreed
dates, not individuals; the notes describe tasks, not people. Not automatic by default: the
shipped default asks before writing to PMS.

---

## Decisions that need you

| # | Decision | Recommendation |
|---|---|---|
| 1 | Are the counting rules the company standard? | Yes, and fixed. The value is entirely in everyone counting the same way |
| 1b | Who may set a project's targets in PMS? | Already a PMS setting. Worth agreeing who signs off a non-default target, and that it is visible on the report |
| 2 | Who owns a rule change? | You, or a named person. It changes every project's numbers at once |
| 3 | Default output mode for the org | `assisted-push`. Nothing reaches PMS without a person |
| 4 | Is unattended pushing allowed at all? | No. Schedules prepare drafts; submissions need conversation approval |
| 5 | Who gets Claude Code seats? | Every project lead who prepares KPIs |
| 6 | Who grants PMS project access and edit rights? | Name them now — this is the slowest step |
| 7 | Where does the plugin live? | A private marketplace repo, so updates reach everyone |

Decisions 5 and 6 are organisational and take the longest. Start them the day you agree to a
pilot; everything technical is a `pip install`.

---

## Phased plan

### Phase 0 — Pilot (2 weeks, 3 people)

Pick three leads on **three different trackers** — that is the point of the pilot, not
coverage of three projects. One should be somebody who will have to use the CSV adapter,
because that is the experience most of the company will have.

Each: set up, run one completed period, compare against numbers they already trust.

**Success looks like:** each lead recognises the numbers for a period they know, and can
explain any difference. Any surprise is either a real rule they had been applying informally,
or a mapping error — both are worth finding now.

**Watch for:** setup taking more than 90 minutes, which means the interview is asking things
it should be detecting; and a project quietly running on a non-default target nobody agreed to
— the report marks those, so check them.

### Phase 1 — One account (1 month)

Every project on one client account. This is where multi-project use gets exercised: shared
conventions, one profile covering several projects, the workbook as a handover artefact.

Add a native adapter only if a real team is genuinely blocked by the manual export step.

### Phase 2 — Company (1 quarter)

Marketplace install, a named owner, a short internal session, and the four-page doc set.
Measure adoption by *runs*, not installs.

---

## What could go wrong, and what to do

| Risk | What it looks like | What to do |
|---|---|---|
| **Numbers disagree with what a lead expects** | Cycle one, every time | Expected. It is usually a mapping error or an informal rule. Two or three rounds is normal. Build the review round into the plan rather than treating it as a defect |
| **A lead wants a different target** | "Our integration project can't hit 15%" | Legitimate, and PMS already supports it per project. Set it there, with someone signing off. The report marks it as this project's own target so nobody mistakes it for the company default |
| **Targets drift quietly** | Projects on non-default bars nobody agreed | Every run prints which targets are the project's own. Review them at the same time as the numbers |
| **Half the KPIs say "Not measured"** | A team on a tracker with no history | Working as designed, and better than a false number. Six honest KPIs beat nine confident ones. A native adapter fixes it when it is worth the work |
| **A tracker nobody has an adapter for** | Any tracker but Asana and Jira | CSV, same day. Native adapter later if the export becomes a nuisance |
| **PMS access takes weeks** | Blocks the pilot | Start it on day one. The readiness check names the owner for exactly this reason |
| **It becomes one person's tool** | Only the author ever runs it | Name an owner who is not the author. Profiles live where the team can read them |
| **Drift from PMS** | Thresholds change and nobody notices | The registry syncs from PMS on every run, and the fallback announces itself |
| **Too much trust** | Numbers pushed without review | Every submission requires explicit conversation approval |

The two most likely to actually happen are the first and the fifth. Plan for both.

---

## What to measure

After one quarter:

- **Runs per cycle** — the real adoption number.
- **Hours saved**, self-reported against the previous manual process.
- **Review rounds per run** — should fall sharply after the first cycle. If it does not, the
  profile is wrong and nobody has fixed it.
- **KPIs reported "Not measured"** — tells you where tracker quality is actually costing
  visibility.
- **Counting-rule change requests** — each one is either a real gap in the standard or a lead
  trying to score themselves differently. Both are worth knowing about.
- **Projects on non-default targets** — how many, and whether each was signed off.

---

## What it costs

| | |
|---|---|
| Build | Done. Working, self-tested, with two complete example stacks |
| Per lead, setup | About an hour |
| Per lead, per cycle | Minutes of machine time plus review |
| Ongoing ownership | Light. A named owner, occasional adapter work |
| Licences | Claude Code seats. No other new tooling |

---

## The ask

Approve a two-week pilot with three leads on three different trackers, and name the person
who can grant PMS project access.

Everything else can be decided after the pilot, with real numbers from real projects rather
than from this document.
