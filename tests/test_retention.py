"""Tests for the retention and graduation area.

Three guard published fields that are present, plausible and wrong:
`completers_100pct` in grad_rates is the missing sentinel in every row of this
sample, `completion_rate_4yr` in outcome_measures reads zero for every
institution, and a cohort of three students will happily report "33%". All
three would produce a chart that looks finished.

`test_the_derivation_matches_the_published_six_year_rate` is the one that makes
the four-year figure trustworthy: the same arithmetic, applied to the six-year
awards, has to reproduce the rate IPEDS publishes.
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

STANFORD, MICHIGAN, NOTRE_DAME, UNC = 243744, 170976, 152080, 199120


@pytest.fixture
def conn():
    with connect() as connection:
        yield connection


@pytest.fixture
def year(conn):
    return latest_year(conn, retention.TABLE)


def _row(context, unitid):
    return next(r for r in context["rows"] if r["school"].unitid == unitid)


def test_every_school_reports_both_rates(conn, year):
    rows = retention.load(conn, all_schools(conn), year)["rows"]
    assert len(rows) == 25
    for row in rows:
        assert 0 < row["rate_4yr"] <= 1
        assert 0 < row["rate_6yr"] <= 1


def test_nobody_finishes_faster_in_six_years_than_in_four(conn, year):
    """Six-year awards are cumulative, so the gap can never be negative."""
    for row in retention.load(conn, all_schools(conn), year)["rows"]:
        assert row["rate_6yr"] >= row["rate_4yr"]
        assert row["took_longer"] >= 0


def test_the_derivation_matches_the_published_six_year_rate(conn, year):
    """Why the derived four-year rate can be trusted.

    completion_rate_4yr is published and reads zero everywhere, so both rates
    are computed from award counts instead. Running that same arithmetic on the
    six-year awards has to reproduce the six-year rate IPEDS does publish. If
    this fails, the four-year figure is not to be believed either.
    """
    published = dict(
        conn.execute(
            "SELECT unitid, completion_rate_6yr FROM outcome_measures "
            "WHERE year = ? AND ftpt = 1 AND fed_aid_type = 99 AND class_level = 1 "
            "AND completion_rate_6yr > 0",
            (year,),
        ).fetchall()
    )
    assert published
    for row in retention.load(conn, all_schools(conn), year)["rows"]:
        expected = published.get(row["school"].unitid)
        if expected is not None:
            assert abs(row["rate_6yr"] - expected) <= 0.011


def test_the_gap_is_the_finding(conn, year):
    """Two schools in the mid-nineties at six years, wildly different at four."""
    context = retention.load(conn, selected(conn, [STANFORD, NOTRE_DAME]), year)
    stanford, notre_dame = _row(context, STANFORD), _row(context, NOTRE_DAME)
    assert abs(stanford["rate_6yr"] - notre_dame["rate_6yr"]) < 0.03
    assert stanford["took_longer"] > 4 * notre_dame["took_longer"]


def test_one_row_per_school_from_a_table_that_repeats_them(conn, year):
    """outcome_measures carries each school three times, by class_level.

    1 is first-time entrants, 2 transfers, 99 pools them. Picking the wrong one
    silently compares different cohorts between schools.
    """
    count = conn.execute(
        "SELECT COUNT(*) FROM outcome_measures WHERE year = ? AND unitid = ? "
        "AND ftpt = 1 AND fed_aid_type = 99 AND class_level = 1",
        (year, MICHIGAN),
    ).fetchone()[0]
    assert count == 1


def test_a_cohort_of_three_cannot_carry_a_rate(conn, year):
    """Michigan reports 33% for 3 American Indian or Alaska Native students.

    One person's outcome moves that figure 33 points. Including it produced a
    62-point "spread" where the real one is nearer 12.
    """
    row = _row(retention.load(conn, selected(conn, [MICHIGAN]), year), MICHIGAN)
    assert row["suppressed"] >= 1
    assert row["race_range"] < 0.25


def test_reporting_categories_are_not_an_equity_gap(conn, year):
    """International and unknown describe filing, not a background."""
    excluded = {codes.RACE[c] for c in codes.NOT_AN_IDENTITY}
    for row in retention.load(conn, all_schools(conn), year)["rows"]:
        if row["best"]:
            assert row["best"]["race"] not in excluded
            assert row["worst"]["race"] not in excluded


def test_the_six_year_rate_sits_inside_the_range_by_race(conn, year):
    """The marker is the same measure as the dots — both 150% of normal time."""
    row = _row(retention.load(conn, selected(conn, [MICHIGAN]), year), MICHIGAN)
    assert row["worst"]["rate"] < row["rate_6yr"] < row["best"]["rate"]


def test_suppression_is_disclosed_not_silent(conn, year):
    context = retention.load(conn, selected(conn, [MICHIGAN]), year)
    assert "too small" in " ".join(n.text for n in context["notices"])


def test_no_sentinel_reaches_the_page(conn, year):
    for row in retention.load(conn, all_schools(conn), year)["rows"]:
        for key in ("rate_4yr", "rate_6yr", "retention", "cohort"):
            assert row[key] is None or row[key] > 0


def test_part_time_retention_is_never_read(conn, year):
    """ftpt = 2 is almost entirely sentinel across this sample."""
    for row in retention.load(conn, all_schools(conn), year)["rows"]:
        assert row["retention"] is None or 0 < row["retention"] <= 1


def test_the_query_is_filtered_to_one_year(conn):
    schools = all_schools(conn)
    old = retention.load(conn, schools, 2017)["rows"]
    new = retention.load(conn, schools, 2021)["rows"]
    assert [r["rate_4yr"] for r in old] != [r["rate_4yr"] for r in new]


def test_the_paired_chart_sorts_by_the_gap(conn, year):
    chart = retention.load(conn, all_schools(conn), year)["gap_chart"]
    gaps = [float(b["gap"].split()[0]) for b in chart["bars"]]
    assert gaps == sorted(gaps, reverse=True)


def test_trend_shows_both_rates_and_the_distance(conn):
    years = years_available(conn, retention.TABLE)
    context = retention.trend(conn, selected(conn, [STANFORD, NOTRE_DAME]), years)
    assert [p["title"] for p in context["panels"]] == [
        "Finishing in four years",
        "Finishing in six",
        "Taking longer than four years",
    ]
    assert context["panels"][0]["chart"]["series"]


def test_coverage_only_claims_what_it_can_draw(conn):
    pairs = retention.coverage(conn)
    assert pairs
    for unitid, pinned in sorted(pairs)[:3]:
        row = retention.load(conn, selected(conn, [unitid]), pinned)["rows"][0]
        assert row["took_longer"] is not None
