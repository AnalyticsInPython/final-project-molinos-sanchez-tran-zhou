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

## Cuts — breaking a metric out by who you are

Proposed 3 Sep 2026. **Nothing here is built**; it is a design waiting for a decision.
The by-race completion spread that was cut from retention the same day is the first case
and the reason this section exists.

A *cut* is the same metric, at the same school, in the same year, reported for one group
of students rather than all of them: the six-year completion rate for Black students at
Michigan (83%) rather than for everyone (93%). Nothing is estimated. IPEDS surveys
already report most figures by group; a cut is choosing to show one of those rows. The
UI should never use the word — it says **Show by race** when the reader asks, and
**for students like you** when the profile does the asking.

### The two ways one appears

The request was that a breakdown by race should only show up if the student asks for it,
or if the tool knows their race and can be more precise on their behalf. That is two
triggers for one mechanism:

1. **Asked for.** A row of chips in an area's header — *Show by: sex · race · how you
   entered* — listing only the dimensions that area's own table carries. Picking one
   redraws the area with every group beside the total. Nothing is pre-selected.
2. **Offered.** A signed-in profile with a value on a dimension the area supports gets
   that cut applied on arrival, with the reader's own group emphasised and the rest
   faded. It is labelled (*Showing Hispanic students — everyone · hide*), removed with
   one click, and the removal is remembered on the profile.

Both set the same URL parameter — `cut=race` for the full breakdown, `cut=race:3` to
emphasise one group. The profile only supplies a default. That keeps the state
shareable, keeps tests trivial, and means the second trigger is one line in `main.py`
once the first exists.

### What the tables actually carry

Checked against the database on 3 Sep 2026, not the codebooks.

| Area | Table | Groups the table reports | Same cohort as the headline? |
| --- | --- | --- | --- |
| Selectiveness | `admissions_enrollment` | sex | **Yes** — one table, one row per sex |
| Retention and graduation | `outcome_measures` | first-time vs transfer-in (`class_level`); Pell / direct loan / neither | **Yes** |
| | `grad_rates` | race, and race × sex (150%-of-time rate) | **No** — a different survey with its own cohort |
| | `fall_retention` | full- or part-time only | no identity cut exists |
| Financial aid | `sfa_grants_and_net_price` | income band (already the area's axis); residency | **Yes** |
| Enrollment | `enrollment_headcount` | race, sex | it *is* the cut — a share of the student body |
| After graduation | College Scorecard | sex, income tercile, first-generation, Pell; field of study | **No** — see the Scorecard trap below |
| Athletics | EADA | sex | **Yes** — men's and women's columns in one row |
| Majors *(unbuilt)* | `completions_cip_2` | field, race, sex | **Yes** |

Watch `sex` in admissions: codes are `1, 2, 99` through 2021, then `9` appears in 2022
and `3` in 2023. Pin the total, never sum the parts — the same rule selectiveness already
follows.

### The numbers that make it worth doing

- **Admit rate by sex, 2024.** Carnegie Mellon admits 9.8% of men and 14.7% of women.
  MIT 3.5% and 6.8%; Caltech 1.8% and 4.3%; Berkeley 9.0% and 12.8%. Brown runs the
  other way, 7.0% and 4.4%. All 25 schools report both. This is the cheapest cut in the
  project — same table as the headline, no cohort question — and the one with the widest
  audience, since every applicant has a sex code in IPEDS and only some will enter a race.
- **Six-year completion by race, 2023.** Berkeley graduates 78% of its Black students
  against 93% overall (118 in the cohort); Michigan 83% against 93% (263); Georgetown 85%
  against 95%. UNC reports 73% for 30 American Indian students against 91%. Same finding
  the old chart showed, but this time the reader chose to look.
- **Athletic aid by sex, 2024.** Vanderbilt spends $59,796 per male athlete and $36,110
  per female athlete. Already computed in the EADA file; no work beyond a chip.
- **Field of study, the one that dwarfs the rest.** Michigan's bachelor's programmes
  report median earnings two years after completion from **$16,169** (CIP 2605, 28
  awards) to **$94,281** (computer science, 1,215 awards); 57 of its 88 bachelor's
  programmes carry the figure. The whole 25-school headline runs $57,057 (UNC) to
  $132,140 (Caltech). Major spreads earnings inside one school nearly as far as the
  school does across the entire sample. It needs *intended major* on the questionnaire,
  which is already the first item on that list.
- **Transfer-in completion, 2021.** Carnegie Mellon reports 20% of its 80 full-time
  transfer entrants finishing in six years against 93% of first-time entrants; Michigan
  90% against 93%. The CMU figure is either the most important number in the area for a
  transfer student or an artefact of how CMU files, and nothing in the table says which.
  That is what a cut does: it surfaces a row nobody was reading, and someone has to
  check it before it ships.

### The rules

Each of these was learned from a chart that would otherwise have shipped.

1. **The reference is everyone, from the same table.** A group is drawn beside that
   table's own total, never beside a headline from a different survey. The old race chart
   drew `grad_rates` dots against the `outcome_measures` six-year rate — different
   surveys, different cohort definitions — and got away with it because they happened to
   agree. When the cut's table is not the headline's, the caption says the cohort differs,
   exactly as the retention page now says of attrition against completion.
2. **Beside, never instead.** The finding is the gap. A page that replaces 93% with 83%
   has hidden the thing the reader came to see.
3. **One cut at a time.** Cells shrink fast, and IPEDS only crosses race with sex anyway.
4. **Suppress small cells and say so.** 52 of the 175 race-by-school cells in this sample
   are under `MIN_COHORT`; Caltech has four of seven. For a small group at a small school,
   *the reader's own cell being the suppressed one is the normal case*, and the page has
   to say "fewer than 30 Native American students in this cohort at Caltech — a rate
   would move several points per person" rather than fall back to the total silently.
5. **Reporting categories are not identities, except when they are yours.** International
   (8) and unknown (9) never enter a best-or-worst across groups. But IPEDS files an
   international student under 8 regardless of their race, so a profile that says
   *Nonresident* is mapped to 8 and shown that row. It is the only honest comparator.
6. **"Prefer not to say" produces nothing.** No cut, and no *add your race to see more*.
   The profile has no password; the app should not be coaxing anyone to put more in it.
7. **Describe the school, not the student.** *How Michigan does for Black students*, never
   *your odds*. A group's 78% is the school's record with that group, not a forecast
   for a reader, and copy that slides from one to the other is the fastest way to lose
   the trust the financial aid area has earned.
8. **A cut is a reported row, never an estimate.** No interpolating between income
   bands, no imputing a suppressed cell from its neighbours, no blending two surveys into
   one number. Where the survey has no row, the page has no figure.
9. **Snapshot first.** A trend with a cut is one school with a line per group, not five
   schools times seven groups. Defer it; nothing in the snapshot design blocks it.

### The Scorecard trap

The Scorecard's by-sex and by-income earnings fields are **means from a different
vintage than the headline median** and cannot be drawn against it. Michigan:
`6_yrs_after_entry.median` is $73,762; `mean_earnings.female_students` is $47,900 and
`.male_students` $64,300. A combined mean near $56,000 sitting $18,000 *below* the
median is not one cohort — earnings distributions skew the other way. The first-generation
and Pell splits come back empty for Michigan. Skip sex and income cuts on earnings
entirely; field of study is the cut that matters there, and it is a different endpoint
(`programs.cip_4_digit`, 363 rows for Michigan alone).

### What the profile can already drive

| Profile field | Cut | Note |
| --- | --- | --- |
| `race` (1–8) | race | Codes match IPEDS exactly; 8 *Nonresident* is right (see rule 5); 9 drives nothing |
| `gender` (1, 2) | sex | 0 drives nothing |
| `income_bracket` (1–5) | income band | Financial aid already draws all five bands. "You" is emphasising one — the same pattern, on a chart that exists |
| `home_state` | residency | Already planned for student charges |
| *not collected:* intended major | field of study | The largest payoff; on the questionnaire list |
| *not collected:* first-time or transfer | entrant type | One radio button; `outcome_measures` has the rows |
| *not collected:* athlete | — | No federal collection reports outcomes by athlete status. The NCAA's GSR is not public data |

### Where it lives in the code

Each area declares its cuts next to its other constants — `CUTS = {"sex": Cut(label,
query, codes, same_cohort)}` — empty for the areas that have none. `load()` grows an
optional `cut` argument. `main.py` collects them exactly as it collects `coverage()` now,
the template draws the chips from that, and the profile supplies the default. The chart is
the retention range chart turned inside out: every group a faded dot, everyone a solid
marker, the selected group in colour with the gap printed at the right. One shape serves
both triggers.

The Pell / direct-loan split lives in the same `outcome_measures` rows. It is not going
back in as a headline. Whether it earns a chip is not a decision for now.

### Order, by value per hour

1. **Sex on selectiveness.** Same table, 25 of 25, widest audience. A day. Establishes
   the chip, the URL parameter and the chart.
2. **Race on completion.** The data we already had, rebuilt under rules 1, 4 and 5. Sets
   the pattern for suppression and reference-from-same-table that every later cut copies.
3. **Profile defaults.** After 1 and 2 exist, since it is only a default for a parameter
   that already works.
4. **Entrant type on completion** — after someone has explained Carnegie Mellon's 20%.
5. **Field of study on earnings** — after intended major is on the questionnaire. The
   biggest payoff and the most work, because it is program-level rows rather than one
   more column.

Not doing: earnings by sex or income from the Scorecard (vintage mismatch); any cut
across two dimensions; any estimated cell.

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
| Does a profile apply a cut without being asked? | **Yes, visibly** — labelled, one click to remove, the removal remembered. Never for *prefer not to say*. See [Cuts](#cuts--breaking-a-metric-out-by-who-you-are). |
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
