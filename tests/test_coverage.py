"""Tests for what each area says it can draw.

`coverage` drives the year picker's colours, so it has to mean *renderable*
rather than "a row exists". If it over-reports, the picker offers a green year
and the reader clicks through to an empty chart — the exact broken promise the
notices were written to prevent.
"""

import pytest

from app.areas import financial_aid, selectiveness
from app.db import DB_PATH, connect, years_available

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="No database — run: uv run python scripts/import_ipeds.py",
)

CALTECH = 110404
STANFORD = 243744

AREAS = [financial_aid, selectiveness]


@pytest.fixture
def conn():
    with connect() as connection:
        yield connection


@pytest.mark.parametrize("area", AREAS, ids=lambda a: a.KEY)
def test_coverage_never_exceeds_the_years_ingested(conn, area):
    ingested = set(years_available(conn, area.TABLE))
    assert {year for _, year in area.coverage(conn)} <= ingested


@pytest.mark.parametrize("area", AREAS, ids=lambda a: a.KEY)
def test_a_covered_year_actually_renders(conn, area):
    """The promise the picker makes, checked against the thing it promises."""
    from app.schools import selected

    pairs = sorted(area.coverage(conn))
    for unitid, year in (pairs[0], pairs[len(pairs) // 2], pairs[-1]):
        context = area.load(conn, selected(conn, [unitid]), year)
        assert context["rows"], f"{area.KEY} claims {unitid} in {year} and draws nothing"


def test_net_price_coverage_stops_where_the_series_does(conn):
    years = {year for _, year in financial_aid.coverage(conn)}
    assert max(years) == 2021
    assert 2022 not in years


def test_admissions_coverage_reaches_the_present(conn):
    years = {year for _, year in selectiveness.coverage(conn)}
    assert max(years) == 2024


def test_a_school_missing_a_year_is_absent_from_coverage(conn):
    """Stanford has no 2015 admissions row; the picker must show that gap."""
    pairs = selectiveness.coverage(conn)
    assert (STANFORD, 2015) not in pairs
    assert (STANFORD, 2016) in pairs
    assert (CALTECH, 2015) in pairs


def test_coverage_requires_both_ends_of_the_income_range(conn):
    """A school with middle bands only cannot have its spread drawn.

    Coverage is defined on bands 1 and 5 rather than on any row, because the
    spread is the metric and it needs both ends.
    """
    covered = financial_aid.coverage(conn)
    rows = conn.execute(
        "SELECT unitid, year FROM sfa_grants_and_net_price "
        "WHERE type_of_aid = 9 AND income_level IN (1, 5) "
        "AND net_price NOT IN (-1, -2, -3) "
        "GROUP BY unitid, year HAVING COUNT(DISTINCT income_level) = 1"
    ).fetchall()
    for row in rows:
        assert (row["unitid"], row["year"]) not in covered


@pytest.mark.parametrize("area", AREAS, ids=lambda a: a.KEY)
def test_coverage_is_pairs_of_plain_integers(conn, area):
    """It crosses into JSON for the browser, so it cannot carry sqlite Rows."""
    for unitid, year in area.coverage(conn):
        assert isinstance(unitid, int)
        assert isinstance(year, int)
