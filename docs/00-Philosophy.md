# Philosophy

The core document. Everything else in this project is downstream of what is written here.

If you are picking this up to extend it, change a rule, add a tracker, or decide whether some
new idea belongs — read this first, and use it to decide. The code can be rewritten; these
commitments are the thing worth keeping.

---

## What this is really for

Automate KPI preparation and insertion, with judgement a person can inspect.

The expensive part of preparing a project's KPIs was never the arithmetic — it was the
**judgement**: deciding what counted as delivered, whether a QA failure was rework, whether a
bug was already in the product, whether a date was agreed or merely planned. Two careful
people applying their own judgement to the same board reach different numbers, and both can
defend their answer.

That is the actual problem. When every project lead is their own measuring instrument, the
numbers management reads are not comparable, and nobody can tell whether a Defect Rate of 12%
on one project means anything next to 12% on another.

**The purpose is to save the lead's time without losing the reason behind a number.**
Stable judgement, bounded source reads and reusable configuration make that automation useful.

---

## The twelve commitments

### 1. Separate what must be identical from what must not be

This is the first question to ask about any new feature, and it answers most of them.

**Shared:** the calculation engine, evidence requirements and published meaning of each KPI.
The same inputs and policy must produce the same result.

**Free to vary:** the tracker, the column names, the ticket format, the chat tool, the period
model, the spreadsheet, where files live, delivery gates, defect inclusion policy, note style,
and the **target** each project is held to. Differences must be visible alongside the result.

Getting this line right is the whole design. Put too much on the fixed side and nobody adopts
it, because it demands they change how they work. Put too much on the varying side and the
numbers stop being comparable, which was the point.

When a new setting is proposed, the test is: *would two leads getting different answers here
make their KPIs incomparable?* If yes, it is fixed. If no, it is theirs.

### 2. A wrong number is worse than a missing one

A missing number prompts a question. A wrong number gets quoted in a review, defended, built
on, and discovered six months later by somebody who then distrusts everything else.

So the tool refuses to guess. When an adapter cannot observe what a KPI needs, the KPI comes
back **"Not measured"** with a sentence saying why — never a plausible zero.

This has a cost that is worth naming: a team on a weak tracker will see three of nine KPIs
unmeasured, and that looks worse than a full set. It is not worse. Six honest numbers beat
nine confident ones, and the gap tells you something true about the tracker.

The mechanism that makes this work is **capabilities**: every adapter declares what it could
actually observe, and the engine will not compute past that declaration. An adapter that
claims a capability it does not have is the most damaging bug in the system.

### 3. Nothing disagrees silently

If two places could say different things about the same number, either one is derived from
the other, or the difference is printed where a reader will see it.

This single rule produced most of the design:

- The sheet and PMS cannot disagree, because what reaches PMS is always regenerated from the
  current inputs — never typed separately.
- A hand-set value never replaces the computed one; both are kept, the reason is printed
  above the numbers, and the note itself says a person recorded a different figure.
- A target set for one project is marked, so nobody comparing two projects mistakes a local
  bar for the company default.
- A local rule override is printed before the values, not in a footnote.
- Every push is read back and compared.

The failure this prevents is not a crash. It is the quiet variety: a workbook saying "Met"
while PMS says "Not met", discovered by the one person who has to explain it.

### 4. A refusal must name the alternative

Refusing something without saying where it should go does not prevent the behaviour — it
moves it somewhere you cannot see. Refuse to let someone set a target in their profile and
they will change it in PMS afterwards without telling anyone. Refuse to let someone correct a
figure and they will edit it in PMS by hand.

Local review targets are allowed with a reason and a visible source label. They never
silently change PMS targets; reconcile them before submission. Every refusal points at
the supported route in the same sentence. "Set it on
this project in PMS instead." "Put it in 'Set value by hand' with a reason."

If you add a restriction and cannot name the alternative, you have not finished designing it.

### 5. Contracts at the boundary, not branches in the middle

The obvious way to support a second tracker is a branch. Two branches later, nobody can change
the KPI logic without regression-testing five integrations, and each new tracker makes the
next one harder.

Instead there is one interchange format in the middle. An adapter's only job is to produce it.
Everything downstream — the nine KPIs, the note wording, the workbook, the dry run, the push,
the audit trail — is written once and behaves identically no matter where the data came from.

Adapters should stay small and slightly boring. When you find yourself putting KPI logic,
note wording or spreadsheet code in one, it belongs somewhere else.

### 6. Meet people where they already work

Adoption is not a training problem. It is a *don't make me move* problem.

Nobody has to change tracker, learn a query language, or maintain a new system. The
configuration has a spreadsheet face because project leads live in spreadsheets. The tracker
workbook is editable because reviewing in a sheet is how people actually review. The tool
reads the board, the chat, the plan that already exist.

Corollary: when a team's tool is not supported, the answer is "export a CSV and start this
afternoon", not "wait for an integration". Being useful immediately beats being elegant later.

The same goes for signing in. A tool that offers one way in - "create a token and paste it
into a terminal" - loses everybody who would rather click Allow in the browser they already
have open, and everybody whose workspace forbids tokens. So every route is supported, the tool
works out which is best on this machine and says why, and the person chooses. The one thing
that does not vary is that a secret never passes through the assistant.

### 7. Detect, then confirm — never ask what you can read

Setup is an interview, not a form. Nearly everything in a profile can be discovered by
looking at somebody's board: the columns, the key format, the defect convention, the cards
that are obviously not deliverables.

So the tool looks first and presents what it found as statements to correct. A question you
could have answered by reading their tracker is a question you should not have asked.

Reserve the asking for what is genuinely unknowable from outside: which of two plausible
states really means "delivered", what the team actually commits to and to whom, whether a
date was agreed or assumed, what should happen at the end.

### 8. Evidence or it does not go in

Every judgement carries a link to the thing that justifies it — a comment, a status change,
a chat message, a row in the plan.

This is what makes a number survive being questioned three months later. It is also what
makes the tool honest with itself: a rule that cannot point at evidence is a rule that was
guessing.

### 9. Generated text is read as English, by a person, before anyone sees it

**Must have: every PMS note must make sense to a decision maker who knows nothing about
the project.** State the result and what was measured, explain the work and events that
matter, and describe the effect on delivery and any agreed decision. Explain local workflow
terms before relying on them. A ticket number, a status name, or a technically correct ratio
is not an explanation. Where the evidence cannot establish a cause, say so; do not invent
one. This applies to met and unmeasured KPIs as well as missed targets.

Every generated note goes through the assistant's evidence-based clarity review. The tool
records that review and asks again when its facts, wording or explanation change. Company
and client vocabulary is configurable, but readability and factual accuracy are mandatory.

Notes are read by management. A note that says "1 observations" tells the reader that nobody
is looking at the output — and once they believe that, they stop trusting the numbers too.

So the tool writes whole sentences rather than joined fragments, and spends real effort on
plural agreement, on saying the basis in words rather than as a bracketed tag, on not repeating a count the sheet already printed, on an open period
saying plainly what is still pending. The self-test asserts this. It looks like fussiness and
it is not: it is the difference between a report that gets read and one that gets skimmed.

### 10. Put the friction where the stakes are

Most of the tool is deliberately frictionless. A few places are deliberately not:

- Nothing reaches PMS without a person saying yes, and approval does not carry between runs.
- A hand-set value requires a written reason.
- Changing a counting rule is a conversation, not a commit, because it moves every project's
  numbers at once.

Friction in the right place is a feature. The test for whether it is in the right place: does
the cost of getting this wrong fall on somebody other than the person doing it? If yes, slow
it down.

### 11. The assistant is the brain, not the plumbing

This tool is driven by an assistant, and an assistant can do two very different kinds of
work. It can **judge**: read a card and decide whether the client had to explain the
requirement. Or it can **carry**: page through a board, paste a spreadsheet into its context,
reshape JSON, format cells. It is good at the first and expensive, slow and inconsistent at
the second — and because it *can* do the second, a tool that leaves a gap will find the
assistant quietly filling it, differently every time.

So the line is drawn in the code, not in the instructions:

- **Scripts move data.** The board, the sources and the sheet go API to disk to API. Nothing
  bulky ever passes through a conversation.
- **The assistant judges** — only what the rules were unsure of, all at once, from one file
  that carries the context and the definitions, answered into one file.
- **A person decides** what nobody can know from outside, once, and it is remembered.

And every judgement is **held still**: made once, stored with who made it and why, reused
until the card changes. A person outranks an assistant, which outranks a rule. That is
commitment 1 applied to the assistant itself — the judgement must not vary with who, or
what, happened to be running the tool that day.

The test for a new feature: *does this make the assistant carry something?* If yes, write the
script instead.

### 12. Rules propose; they do not get the last word

A literal rule is correct right up to the day somebody types `[Exisiting]`. Then a bug that
was already in the product is counted against the team, and nobody decided that it should
be — the regex did exactly what it was told.

People mistype, abbreviate and improvise, and the tool is reading what people wrote. So rules
read tolerantly, say how sure they are, and **say so on the row** when they were not sure:
"read [Exisiting] as Existing". What a rule cannot settle goes to the assistant, by a fixed
rubric; what the assistant cannot settle goes to a person. Nothing tolerant is ever silent,
which is what keeps tolerance from turning into guessing (commitment 2).

---

## How to decide something this document does not cover

In rough order of priority:

1. **Would it let two leads get different numbers for the same situation?** Then it is fixed,
   or it is printed.
2. **Could it produce a number that is plausible and wrong?** Then it must degrade to "Not
   measured" with a reason instead.
3. **Could two places end up saying different things?** Then derive one from the other, or
   print the difference.
4. **Does it ask somebody to change how they work?** Then find the version that does not.
5. **Is the restriction actionable?** Name the alternative in the same breath.
6. **Will the person who has to defend the number be able to?** If not, the design is not done.

---

## What was got wrong, and what it taught

**Thresholds were treated as company-fixed.** An early version refused to let anyone change a
KPI target, on the reasoning that comparability required one bar for everyone. That was
wrong: targets are configurable per project in PMS, and rightly so — an integration over a
legacy surface should not be held to a greenfield defect rate.

The correction was not just to allow it. It was to notice that *comparability lives in the
counting, not in the bar*. A Defect Rate of 12% has to **mean** the same thing everywhere;
whether 12% is good news can reasonably differ. Reading the targets from PMS per project, and
marking any that a project sets for itself, gives both.

The general lesson, and it is the reason this section exists: **when a rule feels principled,
check whether it is actually protecting the thing you think it is.** The rule felt like it was
protecting comparability. It was protecting uniformity, which is not the same and is not
valuable.

**Delivery Commitment was read as "delivered to QA".** The name suggests delivery, so an
early version counted every deliverable against a date, with "delivered" hardcoded to mean
reaching QA. The PMS definition says something different: *"team-negotiated commitments that
were delivered on time"*, formula *task count delivered on time / total team-committed task
count*, insight *reliability of the team*.

Two errors in one sentence. The denominator is the items the team **committed to**, not every
deliverable — counting the whole backlog turns a measure of promises kept into a measure of
how much work happened to finish. And "delivered on time" means whatever the team promised to
deliver, which is not always to QA.

The lesson is commitment 1 turned back on itself: **read the definition from the system of
record, not the one the name suggests.** "Delivery Commitment" sounds like it is about
delivery. It is about commitment; the meaning was in the second word. Where a definition
exists somewhere authoritative, go and read it, and put the words in the code where the next
person will see them.

**The slow part was not the code.** A real run took over half an hour, and the reflex was to
look at the Python. That was the wrong place: the whole chain — preflight, extract, validate,
compute, workbook, payloads — takes about a quarter of a second. Nothing in it needed
optimising, and any time spent making it faster would have bought nothing.

The time went on two things the code had shaped without anybody deciding to. The pipeline was
seven separate commands, so it was seven round trips with a decision between each. And
evidence was gathered *before* anything computed, which means searching chat, mail and plan
documents across a space with no edges for facts the board very likely already held.

Both fixes were about order and shape rather than speed. One command runs the chain. It ends
by printing what the tracker could not answer, naming the tickets — so the search that
follows is a list somebody can finish rather than a sweep with no natural end. And the list is
filtered by what would actually move a number: an item nobody committed to does not appear on
it, because under the real definition of Delivery Commitment a blank there is the correct
answer, not a gap.

The lesson: **measure before optimising, and when the measurement says the code is not the
problem, believe it.** Slowness in a tool that talks to a person is usually the shape of the
conversation, not the execution time — how many turns it takes, and whether it asks for things
before it knows it needs them. Those do not appear in a profiler.

**The assistant was the pipeline.** After the fix above, a real run *still* took over half an
hour, and the sheet it produced did not look like the hand-built one it was meant to replace.
The reason was embarrassing once seen: the Asana adapter never read Asana. It converted the
output of an extractor the repository did not ship. So on every run the assistant wrote a
scraper, ran it in a browser tab, carried fifty kilobytes of JSON back through the chat,
read the plan and two spreadsheets the same way, judged every card by hand, wrote helper
scripts beside the profile to enrich and reshape the result, and then built a spreadsheet.
The profile described a pipeline — sources, scan limits, a Google Sheets destination — that
no code implemented. The assistant *was* the pipeline, and a different one each time: the
same board came out as 53 deliverables one week and 41 the next.

One of those improvised scrapers matched `/\[Existing/`, and a bug tagged `[Exisiting]` was
counted against the team.

The fix was commitments 11 and 12: a real reader (API to disk, cached by `modified_at`), a
real source layer (fetched only when changed, read through a mapping or digested once), one
classifier for every tracker (tolerant, and visible when it was tolerant), a ledger that
keeps every judgement, a single file for the calls that need a brain, and a sheet written
by the tool — locally and as a Google Sheet updated in place — from one description that
mirrors the hand-built one.

The lesson: **when a tool is driven by an assistant, every gap in the tool is filled by
improvisation, and improvisation is slow and unrepeatable.** "The assistant can do that" is
not a design. Ask what the assistant would have to *carry*, and write that part down as code.

**The sheet was treated as a report.** The first workbooks were static: numbers computed in
Python and pasted into cells. The hand-built tracker they replaced was alive — grey cells
were formulas, so changing a yellow cell moved the KPI, the dashboard and the PMS note at
once — and that, as much as the formatting, was why people trusted it. The sheet is the
product, not a by-product of the run. It is now described once and written twice (xlsx and
Google Sheets), with live formulas that mirror the engine's rules; the engine's own figure
sits beside each live one, so an edit made after the run is visible instead of being a
second, silent number (commitment 3).

**Computed cells were made read-only.** The first version of the editable workbook forbade
changing a computed figure at all. Also wrong, for the reason in commitment 4: someone who
cannot correct a number in the sheet will correct it in PMS, where nobody can see they did.
Allowing it, requiring a reason, and printing both figures is strictly better than a
prohibition that gets routed around.

---

## What this project is not

**Not a measurement of people.** It measures delivery against agreed dates. Notes describe
tasks; effort overruns name the work, not who did it. Nothing produces a per-person figure,
and nothing should. If a feature request would make it possible to rank individuals, that is
a reason to decline it, not a requirement to satisfy.

**Not a replacement for judgement.** It concentrates a lead's attention on the handful of
calls that genuinely need a person, and does the rest the same way every time. A run that
needs no human review has probably hidden something.

**Not a second project-management system.** It serves many teams through the trackers and
spreadsheets they already maintain. Start with a small profile; expose advanced settings only
when a team's workflow needs them. Examples and published material use fictional organizations.

### Recovery is part of a successful run

Never replace a review sheet whose edits could not be read. Offline output is a separate
preview when the authoritative sheet is remote. A failed publish preserves the remote sheet's
identity and comparison baseline. Corrupt memory stops with a recovery instruction; it never
silently becomes an empty ledger. Use one resolved KPI registry for calculations and output.

An assistant's undecidable answer becomes a remembered question for the person. Unresolved
judgements and stale sources remain visible and prevent an unattended-looking final result.
Preparing a scheduled draft is supported; a configuration flag is never approval to send it.

---

## For whoever maintains this next

The tests are the specification. `scripts/selftest.py` asserts the behaviour these
commitments require — that unmeasurable things come back unmeasured, that a refusal names its
alternative, that one client's run cannot read another client's chat, that no generated note
says "1 observations", that a mistyped tag is read and *says* it was, that an assistant
cannot overrule a person, that every live formula in the sheet gives the engine's number. If
you change something and a test fails, read the test before
changing it: it is probably encoding a decision from this document.

Where a rule has a reason, the reason is in the code next to it. That is deliberate — a rule
with its reasoning attached survives being edited by somebody who was not there when it was
made. When you add one, write the why.

And keep this document honest. If a decision here stops being true, change it here first.
