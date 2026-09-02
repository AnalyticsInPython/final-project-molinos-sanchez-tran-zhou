"""Tests for the selectiveness area.

The one that matters most is `test_yield_uses_the_reported_total`. Deriving
enrolments by adding full-time and part-time looks obviously correct and is
wrong for 13 of the 25 schools, because they report part-time as the missing
sentinel rather than as zero. It fails by one student, which is small enough to
survive review and large enough to reorder schools that sit close together.
"""

import pytest

from app.areas import selectiveness
from app.db import DB_PATH, connect
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


def _row(context, unitid):
    return next(r for r in context["rows"] if r["school"].unitid == unitid)


def test_every_school_reports_both_rates(conn):
    context = selectiveness.load(conn, all_schools(conn))
    assert len(context["rows"]) == 25
    for row in context["rows"]:
        assert 0 < row["admit_rate"] <= 1
        assert 0 < row["yield_rate"] <= 1


def test_yield_uses_the_reported_total_not_ft_plus_pt(conn):
    """Caltech reports part-time first-time enrolment as -1, not as zero."""
    context = selectiveness.load(conn, selected(conn, [CALTECH]))
    row = _row(context, CALTECH)
    assert row["enrolled"] == 270  # not 269, which ft + pt would give
    assert row["yield_rate"] == row["enrolled"] / row["admitted"]


def test_no_sentinel_reaches_the_page(conn):
    for row in selectiveness.load(conn, all_schools(conn))["rows"]:
        for field in ("applied", "admitted", "enrolled"):
            assert row[field] is None or row[field] > 0


def test_rates_are_computed_from_the_counts_beside_them(conn):
    """The table shows both the rate and its inputs; they have to agree."""
    for row in selectiveness.load(conn, all_schools(conn))["rows"]:
        assert row["admit_rate"] == row["admitted"] / row["applied"]
        assert row["yield_rate"] == row["enrolled"] / row["admitted"]


def test_the_finding_holds(conn):
    """Same admit rate, very different yield — the reason this area exists."""
    context = selectiveness.load(conn, selected(conn, [CALTECH, STANFORD]))
    caltech, stanford = _row(context, CALTECH), _row(context, STANFORD)
    assert round(caltech["admit_rate"], 3) == round(stanford["admit_rate"], 3)
    assert stanford["yield_rate"] - caltech["yield_rate"] > 0.25


def test_selectivity_does_not_predict_yield(conn):
    """UNC admits five times as many and holds a similar share of them."""
    context = selectiveness.load(conn, selected(conn, [CALTECH, UNC]))
    caltech, unc = _row(context, CALTECH), _row(context, UNC)
    assert unc["admit_rate"] > caltech["admit_rate"] * 4
    assert abs(unc["yield_rate"] - caltech["yield_rate"]) < 0.10


def test_rates_chart_sorts_most_selective_first(conn):
    """The sort is the argument: admit descends, yield visibly does not."""
    chart = selectiveness.load(conn, all_schools(conn))["rates_chart"]
    admit = [bar["cells"][0]["value"] for bar in chart["bars"]]
    assert admit == sorted(admit)
    assert len(chart["bars"]) == 25


def test_volume_chart_sorts_by_applications(conn):
    chart = selectiveness.load(conn, all_schools(conn))["volume_chart"]
    applied = [bar["value"] for bar in chart["bars"]]
    assert applied == sorted(applied, reverse=True)


def test_a_school_with_no_row_is_reported_not_dropped(conn):
    """An unknown school must produce a notice, not a silently shorter table."""
    schools = selected(conn, [CALTECH])
    context = selectiveness.load(conn, schools)
    assert len(context["rows"]) == 1
    assert context["notices"] == []


def test_charts_are_none_rather_than_empty_when_there_is_nothing_to_draw(conn):
    context = selectiveness.load(conn, [])
    assert context["rates_chart"] is None
    assert context["volume_chart"] is None
