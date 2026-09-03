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
- `left_after_year_one` — the share of a first-year class that did not come
  back for a second. The earliest signal there is, and the one that reaches a
  student soonest: someone who leaves in year one never appears in any
  graduation figure at all.

**Retention describes different people from the graduation figures, and the
page says so.** `fall_retention` for 2021 is the class that started in 2020 and
came back in 2021. `outcome_measures` for 2021 is the class that started in
2014 and had eight years to finish. Seven years separate them, so they cannot
be drawn as one funnel of the same cohort narrowing — which is the obvious and
wrong way to present them together. They are two facts about one school,
measured on two groups of students.

**The four-year rate has to be derived, and from a second table.** `grad_rates`
carries a `completers_100pct` column that is the missing sentinel in all 225
rows of this sample, so on-time completion is unavailable there. It comes from
`outcome_measures` instead — where `completion_rate_4yr` is *also* unusable,
reading 0 for every institution, so the rate is computed from `award_bach_4yr`
over `cohort_adj`. That derivation was checked by computing the six-year rate
the same way and comparing it to the published `completion_rate_6yr`: they
agree in 74 of 74 rows.

**Three traps here, and the last one would have shipped.**

Sentinels first: -1, -2 and -3 mean missing, and part-time retention is almost
entirely sentinel across this sample, which is why only full-time retention
(`ftpt = 1`) is read. Rates are fractions — 0.93, not 93.

The third is a cohort too small to carry a rate. A cohort of a few students
reports a plausible-looking percentage that one person's outcome moves by tens
of points, so any completion cohort below `MIN_COHORT` is treated as unreported
rather than drawn. The floor was first needed by a by-race breakdown this area
no longer shows — Michigan reported 33% completion for three American Indian
or Alaska Native students — and it stays because the completion cohorts
themselves are subject to the same arithmetic.
"""

import sqlite3

import polars as pl

from app import codes, cuts
from app.format import percent
from app.notices import coverage_notices
from app.schools import School
from app.trend import chart as line_chart

KEY = "retention"
TITLE = "Retention and graduation"
QUESTION = "Will I finish here, and how long will it take?"
SUBJECT = "graduation rates"
TABLE = "outcome_measures"
TEMPLATE = "areas/retention.html"

# A figure crossing a line.
ICON = '<path d="M5 20V4"/><path d="M5 5h10l-1.5 3L15 11H5"/><path d="M19 4v16"/>'

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

# ftpt 1 is full-time. Part-time retention is almost entirely sentinel across
# this sample, and averaging it in would report missing data as attrition.
RETENTION_QUERY = """
    SELECT unitid,
           retention_rate     AS rate,
           prev_cohort_adj    AS started,
           returning_students AS returned
    FROM fall_retention
    WHERE ftpt = 1 AND year = {year}
"""

RETENTION_TREND_QUERY = """
    SELECT year, unitid,
           retention_rate     AS rate,
           prev_cohort_adj    AS started,
           returning_students AS returned
    FROM fall_retention
    WHERE ftpt = 1 AND year BETWEEN {first} AND {last}
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


def _attrition(record: dict | None) -> float | None:
    """Share of a first-year class that did not return, from the head counts.

    Falls back to the published rate when a count is missing, since a rounded
    figure beats no figure — but the counts are preferred wherever they exist.
    """
    if not record:
        return None
    started, returned = record.get("started"), record.get("returned")
    if started and returned is not None and started > 0:
        return 1 - (returned / started)
    rate = record.get("rate")
    return 1 - rate if rate is not None else None


def _clean(frame: pl.DataFrame, column: str = "rate") -> pl.DataFrame:
    return frame.with_columns(
        pl.when(pl.col(column).is_in(SENTINELS)).then(None).otherwise(pl.col(column)).alias(column)
    )


# Six-year completion by race comes from a different survey — the Graduation
# Rates component, 150% of normal time — so the cut carries that survey's own
# total as "everyone" rather than the outcome_measures figure in the table.
# International students (8) are filed there regardless of race and are drawn
# only when the profile says Nonresident; "unknown" (9) is never drawn.
RACE_CUT_QUERY = """
    SELECT unitid, race, completion_rate_150pct AS rate, cohort_adj_150pct AS cohort
    FROM grad_rates
    WHERE year = {year} AND subcohort = 99 AND sex = 99
"""

CUTS = {
    "race": cuts.Cut(
        key="race",
        label="Race",
        metric="Six-year completion",
        groups={c: codes.RACE[c] for c in codes.RACE_ORDER if c not in codes.NOT_AN_IDENTITY},
        own_only={8: codes.RACE[8]},
        profile_field="race",
        places=0,
        count_noun="students in the cohort",
        note=(
            "From the IPEDS Graduation Rates survey: completion within six years for "
            "first-time, full-time students. A different survey from the outcome measures "
            "below, so everyone here is that survey's own total rather than the six-year "
            "figure in the table. Groups under 30 students are not drawn."
        ),
    ),
}


def _cohort_year(conn: sqlite3.Connection, table: str, year: int) -> int | None:
    """The fall the students labelled `year` actually started, as the table says."""
    row = conn.execute(
        f"SELECT cohort_year FROM {table} WHERE year = ? AND cohort_year > 0 LIMIT 1",
        (int(year),),
    ).fetchone()
    return int(row[0]) if row else None


def year_meaning(conn: sqlite3.Connection, year: int, trend: bool = False) -> str:
    """What the year on the card means here, because it is not the obvious thing.

    outcome_measures labelled 2021 follows the class that started in fall
    2014 — one class, with one cohort count, whose awards are tallied at four
    years and again at six. The natural reading, that a "2021 four-year rate"
    is the class of 2017 and the six-year rate the class of 2015, is how some
    sites present it and is wrong here: both rates share `cohort_adj`.
    fall_retention labelled 2021 follows the class that started in fall 2020.
    Neither is "students who graduated in 2021".

    `cohort_year` is the fall the class entered, checked table against table:
    Stanford's grad_rates cohort of 1,738 (cohort_year 2016) equals its fall
    2016 entrants in fall_retention exactly, and its outcome_measures cohort
    of 1,677 (cohort_year 2014) equals its fall 2014 entrants.
    """
    started = _cohort_year(conn, TABLE, year)
    if started is None and trend:
        # The window runs past this table's last year; explain the newest
        # year it does have, since that is the one the line ends on.
        row = conn.execute(
            f"SELECT year, cohort_year FROM {TABLE} WHERE cohort_year > 0 "
            "ORDER BY year DESC LIMIT 1"
        ).fetchone()
        if row:
            year, started = int(row[0]), int(row[1])
    if started is None:
        return (
            f"{year} is the year IPEDS reported these figures, "
            f"not the year the students enrolled."
        )
    if trend:
        return (
            f"Each year's graduation figures follow one class that started {year - started} "
            f"years before the label, counted at four years and again at six — {year} is the "
            f"class of fall {started}. The retention line follows the class that started the "
            f"year before each label."
        )
    return (
        f"Every graduation figure labelled {year} follows one class — students who started "
        f"in fall {started} — counted at four years and again at six. The four-year rate is "
        f"not a later class. {year} is when IPEDS reported them, not when anyone enrolled. "
        f"Left after year one is a different class: those who started in fall {year - 1} and "
        f"came back in fall {year}."
    )


def cut(
    conn: sqlite3.Connection, schools: list[School], year: int, selection: cuts.Selection
) -> dict:
    """Six-year completion by race, beside that survey's own total."""
    ids = {s.unitid for s in schools}
    started = _cohort_year(conn, "grad_rates", year)
    records = [
        r
        for r in pl.read_database(RACE_CUT_QUERY.format(year=int(year)), conn).to_dicts()
        if r["unitid"] in ids and r["rate"] is not None and r["rate"] >= 0
    ]
    return cuts.context(
        CUTS[selection.dimension],
        schools,
        records,
        code_field="race",
        value=lambda r: r["rate"],
        count=lambda r: r["cohort"] or 0,
        emphasis=selection.emphasis,
        note=(
            f"From the IPEDS Graduation Rates survey: students who started in fall {started} "
            f"and finished within six years. A different survey from the outcome measures "
            f"below, so everyone here is that survey's own total rather than the six-year "
            f"figure in the table. Groups under 30 students are not drawn."
            if started
            else None
        ),
    )


def load(conn: sqlite3.Connection, schools: list[School], year: int) -> dict:
    """On-time and eventual completion, and first-year retention."""
    finishing = pl.read_database(COMPLETION_QUERY.format(year=int(year)), conn)
    if finishing.is_empty():
        return {
            "rows": [],
            "gap_chart": None,
            "leaving_chart": None,
            "notices": coverage_notices(list(schools), [], subject=SUBJECT),
        }

    retention = _clean(pl.read_database(RETENTION_QUERY.format(year=int(year)), conn))

    # A rate is only kept if enough people stand behind it.
    completion = {
        r["unitid"]: r
        for r in finishing.to_dicts()
        if (r["cohort"] or 0) >= MIN_COHORT
        and (r["finished_4yr"] or 0) > 0
        and (r["finished_6yr"] or 0) > 0
    }
    staying = {r["unitid"]: r for r in retention.to_dicts()}

    rows = []
    for school in schools:
        uid = school.unitid
        done = completion.get(uid)
        rate_4yr = done["finished_4yr"] / done["cohort"] if done else None
        rate_6yr = done["finished_6yr"] / done["cohort"] if done else None

        rows.append(
            {
                "school": school,
                "cohort": done["cohort"] if done else None,
                "rate_4yr": rate_4yr,
                "rate_6yr": rate_6yr,
                # The computed metric: finishes, but not on time.
                "took_longer": (
                    rate_6yr - rate_4yr if rate_4yr is not None and rate_6yr is not None else None
                ),
                "retention": (staying.get(uid) or {}).get("rate"),
                # The loss, not the rate: "3% left" is the number a student is
                # asking about and 97% retention buries it.
                #
                # Computed from the counts rather than from retention_rate,
                # which IPEDS rounds to two decimals. At these schools that
                # rounding is the difference between 2.6% and 3.0% attrition —
                # a sixth of the figure, on a measure where the whole spread is
                # about five points.
                "left_after_year_one": _attrition(staying.get(uid)),
                "started": (staying.get(uid) or {}).get("started"),
                "did_not_return": (
                    staying[uid]["started"] - staying[uid]["returned"]
                    if staying.get(uid)
                    and staying[uid].get("started")
                    and staying[uid].get("returned")
                    else None
                ),
            }
        )

    missing = [r["school"] for r in rows if r["took_longer"] is None]
    partial = [r["school"] for r in rows if r["took_longer"] is not None and r["retention"] is None]

    return {
        "rows": rows,
        "gap_chart": _gap_chart(rows),
        "leaving_chart": _leaving_chart(rows),
        "notices": coverage_notices(missing, partial, subject=SUBJECT),
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
        {
            "x": round(x(low + span * i / 4), 1),
            "label": percent(low + span * i / 4, 0),
            "y_end": height - bottom + 6,
        }
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


def _leaving_chart(rows: list[dict]) -> dict | None:
    """The share of a first-year class that did not come back, worst first.

    Drawn as the loss rather than the retention rate. These schools retain
    between 93% and 99%, and a bar chart of that is five bars of identical
    length; the same data as attrition runs from 1% to 7% and separates them
    sevenfold. It is the same number either way, and only one of them is
    legible.
    """
    entries = [r for r in rows if r["left_after_year_one"] is not None]
    if not entries:
        return None
    entries.sort(key=lambda r: r["left_after_year_one"], reverse=True)

    width, row_h = 640, 26
    # The value gutter carries "3.9% — 234 of 6,072", which is the widest label
    # any chart in this app draws; 108px clipped the school with both the
    # highest attrition and the largest cohort.
    label_w, value_w = 150, 150
    top, bottom = 10, 10
    plot_w = width - label_w - value_w
    largest = max(r["left_after_year_one"] for r in entries) or 1

    bars = []
    for i, row in enumerate(entries):
        y = top + row_h * i + row_h / 2
        length = plot_w * (row["left_after_year_one"] / largest)
        count = row["did_not_return"]
        bars.append(
            {
                "name": row["school"].short,
                "color": row["school"].color,
                "y": round(y - 7, 1),
                "text_y": round(y + 4, 1),
                "width": round(max(length, 2), 1),
                "label_x": round(label_w + max(length, 2) + 8, 1),
                "value": percent(row["left_after_year_one"], 1),
                "detail": (
                    f"{count:,} of {row['started']:,}"
                    if count is not None and row["started"]
                    else ""
                ),
            }
        )

    return {
        "width": width,
        "height": top + row_h * len(entries) + bottom,
        "bars": bars,
        "label_x": label_w - 10,
        "plot_x": label_w,
    }


def trend(conn: sqlite3.Connection, schools: list[School], years: list[int]) -> dict:
    """On-time and eventual completion over time, and the distance between."""
    frame = pl.read_database(TREND_QUERY.format(first=int(min(years)), last=int(max(years))), conn)
    if frame.is_empty():
        return {
            "panels": [],
            "notices": coverage_notices(list(schools), [], subject=SUBJECT, series=True),
        }

    frame = frame.filter(pl.col("unitid").is_in([s.unitid for s in schools]))

    four, six, later = {}, {}, {}
    leaving = {}
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

    # Retention spans more years than completion does, and is its own cohort,
    # so it is queried over the same window separately rather than joined.
    span = pl.read_database(
        RETENTION_TREND_QUERY.format(first=int(min(years)), last=int(max(years))), conn
    )
    wanted = {s.unitid for s in schools}
    for r in _clean(span).to_dicts():
        value = _attrition(r)
        if value is not None and r["unitid"] in wanted:
            leaving[(r["unitid"], r["year"])] = value

    panels = [
        {
            "title": "Left after the first year",
            "subtitle": (
                "A different and more recent cohort than the completion figures "
                "below — this is last year's first-years, not the class that "
                "graduated."
            ),
            "chart": line_chart(schools, years, leaving, fmt=lambda v: percent(v, 1)),
        },
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
        s for s in schools if s.unitid in reported and any((s.unitid, y) not in seen for y in years)
    ]

    return {
        "panels": [p for p in panels if p["chart"]],
        "notices": coverage_notices(missing_all, missing_some, subject=SUBJECT, series=True),
    }


def coverage(conn: sqlite3.Connection) -> set[tuple[int, int]]:
    """Every (unitid, year) this area can render, for the year picker."""
    return {(row[0], row[1]) for row in conn.execute(COVERAGE_QUERY)}
