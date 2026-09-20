---
name: kpi-setup
description: "Set up or change a person's KPI Copilot profile: check that every prerequisite is in place, look at their actual issue tracker and working files, propose how their workflow maps onto the nine PMS KPIs, and write the profile and the KPI Profile Workbook. Use this whenever someone is starting with KPI Copilot for the first time, onboarding onto a new project or account, switching issue tracker, changing how results reach PMS, changing where the KPI sheet lives (a local file, a Google Drive folder or a specific Google Sheet), naming which sources a run may read, connecting Asana or Google, seeing 'Not measured' on KPIs they expected numbers for, or asking what they need before they can run KPIs. Also use it when someone asks to check prerequisites, run the readiness check, or fix a blocked check."
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, WebFetch, AskUserQuestion
---

# Set up one working project

The outcome is a reviewed first run, not a large configuration form. Locate the plugin root
containing `scripts/kpi.py`; use the configured Python runtime or optional MCP connection.
No specific AI vendor is required. See the repository's `docs/03-Prerequisites.md` for host
capabilities and connection setup.

## Learn enough to propose

Ask together for the tracker/board, one project, reporting period, hours or story points,
source documents (if any), and review destination. Default to a local workbook and
`review-only`. Use existing context rather than asking again. Add other projects afterwards.

Run `profile_tool.py init --out <private-folder>/profile.yaml` for the minimal template.
Use `--full` only when the extra settings help. Configure the tracker, project and available
workflow facts, then run `kpi.py auth --profile … --project …`. Present the printed sign-in
choices; the person handles consent and secrets. `kpi.py doctor` checks the connection.
Never ask for a token in chat or test PMS access by writing a value.

Use the supported adapter to read the board to disk; the first run and judgement queue
provide the relevant evidence. Do not inspect the tracker card by card or scrape pages.
Propose delivery/closed/reopened states, defect exclusions and period grouping. Ask only
about ambiguity: what counts as delivery, which promises are commitments, and which dates
were actually agreed. Validate a proposal with the person before treating it as policy.

## Keep configuration understandable

One profile can cover many accounts and projects. Put shared settings at the top and only
differences in account/project overrides. Use `profile_lib.py --profile … --list` to show
resolved projects. `profile_tool.py validate --profile …` checks the result.

Configure only named sources: plan, estimates and timeline. Tables need column mappings;
a PDF is digested once when NEXT asks, following `../kpi-run/references/facts.md`.
Record agreed period facts under the project. Missing evidence means Not measured or an
Open Question. Do not search mail/chat without explicit scope from the person.

Use `policy` for which defect categories count, `workflow` for the team's status meanings,
and `rule_overrides` with a why for supported exceptions. Targets normally come from the
project's PMS registry. Local `targets.<kpi>.value` plus `why` are supported for review and
clearly labelled; they block PMS submission until reconciled. Do not change formulas to
make results look better. Detailed options are in `docs/05-Adapting-To-Your-Workflow.md`.

If wanted, `workbook.py build` creates an editable Profile Workbook; `workbook.py read`
imports it back. It is optional. Users normally need only their profile and review workbook.
For Google, configure a dedicated output file/folder, not the supplied manual reference.
Use a stable project-level workbook name, without a reporting period. Save `workbook_file`
after the first successful publication and keep it for every later period. Separate clients
should have separate private profile folders unless the person explicitly wants one shared
multi-account profile. A new reporting period is a row in the project history, not a new
profile, project, or workbook.

## Prove the setup

Run `kpi.py run --profile … --project …` for a completed period in review-only mode.
Follow the kpi-run skill: judge one queue, ask remaining person questions together, rerun.
Show the workbook and all nine results with missing-data reasons. Ask what disagrees with
known outcomes; correct the input or mapping and recompute. Do not declare setup validated
until the user has reviewed that comparison.

Hand over the profile/workbook locations, how to request the next run, and any connection
or evidence limits. Persistent preferences can be recorded with `remember.py` and a why
when requested; otherwise offer before saving. PMS writes always need explicit approval
in the current conversation, including legacy automatic modes.

For deeper examples see `references/worked-example.md`; consult `references/discovery.md`
for mapping concepts, using API-to-disk evidence rather than manual card inspection.
