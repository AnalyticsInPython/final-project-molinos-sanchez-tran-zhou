"""Tests for setting a student's actual offer against the published pattern.

The comparison is deliberately on discount rate rather than dollars, because
published net price stops in 2021 and an offer letter is for next year.
`test_the_comparison_is_a_rate_not_a_dollar_gap` is the one guarding that: if
someone later "simplifies" this to subtracting dollars, every school starts
looking more generous than it is by roughly five years of inflation.
"""

import pytest

from app import offers, profiles
from app.db import DB_PATH, connect

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="No database — run: uv run python scripts/import_ipeds.py",
)

DARTMOUTH = 182670
MICHIGAN = 170976


@pytest.fixture
def conn():
    with connect() as connection:
        yield connection


@pytest.fixture
def pconn(tmp_path):
    with profiles.connect(tmp_path / "p.db") as connection:
        profiles.get_or_create(connection, "rafa")
        yield connection


def test_home_state_changes_the_sticker_it_is_measured_against(conn):
    """The whole reason the questionnaire asks where someone lives."""
    resident = offers.compare(conn, MICHIGAN, net_offer=20000, income_band=3, home_state="MI")
    visitor = offers.compare(conn, MICHIGAN, net_offer=20000, income_band=3, home_state="NY")
    assert resident.in_state and not visitor.in_state
    assert visitor.sticker > resident.sticker * 1.5
    # Same offer, and it is a far better deal from out of state.
    assert visitor.your_discount > resident.your_discount


def test_a_private_school_charges_everyone_the_same(conn):
    here = offers.compare(conn, DARTMOUTH, net_offer=12000, income_band=1, home_state="NH")
    away = offers.compare(conn, DARTMOUTH, net_offer=12000, income_band=1, home_state="NY")
    assert here.sticker == away.sticker


def test_a_weak_offer_reads_as_weak(conn):
    result = offers.compare(conn, DARTMOUTH, net_offer=12000, income_band=1, home_state="NY")
    assert result.gap < 0
    assert "Less generous" in result.verdict


def test_a_typical_offer_reads_as_typical(conn):
    """Dartmouth's published net price at the lowest band is about $2,400."""
    result = offers.compare(conn, DARTMOUTH, net_offer=2400, income_band=1, home_state="NY")
    assert abs(result.gap) < 0.05
    assert "About what" in result.verdict


def test_the_comparison_is_a_rate_not_a_dollar_gap(conn):
    """Rates are the only thing comparable across a five-year data gap.

    Both figures are shares of the sticker of their own year, so neither is
    contaminated by the other year's prices.
    """
    result = offers.compare(conn, DARTMOUTH, net_offer=12000, income_band=1, home_state="NY")
    assert 0 <= result.your_discount <= 1
    assert 0 <= result.typical_discount <= 1
    assert result.typical_year == 2021


def test_no_income_band_still_prices_the_offer(conn):
    """Someone who skipped the income question still learns the sticker."""
    result = offers.compare(conn, DARTMOUTH, net_offer=12000, income_band=None, home_state=None)
    assert result.your_discount > 0
    assert result.typical_discount is None
    assert result.gap is None
    assert "does not publish" in result.verdict


def test_an_unknown_school_is_none_rather_than_a_guess(conn):
    assert offers.compare(conn, 999999, net_offer=1000, income_band=1, home_state="NY") is None


def test_offers_round_trip_and_clear(pconn):
    profiles.set_offer(pconn, "rafa", DARTMOUTH, net_offer=12000, grant_aid=45000, loan_aid=15000)
    saved = profiles.offers(pconn, "rafa")[DARTMOUTH]
    assert saved.net_offer == 12000
    assert saved.gift_share == 0.75

    profiles.set_offer(pconn, "rafa", DARTMOUTH, net_offer=None, grant_aid=None, loan_aid=None)
    assert profiles.offers(pconn, "rafa") == {}


def test_a_full_ride_is_kept_not_treated_as_blank():
    """Zero is the most interesting offer on the page, not a missing value."""
    assert profiles.clean_money("0") == 0
    assert profiles.clean_money("") is None


@pytest.mark.parametrize(
    "value,expected", [("$42,500", 42500), ("42500", 42500), ("  1,000 ", 1000)]
)
def test_money_accepts_what_people_actually_type(value, expected):
    assert profiles.clean_money(value) == expected


@pytest.mark.parametrize("value", ["-100", "abc", "999999999", None, ""])
def test_impossible_money_is_discarded(value):
    assert profiles.clean_money(value) is None


def test_gift_share_separates_two_identical_headline_packages(pconn):
    """$60k of grant and $60k of loan are not the same offer."""
    profiles.set_offer(pconn, "rafa", 1, net_offer=10000, grant_aid=60000, loan_aid=0)
    profiles.set_offer(pconn, "rafa", 2, net_offer=10000, grant_aid=0, loan_aid=60000)
    saved = profiles.offers(pconn, "rafa")
    assert saved[1].gift_share == 1.0
    assert saved[2].gift_share == 0.0
