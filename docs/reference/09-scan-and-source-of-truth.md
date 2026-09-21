# Source policy and scan limits

[Documentation](../README.md) · [Configuration reference](README.md) · [Source mappings](05-sources.md)

A normal run reads the configured tracker and named plan, estimates and timeline. A missing
answer becomes an Open Question. Mail/chat searches require a requested deep run or explicit
permission for named places, and are limited to the unresolved questions.

## Source modes

| `sources.mode` | Intended use and current behavior |
|---|---|
| `tracker-only` | The board/export is the agreed source. Optional external sources are not loaded; missing evidence remains visible |
| `tracker-first` | The board plus named supporting sources, with configured effort/date precedence |
| `multi-source` | A profile for using several named sources. Review conflicting evidence explicitly; do not assume every conflict is automatically detected |

The current source loader reads named sources for both `tracker-first` and `multi-source`.
Neither mode enables chat searching. Listing a tool in the registry is not permission to
read it, and neither source mode gives a client connector to the Python runner.

## Scan settings and implementation limits

```yaml
scan:
  tracker_scope: all
  comments: on-demand
  window: period+grace
  grace_days: 14
  chat: {lookback_days: 45, max_messages_per_channel: 300, only_when_missing: true}
  mail: {lookback_days: 45, max_threads: 50}
  stop_when_found: true
  max_sources_per_fact: 2
```

These settings mix implemented reader controls with instructions for an assistant's bounded
follow-up. Do not treat every accepted field as an enforced API filter.

| Setting | Current boundary |
|---|---|
| `tracker_scope: all` | Read configured tracker membership; preferred default for complete reporting |
| `tracker_scope: touched-since` | The orchestrator derives a cutoff from saved period starts; Asana can use it when deciding which history needs refresh. It is not a universal filter across Jira/GitHub |
| `tracker_scope: period` | Accepted configuration intent, not a general period-query implementation. Use supported tracker-specific scope and inspect coverage |
| `comments: never` | Asana can omit stored comment text. Other readers have their own behavior; this is not a cross-adapter privacy filter |
| `comments: on-demand` | Asana's current reader retains comments from fetched history; it is not a second fetch only for assistant-queued cards |
| `window`, `grace_days`, `days` | Describe a bounded evidence window. Do not assume they limit all tracker API calls |
| `chat.*`, `mail.*` | Limits the assistant must honor during an authorized follow-up; no general chat/mail crawler is shipped |
| `stop_when_found`, `max_sources_per_fact` | Follow-up search instructions, not proof that a provider query enforced the limit |

Jira and GitHub refresh current membership so moved/deleted records and changed Project
fields are not hidden by stale caches. Signed-in exports read their configured scope and do
not inherit every API cache optimization. Reader behavior is documented under
[tracker options](03-tracker-and-conventions.md).

## How to keep a run bounded

Choose the narrow project or supported tracker query that actually represents the agreed
scope. Reuse the current snapshot when applying judgements. Read a plan again only when its
fingerprint changes. Do not narrow a query in a way that drops still-relevant commitments
or defects just to improve speed.

When an open question needs chat evidence, name the question, channel and time window.
Record the answer and source link or state that it was not found. Widen only for that fact
with the person's scope, rather than searching every client's history.

The Run Log identifies loaded sources and skipped categories. A deep-run flag is permission
for the assistant to follow up, not evidence that a search actually happened. Report actual
search coverage and limits separately.

Use the run's printed timings and whole-session elapsed time. Synthetic examples do not
promise fixed durations for real boards, network calls or human review.
