"""Retention and graduation — who finishes, and who does not.

The headline graduation rate is the least useful number in this dataset, and
this area exists to get past it. Michigan graduates 93% of its students. It
graduates 83% of its Black students and 95% of its Asian ones. A family reading
"93%" has been told something true and been left unable to answer the question
they actually asked, which is whether someone like their child finishes here.

So the computed metrics are both **gaps**, and neither is published:

- `pell_gap` — completion for students on a Pell grant against students on no
  federal aid at all. A proxy for whether a school supports students who
  arrive without money, once they are through the door.
- `race_range` — the distance between the best and worst reported racial
  group at that school. Not an average: the point is the spread the headline
  conceals.

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
lie. The same floor applies to the Pell comparison, whose smallest cohort in
this sample is 27.

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
QUESTION = "Do students like me come back, and finish?"
SUBJECT = "graduation rates"
TABLE = "grad_rates_pell"
TEMPLATE = "areas/retention.html"

# A figure crossing a line.
ICON = (
    '<path d="M5 20V4"/><path d="M5 5h10l-1.5 3L15 11H5"/>'
    '<path d="M19 4v16"/>'
)

# fed_aid_type in grad_rates_pell. 2 is students with subsidised loans but no
# Pell grant, which sits between the two and is not the comparison we want:
# the question is how a school does by students who arrived with nothing
# against students who needed nothing.
PELL, NO_AID, ALL_STUDENTS = 1, 3, 99

# Missing and not-applicable. Unlike net price, no completion rate is
# meaningfully negative.
SENTINELS = [-1, -2, -3]

# Smallest cohort a percentage is reported from. Below this a rate is one or
# two students' outcomes wearing a percent sign: Michigan's three American
# Indian or Alaska Native students produce "33%", which moves 33 points if a
# single person's result changes. Thirty is the conventional floor for
# reporting a rate and is applied to every breakdown in this area.
MIN_COHORT = 30

# subcohort 99 is the full cohort. Only 2 and 99 exist in this sample and they
# carry identical values, so this picks the one that means what it says.
COHORT = 99

PELL_QUERY = """
    SELECT unitid, fed_aid_type, completion_rate_150pct AS rate, cohort_rev AS cohort
    FROM grad_rates_pell
    WHERE subcohort = 99 AND year = {year}
      AND fed_aid_type IN (1, 3, 99)
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
    SELECT year, unitid, fed_aid_type, completion_rate_150pct AS rate
    FROM grad_rates_pell
    WHERE subcohort = 99 AND fed_aid_type IN (1, 3, 99)
      AND year BETWEEN {first} AND {last}
"""

# The cohort floor belongs here too, or the picker offers a green year and the
# reader clicks through to a blank row. Caltech's 2023 Pell cohort is 27
# students, so it is genuinely not renderable and must not be promised.
COVERAGE_QUERY = """
    SELECT unitid, year
    FROM grad_rates_pell
    WHERE subcohort = 99 AND fed_aid_type IN (1, 3)
      AND completion_rate_150pct NOT IN (-1, -2, -3)
      AND cohort_rev >= 30
    GROUP BY unitid, year
    HAVING COUNT(DISTINCT fed_aid_type) = 2
"""


def _clean(frame: pl.DataFrame, column: str = "rate") -> pl.DataFrame:
    return frame.with_columns(
        pl.when(pl.col(column).is_in(SENTINELS))
        .then(None)
        .otherwise(pl.col(column))
        .alias(column)
    )


def load(conn: sqlite3.Connection, schools: list[School], year: int) -> dict:
    """Completion by Pell status and by race, plus first-year retention."""
    pell = _clean(pl.read_database(PELL_QUERY.format(year=int(year)), conn))
    if pell.is_empty():
        return {
            "rows": [],
            "gap_chart": None,
            "range_chart": None,
            "notices": coverage_notices(list(schools), [], subject=SUBJECT),
        }

    races = _clean(pl.read_database(RACE_QUERY.format(year=int(year)), conn))
    retention = _clean(pl.read_database(RETENTION_QUERY.format(year=int(year)), conn))

    # A rate is only kept if enough people stand behind it.
    by_aid = {
        (r["unitid"], r["fed_aid_type"]): r["rate"]
        for r in pell.to_dicts()
        if (r["cohort"] or 0) >= MIN_COHORT
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
        pell_rate = by_aid.get((uid, PELL))
        no_aid_rate = by_aid.get((uid, NO_AID))
        headline = by_aid.get((uid, ALL_STUDENTS))
        spread = groups.get(uid, {})

        best = max(spread.items(), key=lambda kv: kv[1]) if spread else None
        worst = min(spread.items(), key=lambda kv: kv[1]) if spread else None

        rows.append(
            {
                "school": school,
                "headline": headline,
                "retention": by_school.get(uid),
                "pell": pell_rate,
                "no_aid": no_aid_rate,
                "pell_gap": (
                    no_aid_rate - pell_rate
                    if pell_rate is not None and no_aid_rate is not None
                    else None
                ),
                "groups": spread,
                "best": {"race": codes.RACE.get(best[0]), "rate": best[1]} if best else None,
                "worst": {"race": codes.RACE.get(worst[0]), "rate": worst[1]} if worst else None,
                "race_range": (best[1] - worst[1]) if best and worst else None,
                "suppressed": suppressed.get(uid, 0),
                "groups_shown": len(spread),
            }
        )

    missing = [r["school"] for r in rows if r["pell_gap"] is None]
    partial = [
        r["school"]
        for r in rows
        if r["pell_gap"] is not None and (r["race_range"] is None or r["retention"] is None)
    ]

    notices = coverage_notices(missing, partial, subject=SUBJECT)

    # Say what was left out. A range drawn over five groups when the school
    # reports seven is a different claim from one drawn over all seven, and the
    # reader cannot tell which they are looking at unless we say.
    dropped = [r for r in rows if r["suppressed"]]
    if dropped:
        names = ", ".join(
            f"{r['school'].short} ({r['suppressed']})" for r in dropped
        )
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
    """Pell against no-aid, one row per school, widest gap first.

    A paired dot rather than two bars: the finding is the distance between two
    numbers that are both in the nineties, and a bar chart of 92% against 96%
    is two bars a reader cannot tell apart.
    """
    pairs = [r for r in rows if r["pell_gap"] is not None]
    if not pairs:
        return None
    pairs.sort(key=lambda r: r["pell_gap"], reverse=True)

    width, row_h = 640, 32
    left, right, top, bottom = 136, 70, 26, 34
    height = top + row_h * len(pairs) + bottom
    plot_w = width - left - right

    values = [v for r in pairs for v in (r["pell"], r["no_aid"])]
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
                "x_pell": round(x(row["pell"]), 1),
                "x_no_aid": round(x(row["no_aid"]), 1),
                "pell": percent(row["pell"], 0),
                "no_aid": percent(row["no_aid"], 0),
                "gap": f"{row['pell_gap'] * 100:+.0f} pts",
                "gap_x": round(x(row["no_aid"]) + 10, 1),
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
    """How far completion spreads across racial groups within one school.

    The headline is drawn on the same row as a hollow marker, because the
    point is that it sits inside a range it does not describe.
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
                "x_headline": round(x(row["headline"]), 1) if row["headline"] else None,
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
    """The Pell gap over time — whether a school is closing it or not."""
    frame = _clean(
        pl.read_database(
            TREND_QUERY.format(first=int(min(years)), last=int(max(years))), conn
        )
    )
    if frame.is_empty():
        return {
            "panels": [],
            "notices": coverage_notices(list(schools), [], subject=SUBJECT, series=True),
        }

    frame = frame.filter(pl.col("unitid").is_in([s.unitid for s in schools]))
    records = frame.to_dicts()

    by_key: dict[tuple[int, int], dict[int, float]] = {}
    for r in records:
        if r["rate"] is not None:
            by_key.setdefault((r["unitid"], r["year"]), {})[r["fed_aid_type"]] = r["rate"]

    gap, pell_only, reported, seen = {}, {}, set(), set()
    for key, aid in by_key.items():
        if PELL in aid:
            pell_only[key] = aid[PELL]
            reported.add(key[0])
            seen.add(key)
        if PELL in aid and NO_AID in aid:
            gap[key] = aid[NO_AID] - aid[PELL]

    panels = [
        {
            "title": "The Pell gap over time",
            "subtitle": (
                "Completion for students on no federal aid minus students on a Pell "
                "grant. Falling is a school closing it."
            ),
            "chart": line_chart(schools, years, gap, fmt=lambda v: percent(v, 0)),
        },
        {
            "title": "Completion for students on a Pell grant",
            "subtitle": "The rate itself, not the gap.",
            "chart": line_chart(schools, years, pell_only, fmt=lambda v: percent(v, 0)),
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
