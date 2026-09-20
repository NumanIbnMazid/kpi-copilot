# Start here

Tell your assistant which project you want to measure, where its tracker lives, and whether
you want a local workbook or a Google Sheet. You do not need to learn the commands below;
they are the assistant's repeatable route.

## 1. Choose a runtime

Use any assistant with command/file access to this repository. For an assistant that supports
local MCP, use the [MCP connection](03-Prerequisites.md). A browser assistant with a code
workspace can use exports and the same Python scripts. A chat without execution or a runtime
connection can review results but cannot run the pipeline.

Install the core dependencies once:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Use this environment's Python for the commands below. The CLI supports Python 3.9+; the
optional MCP bridge requires Python 3.10+.

## 2. Start small

Keep your profile outside the repository. From `plugin/kpi-copilot`:

```bash
python scripts/profile_tool.py init --out /private/kpi/profile.yaml
```

This creates a short starting profile. The assistant fills in the tracker, project reference,
what delivered and closed mean, the estimation unit, and your defect convention. It presents
those choices for correction. Use `--full` only when you want the advanced template.

For several projects, add rows under `projects`. Put shared client settings under `accounts`
only when that avoids repetition. An override contains only what differs.

The project may use hours, points, release cycles, sprints or months. Define actual periods
on the workbook's **Periods** tab or in `<project>/facts/periods.yaml`. Without periods the
first draft uses **Full Project** and asks for them. It does not invent sprint dates.

## 3. Connect only what is needed

```bash
python scripts/kpi.py auth --profile /private/kpi/profile.yaml --project my-project
```

The assistant explains the available choices: an existing login, browser sign-in, a token
you enter privately in a terminal, or a signed-in-tab export where supported. You choose;
the assistant never takes a secret in chat or accepts an OAuth consent on your behalf.

Google is needed only for Drive sources or live Sheets output. PMS access is needed for
refreshing authoritative definitions or approved delivery, not for trying an offline draft.

```bash
python scripts/kpi.py doctor --profile /private/kpi/profile.yaml --project my-project
```

## 4. Name the sources and destination

Start with the tracker. Add a plan, estimates or timeline only if they supply facts absent
from the tracker. The assistant maps tabular columns once. A PDF is digested once and checked
against its source fingerprint on later runs. Chat and mail remain opt-in.

For Google Sheets, set `output.workbook: google-sheets` and either `workbook_file` to a
**dedicated generated tracker** or `workbook_location` to a Drive folder. Do not point it at
your reference workbook or original project tracker: generated tabs are replaced after edits
are read back. Keep an existing manual workbook as a read-only reference during setup.

Without Google access, use exported source files and local `.xlsx` output. A later offline
run on an established remote tracker produces a separate preview and preserves its link.

## 5. Prepare, review, decide

```bash
python scripts/kpi.py run --profile /private/kpi/profile.yaml --project my-project
```

Follow **NEXT**. The assistant reads and answers one judgement queue; a person gets one
message containing the questions that remain. A missed KPI needs a factual explanation,
not a guessed cause. You can answer or correct judgements in the yellow cells.

```bash
python scripts/kpi.py judge --profile /private/kpi/profile.yaml --project my-project
python scripts/kpi.py push --profile /private/kpi/profile.yaml --project my-project
```

The final command previews delivery. After you approve those values and notes in the current
conversation, the assistant may add `--apply`. If inputs or the sheet changed, it must refresh
and show you the new result. Scheduled runs prepare drafts; they do not inherit approval.

The [fictional example](../README.md#try-the-fictional-example) is the quickest way to see the
whole flow before connecting a real project.
