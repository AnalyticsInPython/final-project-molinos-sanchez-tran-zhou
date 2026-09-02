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

from app.schools import School

KEY = "financial_aid"
TITLE = "Student financial aid"
QUESTION = "What will I actually pay, at my income?"
TABLE = "sfa_grants_and_net_price"
TEMPLATE = "areas/financial_aid.html"

# IPEDS income bands for net price. The labels are the family income ranges
# the bands are defined on, not our shorthand for them.
BANDS = {
    1: "$0–30,000",
    2: "$30,001–48,000",
    3: "$48,001–75,000",
    4: "$75,001–110,000",
    5: "$110,001 and up",
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
        return {"rows": [], "bands": BANDS, "chart": None}

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

    return {"rows": rows, "bands": BANDS, "chart": _chart(rows)}


def _chart(rows: list[dict]) -> dict | None:
    """Points for one line per school across the five bands.

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
        ticks.append({"y": round(y(value), 1), "label": f"${value:,.0f}"})

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
