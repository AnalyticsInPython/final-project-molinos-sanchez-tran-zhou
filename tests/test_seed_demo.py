"""Tests for the demo seed: the sample student's answers, and her shortlist.

Like `tests/test_profiles.py`, these touch a writable database, and like those
they point at a throwaway file under `tmp_path` — the seed's whole job is to
overwrite a profile, and the one it overwrites by default is the developer's
own `data/profiles.db`.

`scripts/` is not a package, so the script is loaded from its path rather than
imported by name. It puts the repository root on `sys.path` itself when it
loads, which is what lets it import `app.profiles` when run as a file.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

from app.profiles import add_school, connect, get, get_or_create, set_scores

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "seed_demo.py"

CALTECH = 110404
BERKELEY = 110635
STANFORD = 243744
MIT = 166683
CARNEGIE_MELLON = 211440
MICHIGAN = 170976


def _load():
    spec = importlib.util.spec_from_file_location("seed_demo", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seed_demo = _load()


@pytest.fixture
def conn(tmp_path):
    with connect(tmp_path / "test_profiles.db") as connection:
        yield connection


def test_seeds_every_answer_from_the_sample_student_table(conn):
    profile = seed_demo.seed(conn)

    assert profile.username == "maya"
    assert profile.display_name == "Maya"
    assert profile.name == "Maya"
    assert profile.stage == "applying"
    assert profile.home_state == "CA"
    assert profile.income_bracket == 2
    assert profile.sat_score == 1480
    assert profile.act_score is None
    assert profile.gpa == 3.8
    assert profile.race == 3
    assert profile.gender == 2


def test_the_labels_those_codes_render_as_are_the_ones_the_script_says(conn):
    """The codes are only worth checking as the words they draw on the page."""
    profile = seed_demo.seed(conn)

    assert profile.race_label == "Hispanic or Latino"
    assert profile.gender_label == "Woman"
    assert profile.stage_label == "Deciding where to apply"


def test_the_shortlist_is_the_five_schools_in_the_order_the_demo_reads_them(conn):
    profile = seed_demo.seed(conn)

    assert profile.shortlist == [BERKELEY, STANFORD, MIT, CARNEGIE_MELLON, MICHIGAN]


def test_seeding_twice_leaves_one_profile_unchanged(conn):
    first = seed_demo.seed(conn)
    second = seed_demo.seed(conn)

    assert second == first
    rows = conn.execute("SELECT COUNT(*) FROM profiles WHERE username = 'maya'").fetchone()
    assert rows[0] == 1
    schools = conn.execute("SELECT COUNT(*) FROM profile_schools WHERE username = 'maya'")
    assert schools.fetchone()[0] == 5


def test_a_stale_extra_school_from_an_earlier_run_is_removed(conn):
    """Caltech is the school the roadmap keeps out; it must not survive a seed."""
    get_or_create(conn, "maya")
    add_school(conn, "maya", CALTECH)

    profile = seed_demo.seed(conn)

    assert CALTECH not in profile.shortlist
    assert profile.shortlist == [BERKELEY, STANFORD, MIT, CARNEGIE_MELLON, MICHIGAN]


def test_a_school_added_out_of_order_does_not_stay_out_of_order(conn):
    get_or_create(conn, "maya")
    add_school(conn, "maya", MICHIGAN)
    add_school(conn, "maya", MIT)

    profile = seed_demo.seed(conn)

    assert profile.shortlist == [BERKELEY, STANFORD, MIT, CARNEGIE_MELLON, MICHIGAN]


def test_a_score_left_over_from_an_earlier_run_is_replaced(conn):
    """`set_scores` replaces the whole group, so a stale ACT must not survive."""
    get_or_create(conn, "maya")
    set_scores(conn, "maya", sat=1200, act=32, income_bracket=5)

    profile = seed_demo.seed(conn)

    assert profile.sat_score == 1480
    assert profile.act_score is None
    assert profile.income_bracket == 2


def test_another_profile_in_the_same_database_is_left_alone(conn):
    get_or_create(conn, "rafa")
    set_scores(conn, "rafa", sat=1300, act=None, income_bracket=4)
    add_school(conn, "rafa", CALTECH)

    seed_demo.seed(conn)

    rafa = get(conn, "rafa")
    assert rafa.sat_score == 1300
    assert rafa.income_bracket == 4
    assert rafa.shortlist == [CALTECH]


def test_the_compare_url_carries_the_five_brand_colours_in_order():
    """The same link `profile.html` builds, down to the percent-encoded hash."""
    assert seed_demo.compare_url(seed_demo.SHORTLIST) == (
        "/compare?school=110635&color=%23003262"
        "&school=243744&color=%238c1515"
        "&school=166683&color=%23a31f34"
        "&school=211440&color=%23c41230"
        "&school=170976&color=%2300274c"
    )


def test_the_compare_url_never_leaks_who_the_reader_is():
    """A shared link tailors to whoever opens it — see tests/test_cuts.py."""
    url = seed_demo.compare_url(seed_demo.SHORTLIST)

    for leaked in ("maya", "race", "gender", "income", "CA", "1480", "3.8"):
        assert leaked not in url


def test_the_documented_command_runs_and_prints_the_compare_url(tmp_path):
    """`uv run python scripts/seed_demo.py --db ...`, as the docstring says."""
    db = tmp_path / "seeded.db"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--db", str(db)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=True,
    )

    assert db.exists()
    assert seed_demo.compare_url(seed_demo.SHORTLIST) in result.stdout
    assert "Hispanic or Latino" in result.stdout
    assert "$30,001–48,000" in result.stdout

    with connect(db) as connection:
        assert get(connection, "maya").shortlist == seed_demo.SHORTLIST
