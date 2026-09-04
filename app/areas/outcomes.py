"""After graduation — what alumni go on to earn, and what they still owe.

IPEDS answers what a family pays. It has nothing on what that payment buys:
no school in this database reports what its own graduates earn. This area
closes that loop with the College Scorecard API (ed.gov / Treasury / NSLDS),
joined on `unitid` — Scorecard's institution id IS the IPEDS unitid, so no
crosswalk is needed.

**The three numbers are three different cohorts, not one graduating class.**
Checked against the Scorecard data dictionary's cohort map, all three land in
the same "most recent" release but describe different people:

- `median_debt` is FY2020-21 completers who borrowed.
- `earnings_6yr` tracks students who *entered* college in 2013-15, earnings
  measured in 2020-21.
- `earnings_10yr` tracks students who entered in 2009-11, also measured in
  2020-21.

Reading "6-year earnings" and "debt" side by side as if they described one
person is exactly the mistake this module's docstring exists to prevent.
They are the best available proxies for the same school, not a before/after
of the same cohort.

**`median_debt` is sometimes null, and that is not the same as zero.**
Caltech's is null in this sample — NSLDS suppresses a median computed from
too few borrowers, not "nobody borrowed." Rendered as a dash, never as $0.

`debt_to_earnings` is this module's one computed figure: median debt divided
by 6-year median earnings, in years. It answers a real question — "how much
of one year's early-career salary would clearing this debt take?" — that
neither raw number answers alone. Named and documented here because, like
`financial_aid.spread`, IPEDS/Scorecard does not publish it; we compute it.

**This area has no year axis, unlike the rest of this app.** `scorecard_outcomes`
is one pooled snapshot, not a range — see the cohort note above for why a
"year" would be misleading here anyway. `load` accepts a `year` argument to
satisfy the shared area contract, and ignores it; `ingest_runs` records this
table under a single year (2021) so `years_available`/`latest_year` resolve
to that one value regardless of what is pinned elsewhere on the page.

**ROADMAP.md parks this exact feature, pulled through a different route.**
Its "Parking lot" section describes fetching Scorecard data through the same
Urban Institute API this project's other ingests use, and reports that path
blocked — most fields return only a 2018 snapshot with placement rate
uncomputable. This module instead calls the College Scorecard API directly
(api.data.gov, free key or the public DEMO_KEY), which serves current pooled
cohorts through 2020-21 with no such gap. Worth a second look before this
area ships: two ingest paths for the same data is a second place for it to
drift, and the team should choose one on purpose rather than by accident.
"""

import sqlite3

import polars as pl

from app.format import money
from app.notices import coverage_notices
from app.schools import School

KEY = "outcomes"
TITLE = "After graduation"
QUESTION = "What do graduates earn, and what do they owe?"
SUBJECT = "post-graduation earnings"
TABLE = "scorecard_outcomes"
SOURCE = "College Scorecard"
TEMPLATE = "areas/outcomes.html"

# Drawn on a 24x24 grid, stroked in the caller's colour. A rising line: this
# area is about where earnings go after the school, not what happens at it.
ICON = '<path d="M3 17l6-6 4 4 8-8"/><path d="M17 7h4v4"/>'

QUERY = """
    SELECT
        unitid,
        "latest.earnings.6_yrs_after_entry.median" AS earnings_6yr,
        "latest.earnings.10_yrs_after_entry.median" AS earnings_10yr,
        "latest.aid.median_debt.completers.overall" AS median_debt
    FROM scorecard_outcomes
"""


def year_meaning(conn: sqlite3.Connection, year: int, trend: bool = False) -> str:
    """Three cohorts, none of them a graduating class — see the module docstring.

    Which entry years go with which figure, and the 2020–21 release they were
    all measured in, are in the card's footnote in templates/areas/
    outcomes.html. This line is the part a reader has to have before reading
    the chart: the three numbers are not three views of one group.
    """
    return (
        "Three different groups: earnings for those who entered in 2013–15 and 2009–11, "
        "debt for 2020–21 completers."
    )


def load(conn: sqlite3.Connection, schools: list[School], year: int) -> dict:
    """Earnings at 6 and 10 years, median debt, and the debt-to-earnings figure.

    `year` is accepted, not used — see the module docstring.
    """
    frame = pl.read_database(QUERY, conn)
    if frame.is_empty():
        return {
            "rows": [],
            "chart": None,
            "notices": coverage_notices(list(schools), [], subject=SUBJECT),
        }

    unitids = [s.unitid for s in schools]
    by_unitid = {
        row["unitid"]: row
        for row in frame.filter(pl.col("unitid").is_in(unitids)).to_dicts()
    }

    rows = []
    for school in schools:
        o = by_unitid.get(school.unitid, {})
        earnings_6yr = o.get("earnings_6yr")
        earnings_10yr = o.get("earnings_10yr")
        median_debt = o.get("median_debt")

        rows.append(
            {
                "school": school,
                "earnings_6yr": earnings_6yr,
                "earnings_10yr": earnings_10yr,
                "growth": (
                    earnings_10yr - earnings_6yr
                    if earnings_6yr is not None and earnings_10yr is not None
                    else None
                ),
                "median_debt": median_debt,
                "debt_to_earnings": (
                    round(median_debt / earnings_6yr, 1)
                    if median_debt is not None and earnings_6yr
                    else None
                ),
            }
        )

    # A missing `earnings_6yr` is the one that matters: it drives both the
    # chart and the debt ratio, so its absence is what makes the row go dark
    # rather than partially lit. A null `median_debt` alone is not a gap —
    # see the module docstring, it is NSLDS suppressing a small cohort.
    missing_all = [row["school"] for row in rows if row["earnings_6yr"] is None]
    missing_some = [
        row["school"]
        for row in rows
        if row["earnings_6yr"] is not None and row["median_debt"] is None
    ]

    return {
        "rows": rows,
        "chart": _chart(rows, lead=_lead(rows)),
        "notices": coverage_notices(missing_all, missing_some, subject=SUBJECT),
    }


def _lead(rows: list[dict]) -> set[int]:
    """The school the headline names: the highest earnings six years after entry."""
    earners = [row for row in rows if row["earnings_6yr"] is not None]
    if len(earners) < 2:
        return set()
    return {max(earners, key=lambda row: row["earnings_6yr"])["school"].unitid}


def _chart(rows: list[dict], lead: set[int] | None = None) -> dict | None:
    """One row per school: 6-year earnings to 10-year earnings, sorted by growth.

    `lead` is the school the card's headline names, marked so the template can
    draw the other rows faint — see the `.headline` note in base.html. No lead
    marks every bar instead of none: a page with one school has no sentence
    naming anybody, and drawing its only row faint would say the opposite.

    Same range-plot shape as financial_aid's primary chart — a per-school
    before/after — because the question is the same shape: how far does this
    number move, and for whom does it move furthest. Consistency here is
    deliberate: a reader who has already learned to read that chart reads
    this one for free.
    """
    pairs = [
        (row, row["earnings_6yr"], row["earnings_10yr"])
        for row in rows
        if row["earnings_6yr"] is not None and row["earnings_10yr"] is not None
    ]
    if not pairs:
        return None

    pairs.sort(key=lambda p: p[2] - p[1], reverse=True)

    # Only a school this chart actually draws can be marked on it. The
    # sentence is about six-year earnings, which a school can report without
    # the ten-year figure this chart also needs, and a chart with every row
    # faint and none at full strength says nothing at all.
    lead = (lead or set()) & {row["school"].unitid for row, _, _ in pairs}

    width, row_h = 640, 34
    left, right, top = 132, 64, 26
    bottom = 34
    height = top + row_h * len(pairs) + bottom
    plot_w = width - left - right

    low = min(lo for _, lo, _ in pairs)
    high = max(hi for _, _, hi in pairs)
    span = high - low or 1

    def x(value: float) -> float:
        return left + plot_w * (value - low) / span

    bars = []
    for i, (row, lo, hi) in enumerate(pairs):
        y = top + row_h * i + row_h / 2
        bars.append(
            {
                "name": row["school"].short,
                "y": round(y, 1),
                "label_y": round(y + 4, 1),
                "x_low": round(x(lo), 1),
                "x_high": round(x(hi), 1),
                "low": lo,
                "high": hi,
                "growth": hi - lo,
                "growth_x": round(x(hi) + 10, 1),
                "lead": not lead or row["school"].unitid in lead,
            }
        )

    ticks = []
    for step in range(5):
        value = low + span * step / 4
        ticks.append(
            {"x": round(x(value), 1), "label": money(value), "y_end": height - bottom + 6}
        )

    return {
        "width": width,
        "height": height,
        "bars": bars,
        "ticks": ticks,
        "axis_y": height - bottom + 20,
        "top": top - 8,
    }


# Every row here is already "year 2021" (see the module docstring), so
# coverage is just which schools have the one figure the chart and the debt
# ratio both depend on.
COVERAGE_QUERY = """
    SELECT unitid FROM scorecard_outcomes
    WHERE "latest.earnings.6_yrs_after_entry.median" IS NOT NULL
"""


def coverage(conn: sqlite3.Connection) -> set[tuple[int, int]]:
    """Every (unitid, year) this area can render, for the year picker."""
    return {(row[0], 2021) for row in conn.execute(COVERAGE_QUERY)}


def headline(context: dict, cut: dict | None = None) -> str | None:
    """The card's finding, in a sentence: the earnings spread, and who owes what.

    Six-year earnings rather than ten-year: it is the figure the debt ratio is
    computed against, and the one a family is asking about. The debt clause is
    added only where both schools reported a median, since a missing one means
    too few borrowers to publish rather than a school whose graduates owe
    nothing — see the module docstring.

    Scorecard carries no breakdowns here, so `cut` is always None.
    """
    earners = [row for row in context.get("rows", []) if row["earnings_6yr"] is not None]
    if len(earners) < 2:
        return None

    top = max(earners, key=lambda row: row["earnings_6yr"])
    bottom = min(earners, key=lambda row: row["earnings_6yr"])
    debts = (top["median_debt"], bottom["median_debt"])
    owing = ", with less debt" if all(d is not None for d in debts) and debts[0] < debts[1] else ""
    return (
        f"{top['school'].short} graduates earn {money(top['earnings_6yr'])} six years after "
        f"entry, {money(top['earnings_6yr'] - bottom['earnings_6yr'])} more than "
        f"{bottom['school'].short}'s{owing}."
    )
