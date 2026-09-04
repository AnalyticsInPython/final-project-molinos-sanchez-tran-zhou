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

from app.db import series_ends, years_available
from app.format import money
from app.notices import Notice, coverage_notices, series_notices
from app.offers import IN_STATE, OUT_OF_STATE, school_state
from app.schools import School
from app.trend import chart as line_chart

KEY = "financial_aid"
TITLE = "Student financial aid"
QUESTION = "What will I actually pay, at my income?"
# Named in the reader's terms, because it goes inside sentences like "no net
# price data at all" rather than being used as a heading.
SUBJECT = "net price"
TABLE = "sfa_grants_and_net_price"
SOURCE = "IPEDS"
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
#
# The year filter is not optional: the table holds every year we ingested, and
# without it the pivot below silently averages a decade into one column.
# `{year}` is interpolated through int(), so it cannot carry anything but a
# number.
QUERY = """
    SELECT unitid, income_level, net_price
    FROM sfa_grants_and_net_price
    WHERE type_of_aid = 9 AND income_level BETWEEN 1 AND 5 AND year = {year}
"""

# Missing and not-applicable. Any other negative is a real price.
SENTINELS = [-1, -2, -3]

# What a signed-in profile can change on this card, read by cuts.wants() and
# cuts.signals() to draw the "Tailor data for me" button and its hint. Neither
# is a cut: a cut breaks a survey's rows out by group and is drawn above the
# area by cut.html, whereas the income band is already this table's own axis
# and the home state picks which published price applies. `tailor()` below
# does the work; the value shown in the hint is the band's label and the state
# itself, so the button says what it will use before it is pressed.
TAILORS = {
    "income_bracket": ("income band", BANDS),
    "home_state": ("home state", None),
}

# Published tuition and fees, for the sticker the reader's home state
# qualifies them for. Deliberately *not* the net price series: it is a
# different survey year (2023 against 2021) and a different quantity — before
# any aid, rather than after it — so the two are shown side by side and never
# subtracted from one another.
#
# The year is read from the table rather than pinned, so this does not go
# stale the day the next tuition year is ingested; `level_of_study = 1` is
# undergraduate, and tuition types 3 and 4 are in-state and out-of-state.
STICKER_QUERY = """
    SELECT unitid, year, tuition_type, tuition_fees_ft
    FROM academic_year_tuition
    WHERE level_of_study = 1 AND tuition_type IN (?, ?)
      AND year = (SELECT MAX(year) FROM academic_year_tuition WHERE level_of_study = 1)
"""

# How much published cost of attendance has risen since a given year, read from
# the data rather than assumed. The freshness notice can then say how far off a
# stale net price is likely to be, instead of only how old it is — "five years
# old" tells a family the figure is not current, and "prices have risen about
# 8% since" tells them what to do about it.
INFLATION_QUERY = """
    SELECT year, AVG(tuition_fees_ft) AS sticker
    FROM academic_year_tuition
    WHERE level_of_study = 1 AND tuition_type = 3 AND tuition_fees_ft > 0
    GROUP BY year
"""

# Every year at once, for the trend view.
TREND_QUERY = """
    SELECT year, unitid, income_level, net_price
    FROM sfa_grants_and_net_price
    WHERE type_of_aid = 9 AND income_level BETWEEN 1 AND 5
      AND year BETWEEN {first} AND {last}
"""


def year_meaning(conn: sqlite3.Connection, year: int, trend: bool = False) -> str:
    if trend:
        return "Each year is an academic year: 2021 means what families paid in 2021–22."
    return f"Net price labelled {year} is what families paid in {year}–{str(year + 1)[-2:]}."


def _prices(conn: sqlite3.Connection, schools: list[School], year: int) -> list[dict] | None:
    """One row per school — the five bands and the spread — or None for an empty year.

    Shared by `load` and `tailor` so the year filter, the sentinel rule and
    the definition of `spread` are written once. Tailoring redraws the range
    chart with the reader's band marked on it, which needs the same numbers
    the table is already showing; recomputing them from a second query with
    its own filters is how the mark ends up on a different figure than the
    one under it.
    """
    frame = pl.read_database(QUERY.format(year=int(year)), conn)
    if frame.is_empty():
        return None

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
    return rows


def load(conn: sqlite3.Connection, schools: list[School], year: int) -> dict:
    """Net price per band per school, plus the spread between top and bottom."""
    rows = _prices(conn, schools, year)
    if rows is None:
        return {
            "rows": [],
            "bands": BANDS,
            "headers": BAND_HEADERS,
            "range_chart": None,
            "chart": None,
            "notices": coverage_notices(list(schools), [], subject=SUBJECT),
        }

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
        "range_chart": _range_chart(rows, lead=_lead(rows)),
        "chart": _chart(rows),
        "notices": (
            coverage_notices(missing_all, missing_some, subject=SUBJECT)
            + [n for n in [_drift_notice(conn, year)] if n]
        ),
    }


def tailor(conn: sqlite3.Connection, schools: list[School], year: int, profile) -> dict:
    """What changes on this card when the reader asks it to use their profile.

    Merged into `load`'s context by the route, so this returns only the keys
    it changes and the template renders one card either way. Two independent
    additions, because a profile can hold either answer or both:

    - **The income band.** The reader's band is marked in the table and drawn
      as a solid dot on the range chart, and one sentence names the cheapest
      and dearest school at that band and the gap between them. Nothing is
      estimated and nothing is hidden: every band stays on the page, because
      the finding is still the range and a card that showed only the reader's
      band would have thrown it away.
    - **The home state.** The published sticker each school would charge
      *this* reader — in-state where their state matches, out-of-state where
      it does not, one price where the school charges everyone the same.

    Returns `{}` when the profile holds neither, which is the same card as
    before. Never blends the two figures: see `_stickers`.
    """
    if profile is None:
        return {}
    band = profile.income_bracket if profile.income_bracket in BANDS else None
    home_state = profile.home_state or None
    if band is None and home_state is None:
        return {}

    rows = _prices(conn, schools, year)
    if rows is None:
        return {}

    tailored: dict = {}
    if band is not None:
        tailored |= {
            "own_band": band,
            "own_band_label": BANDS[band],
            # What to call the reader in the card's headline. Only a name they
            # chose to give: the username is a login, and "MIT pays maya-live
            # $2,251" is not a sentence anyone wants read off a projector.
            "own_name": profile.display_name,
            "band_sentence": _band_sentence(rows, band, year),
            # Redrawn rather than annotated: the dot has to sit at the band's
            # own position on the same axis as the bar it lands on.
            "range_chart": _range_chart(rows, own=band, lead=_band_lead(rows, band)),
        }
    if home_state is not None:
        tailored |= {
            "home_state": home_state,
            "stickers": _stickers(conn, rows, home_state, band),
            "net_price_year": year,
        }
    return tailored


def _band_extremes(rows: list[dict], band: int) -> tuple[tuple, tuple] | None:
    """The cheapest and dearest school at one income band, or None for fewer than two.

    The headline, the tailored sentence and the mark on the chart all name
    these two schools, so they are found once here rather than three times
    from three slightly different filters.
    """
    priced = [(r["school"], r["bands"][band - 1]) for r in rows if r["bands"][band - 1] is not None]
    if len(priced) < 2:
        return None
    return min(priced, key=lambda pair: pair[1]), max(priced, key=lambda pair: pair[1])


def _band_lead(rows: list[dict], band: int) -> set[int]:
    """The two schools the tailored headline names, for the chart to hold up."""
    extremes = _band_extremes(rows, band)
    return {school.unitid for school, _ in extremes} if extremes else set()


def _lead(rows: list[dict]) -> set[int]:
    """The school the untailored headline names — the widest price swing here."""
    widest = _widest(rows)
    return {widest["school"].unitid} if widest else set()


def _widest(rows: list[dict]) -> dict | None:
    """The row whose price depends most on income, or None for fewer than two."""
    priced = [row for row in rows if row.get("spread") is not None]
    if len(priced) < 2:
        return None
    return max(priced, key=lambda row: row["spread"])


def _band_sentence(rows: list[dict], band: int, year: int) -> str | None:
    """The one sentence the reader came for: cheapest, dearest, and the gap.

    Computed rather than written, so it cannot drift from the table under it.
    A single school gets no sentence — a gap needs two.
    """
    extremes = _band_extremes(rows, band)
    if not extremes:
        return None

    low, high = extremes
    priced = [r for r in rows if r["bands"][band - 1] is not None]
    return (
        f"At {BANDS[band]}, these {len(priced)} schools ran from {money(low[1])} at "
        f"{low[0].short} to {money(high[1])} at {high[0].short} in {year} — a gap of "
        f"{money(high[1] - low[1])} between two schools, at the same family income."
    )


def _stickers(
    conn: sqlite3.Connection, rows: list[dict], home_state: str, band: int | None
) -> dict | None:
    """The published price that applies to this reader at each school.

    Residency is the answer the questionnaire calls the one that moves the
    numbers most, and it moves them here: Berkeley charges a Californian
    $14,850 and everyone else $45,627. Which side of that line someone falls
    on comes from `offers.school_state`, so the offer comparison and this card
    cannot disagree about where a school is.

    A school whose in-state and out-of-state figures are identical is
    reported as charging one price rather than being labelled out-of-state,
    because that is what the data says and "out-of-state at MIT" would imply
    an in-state rate exists.

    The net price beside it is carried through untouched and stated with its
    own year. The two are different surveys, different years and different
    quantities — published cost before aid against what families actually paid
    after it — and subtracting one from the other would produce the most
    confident-looking number on the page and the least supported one.
    """
    found: dict[int, dict[int, int]] = {}
    sticker_year = None
    for record in conn.execute(STICKER_QUERY, (IN_STATE, OUT_OF_STATE)):
        if record["tuition_fees_ft"] in SENTINELS or record["tuition_fees_ft"] is None:
            continue
        sticker_year = record["year"]
        found.setdefault(record["unitid"], {})[record["tuition_type"]] = record["tuition_fees_ft"]

    listed = []
    for row in rows:
        school = row["school"]
        prices = found.get(school.unitid, {})
        resident = school_state(conn, school.unitid) == home_state
        one_price = prices.get(IN_STATE) is not None and prices.get(IN_STATE) == prices.get(
            OUT_OF_STATE
        )
        listed.append(
            {
                "school": school,
                "sticker": prices.get(IN_STATE if resident else OUT_OF_STATE),
                "basis": (
                    "One price for everyone"
                    if one_price
                    else "In-state"
                    if resident
                    else "Out-of-state"
                ),
                "in_state": resident and not one_price,
                # The other side of the residency line, so a reader can see
                # what their state is worth. None where there is one price.
                "alternative": None
                if one_price
                else prices.get(OUT_OF_STATE if resident else IN_STATE),
                "net_price": row["bands"][band - 1] if band else None,
            }
        )

    return {"year": sticker_year, "rows": listed} if sticker_year else None


def _drift_notice(conn: sqlite3.Connection, year: int) -> Notice | None:
    """How much costs have risen since the year being shown.

    Net price stops at 2021 while published cost of attendance runs to 2023, so
    the later years of one series can size the staleness of the other. This
    reports only observed growth and does not extrapolate past the last year we
    have — a projection would be the most confident-looking number on the page
    and the least supported.
    """
    prices = {
        int(r["year"]): r["sticker"]
        for r in pl.read_database(INFLATION_QUERY, conn).to_dicts()
        if r["sticker"]
    }
    later = [y for y in prices if y > year]
    if not later or year not in prices:
        return None

    newest = max(later)
    growth = prices[newest] / prices[year] - 1
    if growth < 0.02:
        return None

    return Notice(
        "info",
        f"Published costs at these schools rose about {growth * 100:.0f}% between "
        f"{year} and {newest}, the last year we have for them, and have kept rising "
        f"since. A {year} net price is likely to understate what a family pays now by "
        f"at least that much — more at the higher income bands, where the figures below "
        f"have been climbing fastest.",
    )


def _range_chart(
    rows: list[dict], own: int | None = None, lead: set[int] | None = None
) -> dict | None:
    """One row per school: lowest income band to highest, sorted by spread.

    `own` is the reader's income band when the card is tailored, drawn as a
    solid dot in the school's own colour where that band falls along the bar.
    Beside, never instead: the bar and both ends stay, because the reader's
    band is only meaningful against the range it sits in.

    `lead` is the school or schools the card's headline names, marked so the
    template can draw every other row faint — see the `.headline` note in
    templates/base.html for why the sentence and the chart have to point at
    the same school from across a lecture theatre. No lead marks every row
    instead of none: a page with one school has no sentence naming anybody,
    and drawing its only row faint would say the opposite.

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

    # The reader's band joins the domain rather than being clamped into it:
    # net price does not have to rise monotonically across the bands, and a
    # dot pinned to the end of a bar it actually sits outside of would be a
    # drawn lie rather than a rounding error.
    marked = [row["bands"][own - 1] for row, _, _ in pairs if own] if own else []
    low = min([0, *(lo for _, lo, _ in pairs), *(v for v in marked if v is not None)])
    high = max([*(hi for _, _, hi in pairs), *(v for v in marked if v is not None)])
    span = high - low or 1

    def x(value: float) -> float:
        return left + plot_w * (value - low) / span

    bars = []
    for i, (row, lo, hi) in enumerate(pairs):
        y = top + row_h * i + row_h / 2
        # A band the school does not report leaves the bar undotted rather
        # than putting the mark at zero, which would read as "free".
        own_price = row["bands"][own - 1] if own else None
        bars.append(
            {
                "name": row["school"].short,
                "color": row["school"].color,
                "y": round(y, 1),
                "label_y": round(y + 4, 1),
                "x_low": round(x(lo), 1),
                "x_high": round(x(hi), 1),
                "low": lo,
                "high": hi,
                "own": own_price,
                "x_own": round(x(own_price), 1) if own_price is not None else None,
                "spread": hi - lo,
                "spread_x": round(x(hi) + 10, 1),
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


def trend(conn: sqlite3.Connection, schools: list[School], years: list[int]) -> dict:
    """The spread over time, and what the poorest families actually pay.

    Two panels, and they answer different questions. The spread says how much
    a school's price depends on income and whether that dependence is widening.
    The lowest band says what a family with nothing is asked for, which can
    improve while the spread grows — a school can get more generous at the
    bottom and more expensive at the top in the same year.

    The average across all incomes is deliberately not here. It moves with the
    mix of families who enrolled as much as with any price, and it is the exact
    number this project exists to argue against.
    """
    # Where the survey itself starts and stops, so a year past the end of it is
    # not read as a hole in a school's reporting. See notices.series_notices.
    published = years_available(conn, TABLE)
    stopped = series_ends(conn, TABLE)

    frame = pl.read_database(TREND_QUERY.format(first=int(min(years)), last=int(max(years))), conn)
    if frame.is_empty():
        return {
            "panels": [],
            "notices": series_notices(
                schools,
                years,
                set(),
                subject=SUBJECT,
                source=SOURCE,
                published=published,
                ends=stopped,
            ),
        }

    frame = frame.with_columns(
        pl.when(pl.col("net_price").is_in(SENTINELS))
        .then(None)
        .otherwise(pl.col("net_price"))
        .alias("net_price")
    ).filter(pl.col("unitid").is_in([s.unitid for s in schools]))

    lowest, spread = {}, {}
    seen = set()
    for record in frame.to_dicts():
        key = (record["unitid"], record["year"])
        if record["income_level"] == 1:
            lowest[key] = record["net_price"]
        if record["income_level"] in (1, 5) and record["net_price"] is not None:
            seen.add(key)

    wide = frame.pivot(on="income_level", index=["unitid", "year"], values="net_price")
    for record in wide.to_dicts():
        top, bottom = record.get("5"), record.get("1")
        if top is not None and bottom is not None:
            spread[(record["unitid"], record["year"])] = top - bottom

    panels = [
        {
            "title": "How far price depends on income",
            "subtitle": (
                "Highest income band minus lowest. A widening gap means income "
                "matters more."
            ),
            "chart": line_chart(schools, years, spread, fmt=money),
        },
        {
            "title": "What the lowest income band pays",
            "subtitle": (
                "Net price for families under $30,000. Below zero means aid "
                "exceeded the cost of attendance."
            ),
            "chart": line_chart(schools, years, lowest, fmt=money),
        },
    ]

    return {
        "panels": [p for p in panels if p["chart"]],
        "notices": series_notices(
            schools,
            years,
            seen,
            subject=SUBJECT,
            source=SOURCE,
            published=published,
            ends=stopped,
        ),
    }


# Coverage is the pair the spread needs, not merely the presence of a row.
# A school reporting three middle bands and neither end cannot be drawn, and
# offering that year in the picker would promise a chart we cannot deliver.
COVERAGE_QUERY = """
    SELECT unitid, year
    FROM sfa_grants_and_net_price
    WHERE type_of_aid = 9 AND income_level IN (1, 5) AND net_price NOT IN (-1, -2, -3)
    GROUP BY unitid, year
    HAVING COUNT(DISTINCT income_level) = 2
"""


def coverage(conn: sqlite3.Connection) -> set[tuple[int, int]]:
    """Every (unitid, year) this area can render, for the year picker."""
    return {(row[0], row[1]) for row in conn.execute(COVERAGE_QUERY)}


def headline(context: dict, cut: dict | None = None) -> str | None:
    """The card's finding, in a sentence, from figures the card already shows.

    Tailored, it is the reader's own income band: what the cheapest school on
    the page asks a family that earns that, what the dearest one asks, and the
    distance between two schools at one income. Untailored it is the spread —
    the metric this module exists to compute.

    Computed rather than written, so it cannot drift from the table under it,
    and None where a comparison would need a second school it does not have.
    `cut` is unused here: this area's tailoring is its own axis rather than a
    breakdown of a survey's rows (see `tailor`).
    """
    rows = context.get("rows", [])
    band = context.get("own_band")

    if band:
        extremes = _band_extremes(rows, band)
        if not extremes:
            return None
        (cheapest, low), (dearest, high) = extremes
        # A negative net price is grant aid exceeding the whole cost of
        # attendance, and "pays her $2,251 to attend" is what that means.
        # Saying "charges -$2,251" would bury the most striking fact here.
        who = context.get("own_name") or "a family at that income"
        asks = (
            f"pays {who} {money(-low)} to attend" if low < 0 else f"charges {who} {money(low)}"
        )
        return (
            f"At {BANDS[band]}, {cheapest.short} {asks} and {dearest.short} charges "
            f"{money(high)}. Same income, {money(high - low)} apart."
        )

    widest = _widest(rows)
    if widest is None:
        return None
    narrowest = min(
        (row for row in rows if row.get("spread") is not None), key=lambda row: row["spread"]
    )
    return (
        f"{widest['school'].short}'s price swings {money(widest['spread'])} by income, "
        f"the widest here. {narrowest['school'].short}'s moves {money(narrowest['spread'])}."
    )
