# Product audit — September 2026

The existing architecture is worth retaining: one Python pipeline, a private profile, a
review workbook, and a batch of unresolved decisions for the assistant. A separate app or
large hosted platform would add deployment and credential management before improving the
core experience. This revision adds a small optional local MCP interface and fixes concrete
reliability problems. It is a release candidate, not evidence that every live integration
has passed acceptance.

Work is tracked on the [repository-linked project board](https://github.com/users/NumanIbnMazid/projects/18).
Statuses are Todo, In Progress, Blocked, In Review and Done. Code awaiting review remains
In Review; external acceptance gaps remain open.

## Authoritative definitions and reference workbook

The supplied private workbook was inspected read-only for tab structure, configuration and
KPI definitions. The signed-in PMS interface displayed nine KPIs and their explanatory
tooltips. No private source records, organization names, project identifiers or screenshots
are copied here, and no production KPI was changed.

| KPI | Meaning verified in the PMS interface | Workflow mapping that needs agreement |
|---|---|---|
| Velocity | Work completed in a cycle | Hours or points, delivery event, whether QA effort is included |
| Task Comprehension | Tasks understood without client assistance / tasks | Evidence of clarification; treatment of unknowns |
| Client Expectation | Client-prioritized tasks delivered by expected date / client-expected tasks | Agreed date and delivery vs handover |
| Delivery Commitment | Team commitments delivered on time / team-committed tasks | Which tasks carry a commitment and what fulfills it |
| Defect Rate | Defects / tasks | Defect inclusion policy and task population |
| Escaped Defect Rate | Post-release defects / defects before and after release | Release boundary and which report categories count |
| Defect Rejection Rate | Rejected / reported defects | Rejection evidence and report population |
| Rework Rate | Tasks reopened after closure / completed tasks | Closure and reopening states |
| CR Rate | Tasks changing after cycle start / initial tasks | Initial scope and how approved additions are identified |

The engine normalizes these meanings into explicit workflow rules; a tooltip alone does
not settle every denominator. In the current counting model, Defect Rate applies the
observation/improvement/pre-existing policy and uses delivered work as its denominator.
Escaped Defect Rate uses non-rejected reports; Rejection Rate uses all reports. These
populations are visible in Config and the detailed rules, and must be reviewed during
onboarding rather than assumed equivalent to another team's policy. Unknown outcomes and
not-yet-due items are excluded from decided-outcome ratios and called out in notes.

The reference's useful layout is retained: Read Me, Dashboard, Config, Periods, task and
defect registers, KPI Summary and PMS Push Log. Open Questions and Run Log make unresolved
work visible. Navy headings, yellow inputs, grey formulas, frozen headers, evidence links,
validation and conditional colors remain part of both output models.

## Defects corrected

| Finding | Resulting behavior |
|---|---|
| Engine and sheet could use different target registries | One profile-relative registry feeds calculation and workbook; absent custom files fail explicitly |
| Configuration and inherited overrides were not consistently validated | Validate before running; minimal profile by default, advanced template optional |
| Project-specific review targets had no honest local route | Explicit value + reason, labelled local; PMS submission blocked until reconciled |
| Missing delivered estimates were added as zero | Velocity becomes Not measured; a real zero remains zero |
| Changed comments could retain old assistant decisions | Content fingerprints include text and relevant history |
| Unanswerable decisions could return to the assistant indefinitely | Null decisions persist and become person questions |
| Stale/mis-mapped sources could keep affecting calculations | Preserve stored evidence for repair but withhold invalid derived facts; block submission |
| Failed sheet reads could lead to destructive refresh behavior | Stop on read errors; offline Google runs preserve destination/baseline and create a separate preview |
| Generated workbooks could remove unrelated tabs or execute source strings as formulas | Preserve custom tabs, write source strings literally, replace the file atomically |
| Long boards exceeded fixed read/formula limits | Read whole owned Google tabs; grow task/defect formula ranges with the model |
| Google dimension updates could exceed the old grid size | Expand the grid before resizing/unhiding columns |
| Unknown plan delivery became late in Excel | Sheet and engine both leave it unresolved until evidence is entered |
| Workbook results depended on the date it was opened | Use the calculation date, not volatile TODAY() |
| Long notes could be clipped | Size summary rows according to note length |
| Excel dashboard bars used undefined-function wrappers | Use native Excel fallback formulas and Google SPARKLINE variants in their respective writers |
| A second run without period facts could create an empty period and crash | Unchanged draft rows do not become empty facts; period edits match names, preserving metadata when reordered |
| Jira histories and GitHub comments/events could be truncated | Read available pagination and reject unsupported incomplete snapshots |
| Removed project items could survive cached membership | Reconcile current membership on refresh |
| Expanded GitHub queries exceeded its node limit | Smaller pages; verified against the live repository |
| PMS payloads could be applied to the wrong selected scope | Check project/period ownership, reviewed input/payload digests, unresolved work and current sheet edits |
| An incomplete replacement payload could erase unmeasured KPIs | Refuse incomplete sets pending live endpoint-contract acceptance |
| Documentation advertised unattended approval bypasses and universal host support | One explicit approval rule and an honest runtime capability matrix |

The eight-tool MCP bridge delegates to the existing CLI. It does not duplicate the engine,
host credentials remotely, or introduce a second source of calculation truth.

## Verification

- Required selftest: **268 checks passed**, including the nested **34-test audit regression
  suite**. The nested suite is one of the 268 checks, not 34 additional independent checks.
  Formula evaluation is required; missing dependencies fail rather than silently skip.
- Formula parity is checked against engine results, including an unresolved plan item and
  a historical calculation date. Both missing and zero effort are covered.
- A real local MCP client tested initialization, discovery of eight tools, project listing,
  offline preparation, batch review, preview, stale approval refusal and invalid project refusal.
- Live GitHub read of this repository's seven audit issues: **1.8 s first successful run,
  1.7 s rerun**. These are small-board pipeline timings, excluding installation, assistant
  judgement and user review. They do not predict large Asana/Jira project timings.
- The fictional 25-card fixture produced its draft workbook in **0.3 s** locally. It still
  had open judgements and person questions; draft generation is not final acceptance.
- The generated workbook was opened in desktop Excel. Dashboard calculations exposed the
  unknown-delivery mismatch; after repair, the dashboard showed the engine's 10 met,
  6 not met and 2 not measured outcomes. Error-marker wrappers were subsequently removed
  and covered by the required native-formula check.
- Setup/run skill metadata validates. Both release manifests move together to 2.1.0.
- CI runs the full suite and MCP smoke test on Python 3.10 and 3.12. Check the PR's actual
  result before merging; configuration of CI is not a passing CI result.

## Acceptance still outstanding

[Live-provider acceptance](https://github.com/NumanIbnMazid/kpi-copilot/issues/9) is blocked
on private runtime connections and designated disposable test destinations. Live Asana/Jira,
OAuth refresh, Google write/read-back and PMS approved write behavior are not certified by
mock tests or read-only interface inspection. PMS period ownership and replacement/concurrency
contracts must be verified against the deployment. No production test write was attempted.

[Host acceptance and browser deployment](https://github.com/NumanIbnMazid/kpi-copilot/issues/10)
tracks installation checks in individual AI clients. A browser code workspace can use exports;
a browser chat without execution needs an authenticated hosted runtime, which is not shipped.
Local MCP protocol success does not establish all-host compatibility.

Additional practical limits: do not run multiple writers on one profile; same-day reruns reuse
a run folder unless a distinct label is supplied; source tables need explicit mappings; a
PDF still needs one assistant digest after each change. User approval of a known completed
period remains the final onboarding check.

## Research used

The implementation was checked against primary documentation: [GitHub GraphQL resource
limits](https://docs.github.com/en/graphql/overview/resource-limitations), [Jira issue search](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/),
[Asana pagination](https://developers.asana.com/docs/pagination) and
[rate limits](https://developers.asana.com/docs/rate-limits),
[Google Sheets batch updates](https://developers.google.com/workspace/sheets/api/guides/batch),
and [MCP runtime/host distinctions](https://py.sdk.modelcontextprotocol.io/get-started/real-host/).
The optional bridge pins the stable Python SDK v1 API; the upstream tutorial also discusses
newer SDK generations, so installation guidance is grounded in the tested code here.
