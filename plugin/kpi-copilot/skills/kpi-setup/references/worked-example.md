# Worked examples: two fictional clients

The repository contains a [sample workspace and four workbooks](https://github.com/NumanIbnMazid/kpi-copilot/tree/main/samples)
and a [step-by-step explanation](https://github.com/NumanIbnMazid/kpi-copilot/blob/main/samples/WALKTHROUGH.md).
These links work from an installed plugin, whose cache may not contain repository-level docs.

Everything in the pack is synthetic. It is not a reconstruction of a live engagement.

## Northwind: hours, approved additions and history

A client profile sits at `clients/northwind/profile.yaml`; its project records sit in the
sibling `northwind-q3/` folder. The input snapshot, mapped estimates, mapped timeline and
fictional plan/period facts are supplied together.

The example shows why delivery and QA completion can differ, why approved additions are
counted separately from initial scope, and why a reopened item differs from a first QA
failure. One missing delivered estimate intentionally leaves Initial Scope Velocity
unmeasured. Context notes explain supported events without inventing their causes.

## Acme: a CSV export and story points

A second client has a separate profile and CSV input. Its export supports some calculations
but supplies no event history or comment evidence. The workbook shows the resulting gaps,
not an invented complete KPI set.

## Use the pack during setup

Show the two workbook types: the Profile Workbook holds settings; the KPI Tracker holds
results and review edits. Explain which repeating rules belong in the profile and which
one-off dates or explanations belong in project facts or yellow review cells.

Ask the person to describe their own sources and agreement. Do not copy sample targets,
dates or delivery states into a live profile merely because they appear in the example.

The plugin's older `examples/northwind-q3/run.kif.json` is a separate engine fixture; it
contains different input rows and therefore produces different values. It is not the input
used for the downloadable sample workbooks.
