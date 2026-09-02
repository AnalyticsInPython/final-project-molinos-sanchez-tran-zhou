"""Selectiveness — how hard a school is to get into, and how badly people want in.

Two rates, and the finding is that they are close to independent.

Caltech and Stanford both admit 3.9% of applicants, which is where most
comparison tools stop. Of the students they admit, Stanford enrols 80.2% and
Caltech 52.9% — Caltech loses nearly half the people it said yes to, and sits
15th of 25 on yield while sitting joint-first on selectivity. UNC admits one in
five, five times Caltech's rate, and holds essentially the same share of its
admits. "Selective" and "wanted" are two different properties, and a school can
have a great deal of one and much less of the other.

IPEDS publishes neither rate. It publishes three counts, and both rates are
ours to compute — which is also why the denominators have to be right.

One trap, and it is the reason `number_enrolled_pt` appears nowhere below:
**13 of the 25 schools report it as -1**, the IPEDS missing sentinel. Deriving
enrolments as `number_enrolled_ft + number_enrolled_pt` therefore subtracts one
student from over half the sample, and yields a yield rate that is wrong in the
third significant figure — wrong enough to reorder schools that sit close
together, and small enough that nobody would notice. `number_enrolled_total` is
reported directly and carries no sentinels in this sample.
"""

import sqlite3

import polars as pl

from app.notices import coverage_notices
from app.schools import School

KEY = "selectiveness"
TITLE = "Selectiveness"
QUESTION = "Can I get in — and do the people who get in choose to go?"
SUBJECT = "admissions"
TABLE = "admissions_enrollment"
TEMPLATE = "areas/selectiveness.html"

# A funnel: many applications in the top, few enrolments out of the bottom.
ICON = '<path d="M3 5h18l-7 8v6l-4 2v-8z"/>'

# sex 99 is the reported total. Summing sex 1 and 2 instead would be a
# different number at some schools — Georgetown's parts fall 123 short of its
# published total — and the total is the figure the school stands behind.
# The year filter is not optional: the table holds every year we ingested.
# `{year}` is interpolated through int(), so it cannot carry anything but a
# number.
#
# Pinning sex = 99 also survives a schema change the multi-year pull exposed:
# IPEDS reported [1, 2, 99] through 2021, added 9 in 2022 and 3 in 2023. Any
# code that enumerated the categories, or summed men and women to get a total,
# would quietly change meaning partway along the series.
QUERY = """
    SELECT unitid, number_applied, number_admitted, number_enrolled_total
    FROM admissions_enrollment
    WHERE sex = 99 AND year = {year}
"""

COUNTS = ["number_applied", "number_admitted", "number_enrolled_total"]

# Missing and not-applicable. Unlike net price, no count here is meaningfully
# negative — you cannot receive minus one application.
SENTINELS = [-1, -2, -3]


def load(conn: sqlite3.Connection, schools: list[School], year: int) -> dict:
    """Applications, admits and enrolments per school, plus the two rates."""
    frame = pl.read_database(QUERY.format(year=int(year)), conn)
    if frame.is_empty():
        return _empty(schools)

    frame = frame.with_columns(
        [
            pl.when(pl.col(column).is_in(SENTINELS))
            .then(None)
            .otherwise(pl.col(column))
            .alias(column)
            for column in COUNTS
        ]
    ).filter(pl.col("unitid").is_in([s.unitid for s in schools]))

    # The computed metrics. Guarded on the denominator rather than trusted:
    # a school that reports zero applications would otherwise divide by zero,
    # and an open-admissions school reporting equal counts is a real case the
    # moment this sample widens.
    frame = frame.with_columns(
        [
            pl.when(pl.col("number_applied") > 0)
            .then(pl.col("number_admitted") / pl.col("number_applied"))
            .otherwise(None)
            .alias("admit_rate"),
            pl.when(pl.col("number_admitted") > 0)
            .then(pl.col("number_enrolled_total") / pl.col("number_admitted"))
            .otherwise(None)
            .alias("yield_rate"),
        ]
    )

    by_id = {row["unitid"]: row for row in frame.to_dicts()}
    rows = []
    for school in schools:
        record = by_id.get(school.unitid, {})
        rows.append(
            {
                "school": school,
                "applied": record.get("number_applied"),
                "admitted": record.get("number_admitted"),
                "enrolled": record.get("number_enrolled_total"),
                "admit_rate": record.get("admit_rate"),
                "yield_rate": record.get("yield_rate"),
            }
        )

    fields = ("applied", "admitted", "enrolled", "admit_rate", "yield_rate")
    missing_all = [r["school"] for r in rows if all(r[f] is None for f in fields)]
    missing_some = [
        r["school"]
        for r in rows
        if any(r[f] is None for f in fields) and not all(r[f] is None for f in fields)
    ]

    return {
        "rows": rows,
        "rates_chart": _rates_chart(rows),
        "volume_chart": _volume_chart(rows),
        "notices": coverage_notices(missing_all, missing_some, subject=SUBJECT),
    }


def _empty(schools: list[School]) -> dict:
    return {
        "rows": [],
        "rates_chart": None,
        "volume_chart": None,
        "notices": coverage_notices(list(schools), [], subject=SUBJECT),
    }


def _rates_chart(rows: list[dict]) -> dict | None:
    """Admit rate and yield side by side, rows sorted by admit rate.

    Two panels rather than one shared axis. On a common 0-100% scale the admit
    bars collapse into a stub — these schools admit between 4% and 20% — and
    the difference between 3.9% and 4.4%, which is the difference between two
    of the most selective schools in the country, becomes a rounding error on
    screen. Each panel therefore carries its own scale, stated in its heading.

    The sort is the argument. Rows run most selective first, so the admit
    column descends cleanly and the yield column beside it does not. That
    jaggedness is the finding: the two rates do not track each other.
    """
    entries = [
        row for row in rows if row["admit_rate"] is not None and row["yield_rate"] is not None
    ]
    if not entries:
        return None

    entries.sort(key=lambda row: row["admit_rate"])

    width, row_h = 640, 30
    label_w, gap, value_w = 124, 34, 44
    top, bottom = 40, 16
    panel_w = (width - label_w - gap - value_w * 2) / 2

    admit_max = max(row["admit_rate"] for row in entries)
    yield_max = max(row["yield_rate"] for row in entries)

    panels = [
        {"x": label_w, "key": "admit_rate", "max": admit_max},
        {"x": label_w + panel_w + value_w + gap, "key": "yield_rate", "max": yield_max},
    ]

    bars = []
    for i, row in enumerate(entries):
        y = top + row_h * i + row_h / 2
        entry = {
            "name": row["school"].short,
            "y": round(y, 1),
            "text_y": round(y + 4, 1),
            "cells": [],
        }
        for panel in panels:
            value = row[panel["key"]]
            length = panel_w * (value / panel["max"]) if panel["max"] else 0
            entry["cells"].append(
                {
                    "x": round(panel["x"], 1),
                    "width": round(max(length, 1.5), 1),
                    "label_x": round(panel["x"] + length + 7, 1),
                    "value": value,
                }
            )
        bars.append(entry)

    return {
        "width": width,
        "height": top + row_h * len(entries) + bottom,
        "bars": bars,
        "label_x": label_w - 10,
        "headings": [
            {"x": round(panels[0]["x"], 1), "y": top - 16, "text": "Admit rate", "max": admit_max},
            {"x": round(panels[1]["x"], 1), "y": top - 16, "text": "Yield", "max": yield_max},
        ],
    }


def _volume_chart(rows: list[dict]) -> dict | None:
    """Raw applications, in the school's own colour.

    Demand before any rate is taken of it. Deliberately unadjusted for size —
    UCLA's 139,489 applications against Caltech's 13,026 is mostly a statement
    about how big the two schools are, and the caption says so rather than the
    chart pretending otherwise.
    """
    entries = [row for row in rows if row["applied"] is not None]
    if not entries:
        return None

    entries.sort(key=lambda row: row["applied"], reverse=True)

    width, row_h = 640, 26
    label_w, value_w = 124, 66
    top, bottom = 10, 10
    plot_w = width - label_w - value_w
    largest = max(row["applied"] for row in entries)

    bars = []
    for i, row in enumerate(entries):
        y = top + row_h * i + row_h / 2
        length = plot_w * (row["applied"] / largest) if largest else 0
        bars.append(
            {
                "name": row["school"].short,
                "color": row["school"].color,
                "y": round(y - 7, 1),
                "text_y": round(y + 4, 1),
                "width": round(max(length, 1.5), 1),
                "label_x": round(label_w + length + 8, 1),
                "value": row["applied"],
            }
        )

    return {
        "width": width,
        "height": top + row_h * len(entries) + bottom,
        "bars": bars,
        "label_x": label_w - 10,
        "plot_x": label_w,
    }
