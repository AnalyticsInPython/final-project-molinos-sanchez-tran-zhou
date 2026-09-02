"""Tests for the year metadata the whole app now reads from.

`series_ends` is the one worth reading. It answers "does IPEDS publish anything
newer?" from evidence rather than from a flag someone maintains by hand: the
ingest asks for years past the end of each series and records the empty
answers, so a zero-row year above the newest live one is the survey saying it
stops there. Get this wrong in the optimistic direction and the app tells a
student a five-year-old figure is the best available when a current one exists.
"""

import pytest

from app.db import DB_PATH, connect, latest_year, series_ends, years_available

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="No database — run: uv run python scripts/import_ipeds.py",
)

NET_PRICE = "sfa_grants_and_net_price"
ADMISSIONS = "admissions_enrollment"


@pytest.fixture
def conn():
    with connect() as connection:
        yield connection


def test_net_price_really_does_stop(conn):
    """2022 onward returns a successful response with no rows."""
    assert latest_year(conn, NET_PRICE) == 2021
    assert series_ends(conn, NET_PRICE) is True


def test_admissions_is_current_and_does_not_claim_to_have_ended(conn):
    """Admissions runs to 2024, so nothing here should blame the survey."""
    assert latest_year(conn, ADMISSIONS) == 2024
    assert series_ends(conn, ADMISSIONS) is False


def test_the_two_areas_end_in_different_years(conn):
    """The reason a single build-wide anchor year was wrong."""
    assert latest_year(conn, ADMISSIONS) > latest_year(conn, NET_PRICE)


def test_years_are_returned_oldest_first_and_contiguous(conn):
    years = years_available(conn, ADMISSIONS)
    assert years == sorted(years)
    assert len(years) >= 10
    assert years == list(range(years[0], years[-1] + 1))


def test_latest_year_is_the_last_year_available(conn):
    for table in (NET_PRICE, ADMISSIONS):
        assert latest_year(conn, table) == years_available(conn, table)[-1]


def test_an_unknown_table_is_none_rather_than_an_error(conn):
    assert latest_year(conn, "no_such_table") is None
    assert years_available(conn, "no_such_table") == []
    assert series_ends(conn, "no_such_table") is False


def test_empty_years_are_recorded_not_discarded(conn):
    """The empty rows are the evidence; dropping them breaks series_ends."""
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM ingest_runs WHERE table_name = ? AND rows = 0",
        (NET_PRICE,),
    ).fetchone()
    assert row["n"] > 0
