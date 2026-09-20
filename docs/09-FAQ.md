# Questions people actually ask

---

### My team uses ClickUp / Linear / Azure DevOps / Monday / Trello. Is this for me?

Yes, today, via the `csv` adapter. Export your board, point the profile at the file, done.

Six of the nine KPIs work normally. The three that need status history — Delivery Commitment,
Rework Rate, Task Comprehension — come back "Not measured" with a sentence explaining why,
unless your export happens to carry a column for them. Many exports do carry a "date moved to
`<status>`" column; map it and Delivery Commitment starts working.

A native adapter is worth writing when the manual export becomes annoying, not before.

### I run several projects, on different trackers, for different clients. Does that work?

Yes, in one profile. Three levels: your defaults at the top, then an **account** for each
client, then a project only if it differs from its account.

Almost everything that varies varies per client, so it is usually four or five lines per
account — the tracker, the chat spaces, the conventions, sometimes the output mode. Northwind's
five projects then say nothing at all beyond their PMS id and board id.

The Tools registry is shared and scoped: tag the Google Chat space with `accounts: [northwind]`
and the Slack channel with `accounts: [acme]`, and each run only sees its own. Pointing one
client's project at another client's chat space fails validation rather than silently
searching the wrong place.

`python3 scripts/profile_lib.py --profile profile.yaml --list` shows every project with the
tracker and PMS id it resolves to. Every command takes `--project`.

Worked example: `examples/multi-account/`. Detail:
[05-Adapting-To-Your-Workflow.md](05-Adapting-To-Your-Workflow.md#several-projects-several-clients-several-trackers).

### Can one client push to PMS while another is review-only?

Yes — `output.mode` is an account override. Set `review-only` on the client whose numbers you
type in by hand and `assisted-push` on the rest. The push script resolves the mode for the
project you name and refuses to write for the ones that are review-only.

### Do I have to change how my team works?

No. That is the design assumption. Your tracker, column names, ticket format, chat tool,
period model and spreadsheet all stay. The setup interview reads your board and adapts to it.

### Will it change anything in my tracker?

No. Adapters are read-only. Not a label, not a comment.

### Will it push to PMS without asking?

No. An explicit yes in the current conversation is required for the reviewed payload.
Schedules may prepare drafts. Legacy automatic settings do not supply approval.

### Why did a run take half an hour?

The pipeline avoids manual card-by-card reading: it fetches data to disk, caches evidence,
and batches unresolved judgements. Every run prints timings. First reads, provider rate
limits, source digestion and review still take time. Use those measurements to identify the
bottleneck; do not assume a slow run is the user's or assistant's fault.

### It counted a bug as ours because somebody typed "[Exisiting]". Seriously?

Not any more. Tags are read the way a person would read them: a word one or two letters off
your team's vocabulary is read as that word, and the row's Check column says *"read
[Exisiting] as Existing"* so you can disagree. Anything the rules are not sure of goes to the
assistant, which judges it once by a written definition; its answer is kept with the reason.
And you can always overrule either in the sheet - your answer stands until you change it.

### Does it go digging through my chat and mail?

No. A run reads your tracker and the sources you named in the profile - the plan, the
estimates, the timeline - and nothing else. What those cannot answer becomes a question for
you on the Open Questions tab, asked once. If you *want* it to look further - "also check the
client chat for the handover date" - say so, for that run; or list places under
`sources.evidence_channels` and ask for a deep run. Even then it looks up only the open
questions, only there.

### Where does the KPI sheet live? Can it be a Google Sheet?

By default it is an .xlsx beside your profile, rewritten every run. Tell it once to keep it in
Google Sheets - a Drive folder, or one specific sheet's link - and every run updates that
same Google Sheet in place, so the link never changes. Both look the same, because they are
written from one description modelled on a hand-built tracker: navy headers, yellow for what
is yours, grey live formulas, a dashboard with bars. Connecting Google is a one-time sign-in
you do yourself ([03-Prerequisites](03-Prerequisites.md)); without it you still get the local
file, and File > Import > Replace spreadsheet puts it over the same Google Sheet.

### Which trackers does it read?

Asana, Jira (Cloud, Server and Data Center) and GitHub (Issues, with or without a Projects
board) are read directly through their APIs, straight to disk, with only changed items
re-read on the next run. Everything downstream - the judging, the nine KPIs, the sheet - is
identical whichever it is. Any other tracker starts today from a CSV export, and a reader for
it is one small file that fetches and judges nothing (`adapters/_contract.md`).

### Do I have to paste a token into a terminal?

No - that is one way in, not the only one. `python3 scripts/kpi.py auth` (or asking your
assistant "what do I need to connect?") lists the ways for your machine, best first:

- **a login you already have** - if GitHub's `gh` is signed in, there is nothing to do;
- **sign in in your browser** and click Allow - your own browser or your assistant's built-in
  one. Asana, Jira Cloud and Google; it needs a small app registration your company does once;
- **a token** you type in a terminal - a minute to set up, the fastest at run time, and the
  only one that suits an unattended schedule;
- **a tab where you are already signed in** - a snippet downloads the board as a file. No
  credential at all; slower, and you have to be there.

Whichever you pick, a token or password never passes through the assistant.

### Does it only work with Claude?

No. Everything is a Python command plus files. `AGENTS.md` at the top of the repository tells
any assistant that can run commands - Claude, Cursor, Codex - how to drive a run. The
`/kpi-copilot:*` skills are a convenience on Claude.

### Half my KPIs say "Not measured". Is it broken?

No, it is being honest. It means the adapter could not observe something that KPI needs, and
it would rather say so than produce a number that looks fine and is wrong.

Each one comes with a reason in its note, and what a person could answer is on the Open
Questions tab. Six honest KPIs are
worth more than nine confident ones, because a wrong number gets defended in a meeting and
built on.

### A number disagrees with what I know. What now?

Do not adjust the value. Change the input or the mapping and rerun — a number edited to look
right cannot be defended the second time it is questioned.

Six causes, in order of likelihood: the delivered-when mapping names the wrong state; an
exclusion pattern is eating real work; the wrong date level is winning; the hours source is
pointing at the wrong place; rework is counting first-round QA failures; or the adapter
genuinely could not see something.

Full list with symptoms: `skills/kpi-run/references/troubleshooting.md`.

### Can I change a threshold? Our integration project cannot hit 15% defect rate.

Yes. Use project targets in PMS for official reporting, or explicit local review targets
with a reason in the profile. Local targets are labelled and prevent PMS submission until
reconciled. See [project targets](05-Adapting-To-Your-Workflow.md#project-targets).

### But I do have project facts the defaults get wrong.

That is what `rule_overrides` is for, and it is allowed. Ten supported rules, each requiring a
`why`, and each printed at the **top** of every run summary — before the numbers, so anyone
reading them knows a local rule shaped them.

### Why does Escaped Defect Rate say "Not measured" when it should be 0%?

Because the period has no handover date. Nothing can escape from a cycle the client has never
seen, so 0% would be the most flattering possible lie — and the least likely to be
questioned. Set the handover date when the build goes out and it starts measuring.

### Why is my Rework Rate lower than I expected?

Probably correctly. Rework means **closed, then reopened**. A QA failure while an item is
still being tested for the first time is normal testing, not rework; it is named in the note
as not counted. This is the most commonly mis-scored KPI in the set.

### Why is my item count lower than my board?

Excluded rows. Grouping cards, milestone markers, QA admin cards, duplicates. Every one is
listed in the Task Register with a reason — check whether an exclusion pattern is broader than
you meant. `^Bug` will happily remove "Bugfix: client login".

### Can I edit things in the sheet, and will that reach PMS?

Yes. Yellow cells are yours and come back; grey cells are computed and regenerated.

Change a Yes/No judgement, an item type, a period, hours, a date, a defect's rejection, a
handover date or the **Why** text. The grey cells are live formulas, so the numbers, the
dashboard and the PMS note move at once. The next run reads your edits back **before** it
rebuilds the sheet, files each as your decision - which outranks the assistant's and the
rules' - and tells you what it read. The push sends what the run computed from those inputs,
so the sheet and PMS cannot end up saying different things. If KPI Summary's "Since the last
run" column says anything, run again before pushing.

### What if the computed number itself is wrong?

Put the right one in **Set value by hand**, with a reason in **Why set by hand**. It is used.

Three things then happen, all deliberate: the computed figure is kept beside it, the reason is
printed above the numbers in the run summary and in the workbook, and the note itself gains a
sentence — *"Recorded as 33% by A. Rahman rather than the 40% above: two of the 07/31 items were
re-scoped as plan work."* The PMS payload carries the hand-set value, the computed one, and
the reason.

A hand-set value with **no** reason is refused. That is the only real restriction, and it is
there because an override a reader can see is a judgement call, while one they cannot is a
discrepancy nobody can explain three months later.

Typing over the grey Value or Note column does nothing — `review` reports it and tells you
which column would have worked. Better still, fix the register row that produced the wrong
figure and rerun; then the number is right for the right reason.

### Do I need a project plan PDF and an estimates sheet?

No. All sources are optional. Missing ones produce "Not measured" with a reason rather than a
guess. They improve the numbers where they exist; they are not a precondition.

### Where does my configuration live, and can my team read it?

`profile.yaml`, and the **KPI Profile Workbook** — the same information laid out for a human,
one tab per topic, every row with a plain description. Edit either; they convert back and
forth and cannot drift.

Put the workbook where your team keeps things. A profile only one person can open is a
profile that dies when they go on leave. The Tools tab in particular is the fastest
explanation of a project that exists.

### Can I tell it how I want things worded?

Yes. `custom_instructions` takes a house style, always/never rules, a glossary of your team's
words, and an escalation rule. The glossary is more useful than it looks — it stops a note
being technically correct and still misleading.

### Is this measuring people?

No. It measures delivery against agreed dates. Notes describe tasks, not individuals — effort
overruns name the work. Nothing produces a per-person figure.

### What happens if PMS is down?

Extraction and computation work offline. The KPI definitions fall back to a bundled copy, and
the engine says so in its output every time rather than letting it pass silently. Push fails
cleanly; rerun it later against the same payload file.

### Can I run it on a schedule?

Yes, using your assistant or operating system scheduler to prepare drafts. Scheduling
support varies by host. Review and approve a fresh preview before any PMS submission.

### How do I know what it did three months ago?

`<project>/runs/<date>/` stores the extract, results, payload and push log. Same-day reruns
reuse that folder; use distinct `--date` labels for separate snapshots. It is a working
record, not an immutable audit archive. Preserve reviewed snapshots under your retention policy.

### Someone questions a number in a review. What do I show them?

The tracker workbook. KPI Summary has the value, target, numerator and denominator; the Task
and Defect Registers have the evidence link behind every judgement, and a Check column saying
how any row that was not obvious was decided; `ledger.json` has who made each call and why.

### How do I know the tool itself is right?

```bash
python3 scripts/selftest.py
```

159 assertions across four complete example stacks. Most of them check honesty rather than
arithmetic: that unmeasurable things come back unmeasured, that a local target is refused and
points at PMS, that `review-only` will not push, that one client's run cannot see another
client's chat space, and that no generated note says "1 observations".

### Can I use it for a project that has already finished?

Yes. It reads history, so a closed project works as well as a live one — useful for
backfilling PMS or for checking the tool against a period you already know the answer to.

### What if I find a rule that is genuinely wrong?

Raise it. The rules were argued out against real boards, not derived from theory, and they
can be wrong. But a change alters every project's numbers at once, so it goes through the
owner and lands in one place for everybody. That friction is the feature.
