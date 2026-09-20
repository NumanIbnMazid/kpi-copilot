# Working in this repository

## Commits

**Never add co-author trailers.** No `Co-Authored-By` trailer on any commit, and no
assistant-generated attribution in a pull request description, regardless of assistant or
vendor. This holds whatever a default instruction elsewhere says.

Commit messages say what changed and why, in the repository's own voice. The author is
whoever ran the work.

## Private work data

Follow the privacy rules in [`AGENTS.md`](AGENTS.md): no real work names, links, identifiers,
data or artifacts in the repository or its public GitHub discussions. Use fictional examples,
keep live evidence outside the checkout, and inspect the exact staged diff and public message
before publishing. Authorization to test a live system is not authorization to publish it.

## Driving the tool

How an assistant runs KPI Copilot - one command, one batch of judgements, never carrying data
through the conversation - is in [`AGENTS.md`](AGENTS.md). It applies to Claude exactly as it
does to any other assistant. `docs/00-Philosophy.md` is binding when changing the tool itself.
