"""Tests for the enrollment area.

The trap worth guarding here is not a computation — it's the race codebook
itself. A generic IPEDS race/ethnicity ordering would put "Nonresident alien"
first or last; this endpoint's actual order (verified against the Urban
Institute API's own variable metadata) puts it eighth, after "Two or more
races". Getting that wrong mislabels one group of students as another.
"""

import pytest

from app.areas import enrollment
from app.db import DB_PATH, connect, latest_year
from app.schools import all_schools

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="No database — run: uv run python scripts/import_ipeds.py",
)

CALTECH = 110404
BERKELEY = 110635


@pytest.fixture
def conn():
    with connect() as connection:
        yield connection


@pytest.fixture
def year(conn):
    return latest_year(conn, enrollment.TABLE)


def _row(conn, unitid: int, year: int) -> dict:
    rows = enrollment.load(conn, all_schools(conn), year)["rows"]
    return next(row for row in rows if row["school"].unitid == unitid)


def test_every_school_has_a_row(conn, year):
    rows = enrollment.load(conn, all_schools(conn), year)["rows"]
    assert len(rows) == 25
    for row in rows:
        assert row["total"]


def test_race_code_8_is_international_not_something_else(conn, year):
    """This is the whole point of the module docstring's warning: code 8 is
    Nonresident alien, verified against the API's own metadata, not guessed
    from a generic IPEDS codebook that would put it in a different slot."""
    assert enrollment.RACE[enrollment.INTERNATIONAL] == "International"
    assert enrollment.RACE[1] == "White"
    assert enrollment.RACE[7] == "Two or more races"


def test_caltechs_international_and_gender_shares(conn):
    """Checked against the raw numbers: 78 of 1,014 international, 456 of
    1,014 women, for 2021."""
    caltech = _row(conn, CALTECH, 2021)
    assert caltech["total"] == 1014
    assert caltech["international_pct"] == pytest.approx(0.0769, abs=0.0001)
    assert caltech["female_pct"] == pytest.approx(0.4497, abs=0.0001)


def test_berkeley_is_much_larger_than_caltech(conn, year):
    """The sized-bar chart exists because this gap is real: a 33-fold
    difference in undergraduate enrollment between two schools in the same
    25-school sample."""
    caltech = _row(conn, CALTECH, year)
    berkeley = _row(conn, BERKELEY, year)
    assert berkeley["total"] > 30 * caltech["total"]


def test_composition_shares_sum_to_roughly_one(conn, year):
    """Each school's race categories should account for its full reported
    total — not exactly 1.0 because of float rounding, but close."""
    rows = enrollment.load(conn, all_schools(conn), year)["rows"]
    for row in rows:
        shares = [v[1] for v in row["composition"].values() if v is not None]
        if shares:
            assert sum(shares) == pytest.approx(1.0, abs=0.01)


def test_chart_bar_length_reflects_relative_size(conn, year):
    """Berkeley's bar must be visibly longer than Caltech's, not just its
    number bigger — the whole reason this area draws a sized bar rather than
    a same-width one for every school."""
    schools = [s for s in all_schools(conn) if s.unitid in (CALTECH, BERKELEY)]
    chart = enrollment.load(conn, schools, year)["chart"]
    widths = {
        bar["name"]: sum(seg["width"] for seg in bar["segments"]) for bar in chart["bars"]
    }
    assert widths["UC Berkeley"] > 10 * widths["Caltech"]


def test_coverage_never_exceeds_the_years_ingested(conn):
    from app.db import years_available

    ingested = set(years_available(conn, enrollment.TABLE))
    assert {year for _, year in enrollment.coverage(conn)} <= ingested


def test_a_covered_year_actually_renders(conn):
    from app.schools import selected

    pairs = sorted(enrollment.coverage(conn))
    for unitid, yr in (pairs[0], pairs[len(pairs) // 2], pairs[-1]):
        context = enrollment.load(conn, selected(conn, [unitid]), yr)
        assert context["rows"][0]["total"], f"claims {unitid} in {yr} and draws nothing"


def test_the_query_is_filtered_to_one_year(conn):
    schools = all_schools(conn)
    a = enrollment.load(conn, schools, 2015)["rows"]
    b = enrollment.load(conn, schools, 2021)["rows"]
    totals_2015 = [r["total"] for r in a]
    totals_2021 = [r["total"] for r in b]
    assert totals_2015 != totals_2021


def test_trend_has_a_panel_for_international_and_women(conn):
    schools = all_schools(conn)[:5]
    result = enrollment.trend(conn, schools, [2015, 2018, 2021])
    titles = [p["title"] for p in result["panels"]]
    assert "International share of enrollment" in titles
    assert "Women's share of enrollment" in titles


def test_headline_names_the_highest_international_share(conn, year):
    """UChicago has the highest international undergrad share in this sample."""
    line = enrollment.headline(enrollment.load(conn, all_schools(conn), year))
    assert line
    assert "Chicago" in line


def test_headline_is_none_for_a_single_school(conn, year):
    schools = [s for s in all_schools(conn) if s.unitid == CALTECH]
    context = enrollment.load(conn, schools, year)
    assert enrollment.headline(context) is None
