# Source of truth, and how far a run looks

The settings that decide what a run may read.

A run has to answer a fixed set of questions: what was delivered, when, against which
promised date, how many defects, how many escaped. **Where it is allowed to look for those
answers is entirely yours to set, and it never looks anywhere else.**

The rule, whatever the settings: a run reads the **tracker**, plus the **sources named in the
profile** (plan, estimates, timeline). It does not search chat, mail or Drive. What those
cannot answer becomes a question for a person on the Open Questions tab - asked once,
remembered. Looking further is something a person asks for, run by run (`--deep`, or "also
check the client chat"), and even then only the open questions are looked up, only in the
places named.

---

## `sources.mode` — which places may answer

```yaml
sources:
  mode: tracker-only        # tracker-only | tracker-first | multi-source
```

| Mode | What happens | Who it is for |
|---|---|---|
| `tracker-only` | The issue tracker is the single source of truth. Chat, mail and documents are **never opened**. Anything the board cannot answer comes back "Not measured", with that as the stated reason | Teams whose board is genuinely the record: status moves to Dev Complete, QA Ready and Closed are made properly and on time |
| `tracker-first` *(default)* | The board answers first; the plan, estimates and timeline named in the profile supply scope, hours and dates. Nothing else is opened | Most teams |
| `multi-source` | Other sources are read even where the board has an answer, and a disagreement is reported rather than resolved silently | Teams where the board and reality routinely differ, and you want both quoted |

**`tracker-only` is not a degraded mode.** It is a legitimate, and often the correct, choice.
If your team's process is that nothing is delivered until the card moves, then the card moving
*is* the truth and reading a chat space to second-guess it adds cost and risk, not accuracy.
The readiness check knows this: on a `tracker-only` profile a missing plan, estimates sheet or
chat space is reported as "not needed", not as a gap.

What it costs you: KPIs that depend on something outside the board. In practice that is the
client-agreed date, the handover date, and change-request hours when they live in a sheet. If
those are on the board too, `tracker-only` costs you nothing at all.

---

## `scan` — how far back, and how much

```yaml
scan:
  window: period+grace      # period | period+grace | days | all
  grace_days: 14
  tracker_scope: all        # all | touched-since | period
  comments: on-demand       # always | on-demand | never
  chat:
    lookback_days: 45
    max_messages_per_channel: 300
    only_when_missing: true
  mail:
    lookback_days: 45
    max_threads: 50
  stop_when_found: true
  max_sources_per_fact: 2
```

| Setting | Default | What it decides |
|---|---|---|
| `window` | `period+grace` | The time range. `period` is the period's own dates; `period+grace` adds `grace_days` either side; `days` uses `days`; `all` removes the limit |
| `grace_days` | 14 | How far either side of the period to still look. This is what catches a handover announced the morning after the period closed |
| `days` | 90 | Used when `window: days` |
| `tracker_scope` | `all` | `all` reads the whole board. `touched-since` reads only items modified inside the window. `period` reads only items assigned to the period |
| `comments` | `on-demand` | `on-demand` reads a ticket's comments only where that item's judgement depends on one |
| `chat.lookback_days` | 45 | How far back a chat space is searched |
| `chat.max_messages_per_channel` | 300 | Cap per space |
| `chat.only_when_missing` | `true` | Search a space only for a fact nothing else answered |
| `mail.lookback_days` / `mail.max_threads` | 45 / 50 | The same, for mailboxes |
| `stop_when_found` | `true` | Stop at the first source that answers, rather than collecting every mention |
| `max_sources_per_fact` | 2 | How many sources one fact is worth |

### `window`

`period+grace` is right for almost everyone. A period does not end cleanly: the build goes out
on the last afternoon and is announced the next morning, and the client agrees the next date a
week before the period opens. Fourteen days either side catches both without dragging in the
previous quarter.

Use `all` only while investigating something. Leaving it on makes every monthly refresh re-read
the project's entire history, and the readiness check will say so.

### `tracker_scope`

Leave it at `all` for a normal project board — a few hundred cards is cheap, and the card
history is what proves a date. Switch to `touched-since` on a long-running board with thousands
of items, where reading everything to compute one month is the single most wasteful thing a run
does.

`period` is the tightest, and it is only safe when every item genuinely carries its period. If
items are assigned to periods by hand, something will be missing and Velocity will quietly come
out low.

### `comments`

Comments are the most expensive thing on a board and matter for a handful of items: the one
where the client asked for a change, the one where a date was disputed, the one where QA and
dev disagreed about whether a failure was rework. `on-demand` reads them exactly there.

Set `always` if your team records delivery decisions in comments rather than in status moves.
Set `never` and a run will be fast and will lose the evidence links behind several judgements.

---

## What it costs

| Step | First run | Every run after |
|---|---|---|
| The board (150 cards, with history) | ~15 s | 2-3 s - only cards whose `modified_at` moved are re-read |
| Each source | 1-2 s | nothing, unless the file changed |
| Judging | a few dozen cards put to the assistant, once | only cards that are new or changed |
| The sheet | under a second locally; a few seconds for Google | the same |

`scan.chat` and `scan.mail` bound a **deep** run only. A normal run never opens either.

## Saying what was skipped

Both settings are honest by construction. **The sheet's Run Log tab lists every source the
run read, with its date, and says what it deliberately did not read** - "chat, mail, other
documents: not read" is there on every normal run. On a deep run, a limit that cut something
off is named the same way:

> Chat searched back to 08/01 only (`scan.chat.lookback_days: 45`). If a date was agreed
> before then, it is not in these numbers.

And when a fact the run genuinely needs falls outside the window, the rule is: widen for that
one fact, say so, and offer to change the profile. Never quietly re-read everything.

This matters more than the speed. A run that is fast because it looked in fewer places and
*said so* is trustworthy. A run that is fast because it silently gave up is not.

---

## Setting it per client

Both sections are overridable, so one lead with two clients can run one on the board alone and
the other across chat as well:

```yaml
accounts:
  - id: northwind
    overrides:
      sources: {mode: multi-source}        # dates get agreed in the weekly call
      scan:    {window: period+grace, grace_days: 21}

  - id: acme
    overrides:
      sources: {mode: tracker-only}        # the board is the contract
      scan:    {tracker_scope: touched-since, comments: never}
```

→ [05-sources.md](05-sources.md) · [02-accounts-and-projects.md](02-accounts-and-projects.md)
