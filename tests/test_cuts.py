"""Tests for cuts — a metric broken out by a group of students, beside everyone.

Two of these guard rules that would otherwise quietly erode. The reader's own
code never goes in the URL (`test_the_link_carries_the_dimension_not_the_person`),
and "unknown" is never drawn while "international" is drawn only as someone's
own group (`test_reporting_categories_are_not_offered_as_groups`).
"""

import pytest

from app import cuts
from app.areas import retention, selectiveness
from app.db import DB_PATH, connect, latest_year
from app.profiles import Profile
from app.schools import all_schools, selected

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="No database — run: uv run python scripts/import_ipeds.py",
)

CALTECH, MICHIGAN, BROWN = 110404, 170976, 217156


def _profile(**values) -> Profile:
    return Profile(
        username="t", sat_score=None, act_score=None, income_bracket=None, shortlist=[], **values
    )


@pytest.fixture
def conn():
    with connect() as connection:
        yield connection


def _row(context, unitid):
    return next(r for r in context["rows"] if r["school"].unitid == unitid)


# --- URL state --------------------------------------------------------------


def test_parse_keeps_only_well_formed_pairs():
    assert cuts.parse(["selectiveness:sex", "junk", "a:b:c", ":x", "retention:race"]) == {
        "selectiveness": "sex",
        "retention": "race",
    }
    assert cuts.parse(None) == {}


def test_the_link_replaces_one_areas_cut_and_keeps_the_rest():
    params = [("school", "1"), ("school", "2"), ("cut", "retention:race"), ("year", "2021")]
    href = cuts.link(params, "selectiveness", "sex")
    assert href == (
        "/compare?school=1&school=2&cut=retention%3Arace&year=2021&cut=selectiveness%3Asex"
    )
    assert cuts.link(params, "retention", None) == "/compare?school=1&school=2&year=2021"


def test_the_link_carries_the_area_not_the_person():
    """Tailoring is a per-area flag. The reader's code is resolved server-side
    from the profile, so a shared URL never says what the sharer's race or sex is."""
    on = cuts.tailor_link([("school", "1")], "selectiveness", True)
    assert on == "/compare?school=1&tailor=selectiveness"
    both = [("school", "1"), ("tailor", "selectiveness"), ("tailor", "retention")]
    assert cuts.tailor_link(both, "retention", False) == "/compare?school=1&tailor=selectiveness"
    assert cuts.parse_tailor(["retention", "", "selectiveness"]) == {"retention", "selectiveness"}


# --- choosing -------------------------------------------------------------------


def test_an_area_without_cuts_never_gets_one():
    from app.areas import outcomes

    assert cuts.choose(outcomes, "sex", _profile(gender=2)) is None


def test_an_explicit_choice_without_tailoring_has_no_emphasis():
    assert cuts.choose(selectiveness, "sex", None) == cuts.Selection("sex", None)
    assert cuts.choose(selectiveness, "race", None) is None


def test_tailoring_picks_what_the_profile_holds():
    assert cuts.choose(selectiveness, None, _profile(gender=2)) == cuts.Selection("sex", 2)
    assert cuts.choose(retention, None, _profile(race=3)) == cuts.Selection("race", 3)
    # An explicit choice is respected; the profile only adds the emphasis.
    assert cuts.choose(selectiveness, "sex", _profile(gender=1)) == cuts.Selection("sex", 1)


def test_declining_to_say_drives_nothing():
    """Gender 0 and race 9 are a person declining the question, not a group."""
    assert cuts.choose(selectiveness, None, _profile(gender=0)) is None
    assert cuts.choose(retention, None, _profile(race=9)) is None
    assert cuts.signals(selectiveness, _profile(gender=0, race=9)) == []
    assert cuts.signals(retention, _profile(gender=0, race=9)) == []


def test_signals_name_what_the_button_will_use():
    reader = _profile(gender=2, race=3)
    assert cuts.signals(selectiveness, reader) == ["Women"]
    assert cuts.signals(retention, reader) == ["Hispanic"]
    assert cuts.wants(selectiveness) == ["sex"] and cuts.wants(retention) == ["race"]


# --- admit rate by sex ---------------------------------------------------------


def test_every_school_reports_admits_by_sex(conn):
    year = latest_year(conn, selectiveness.TABLE)
    context = selectiveness.cut(conn, all_schools(conn), year, cuts.Selection("sex"))
    for row in context["rows"]:
        assert row["total"] is not None
        assert set(row["rates"]) == {1, 2}, row["school"].short


def test_the_sex_gap_runs_both_ways(conn):
    """Carnegie Mellon admits women at a higher rate; Brown admits men. A cut
    that only ever showed one direction would be a bug, not a finding."""
    year = latest_year(conn, selectiveness.TABLE)
    context = selectiveness.cut(conn, all_schools(conn), year, cuts.Selection("sex"))
    cmu = next(r for r in context["rows"] if r["school"].short == "Carnegie Mellon")
    brown = _row(context, BROWN)
    assert cmu["rates"][2] > cmu["rates"][1]
    assert brown["rates"][1] > brown["rates"][2]


def test_everyone_is_the_published_total_not_the_sum(conn):
    """Sex codes 3 and 9 exist from 2022, so the two drawn groups need not add
    up to the total. The reference is the row IPEDS publishes as 99."""
    year = latest_year(conn, selectiveness.TABLE)
    context = selectiveness.cut(conn, selected(conn, [MICHIGAN]), year, cuts.Selection("sex"))
    row = _row(context, MICHIGAN)
    published = conn.execute(
        "SELECT number_admitted * 1.0 / number_applied FROM admissions_enrollment "
        "WHERE unitid = ? AND year = ? AND sex = 99",
        (MICHIGAN, year),
    ).fetchone()[0]
    assert row["total"] == pytest.approx(published)


def test_emphasis_marks_exactly_one_dot_per_school(conn):
    year = latest_year(conn, selectiveness.TABLE)
    context = selectiveness.cut(conn, all_schools(conn), year, cuts.Selection("sex", 2))
    assert context["own_label"] == "Women"
    for bar in context["figure"]["bars"]:
        assert sum(dot["own"] for dot in bar["dots"]) == 1
        assert bar["text"].startswith("Women ")


# --- six-year completion by race ----------------------------------------------


@pytest.fixture
def grad_year(conn):
    return latest_year(conn, retention.TABLE)


def test_the_race_cut_reproduces_the_michigan_gap(conn, grad_year):
    context = retention.cut(conn, selected(conn, [MICHIGAN]), grad_year, cuts.Selection("race"))
    row = _row(context, MICHIGAN)
    assert row["rates"][2] < row["total"] < row["rates"][4]


def test_small_groups_are_suppressed_and_named(conn, grad_year):
    context = retention.cut(conn, selected(conn, [CALTECH]), grad_year, cuts.Selection("race", 5))
    row = _row(context, CALTECH)
    assert row["suppressed"], "Caltech's 231-student cohort has groups under 30"
    assert all(row["counts"][code] >= cuts.MIN_COHORT for code in row["rates"])
    if 5 in row["suppressed"]:
        text = " ".join(n.text for n in context["notices"])
        assert "Fewer than 30" in text and "Caltech" in text


def test_reporting_categories_are_not_offered_as_groups(conn, grad_year):
    """Unknown (9) is never a column. International (8) appears only as the
    reader's own group — IPEDS files them there regardless of race."""
    asked = retention.cut(conn, selected(conn, [MICHIGAN]), grad_year, cuts.Selection("race"))
    assert 9 not in dict(asked["columns"]) and 8 not in dict(asked["columns"])
    own = retention.cut(conn, selected(conn, [MICHIGAN]), grad_year, cuts.Selection("race", 8))
    assert 8 in dict(own["columns"]) and 9 not in dict(own["columns"])
    assert own["own_label"] == "International"


def test_the_cut_is_drawn_against_its_own_surveys_total(conn, grad_year):
    """Rule 1: everyone is grad_rates' race = 99 row, not the outcome_measures
    six-year rate the headline uses. They happen to agree here; they are not
    the same number and the code must not assume they are."""
    context = retention.cut(conn, selected(conn, [MICHIGAN]), grad_year, cuts.Selection("race"))
    published = conn.execute(
        "SELECT completion_rate_150pct FROM grad_rates WHERE unitid = ? AND year = ? "
        "AND subcohort = 99 AND sex = 99 AND race = 99",
        (MICHIGAN, grad_year),
    ).fetchone()[0]
    assert _row(context, MICHIGAN)["total"] == pytest.approx(published)


# --- the route ------------------------------------------------------------------


def test_the_page_draws_a_cut_only_when_asked():
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    base = f"/compare?school={MICHIGAN}&school={BROWN}&area=selectiveness"
    plain = client.get(base).text
    assert "Admit rate by sex" not in plain
    assert plain.count('class="cuts"') == 1, "one Show-by menu per card"
    assert "Tailor data for me" not in plain, "signed out, no tailoring control at all"

    cut = client.get(base + "&cut=selectiveness:sex").text
    assert "Admit rate by sex" in cut
    assert "Everyone only" in cut
    assert "Tailored to you" not in cut

    # Every card gets the menu, including one whose survey has no breakdown.
    more = client.get(base + "&area=outcomes").text
    assert more.count('class="cuts"') == 2
    assert "This survey has no breakdowns" in more

    # Trend view: the menu stays, says why it is empty, and a cut in the URL
    # is ignored rather than drawn.
    trend = client.get(base + "&year=2020&year=2024&cut=selectiveness:sex").text
    assert "Admit rate by sex" not in trend
    assert "Available on the single-year view" in trend


def test_tailoring_reads_the_profile_and_never_the_url(tmp_path, monkeypatch):
    """`tailor=1` with a signed-in profile draws each area's cut with the
    reader's own group emphasised. The page says which signals it used, and
    the link it offers to turn tailoring off carries no code for either."""
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app import profiles
    from app.main import app

    real_connect = profiles.connect
    monkeypatch.setattr(profiles, "connect", lambda: real_connect(tmp_path / "profiles.db"))
    with profiles.connect() as pconn:
        profiles.get_or_create(pconn, "reader")
        pconn.execute("UPDATE profiles SET gender = 2, race = 3 WHERE username = 'reader'")
        pconn.commit()

    client = TestClient(app, cookies={"profile": "reader"})
    base = f"/compare?school={MICHIGAN}&school={BROWN}&area=selectiveness&area=retention"

    off = client.get(base).text
    assert "Tailored to you" not in off
    assert off.count("Tailor data for me") == 2, "one button per card that can use the profile"
    assert "Uses your profile: Women" in off and "Uses your profile: Hispanic" in off

    one = client.get(base + "&tailor=selectiveness").text
    assert "Tailored to you: Women" in one
    assert "Tailored to you: Hispanic" not in one, "tailoring is per card"

    on = client.get(base + "&tailor=selectiveness&tailor=retention").text
    assert "Tailored to you: Women" in on
    assert "Tailored to you: Hispanic" in on
    assert on.count("Tailored to you &middot; stop") == 2
    for code in ("gender=2", "race=3", "sex:2", "race:3"):
        assert code not in on, f"{code} must never appear in a link"

    # An explicit choice on one area keeps the emphasis from the profile.
    both = client.get(base + "&tailor=selectiveness&cut=selectiveness:sex").text
    assert "Tailored to you: Women" in both

    # A profile with nothing usable sees the button, disabled, told what to add.
    with profiles.connect() as pconn:
        profiles.get_or_create(pconn, "blank")
    empty = TestClient(app, cookies={"profile": "blank"}).get(base).text
    assert "Add your sex to your profile" in empty
    assert "Add your race to your profile" in empty
