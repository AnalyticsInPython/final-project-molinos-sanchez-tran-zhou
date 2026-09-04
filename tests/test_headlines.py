"""The sentence at the top of every card, and the chart agreeing with it.

A chart on a projector is a shape: the axis labels are gone by the third row
of a lecture theatre and the finding goes with them. So each area computes one
sentence from figures the card already shows, and the card leads with it.

The strings below are the exact sentences the demo's five schools produce —
Berkeley, Stanford, MIT, Carnegie Mellon, Michigan, signed in as the seeded
profile in DEMO.md. They are asserted in full rather than by keyword because
the point of a headline is the whole sentence: a test that only checked
"Stanford" in it would pass on a sentence that had lost its number, its
comparison or its verb, which is every way this can actually break.

Pinned to the newest year each area holds, like the rest of the suite. A fresh
ingest that adds a year will move these, and the figures in DEMO.md with them.
"""

import html
import re

import pytest

from app import areas, cuts
from app.areas import (
    athletics,
    enrollment,
    financial_aid,
    institution_characteristics,
    outcomes,
    retention,
    selectiveness,
)
from app.db import DB_PATH, connect, latest_year
from app.profiles import Profile
from app.schools import selected

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="No database — run: uv run python scripts/import_ipeds.py",
)

# The demo's five, in the order the seeded shortlist holds them.
BERKELEY, STANFORD, MIT, CARNEGIE_MELLON, MICHIGAN = 110635, 243744, 166683, 211440, 170976
FIVE = [BERKELEY, STANFORD, MIT, CARNEGIE_MELLON, MICHIGAN]

# What each area's own primary chart is called in its context, and therefore
# which chart has to point at the school the sentence names.
PRIMARY_CHART = {
    financial_aid: "range_chart",
    selectiveness: "rates_chart",
    retention: "gap_chart",
    outcomes: "chart",
    enrollment: "chart",
    athletics: "share_chart",
}

# Untailored — what someone with no profile, or nobody signed in at all, reads.
EXPECTED = {
    financial_aid: (
        "Stanford's price swings $46,662 by income, the widest here. Michigan's moves $21,998."
    ),
    selectiveness: (
        "Stanford admits 3.6% and 82% of them come. Michigan admits four times as many "
        "and keeps fewer than half."
    ),
    retention: (
        "One Stanford student in five takes more than four years to finish. "
        "At MIT it is one in eleven."
    ),
    outcomes: (
        "MIT graduates earn $131,633 six years after entry, $57,871 more than "
        "Michigan's, with less debt."
    ),
    enrollment: (
        "Carnegie Mellon is the most international here: 18.4% of undergraduates, "
        "twice Michigan's 8.9%."
    ),
    athletics: (
        "One in six MIT undergrads plays a varsity sport, six times Michigan's share. "
        "MIT and Carnegie Mellon give $0 in athletic aid: Division III."
    ),
    institution_characteristics: (
        "MIT has 3 students per faculty member; UC Berkeley has 18, six times as many."
    ),
}


@pytest.fixture
def conn():
    with connect() as connection:
        yield connection


@pytest.fixture
def five(conn):
    return selected(conn, FIVE)


def maya(**overrides) -> Profile:
    """The seeded demo profile — scripts/seed_demo.py's answers, in a dataclass."""
    answers = {
        "username": "maya",
        "display_name": "Maya",
        "sat_score": 1480,
        "act_score": None,
        "income_bracket": 2,
        "shortlist": list(FIVE),
        "gpa": 3.8,
        "home_state": "CA",
        "race": 3,
        "gender": 2,
        "stage": "applying",
    }
    return Profile(**{**answers, **overrides})


def headline_for(conn, module, schools, profile=None) -> str | None:
    """One card's sentence, built the way app/main.py builds it."""
    year = latest_year(conn, module.TABLE)
    context = module.load(conn, schools, year)
    if profile is not None and hasattr(module, "tailor"):
        context.update(module.tailor(conn, schools, year, profile))
    selection = cuts.choose(module, None, profile)
    cut = module.cut(conn, schools, year, selection) if selection else None
    return module.headline(context, cut)


@pytest.mark.parametrize("module", list(EXPECTED), ids=lambda m: m.KEY)
def test_every_area_states_its_finding_for_the_demo_five(conn, five, module):
    assert headline_for(conn, module, five) == EXPECTED[module]


@pytest.mark.parametrize("module", areas.ALL, ids=lambda m: m.KEY)
def test_every_area_has_one(module):
    """The contract in app/areas/__init__.py: seven areas, seven sentences."""
    assert callable(getattr(module, "headline", None))


@pytest.mark.parametrize("module", areas.ALL, ids=lambda m: m.KEY)
def test_one_school_gets_no_headline(conn, module):
    """Every sentence here is a comparison, and one school is not one."""
    assert headline_for(conn, module, selected(conn, [MIT])) is None


def test_the_tailored_aid_headline_names_the_reader_and_both_ends(conn, five):
    """The demo's own number: $17,390 between two schools at one income."""
    assert headline_for(conn, financial_aid, five, maya()) == (
        "At $30,001–48,000, MIT pays Maya $2,251 to attend and Carnegie Mellon charges "
        "$15,139. Same income, $17,390 apart."
    )


def test_a_reader_with_no_display_name_is_described_not_named(conn, five):
    """The username is a login, not what to call someone on a projector."""
    line = headline_for(conn, financial_aid, five, maya(display_name=None))
    assert "a family at that income" in line
    assert "maya" not in line


def test_the_tailored_selectiveness_headline_names_the_group(conn, five):
    assert headline_for(conn, selectiveness, five, maya()) == (
        "Women are admitted above the overall rate at all five schools here, by three "
        "points at Carnegie Mellon: 14.7% against 11.7%."
    )


def test_the_tailored_retention_headline_names_the_group(conn, five):
    """A fact about the school, never about the reader's own chances — rule 6
    in app/cuts.py. The verb is "graduates", and its subject is a university."""
    line = headline_for(conn, retention, five, maya())
    assert line == (
        "Carnegie Mellon graduates Hispanic students ten points behind its own "
        "headline; MIT and Stanford are within a point."
    )
    assert "your" not in line.lower()


@pytest.mark.parametrize("module", list(PRIMARY_CHART), ids=lambda m: m.KEY)
def test_the_chart_points_at_the_school_the_sentence_names(conn, five, module):
    """One bar at full strength, and it is the one the sentence is about.

    The whole reason `lead` exists: a sentence naming Stanford over a chart
    that emphasises MIT is worse than no sentence, because the reader believes
    the picture.
    """
    year = latest_year(conn, module.TABLE)
    context = module.load(conn, five, year)
    lead = [bar for bar in context[PRIMARY_CHART[module]]["bars"] if bar["lead"]]
    assert len(lead) == 1
    assert lead[0]["name"] in module.headline(context)


@pytest.mark.parametrize("module", list(PRIMARY_CHART), ids=lambda m: m.KEY)
def test_one_school_is_not_drawn_faint(conn, module):
    """No comparison means no sentence and nobody to single out, so nothing is
    dimmed: a lone bar at a third opacity reads as missing data."""
    chart = module.load(conn, selected(conn, [MIT]), latest_year(conn, module.TABLE))
    assert all(bar["lead"] for bar in chart[PRIMARY_CHART[module]]["bars"])


def test_the_tailored_cut_chart_points_at_the_school_its_sentence_names(conn, five):
    """The cut figure is the chart a tailored headline is drawn from, so it
    carries the mark on those cards rather than the area's own chart."""
    year = latest_year(conn, retention.TABLE)
    cut = retention.cut(conn, five, year, cuts.choose(retention, None, maya()))
    lead = [bar for bar in cut["figure"]["bars"] if bar["lead"]]
    assert len(lead) == 1
    assert lead[0]["name"] == "Carnegie Mellon"


def test_an_untailored_cut_singles_out_nobody(conn, five):
    """Asked for rather than offered, there is no reader's group to be
    furthest from anything, so every row is drawn at full strength."""
    year = latest_year(conn, retention.TABLE)
    cut = retention.cut(conn, five, year, cuts.Selection("race"))
    assert all(bar["lead"] for bar in cut["figure"]["bars"])


# --- The page ----------------------------------------------------------------


@pytest.fixture
def page():
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app.main import app

    query = "&".join(f"school={unitid}" for unitid in FIVE)
    return TestClient(app).get(f"/compare?{query}").text


def test_one_headline_per_card(page):
    assert page.count('<p class="headline">') == len(areas.ALL)


def test_the_headline_comes_before_the_caveats_on_every_card(page):
    """A sentence a reader has to scroll past two notices to reach is not the
    first thing on the card, whatever the stylesheet says."""
    for card in re.findall(r'<section class="area".*?</section>', page, re.S):
        headline = card.find('<p class="headline">')
        assert headline != -1
        notice = card.find('class="notice')
        assert notice == -1 or headline < notice


def test_the_strip_gathers_the_other_cards_and_not_this_one(page):
    """The characteristics card carries the page's summary, so its own
    sentence must not appear on it twice."""
    card = re.search(
        r'<section class="area" id="area-institution_characteristics".*?</section>', page, re.S
    ).group(0)
    # Jinja escapes the apostrophes in "Stanford's" on the way out; the
    # sentence under test is the one the module produced, not its encoding.
    strip = html.unescape(re.search(r'<ul class="highlights">(.*?)</ul>', card, re.S).group(1))
    assert EXPECTED[institution_characteristics] not in strip
    for module in (financial_aid, selectiveness, retention, outcomes, enrollment, athletics):
        assert EXPECTED[module] in strip
