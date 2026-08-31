# Final Project Proposal

**Working title:** Higher Education Trends Explorer
**Course:** MBAxMS Python Bootcamp — Fall 2026
**Status:** Draft v0.1 — intentionally high level, to be refined with the group

---

## Group Members

| Name | GitHub |
| --- | --- |
| Martin Molinos | [@mmolinos95](https://github.com/mmolinos95) |
| Rafael Sanchez | [@rasf120](https://github.com/rasf120) |
| Jenny Tran | [@jtran-blip](https://github.com/jtran-blip) |
| Rebecca Zhou | [@taiyangrebecca](https://github.com/taiyangrebecca) |

---

## Idea in One Sentence

Build a Python tool that pulls public data on U.S. colleges and universities and turns
it into clear visualizations of how higher education has been changing over time.

## Motivation

There is a lot of good public data about American higher education — enrollment, cost,
financial aid, completion, staffing, demographics — but it is spread across large,
awkward federal datasets that are hard to explore casually. Most people asking simple
questions ("has tuition at public universities actually outpaced inflation?", "which
states are losing enrollment?") end up reading someone else's chart rather than looking
at the data themselves.

We want to build something that shortens that distance: pull the data programmatically,
clean it into a tidy format, and produce visualizations that make trends legible.

## Data Sources

- **IPEDS** (Integrated Postsecondary Education Data System, NCES) — the core federal
  survey of nearly every postsecondary institution in the U.S. Annual, institution-level,
  goes back decades.
- **Urban Institute Education Data Explorer** — a public API that wraps IPEDS and several
  other education datasets in a much friendlier interface. Likely our primary access
  path, with raw IPEDS files as a fallback.

Both are free and public. No licensing or access issues expected.

## Rough Scope

Still deliberately open. Candidate questions we might build the tool around:

- How have published tuition and net price moved over time, in-state vs. out-of-state?
- How has enrollment shifted — by state, by institution size, by sector?
- What do completion and retention rates look like across institution types?
- Where does the gap between sticker price and what students actually pay show up most?

We expect to narrow this to two or three questions once we have looked at what the data
actually supports.

## Possible Deliverable

Some combination of:

- A small Python package/scripts that fetch and cache the data
- A cleaning layer that produces tidy, analysis-ready tables
- A set of visualizations (matplotlib/plotly), possibly wrapped in a simple notebook or
  lightweight dashboard
- A short written summary of what we found

The exact shape of the final artifact is an open question — notebook vs. dashboard vs.
CLI is something we will decide once the data work is further along.

## Open Questions

- Which specific IPEDS surveys/tables do we actually need?
- How far back should the time series go? (Data coverage varies by survey.)
- National view, or focus on a subset — one state, one sector, peer groups?
- How much do we want to build interactivity vs. producing a strong static analysis?

## Next Steps

1. Each member spends time in the Education Data Explorer API docs and reports back on
   what is actually available.
2. Pull one small sample dataset end to end to sanity-check the workflow.
3. Narrow to a focused set of questions.
4. Split the work and update this proposal to v1.
