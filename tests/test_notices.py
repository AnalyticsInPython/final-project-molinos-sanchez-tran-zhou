"""Tests for the data-quality notices.

These guard wording as much as logic, because the wording is the feature. A
notice that says "out of date" and stops has thrown away the true and useful
half — that a stale figure is a bad quote and still a good comparison.
"""

from app.notices import (
    LAG,
    STALE,
    Notice,
    age_notice,
    coverage_notices,
    for_area,
)
from app.schools import School

CALTECH = School(110404, "California Institute of Technology", "#ff6c0c")
MIT = School(166683, "Massachusetts Institute of Technology", "#a31f34")
YALE = School(130794, "Yale University", "#00356b")


def test_recent_data_says_nothing():
    """A notice on every area every time is a notice nobody reads."""
    assert age_notice(2026, subject="net price", as_of=2026) is None
    assert age_notice(2026 - LAG, subject="net price", as_of=2026) is None


def test_a_few_years_old_is_context_not_a_warning():
    notice = age_notice(2023, subject="net price", as_of=2026)
    assert notice.level == "info"
    assert "2023" in notice.text


def test_five_years_old_warns_and_keeps_the_comparison():
    notice = age_notice(2021, subject="net price", as_of=2026)
    assert notice.level == "warn"
    assert "2021" in notice.text
    assert "5 years old" in notice.text
    # The half that still works has to survive the warning.
    assert "comparison" in notice.text
    assert "quote" in notice.text


def test_the_stale_boundary_is_where_it_says_it_is():
    assert age_notice(2026 - STALE + 1, subject="x", as_of=2026).level == "info"
    assert age_notice(2026 - STALE, subject="x", as_of=2026).level == "warn"


def test_an_undated_figure_warns_rather_than_passing_silently():
    notice = age_notice(None, subject="net price")
    assert notice.level == "warn"
    assert "undated" in notice.text


def test_a_missing_school_is_named_not_counted():
    """A student who picked four schools needs to know it is theirs."""
    (notice,) = coverage_notices([CALTECH], [], subject="net price")
    assert notice.level == "warn"
    assert "Caltech" in notice.text
    assert "reports no net price data" in notice.text
    assert "not a zero" in notice.text


def test_two_and_three_missing_schools_read_as_english():
    (two,) = coverage_notices([CALTECH, MIT], [], subject="net price")
    assert "Caltech and MIT" in two.text
    assert "report no" in two.text  # plural verb

    (three,) = coverage_notices([CALTECH, MIT, YALE], [], subject="net price")
    assert "Caltech, MIT, and Yale" in three.text


def test_partial_data_is_separate_from_none_at_all():
    notices = coverage_notices([CALTECH], [MIT], subject="net price")
    assert [n.level for n in notices] == ["warn", "info"]
    assert "not zeros" in notices[1].text


def test_verbs_agree_with_the_number_of_schools():
    """Caught in the rendered page: "MIT report only part of this data"."""
    (one,) = coverage_notices([], [MIT], subject="net price")
    assert "MIT reports only part" in one.text

    (many,) = coverage_notices([], [MIT, YALE], subject="net price")
    assert "MIT and Yale report only part" in many.text


def test_full_coverage_says_nothing():
    assert coverage_notices([], [], subject="net price") == []


def test_age_is_stated_before_coverage():
    """Age qualifies every number; coverage qualifies one row."""
    coverage = coverage_notices([CALTECH], [], subject="net price")
    notices = for_area(2021, coverage, subject="net price", as_of=2026)
    assert len(notices) == 2
    assert "2021" in notices[0].text
    assert "Caltech" in notices[1].text


def test_fresh_data_with_full_coverage_produces_no_notices():
    assert for_area(2026, [], subject="net price", as_of=2026) == []


def test_notice_is_immutable():
    assert isinstance(Notice("info", "x"), Notice)
