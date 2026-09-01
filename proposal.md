# Final Project Proposal

**Working title:** Shortlist — Undergrad School Matching Tool
**Course:** MBAxMS Python Bootcamp — Fall 2026
**Status:** Draft v0.2 — narrowed from the original trends-explorer idea to a more specific, buildable tool; ready for group review

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

Build a Python tool that takes a student's academic stats and personal priorities — budget, financial aid need, field of study, and more — and ranks U.S. undergraduate schools against them, using public admissions data.

## Motivation

Most public higher-education data is built for administrators and researchers, not for the students actually making decisions with it. A prospective student comparing schools has to translate cost tables, admission-rate percentiles, and financial-aid formulas into an answer to a much simpler question: which of these schools actually fit me?

Instead of building general-purpose trend visualizations (our original idea in v0.1), we want to build something a student could actually use: a short set of plain-language questions about their scores, budget, and priorities, and a ranked, explainable list of schools back — not a black-box score, but one where the student can see why a school ranks where it does and adjust their priorities to watch the list change.

## Data Sources

- **College Scorecard** (U.S. Dept. of Education) — the core data source for this project. A free, public API covering admission rates, SAT/ACT ranges, cost of attendance, net price by income bracket, aid received, graduation rates, and post-graduation earnings for nearly every degree-granting institution in the U.S. No licensing or access issues; an API key is issued instantly.

We considered IPEDS and the Urban Institute Education Data Explorer (our original sources from v0.1) as alternatives. Scorecard covers what this narrower, ranking-focused use case needs on its own, so we're treating those as a fallback rather than a primary source unless scope grows.

**Known gap:** Scorecard's financial-aid figures are based on FAFSA, the U.S. federal aid system, so they don't reflect what international students are actually offered. If the tool should be useful to international applicants, we'll need to supplement this with a manually curated list (e.g., the published set of schools that are need-blind for international students) rather than relying on Scorecard alone for that question.

## Rough Scope

**Feasible with Scorecard data alone:**
- Reach / Target / Safety classification, based on the student's SAT/ACT against each school's admitted range
- Ranking by cost, net price, and aid against the student's stated budget
- Ranking by graduation rate and post-graduation earnings
- Filtering and weighting by school size, location, and public vs. private status

**Not feasible with Scorecard alone (gaps, not blockers):**
- Financial aid specifically for international students
- Any signal on graduate-school preparation or research opportunities
- Schools outside the U.S.

We're scoping the first version to U.S. four-year institutions only, roughly 300–500 of them, to keep the data pull and testing fast.

## Possible Deliverable

- A Python ingestion script that pulls and caches the relevant College Scorecard fields locally, so the demo doesn't depend on live API calls
- A ranking module — normalizes each metric, weights it by the student's stated priorities, and classifies each school as reach/target/safety — written as a standalone package, not tied to any particular UI
- A Streamlit app: a short, plain-language question flow for entering a student's profile, and a results screen showing the ranked list with toggleable columns
- A short written summary of what the data does and doesn't support, including the international-aid gap above

We're leaning toward a single Streamlit app for the first working version, since it keeps the data, ranking logic, and UI in one Python codebase — the fastest path to something demoable. Splitting into a separate backend and frontend is a reasonable next step if we take this further, but isn't needed for the first version.

## Open Questions

- How exactly should a student's ranked list of priorities convert into scoring weights?
- Should "grad school interest" be a real filter, or just a soft proxy (e.g., favor higher graduate rates)?
- Should the international-aid gap be handled with a manually curated supplement list, or left as a clearly labeled limitation for v1?
- How many schools does the demo dataset need for the results to feel credible, without slowing down the data pull?

## Next Steps

1. Request a College Scorecard API key and pull a small sample of schools end to end, to confirm the fields we need are actually available and usable.
2. Build the ranking and classification logic as a standalone, tested module, independent of any UI.
3. Build the Streamlit intake flow and results screen around that module.
4. Rehearse the demo with 2–3 realistic student profiles and note where the data or ranking logic needs adjusting.
5. Update this proposal to v1 once the group has reviewed the narrowed scope.
