# Metrics review — is what we show worth knowing?

Written 3 Sep 2026, against seven built areas. One question throughout: **does
this number help someone decide which school to attend?** A figure can be
accurate, correctly sourced, well drawn, and still fail that test.

Every claim below was checked against the database rather than reasoned about.
Where a fix was obvious it is already applied and noted as such; where it needs
a decision it is listed at the end.

---

## The finding that matters most

**Financial aid's single-year view is the one place in the app where the
default actively misleads, and its trend is not decoration — it is the
finding.**

Across the sample, 2015 to 2021:

| | 2015 | 2021 | Change |
| --- | ---: | ---: | ---: |
| Net price, lowest income band | $6,690 | $4,197 | **−37%** |
| Net price, highest income band | $39,180 | $44,183 | **+13%** |

Schools became dramatically cheaper for poor families and more expensive for
rich ones, over six years, consistently. That is arguably the most
decision-relevant fact in the whole dataset — it tells a low-income family the
direction of travel is in their favour and a high-income family the opposite —
and **it is completely invisible in the snapshot the page shows by default.**

The snapshot shows the spread at one moment. The trend shows the spread
*widening*. Only one of those tells you what to expect for a child starting in
2027.

This matters more here than in any other area because financial aid is the only
area that is both **five years stale and terminal** — IPEDS publishes nothing
after 2021, so a reader has no way to gauge how far off the figure is unless we
show them the slope.

**Recommendation:** financial aid should open in trend mode, not snapshot. Every
other area can keep the current default. Flagged as a decision below rather than
done, because "which view is default" is a product call.

---

## Staleness, quantified

Age alone is a weak warning. "These are 2021 figures, five years old" tells a
family the number is not current; it does not tell them what to do about it.

Published cost of attendance runs to 2023 while net price stops at 2021, so the
later years of one series can size the staleness of the other:

| Year | Average published tuition and fees |
| --- | ---: |
| 2021 | $51,635 |
| 2022 | $53,483 |
| 2023 | $55,827 |

**Applied.** The freshness notice on financial aid now reads: *"Published costs
at these schools rose about 8% between 2021 and 2023, the last year we have for
them, and have kept rising since. A 2021 net price is likely to understate what
a family pays now by at least that much."*

It reports only observed growth and deliberately does not extrapolate to 2026.
A projected figure would be the most confident-looking number on the page and
the least supported, and aid policy moves discontinuously — a school changing
its formula breaks the series outright.

---

## A correction to our own work

The offer comparison in `app/offers.py` prices a real aid letter against what a
school usually gives, and does it on **discount rate rather than dollars**,
because dollars across a five-year gap report inflation as generosity. That
reasoning holds. The word "stable" did not.

Checked 2015–2021:

| | 2015 | 2021 | Drift |
| --- | ---: | ---: | ---: |
| Discount rate, lowest band | 88.3% | 93.0% | +4.7 pts |
| Discount rate, highest band | 32.6% | 36.6% | +4.0 pts |

So the rate drifts about **0.7 points a year, consistently upward**. Over the
gap this comparison spans, expect the published rate to understate a school's
current generosity by three or four points.

That is small beside the dollar error it avoids — dollars moved 13% and 37% over
the same period — so the method stands. But it means a verdict landing within a
few points of the threshold is "about typical", not a finding. The module used a
five-point band already; its docstring now says why, and no longer claims
stability it cannot support.

---

## Single year or multi year, area by area

| Area | Latest | Age | Years held | Trend? | Verdict |
| --- | ---: | ---: | ---: | --- | --- |
| Student financial aid | 2021 | 5 | 7 | yes | **Trend should be the default.** See above. |
| Selectiveness | 2024 | 2 | 10 | yes | Correct as is. Current, and the trend adds real signal. |
| Retention and graduation | 2021 | 5 | 7 | yes | Correct as is. Now sourced from `outcome_measures`, which stops at 2021. |
| After graduation | 2021 | 5 | 1 | **no** | **Correct that it has no trend.** See below. |
| Enrollment | 2021 | 5 | 7 | yes | Under-warned. See below. |
| Athletics | 2024 | 2 | 6 | yes | Correct as is. |
| Institution characteristics | 2024 | 2 | 4 | no | Correct. Founding year does not trend. |

### Where a trend would be wrong

**After graduation is right to have no year axis, and this is worth defending
because it looks like an omission.** Its three figures describe three different
entry cohorts pooled into one release: debt is 2020–21 completers, six-year
earnings tracks students who entered in 2013–15, ten-year earnings those who
entered 2009–11. Plotting them against a year would imply a before-and-after of
one person's life. They are best-available proxies for the same institution, not
a timeline.

### Where the warning is too quiet

**Enrollment is 2021 and says nothing about it.** Five years stale, series
terminal at `level_of_study = 1`. Demographics move slowly, so the figure is
less wrong than a stale price — but "less wrong" is not "current", and a family
reading a racial composition from 2021 should know that. It inherits the generic
freshness notice and no more. Low-cost fix, listed below.

---

## Metrics we show that earn their place

Worth stating, because the review is otherwise all criticism.

**Net price, not average grant.** The financial aid area shows what families
actually pay by income band. It does *not* show average grant aid, and the
`average_grant` and `total_grant` columns sit unread in the table. That is the
right call and worth protecting: a school with a $50,000 sticker giving $30,000
average grants costs the same as one with a $30,000 sticker giving $10,000, and
the grant figures differ threefold. Average grant measures a school's pricing
strategy. Net price measures your bill. Whoever decides to "use the columns we
already pull" should be pointed at this paragraph.

**Every headline metric in the app is a gap or a rate we compute, not a number
we look up.** `spread` (financial aid), `yield` (selectiveness), `pell_gap` and
`race_range` (retention), `debt_to_earnings` (outcomes), athlete share
(athletics). In each case the published figure conceals the finding and the
computed one reveals it. That is the project's actual analytical contribution
and it is consistent across seven areas built by four people, which is more than
most of these projects manage.

**Athlete share is the widest-separating metric we have.** 2.1% at UCLA to 26.6%
at Caltech, against graduation rates that span 91–98% across the same schools.
For a recruited athlete it is close to decisive, and no ranking site shows it.

---

## Metrics that would fail the test, and are correctly absent

- **Average admitted GPA.** Not collected by IPEDS. Would have to be invented.
- **Merit versus need aid.** Reported as one lump. A merit share would be fiction.
- **Job placement rate.** `count_not_working` is null in Scorecard, so there is
  no denominator. Any rate we published would be made up.
- **Athletics revenue and expenses.** Every institution reports them equal,
  because institutional support is booked as revenue. Showing them invites a
  profit-and-loss reading the survey cannot support.
- **Academic libraries.** Harvard holds 14.5M volumes to MIT's 1.3M and reports
  786k circulations to MIT's 6.3M. That is a difference in counting, not in use.

---

## The gap nobody has filled

**No area answers "what will four years cost me in total."**

Every cost figure in the app is annual. A family deciding between two offers is
committing to four years, prices are rising 4% a year on the evidence above, and
nobody anywhere in this app multiplies. The number a family actually needs —
roughly `net price × 4`, grown at observed inflation, against `median debt at
graduation` from the outcomes area — is one join away from data we already hold,
and it is the single most decision-relevant figure missing.

It belongs in student charges, which is the last unbuilt area in `ROADMAP.md`.
That reframes it from "cheapest to build" to "the one that closes the loop."

---

## Decisions this needs

Listed rather than taken, because each is a product call.

1. **Should financial aid default to trend rather than snapshot?** Recommended
   yes. It is the only area where the default view hides the finding.
2. **Should enrollment carry a stronger staleness note than the generic one?**
   Recommended yes, one sentence.
3. **Should student charges be built around four-year total cost** rather than
   annual sticker-versus-net? Recommended yes — it is the gap above.
4. **Two ingest paths now reach College Scorecard.** Resolved in favour of the
   direct API; `ROADMAP.md`'s parking-lot entry describing the Urban route as
   the plan is now stale and should be corrected.
