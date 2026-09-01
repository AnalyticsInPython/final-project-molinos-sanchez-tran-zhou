# Final Project Proposal

**Working title:** Undergrad School Matching Tool
**Course:** MBAxMS Python Bootcamp — Fall 2026

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

Build a Python tool that takes a student's academic stats and personal priorities (budget, financial aid need, field of study, and more) and ranks U.S. undergraduate schools against them, using public admissions data.

## Motivation

Most public higher-education data is built for administrators and researchers, not for the students actually making decisions with it. A prospective student comparing schools has to translate cost tables, admission-rate percentiles, and financial-aid formulas into an answer to a much simpler question: which of these schools actually fit me?

Instead of building general-purpose trend visualizations, we want to build something a student could actually use: a short set of plain-language questions about their scores, budget, and priorities, and a ranked, explainable list of schools back, where the student can see why a school ranks where it does and adjust their priorities to watch the list change.

## Data Sources

- **College Scorecard** (U.S. Dept. of Education) — the core data source for this project. A free, public API covering admission rates, SAT/ACT ranges, cost of attendance, net price by income bracket, aid received, graduation rates, and post-graduation earnings for nearly every degree-granting institution in the U.S. No licensing or access issues; an API key is issued instantly.

We considered IPEDS and the Urban Institute Education Data Explorer as alternatives. Scorecard covers what this narrower, ranking-focused use case needs on its own, so we're treating those as a fallback rather than a primary source unless scope grows.

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

We're scoping the first version to U.S. four-year institutions only, roughly 300–500 of them.
