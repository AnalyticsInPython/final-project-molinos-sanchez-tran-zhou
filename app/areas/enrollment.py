"""Enrollment — who actually goes here, by race, gender, and origin.

Undergraduate headcount from IPEDS's Fall Enrollment survey
(`enrollment_headcount`, `level_of_study = 1`), broken out by `race` and
`sex`. Both dimensions are pinned to their own total (`race = 99` for the
gender split, `sex = 99` for the race/international split) rather than
summed from parts, for the same reason `selectiveness` pins `sex = 99` on
`number_enrolled_total`: IPEDS's own published total is the number the
school stands behind, and category lists have grown before (a `sex` code 3,
"Gender Not-Identified", and 9, "Unknown", exist in this endpoint's codebook
even though neither appears in this sample yet).

**The race codes are not the order you'd guess, and getting them wrong here
is a worse mistake than most in this project** — mislabelling a demographic
category is not a rounding error, it is calling one group of students by
another group's name. Verified against the Urban Institute API's own
variable metadata (`/api/v1/api-endpoint-varlist/`), not assumed from a
generic IPEDS codebook that turned out to describe a different survey's
ordering:

    1 White · 2 Black · 3 Hispanic · 4 Asian · 5 American Indian or Alaska
    Native · 6 Native Hawaiian or other Pacific Islander · 7 Two or more
    races · 8 Nonresident alien · 9 Unknown

**`Nonresident alien` is IPEDS's own term for what this page calls
"International."** It is a single bucket — no breakdown by country of
origin. That granularity exists (IIE's *Open Doors* report) but is not an
API this project can pull from; a school's page here says what share of
students are international, not where they are from.

**"Sized bar with composition" (SCOPE.md's own visualisation plan for this
area), not a same-width stacked bar.** Rice enrols 4,510 undergraduates,
Berkeley 33,715 — drawing both as full-width bars would flatten the
seven-fold size difference this area is partly about. Bar length is total
enrollment; the segments within it are that school's own composition.
"""

import sqlite3

import polars as pl

from app import codes
from app.format import percent
from app.notices import coverage_notices
from app.schools import School
from app.trend import chart as line_chart

KEY = "enrollment"
TITLE = "Enrollment"
QUESTION = "Who goes here?"
SUBJECT = "enrollment demographics"
TABLE = "enrollment_headcount"
SOURCE = "IPEDS"
TEMPLATE = "areas/enrollment.html"

# Drawn on a 24x24 grid, stroked in the caller's colour. Two figures: this
# area is about the student body, not the institution.
ICON = (
    '<circle cx="9" cy="8" r="3"/><circle cx="17" cy="9" r="2.3"/>'
    '<path d="M3 20c0-3.5 2.7-6 6-6s6 2.5 6 6"/><path d="M14.5 15c2.6.3 4.5 2.4 4.5 5"/>'
)

# Labels live in app/codes.py, shared with the retention area. Order matters
# here: it is the stacking order in the composition chart.
RACE = codes.RACE
INTERNATIONAL = 8

# A fixed qualitative colour per category, consistent across every school's
# bar and the legend — the same category must read as the same colour
# wherever it appears. Not colour-blindness-checked the way schools.py's
# palette is; nine categories side by side is past the point that survives
# a check like that regardless of which nine colours are picked.
RACE_COLOR = {
    1: "#4c78a8",
    2: "#54a24b",
    3: "#f58518",
    4: "#e45756",
    5: "#72b7b2",
    6: "#ff9da6",
    7: "#9d755d",
    8: "#b279a2",
    9: "#bab0ac",
}

QUERY = """
    SELECT unitid, race, sex, headcount
    FROM enrollment_headcount
    WHERE level_of_study = 1 AND year = {year}
"""

TREND_QUERY = """
    SELECT year, unitid, race, sex, headcount
    FROM enrollment_headcount
    WHERE level_of_study = 1 AND race IN (8, 99) AND sex IN (2, 99)
      AND year BETWEEN {first} AND {last}
"""


def year_meaning(conn: sqlite3.Connection, year: int, trend: bool = False) -> str:
    if trend:
        return "Each year is that autumn's headcount."
    return f"Headcount as of fall {year}."


def load(conn: sqlite3.Connection, schools: list[School], year: int) -> dict:
    """Total undergrad headcount, composition by race, and the gender split."""
    frame = pl.read_database(QUERY.format(year=int(year)), conn)
    if frame.is_empty():
        return _empty(schools)

    frame = frame.filter(pl.col("unitid").is_in([s.unitid for s in schools]))

    by_school: dict[int, list[dict]] = {}
    for r in frame.to_dicts():
        by_school.setdefault(r["unitid"], []).append(r)

    rows = []
    for school in schools:
        records = by_school.get(school.unitid, [])
        total = next(
            (r["headcount"] for r in records if r["race"] == 99 and r["sex"] == 99), None
        )
        composition = {}
        if total:
            for code in RACE:
                count = next(
                    (r["headcount"] for r in records if r["race"] == code and r["sex"] == 99),
                    None,
                )
                composition[code] = (count, round(count / total, 4)) if count is not None else None

        female = next((r["headcount"] for r in records if r["race"] == 99 and r["sex"] == 2), None)
        male = next((r["headcount"] for r in records if r["race"] == 99 and r["sex"] == 1), None)

        rows.append(
            {
                "school": school,
                "total": total,
                "composition": composition,
                "international_pct": (
                    composition.get(INTERNATIONAL)[1] if composition.get(INTERNATIONAL) else None
                ),
                "female_pct": round(female / total, 4) if female is not None and total else None,
                "male_pct": round(male / total, 4) if male is not None and total else None,
            }
        )

    missing_all = [row["school"] for row in rows if not row["total"]]
    missing_some = [
        row["school"]
        for row in rows
        if row["total"] and any(v is None for v in row["composition"].values())
    ]

    return {
        "rows": rows,
        "chart": _composition_chart(rows),
        "legend": [{"label": label, "color": RACE_COLOR[code]} for code, label in RACE.items()],
        "notices": coverage_notices(missing_all, missing_some, subject=SUBJECT, series=False),
    }


def _empty(schools: list[School]) -> dict:
    return {
        "rows": [],
        "chart": None,
        "legend": [],
        "notices": coverage_notices(list(schools), [], subject=SUBJECT),
    }


def _composition_chart(rows: list[dict]) -> dict | None:
    """One horizontal bar per school, length proportional to enrollment,
    segmented proportional to that school's own race/ethnicity composition.

    See the module docstring for why length carries size rather than every
    bar running the same width — the sevenfold gap between the smallest and
    largest school here is as much a finding as the composition is.
    """
    entries = [row for row in rows if row["total"]]
    if not entries:
        return None

    entries.sort(key=lambda row: row["total"], reverse=True)

    width, row_h = 640, 34
    label_w, right = 124, 70
    top, bottom = 10, 10
    plot_w = width - label_w - right
    largest = max(row["total"] for row in entries)

    bars = []
    for i, row in enumerate(entries):
        y = top + row_h * i
        bar_w = plot_w * (row["total"] / largest)
        segments = []
        x = float(label_w)
        for code in RACE:
            entry = row["composition"].get(code)
            if not entry:
                continue
            seg_w = bar_w * entry[1]
            if seg_w > 0.5:
                segments.append(
                    {
                        "x": round(x, 1),
                        "width": round(seg_w, 1),
                        "color": RACE_COLOR[code],
                        "label": RACE[code],
                        "pct": entry[1],
                    }
                )
            x += seg_w
        bars.append(
            {
                "name": row["school"].short,
                "y": round(y + row_h / 2 - 7, 1),
                "text_y": round(y + row_h / 2 + 4, 1),
                "segments": segments,
                "total": row["total"],
                "total_x": round(label_w + bar_w + 8, 1),
            }
        )

    return {
        "width": width,
        "height": top + row_h * len(entries) + bottom,
        "bars": bars,
        "label_x": label_w - 10,
    }


def trend(conn: sqlite3.Connection, schools: list[School], years: list[int]) -> dict:
    """International share and women's share of undergrad enrollment, over time."""
    frame = pl.read_database(
        TREND_QUERY.format(first=int(min(years)), last=int(max(years))), conn
    )
    if frame.is_empty():
        return {
            "panels": [],
            "notices": coverage_notices(list(schools), [], subject=SUBJECT, series=True),
        }

    frame = frame.filter(pl.col("unitid").is_in([s.unitid for s in schools]))
    records = frame.to_dicts()
    reported = {r["unitid"] for r in records}
    seen = {(r["unitid"], r["year"]) for r in records if r["race"] == 99 and r["sex"] == 99}

    def by_key(race: int, sex: int) -> dict:
        return {
            (r["unitid"], r["year"]): r["headcount"]
            for r in records
            if r["race"] == race and r["sex"] == sex
        }

    totals = by_key(99, 99)
    intl = by_key(INTERNATIONAL, 99)
    women = by_key(99, 2)

    def share(numerators: dict) -> dict:
        result = {}
        for key, total in totals.items():
            n = numerators.get(key)
            if n is not None and total:
                result[key] = n / total
        return result

    panels = [
        {
            "title": "International share of enrollment",
            "subtitle": "Nonresident alien undergraduates as a share of the total.",
            "chart": line_chart(schools, years, share(intl), fmt=percent),
        },
        {
            "title": "Women's share of enrollment",
            "subtitle": "Women as a share of total undergraduate enrollment.",
            "chart": line_chart(schools, years, share(women), fmt=percent),
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


COVERAGE_QUERY = """
    SELECT unitid, year FROM enrollment_headcount
    WHERE level_of_study = 1 AND race = 99 AND sex = 99 AND headcount > 0
"""


def coverage(conn: sqlite3.Connection) -> set[tuple[int, int]]:
    """Every (unitid, year) this area can render, for the year picker."""
    return {(row[0], row[1]) for row in conn.execute(COVERAGE_QUERY)}


def highlights(context: dict) -> list[str]:
    """One line naming the school with the largest international share here.

    Optional, like `trend`/`coverage` elsewhere — see financial_aid.highlights
    for the shared convention.
    """
    rows = [row for row in context.get("rows", []) if row.get("international_pct") is not None]
    if len(rows) < 2:
        return []
    most_intl = max(rows, key=lambda row: row["international_pct"])
    return [
        f"{most_intl['school'].short} has the most international students here — "
        f"{percent(most_intl['international_pct'])} of undergrads."
    ]
