# Roadmap

A running tally: what is built, what is next, what we decided not to do and why.
[PROPOSAL.md](PROPOSAL.md) says what the project is for; this says where it is.

Add to it rather than rewriting it. An idea that was rejected is worth more written
down with its reason than deleted, because the same idea comes back.

---

See also [METRICS-REVIEW.md](METRICS-REVIEW.md) — whether the numbers we show
are the ones worth knowing, checked against the data rather than assumed.

## Built

- **Ingest** — fourteen IPEDS endpoints, a year range each, into a gitignored SQLite
  build artifact. Records every endpoint-year attempted *including the empty ones*,
  which is how the app tells "IPEDS publishes nothing newer" from "we have not loaded
  it yet".
- **Picker** — searchable school combobox, per-school brand colours the user can
  override, clash detection when two colours are too close to tell apart.
- **Year control** — span buttons plus a per-year availability map, green / amber /
  grey, hover naming which school is missing what.
- **Snapshot and trend views** — no years is a snapshot of each area's newest year,
  one year pins it, two or more draw a trend across a window shared by every area.
- **Data-quality notices** — how old the figures are and which schools report nothing,
  stated above the charts rather than in a footnote.
- **Areas** — student financial aid, selectiveness, retention and graduation, after
  graduation (earnings and debt), enrollment, athletics, institution characteristics.
- **Profiles** *(Rebecca, PR #4, unmerged)* — username-only, cookie, shortlist.
- **Questionnaire** *(branch `questionnaire`, unmerged)* — sign-up questions gated by
  whether someone is pre- or post-application, and an offer comparison that prices a
  real aid letter against what the school usually gives at that income.

---

## Next

Ordered by value per hour. Build downward.

### Areas

1. ~~**Retention and graduation.**~~ **Built.** Four-year against six-year completion,
   and the share of a first-year class that does not come back. It was first built
   around the Pell gap and a by-race spread; both were cut on 3 Sep 2026 — Pell because
   it is not a question this tool's users are asking, race because a breakdown nobody
   asked for was leading the area. The by-race data was the best in the project, though
   (Michigan is 83% for Black students against 95% for Asian, behind 93% overall), and
   it is the first case for [Cuts](#cuts--breaking-a-metric-out-by-who-you-are) below.
2. **Student charges.** Cheapest to build; joins the table financial aid already reads.
   Sticker against net at the lowest band: Penn is $83,298 published against $344 paid.
   **Decide first:** `tuition_type` 2/3/4 is in-district / in-state / out-of-state, and
   the four publics differ by $38,000 between them. A profile's home state settles it
   for a signed-in user; something has to be picked for everyone else.
3. **Majors.** 145,620 rows of `completions_cip_2` sitting unused. `award_level = 7` is
   Bachelor's, and the totals row is `cipcode = 990000` — exclude it or every school
   double-counts.
4. **Enrollment / demographics** *(in flight, branch `enrollment-demographics-area`)*.
5. **Institution characteristics.** Reference table, no analysis, cheap to ship.

### Questionnaire

- **Intended major** *(pre-application)*. The strongest metric not yet collected.
  Answers "does this school actually graduate people in the thing I want" — Michigan
  awards 1,142 computer science degrees a year, Dartmouth around 90. Needs 2-digit CIP
  labels hardcoded, roughly 38 of them.
- **Early decision intent** *(pre-application)*. ED admit rates run several times
  higher, and ED is binding — a student who applies ED cannot use the offer comparison
  at all. Worth surfacing as a tradeoff rather than a checkbox.
- **Whether they will submit scores** *(pre-application)*. Submission rates run 26–49%
  at these schools, so "should I send this 1480" is a live question the percentile data
  answers.
- **On-campus or commuting** *(post-application)*. `living_arrangement` changes the
  cost of attendance the discount is measured against. Mechanically identical to
  `home_state`, which is already done.
- **Is the aid renewable** *(post-application)*. IPEDS cannot answer it. Asking makes
  the student go and check, which is the useful part.

### Athletics — a third source, and the widest spread we have found

Scoped 2 Sep 2026 while pulling athletics data for an unrelated piece of work. The
headline metric a prospective athlete wants is **what share of the student body is a
varsity athlete**, and it separates schools harder than anything else in the project:
**2.1% at UCLA to 26.6% at Caltech**, a twelve-fold range, against graduation rates that
span 91–98% across the same 25 schools.

**It is not in IPEDS.** IPEDS carries only membership flags — `member_ncaa`,
`conf_number_football` and similar in `institutional-characteristics`. No participation,
no athletics money.

**It is also not a scrape.** It is EADA, the Equity in Athletics Disclosure Act
collection, published as bulk files by the Department of Education:

    https://ope.ed.gov/athletics/api/dataFiles/file?fileName=EADA_2024-2025.zip

- `instLevel.xlsx` — one row per institution, 168 columns
- `schools.xlsx` — one row per sport per institution
- 2,037 institutions in 2024-25; **25/25 of our sample**, joined on `unitid`
- Survey years 2003 through 2025, one zip each

Do **not** use EADA's own JSON API for this: it ignores its year parameter entirely, so
`?year=2020` and `?surveyYear=2020` both return the newest survey. The bulk files are the
only route to history.

Metrics worth building, all from `instLevel.xlsx`:

| Metric | Why it earns its place |
| --- | --- |
| Athlete share of the student body | `UNDUP_CT_PARTIC_MEN + _WOMEN` over `EFTotalCount`. The headline. |
| Athletic aid per athlete | $0 to ~$54,000. Encodes scholarship policy, not just money. |
| Men's / women's participation and aid split | The Title IX comparison, already computed in the file. |
| Sports offered | From `schools.xlsx`, one row per sport. |
| NCAA classification | `classification_name`, e.g. "NCAA Division I-FCS". |

Four traps, each of which produces a plausible wrong number:

- **`PARTIC_*` double-counts multi-sport athletes; `UNDUP_CT_PARTIC_*` does not.** A
  cross-country runner who also runs track appears twice in the first. Using the wrong one
  overstates Furman's athlete share as 19.6% when it is 15.9% — one in five rather than
  one in six.
- **$0 athletic aid is a reported value, not a missing one.** Across 2,037 institutions
  the column is 1,366 positive, 671 exactly zero and never null. The zeros are almost all
  Division III (223 of 235 D-III-with-football) plus the Ivy League, none of which awards
  athletic scholarships. Treating $0 as missing deletes a real and decision-changing fact:
  an Ivy at $0 means need-based aid only.
- **Revenues always equal expenses.** Institutional support is booked as revenue, so every
  filing balances and EADA's own summary line reads $0. **EADA cannot show an athletics
  deficit** and nothing built from it may imply one.
- **`EFTotalCount` is EADA's own full-time undergraduate count**, not an IPEDS figure.
  Use it as the denominator so the ratio is internally consistent, and label it as EADA's.

Cost: xlsx-in-zip rather than JSON, so the ingest needs `openpyxl` and a second fetch
shape. That is the only structural difference — the join key and the per-year table
pattern are identical to what `import_ipeds.py` already does.

### Infrastructure

- **Per-area ingest years.** Several endpoints run to 2023 or 2024 and are pulled to
  2024 already, but anything added later should not inherit a hardcoded anchor.
- **A stratified sample.** The peer-group comparison in PROPOSAL.md cannot be exercised
  on 25 selective schools — graduation rates span 91–98%, which is no spread at all.
  Needs open-access institutions in the sample before that analysis means anything.
- **README currency.** It has drifted behind twice now.

---

## Parking lot

Not rejected, just not now.

- ~~**Post-graduation earnings** via the Urban API.~~ **Built, by a different route.**
  The Urban path is the wrong one — it serves a single 2018 snapshot. `app/areas/outcomes.py`
  calls the College Scorecard API directly instead and gets current pooled cohorts. The
  placement-rate finding still stands: `count_not_working` is null, so no such rate can be
  computed from any route.
- **Loan default rate.** `scorecard/default`, one row per school, near-free to add.
- **Athletics deficit / institutional subsidy.** Not in EADA, not in IPEDS, not in any
  federal collection. It lives only in a university's audited financial statements or its
  IRS Form 990. Worth writing down so nobody goes looking for it twice.
- **Endowment per student.** `nacubo/endowments`. Explains *why* a school can discount
  to near zero.
- **Missing-data summary block.** A standing list of every gap, complementing the
  per-year hover. Scope it to selected schools and areas or it becomes a wall of text.
- **Saved comparisons.** PROPOSAL.md floats analysing which schools users weigh against
  each other. Needs traffic to be worth anything.

---

## Decided against

- **Academic libraries.** Harvard holds 14.5M physical books to MIT's 1.3M but reports
  786k circulations to MIT's 6.3M. That is a difference in counting method, not in use,
  and publishing the columns side by side invites a comparison the data does not
  support.
- **Campus photos.** IPEDS has none; sourcing them means per-image licensing or
  copyright infringement, and no decision changes because someone saw a quad. The job a
  photo would do — helping the eye track which column is which school — is done by the
  colour chips.
- **Average admitted GPA.** IPEDS does not collect it. `reqt_hs_gpa` is a flag for
  whether a school *requires* one, not a value. It lives in the Common Data Set, which
  is not a public API.
- **Merit versus need-based aid.** IPEDS reports institutional grant aid as one figure
  with no split. Publishing a merit share would mean inventing it.
- **A GMAT field.** This tool compares undergraduate institutions on undergraduate
  data. A GMAT score has no counterpart in any table here.
- **Extrapolating a current net price.** The trend invites it and aid policy moves
  discontinuously. Draw the trend, draw the gap, let the eye finish it — do not print a
  number IPEDS never published.

---

## Open decisions

Someone has to choose. Listed with a recommendation, not a decision.

| Question | Recommendation |
| --- | --- |
| Areas as a dropdown or a plain list? (PR #5 removes the dropdown) | Unresolved. Rebecca's PR is open against a dropdown that was explicitly asked for. |
| Should profiles have a password? | **Yes, before the demo.** See below. |
| Which tuition type for a signed-out user? | Out-of-state, and say so. It is the figure that is wrong for fewer people. |
| Does the comparison screen ask for income up front? | Already answered by showing all five bands, but never decided deliberately. |

---

## Known constraints

The things that produce a plausible-looking wrong answer rather than an error.

- **Every ingest table holds many years. Every query needs a year filter.** Without one
  a pivot silently averages a decade and still returns a believable number.
- **Negative values are sentinels (-1, -2, -3) — except `net_price`,** where a negative
  is real and means grant aid exceeded the cost of attendance. Drop the exact sentinels,
  never "anything below zero".
- **The API's schema drifts between years.** `directory` gains Carnegie 2025 columns
  partway along the range; `sex` runs `[1, 2, 99]` through 2021, gains 9 in 2022 and 3
  in 2023. Pin the total, never sum the parts, and take table columns as the union
  across years.
- **`number_enrolled_pt` is a sentinel at 13 of 25 schools.** Deriving enrolments as
  full-time plus part-time is wrong in the third significant figure — enough to reorder
  schools, small enough to pass review.
- **Rates are fractions.** `completion_rate_150pct` is 0.98, not 98.
- **The endpoints paginate at 10,000 rows.** Small result sets arrive whole, which makes
  it look like they do not. Follow `next` and assert against the reported `count`.

---

## Risk worth naming

The profile is a username in a cookie with **no password**. It now holds a home state,
an income bracket, race, gender, GPA, and — since the questionnaire — actual financial
aid packages. Anyone who types a username sees all of it.

That was a deliberate call for a class project, and it is a much larger call than it was
when the profile held a shortlist and a test score. An aid letter is the most sensitive
thing in the app. Either add a signed cookie or drop the sensitive fields before anyone
demonstrates this in a room; showing a classmate's race and aid package by typing their
name is the kind of thing that is remembered.

It also cuts against the project's own argument. This tool's credibility rests on being
straight with families about money.
