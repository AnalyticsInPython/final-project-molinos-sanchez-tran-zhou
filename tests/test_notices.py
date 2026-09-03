"""Tests for the data-quality notices.

These guard wording as much as logic, because the wording is the feature. A
notice that says "out of date" and stops has thrown away the true and useful
half — that a stale figure is a bad quote and still a good comparison. Two
of them guard facts rather than tone: which agency published the figure, and
whether a newer year could exist at all.
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
    notice = age_notice(2023, subject="net price", as_of=2026, series_ends=True)
    assert notice.level == "info"
    assert "2023" in notice.text


def test_five_years_old_warns_and_keeps_the_comparison():
    notice = age_notice(2021, subject="net price", as_of=2026, series_ends=True)
    assert notice.level == "warn"
    assert "2021" in notice.text
    assert "5 years old" in notice.text
    # The half that still works has to survive the warning.
    assert "comparison" in notice.text
    assert "quote" in notice.text


def test_an_ended_series_may_claim_to_be_the_newest_that_exists():
    notice = age_notice(2021, subject="net price", as_of=2026, series_ends=True)
    assert "most recent IPEDS publishes" in notice.text


def test_our_own_stale_ingest_does_not_blame_the_survey():
    """Admissions runs to 2024. Claiming 2021 is the newest available is a lie."""
    notice = age_notice(2021, subject="admissions", as_of=2026)
    assert notice.level == "warn"
    assert "most recent IPEDS publishes" not in notice.text
    assert "has not loaded" in notice.text
    assert "comparison" in notice.text


def test_the_honest_branch_is_the_default():
    """An area has to assert its series ended; it is not assumed."""
    assert "newer years" in age_notice(2022, subject="x", as_of=2026).text


def test_the_source_is_the_callers_to_name():
    """Every branch that names an agency takes it from the area. The default
    is IPEDS because thirteen of the fourteen ingest tables are."""
    ours = age_notice(2021, subject="athletics", as_of=2026, source="EADA")
    assert "EADA publishes newer years" in ours.text
    assert "IPEDS" not in ours.text

    theirs = age_notice(2021, subject="athletics", as_of=2026, source="EADA", series_ends=True)
    assert "most recent EADA publishes" in theirs.text
    assert "IPEDS" not in theirs.text

    assert "IPEDS publishes newer years" in age_notice(2021, subject="x", as_of=2026).text


def test_a_pooled_release_says_what_the_figures_are_not_what_was_skipped():
    """After graduation holds one year because the Scorecard pools several
    entry cohorts into one release, not because an ingest stopped early.
    Saying "this build has not loaded" newer years names a year that does
    not exist and blames the wrong side for it."""
    notice = age_notice(
        2021,
        subject="post-graduation earnings",
        as_of=2026,
        source="College Scorecard",
        single_release=True,
    )
    assert notice.level == "warn"
    assert "5 years old" in notice.text, "the age itself is still true and still warned about"
    assert "pools several entry cohorts" in notice.text
    assert "no newer year to load" in notice.text
    assert "has not loaded" not in notice.text
    assert "IPEDS" not in notice.text


def test_a_pooled_release_inside_the_stale_boundary_is_context():
    notice = age_notice(
        2023,
        subject="post-graduation earnings",
        as_of=2026,
        source="College Scorecard",
        single_release=True,
    )
    assert notice.level == "info"
    assert "2023" in notice.text
    assert "no newer year to load" in notice.text


def test_an_ended_series_outranks_a_single_release():
    """A one-year table with an empty year recorded above it is the survey
    saying it stops there, which is a different sentence."""
    notice = age_notice(2021, subject="x", as_of=2026, series_ends=True, single_release=True)
    assert "most recent IPEDS publishes" in notice.text
    assert "pools" not in notice.text


def test_the_stale_boundary_is_where_it_says_it_is():
    for ends in (True, False):
        fresh = age_notice(2026 - STALE + 1, subject="x", as_of=2026, series_ends=ends)
        stale = age_notice(2026 - STALE, subject="x", as_of=2026, series_ends=ends)
        assert fresh.level == "info"
        assert stale.level == "warn"


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


def test_for_area_hands_the_source_and_the_pooling_through():
    """The route knows both — it holds the area module and the connection —
    and this is the only path the page's freshness notice takes."""
    (age,) = for_area(
        2021,
        [],
        subject="post-graduation earnings",
        as_of=2026,
        source="College Scorecard",
        single_release=True,
    )
    assert "College Scorecard pools several entry cohorts" in age.text
    assert "IPEDS" not in age.text


def test_notice_is_immutable():
    assert isinstance(Notice("info", "x"), Notice)
