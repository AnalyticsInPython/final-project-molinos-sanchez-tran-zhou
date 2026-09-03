"""Tests for the athletics area.

Two guard traps rather than logic, and both are traps that return a believable
number. `test_athletes_are_counted_once` catches the duplicated participant
count; `test_zero_athletic_aid_is_a_real_answer` catches the instinct to treat
$0 as missing, which would hide the most useful thing an Ivy can tell a recruit.
"""

import pytest

from app.areas import athletics
from app.db import DB_PATH, connect, latest_year, years_available
from app.schools import all_schools, selected

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="No database — run: uv run python scripts/import_ipeds.py && "
    "uv run python scripts/import_eada.py",
)

CALTECH, DARTMOUTH, UCLA, PRINCETON = 110404, 182670, 110662, 186131


@pytest.fixture
def conn():
    with connect() as connection:
        yield connection


@pytest.fixture
def year(conn):
    return latest_year(conn, athletics.TABLE)


def _row(context, unitid):
    return next(r for r in context["rows"] if r["school"].unitid == unitid)


def test_every_school_reports_a_share(conn, year):
    rows = athletics.load(conn, all_schools(conn), year)["rows"]
    assert len(rows) == 25
    for row in rows:
        assert 0 < row["share"] < 1


def test_athletes_are_counted_once(conn, year):
    """UNDUP_CT_*, not PARTIC_*: a runner on two teams is one person.

    If this starts failing high, someone has switched to the per-sport counts
    and every share on the page is overstated.
    """
    context = athletics.load(conn, selected(conn, [DARTMOUTH]), year)
    row = _row(context, DARTMOUTH)
    assert row["athletes"] == row["men"] + row["women"]
    assert row["athletes"] < row["enrolled"]


def test_zero_athletic_aid_is_a_real_answer(conn, year):
    """The Ivy League and Division III award none. That is information."""
    context = athletics.load(conn, selected(conn, [PRINCETON, CALTECH, UCLA]), year)
    assert _row(context, PRINCETON)["per_athlete"] == 0  # Ivy: need-based only
    assert _row(context, CALTECH)["per_athlete"] == 0  # Division III
    assert _row(context, UCLA)["per_athlete"] > 0
    # Zero must survive into the chart rather than being filtered out as falsy.
    names = [b["name"] for b in context["aid_chart"]["bars"]]
    assert "Princeton" in names and "Caltech" in names


def test_the_spread_is_why_this_area_exists(conn, year):
    """A twelvefold range, where graduation rates give almost none."""
    rows = athletics.load(conn, all_schools(conn), year)["rows"]
    shares = [r["share"] for r in rows]
    assert max(shares) / min(shares) > 5


def test_a_big_public_and_a_small_private_are_opposite(conn, year):
    context = athletics.load(conn, selected(conn, [CALTECH, UCLA]), year)
    assert _row(context, CALTECH)["share"] > 4 * _row(context, UCLA)["share"]


def test_the_query_is_filtered_to_one_year(conn):
    """Six years live in this table; an unfiltered query would blend them."""
    schools = all_schools(conn)
    old = athletics.load(conn, schools, 2019)["rows"]
    new = athletics.load(conn, schools, 2024)["rows"]
    assert [r["share"] for r in old] != [r["share"] for r in new]


def test_the_share_chart_sorts_widest_first(conn, year):
    chart = athletics.load(conn, all_schools(conn), year)["share_chart"]
    widths = [b["width"] for b in chart["bars"]]
    assert widths == sorted(widths, reverse=True)


def test_trend_covers_the_ingested_years(conn):
    years = years_available(conn, athletics.TABLE)
    assert len(years) >= 5
    context = athletics.trend(conn, selected(conn, [CALTECH, UCLA]), years)
    assert len(context["panels"]) == 2
    assert context["panels"][0]["chart"]["series"]


def test_coverage_only_claims_school_years_it_can_draw(conn):
    """The picker greys out against this, so it must not over-report."""
    pairs = athletics.coverage(conn)
    assert pairs
    for unitid, pinned in sorted(pairs)[:3]:
        context = athletics.load(conn, selected(conn, [unitid]), pinned)
        assert context["rows"][0]["share"] is not None


def test_a_year_nobody_reported_is_absent_from_coverage(conn):
    """2020 is short three schools; the picker should show that year amber."""
    years = {y: 0 for y in years_available(conn, athletics.TABLE)}
    for _, y in athletics.coverage(conn):
        years[y] += 1
    assert years[2020] < max(years.values())
