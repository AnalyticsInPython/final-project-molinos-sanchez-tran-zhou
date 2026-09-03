"""Tests for the shared trend renderer.

The two that matter are `test_a_gap_breaks_the_line` and
`test_the_axis_is_the_window_not_the_data`. Both guard drawings that would be
wrong rather than ugly: joining across a missing year draws a segment through
data that does not exist, and shrinking the axis to fit the data hides the fact
that a series stopped years ago — which is the whole reason the trend view is
better than the snapshot it replaces.
"""

import pytest

from app.areas import financial_aid, selectiveness
from app.db import DB_PATH, connect, years_available
from app.format import money, number
from app.schools import School
from app.trend import chart, window

A = School(1, "Alpha University", "#2a6fb0")
B = School(2, "Beta College", "#e07b39")

YEARS = [2020, 2021, 2022, 2023, 2024]


def test_a_gap_breaks_the_line():
    """Alpha is missing 2022, so it draws as two segments rather than one.

    Joining 2021 to 2023 would draw a segment through a year with no data and
    invite the reader to read a value off it.
    """
    values = {
        (1, 2020): 10, (1, 2021): 12, (1, 2023): 16, (1, 2024): 18,
        (2, 2020): 5, (2, 2021): 6, (2, 2022): 7, (2, 2023): 8, (2, 2024): 9,
    }
    spec = chart([A, B], YEARS, values, fmt=number)
    alpha = next(s for s in spec["series"] if s["name"] == "Alpha University")
    beta = next(s for s in spec["series"] if s["name"] == "Beta College")
    assert len(alpha["lines"]) == 2
    assert len(beta["lines"]) == 1
    assert len(alpha["dots"]) == 4
    # Neither segment may contain a point for the missing year.
    assert all(len(path.split(" ")) == 2 for path in alpha["lines"])


def test_an_isolated_year_draws_a_dot_and_no_line():
    """One point is not a line. It still has to appear."""
    spec = chart([A], YEARS, {(1, 2020): 10, (1, 2024): 18}, fmt=number)
    alpha = spec["series"][0]
    assert alpha["lines"] == []
    assert len(alpha["dots"]) == 2


def test_the_axis_is_the_window_not_the_data():
    """A series ending early leaves visible empty axis after it."""
    values = {(1, 2020): 10, (1, 2021): 12}
    spec = chart([A], YEARS, values, fmt=number)
    assert [t["label"] for t in spec["x_ticks"]][-1] == "2024"
    assert next(s for s in spec["series"] if s["name"] == A.name)["ends"] == 2021


def test_a_school_with_no_data_is_dropped_from_the_chart():
    spec = chart([A, B], YEARS, {(1, 2020): 1, (1, 2021): 2}, fmt=number)
    assert [s["name"] for s in spec["series"]] == ["Alpha University"]


def test_nothing_to_draw_returns_none():
    assert chart([A], YEARS, {}, fmt=number) is None
    assert chart([A], [2021], {(1, 2021): 5}, fmt=number) is None


def test_a_count_axis_does_not_pad_below_zero():
    """-838 applications is a drawing artefact, not a number."""
    rising = dict(zip(YEARS, [10, 400, 800, 1200, 1600], strict=True))
    spec = chart([A], YEARS, {(1, y): v for y, v in rising.items()}, fmt=number)
    assert all(not t["label"].startswith("-") for t in spec["y_ticks"])


def test_a_price_axis_keeps_its_negative_room():
    """Net price below zero is real — grant aid exceeding cost of attendance."""
    rising = dict(zip(YEARS, [-500, 200, 900, 1600, 2000], strict=True))
    spec = chart([A], YEARS, {(1, y): v for y, v in rising.items()}, fmt=money)
    assert spec["y_ticks"][0]["label"].startswith("-")


def test_converging_lines_do_not_stack_their_labels():
    """Caltech and Stanford land within a pixel of each other by 2024."""
    values = {(1, y): 100 for y in YEARS} | {(2, y): 100.4 for y in YEARS}
    spec = chart([A, B], YEARS, values, fmt=number)
    positions = sorted(s["label_y"] for s in spec["series"])
    assert positions[1] - positions[0] >= 12


def test_window_is_shared_and_bounded_by_what_exists():
    assert window(2024, "5", 2015) == list(range(2020, 2025))
    assert window(2024, "10", 2015) == list(range(2015, 2025))
    assert window(2024, "all", 2015) == list(range(2015, 2025))
    # A range longer than the data does not invent years before it.
    assert window(2021, "10", 2018) == list(range(2018, 2022))


needs_db = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="No database — run: uv run python scripts/import_ipeds.py",
)


@pytest.fixture
def conn():
    with connect() as connection:
        yield connection


@needs_db
def test_areas_expose_a_trend_over_the_shared_window(conn):
    from app.schools import selected

    schools = selected(conn, [110404, 243744])
    shared = window(2024, "10", 2015)

    admissions = selectiveness.trend(conn, schools, shared)
    aid = financial_aid.trend(conn, schools, shared)

    assert [p["title"] for p in admissions["panels"]] == ["Admit rate", "Yield", "Applications"]
    assert len(aid["panels"]) == 2

    # Drawn against the same window, admissions reaches the edge and net price
    # visibly does not. That contrast is the point of a shared axis.
    assert max(s["ends"] for s in admissions["panels"][0]["chart"]["series"]) == 2024
    assert max(s["ends"] for s in aid["panels"][0]["chart"]["series"]) == 2021


@needs_db
def test_the_trend_covers_every_ingested_year(conn):
    years = years_available(conn, selectiveness.TABLE)
    assert len(years) >= 10


def test_labels_never_escape_the_plot():
    """Several series on the same value push each other off the bottom.

    Real case: every Ivy reports $0 of athletic aid, so their labels stack at
    the axis and the last one lands among the year ticks.
    """
    flat = {(uid, y): 0 for uid in (1, 2) for y in YEARS}
    spec = chart([A, B], YEARS, flat, fmt=money)
    floor = spec["plot_bottom"]
    assert all(s["label_y"] <= floor for s in spec["series"])
    positions = sorted(s["label_y"] for s in spec["series"])
    assert positions[1] - positions[0] >= 12
