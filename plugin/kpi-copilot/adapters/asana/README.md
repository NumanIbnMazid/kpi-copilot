# asana adapter

> **Note for the public repository**
>
> `browser_extract.js` is internal tooling belonging to the organisation this was built for,
> and is **not included here**. The adapter's converter is, and it is the part worth having:
> point `--from-extract` at any JSON in the shape documented below and it produces valid KIF.
>
> To use Asana in this repository you have two options: write your own in-browser extractor
> against `adapters/_contract.md` (`/kpi-copilot:kpi-adapter` walks it), or export the board
> to CSV and use the `csv` adapter, which needs nothing at all.

Reads Asana through a signed-in browser tab rather than a token, and converts the result into
KIF.

## Why the browser, not the API

Nobody has to create, store or paste a personal access token, and the extractor sees exactly
what the person can see. The script that does the reading, `browser_extract.js`, has been in
real use on five live Northwind projects. This adapter converts its output rather than
reimplementing it - the judgement encoded in it (what counts as delivered, which QA failure
is rework, which cards are grouping cards) was learned from real boards, and rewriting it
would mean rediscovering all of that.

## How to run it

1. Open a signed-in `app.asana.com` tab.
2. Run your extractor in it, leaving the result on `window.__kpi`.
3. Save `window.__kpi` to a file.
4. Convert:

```bash
python3 extract.py --profile profile.yaml --project q3-release \
  --from-extract kpi.json --out run.kif.json
```

`/kpi-copilot:kpi-run` does all four steps.

## What it can see

The full set: status history, comments, assignee, estimates, story points, created and closed
dates, reporter.

## Mapping notes

- The legacy extract calls the handover `releaseDate`; KIF calls it `handover_date`. Blank
  means not handed over, which the engine turns into an honest "nothing to measure" rather
  than a green zero.
- `Pre-release` becomes `QA`; `Post-release` stays.
- `dev` (the hours the pipeline settled on) wins over `est` (the raw estimate), and
  `hours_source` records which.
- Three-way fields (`Yes` / `No` / `Pending`) carry through; blank becomes null and is left
  out of the denominator.

## Direct API

Not implemented. The adapter says so rather than pretending. The browser route is supported
and needs no token; if a token-based route is ever wanted, the contract is the same.
