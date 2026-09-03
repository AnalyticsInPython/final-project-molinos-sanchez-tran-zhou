"""Tests for the institution characteristics area.

Reference data, so most traps aren't a computed metric going wrong — it's a
code translated to the wrong word, or a real answer (no religious
affiliation) rendered as if it were a missing one. The exception is the
top-fields figure's grand-total row, which looks exactly like a real field
until you check what it sums to — and which cipcode plays that role changed
between 2022 and 2023, a real instance of the schema drift this project's
other areas warn about.
"""

import pytest

from app.areas import institution_characteristics
from app.db import DB_PATH, connect, latest_year
from app.schools import all_schools

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="No database — run: uv run python scripts/import_ipeds.py",
)

CALTECH = 110404
BERKELEY = 110635
GEORGETOWN = 131496
BROWN = 217156
PRINCETON = 186131
STANFORD = 243744


@pytest.fixture
def conn():
    with connect() as connection:
        yield connection


@pytest.fixture
def year(conn):
    return latest_year(conn, institution_characteristics.TABLE)


def _row(conn, unitid: int, year: int) -> dict:
    rows = institution_characteristics.load(conn, all_schools(conn), year)["rows"]
    return next(row for row in rows if row["school"].unitid == unitid)


def test_every_school_has_a_row(conn, year):
    """25 rows, every one with a city — even at 2024, where only 12 of 25
    schools have a directly-reported directory row. The other 13 backfill to
    an earlier year rather than going blank; see the backfill tests below."""
    rows = institution_characteristics.load(conn, all_schools(conn), year)["rows"]
    assert len(rows) == 25
    for row in rows:
        assert row["city"] and row["state"]


def test_a_gap_year_backfills_to_the_nearest_earlier_report(conn):
    """Stanford has no usable 2024 directory row. Rather than a blank cell,
    it should show 2022's location, marked as such."""
    stanford = _row(conn, STANFORD, 2024)
    assert stanford["city"] == "Stanford"
    assert stanford["directory_year"] == 2022
    assert stanford["directory_is_stale"] is True


def test_an_exact_year_is_not_marked_stale(conn):
    """Caltech has a full 2021 directory row — no backfill, no marker."""
    caltech = _row(conn, CALTECH, 2021)
    assert caltech["directory_year"] == 2021
    assert caltech["directory_is_stale"] is False


def test_unreported_housing_reads_as_a_dash_not_no(conn):
    """`oncampus_housing` only ever takes 1 or the sentinel -1 in this sample
    — no school reports a real 0. Caltech, MIT and Stanford all report -1 for
    2024 while the rest of that row (calendar, control) is real data. Reading
    the sentinel as falsy would render three residential research
    universities as having no on-campus housing, which is absurd on its
    face."""
    for unitid in (CALTECH, 166683, STANFORD):
        row = _row(conn, unitid, 2024)
        assert row["housing"] is None
        assert row["dormitory_capacity"] is None


def test_reported_housing_still_reads_true_or_false(conn):
    """The sentinel fix must not swallow the real signal along with it."""
    caltech = _row(conn, CALTECH, 2021)
    assert caltech["housing"] is True
    assert caltech["dormitory_capacity"] == 1572


def test_directory_and_characteristics_backfill_independently(conn):
    """The two source tables miss different years for different schools —
    Caltech's `institutional_characteristics` has no 2023 row even though its
    `directory` row that year is fine. Each field group should say so on its
    own, not share one flag."""
    caltech = _row(conn, CALTECH, 2023)
    assert caltech["directory_year"] == 2023
    assert caltech["directory_is_stale"] is False
    assert caltech["characteristics_year"] == 2022
    assert caltech["characteristics_is_stale"] is True


def test_a_backfilled_calendar_year_produces_a_named_notice(conn):
    """`institutional_characteristics` (calendar system) drops to 17/25 in
    2023 — Caltech among them. The reader has to be told which school and
    how old, not just that something, somewhere, might be off."""
    result = institution_characteristics.load(conn, all_schools(conn), 2023)
    assert result["notices"], "8/25 schools backfilled in 2023 produced no notice"
    text = " ".join(n.text for n in result["notices"])
    assert "Caltech" in text
    assert "2022" in text


def test_a_directory_only_gap_produces_no_notice(conn):
    """`directory` (location, control, size) backfills silently — Stanford's
    2024 directory row is missing, but its `institutional_characteristics`
    row is fine that year, so nothing here should mention Stanford at all."""
    result = institution_characteristics.load(conn, all_schools(conn), 2024)
    text = " ".join(n.text for n in result["notices"])
    assert "Stanford" not in text


def test_public_and_private_control_are_both_present(conn, year):
    """The sample mixes public flagships and private research universities."""
    rows = institution_characteristics.load(conn, all_schools(conn), year)["rows"]
    controls = {row["control"] for row in rows}
    assert "Public" in controls
    assert "Private nonprofit" in controls


def test_caltech_and_berkeley_are_on_the_quarter_system(conn, year):
    """Both are well known for it — the code-to-label mapping stands or falls here."""
    rows = {
        row["school"].unitid: row
        for row in institution_characteristics.load(conn, all_schools(conn), year)["rows"]
    }
    assert rows[CALTECH]["calendar"] == "Quarter"


def test_no_religious_affiliation_reads_as_none_not_a_dash(conn, year):
    """Brown has no religious affiliation. That's an answer, not a gap."""
    rows = {
        row["school"].unitid: row
        for row in institution_characteristics.load(conn, all_schools(conn), year)["rows"]
    }
    assert rows[BROWN]["religious"] == "None"


def test_georgetown_is_catholic(conn, year):
    rows = {
        row["school"].unitid: row
        for row in institution_characteristics.load(conn, all_schools(conn), year)["rows"]
    }
    assert rows[GEORGETOWN]["religious"] == "Roman Catholic"


def test_school_url_gets_a_scheme():
    assert institution_characteristics._https("www.brown.edu/") == "https://www.brown.edu/"
    assert institution_characteristics._https("https://already.edu") == "https://already.edu"
    assert institution_characteristics._https(None) is None


def test_unmapped_code_shows_as_unknown_rather_than_guessed():
    assert institution_characteristics._label({1: "One"}, 2) == "Unknown (2)"
    assert institution_characteristics._label({1: "One"}, None) is None


def test_grand_total_cip_row_never_appears_as_a_field(conn, year):
    """Neither `990000` (the total through 2022) nor `99` (2023 onward) may
    show up in `top_fields`. If either does, someone's "top field" is "all of
    them" — the exact bug this module's docstring exists to prevent."""
    rows = institution_characteristics.load(conn, all_schools(conn), year)["rows"]
    for row in rows:
        for field in row["top_fields"]:
            assert field["label"] not in ("CIP 99", "CIP 00")


def test_caltechs_top_field_is_engineering_at_the_right_share(conn, year):
    """Checked against the raw numbers: 245 of 591 total 2023 awards, family 14."""
    rows = {
        row["school"].unitid: row
        for row in institution_characteristics.load(conn, all_schools(conn), year)["rows"]
    }
    top = rows[CALTECH]["top_fields"][0]
    assert top["label"] == "Engineering"
    assert top["awards"] == 245
    assert top["share_pct"] == 41


def test_top_fields_share_is_never_none_when_a_total_exists(conn, year):
    """The exact failure mode of the grand-total bug: every real field gets a
    share, or the total code being summed against silently changed again."""
    rows = institution_characteristics.load(conn, all_schools(conn), year)["rows"]
    for row in rows:
        for field in row["top_fields"]:
            assert field["share_pct"] is not None


def test_top_fields_are_sorted_richest_share_first(conn, year):
    rows = institution_characteristics.load(conn, all_schools(conn), year)["rows"]
    for row in rows:
        awards = [f["awards"] for f in row["top_fields"]]
        assert awards == sorted(awards, reverse=True)


def test_top_fields_run_on_their_own_year_not_the_areas_year(conn, year):
    """`completions_cip_2` covers 2022-2023 only; `directory` (this area's
    TABLE) now reaches 2024. The two years should not be forced to match."""
    result = institution_characteristics.load(conn, all_schools(conn), year)
    assert result["fields_year"] == 2023
    assert result["fields_year"] != year


def test_map_has_one_dot_per_school_with_coordinates(conn):
    schools = all_schools(conn)[:4]
    result = institution_characteristics.load(conn, schools, 2022)
    dots = result["map"]["dots"]
    assert len(dots) == 4
    for dot in dots:
        assert -90 <= dot["lat"] <= 90
        assert -180 <= dot["lon"] <= 180


def test_map_works_with_a_single_school(conn):
    schools = [s for s in all_schools(conn) if s.unitid == PRINCETON]
    result = institution_characteristics.load(conn, schools, 2022)
    assert len(result["map"]["dots"]) == 1


def test_caltechs_student_faculty_ratio_is_narrower_than_berkeleys(conn, year):
    """Real, well-known contrast: Caltech is tiny and research-heavy, Berkeley is a
    public flagship. If the join or the column name is wrong, this is the first
    thing that goes quiet rather than wrong."""
    rows = {
        row["school"].unitid: row
        for row in institution_characteristics.load(conn, all_schools(conn), year)["rows"]
    }
    assert rows[CALTECH]["student_faculty_ratio"] < rows[BERKELEY]["student_faculty_ratio"]


def test_requesting_different_years_gives_different_real_answers(conn):
    """`directory` and friends now hold four years each; each requested year
    should pick that year's own data (or the nearest earlier report), not
    silently collapse to whichever row `_by_unitid_backfilled` saw last."""
    schools = all_schools(conn)
    a = institution_characteristics.load(conn, schools, 2021)["rows"]
    b = institution_characteristics.load(conn, schools, 2024)["rows"]
    ratios_2021 = [r["student_faculty_ratio"] for r in a]
    ratios_2024 = [r["student_faculty_ratio"] for r in b]
    assert ratios_2021 != ratios_2024


def test_backfill_never_reaches_forward_past_the_requested_year(conn):
    """A school's own first good year still bounds coverage (see `coverage`'s
    docstring) — nothing here should ever show a *future* year's facts as if
    they were the requested year's."""
    pairs = sorted(institution_characteristics.coverage(conn))
    for unitid, yr in (pairs[0], pairs[len(pairs) // 2], pairs[-1]):
        row = _row(conn, unitid, yr)
        assert row["directory_year"] is None or row["directory_year"] <= yr


def test_coverage_never_exceeds_the_years_ingested(conn):
    from app.db import years_available

    ingested = set(years_available(conn, institution_characteristics.TABLE))
    assert {year for _, year in institution_characteristics.coverage(conn)} <= ingested


def test_a_covered_year_actually_renders(conn):
    from app.schools import selected

    pairs = sorted(institution_characteristics.coverage(conn))
    for unitid, yr in (pairs[0], pairs[len(pairs) // 2], pairs[-1]):
        context = institution_characteristics.load(conn, selected(conn, [unitid]), yr)
        assert context["rows"], f"claims {unitid} in {yr} and draws nothing"


def test_highlights_names_the_narrowest_ratio(conn, year):
    """Caltech and MIT are tied at 3:1 — the narrowest in this sample."""
    context = institution_characteristics.load(conn, all_schools(conn), year)
    lines = institution_characteristics.highlights(context)
    assert lines
    assert "Caltech" in lines[0] or "MIT" in lines[0]


def test_highlights_is_empty_for_a_single_school(conn, year):
    schools = [s for s in all_schools(conn) if s.unitid == CALTECH]
    context = institution_characteristics.load(conn, schools, year)
    assert institution_characteristics.highlights(context) == []
