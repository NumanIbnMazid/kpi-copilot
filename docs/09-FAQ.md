# Frequently asked questions

[Documentation](README.md) · [Start here](02-Start-Here.md) · [Troubleshooting](14-Troubleshooting.md)

## Is this a plugin or a skill? Do I need to clone it?

It is a Python tool with three assistant skills, packaged as a Claude Code plugin and
available as a repository. A local coding assistant can use a clone or ZIP directly. The
Claude Code plugin installer downloads its own copy, so manual cloning is unnecessary for
that route. Both need Python dependencies. See [installation](12-Installation.md).

## Does it require Claude, Codex, Cursor, or a particular subscription?

No single vendor is required by the engine. Your chosen assistant needs permission to run
commands or call the local MCP server. Client features, subscriptions and organization
policies determine that access; installing KPI Copilot does not grant it.

## Can I use plain browser chat?

Only a session with a compatible code/file workspace or an appropriate connected runtime can
execute it. Ordinary chat can discuss a workbook. The shipped MCP server is local stdio;
there is no hosted service. See [assistant connections](13-Assistant-Connections.md).

## Can I see examples before connecting real accounts?

Yes. Download the [fictional profile and KPI workbooks](../samples/README.md). The sample
workspace shows client/project folders, source files and the settings that produce them.
All example work data and operational links are fictional.

## Which trackers work?

Asana, Jira Cloud/Server/Data Center and GitHub Issues/Projects have API readers. Other
trackers can start with CSV. The available fields and evidence determine which measures can
be calculated; a CSV does not guarantee six—or any fixed count—of the nine KPIs.

## Will it modify my tracker or search my entire chat history?

Tracker adapters are read-only. Normal runs read the configured tracker and named plan,
estimates and timeline sources. Chat/mail follow-up needs explicit scope and is limited to
unresolved questions. Merely listing a chat in the profile does not trigger a search.

## Can one profile cover different clients and trackers?

Yes. Settings resolve from profile defaults, then account overrides, then project overrides.
Alternatively, keep a separate profile in each client folder, as the samples do. Project
folders are created beside their profile; the account field alone does not create a nested
client folder. See [accounts and projects](reference/02-accounts-and-projects.md).

## Where are my settings, and can I edit them in Excel?

The runner uses the `profile.yaml` path you supply. The optional **KPI Profile Workbook** is
an editable representation of those settings. Ask the assistant to import it with
`workbook.py read`, validate the result and rebuild the companion workbook. It is not a
live synchronized file. The **KPI Tracker** is a different workbook for reviewing results.

## Do I need Google, PMS, a plan, or an estimates sheet?

No, not for a local tracker/export-based review. Add sources that your workflow requires.
A configured source that becomes missing or stale must be repaired or explicitly removed;
it must not silently disappear from the evidence used for submission.

## Why does a KPI say Not measured?

Its required evidence is missing or no eligible population exists. Read the reason and
Open Questions. For example, an exported Done state may not establish the date a commitment
was fulfilled, and no handover date may prevent release-based measures. Do not replace
missing evidence with zero. See [KPI definitions](01-Overview.md).

## What if a number looks wrong?

Review the register rows, delivery mapping, estimate source, date hierarchy, exclusions and
rework boundary. Correct the inputs and refresh. For an exceptional manual value, use
**Set value by hand** with **Why set by hand**; the computed number stays visible too.

## What if an existing bug is misspelled as “Exisiting”?

Tolerant classification can recognize configured vocabulary, and records that interpretation
for review. Uncertain calls go to the assistant with a rubric; insufficient evidence goes to
a person. You can correct the judgement in a yellow cell or through the assistant.

## Does “closed” always mean delivered?

No. Configure the event your team actually promised. Delivery may mean QA handoff, final
acceptance or client handover. Closure may be the same event or a later one. Rework uses a
closure boundary followed by reopening; ordinary first-round testing is not automatically
rework. See [workflow fields](reference/04-workflow.md).

## Can targets differ between projects?

Yes. Official targets come from the project's PMS registry after refresh. A local review
target also works when it has a value and reason; it is labelled and blocks PMS submission
until reconciled. Do not change formulas to reach a target.

## Do edits in the KPI sheet survive a refresh?

Supported yellow-cell edits do. The tool reads them before rebuilding. Grey formula cells
are regenerated. Google review edits are authoritative when Google is configured; a failed
read is not permission to use an older local copy. Finish editing before the refresh.

## Can I keep one Google Sheet link?

Yes. Configure a dedicated file or Drive folder and connect Google with edit rights. Later
runs reuse the output sheet. If publishing fails, follow the warning and preserve the review
baseline; do not replace the spreadsheet manually. See [output settings](reference/07-output-and-files.md).

## Will it send KPIs or messages without asking?

PMS submission needs explicit approval of the current preview in the conversation, including
with legacy automatic settings. The Python runner does not post messages merely because
`output.notify` is set. Any assistant messaging integration needs explicit authorization.

## Can it run on a schedule?

A compatible host or operating-system scheduler can prepare drafts with appropriate
credentials. It cannot provide the conversation approval for PMS submission. Keep one writer
per profile and review a fresh preview before sending.

## Why can a run take longer than a few seconds?

First reads, board size, provider limits, changed documents, assistant review and user answers
all affect elapsed time. Printed processing timings cover only the command. The samples are
small offline examples, not performance guarantees for a live project.

## What happens if PMS is unavailable?

Local calculation can use cached or bundled definitions with the relevant source label.
Submission stops if access or required verification fails. Restore access, refresh the
preview and approve the current result; do not blindly resend an old payload.

## Can I use a completed project or explain an old result?

Yes, if the necessary records remain available. The workbook shows populations, evidence and
notes; the saved judgement ledger records reasons. Daily run folders keep working snapshots,
but same-day reruns can replace them. Preserve separate reviewed snapshots under your
retention policy if you need an immutable record.

## How is the tool checked?

The [contributor guide](07-Extending.md#validation) gives the self-test and MCP protocol
checks. They include calculations, formula parity, missing-data behavior and refusal paths.
The [audit](11-Audit.md) records historical validation and outstanding live acceptance.
Passing local tests is not proof of successful installation or live writes in every client.
