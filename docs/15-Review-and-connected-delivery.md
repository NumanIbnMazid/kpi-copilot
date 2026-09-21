# Review notes and connected delivery

[Documentation](README.md) · [Daily use](04-Daily-Use.md) · [Assistant connections](13-Assistant-Connections.md)

This technical companion explains review preservation and delivery. Start with Daily use
if you only want to prepare and approve a workbook.

The KPI Summary has two editable yellow fields: **Result summary** and **Why / context**.
The combined note is the text sent to PMS. Edits survive refreshes, including an intentional
blank. An edited summary that no longer matches its measurement basis is retained for
review; that KPI is not overwritten in PMS until the wording has been reconciled.

PMS notes describe outcomes, their scope and supported explanations. Missing inputs,
measurement diagnostics and requests for clarification belong in **Open Questions**.
Unmeasured values remain blank, never zero. Real delivery delays, defects, exclusions and
PMS numeric limits remain visible in the result; note cleanup must not change their meaning.
The assistant still reviews every changed complete narrative: phrase matching is a safety
net, not a substitute for judgment.

Every push reads the configured review sheet again. When Google Sheets is configured, its
current edits are authoritative; the local preview cannot silently replace it. If access
fails, publication stops. With local output, the existing local workbook is read instead.
Changed inputs are recomputed and subjected to the same classification and note checks.

`kpi.py push --apply --create-periods` may create missing PMS periods only when the person
has authorized creation. Existing periods are resolved by exact name or saved ID, verified
against their project, and updated with a concurrency timestamp. Each write is read back.
Repeated runs keep the same Google Sheet and PMS period IDs. Only the nine managed KPI
fields are touched; unrelated KPIs are left alone. Previously published managed measures
that become unmeasured are explicitly cleared, not replaced with zero.

## Project-specific workflow settings

Use `workflow.reopened_when.closed_values` when the close boundary for rework differs from
final completion. For example, a project can count a return after QA handoff as rework while
`workflow.closed_when.values` still identifies finished QA for effort accounting. No client
or tracker has a hard-coded interpretation.

`periods.by_ancestor` maps a parent-container title pattern to a period before date-based
fallback. This supports overlapping milestone calendars. `sources.team_hours_when:
handover` counts the period's shared effort on recorded client handover rather than with
the first delivered item. Both settings are optional; existing defaults are unchanged.

## Connected-host transport

The normal OAuth/token routes remain supported. An assistant host may instead keep an
already-authorized connection in its own browser or Drive connector and use the reusable
file-backed transport. The pipeline still performs all pagination, caching, parsing,
classification, workbook generation and verification.

1. Create a private temporary directory outside the checkout. Put a `session.json` there
   with an explicit service allowlist (`asana`, `google`, `pms`) and a short Unix
   `expires_at` timestamp. Set `KPI_HOST_BRIDGE` to that directory for the process only.
2. For browser connections, load `scripts/browser_transport.mjs` in the host's supported
   browser runtime and pass selected CDP handles, their exact API origins, and the host
   filesystem capability to `drain`. Asana requests are read-only. PMS credentials remain
   inside the signed-in origin and are never written to the transport directory.
3. For connected Drive, load `scripts/google_transport.mjs`; pass each pending Google
   request to `respond` with the connected tool collection and an authenticated-download
   callback. The callback returns a file path inside the private session directory.
4. Service pending requests while the pipeline runs. Write each response atomically to
   the matching response filename. Never route a request after its expiry. Keep large
   source responses file-backed, not in the conversation.

The manifest does not authorize a write. The user's requested scope, profile mode, explicit
apply flag and ordinary review guards still apply. The host must honor its own consent and
browser policies. This route works while the assistant host is active; a background schedule
needs independently configured credentials. Do not commit session files or live evidence.
