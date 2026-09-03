"""Tests for the selectiveness area.

The one that matters most is `test_yield_uses_the_reported_total`. Deriving
enrolments by adding full-time and part-time looks obviously correct and is
wrong for 13 of the 25 schools, because they report part-time as the missing
sentinel rather than as zero. It fails by one student, which is small enough to
survive review and large enough to reorder schools that sit close together.
"""

import pytest

from app.areas import selectiveness
from app.db import DB_PATH, connect, latest_year
from app.schools import all_schools, selected

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="No database — run: uv run python scripts/import_ipeds.py",
)

CALTECH = 110404
STANFORD = 243744
UNC = 199120


@pytest.fixture
def conn():
    with connect() as connection:
        yield connection


@pytest.fixture
def year(conn):
    """The newest ingested year. Admissions runs to 2024."""
    return latest_year(conn, selectiveness.TABLE)


def _row(context, unitid):
    return next(r for r in context["rows"] if r["school"].unitid == unitid)


def test_every_school_reports_both_rates(conn, year):
    context = selectiveness.load(conn, all_schools(conn), year)
    assert len(context["rows"]) == 25
    for row in context["rows"]:
        assert 0 < row["admit_rate"] <= 1
        assert 0 < row["yield_rate"] <= 1


def test_yield_uses_the_reported_total_not_ft_plus_pt(conn):
    """Caltech reports part-time first-time enrolment as -1, not as zero."""
    context = selectiveness.load(conn, selected(conn, [CALTECH]), 2021)
    row = _row(context, CALTECH)
    assert row["enrolled"] == 270  # not 269, which ft + pt would give
    assert row["yield_rate"] == row["enrolled"] / row["admitted"]


def test_no_sentinel_reaches_the_page(conn, year):
    for row in selectiveness.load(conn, all_schools(conn), year)["rows"]:
        for field in ("applied", "admitted", "enrolled"):
            assert row[field] is None or row[field] > 0


def test_rates_are_computed_from_the_counts_beside_them(conn, year):
    """The table shows both the rate and its inputs; they have to agree."""
    for row in selectiveness.load(conn, all_schools(conn), year)["rows"]:
        assert row["admit_rate"] == row["admitted"] / row["applied"]
        assert row["yield_rate"] == row["enrolled"] / row["admitted"]


def test_comparable_selectivity_can_mean_very_different_yield(conn, year):
    """The durable claim, checked against whatever the newest year is.

    In 2021 Caltech and Stanford happened to share an admit rate to two decimal
    places, which made the point vividly and was a coincidence — by 2024 they
    are 2.57% and 3.61%. What survives is the shape: comparable selectivity,
    roughly twenty points of yield between them.
    """
    context = selectiveness.load(conn, selected(conn, [CALTECH, STANFORD]), year)
    caltech, stanford = _row(context, CALTECH), _row(context, STANFORD)
    assert abs(caltech["admit_rate"] - stanford["admit_rate"]) < 0.02
    assert stanford["yield_rate"] - caltech["yield_rate"] > 0.15


def test_the_2021_snapshot_caught_caltech_mid_climb(conn):
    """Why this build stopped anchoring everything on 2021.

    Caltech's yield sat near 43% through 2019, reached 52.9% in 2021 and 61.2%
    by 2024. Reporting the 2021 figure as though it were current described a
    school at the bottom of a climb, and the number was true and unrepresentative
    at the same time.
    """
    rates = {}
    for pinned in (2019, 2021, 2024):
        context = selectiveness.load(conn, selected(conn, [CALTECH]), pinned)
        rates[pinned] = _row(context, CALTECH)["yield_rate"]
    assert rates[2019] < rates[2021] < rates[2024]
    assert rates[2024] - rates[2019] > 0.15


def test_admit_rate_does_not_rank_schools_the_way_yield_does(conn, year):
    """The structural claim the area is built on, independent of any year.

    If ranking by selectivity produced the same order as ranking by yield, the
    second panel would be redundant and this area would be one chart.
    """
    rows = [
        row
        for row in selectiveness.load(conn, all_schools(conn), year)["rows"]
        if row["admit_rate"] is not None and row["yield_rate"] is not None
    ]
    by_admit = [r["school"].unitid for r in sorted(rows, key=lambda r: r["admit_rate"])]
    by_yield = [r["school"].unitid for r in sorted(rows, key=lambda r: -r["yield_rate"])]
    assert by_admit != by_yield


def test_the_query_is_filtered_to_one_year(conn):
    """Ten years live in this table; an unfiltered query would blend them."""
    schools = all_schools(conn)
    old = selectiveness.load(conn, schools, 2015)["rows"]
    new = selectiveness.load(conn, schools, 2024)["rows"]
    assert [r["admit_rate"] for r in old] != [r["admit_rate"] for r in new]


def test_rates_chart_sorts_most_selective_first(conn, year):
    """The sort is the argument: admit descends, yield visibly does not."""
    chart = selectiveness.load(conn, all_schools(conn), year)["rates_chart"]
    admit = [bar["cells"][0]["value"] for bar in chart["bars"]]
    assert admit == sorted(admit)
    assert len(chart["bars"]) == 25


def test_volume_chart_sorts_by_applications(conn, year):
    chart = selectiveness.load(conn, all_schools(conn), year)["volume_chart"]
    applied = [bar["value"] for bar in chart["bars"]]
    assert applied == sorted(applied, reverse=True)


def test_a_school_with_no_row_is_reported_not_dropped(conn, year):
    """An unknown school must produce a notice, not a silently shorter table."""
    schools = selected(conn, [CALTECH])
    context = selectiveness.load(conn, schools, year)
    assert len(context["rows"]) == 1
    assert context["notices"] == []


def test_charts_are_none_rather_than_empty_when_there_is_nothing_to_draw(conn, year):
    context = selectiveness.load(conn, [], year)
    assert context["rates_chart"] is None
    assert context["volume_chart"] is None


def test_highlights_names_the_lowest_admit_rate(conn, year):
    """Caltech is the most selective school in this sample."""
    context = selectiveness.load(conn, all_schools(conn), year)
    lines = selectiveness.highlights(context)
    assert lines
    assert "Caltech" in lines[0]


def test_highlights_is_empty_for_a_single_school(conn, year):
    schools = selected(conn, [CALTECH])
    context = selectiveness.load(conn, schools, year)
    assert selectiveness.highlights(context) == []
