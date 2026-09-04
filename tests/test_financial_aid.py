"""Tests for the financial aid area.

Three of these guard traps rather than code: that we never drop a real
negative net price, that the sentinels never reach the page as if they were
prices, and that the 2023 published sticker is never blended into the 2021
net price the tailored card shows beside it. All three are mistakes that
produce a plausible-looking table.
"""

import re

import pytest

from app import cuts
from app.areas import financial_aid
from app.db import DB_PATH, connect, latest_year
from app.profiles import Profile
from app.schools import all_schools, selected

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="No database — run: uv run python scripts/import_ipeds.py",
)

CALTECH = 110404
DARTMOUTH = 182670

# The demo's five, in the order the shortlist holds them. Chosen because
# Maya's own answers are drawn on every one: two schools pay her to attend at
# her income, one charges $15,000, and the two publics land on opposite sides
# of the residency line.
MIT, STANFORD, MICHIGAN, BERKELEY, CARNEGIE_MELLON = 166683, 243744, 170976, 110635, 211440
FIVE = [MIT, STANFORD, MICHIGAN, BERKELEY, CARNEGIE_MELLON]


def _profile(**values) -> Profile:
    return Profile(
        username="maya",
        sat_score=None,
        act_score=None,
        shortlist=[],
        **{"income_bracket": None, **values},
    )


@pytest.fixture
def conn():
    with connect() as connection:
        yield connection


@pytest.fixture
def year(conn):
    """Whatever the newest ingested year is — net price stops at 2021."""
    return latest_year(conn, financial_aid.TABLE)


def test_every_school_has_all_five_bands(conn, year):
    rows = financial_aid.load(conn, all_schools(conn), year)["rows"]
    assert len(rows) == 25
    for row in rows:
        assert len(row["bands"]) == 5
        assert all(value is not None for value in row["bands"])


def test_negative_net_price_survives(conn, year):
    """Caltech's lowest band is below zero because grant aid exceeds cost.

    It is a real number. If this test fails because the value is gone, someone
    has added a drop-negatives rule and deleted the most interesting fact in
    the dataset.
    """
    caltech = _row(conn, CALTECH, year)
    assert caltech["bands"][0] < 0


def test_no_sentinel_reaches_the_page(conn, year):
    for row in financial_aid.load(conn, all_schools(conn), year)["rows"]:
        assert not any(value in (-1, -2, -3) for value in row["bands"])


def test_spread_is_top_band_minus_bottom(conn, year):
    dartmouth = _row(conn, DARTMOUTH, year)
    assert dartmouth["spread"] == dartmouth["bands"][4] - dartmouth["bands"][0]
    assert dartmouth["spread"] == 53332


def test_chart_has_a_line_per_school(conn, year):
    schools = all_schools(conn)[:5]
    chart = financial_aid.load(conn, schools, year)["chart"]
    assert len(chart["series"]) == 5
    assert all(line["points"].count(",") == 5 for line in chart["series"])


def _row(conn, unitid: int, year: int) -> dict:
    rows = financial_aid.load(conn, all_schools(conn), year)["rows"]
    return next(row for row in rows if row["school"].unitid == unitid)


def test_the_query_is_filtered_to_one_year(conn):
    """The table now holds seven years; an unfiltered pivot would mix them.

    2020 and 2021 are different data. If this ever starts passing with equal
    values, the year filter has been dropped from the query and every figure
    on the page is a seven-year average wearing a single year's label.
    """
    schools = all_schools(conn)
    a = financial_aid.load(conn, schools, 2020)["rows"]
    b = financial_aid.load(conn, schools, 2021)["rows"]
    assert [r["spread"] for r in a] != [r["spread"] for r in b]


def test_headline_names_the_widest_spread(conn, year):
    """Dartmouth's spread ($53,332) is the widest in the 25-school sample."""
    line = financial_aid.headline(financial_aid.load(conn, all_schools(conn), year))
    assert line
    assert "Dartmouth" in line


def test_headline_is_none_for_a_single_school(conn, year):
    """A "widest spread" claim needs something to be wider than."""
    schools = [s for s in all_schools(conn) if s.unitid == CALTECH]
    context = financial_aid.load(conn, schools, year)
    assert financial_aid.headline(context) is None


# --- tailoring: the reader's own income band ----------------------------------


@pytest.fixture
def five(conn):
    return selected(conn, FIVE)


def test_the_button_says_which_answers_it_will_use(conn):
    """`wants` names the fields, `signals` the values found — and the button's
    hint uses the second, so it reads "$30,001–48,000" rather than "income
    band". A profile holding neither answer drives nothing at all."""
    assert cuts.wants(financial_aid) == ["income band", "home state"]
    maya = _profile(income_bracket=2, home_state="CA")
    assert cuts.signals(financial_aid, maya) == ["$30,001–48,000", "CA"]
    assert cuts.signals(financial_aid, _profile(income_bracket=None, home_state=None)) == []


def test_the_gap_sentence_is_computed_from_the_band_the_profile_holds(conn, five):
    """The sentence the demo is built around, at Maya's income.

    Two of these five schools pay a family at $30,001–48,000 to attend and one
    charges $15,139. If this ever stops naming both ends, the card has lost
    the only number on it that is about the reader.
    """
    context = financial_aid.tailor(conn, five, 2021, _profile(income_bracket=2))
    assert context["own_band"] == 2
    assert context["own_band_label"] == "$30,001–48,000"

    sentence = context["band_sentence"]
    assert "-$2,251" in sentence and "MIT" in sentence
    assert "$15,139" in sentence and "Carnegie Mellon" in sentence
    assert "$17,390" in sentence, "the gap is the finding, not the two ends alone"
    assert "2021" in sentence


def test_the_reader_gets_a_dot_where_their_band_falls(conn, five):
    """Marked on the range chart, beside the two ends rather than instead of
    them: a band is only meaningful against the range it sits in.

    MIT charges the $0–30,000 band $5,347 and the $30,001–48,000 band -$2,251,
    so the dot legitimately falls *outside* the bar. The chart's scale has to
    stretch to hold it — clamping it onto the bar's end would draw a school
    Maya's band pays less at than the band below her as though it did not.
    """
    plain = financial_aid.load(conn, five, 2021)["range_chart"]
    assert all(bar["x_own"] is None for bar in plain["bars"]), "no dot until asked"

    chart = financial_aid.tailor(conn, five, 2021, _profile(income_bracket=2))["range_chart"]
    marked = {bar["name"]: bar for bar in chart["bars"]}
    assert len(marked) == 5
    assert all(bar["own"] is not None for bar in marked.values())
    assert marked["MIT"]["own"] == -2251 < marked["MIT"]["low"]
    assert marked["MIT"]["x_own"] >= 0, "the dot has to stay on the canvas"
    # Both ends survive, and the bar is unchanged by the marking.
    for name, bar in marked.items():
        assert bar["spread"] == bar["high"] - bar["low"], name


def test_a_profile_with_no_band_and_no_state_changes_nothing(conn, five):
    assert financial_aid.tailor(conn, five, 2021, _profile()) == {}
    assert financial_aid.tailor(conn, five, 2021, None) == {}
    # An out-of-range band is not a band. income_bracket is validated on the
    # way in, but the card must not key a table column off it regardless.
    assert financial_aid.tailor(conn, five, 2021, _profile(income_bracket=9)) == {}


def test_load_keeps_its_signature_and_its_output(conn, five):
    """Tailoring is merged on top of `load`, never woven into it: the card a
    signed-out reader sees has to be the one it was before any of this."""
    before = financial_aid.load(conn, five, 2021)
    assert set(before) == {"rows", "bands", "headers", "range_chart", "chart", "notices"}
    assert [r["spread"] for r in before["rows"]] == [39379, 46662, 21998, 26981, 39930]


# --- tailoring: the sticker the reader's home state qualifies them for --------


def test_a_californian_gets_berkeley_in_state_and_michigan_out_of_state(conn, five):
    """The whole reason the questionnaire asks where someone lives, on one
    screen: the two publics land on opposite sides of the residency line."""
    stickers = financial_aid.tailor(conn, five, 2021, _profile(home_state="CA"))["stickers"]
    assert stickers["year"] == 2023
    by_school = {row["school"].unitid: row for row in stickers["rows"]}

    berkeley = by_school[BERKELEY]
    assert berkeley["sticker"] == 14850 and berkeley["basis"] == "In-state"
    assert berkeley["alternative"] == 45627, "what she is spared, named beside it"

    michigan = by_school[MICHIGAN]
    assert michigan["sticker"] == 60107 and michigan["basis"] == "Out-of-state"
    assert michigan["alternative"] == 18309

    # A school that charges everyone the same is said to, rather than labelled
    # out-of-state — "out-of-state at MIT" implies an in-state rate exists.
    for unitid, price in ((MIT, 60156), (STANFORD, 62484), (CARNEGIE_MELLON, 63274)):
        row = by_school[unitid]
        assert row["sticker"] == price
        assert row["basis"] == "One price for everyone"
        assert row["alternative"] is None and row["in_state"] is False


def test_residency_is_read_from_the_newest_row_that_names_a_state(conn, five):
    """The 2024 directory rows carry a blank `state_abbr` for Stanford and
    Carnegie Mellon. Taking "the newest row" rather than "the newest row that
    says anything" would make a Californian a visitor at Stanford."""
    stickers = financial_aid.tailor(conn, five, 2021, _profile(home_state="PA"))["stickers"]
    by_school = {row["school"].unitid: row for row in stickers["rows"]}
    # Both still report one price, so residency changes no figure here — but
    # it is resolved, and Michigan's Pennsylvanian is out-of-state.
    assert by_school[CARNEGIE_MELLON]["sticker"] == 63274
    assert by_school[MICHIGAN]["basis"] == "Out-of-state"
    assert financial_aid.tailor(conn, five, 2021, _profile(home_state="MI"))["stickers"]["rows"]


def test_the_sticker_is_never_blended_into_the_net_price(conn, five):
    """Two surveys, two years, two quantities. The 2023 published figure sits
    beside the 2021 net price and is never subtracted from it, and both years
    are carried into the context so the page can state each on its own line.

    If someone later "helpfully" reports the difference, this fails: the
    result would be the most confident-looking number on the card and the
    least supported one.
    """
    context = financial_aid.tailor(conn, five, 2021, _profile(income_bracket=2, home_state="CA"))
    assert context["net_price_year"] == 2021
    assert context["stickers"]["year"] == 2023

    by_school = {row["school"].unitid: row for row in context["stickers"]["rows"]}
    berkeley = by_school[BERKELEY]
    assert berkeley["sticker"] == 14850 and berkeley["net_price"] == 10294
    assert berkeley["net_price"] == _row(conn, BERKELEY, 2021)["bands"][1]
    for row in context["stickers"]["rows"]:
        assert row["sticker"] != row["net_price"]
        assert row["net_price"] not in (-1, -2, -3)

    # Without a band there is nothing to put in that column, and the card must
    # leave it empty rather than reach for some other family's figure.
    state_only = financial_aid.tailor(conn, five, 2021, _profile(home_state="CA"))
    assert all(row["net_price"] is None for row in state_only["stickers"]["rows"])


# --- the route ----------------------------------------------------------------


def test_the_card_offers_tailoring_only_to_a_signed_in_reader(tmp_path, monkeypatch):
    """The button, what it says it will use, and the rule that none of it ever
    enters a URL: the reader's income band is the most sensitive thing this
    card knows, and a shared link must tailor to whoever opens it or to nobody.
    """
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app import profiles
    from app.main import app

    real_connect = profiles.connect
    monkeypatch.setattr(profiles, "connect", lambda: real_connect(tmp_path / "profiles.db"))
    with profiles.connect() as pconn:
        profiles.get_or_create(pconn, "maya")
        pconn.execute(
            "UPDATE profiles SET income_bracket = 2, home_state = 'CA' WHERE username = 'maya'"
        )
        profiles.get_or_create(pconn, "blank")
        pconn.commit()

    base = "/compare?" + "&".join(f"school={unitid}" for unitid in FIVE) + "&area=financial_aid"

    signed_out = TestClient(app).get(base).text
    assert "Tailor data for me" not in signed_out
    assert "Tailored to you" not in signed_out
    assert "$30,001–48,000" not in signed_out.split("Family income bands")[0]

    client = TestClient(app, cookies={"profile": "maya"})
    off = client.get(base).text
    assert off.count("Tailor data for me") == 1
    assert "Uses your profile: $30,001–48,000, CA" in off
    assert "Tailored to you" not in off

    on = client.get(base + "&tailor=financial_aid").text
    assert "Tailored to you: $30,001–48,000" in on
    assert "Tailored to you: CA" in on
    assert "Tailored to you &middot; stop" in on
    assert "a gap of $17,390" in on
    assert "In-state" in on and "Out-of-state" in on and "One price for everyone" in on

    # Nothing about the reader may reach a link. Checked against every href on
    # the page rather than against the whole document, because the card is
    # supposed to *say* her band in its own copy.
    hrefs = re.findall(r'href="([^"]*)"', on)
    assert hrefs, "no links found — the assertion below would pass vacuously"
    for href in hrefs:
        assert "income" not in href.lower(), href
        assert "band" not in href.lower(), href
        assert "30" not in href.split("?")[-1].replace("school=", ""), href
        assert "CA" not in href and "state" not in href.lower(), href

    # A profile holding neither answer is told what to add, not shown a
    # control that would do nothing.
    empty = TestClient(app, cookies={"profile": "blank"}).get(base).text
    assert "Add your income band or home state to your profile" in empty
    assert "Tailored to you" not in empty
