"""Tests for the financial aid area.

Two of these guard traps rather than code: that we never drop a real negative
net price, and that the sentinels never reach the page as if they were prices.
Both are mistakes that produce a plausible-looking table.
"""

import pytest

from app.areas import financial_aid
from app.db import DB_PATH, connect
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


def test_every_school_has_all_five_bands(conn):
    rows = financial_aid.load(conn, all_schools(conn))["rows"]
    assert len(rows) == 25
    for row in rows:
        assert len(row["bands"]) == 5
        assert all(value is not None for value in row["bands"])


def test_negative_net_price_survives(conn):
    """Caltech's lowest band is below zero because grant aid exceeds cost.

    It is a real number. If this test fails because the value is gone, someone
    has added a drop-negatives rule and deleted the most interesting fact in
    the dataset.
    """
    caltech = _row(conn, CALTECH)
    assert caltech["bands"][0] < 0


def test_no_sentinel_reaches_the_page(conn):
    for row in financial_aid.load(conn, all_schools(conn))["rows"]:
        assert not any(value in (-1, -2, -3) for value in row["bands"])


def test_spread_is_top_band_minus_bottom(conn):
    dartmouth = _row(conn, DARTMOUTH)
    assert dartmouth["spread"] == dartmouth["bands"][4] - dartmouth["bands"][0]
    assert dartmouth["spread"] == 53332


def test_chart_has_a_line_per_school(conn):
    schools = all_schools(conn)[:5]
    chart = financial_aid.load(conn, schools)["chart"]
    assert len(chart["series"]) == 5
    assert all(line["points"].count(",") == 5 for line in chart["series"])


def _row(conn, unitid: int) -> dict:
    rows = financial_aid.load(conn, all_schools(conn))["rows"]
    return next(row for row in rows if row["school"].unitid == unitid)
