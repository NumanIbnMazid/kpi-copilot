# Extending it, and how the skills are written

Two audiences: somebody adding a tracker, and somebody who has to edit the skills themselves.
The second half is a short guide to writing Claude skills properly, because that is the part
people usually have to look up.

---

## Part 1: adding a tracker

### First, decide whether you need to

Usually not, and saying so saves a week.

The `csv` adapter works with an export from any tracker. A native adapter buys exactly two
things: **status history** (which turns Delivery Commitment, Rework Rate and Task
Comprehension from "Not measured" into real numbers) and **no manual export step**.

A team running monthly who are content with six of nine KPIs should use `csv` and move on.

### If you do need one

```bash
cp -r adapters/csv adapters/<name>
```

Start from `csv`, not `jira` — it is the simplest complete example and already handles the
classification, the review list and the profile plumbing. A native adapter mostly replaces
"read a file" with "call an API".

Read `adapters/_contract.md`. The rules that matter:

- Emit valid KIF and nothing else. No KPI maths, no note wording, no spreadsheets.
- Declare `generated.capabilities` **honestly**. Claim `status_history` because you read it,
  not because the API has an endpoint for it.
- Unknown is `null`. Never a default, never a guess.
- Judgement calls go in `review[]`, each **with a proposal**.
- Excluded rows stay, with a reason.
- Read conventions and workflow states from the profile. A hardcoded column name is a bug.
- Read-only. Never write to the tracker.

Then:

```bash
python3 adapters/<name>/extract.py --profile <p> --project <id> --out /tmp/t.kif.json
python3 scripts/validate_kif.py --kif /tmp/t.kif.json
python3 scripts/kpi_engine.py --kif /tmp/t.kif.json --profile <p>
```

And the test that actually matters: run it against a period whose answer somebody already
knows, and sit with them while they read the nine numbers.

Add a case to `scripts/selftest.py`, write the README — especially the section on what the
adapter *cannot* see — and you are done.

`/kpi-copilot:kpi-adapter` walks all of this interactively.

### Things that bite

Estimate units (Jira returns seconds). Paging (a silently truncated board gives a confident,
wrong Velocity). "Complete" meaning merged on one board and accepted on another. Rate limits
— back off, do not fail. Time zones — an off-by-one on a milestone boundary moves a KPI and
is very hard to spot later.

---

## Part 2: changing a counting rule

`scripts/kpi_engine.py`, plus `skills/kpi-run/references/kpi-rules.md`, plus a self-test case.

And a conversation first. A counting rule change alters every project's numbers at once,
which is the whole reason the rules live in one place. That friction is intentional — it is
the difference between a shared standard and nine private ones.

Adding a KPI starts in PMS: add it there, refresh the registry, then teach the engine to
count it. Until the engine knows how, the registry flags it rather than dropping it.

---

## Part 3: how the skills are written

Three skills: `kpi-setup`, `kpi-run`, `kpi-adapter`. If you have not written one before, this
is the format.

### The anatomy

```
skills/<skill-name>/
├── SKILL.md            required
│   ├── YAML frontmatter
│   └── Markdown instructions
└── references/         loaded only when the skill points at them
```

```markdown
---
name: kpi-run
description: "Prepare, review and deliver PMS KPIs ... Use whenever someone asks to prepare,
  calculate, refresh, recompute, review or push KPIs, do the KPI run for a project or
  milestone or sprint or cycle, update PMS KPIs, or explain why a KPI value came out the way
  it did."
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion
---

# Instructions in Markdown
```

### Progressive disclosure — the thing to understand

Three levels, and they have different costs:

1. **Name and description** — always in context, for every conversation. Keep it tight.
2. **The SKILL.md body** — loaded whenever the skill triggers, and it stays there. Under 500
   lines.
3. **`references/*.md`** — loaded only when the body points at them. Effectively free until
   used.

So the body holds the workflow and the decisions. Everything deep — the counting rules, the
note style, the troubleshooting list — goes in `references/`, with a line in the body saying
when to read it. `kpi-run/SKILL.md` is about 120 lines; its references are four times that.

### Writing the description

This is the primary triggering mechanism, and skills are more often under-triggered than
over-triggered. Be a little pushy, and name the **phrases people actually use**, not the ones
you wish they used.

Weak:

> Prepares KPIs.

What is there now:

> Prepare, review and deliver Enosis PMS project KPIs for a project or period, from any issue
> tracker. ... Use whenever someone asks to prepare, calculate, refresh, recompute, review or
> push KPIs, do the KPI run for a project or milestone or sprint or cycle, update PMS KPIs, or
> explain why a KPI value came out the way it did.

`description` and `when_to_use` share a 1,536-character budget.

### Frontmatter worth knowing

| Field | Use |
|---|---|
| `name` | Invocation name. Plugin skills become `/plugin:name` |
| `description` | What it does **and when to use it**. The trigger |
| `allowed-tools` | Pre-approve tools for the turn. Grant clears on the next user message |
| `disable-model-invocation` | `true` = manual only |
| `context: fork` | Run in an isolated subagent |
| `model`, `effort` | Override for this skill |
| `metadata`, `license`, `compatibility` | Free-form; part of the Agent Skills spec |

Only `name`, `description`, `license`, `compatibility`, `metadata` and `allowed-tools` are
portable to claude.ai. The rest are Claude Code only — uploading with a non-spec field fails.

### Style

- **Imperative.** "Read the checklist back to them", not "the skill should read".
- **Explain why, sparingly.** A rule with a reason survives being edited by the next person;
  a wall of MUSTs does not. But do not narrate.
- **Give the shape of the output** where it matters. `kpi-setup` includes the exact form of
  the mapping proposal, because the phrasing is what makes the interview work.
- **Tables for decisions**, prose for judgement.
- Assume the reader is competent and in a hurry.

### Testing a skill

```bash
claude --plugin-dir ./plugin/kpi-copilot
/kpi-copilot:kpi-run
/reload-plugins        # after edits
```

Write three prompts a real person would actually type and check the skill triggers on all
three. Under-triggering is the usual failure, and it is invisible unless you test for it.

`claude plugin eval` runs a prompt set with and without the plugin, which is how you find out
whether it earns its context.

---

## Part 4: packaging

```
plugin/kpi-copilot/
├── .claude-plugin/plugin.json      name, description, version, author
├── skills/<name>/SKILL.md
├── scripts/   adapters/   schemas/   examples/
└── README.md
```

Only `plugin.json` goes inside `.claude-plugin/`. Everything else sits at the plugin root —
putting `skills/` inside `.claude-plugin/` is the most common packaging mistake.

Install:

```bash
claude --plugin-dir ./plugin/kpi-copilot     # development, no install
claude plugin validate ./plugin/kpi-copilot  # before sharing
```

**Distribution without a public marketplace.** `KPI Copilot/.claude-plugin/marketplace.json`
makes the project folder its own private marketplace, with `source: "./plugin/kpi-copilot"`.
Anyone with the folder — a shared drive, a clone of a private repo — adds it once:

```bash
claude plugin marketplace add "/path/to/KPI Copilot"
claude plugin install kpi-copilot@enosis
```

The same manifest works from a private git repo, so `claude plugin marketplace add
enosis/claude-plugins` works the day someone puts it there. Nothing needs to be public at any
point.

Bump `version` in **both** `plugin.json` and the marketplace entry when you want people to
receive an update; `claude plugin marketplace update` then `claude plugin update` pulls it.

---


## Part 5: how updates reach people

This catches everyone out once, so it is worth being blunt about it.

**Claude Code installs a plugin by copying it.** `claude plugin install kpi-copilot@enosis`
copies the folder to `~/.claude/plugins/cache/enosis/kpi-copilot/<version>/` and runs from
there. Editing the source folder afterwards changes nothing for anyone who installed it.

**The version is the only signal that there is something new.** Run `claude plugin update`
against an unchanged version and it replies *"already at the latest version"* and does
nothing — even though the files differ. Tested, not assumed.

**The version lives in two files and they must agree:**

| File | Field |
|---|---|
| `plugin/kpi-copilot/.claude-plugin/plugin.json` | `version` |
| `.claude-plugin/marketplace.json` | `plugins[].version` |

So releasing a change is:

```bash
python3 plugin/kpi-copilot/scripts/release.py --patch
```

That runs the self-test first, refuses to bump if it fails, updates both files, and prints
the two commands everyone else runs:

```bash
claude plugin marketplace update enosis
claude plugin update kpi-copilot@enosis
/reload-plugins        # or restart Claude
```

`release.py --check` reports the current state and whether the two manifests are in step.

### While you are iterating, do not version anything

```bash
claude --plugin-dir "/path/to/KPI Copilot/plugin/kpi-copilot"
```

This loads in place: no cache, no version, no install. Edit a skill, run `/reload-plugins`,
see the change. Use the release flow only when you want other people to get it.

### If the folder is a git repo

Same flow, one step earlier: they `git pull`, then run the two commands. The marketplace
source in `known_marketplaces.json` is a path, so pulling updates what the marketplace
points at. Moving the folder breaks that path — re-add the marketplace at the new location if
you do.

### What a person on an old version sees

Nothing alarming: their copy keeps working. The risk is quieter — they are scoring against
whatever counting rules their version has. When a counting rule changes, say so and ask
people to update, rather than assuming they will. That is another reason a rule change is a
decision, not a commit.

---

## Reference

- Agent Skills: https://code.claude.com/docs/en/skills
- Plugins: https://code.claude.com/docs/en/plugins
- Plugin reference: https://code.claude.com/docs/en/plugins-reference
- Marketplaces: https://code.claude.com/docs/en/plugin-marketplaces
