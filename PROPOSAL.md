# In League

**A college comparison tool that answers what a school will actually cost you, and
whether it is better than the schools it resembles.**

**Course:** ENGI 4503, Analytics in Python (MBAxMS) — Fall 2026
**Status:** v2 — product framing and data-quality commitments added 2 Sep 2026

| Name | GitHub |
| --- | --- |
| Martin Molinos | [@mmolinos95](https://github.com/mmolinos95) |
| Rafael Sanchez | [@rasf120](https://github.com/rasf120) |
| Jenny Tran | [@jtran-blip](https://github.com/jtran-blip) |
| Rebecca Zhou | [@taiyangrebecca](https://github.com/taiyangrebecca) |

---

## What Shipped, and What Changed

Everything below this section is kept as written on 2 Sep 2026. Three things changed in the
building, and they should be read here rather than found by diffing the proposal against the
code.

- **Peer-group outcomes were not built,** for the reason this proposal already gives itself
  under *Known Limitations*: across the 25 selective universities in `scripts/schools.py`,
  graduation rates span 91–98% and retention 96–99%. There is no spread for a peer median to
  measure anything against, and the stratified sample that would create one was out of scope.
- **The analysis moved to reported cuts and computed gaps.** A cut redraws one area's metric
  for one group beside everyone, from the same survey, rather than against a peer group we
  assembled — the comparison is reported rather than invented. Beside it, the headline figure
  in each area is one we compute and IPEDS does not publish: spread (financial aid), yield
  (selectiveness), took-longer and first-year attrition (retention), debt-to-earnings (after
  graduation), athlete share (athletics).
- **The architecture is one module per area over the ingest tables, with no ORM** — there is
  no `app/models.py`, no `app/routers/` and no `app/analysis/`. Each area owns its query, its
  Polars computation, its template and its test, so the set grows by addition.

[ROADMAP.md](ROADMAP.md) tracks what is built and what was decided against;
[METRICS-REVIEW.md](METRICS-REVIEW.md) argues which of these metrics earn their place.

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

## The Shape of the Product

The comparison is not one fixed table. Schools are compared **area by area**, and inside
each area the user chooses which metrics they care about. Someone weighing cost against
debt wants a different page from someone weighing selectivity against outcomes, and
neither should have to scroll past the other's numbers to find their own.

Two controls drive it: schools on one side, areas on the other. Each area is a
self-contained module — its own query, its own computed metric, its own template, its own
test — so the set grows by addition rather than by redesign.

### The metric families

Seven areas were originally scoped from the NCES *Compare Institutions* tool. Working back
from what a family actually asks, they collapse into five:

| Family | The question behind it | Where it stands |
| --- | --- | --- |
| **Student finances** | What will this cost me, and what will I owe? | Net price by income band built; discount and out-of-pocket next |
| **Selectiveness** | Can I get in — and does anyone who gets in choose to go? | Derived from applications, admits and enrolments |
| **Admissions profile** | What did the students who got in look like? | Test scores and application requirements |
| **Student body** | Who goes here? | Race, gender, size and composition |
| **Outcomes** | Do students finish, and what happens after? | Completion, retention and equity gaps |

Student charges are not a sixth family. A sticker price is only meaningful next to the net
price it is discounted from, so it belongs inside student finances.

### The finance metrics we are building

Aid broken out by type — Pell against state grants against institutional grants — is
available, and is not the question a family asks. Three figures answer that question
directly, and all three are ours to compute rather than to look up:

1. **Average net tuition.** What students actually paid, set against the published price.
2. **Average discount rate.** Net as a share of sticker. This is the figure that makes two
   schools with very different published prices directly comparable, and it is the one
   number that survives a school raising its sticker price and its aid together.
3. **Average out-of-pocket cost across all students**, not only aid recipients — with the
   caveat in the next paragraph, which is load-bearing.

The third one needs care. IPEDS net price describes first-time, full-time students
receiving Title IV aid, who are a minority of the student body at most schools.
`sfa-all-undergraduates` covers everyone but reports *aid received* rather than a
published net price, so an all-student figure has to be derived from sticker price and
average grant aid. It will be labelled as derived wherever it appears, and it will not be
presented as an IPEDS figure, because it is not one.

### What we are deliberately not building

Both of these were asked for and neither exists in the data. Recording them here so the
absence is a decision rather than an oversight:

- **Average admitted GPA.** IPEDS does not collect it. The API carries `reqt_hs_gpa`, a
  flag for whether a school *requires* a GPA, not a value. The number lives in the Common
  Data Set, which is not a public API.
- **Merit versus need-based aid.** IPEDS reports institutional grant aid as a single
  figure with no split. Publishing a merit share would mean inventing one.

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
- **The endpoints paginate above 10,000 rows.** ~~They do not paginate.~~ Corrected after
  building the ingest: a response is capped at 10,000 rows and carries a `next` link.
  Small result sets arrive whole, which is why it first looked as though there were no
  pagination at all. `completions-cip-2` for 25 institutions is 71,010 rows and arrived as
  10,000 rows covering 4 institutions until the ingest followed `next`. **Ingest must be a
  pagination loop, and must assert the row count against the `count` the API reports** —
  otherwise a full-directory pull truncates silently.
- **Net price is broken out by income bracket** in `sfa-grants-and-net-price`, via an
  `income_level` field with five brackets plus an all-students total. Bracket boundaries
  will be confirmed against the IPEDS codebook before we display them.
- **Filtering accepts comma-separated unitids.** `?unitid=186131,166683,...` returns all of
  them, so a sample pull is one request per endpoint plus its pages, not one per school.

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
- **Missing values are encoded as negative numbers — but not every negative is missing.**
  IPEDS uses sentinels such as `-1`, `-2`, and `-3` for missing and not-applicable, and
  read naively these become real values and silently corrupt any average. Stripping them
  is part of the cleaning layer. **A negative `net_price` is the exception and must
  survive cleaning:** grant aid can exceed the total cost of attendance, and in the
  25-school sample five institutions post a genuinely negative net price (−$1,012 to
  −$2,251) while zero rows carry −1, −2, or −3. The cleaning rule is therefore
  column-specific — drop the exact sentinel values, never "drop anything below zero".
- **Rates are stored as fractions, not percentages.** `completion_rate_150pct` and
  `retention_rate` come back as 0.98, not 98. Rendered without conversion, a school with a
  98% graduation rate displays as 1%.
- **A top-25 sample cannot exercise the peer comparison.** Across the 25 selective
  universities in `scripts/schools.py`, graduation rates span 91–98% and retention 96–99%.
  There is no outcome spread to measure anything against, so the peer-adjusted analysis —
  the part of this project that is not a table of numbers — needs a sample stratified
  across sectors and selectivity, where open-access institutions sit at 20–45%. The
  selective sample remains useful as a fixture for the comparison interface.

## Telling the User What the Data Does Not Cover

Every limitation in the previous section is invisible to the student unless the interface
says so out loud. A blank cell reads as a zero. A 2021 figure reads as current. Both
produce a page that looks finished and is wrong, and neither raises an error.

The tool therefore states, at the top of each area and above the charts rather than in a
footnote beneath them:

- **How old the figures are**, whenever they are older than the normal publication lag for
  a federal survey. Net price ends at 2021, so in 2026 this reads as five years old. The
  wording preserves the distinction that matters: a stale figure is a bad quote and still a
  good comparison, because the schools all moved together. Saying only "out of date" would
  throw away the half that still works.
- **Which of the chosen schools report nothing at all**, by name. A student who picked four
  schools needs to know that it is *their* school that is blank; a count does not tell them
  that. Caltech reporting no test scores has to be a state the interface can draw, with a
  reason, rather than an empty cell.
- **Which schools report only partially**, kept separate from those reporting nothing,
  because a school missing one income band and a school missing all five are different
  problems and warrant different confidence.

This lives in `app/notices.py`. An area reports its own coverage gaps, since it is the only
thing that knows which schools came back empty; the route adds freshness, since that is
where the year is known. Both are rendered before the reader has had a chance to draw a
conclusion from the chart.

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

**Out of scope for the graded build, with the reason corrected:** post-graduation
earnings. v1 ruled these out as "a second data source with its own join". That was wrong —
College Scorecard is served by the *same* Urban API under a different source segment, and
joins on `unitid` like everything else. The real blockers are coverage: only 2018 returns
any rows, and `count_not_working` comes back null, so a job placement rate cannot be
computed at all rather than merely being hard. Median earnings at 6, 8 and 10 years after
entry are real and usable, and belong on the roadmap as a labelled single-year figure
rather than a headline.
