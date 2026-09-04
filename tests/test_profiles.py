"""Tests for saved profiles: username validation, the shortlist CRUD, and the
optional passphrase.

Unlike every other test in this project, these touch a writable database.
The `conn` fixture points at a throwaway file under `tmp_path` rather than
the shared `data/profiles.db` a developer might have open locally — nothing
here should depend on, or clobber, an actual saved profile.

The passphrase tests below are the ones worth reading. Two promises are held
by every one of them: a profile that set a passphrase does not open without
it, and a profile that did not set one opens exactly as it always did. The
second is why every profile saved before the column existed still works, and
it is checked at both levels — the store, and the route that hands out the
cookie.
"""

import pytest

from app.profiles import (
    MAX_SHORTLIST,
    MIN_PASSPHRASE,
    add_school,
    clean_passphrase,
    clean_username,
    connect,
    get,
    get_or_create,
    has_passphrase,
    hash_passphrase,
    passphrase_opens,
    passphrase_problem,
    remove_school,
    set_passphrase,
    set_scores,
    verify_passphrase,
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


# --- the optional passphrase -----------------------------------------------------

GOOD = "correct horse battery"


def test_a_profile_without_a_passphrase_opens_for_anyone(conn):
    """The compatibility promise: every profile saved before this existed."""
    get_or_create(conn, "jenny")
    assert has_passphrase(conn, "jenny") is False
    assert passphrase_opens(conn, "jenny", None) is True
    assert passphrase_opens(conn, "jenny", "anything at all") is True


def test_an_unclaimed_username_is_not_blocked(conn):
    """Typing a name nobody has taken is still how a profile gets made."""
    assert passphrase_opens(conn, "nobody", None) is True


def test_only_the_right_passphrase_opens_a_protected_profile(conn):
    get_or_create(conn, "maya")
    set_passphrase(conn, "maya", GOOD)

    assert has_passphrase(conn, "maya") is True
    assert passphrase_opens(conn, "maya", GOOD) is True
    assert passphrase_opens(conn, "maya", GOOD.upper()) is False
    assert passphrase_opens(conn, "maya", GOOD + " ") is False
    assert passphrase_opens(conn, "maya", "") is False
    assert passphrase_opens(conn, "maya", None) is False, "a blank field is not a key"


def test_the_passphrase_is_never_stored_in_the_clear(conn):
    get_or_create(conn, "maya")
    set_passphrase(conn, "maya", GOOD)

    stored = conn.execute(
        "SELECT passphrase_hash FROM profiles WHERE username = 'maya'"
    ).fetchone()["passphrase_hash"]
    assert GOOD not in stored
    assert stored.startswith("scrypt$"), "self-describing, so the work factors can change"


def test_the_hash_is_not_on_the_profile_a_template_gets(conn):
    """A template can ask whether there is one; it cannot be handed the hash."""
    get_or_create(conn, "maya")
    set_passphrase(conn, "maya", GOOD)

    profile = get(conn, "maya")
    assert profile.has_passphrase is True
    assert not any("scrypt$" in str(value) for value in vars(profile).values())


def test_two_profiles_with_the_same_passphrase_get_different_hashes(conn):
    """Per-profile salt: one cracked hash must not read as two."""
    get_or_create(conn, "jenny")
    get_or_create(conn, "martin")
    set_passphrase(conn, "jenny", GOOD)
    set_passphrase(conn, "martin", GOOD)

    hashes = {
        row["passphrase_hash"]
        for row in conn.execute("SELECT passphrase_hash FROM profiles")
    }
    assert len(hashes) == 2
    assert passphrase_opens(conn, "jenny", GOOD) and passphrase_opens(conn, "martin", GOOD)


def test_a_passphrase_can_be_changed_and_removed(conn):
    get_or_create(conn, "maya")
    set_passphrase(conn, "maya", GOOD)
    set_passphrase(conn, "maya", "a different one entirely")
    assert passphrase_opens(conn, "maya", GOOD) is False
    assert passphrase_opens(conn, "maya", "a different one entirely") is True

    set_passphrase(conn, "maya", None)
    assert has_passphrase(conn, "maya") is False
    assert passphrase_opens(conn, "maya", None) is True


def test_setting_a_passphrase_leaves_the_rest_of_the_profile_alone(conn):
    get_or_create(conn, "maya")
    set_scores(conn, "maya", sat=1500, act=None, income_bracket=3)
    add_school(conn, "maya", DARTMOUTH)
    set_passphrase(conn, "maya", GOOD)

    profile = get(conn, "maya")
    assert (profile.sat_score, profile.income_bracket) == (1500, 3)
    assert profile.shortlist == [DARTMOUTH]


@pytest.mark.parametrize(
    "stored",
    ["", "scrypt$", "scrypt$16384$8$1$nothex$nothex", "bcrypt$16384$8$1$aa$bb", "junk"],
)
def test_an_unreadable_hash_fails_closed(stored):
    """A truncated or foreign hash verifies against nothing rather than raising."""
    assert verify_passphrase(stored, GOOD) is False


def test_a_hash_verifies_only_against_its_own_passphrase():
    stored = hash_passphrase(GOOD)
    assert verify_passphrase(stored, GOOD) is True
    assert verify_passphrase(stored, "correct horse batteru") is False
    assert verify_passphrase(stored, None) is False
    assert verify_passphrase(None, GOOD) is False


@pytest.mark.parametrize("value", ["", "   ", "\n", None])
def test_a_blank_passphrase_field_means_no_passphrase(value):
    assert clean_passphrase(value) is None


def test_a_passphrase_is_taken_exactly_as_typed():
    """Trimming a secret would lock someone out of their own profile."""
    assert clean_passphrase(" two words ") == " two words "
    assert clean_passphrase("MiXeD Case") == "MiXeD Case"


def test_a_too_short_passphrase_is_refused_with_a_sentence():
    problem = passphrase_problem("x" * (MIN_PASSPHRASE - 1))
    assert problem and str(MIN_PASSPHRASE) in problem
    assert passphrase_problem("x" * MIN_PASSPHRASE) is None
    assert passphrase_problem("x" * 500) is not None


# --- the routes ------------------------------------------------------------------
#
# These drive the real app through a TestClient, because the promise being
# checked is about a cookie: refusing to *set* one is the whole feature, and
# no store-level test can see that. `profiles.connect` is redirected at a
# tmp_path database first, the same way tests/test_cuts.py does it, so the
# suite never opens a developer's saved profiles.


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A signed-out client whose profile writes land under tmp_path."""
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app import profiles
    from app.main import app

    real_connect = profiles.connect
    monkeypatch.setattr(profiles, "connect", lambda: real_connect(tmp_path / "profiles.db"))
    # Redirects are not followed: the Set-Cookie header on the 303 itself is
    # what these tests are about.
    return TestClient(app, follow_redirects=False)


def signed_cookie(response):
    return response.cookies.get("profile")


def test_a_profile_without_a_passphrase_opens_on_the_username_alone(client):
    """Exactly today's behaviour, and the reason existing profiles keep working."""
    created = client.post("/profile/new", data={"username": "cuts_demo"})
    assert created.status_code == 303
    assert signed_cookie(created) == "cuts_demo"

    client.cookies.clear()
    back = client.post("/profile", data={"username": "cuts_demo"})
    assert back.status_code == 303
    assert signed_cookie(back) == "cuts_demo"
    assert "error" not in back.headers["location"]


def test_a_profile_with_a_passphrase_does_not_open_without_it(client):
    made = client.post(
        "/profile/new", data={"username": "maya", "passphrase": GOOD, "home_state": "CA"}
    )
    assert made.status_code == 303
    assert signed_cookie(made) == "maya", "the person who set it is signed straight in"

    client.cookies.clear()
    bare = client.post("/profile", data={"username": "maya"})
    assert bare.status_code == 303
    assert signed_cookie(bare) is None, "no cookie without the passphrase"
    assert "error=" in bare.headers["location"]

    wrong = client.post("/profile", data={"username": "maya", "passphrase": "guessing"})
    assert signed_cookie(wrong) is None
    assert "passphrase" in wrong.headers["location"].lower()

    right = client.post("/profile", data={"username": "maya", "passphrase": GOOD})
    assert signed_cookie(right) == "maya"


def test_the_error_reaches_the_page_the_redirect_points_at(client):
    client.post("/profile/new", data={"username": "maya", "passphrase": GOOD})
    client.cookies.clear()

    location = client.post("/profile", data={"username": "maya"}).headers["location"]
    page = client.get(location).text
    assert "That passphrase does not match this profile." in page
    assert "Signed in as" not in page


def test_signing_up_again_cannot_take_over_a_protected_profile(client):
    """Otherwise the questionnaire is a way round the passphrase it just set."""
    client.post(
        "/profile/new", data={"username": "maya", "passphrase": GOOD, "home_state": "CA"}
    )
    client.cookies.clear()

    stolen = client.post(
        "/profile/new", data={"username": "maya", "display_name": "Not Maya", "home_state": "NY"}
    )
    assert signed_cookie(stolen) is None
    assert "error=" in stolen.headers["location"]

    signed_in = client.post("/profile", data={"username": "maya", "passphrase": GOOD})
    assert signed_cookie(signed_in) == "maya"
    page = client.get("/profile").text
    assert "Not Maya" not in page, "the answers on the profile were not overwritten"


def test_a_short_passphrase_is_refused_rather_than_silently_dropped(client):
    """The worst outcome is thinking a profile is protected when it is not."""
    response = client.post("/profile/new", data={"username": "maya", "passphrase": "short"})
    assert signed_cookie(response) is None
    assert "/profile/new?error=" in response.headers["location"]

    client.cookies.clear()
    assert signed_cookie(client.post("/profile", data={"username": "maya"})) == "maya", (
        "the profile was never created, so the name is still free"
    )


def test_an_existing_profile_can_be_protected_later(client):
    """The seeded demo profile is one of these: made before, protected after."""
    client.post("/profile/new", data={"username": "cuts_demo"})
    set_later = client.post("/profile/passphrase", data={"passphrase": GOOD})
    assert set_later.status_code == 303

    client.cookies.clear()
    assert signed_cookie(client.post("/profile", data={"username": "cuts_demo"})) is None
    assert signed_cookie(
        client.post("/profile", data={"username": "cuts_demo", "passphrase": GOOD})
    ) == "cuts_demo"


def test_setting_a_passphrase_needs_a_cookie(client):
    """Signed out, the route is a no-op rather than a way to protect a name."""
    client.post("/profile/new", data={"username": "cuts_demo"})
    client.cookies.clear()

    client.post("/profile/passphrase", data={"passphrase": GOOD})
    assert signed_cookie(client.post("/profile", data={"username": "cuts_demo"})) == "cuts_demo"


def test_the_hash_never_appears_in_a_rendered_page(client):
    client.post("/profile/new", data={"username": "maya", "passphrase": GOOD})
    page = client.get("/profile").text

    assert "Signed in as maya" in page
    assert "scrypt" not in page
    assert GOOD not in page
    assert "passphrase_hash" not in page


# --- the word on the page ---------------------------------------------------
#
# The comparison card has always said "Sex". The two forms said "Gender", and
# offered a third answer the federal data has no row for. These hold the fix
# from the reader's side, which is the only side that noticed the difference.


def test_both_forms_say_sex_and_never_gender(client):
    """One word on every page a reader sees, including the label's `for`-less
    wrapper text. The `name="gender"` attribute is the stored column and stays;
    it is the only place the old word is allowed to survive."""
    client.post("/profile/new", data={"username": "maya"})

    for page in (client.get("/profile/new").text, client.get("/profile").text):
        without_attributes = page.replace('name="gender"', "")
        assert "Gender" not in without_attributes
        assert "gender" not in without_attributes
        assert ">Sex" in page or "Sex <span" in page


def test_the_forms_offer_exactly_male_and_female(client):
    """Two options, plus the blank one. Nothing else is selectable."""
    client.post("/profile/new", data={"username": "maya"})

    for page in (client.get("/profile/new").text, client.get("/profile").text):
        select = page.split('name="gender"', 1)[1].split("</select>", 1)[0]
        assert select.count("<option") == 3
        assert ">Male<" in select and ">Female<" in select
        assert 'value="1"' in select and 'value="2"' in select
        assert 'value="0"' not in select
        for retired in ("Man<", "Woman<", "Another identity"):
            assert retired not in select


def test_answering_is_still_optional_on_both_forms(client):
    """The blank default is the whole reason withdrawing code 0 costs nothing:
    declining is still an answer, it is just not a code any more. The select
    must also not become `required`."""
    client.post("/profile/new", data={"username": "maya"})

    for page in (client.get("/profile/new").text, client.get("/profile").text):
        select = page.split('name="gender"', 1)[1].split("</select>", 1)[0]
        assert '<option value="">Prefer not to say</option>' in select
        assert "required" not in select


def test_the_profile_heading_calls_you_what_the_nav_calls_you(client):
    """`profile.name`, not the username.

    The nav on the landing page and on every comparison says "Signed in as
    Maya" and this heading said "Signed in as maya" — one person, two
    spellings, on the screen whose subject is who you are.
    """
    client.post("/profile/new", data={"username": "maya", "display_name": "Maya"})

    page = client.get("/profile").text
    heading = page.split("<h1>", 1)[1].split("</h1>", 1)[0]
    assert heading == "Signed in as Maya"

    # A profile that never gave a name falls back to the username, so the
    # heading is never blank; `Profile.name` is what guarantees that.
    client.cookies.clear()
    client.post("/profile/new", data={"username": "nameless"})
    assert "Signed in as nameless" in client.get("/profile").text
