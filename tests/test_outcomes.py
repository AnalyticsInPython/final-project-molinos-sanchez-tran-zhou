"""Tests for the after-graduation outcomes area.

The traps here are not computation bugs so much as reading the numbers as if
they described one cohort: a null median debt rendered as zero, or growth
assumed positive because "more years should mean more pay."
"""

import pytest

from app.areas import outcomes
from app.db import DB_PATH, connect
from app.schools import all_schools

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="No database — run: uv run python scripts/import_ipeds.py",
)

CALTECH = 110404
MIT = 166683

# This area has no year axis (see outcomes.py's docstring) — any value works,
# since `load` accepts it only to satisfy the shared area contract.
YEAR = 2021


@pytest.fixture
def conn():
    with connect() as connection:
        yield connection


def test_every_school_has_a_row(conn):
    rows = outcomes.load(conn, all_schools(conn), YEAR)["rows"]
    assert len(rows) == 25


def test_caltechs_median_debt_is_missing_not_zero(conn):
    """NSLDS suppresses the median when too few students borrowed. That is not
    the same fact as nobody borrowing, and must not read as $0."""
    caltech = _row(conn, CALTECH)
    assert caltech["median_debt"] is None
    assert caltech["debt_to_earnings"] is None


def test_earnings_growth_can_be_negative(conn):
    """Caltech's 10-year median earnings are lower than its 6-year figure —
    a real feature of small, PhD-heavy cohorts, not a bug to clamp away."""
    caltech = _row(conn, CALTECH)
    assert caltech["earnings_6yr"] == 132140
    assert caltech["earnings_10yr"] == 128566
    assert caltech["growth"] == -3574


def test_debt_to_earnings_is_debt_over_six_year_earnings(conn):
    mit = _row(conn, MIT)
    assert mit["median_debt"] == 14768
    assert mit["earnings_6yr"] == 131633
    assert mit["debt_to_earnings"] == 0.1


def test_chart_has_a_bar_per_school_with_both_earnings_figures(conn):
    schools = all_schools(conn)[:5]
    chart = outcomes.load(conn, schools, YEAR)["chart"]
    assert len(chart["bars"]) == 5
    for bar in chart["bars"]:
        assert bar["high"] is not None and bar["low"] is not None


def test_a_null_debt_is_a_notice_not_a_missing_school(conn):
    """Caltech has earnings but no reportable debt — that's `missing_some`,
    not `missing_all`: it still gets a full row, just one flagged cell."""
    result = outcomes.load(conn, all_schools(conn), YEAR)
    assert result["rows"]
    assert result["notices"], "Caltech's suppressed debt figure produced no notice"


def test_coverage_is_pairs_of_plain_integers(conn):
    """It crosses into JSON for the browser, so it cannot carry sqlite Rows."""
    for unitid, year in outcomes.coverage(conn):
        assert isinstance(unitid, int)
        assert isinstance(year, int)


def test_a_covered_school_actually_renders(conn):
    from app.schools import selected

    pairs = sorted(outcomes.coverage(conn))
    unitid, year = pairs[0]
    context = outcomes.load(conn, selected(conn, [unitid]), year)
    assert context["rows"][0]["earnings_6yr"] is not None


def _row(conn, unitid: int) -> dict:
    rows = outcomes.load(conn, all_schools(conn), YEAR)["rows"]
    return next(row for row in rows if row["school"].unitid == unitid)
