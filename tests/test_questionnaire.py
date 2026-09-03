"""Tests for the sign-up questionnaire built on top of the profile store.

Most of these guard the same thing from different angles: a field must either
hold a value the app can render and use, or hold nothing. A questionnaire that
accepts "race=99" or "state=ZZ" stores a row that displays blank and reads as a
bug in the page rather than as bad input.

`test_race_99_is_not_an_identity` is the one worth reading. 99 is the IPEDS
code for the published total across all races. It is a valid code in the data
and is not a person, so it must not be selectable as an answer.
"""

import pytest

from app import profiles

FILLED = dict(
    display_name="Rafa Sanchez",
    gpa=3.85,
    home_state="NY",
    race=3,
    gender=1,
    stage="choosing",
)


@pytest.fixture
def conn(tmp_path):
    with profiles.connect(tmp_path / "profiles.db") as connection:
        yield connection


def test_a_new_profile_starts_empty_and_still_works(conn):
    """Every questionnaire answer is optional, including all of them."""
    profile = profiles.get_or_create(conn, "someone")
    assert profile.display_name is None
    assert profile.race is None
    assert profile.name == "someone"  # falls back to the username


def test_answers_round_trip(conn):
    profiles.get_or_create(conn, "rafa")
    profiles.set_details(conn, "rafa", **FILLED)
    profile = profiles.get(conn, "rafa")
    assert profile.name == "Rafa Sanchez"
    assert profile.home_state == "NY"
    assert profile.gpa == 3.85
    assert profile.race_label == "Hispanic or Latino"
    assert profile.gender_label == "Man"
    assert profile.stage_label == "Choosing between offers I have"


def test_answers_can_be_cleared_again(conn):
    profiles.get_or_create(conn, "rafa")
    profiles.set_details(conn, "rafa", **FILLED)
    profiles.set_details(
        conn, "rafa", display_name=None, gpa=None, home_state=None,
        race=None, gender=None, stage=None,
    )
    profile = profiles.get(conn, "rafa")
    assert (profile.display_name, profile.race, profile.home_state) == (None, None, None)
    assert profile.name == "rafa"


def test_race_99_is_not_an_identity():
    """99 is the IPEDS total across all races, not a person."""
    assert 99 not in profiles.RACES
    assert profiles.clean_choice("99", profiles.RACES) is None


def test_every_offered_race_joins_to_the_outcome_data():
    """The codes are IPEDS codes, so a saved answer can filter grad_rates."""
    assert set(profiles.RACES) <= set(range(1, 10))


@pytest.mark.parametrize(
    "value", ["ZZ", "zz", "", None, "'; DROP TABLE profiles;--", "N", "NYC"]
)
def test_a_bad_state_is_discarded(value):
    assert profiles.clean_choice(value, profiles.STATES) is None


def test_a_real_state_survives():
    assert profiles.clean_choice("NY", profiles.STATES) == "NY"


@pytest.mark.parametrize("value", ["9.9", "-1", "abc", "", None, "4.01"])
def test_an_impossible_gpa_is_discarded(value):
    assert profiles.clean_gpa(value) is None


@pytest.mark.parametrize("value,expected", [("3.85", 3.85), ("4.0", 4.0), ("0", 0.0)])
def test_a_real_gpa_survives(value, expected):
    assert profiles.clean_gpa(value) == expected


def test_a_name_is_trimmed_and_bounded():
    assert profiles.clean_name("  Rafa   Sanchez  ") == "Rafa Sanchez"
    assert profiles.clean_name("   ") is None
    assert len(profiles.clean_name("x" * 200)) == 60


def test_an_unknown_stage_is_discarded():
    assert profiles.clean_choice("hack", profiles.STAGES) is None
    assert profiles.clean_choice("applying", profiles.STAGES) == "applying"


def test_an_older_profile_database_gains_the_new_columns(tmp_path):
    """Rebecca's original schema, opened by this version, must not break.

    The questionnaire columns were added after her first release, so `connect`
    migrates in place — nobody has to delete a profiles.db to keep going.
    """
    import sqlite3

    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript(profiles.SCHEMA)
    old.execute(
        "INSERT INTO profiles (username, sat_score, created_at) VALUES (?, ?, ?)",
        ("legacy", 1400, "2026-09-01T00:00:00Z"),
    )
    old.commit()
    old.close()

    with profiles.connect(path) as conn:
        profile = profiles.get(conn, "legacy")
        assert profile.sat_score == 1400  # her data survives
        assert profile.race is None  # new column exists and is empty
        profiles.set_details(conn, "legacy", **FILLED)
        assert profiles.get(conn, "legacy").home_state == "NY"
