# Start here

Install, configure, run, update. Everything you need to be producing real KPIs, in order,
with links out when you want more depth.

About an hour end to end, most of it answering questions about your own board.

---

## Step 1 — Install (5 minutes)

There is no public marketplace and none is needed. The shared project folder **is** a private
marketplace.

```bash
claude plugin marketplace add "/path/to/KPI Copilot"
claude plugin install kpi-copilot@pm-tools
```

Then `/reload-plugins`, or restart Claude.

<details>
<summary>Other ways in</summary>

**Try it without installing** — good for a first look:

```bash
claude --plugin-dir "/path/to/KPI Copilot/plugin/kpi-copilot"
```

**Auto-load for just you** — copy the plugin folder to `~/.claude/skills/kpi-copilot/` and it
loads every session with no marketplace and no flag.

`claude plugin install kpi-copilot` on its own will **not** work — that form only resolves
against a marketplace you have already added.

</details>

Python 3.9+ and three libraries:

```bash
pip3 install pyyaml openpyxl jsonschema
```

## Step 2 — Check you are ready (10 minutes)

```
/kpi-copilot:kpi-setup
```

The first thing it does is a readiness check, grouped as **blocked / needs your confirmation
/ limited / ready**. For anything blocked it tells you the fix and **who owns it** — several
are things only a PMS admin can do, and it is much better to find that out now.

Two items are usually the slow ones, so start them today:

- **PMS project access**, and edit rights if you will push.
- **A Claude Code seat**, if the company manages them.

If something is blocked, **keep going anyway**. Setup finishes in review-only mode and tells
you what unlocks when the block clears.

→ Full list of what is checked: [03-Prerequisites.md](03-Prerequisites.md)

## Step 3 — Answer the interview (20 minutes)

Claude asks four or five things it genuinely cannot see, then goes and reads your board and
shows you what it found as statements to correct:

> - Your columns: Backlog, In Progress, **In Test**, Testing Failed, **Done**.
> - **Delivered** = the first time an item reaches *In Test*.
> - **Defects** = issue type *Bug*; *Improvement* is reported but not counted.
> - **Not deliverables**: 4 cards titled "Sprint Goal" or "QA Checklist".

Correct what is wrong. That conversation *is* the setup.

The questions worth thinking about before you start:

| Question | Why it matters |
|---|---|
| How many clients and projects, and is the tracker the same for all? | Decides whether you need accounts. One profile covers all of them |
| Which state really means "delivered"? | Velocity and Delivery Commitment both hang off it |
| **What does your team commit to, and what counts as keeping the promise?** | Delivery Commitment measures reliability of promises, so it counts only items with a commitment |
| Hours or story points? | Velocity's unit |
| What happens at the end — you type it into PMS, or it pushes after you approve? | Can differ per client |

You end up with two files: `profile.yaml`, which the tools read, and a **KPI Profile
Workbook**, the same thing laid out for a human. Edit whichever you prefer; they convert both
ways and cannot drift.

## Step 4 — Configure the parts that matter

Most of it is filled in for you. These four are worth looking at yourself.

### The Tools tab — where everything lives

One row per place your projects' truth is kept. This is the tab people actually open, and the
fastest explanation of a project that exists.

```yaml
tools:
  - id: chat-devqa
    kind: chat
    name: Northwind Dev-QA (Google Chat)
    url_or_id: AAAAexampleDevQA
    description: "Builds, QA rounds, environment problems. Best source for when something was delivered."
    used_for: [evidence, handover]
    accounts: [northwind]
    client_facing: false
    access: Google SSO
    note: "Internal. Nothing agreed here counts as a client commitment."

  - id: slack-acme
    kind: chat
    name: "#acme-delivery (Slack)"
    url_or_id: C07ACMEDEL
    description: "Where builds are announced. Best evidence for handover dates."
    used_for: [evidence, handover]
    accounts: [acme]
    people: [Client PM, A. Rahman]
    client_facing: true
    access: Slack SSO
```

`client_facing` and `people` matter more than they look: a client-facing space is where
agreed dates get set and where a client-found defect first appears. Getting it wrong is how a
date somebody agreed in a client call gets treated as an internal decision.

→ Every field, and every kind of tool: [reference/01-tools.md](reference/01-tools.md)

### The Workflow tab — what your states mean

The single most important section. It is what turns "a column called In Test" into a number
comparable across the company.

→ [reference/04-workflow.md](reference/04-workflow.md)

### Output — what happens at the end

```yaml
output:
  mode: assisted-push          # review-only | dry-run | assisted-push | auto-push
  workbook: google-sheets      # or xlsx
  workbook_location: <Drive folder id, or a local folder>
```

Most people want `assisted-push`. Start with `review-only` for a cycle or two if you would
rather watch it first.

→ Where files go, and every mode: [reference/07-output-and-files.md](reference/07-output-and-files.md)

### Accounts — only if you have more than one client

One profile covers several clients on several trackers. Say what is true for a client once,
and every project on it inherits.

→ [reference/02-accounts-and-projects.md](reference/02-accounts-and-projects.md)

## Step 5 — Prove it on a period you already know

Pick your most recently finished milestone or sprint — one where you already know roughly
what the answer should be.

```
/kpi-copilot:kpi-run <your project>
```

or, without the assistant in the loop:

```bash
python3 scripts/run.py --profile profile.yaml --project <id>
```

Either way you get, in under a second: the nine KPIs, the notes, a workbook, and a short list
of the facts the tracker could not answer — with the ticket numbers beside each. Then the only
question that matters:

**Does anything here disagree with what you know to be true?**

When something is off it is nearly always one of four things: the delivered-when mapping, an
exclusion pattern eating real work, a date level, or the hours source. Say what looks wrong;
Claude fixes the profile and reruns. **Two or three rounds is normal** and does not mean
anything is broken.

→ When a number looks wrong: `skills/kpi-run/references/troubleshooting.md`

## Step 6 — From now on

One command per cycle:

```
/kpi-copilot:kpi-run <project>
```

Three commands if you would rather drive it yourself:

```bash
python3 scripts/run.py        --profile profile.yaml --project <id>
python3 scripts/run.py review --profile profile.yaml --project <id> --by "Your Name"
python3 scripts/run.py push   --profile profile.yaml --project <id> --apply
```

Review in chat, or in the sheet — yellow cells come back, grey ones are computed, white ones
were read from your tracker.

→ [04-Daily-Use.md](04-Daily-Use.md)

---

## Updating

An installed plugin is a **copy**, so changes to the shared folder reach you only when the
version is bumped. When someone says there is a new version:

```bash
claude plugin marketplace update pm-tools
claude plugin update kpi-copilot@pm-tools
```

Then `/reload-plugins`.

If you are the one making changes, `scripts/release.py --patch` runs the self-test, bumps
both manifests and prints what everyone else runs.

→ [07-Extending.md](07-Extending.md#part-5-how-updates-reach-people)

---

## Where everything lives

Lost track of which file the tools actually read?

```bash
python3 scripts/where.py --profile /path/to/profile.yaml
```

It prints your profile, workbook, readiness checklist, reasons file, run folder, the KPI
definition cache and the plugin itself — each with whether it exists — then the exact commands
to change something.

→ [reference/07-output-and-files.md](reference/07-output-and-files.md)

---

## Changing something later

| You want to | Do this |
|---|---|
| Change a setting, in a spreadsheet | Edit the workbook, then `workbook.py read --xlsx <it> --out profile.yaml` |
| Change a setting, in text | Edit `profile.yaml`, then `profile_tool.py validate --profile profile.yaml` |
| Find out what a setting means | `profile_tool.py explain --key workflow.delivered_when` |
| See what a project resolves to | `profile_lib.py --profile profile.yaml --list` |
| Add a client or a project | [reference/02-accounts-and-projects.md](reference/02-accounts-and-projects.md) |
| Add a tracker nobody supports | `/kpi-copilot:kpi-adapter` |
| Understand why it works this way | [00-Philosophy.md](00-Philosophy.md) |

---

## Where to go next

| You are | Read |
|---|---|
| Wanting the three-minute version | [01-Overview.md](01-Overview.md) |
| Using it week to week | [04-Daily-Use.md](04-Daily-Use.md) |
| Customising something unusual | [05-Adapting-To-Your-Workflow.md](05-Adapting-To-Your-Workflow.md) |
| Looking up a specific field | [reference/](reference/) |
| Maintaining or extending it | [00-Philosophy.md](00-Philosophy.md), then [06-Architecture.md](06-Architecture.md) |
| Stuck | [09-FAQ.md](09-FAQ.md) |
