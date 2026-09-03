"""What a year on a card means, said on the card.

"2021" on the retention card is the class that started in fall 2014 — read
from the table's own cohort_year, not assumed — while on the selectiveness
card it is the class that entered in fall 2021. A reader asked exactly this
and the page should answer before they have to.
"""

import pytest

from app import areas
from app.db import DB_PATH, connect, latest_year

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="No database — run: uv run python scripts/import_ipeds.py",
)


@pytest.fixture
def conn():
    with connect() as connection:
        yield connection


def test_every_area_says_what_its_year_means(conn):
    for module in areas.ALL:
        year = latest_year(conn, module.TABLE)
        assert hasattr(module, "year_meaning"), module.KEY
        for trend in (False, True):
            text = module.year_meaning(conn, year, trend)
            assert text and text.endswith("."), (module.KEY, trend)


def test_retention_reads_the_cohort_from_the_table(conn):
    from app.areas import retention

    year = latest_year(conn, retention.TABLE)
    started = conn.execute(
        "SELECT cohort_year FROM outcome_measures WHERE year = ? AND cohort_year > 0 LIMIT 1",
        (year,),
    ).fetchone()[0]
    assert started < year - 5, "a six-year rate cannot describe a recent cohort"
    text = retention.year_meaning(conn, year)
    assert f"started in fall {started}" in text
    assert "one class" in text and "four years and again at six" in text, (
        "the four- and six-year rates share a cohort and the page must say so"
    )
    assert f"fall {year - 1}" in text, "retention's cohort is named separately"


def test_the_four_and_six_year_rates_share_one_cohort(conn):
    """The reason the wording insists on 'one class': both awards are counted
    against the same cohort_adj in the same row, and cohort_year is the fall
    that class entered — Stanford's cohort equals its fall entrants exactly."""
    row = conn.execute(
        "SELECT cohort_adj, cohort_year, cohort_adj_6yr FROM outcome_measures "
        "WHERE unitid = 243744 AND year = 2021 AND ftpt = 1 AND fed_aid_type = 99 "
        "AND class_level = 1"
    ).fetchone()
    assert row["cohort_adj_6yr"] < 0, "no separate six-year cohort in this survey structure"
    entrants = conn.execute(
        "SELECT prev_cohort_adj FROM fall_retention WHERE unitid = 243744 AND year = ? "
        "AND ftpt = 1",
        (row["cohort_year"] + 1,),
    ).fetchone()[0]
    assert row["cohort_adj"] == entrants


def test_the_race_cut_names_its_own_cohort(conn):
    from app import cuts
    from app.areas import retention
    from app.schools import selected

    year = latest_year(conn, retention.TABLE)
    started = conn.execute(
        "SELECT cohort_year FROM grad_rates WHERE year = ? LIMIT 1", (year,)
    ).fetchone()[0]
    context = retention.cut(conn, selected(conn, [170976]), year, cuts.Selection("race"))
    assert f"started in fall {started}" in context["note"]
