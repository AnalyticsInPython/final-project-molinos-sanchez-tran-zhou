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
    series_notices,
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


# --- The trend view, where the axis is wider than the survey ----------------
#
# The bug these guard was on the page a day before the demo: asking financial
# aid for 2015-2024 drew "UC Berkeley, Stanford, MIT, Carnegie Mellon, and
# Michigan are missing some years in this range", which reads as five schools
# with holes and is one survey ending in 2021. Every assertion below is either
# "no school is named for the survey's own end" or "a school is still named for
# its own gap", because losing the second half would fix the wording by going
# quiet about a real gap.

NET_PRICE = list(range(2015, 2022))
FULL_WINDOW = list(range(2015, 2025))


def _every_year(schools, years):
    return {(school.unitid, year) for school in schools for year in years}


def test_the_end_of_a_series_is_not_a_schools_gap():
    """The demo case: 2015-2024 asked of a series that stops at 2021."""
    schools = [CALTECH, MIT, YALE]
    notices = series_notices(
        schools,
        FULL_WINDOW,
        _every_year(schools, NET_PRICE),
        subject="net price",
        published=NET_PRICE,
        ends=True,
    )
    (notice,) = notices
    assert "stops at 2021" in notice.text
    assert "IPEDS has published nothing newer" in notice.text
    assert "The axis runs to 2024" in notice.text
    for school in schools:
        assert school.short not in notice.text
    assert "missing some years" not in notice.text


def test_a_series_that_has_not_ended_does_not_claim_it_has():
    """Same shape, opposite fact: admissions runs on and this build stopped.

    The flattering branch — "IPEDS publishes nothing newer" — would tell a
    reader a 2021 admit rate is the best there is when 2024 exists.
    """
    schools = [CALTECH, MIT]
    (notice,) = series_notices(
        schools,
        FULL_WINDOW,
        _every_year(schools, NET_PRICE),
        subject="admissions",
        published=NET_PRICE,
        ends=False,
    )
    assert "stops at 2021" in notice.text
    assert "newest year this build has loaded" in notice.text
    assert "published nothing newer" not in notice.text


def test_the_source_is_the_callers_to_name_here_too():
    """Athletics is EADA, and crediting IPEDS for its end is a factual error."""
    schools = [CALTECH]
    (notice,) = series_notices(
        schools,
        list(range(2019, 2027)),
        _every_year(schools, range(2019, 2025)),
        subject="athletics",
        source="EADA",
        published=list(range(2019, 2025)),
        ends=True,
    )
    assert "EADA has published nothing newer" in notice.text
    assert "IPEDS" not in notice.text


def test_a_window_inside_the_series_says_nothing_at_all():
    """The demo's own trend flip, 2015-2021. Silence is the right answer."""
    schools = [CALTECH, MIT, YALE]
    assert (
        series_notices(
            schools,
            NET_PRICE,
            _every_year(schools, NET_PRICE),
            subject="net price",
            published=NET_PRICE,
            ends=True,
        )
        == []
    )


def test_a_real_gap_still_names_the_school():
    """The half that must survive the fix.

    MIT is missing 2018 while the other two report it, which is a gap in MIT's
    reporting rather than in the survey, and the reader looking at a broken
    line needs to be told whose it is.
    """
    schools = [CALTECH, MIT, YALE]
    seen = _every_year(schools, NET_PRICE) - {(MIT.unitid, 2018)}
    (notice,) = series_notices(
        schools, NET_PRICE, seen, subject="net price", published=NET_PRICE, ends=True
    )
    assert notice.text.startswith("MIT is missing some years")
    assert CALTECH.short not in notice.text


def test_a_real_gap_and_a_series_end_are_two_separate_sentences():
    """Both facts at once: the survey stopped, and MIT is short a year inside it."""
    schools = [CALTECH, MIT, YALE]
    seen = _every_year(schools, NET_PRICE) - {(MIT.unitid, 2018)}
    ending, gap = series_notices(
        schools, FULL_WINDOW, seen, subject="net price", published=NET_PRICE, ends=True
    )
    assert "stops at 2021" in ending.text and "MIT" not in ending.text
    assert "MIT is missing some years" in gap.text


def test_a_year_nobody_here_reports_is_nobody_here_s_fault():
    """A hole every school shares is the survey's, and naming all three for it
    is the same mistake in a smaller window."""
    schools = [CALTECH, MIT, YALE]
    seen = _every_year(schools, [y for y in NET_PRICE if y != 2020])
    assert (
        series_notices(
            schools, NET_PRICE, seen, subject="net price", published=NET_PRICE, ends=True
        )
        == []
    )


def test_a_school_that_reports_none_of_the_series_is_still_named():
    schools = [CALTECH, MIT, YALE]
    seen = _every_year([CALTECH, YALE], NET_PRICE)
    (notice,) = series_notices(
        schools, NET_PRICE, seen, subject="net price", published=NET_PRICE, ends=True
    )
    # The strongest sentence the module has, and MIT has earned it: the other
    # two draw a line across the whole window and MIT draws nothing.
    assert notice.level == "warn"
    assert "MIT reports no net price data at all" in notice.text


def test_a_window_entirely_past_the_end_blames_nobody():
    """2022-2024 of a series that stopped in 2021 draws nothing.

    The old arithmetic called that every school reporting nothing at all, which
    is the strongest accusation the module can make and the least deserved.
    """
    schools = [CALTECH, MIT, YALE]
    (notice,) = series_notices(
        schools,
        [2022, 2023, 2024],
        set(),
        subject="net price",
        published=NET_PRICE,
        ends=True,
    )
    assert "stops at 2021" in notice.text
    for school in schools:
        assert school.short not in notice.text


def test_a_window_that_opens_before_the_series_does():
    """EADA starts in 2019; a window opened for IPEDS starts four years earlier."""
    schools = [CALTECH, MIT]
    years = list(range(2015, 2025))
    (notice,) = series_notices(
        schools,
        years,
        _every_year(schools, range(2019, 2025)),
        subject="athletics",
        source="EADA",
        published=list(range(2019, 2025)),
        ends=False,
    )
    assert "begins in 2019" in notice.text
    for school in schools:
        assert school.short not in notice.text


def test_without_a_published_span_nothing_is_asserted_about_the_survey():
    """`years_available` can come back empty for a table outside the ingest.

    No claim about where the series starts or stops is then available, so none
    is made — and every requested year is fair game for a per-school gap again.
    """
    schools = [CALTECH, MIT]
    seen = _every_year([CALTECH], NET_PRICE) | _every_year([MIT], NET_PRICE[:-1])
    (notice,) = series_notices(schools, NET_PRICE, seen, subject="net price")
    assert "MIT is missing some years" in notice.text
