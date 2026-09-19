# Asana

Reads the board through Asana's REST API, straight to disk, and keeps what it read.

```bash
python3 scripts/kpi.py run --profile profile.yaml --project <id>      # uses this reader
python3 adapters/asana/api.py --project <asana project id> --out board.json   # on its own
```

| | |
|---|---|
| First read, 150 cards | about 15 seconds: one paged list, then each card's history, eight at a time |
| Every read after | 2-3 seconds: a card whose `modified_at` has not moved keeps the history already read |
| What it produces | a **board snapshot** (`scripts/board.py`): cards, fields, column moves, completions, comments. No judgement |
| What it can see | status history, comments, assignee, estimates, story points, tags, created and closed dates, reporter |

It only ever issues GET. Everything that needs a rule or a brain - what is a defect, what
is rework, which period - happens afterwards in `scripts/classify.py`, the same way for
every tracker.

## Signing in

`python3 scripts/kpi.py auth` shows what is connected and the best way in for this machine.

1. **A personal access token** - Asana > Settings > Apps > Developer apps > Personal access
   tokens, then `python3 scripts/kpi.py auth asana --route token`, typed by you in a terminal
   (stored in `~/.config/kpi-copilot`, readable only by you), or `export ASANA_TOKEN=…`. A
   minute to set up, the fastest at run time, and the one for an unattended schedule. A
   different variable name can be set as `tracker.options.token_env`.
2. **Sign in in your browser** - `python3 scripts/kpi.py auth asana --route browser`; click
   Allow. Works in your own browser or your assistant's built-in one (`--no-open` prints the
   link). Needs an Asana app your company registers once (`docs/03-Prerequisites.md`).
3. **No credential at all** - see the last section: a signed-in tab downloads the board.

A token never goes through a chat, whichever route is used.

## Profile

```yaml
tracker:
  adapter: asana
  estimate_field: Estimated Time       # custom field holding hours
  story_point_field: Story Points
  options:
    include_subtasks: false            # yes = subtasks are rows of their own
projects:
  - id: q3-release
    tracker_ref: "1200000000000001"    # the long number in the board's URL
scan:
  comments: on-demand                  # never = do not keep comment text at all
  tracker_scope: all                   # touched-since = only re-read cards modified since the first period began
```

Status is the card's **column in this project**. A card that lives in several projects moves
in all of them; only this board's columns count. Boards that keep status in a custom field
instead are read the same way - a change of an enum field is a status move.

## No token, and no way to get one

`browser_snapshot.js` collects the same raw responses from a signed-in tab and **downloads**
them as a file, so nothing travels through an assistant's context:

```text
kpiSnapshot('1200000000000001')        ->  ~/Downloads/asana-raw-1200000000000001.json
python3 scripts/kpi.py run … --from-raw ~/Downloads/asana-raw-1200000000000001.json
```

Both routes go through the same conversion (`api.py: from_raw`), so they cannot disagree.

## The older converter

`extract.py --from-extract` still converts the legacy `window.__kpi` shape into KIF, for
anybody who has such a file. New work should not use it: that route needed an assistant to
scrape the board and judge every card by hand, which is what made runs slow and made two
runs of the same board disagree.
