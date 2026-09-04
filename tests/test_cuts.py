"""Tests for cuts — a metric broken out by a group of students, beside everyone.

Two of these guard rules that would otherwise quietly erode. The reader's own
code never goes in the URL (`test_the_link_carries_the_dimension_not_the_person`),
and "unknown" is never drawn while "international" is drawn only as someone's
own group (`test_reporting_categories_are_not_offered_as_groups`).
"""

import re

import pytest

from app import codes, cuts
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


def _keys(page: str) -> list[str]:
    """The key drawn under each cut chart. Other areas draw keys of their own;
    only a cut's keys "Everyone", the published total it is measured against."""
    blocks = re.findall(r'<p class="keys">(.*?)</p>', page, re.S)
    return [block for block in blocks if "Everyone" in block]


def _reader(tmp_path, monkeypatch, **columns):
    """A signed-in client whose profile holds the given answers."""
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app import profiles
    from app.main import app

    real_connect = profiles.connect
    monkeypatch.setattr(profiles, "connect", lambda: real_connect(tmp_path / "profiles.db"))
    with profiles.connect() as pconn:
        profiles.get_or_create(pconn, "reader")
        for column, value in columns.items():
            pconn.execute(f"UPDATE profiles SET {column} = ? WHERE username = 'reader'", (value,))
        pconn.commit()
    return TestClient(app, cookies={"profile": "reader"})


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
        "/compare?school=1&school=2&cut=retention%3Arace&year=2021"
        "&cut=selectiveness%3Asex#area-selectiveness"
    )
    assert (
        cuts.link(params, "retention", None)
        == "/compare?school=1&school=2&year=2021#area-retention"
    )


def test_the_link_carries_the_area_not_the_person():
    """Tailoring is a per-area flag. The reader's code is resolved server-side
    from the profile, so a shared URL never says what the sharer's race or sex is."""
    on = cuts.tailor_link([("school", "1")], "selectiveness", True)
    assert on == "/compare?school=1&tailor=selectiveness#area-selectiveness"
    both = [("school", "1"), ("tailor", "selectiveness"), ("tailor", "retention")]
    assert cuts.tailor_link(both, "retention", False) == (
        "/compare?school=1&tailor=selectiveness#area-retention"
    )
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
    """Race 9 is a person declining the question, not a group.

    Sex code 0 was the same thing and has been withdrawn — the form now says
    "Prefer not to say" with a blank value instead of minting a code IPEDS has
    no row for. A profile saved while 0 was still offered has to keep working,
    and this is where that is checked: an unknown code is not a group, so it
    is not a cut and not a signal.
    """
    assert cuts.choose(selectiveness, None, _profile(gender=0)) is None
    assert cuts.choose(retention, None, _profile(race=9)) is None
    assert cuts.signals(selectiveness, _profile(gender=0, race=9)) == []
    assert cuts.signals(retention, _profile(gender=0, race=9)) == []
    # And an explicit "show me the sex cut" on such a profile draws the
    # groups with nobody emphasised, rather than raising on a missing label.
    assert cuts.choose(selectiveness, "sex", _profile(gender=0)) == cuts.Selection("sex", None)


def test_signals_name_what_the_button_will_use():
    reader = _profile(gender=2, race=3)
    assert cuts.signals(selectiveness, reader) == ["Female"]
    assert cuts.signals(retention, reader) == ["Hispanic"]
    assert cuts.wants(selectiveness) == ["sex"] and cuts.wants(retention) == ["race"]


# --- admit rate by sex ---------------------------------------------------------


def test_every_school_reports_admits_by_sex(conn):
    year = latest_year(conn, selectiveness.TABLE)
    context = selectiveness.cut(conn, all_schools(conn), year, cuts.Selection("sex"))
    for row in context["rows"]:
        assert row["total"] is not None
        assert set(row["rates"]) == {1, 2}, row["school"].short


def test_a_stored_code_zero_never_reaches_the_page(tmp_path, monkeypatch):
    """The retired third option, end to end: a profile holding 0 tailors to
    nothing, and the card offers the button disabled rather than half-drawing
    a group with no name."""
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app import profiles
    from app.main import app

    real_connect = profiles.connect
    monkeypatch.setattr(profiles, "connect", lambda: real_connect(tmp_path / "profiles.db"))
    with profiles.connect() as pconn:
        profiles.get_or_create(pconn, "early")
        pconn.execute("UPDATE profiles SET gender = 0 WHERE username = 'early'")
        pconn.commit()

    client = TestClient(app, cookies={"profile": "early"})
    base = f"/compare?school={MICHIGAN}&school={BROWN}&area=selectiveness"

    page = client.get(base + "&tailor=selectiveness")
    assert page.status_code == 200
    assert "Tailored to you" not in page.text
    assert "Add your sex to your profile" in page.text
    assert "Admit rate by sex" not in page.text


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
    assert context["own_label"] == "Female"
    assert dict(context["columns"]) == {1: "Male", 2: "Female"}
    for bar in context["figure"]["bars"]:
        assert sum(dot["own"] for dot in bar["dots"]) == 1
        assert bar["text"].startswith("Female ")


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
    assert "Uses your profile: Female" in off and "Uses your profile: Hispanic" in off

    one = client.get(base + "&tailor=selectiveness").text
    assert "Tailored to you: Female" in one
    assert "Tailored to you: Hispanic" not in one, "tailoring is per card"

    on = client.get(base + "&tailor=selectiveness&tailor=retention").text
    assert "Tailored to you: Female" in on
    assert "Tailored to you: Hispanic" in on
    assert on.count("Tailored to you &middot; stop") == 2
    for code in ("gender=2", "race=3", "sex:2", "race:3"):
        assert code not in on, f"{code} must never appear in a link"

    # An explicit choice on one area keeps the emphasis from the profile.
    both = client.get(base + "&tailor=selectiveness&cut=selectiveness:sex").text
    assert "Tailored to you: Female" in both

    # A profile with nothing usable sees the button, disabled, told what to add.
    with profiles.connect() as pconn:
        profiles.get_or_create(pconn, "blank")
    empty = TestClient(app, cookies={"profile": "blank"}).get(base).text
    assert "Add your sex to your profile" in empty
    assert "Add your race to your profile" in empty


# --- the key under the chart ----------------------------------------------------


def test_the_key_draws_the_marks_the_chart_draws(tmp_path, monkeypatch, conn):
    """Three roles, three shapes, and the key repeats them rather than
    describing them in a colour of its own.

    The reader's own group is a circle filled with each school's brand colour —
    a different colour on every row — so the key carries those colours and says
    so. It used to show one near-black swatch, a colour that appears nowhere on
    the chart but as the outline of the "everyone" square: a dot the reader
    would look for and never find. The groups beside it are named from
    `c.columns`, never spelled out in the template.
    """
    client = _reader(tmp_path, monkeypatch, gender=2, race=3)
    base = f"/compare?school={MICHIGAN}&school={BROWN}&area=selectiveness&area=retention"
    page = client.get(base + "&tailor=selectiveness&tailor=retention").text
    sex = next(k for k in _keys(page) if codes.SEX[2] in k)
    race = next(k for k in _keys(page) if "Hispanic" in k)

    assert "Other groups" not in page, "name the groups drawn, do not lump them"
    for shape in ("<circle", "<polygon", "<rect"):
        assert shape in sex and shape in race, f"the key is missing the {shape} mark"

    # Sex draws two groups, so both are named and the reader's own says whose
    # colour it takes: one circle per school, in that school's own colour.
    assert f"{codes.SEX[2]}, in each school" in sex
    assert re.search(rf"</svg>\s*{codes.SEX[1]}\s*</span>", sex), sex
    colors = [school.color for school in selected(conn, [MICHIGAN, BROWN])]
    assert sex.count("<circle") == len(colors)
    for color in colors:
        assert f'fill="{color}"' in sex
    # No fixed colour is claimed for the reader's own group. #17211d strokes
    # the hollow square and fills nothing.
    assert 'fill="#17211d"' not in sex and "background: #17211d" not in sex

    # Seven race groups would not fit on one line, so the key counts the rest
    # rather than listing them — and still never calls them "other groups".
    assert "Hispanic, in each school" in race
    assert "6 other race groups" in race
    assert "Native Hawaiian" not in race


def test_the_key_names_the_groups_when_nothing_is_emphasised():
    """Asked for rather than tailored, there is no own group: every group is a
    triangle, so the key draws no circle and names the groups where they fit."""
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app.main import app

    base = f"/compare?school={MICHIGAN}&school={BROWN}&area=selectiveness&area=retention"
    page = TestClient(app).get(base + "&cut=selectiveness:sex&cut=retention:race").text
    sex = next(k for k in _keys(page) if f"{codes.SEX[1]}, {codes.SEX[2]}" in k)
    race = next(k for k in _keys(page) if "race group" in k)

    assert "One group" not in page, "say which dimension the groups belong to"
    assert f"{codes.SEX[1]}, {codes.SEX[2]}" in sex
    assert "One race group" in race
    for key in (sex, race):
        assert "<circle" not in key, "no group is drawn in a school colour here"
        assert "<polygon" in key and "<rect" in key


def test_every_card_control_links_back_to_its_own_card(tmp_path, monkeypatch):
    """Every control on a card is a plain link doing a full navigation — "Show
    by", "Everyone only", "Tailor data for me" — so each carries its own card's
    fragment: without
    it, changing the third card down answers by loading the page at the top and
    the card the reader was reading scrolls out of sight. A fragment matching
    no id is a silent no-op, so the ids compare.html renders are checked too."""
    client = _reader(tmp_path, monkeypatch, gender=2, race=3)
    base = f"/compare?school={MICHIGAN}&school={BROWN}&area=selectiveness&area=retention"
    page = client.get(base + "&cut=selectiveness:sex").text

    ids = set(re.findall(r'<section class="area" id="([^"]+)"', page))
    assert ids == {cuts.anchor(key)[1:] for key in ("selectiveness", "retention")}

    menus = re.findall(r'<details class="cuts">(.*?)</details>', page, re.S)
    tailors = re.findall(r'<a class="tailor[^"]*" href="([^"]+)"', page)
    assert len(menus) == 2 and len(tailors) == 2, "one menu and one tailor button per card"
    for href in [h for menu in menus for h in re.findall(r'href="([^"]+)"', menu)] + tailors:
        assert href.partition("#")[2] in ids, f"{href} would land the reader at the page top"
