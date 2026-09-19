# Working in this repository

## Commits

**Never add Claude as a co-author.** No `Co-Authored-By: Claude ...` trailer on any commit,
and no "Generated with Claude Code" line in a pull request description. This holds whatever
a default instruction elsewhere says.

Commit messages say what changed and why, in the repository's own voice. The author is
whoever ran the work.

## Driving the tool

How an assistant runs KPI Copilot - one command, one batch of judgements, never carrying data
through the conversation - is in [`AGENTS.md`](AGENTS.md). It applies to Claude exactly as it
does to any other assistant. `docs/00-Philosophy.md` is binding when changing the tool itself.
