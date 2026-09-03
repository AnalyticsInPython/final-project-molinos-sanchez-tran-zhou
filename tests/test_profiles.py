"""Tests for saved profiles: username validation, and the shortlist CRUD.

Unlike every other test in this project, these touch a writable database.
The `conn` fixture points at a throwaway file under `tmp_path` rather than
the shared `data/profiles.db` a developer might have open locally — nothing
here should depend on, or clobber, an actual saved profile.
"""

import pytest

from app.profiles import (
    MAX_SHORTLIST,
    add_school,
    clean_username,
    connect,
    get_or_create,
    remove_school,
    set_scores,
)

DARTMOUTH = 182670
HARVARD = 166027
STANFORD = 243744


@pytest.fixture
def conn(tmp_path):
    with connect(tmp_path / "test_profiles.db") as connection:
        yield connection


@pytest.mark.parametrize(
    "value",
    ["", None, "ab", "a" * 21, "Jenny Tran", "jenny@tran", "javascript:alert(1)", "  "],
)
def test_junk_usernames_are_rejected(value):
    assert clean_username(value) is None


@pytest.mark.parametrize("value", ["jenny", "Jenny", "  Jenny  ", "j3nny_tran-2"])
def test_valid_usernames_are_accepted_and_lowercased(value):
    cleaned = clean_username(value)
    assert cleaned is not None
    assert cleaned == cleaned.lower()


def test_get_or_create_starts_empty(conn):
    profile = get_or_create(conn, "jenny")
    assert profile.username == "jenny"
    assert profile.sat_score is None
    assert profile.act_score is None
    assert profile.income_bracket is None
    assert profile.shortlist == []


def test_get_or_create_does_not_reset_an_existing_profile(conn):
    """A stale cookie recreating the row must not erase what's already saved."""
    get_or_create(conn, "jenny")
    set_scores(conn, "jenny", sat=1500, act=None, income_bracket=3)

    profile = get_or_create(conn, "jenny")
    assert profile.sat_score == 1500
    assert profile.income_bracket == 3


def test_set_scores_accepts_partial_updates(conn):
    get_or_create(conn, "jenny")
    set_scores(conn, "jenny", sat=1500, act=None, income_bracket=None)
    set_scores(conn, "jenny", sat=1500, act=32, income_bracket=2)

    profile = get_or_create(conn, "jenny")
    assert (profile.sat_score, profile.act_score, profile.income_bracket) == (1500, 32, 2)


def test_set_scores_clears_a_field_back_to_none(conn):
    get_or_create(conn, "jenny")
    set_scores(conn, "jenny", sat=1500, act=32, income_bracket=2)
    set_scores(conn, "jenny", sat=None, act=32, income_bracket=2)

    profile = get_or_create(conn, "jenny")
    assert profile.sat_score is None
    assert profile.act_score == 32


def test_add_school_builds_the_shortlist_in_order(conn):
    get_or_create(conn, "jenny")
    add_school(conn, "jenny", DARTMOUTH)
    add_school(conn, "jenny", HARVARD)

    profile = get_or_create(conn, "jenny")
    assert profile.shortlist == [DARTMOUTH, HARVARD]


def test_adding_the_same_school_twice_is_a_no_op(conn):
    get_or_create(conn, "jenny")
    add_school(conn, "jenny", DARTMOUTH)
    add_school(conn, "jenny", DARTMOUTH)

    profile = get_or_create(conn, "jenny")
    assert profile.shortlist == [DARTMOUTH]


def test_shortlist_caps_at_max_shortlist(conn):
    get_or_create(conn, "jenny")
    for unitid in range(MAX_SHORTLIST + 5):
        add_school(conn, "jenny", unitid)

    profile = get_or_create(conn, "jenny")
    assert len(profile.shortlist) == MAX_SHORTLIST


def test_remove_school_drops_it(conn):
    get_or_create(conn, "jenny")
    add_school(conn, "jenny", DARTMOUTH)
    add_school(conn, "jenny", STANFORD)
    remove_school(conn, "jenny", DARTMOUTH)

    profile = get_or_create(conn, "jenny")
    assert profile.shortlist == [STANFORD]


def test_removing_a_school_never_added_is_a_no_op(conn):
    get_or_create(conn, "jenny")
    add_school(conn, "jenny", DARTMOUTH)
    remove_school(conn, "jenny", STANFORD)

    profile = get_or_create(conn, "jenny")
    assert profile.shortlist == [DARTMOUTH]


def test_two_profiles_keep_separate_shortlists(conn):
    get_or_create(conn, "jenny")
    get_or_create(conn, "martin")
    add_school(conn, "jenny", DARTMOUTH)
    add_school(conn, "martin", STANFORD)

    assert get_or_create(conn, "jenny").shortlist == [DARTMOUTH]
    assert get_or_create(conn, "martin").shortlist == [STANFORD]
