"""Retention and graduation — whether students finish, and how long it takes.

The published graduation rate is measured at six years, and quoting it alone
hides a year of tuition. Stanford graduates 74.0% of a cohort in four years and
95.2% in six: **one student in five takes a fifth or sixth year**, at a school
charging around $60,000 a year. Notre Dame's gap is 3.7 points. Both schools
advertise a mid-nineties graduation rate and they are not selling the same
thing.

So the computed metrics are:

- `took_longer` — the six-year rate minus the four-year rate. The share of a
  cohort that finishes, but not on time. Neither IPEDS nor anyone else
  publishes it.
- `race_range` — the distance between the best and worst reported racial group
  at that school, on the six-year rate. Not an average: the point is the spread
  the headline conceals. Michigan graduates 93% overall, 83% of its Black
  students and 95% of its Asian ones.

**The four-year rate has to be derived, and from a second table.** `grad_rates`
carries a `completers_100pct` column that is the missing sentinel in all 225
rows of this sample, so on-time completion is unavailable there. It comes from
`outcome_measures` instead — where `completion_rate_4yr` is *also* unusable,
reading 0 for every institution, so the rate is computed from `award_bach_4yr`
over `cohort_adj`. That derivation was checked by computing the six-year rate
the same way and comparing it to the published `completion_rate_6yr`: they
agree in 74 of 74 rows.

**Four traps here, and the last two would both have shipped.**

Sentinels first: -1, -2 and -3 mean missing, and part-time retention is almost
entirely sentinel across this sample, which is why only full-time retention
(`ftpt = 1`) is read. Rates are fractions — 0.93, not 93.

The third is a cohort too small to carry a rate. Michigan reports 33%
completion for American Indian or Alaska Native students, which sounds like
the worst equity gap in the sample and is one student out of three not
finishing. Computing a range across that produced a 62-point spread where the
real one is 12. Any group below `MIN_COHORT` is dropped and the reader is told
how many were dropped, because silently excluding people is its own kind of
lie. The same floor applies to the completion cohorts themselves.

The fourth is subtler. `grad_rates` breaks out by race, and two of its
categories are not races: code 8 is international students and code 9 is
"race/ethnicity unknown". Both are artefacts of how a registrar recorded
someone. A range computed across all nine categories measures reporting
practice as much as student outcomes, and at several schools the widest gap
turns out to sit between "unknown" and everyone else, which says nothing about
the school at all. `codes.NOT_AN_IDENTITY` excludes them, and there is a test
named after it.
"""

import sqlite3

import polars as pl

from app import codes
from app.format import percent
from app.notices import Notice, coverage_notices
from app.schools import School
from app.trend import chart as line_chart

KEY = "retention"
TITLE = "Retention and graduation"
QUESTION = "Will I finish here, and how long will it take?"
SUBJECT = "graduation rates"
TABLE = "outcome_measures"
TEMPLATE = "areas/retention.html"

# A figure crossing a line.
ICON = (
    '<path d="M5 20V4"/><path d="M5 5h10l-1.5 3L15 11H5"/>'
    '<path d="M19 4v16"/>'
)

# outcome_measures repeats each school across three dimensions. class_level 1
# is students entering for the first time — the cohort the published rate
# describes; 2 is transfers and 99 pools them. ftpt 1 is full-time,
# fed_aid_type 99 is all aid types. Together they pick exactly one row per
# school-year, which is checked in the tests.
FIRST_TIME, FULL_TIME, ANY_AID = 1, 1, 99

# Missing and not-applicable. Unlike net price, no completion rate is
# meaningfully negative.
SENTINELS = [-1, -2, -3]

# Smallest cohort a percentage is reported from. Below this a rate is one or
# two students' outcomes wearing a percent sign: Michigan's three American
# Indian or Alaska Native students produce "33%", which moves 33 points if a
# single person's result changes. Thirty is the conventional floor for
# reporting a rate and is applied to every breakdown in this area.
MIN_COHORT = 30

# completion_rate_4yr is published and unusable — it reads 0 for every
# institution in every year of this sample. The award counts behind it are
# sound, so both rates are computed from them.
COMPLETION_QUERY = """
    SELECT unitid,
           cohort_adj      AS cohort,
           award_bach_4yr  AS finished_4yr,
           award_bach_6yr  AS finished_6yr
    FROM outcome_measures
    WHERE year = {year} AND ftpt = 1 AND fed_aid_type = 99 AND class_level = 1
"""

RACE_QUERY = """
    SELECT unitid, race, completion_rate_150pct AS rate, cohort_adj_150pct AS cohort
    FROM grad_rates
    WHERE subcohort = 99 AND sex = 99 AND year = {year}
"""

RETENTION_QUERY = """
    SELECT unitid, retention_rate AS rate
    FROM fall_retention
    WHERE ftpt = 1 AND year = {year}
"""

TREND_QUERY = """
    SELECT year, unitid,
           cohort_adj     AS cohort,
           award_bach_4yr AS finished_4yr,
           award_bach_6yr AS finished_6yr
    FROM outcome_measures
    WHERE ftpt = 1 AND fed_aid_type = 99 AND class_level = 1
      AND year BETWEEN {first} AND {last}
"""

# The cohort floor belongs here too, or the picker offers a green year and the
# reader clicks through to a blank row.
COVERAGE_QUERY = """
    SELECT unitid, year
    FROM outcome_measures
    WHERE ftpt = 1 AND fed_aid_type = 99 AND class_level = 1
      AND cohort_adj >= 30
      AND award_bach_4yr > 0 AND award_bach_6yr > 0
"""


def _clean(frame: pl.DataFrame, column: str = "rate") -> pl.DataFrame:
    return frame.with_columns(
        pl.when(pl.col(column).is_in(SENTINELS))
        .then(None)
        .otherwise(pl.col(column))
        .alias(column)
    )


def load(conn: sqlite3.Connection, schools: list[School], year: int) -> dict:
    """On-time and eventual completion, the spread by race, and retention."""
    finishing = pl.read_database(COMPLETION_QUERY.format(year=int(year)), conn)
    if finishing.is_empty():
        return {
            "rows": [],
            "gap_chart": None,
            "range_chart": None,
            "notices": coverage_notices(list(schools), [], subject=SUBJECT),
        }

    races = _clean(pl.read_database(RACE_QUERY.format(year=int(year)), conn))
    retention = _clean(pl.read_database(RETENTION_QUERY.format(year=int(year)), conn))

    # A rate is only kept if enough people stand behind it.
    completion = {
        r["unitid"]: r
        for r in finishing.to_dicts()
        if (r["cohort"] or 0) >= MIN_COHORT
        and (r["finished_4yr"] or 0) > 0
        and (r["finished_6yr"] or 0) > 0
    }
    by_school = {r["unitid"]: r["rate"] for r in retention.to_dicts()}

    # Only groups that describe a student rather than a reporting artefact.
    groups: dict[int, dict[int, float]] = {}
    suppressed: dict[int, int] = {}
    for record in races.to_dicts():
        race, rate, cohort = record["race"], record["rate"], record["cohort"] or 0
        if rate is None or race == codes.TOTAL or race in codes.NOT_AN_IDENTITY:
            continue
        if cohort < MIN_COHORT:
            suppressed[record["unitid"]] = suppressed.get(record["unitid"], 0) + 1
            continue
        groups.setdefault(record["unitid"], {})[race] = rate

    rows = []
    for school in schools:
        uid = school.unitid
        done = completion.get(uid)
        rate_4yr = done["finished_4yr"] / done["cohort"] if done else None
        rate_6yr = done["finished_6yr"] / done["cohort"] if done else None
        spread = groups.get(uid, {})

        best = max(spread.items(), key=lambda kv: kv[1]) if spread else None
        worst = min(spread.items(), key=lambda kv: kv[1]) if spread else None

        rows.append(
            {
                "school": school,
                "cohort": done["cohort"] if done else None,
                "rate_4yr": rate_4yr,
                "rate_6yr": rate_6yr,
                # The computed metric: finishes, but not on time.
                "took_longer": (
                    rate_6yr - rate_4yr
                    if rate_4yr is not None and rate_6yr is not None
                    else None
                ),
                "retention": by_school.get(uid),
                "groups": spread,
                "best": {"race": codes.RACE.get(best[0]), "rate": best[1]} if best else None,
                "worst": {"race": codes.RACE.get(worst[0]), "rate": worst[1]} if worst else None,
                "race_range": (best[1] - worst[1]) if best and worst else None,
                "suppressed": suppressed.get(uid, 0),
                "groups_shown": len(spread),
            }
        )

    missing = [r["school"] for r in rows if r["took_longer"] is None]
    partial = [
        r["school"]
        for r in rows
        if r["took_longer"] is not None
        and (r["race_range"] is None or r["retention"] is None)
    ]

    notices = coverage_notices(missing, partial, subject=SUBJECT)

    # Say what was left out. A range drawn over five groups when the school
    # reports seven is a different claim from one drawn over all seven, and the
    # reader cannot tell which they are looking at unless we say.
    dropped = [r for r in rows if r["suppressed"]]
    if dropped:
        names = ", ".join(f"{r['school'].short} ({r['suppressed']})" for r in dropped)
        notices.append(
            Notice(
                "info",
                f"Some racial groups are too small to report a rate for and are left out "
                f"of the range below — fewer than {MIN_COHORT} students in the cohort, "
                f"where one person finishing or not moves the percentage by tens of "
                f"points. Groups omitted: {names}.",
            )
        )

    return {
        "rows": rows,
        "gap_chart": _gap_chart(rows),
        "range_chart": _range_chart(rows),
        "notices": notices,
    }


def _gap_chart(rows: list[dict]) -> dict | None:
    """Four-year against six-year completion, widest gap first.

    A paired dot rather than two bars: the finding is the distance between the
    two, and a bar chart of 74% against 95% invites reading the taller bar as
    the answer when the space between them is the point.
    """
    pairs = [r for r in rows if r["took_longer"] is not None]
    if not pairs:
        return None
    pairs.sort(key=lambda r: r["took_longer"], reverse=True)

    width, row_h = 640, 32
    left, right, top, bottom = 136, 70, 26, 34
    height = top + row_h * len(pairs) + bottom
    plot_w = width - left - right

    values = [v for r in pairs for v in (r["rate_4yr"], r["rate_6yr"])]
    low = min(values) - 0.04
    high = min(max(values) + 0.02, 1.0)
    span = high - low or 1

    def x(value: float) -> float:
        return left + plot_w * (value - low) / span

    bars = []
    for i, row in enumerate(pairs):
        y = top + row_h * i + row_h / 2
        bars.append(
            {
                "name": row["school"].short,
                "y": round(y, 1),
                "text_y": round(y + 4, 1),
                "x_four": round(x(row["rate_4yr"]), 1),
                "x_six": round(x(row["rate_6yr"]), 1),
                "four": percent(row["rate_4yr"], 0),
                "six": percent(row["rate_6yr"], 0),
                "gap": f"{row['took_longer'] * 100:+.0f} pts",
                "gap_x": round(x(row["rate_6yr"]) + 10, 1),
            }
        )

    ticks = [
        {"x": round(x(low + span * i / 4), 1), "label": percent(low + span * i / 4, 0),
         "y_end": height - bottom + 6}
        for i in range(5)
    ]

    return {
        "width": width,
        "height": height,
        "bars": bars,
        "ticks": ticks,
        "axis_y": height - bottom + 20,
        "top": top - 8,
        "label_x": left - 14,
    }


def _range_chart(rows: list[dict]) -> dict | None:
    """How far six-year completion spreads across racial groups in one school.

    The school's own six-year rate is drawn on the same row as a hollow marker,
    because the point is that it sits inside a range it does not describe. Both
    this and the marker are 150%-of-normal-time rates, so they are the same
    measure — pairing the range with the four-year rate would compare two
    different things.
    """
    entries = [r for r in rows if r["race_range"] is not None]
    if not entries:
        return None
    entries.sort(key=lambda r: r["race_range"], reverse=True)

    width, row_h = 640, 32
    left, right, top, bottom = 136, 70, 26, 34
    height = top + row_h * len(entries) + bottom
    plot_w = width - left - right

    values = [v for r in entries for v in r["groups"].values()]
    low = min(values) - 0.04
    high = min(max(values) + 0.02, 1.0)
    span = high - low or 1

    def x(value: float) -> float:
        return left + plot_w * (value - low) / span

    bars = []
    for i, row in enumerate(entries):
        y = top + row_h * i + row_h / 2
        bars.append(
            {
                "name": row["school"].short,
                "y": round(y, 1),
                "text_y": round(y + 4, 1),
                "x_low": round(x(row["worst"]["rate"]), 1),
                "x_high": round(x(row["best"]["rate"]), 1),
                "x_headline": round(x(row["rate_6yr"]), 1) if row["rate_6yr"] else None,
                "dots": [
                    {"x": round(x(rate), 1), "label": f"{codes.RACE[code]}: {percent(rate, 0)}"}
                    for code, rate in sorted(row["groups"].items())
                ],
                "range": f"{row['race_range'] * 100:.0f} pts",
                "range_x": round(x(row["best"]["rate"]) + 10, 1),
                "worst": row["worst"],
                "best": row["best"],
            }
        )

    ticks = [
        {"x": round(x(low + span * i / 4), 1), "label": percent(low + span * i / 4, 0),
         "y_end": height - bottom + 6}
        for i in range(5)
    ]

    return {
        "width": width,
        "height": height,
        "bars": bars,
        "ticks": ticks,
        "axis_y": height - bottom + 20,
        "top": top - 8,
        "label_x": left - 14,
    }


def trend(conn: sqlite3.Connection, schools: list[School], years: list[int]) -> dict:
    """On-time and eventual completion over time, and the distance between."""
    frame = pl.read_database(
        TREND_QUERY.format(first=int(min(years)), last=int(max(years))), conn
    )
    if frame.is_empty():
        return {
            "panels": [],
            "notices": coverage_notices(list(schools), [], subject=SUBJECT, series=True),
        }

    frame = frame.filter(pl.col("unitid").is_in([s.unitid for s in schools]))

    four, six, later = {}, {}, {}
    reported, seen = set(), set()
    for r in frame.to_dicts():
        cohort = r["cohort"] or 0
        if cohort < MIN_COHORT or not r["finished_4yr"] or not r["finished_6yr"]:
            continue
        key = (r["unitid"], r["year"])
        reported.add(r["unitid"])
        seen.add(key)
        four[key] = r["finished_4yr"] / cohort
        six[key] = r["finished_6yr"] / cohort
        later[key] = six[key] - four[key]

    panels = [
        {
            "title": "Finishing in four years",
            "subtitle": "The share of a cohort graduating on time.",
            "chart": line_chart(schools, years, four, fmt=lambda v: percent(v, 0)),
        },
        {
            "title": "Finishing in six",
            "subtitle": "The rate schools usually advertise.",
            "chart": line_chart(schools, years, six, fmt=lambda v: percent(v, 0)),
        },
        {
            "title": "Taking longer than four years",
            "subtitle": (
                "The distance between the two. A widening gap is more students "
                "paying for a fifth year."
            ),
            "chart": line_chart(schools, years, later, fmt=lambda v: percent(v, 0)),
        },
    ]

    missing_all = [s for s in schools if s.unitid not in reported]
    missing_some = [
        s
        for s in schools
        if s.unitid in reported and any((s.unitid, y) not in seen for y in years)
    ]

    return {
        "panels": [p for p in panels if p["chart"]],
        "notices": coverage_notices(
            missing_all, missing_some, subject=SUBJECT, series=True
        ),
    }


def coverage(conn: sqlite3.Connection) -> set[tuple[int, int]]:
    """Every (unitid, year) this area can render, for the year picker."""
    return {(row[0], row[1]) for row in conn.execute(COVERAGE_QUERY)}
