"""Tests for the financial aid area.

Two of these guard traps rather than code: that we never drop a real negative
net price, and that the sentinels never reach the page as if they were prices.
Both are mistakes that produce a plausible-looking table.
"""

import pytest

from app.areas import financial_aid
from app.db import DB_PATH, connect, latest_year
from app.schools import all_schools

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="No database — run: uv run python scripts/import_ipeds.py",
)

CALTECH = 110404
DARTMOUTH = 182670


@pytest.fixture
def conn():
    with connect() as connection:
        yield connection


@pytest.fixture
def year(conn):
    """Whatever the newest ingested year is — net price stops at 2021."""
    return latest_year(conn, financial_aid.TABLE)


def test_every_school_has_all_five_bands(conn, year):
    rows = financial_aid.load(conn, all_schools(conn), year)["rows"]
    assert len(rows) == 25
    for row in rows:
        assert len(row["bands"]) == 5
        assert all(value is not None for value in row["bands"])


def test_negative_net_price_survives(conn, year):
    """Caltech's lowest band is below zero because grant aid exceeds cost.

    It is a real number. If this test fails because the value is gone, someone
    has added a drop-negatives rule and deleted the most interesting fact in
    the dataset.
    """
    caltech = _row(conn, CALTECH, year)
    assert caltech["bands"][0] < 0


def test_no_sentinel_reaches_the_page(conn, year):
    for row in financial_aid.load(conn, all_schools(conn), year)["rows"]:
        assert not any(value in (-1, -2, -3) for value in row["bands"])


def test_spread_is_top_band_minus_bottom(conn, year):
    dartmouth = _row(conn, DARTMOUTH, year)
    assert dartmouth["spread"] == dartmouth["bands"][4] - dartmouth["bands"][0]
    assert dartmouth["spread"] == 53332


def test_chart_has_a_line_per_school(conn, year):
    schools = all_schools(conn)[:5]
    chart = financial_aid.load(conn, schools, year)["chart"]
    assert len(chart["series"]) == 5
    assert all(line["points"].count(",") == 5 for line in chart["series"])


def _row(conn, unitid: int, year: int) -> dict:
    rows = financial_aid.load(conn, all_schools(conn), year)["rows"]
    return next(row for row in rows if row["school"].unitid == unitid)


def test_the_query_is_filtered_to_one_year(conn):
    """The table now holds seven years; an unfiltered pivot would mix them.

    2020 and 2021 are different data. If this ever starts passing with equal
    values, the year filter has been dropped from the query and every figure
    on the page is a seven-year average wearing a single year's label.
    """
    schools = all_schools(conn)
    a = financial_aid.load(conn, schools, 2020)["rows"]
    b = financial_aid.load(conn, schools, 2021)["rows"]
    assert [r["spread"] for r in a] != [r["spread"] for r in b]


def test_highlights_names_the_widest_spread(conn, year):
    """Dartmouth's spread ($53,332) is the widest in the 25-school sample."""
    context = financial_aid.load(conn, all_schools(conn), year)
    lines = financial_aid.highlights(context)
    assert lines
    assert "Dartmouth" in lines[0]


def test_highlights_is_empty_for_a_single_school(conn, year):
    """A "widest spread" claim needs something to be wider than."""
    schools = [s for s in all_schools(conn) if s.unitid == CALTECH]
    context = financial_aid.load(conn, schools, year)
    assert financial_aid.highlights(context) == []
