"""Drawing one metric across years, one line per school.

Shared rather than written per area, because every trend panel is the same
picture: years along the bottom, a metric up the side, a line per school in
that school's own colour. An area supplies numbers and a label; it does not
lay out a chart. Adding a trend to a new area is a query and a dict.

Two decisions worth stating, because both could be made differently.

**The x axis is the window the user asked for, not the data.** If someone asks
for 2015-2024 and net price stops in 2021, the line stops in 2021 with three
years of empty axis after it. That gap is the most honest thing on the page:
it shows the reader exactly how far behind a figure is, next to an area that
runs to the edge, without either of them saying a word about it.

**A gap in the middle breaks the line.** Joining across a missing year draws a
segment through data that does not exist. Runs of consecutive years are drawn
as separate polylines instead, so a hole reads as a hole.

The y axis is not forced to zero. These are rates and prices tracked over time,
where the shape is the finding and a 0-4% admit rate against a 0-100% axis is a
flat line saying nothing. Every tick carries its real value.
"""

from collections.abc import Callable

# Room for the school's name at the end of its line, so no legend is needed.
LABEL_GUTTER = 92

# Smallest vertical gap between two end labels before they read as one.
LABEL_GAP = 13


def chart(
    schools: list,
    years: list[int],
    values: dict,
    *,
    fmt: Callable,
) -> dict | None:
    """A line per school across `years`.

    `values` is keyed `(unitid, year)`. A missing key and a None are the same
    thing: no data for that school that year.
    """
    points = [
        values.get((school.unitid, year))
        for school in schools
        for year in years
        if values.get((school.unitid, year)) is not None
    ]
    if not points or len(years) < 2 or years[-1] == years[0]:
        return None

    width, height = 640, 268
    left, top, bottom = 66, 16, 36
    right = LABEL_GUTTER
    plot_w = width - left - right
    plot_h = height - top - bottom

    low, high = min(points), max(points)
    if high == low:
        # A perfectly flat metric still deserves a readable band around it.
        pad = abs(high) * 0.1 or 1
        low, high = low - pad, high + pad
    else:
        pad = (high - low) * 0.08
        floor = low
        low, high = low - pad, high + pad
        # Padding must not invent an impossible value. A count of applications
        # cannot be negative, so an axis reading -838 is a drawing artefact
        # rather than a number. Net price genuinely can be, and keeps its pad.
        if floor >= 0:
            low = max(low, 0)
    span = high - low

    # Positioned by the year's value, not its index. If someone picks 2015 and
    # 2024 and nothing between, those two points sit ten years apart rather
    # than side by side, and the slope between them stays honest.
    # Named for the axis, not shortened: `last` is rebound inside the series
    # loop below, and sharing the name silently fed a tuple to this closure.
    first_year, last_year = years[0], years[-1]

    def x(year: int) -> float:
        return left + plot_w * (year - first_year) / (last_year - first_year)

    def y(value: float) -> float:
        return top + plot_h * (1 - (value - low) / span)

    series = []
    for school in schools:
        # Consecutive runs only: a hole in the middle must not be bridged.
        runs, current = [], []
        for year in years:
            value = values.get((school.unitid, year))
            if value is None:
                if current:
                    runs.append(current)
                    current = []
                continue
            current.append((x(year), y(value), year, value))
        if current:
            runs.append(current)
        if not runs:
            continue

        last = runs[-1][-1]
        series.append(
            {
                "name": school.short,
                "color": school.color,
                "lines": [
                    " ".join(f"{px:.1f},{py:.1f}" for px, py, _, _ in run)
                    for run in runs
                    if len(run) > 1
                ],
                "dots": [
                    {"x": round(px, 1), "y": round(py, 1), "year": yr, "label": fmt(val)}
                    for run in runs
                    for px, py, yr, val in run
                ],
                "label_x": round(last[0] + 8, 1),
                "label_y": round(last[1] + 4, 1),
                "ends": last[2],
            }
        )

    if not series:
        return None

    # Lines that converge put their end labels on top of each other — Caltech
    # and Stanford land within a pixel of one another on admit rate by 2024.
    # Push them apart in place, keeping their vertical order so each still
    # reads as belonging to the line it sits beside.
    series.sort(key=lambda item: item["label_y"])
    for above, below in zip(series, series[1:], strict=False):
        if below["label_y"] - above["label_y"] < LABEL_GAP:
            below["label_y"] = round(above["label_y"] + LABEL_GAP, 1)

    # Label every year when there is room, otherwise every other one, always
    # keeping the last so the reader can see where the window closes.
    step = 1 if len(years) <= 6 else 2
    shown = [yr for i, yr in enumerate(years) if i % step == 0 or yr == last_year]

    return {
        "width": width,
        "height": height,
        "series": series,
        "x_ticks": [
            {"x": round(x(yr), 1), "label": str(yr), "y": height - 14} for yr in shown
        ],
        "y_ticks": [
            {
                "y": round(y(low + span * i / 3), 1),
                "label": fmt(low + span * i / 3),
            }
            for i in range(4)
        ],
        "plot_left": left,
        "plot_right": width - right,
        "plot_top": top,
        "plot_bottom": height - bottom,
    }


def window(latest: int, span: str, earliest: int) -> list[int]:
    """The years to draw, shared by every area on the page.

    Deliberately one window for all areas rather than each area's own last N.
    A shared axis is what lets a reader see that admissions reaches 2024 and
    net price stopped in 2021 — per-area windows would hide exactly that by
    stretching both lines to the same width.
    """
    start = earliest if span == "all" else latest - int(span) + 1
    return list(range(max(start, earliest), latest + 1))
