"""Tests for the retention and graduation area.

The two that matter most guard the same instinct from opposite directions:
`test_a_cohort_of_three_cannot_carry_a_rate` and
`test_reporting_categories_are_not_an_equity_gap`. Both catch a number that
looks like a devastating finding and is an artefact — one of a tiny cohort, one
of how a registrar filed someone. Between them they moved Michigan's reported
spread from 62 points to 12.
"""

import pytest

from app import codes
from app.areas import retention
from app.db import DB_PATH, connect, latest_year, years_available
from app.schools import all_schools, selected

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="No database — run: uv run python scripts/import_ipeds.py",
)

MICHIGAN, BERKELEY, PRINCETON, UNC = 170976, 110635, 186131, 199120


@pytest.fixture
def conn():
    with connect() as connection:
        yield connection


@pytest.fixture
def year(conn):
    return latest_year(conn, retention.TABLE)


def _row(context, unitid):
    return next(r for r in context["rows"] if r["school"].unitid == unitid)


def test_almost_every_school_reports_a_pell_gap(conn, year):
    """Not all of them, and the exception is the point.

    Caltech's 2023 Pell cohort is 27 students, under the floor, so its gap is
    suppressed rather than reported from too few people. Everything else in
    the sample clears it.
    """
    rows = retention.load(conn, all_schools(conn), year)["rows"]
    assert len(rows) == 25
    reported = [r for r in rows if r["pell_gap"] is not None]
    assert len(reported) >= 24
    for row in reported:
        assert 0 < row["pell"] <= 1
        assert 0 < row["no_aid"] <= 1


def test_a_school_under_the_floor_is_suppressed_not_guessed(conn, year):
    caltech = _row(retention.load(conn, selected(conn, [110404]), year), 110404)
    assert caltech["pell_gap"] is None
    assert (110404, year) not in retention.coverage(conn)


def test_the_pell_gap_is_no_aid_minus_pell(conn, year):
    row = _row(retention.load(conn, selected(conn, [MICHIGAN]), year), MICHIGAN)
    assert row["pell_gap"] == row["no_aid"] - row["pell"]
    assert row["pell_gap"] > 0  # Michigan's Pell students finish at a lower rate


def test_a_cohort_of_three_cannot_carry_a_rate(conn, year):
    """Michigan reports 33% for 3 American Indian or Alaska Native students.

    One person's outcome moves that figure 33 points. Including it produced a
    62-point "spread" where the real one is 12. If this test fails, the floor
    has been removed and the chart is reporting noise as an equity gap.
    """
    row = _row(retention.load(conn, selected(conn, [MICHIGAN]), year), MICHIGAN)
    assert row["suppressed"] >= 1
    assert row["race_range"] < 0.20
    assert row["worst"]["race"] == "Black"


def test_reporting_categories_are_not_an_equity_gap(conn, year):
    """International and unknown describe filing, not a background.

    A range drawn across them measures the registrar. Neither may appear as
    the best or worst group at any school.
    """
    excluded = {codes.RACE[c] for c in codes.NOT_AN_IDENTITY}
    for row in retention.load(conn, all_schools(conn), year)["rows"]:
        if row["best"]:
            assert row["best"]["race"] not in excluded
            assert row["worst"]["race"] not in excluded


def test_the_headline_sits_inside_the_range_it_does_not_describe(conn, year):
    """The reason this area exists rather than printing one number."""
    row = _row(retention.load(conn, selected(conn, [MICHIGAN]), year), MICHIGAN)
    assert row["worst"]["rate"] < row["headline"] < row["best"]["rate"]


def test_a_tight_school_and_a_wide_one_are_distinguishable(conn, year):
    context = retention.load(conn, selected(conn, [PRINCETON, UNC]), year)
    assert _row(context, UNC)["race_range"] > 3 * _row(context, PRINCETON)["race_range"]


def test_suppression_is_disclosed_not_silent(conn, year):
    """Dropping people quietly is its own kind of lie."""
    context = retention.load(conn, selected(conn, [MICHIGAN, BERKELEY]), year)
    text = " ".join(n.text for n in context["notices"])
    assert "too small" in text
    assert "Michigan" in text


def test_part_time_retention_is_never_read(conn, year):
    """ftpt = 2 is almost entirely sentinel across this sample."""
    rows = retention.load(conn, all_schools(conn), year)["rows"]
    for row in rows:
        assert row["retention"] is None or 0 < row["retention"] <= 1


def test_no_sentinel_reaches_the_page(conn, year):
    for row in retention.load(conn, all_schools(conn), year)["rows"]:
        for key in ("headline", "retention", "pell", "no_aid"):
            assert row[key] is None or row[key] > 0


def test_the_query_is_filtered_to_one_year(conn):
    schools = all_schools(conn)
    old = retention.load(conn, schools, 2016)["rows"]
    new = retention.load(conn, schools, 2023)["rows"]
    assert [r["pell_gap"] for r in old] != [r["pell_gap"] for r in new]


def test_charts_sort_widest_first(conn, year):
    context = retention.load(conn, all_schools(conn), year)
    gaps = [b["gap"] for b in context["gap_chart"]["bars"]]
    assert gaps == sorted(gaps, key=lambda g: -float(g.split()[0]))


def test_trend_shows_whether_the_gap_is_closing(conn):
    years = years_available(conn, retention.TABLE)
    context = retention.trend(conn, selected(conn, [MICHIGAN, BERKELEY]), years)
    assert [p["title"] for p in context["panels"]] == [
        "The Pell gap over time",
        "Completion for students on a Pell grant",
    ]
    assert context["panels"][0]["chart"]["series"]


def test_coverage_only_claims_what_it_can_draw(conn):
    pairs = retention.coverage(conn)
    assert pairs
    for unitid, pinned in sorted(pairs)[:3]:
        row = retention.load(conn, selected(conn, [unitid]), pinned)["rows"][0]
        assert row["pell_gap"] is not None
