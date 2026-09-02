"""Student financial aid — what a family actually pays, by what it earns.

This is the reference area: the pattern every other area copies, and the one
carrying the project's analysis.

IPEDS publishes net price at five income bands. It does not publish the gap
between the top band and the bottom one. We compute it, and it is the finding:
Dartmouth costs a low-income family $2,438 and a wealthy one $55,770, while
UNC Chapel Hill runs $3,296 to $23,695. The private school is cheaper than the
public university at the bottom of the income scale and $32,000 dearer at the
top. "Expensive school" is not a property of the school.

One trap, and it is the whole reason the cleaning below is written the way it
is: **a negative net price is real.** Grant aid can exceed the total cost of
attendance, and five schools in the sample report one. Only the exact
sentinels -1, -2 and -3 mean "missing". A blanket drop-negatives rule deletes
Stanford's -$1,386 and Caltech's -$1,012, which are the most striking numbers
in the dataset.
"""

import sqlite3

import polars as pl

from app.format import money
from app.notices import coverage_notices
from app.schools import School

KEY = "financial_aid"
TITLE = "Student financial aid"
QUESTION = "What will I actually pay, at my income?"
# Named in the reader's terms, because it goes inside sentences like "no net
# price data at all" rather than being used as a heading.
SUBJECT = "net price"
TABLE = "sfa_grants_and_net_price"
TEMPLATE = "areas/financial_aid.html"

# Drawn on a 24x24 grid, stroked in the caller's colour rather than filled, so
# every area's icon sits at the same weight beside its title. A banknote: this
# area is about what leaves the family's account.
ICON = (
    '<rect x="2" y="6" width="20" height="12" rx="2"/>'
    '<circle cx="12" cy="12" r="2.5"/>'
    '<path d="M6 10v4M18 10v4"/>'
)

# IPEDS income bands for net price. The labels are the family income ranges
# the bands are defined on, not our shorthand for them.
BANDS = {
    1: "$0–30,000",
    2: "$30,001–48,000",
    3: "$48,001–75,000",
    4: "$75,001–110,000",
    5: "$110,001 and up",
}

# The table has to fit five schools, five bands and the spread on one screen.
# Full ranges would push the spread — the number the area exists for — off the
# right edge, so the header is short and the exact ranges go in the note.
BAND_HEADERS = {
    1: "Under $30k",
    2: "$30–48k",
    3: "$48–75k",
    4: "$75–110k",
    5: "$110k and up",
}

# type_of_aid 9 is grant or scholarship aid from any source, which is the
# basis IPEDS computes net price on. income_level 99 is the all-incomes
# average and would flatten exactly the variation we are here to show.
QUERY = """
    SELECT unitid, income_level, net_price
    FROM sfa_grants_and_net_price
    WHERE type_of_aid = 9 AND income_level BETWEEN 1 AND 5
"""

# Missing and not-applicable. Any other negative is a real price.
SENTINELS = [-1, -2, -3]


def load(conn: sqlite3.Connection, schools: list[School]) -> dict:
    """Net price per band per school, plus the spread between top and bottom."""
    frame = pl.read_database(QUERY, conn)
    if frame.is_empty():
        return {
            "rows": [],
            "bands": BANDS,
            "headers": BAND_HEADERS,
            "range_chart": None,
            "chart": None,
            "notices": coverage_notices(list(schools), [], subject=SUBJECT),
        }

    frame = frame.with_columns(
        pl.when(pl.col("net_price").is_in(SENTINELS))
        .then(None)
        .otherwise(pl.col("net_price"))
        .alias("net_price")
    ).filter(pl.col("unitid").is_in([s.unitid for s in schools]))

    wide = frame.pivot(on="income_level", index="unitid", values="net_price")

    # The computed metric. Named `spread` everywhere it appears.
    wide = wide.with_columns((pl.col("5") - pl.col("1")).alias("spread"))

    prices = {row["unitid"]: row for row in wide.to_dicts()}
    rows = []
    for school in schools:
        price = prices.get(school.unitid, {})
        rows.append(
            {
                "school": school,
                "bands": [price.get(str(band)) for band in BANDS],
                "spread": price.get("spread"),
            }
        )

    # A school reporting nothing and a school reporting four bands of five are
    # different problems and get different sentences.
    missing_all = [r["school"] for r in rows if all(v is None for v in r["bands"])]
    missing_some = [
        r["school"]
        for r in rows
        if any(v is None for v in r["bands"]) and not all(v is None for v in r["bands"])
    ]

    return {
        "rows": rows,
        "bands": BANDS,
        "headers": BAND_HEADERS,
        "range_chart": _range_chart(rows),
        "chart": _chart(rows),
        "notices": coverage_notices(missing_all, missing_some, subject=SUBJECT),
    }


def _range_chart(rows: list[dict]) -> dict | None:
    """One row per school: lowest income band to highest, sorted by spread.

    This is the primary chart. The finding is a per-item before/after — what
    the poorest family pays against what the richest one does — and a range
    plot is the form that states it directly. Schools are labelled on their
    own row, so no one has to match a colour to a legend to read it, and the
    rows sort by spread so the ranking is the shape.

    The five lines we drew first collided in the bottom-left corner, where
    every school charges roughly nothing, and only separated at the far right.
    That is the wrong emphasis: the interesting part was unreadable.
    """
    pairs = [
        (row, row["bands"][0], row["bands"][-1])
        for row in rows
        if row["bands"][0] is not None and row["bands"][-1] is not None
    ]
    if not pairs:
        return None

    pairs.sort(key=lambda p: p[2] - p[1], reverse=True)

    width, row_h = 640, 34
    left, right, top = 132, 56, 26
    bottom = 34
    height = top + row_h * len(pairs) + bottom
    plot_w = width - left - right

    low = min(0, min(lo for _, lo, _ in pairs))
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
                "spread": hi - lo,
                "spread_x": round(x(hi) + 10, 1),
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
        "zero_x": round(x(0), 1) if low < 0 else None,
    }


def _chart(rows: list[dict]) -> dict | None:
    """One line per school across the five bands — the secondary view.

    The range chart says how big the gap is; this says where in the income
    scale it opens up, which is a different question and worth its own frame.
    Laid out here rather than in the template so the template renders numbers
    it is handed instead of computing any of its own.
    """
    values = [v for row in rows for v in row["bands"] if v is not None]
    if not values:
        return None

    width, height = 640, 300
    left, right, top, bottom = 60, 96, 16, 40
    plot_w = width - left - right
    plot_h = height - top - bottom

    low = min(0, min(values))
    high = max(values)
    span = high - low or 1

    def x(band_index: int) -> float:
        return left + plot_w * band_index / (len(BANDS) - 1)

    def y(value: float) -> float:
        return top + plot_h * (1 - (value - low) / span)

    series = []
    for row in rows:
        points = [
            (x(i), y(v)) for i, v in enumerate(row["bands"]) if v is not None
        ]
        if len(points) < 2:
            continue
        series.append(
            {
                "name": row["school"].name,
                "short": row["school"].short,
                "spread": row["spread"],
                "color": row["school"].color,
                "points": " ".join(f"{px:.1f},{py:.1f}" for px, py in points),
                "dots": [{"x": round(px, 1), "y": round(py, 1)} for px, py in points],
                "label_x": points[-1][0] + 8,
                "label_y": points[-1][1] + 4,
                "end_value": row["bands"][-1],
            }
        )

    ticks = []
    for step in range(5):
        value = low + span * step / 4
        ticks.append({"y": round(y(value), 1), "label": money(value)})

    return {
        "width": width,
        "height": height,
        "series": series,
        "ticks": ticks,
        "band_labels": [
            {"x": round(x(i), 1), "y": height - 14, "label": label}
            for i, label in enumerate(["Lowest", "", "Middle", "", "Highest"])
        ],
        "baseline_y": round(y(0), 1) if low < 0 else None,
    }
