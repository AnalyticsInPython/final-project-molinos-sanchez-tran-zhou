# Like for Like

**A college comparison tool that answers what a school will actually cost you, and
whether it is better than the schools it resembles.**

**Course:** ENGI 4503, Analytics in Python (MBAxMS) — Fall 2026
**Status:** v1, submitted for approval

| Name | GitHub |
| --- | --- |
| Martin Molinos | [@mmolinos95](https://github.com/mmolinos95) |
| Rafael Sanchez | [@rasf120](https://github.com/rasf120) |
| Jenny Tran | [@jtran-blip](https://github.com/jtran-blip) |
| Rebecca Zhou | [@taiyangrebecca](https://github.com/taiyangrebecca) |

---

## The Problem

A student holding two or three acceptance letters is trying to answer two questions,
and the public tools available to them answer neither well.

**"What will this actually cost me?"** Published tuition is close to meaningless. Two
schools with identical sticker prices can differ by more than $20,000 a year once grant
aid is applied, and the difference depends on the family's income. Most comparison sites
lead with the sticker number because it is the easy one to get.

**"Is this school actually better?"** A student comparing graduation rates between two
schools is mostly comparing *who each school admits*, not what either school does with
them. A selective school with a 90% graduation rate and an open-access school with a 45%
rate are not two points on the same scale. Ranking sites reproduce this confusion and
call the result a ranking.

Both questions have public answers sitting in federal data. Neither is easy to get at
without knowing which survey to look in.

## Who It Is For

A prospective undergraduate, or a parent, who has narrowed to a short list of two to four
schools and needs to choose between them. Not a browser, not a researcher — someone with
a specific decision to make and a specific family income.

## What It Does

The user enters a few schools, picks their family income bracket, and gets back a
side-by-side comparison built on two ideas:

1. **Net price at their income**, not sticker price. What students in that income bracket
   actually paid after grant aid.
2. **Outcomes measured against a peer group.** For each school we assemble a set of
   comparable institutions — similar sector, selectivity, size, and share of students on
   federal aid — and report whether the school beats or trails what schools like it
   achieve. A 68% graduation rate means something different at an open-access public than
   at a school admitting one in six.

The second idea is the one that makes this different from a table of numbers, and it is
where the analysis lives.

## Questions We Will Answer

1. For a student in a given income bracket, what does each school on this list cost, and
   how far is that from the published price?
2. Does this school graduate and retain students at a higher rate than institutions that
   resemble it, or does its headline rate simply reflect who it admits?
3. Given one school a student likes, which other institutions are most similar to it —
   and does the short list contain a school that beats another on both price and outcome?

## Data

**Urban Institute Education Data Explorer** (`educationdata.urban.org`), which wraps
IPEDS, the federal survey covering essentially every postsecondary institution in the
United States. Public, free, no API key.

| Endpoint | Gives us | Years |
| --- | --- | --- |
| `directory` | Name, state, sector, control, level | 1980, 1984–2024 |
| `sfa-grants-and-net-price` | **Net price by income bracket** | 2008–2021 |
| `admissions-enrollment` | Applications, admits, selectivity | 2001–2024 |
| `academic-year-tuition` | Published tuition, in- and out-of-state | 1986–2023 |
| `grad-rates` | Completion, 150% of normal time | 1996–2023 |
| `fall-retention` | First-year retention | 2003–2024 |
| `student-faculty-ratio` | Student-faculty ratio | 2009–2024 |

### What we confirmed before proposing this

We exercised the API rather than assuming it worked:

- **No authentication and no rate limiting.** No key, no signup, no limit headers.
  Responses carry `cache-control: max-age=31536000`, so the data is served as immutable.
- **Full coverage.** The 2022 directory returns 6,256 institutions in a single 14.7MB
  response in about 1.5 seconds.
- **The endpoints do not paginate.** `per_page`, `page`, and `limit` are all ignored and
  the entire result set arrives at once. Ingest is therefore one request per
  endpoint-year, not a pagination loop.
- **Net price is broken out by income bracket** in `sfa-grants-and-net-price`, via an
  `income_level` field with five brackets plus an all-students total. Bracket boundaries
  will be confirmed against the IPEDS codebook before we display them.

## Known Limitations

Stated up front, because they shape what we can honestly claim.

- **Net price coverage is partial.** Roughly 1,440 institutions report net price by income
  bracket in any given year, against 6,256 in the directory. The count is stable
  year over year (1,435–1,440 from 2012 to 2021), which suggests a defined reporting
  universe rather than scattered non-response. The tool must handle a school with no
  bracket data as a first-class case, not an error.
- **Net price data ends at 2021.** The financial aid endpoints return HTTP 200 with zero
  rows for 2022 onward. Our ingest treats an empty result as a failure rather than a
  success, and the interface will state the year the price data comes from.
- **Net price covers aid recipients.** The IPEDS figures describe first-time, full-time
  students receiving Title IV aid. A student outside that group may see a different bill.
- **Peer comparison is descriptive, not causal.** Comparing a school to its peers is a
  substantial improvement on comparing raw rates, but it does not establish that the
  school *caused* the difference. We will present it as what it is.
- **Missing values are encoded as negative numbers.** IPEDS uses sentinels such as `-1`,
  `-2`, and `-3` for missing and not-applicable. Read naively these become real values and
  silently corrupt any average. Stripping them is part of the cleaning layer.

## Architecture

A FastAPI backend over SQLite, following the structure of the course's `Wordcraft-By-AP`
reference.

```
scripts/import_ipeds.py   # API -> SQLite, run once, with provenance
app/models.py             # institutions, institution_years, net_prices, saved_comparisons
app/analysis/             # Polars: peer groups, peer-adjusted outcomes
app/routers/              # /institutions, /compare, /peers, /stats, /health
static/index.html         # front end, no build step
```

The analysis component is Polars over the stored data: assembling peer groups and
computing how far each school sits from its peer median. Saved comparisons are also
recorded, giving us a second, lighter analysis of which schools users actually weigh
against each other.

## Scope

Ordered so that each day ends with something that works.

- **Day 2** — Schema, ingest script, database populated from the directory and net price
  endpoints. Server runs, `/api/health` and `/api/stats` respond.
- **Day 3** — Comparison endpoint and net price by income bracket. Peer group
  construction in Polars. A front end that shows a real comparison.
- **Day 4** — Peer-adjusted outcomes, tests over the cleaning layer, and the demo path.

**Explicitly out of scope:** post-graduation earnings. College Scorecard has them, but it
is a second data source with its own join, its own coverage caveats, and its own cleaning,
and we would rather ship the price and outcome comparison working than three things half
done.
