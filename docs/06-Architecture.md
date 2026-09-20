# Architecture

One shared Python engine serves every tracker and assistant. Keep deterministic work out of
the model's context: source APIs write to disk, a compact queue asks for judgement, and the
same workbook description drives local and Google output.

```
CLI / skills / optional local MCP
             |
          kpi.py
             |
tracker reader -> board snapshot -> classifier + saved judgements -> KIF -> KPI engine
                        ^                 ^                                 |
                 approved sources    person corrections              sheet model
                                                                      /        \
                                                                    xlsx     Google Sheet
                                                                              |
                                                        reviewed payload -> approved PMS write
```

## Responsibilities

- `adapters/*/api.py`: fetch tracker facts, pagination and observable history. Asana reuses
  unchanged task history. Jira and GitHub reconcile current membership so moved/deleted items
  and Project field edits do not remain hidden by a modified-since cache.
- `sources.py`: fetch only named sources, map tables, fingerprint document digests. A stale
  digest is kept for repair but withheld from calculations. A missing mapped tab never falls
  through to a different project's tab.
- `classify.py`, `judge.py`, `ledger.py`: propose classifications, create one judgement queue,
  remember answers, and escalate undecidable calls. Person > assistant > rule. Edited comment
  contents invalidate an assistant's answer even when the comment count is unchanged.
- `kpi_engine.py`: calculate the nine measures and notes. Missing required estimates do not
  become zero velocity. Units, denominators, exclusions and uncertainty accompany results.
- `kpi_registry.py`: resolve the profile-relative definition cache for both engine and sheet.
  Per-project PMS targets override PMS defaults. Local review targets are labelled and prevent
  PMS submission until removed and reconciled with PMS.
- `sheet_model.py`: formulas, style, validations and read-back schema shared by both writers.
  Ranges expand with register size. `sheet_readback.py` folds reviewed edits into local facts.
- `kpi.py`: orchestrate the run, report NEXT, and check that the reviewed inputs and payload
  have not changed before delivery. `run.py` remains for older converter workflows.
- `pms_push.py`: preview, check project/period identity, write only when explicitly applied,
  and read values and notes back. No production write is part of the self-test.
- `mcp_server.py`: optional stdio connection for compatible assistants. It invokes the same
  CLI, serializes operations within the server, and exposes a distinct preview/approved-send
  boundary. It is not a hosted service or an automatic source of approval.

## Recovery

An unreadable review workbook stops replacement. An offline run with a Google destination
writes a separate preview and retains the remote baseline. A failed publish also retains
that baseline. Local workbook saves use temporary files and preserve extra user tabs.
Corrupt judgement memory is an error, never an empty replacement.

Google applies the generated requests in one atomic batch. This prevents partial batch
application, but does not lock collaborators out between read and write. Finish editing
before refreshing; concurrent editing during a refresh is not supported.

Daily run folders keep the latest result for that date. They are not an immutable history
of every intraday run. Use a distinct `--date` run name when retaining multiple snapshots.

## Assistant/runtime boundary

A shell-capable assistant can follow `AGENTS.md`; the skills provide conversational guidance.
A local MCP host can invoke the eight bridge tools. A code-enabled browser workspace can run
with uploaded exports. Browser-only chat needs a runtime connection; an authenticated hosted
MCP service and remote credential administration are outside the current release.

No assistant is licensed, authenticated or granted additional access by installing this repo.
The user's chosen runtime still needs permission to execute and to reach each named service.

## Validation

`python scripts/selftest.py` runs the bundled examples, formula evaluation and audit
regressions. Install `requirements-test.txt`; formula validation is required. Separately,
`tests/verify_mcp.py` exercises a real stdio session against fictional offline data. The
GitHub workflow runs both on supported modern Python versions.

[Audit evidence and remaining limits](11-Audit.md) distinguish offline tests, live reads,
visual inspection, host compatibility and production write acceptance.
