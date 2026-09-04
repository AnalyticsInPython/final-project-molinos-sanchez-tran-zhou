"""Present mode: the same pages, sized for the back of a room.

Three things are worth a test here and the rest is CSS, which this suite has
no browser to check:

1. The toggle carries the reader's current page as `?next=`, which is the
   shape an open redirect takes. `safe_next` is the guard, and it is the only
   piece of this feature that can hurt somebody.
2. The cookie has to reach `<body>` as a class, or every rule in the
   stylesheet's present block is inert.
3. A notice has to survive being folded — first sentence out, rest inside a
   `<details>` — with nothing dropped and normal mode untouched.

The rendering tests need the databases; the guard and the sentence split do
not, and run anywhere.
"""

import re

import pytest

from app.db import DB_PATH
from app.main import safe_next
from app.notices import first_sentence

# The five schools the demo compares, in the order seed_demo.py saves them.
DEMO_COMPARE = (
    "/compare?school=110635&color=%23003262&school=243744&color=%238c1515"
    "&school=166683&color=%23a31f34&school=211440&color=%23c41230"
    "&school=170976&color=%2300274c"
    "&tailor=financial_aid&tailor=selectiveness&tailor=retention"
)

needs_db = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="No database — run: uv run python scripts/import_ipeds.py",
)


@pytest.fixture
def client():
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


# --- The redirect guard ---------------------------------------------------


@pytest.mark.parametrize(
    "target",
    [
        "/",
        "/compare?school=110635&color=%23003262",
        "/profile",
        "/compare#area-retention",
    ],
)
def test_a_path_on_this_site_is_where_we_go_back_to(target):
    assert safe_next(target) == target


@pytest.mark.parametrize(
    "target",
    [
        None,
        "",
        "   ",
        "//evil.example",  # a protocol-relative URL: another host entirely
        "///evil.example",
        "/\\evil.example",  # browsers read the backslash as a slash here
        " //evil.example",
        "https://evil.example",
        "http://evil.example/compare",
        "javascript:alert(1)",
        "compare",  # relative, so it depends on where it was clicked from
    ],
)
def test_anything_that_could_leave_the_site_falls_back_to_the_front_page(target):
    assert safe_next(target) == "/"


def test_the_toggle_sets_and_clears_the_cookie_and_returns_to_the_page(client):
    on = client.get("/present/on?next=/profile", follow_redirects=False)
    assert on.status_code == 303
    assert on.headers["location"] == "/profile"
    assert client.cookies.get("present") == "1"

    off = client.get("/present/off?next=/profile", follow_redirects=False)
    assert off.status_code == 303
    assert off.headers["location"] == "/profile"
    assert not client.cookies.get("present")


def test_the_toggle_will_not_send_a_reader_off_the_site(client):
    away = client.get("/present/on?next=https://evil.example", follow_redirects=False)
    assert away.headers["location"] == "/"


@needs_db
def test_the_cookie_reaches_the_body_class_and_the_link_flips(client):
    """Every present rule hangs off this class; without it the feature is CSS
    nobody can reach."""
    plain = client.get("/")
    assert '<body class="present">' not in plain.text
    assert re.search(r'href="/present/on\?next=[^"]*"', plain.text), "no way in"

    client.cookies.set("present", "1")
    shown = client.get("/")
    assert '<body class="present">' in shown.text
    assert re.search(r'href="/present/off\?next=[^"]*"', shown.text), "no way back out"


@needs_db
def test_the_toggle_carries_the_whole_comparison_back(client):
    """The demo's URL is nine query parameters long. Losing them on the way
    through the toggle would land the presenter on the picker mid-sentence."""
    page = client.get(DEMO_COMPARE)
    link = re.search(r'href="/present/on\?next=([^"]*)"', page.text).group(1)

    landing = client.get(f"/present/on?next={link}", follow_redirects=False)
    assert landing.headers["location"] == DEMO_COMPARE


# --- Folding the notices --------------------------------------------------


def test_a_notice_splits_into_its_first_sentence_and_the_rest():
    opening, rest = first_sentence(
        "These are 2021 figures, the most recent IPEDS publishes for net price. "
        "Current figures will have moved since."
    )
    assert opening == "These are 2021 figures, the most recent IPEDS publishes for net price."
    assert rest == "Current figures will have moved since."


def test_a_one_sentence_notice_has_nothing_to_fold():
    text = "Michigan reports no athletics data at all."
    assert first_sentence(text) == (text, "")


def test_the_split_keeps_every_word():
    text = (
        "MIT and Stanford report no financial aid data at all, so they are absent below "
        "and from the charts. That is a gap in the federal data, not a zero."
    )
    opening, rest = first_sentence(text)
    assert f"{opening} {rest}" == text


def test_a_figure_is_not_a_full_stop():
    """The reason the split is not `text.split('. ')`: these notices are full
    of amounts, and cutting "$48,000. 50" out of one would be worse than not
    folding it at all."""
    opening, rest = first_sentence(
        "Published costs rose about 8% between 2021 and 2023. We do not extrapolate."
    )
    assert opening == "Published costs rose about 8% between 2021 and 2023."
    assert rest == "We do not extrapolate."

    whole = "Berkeley's spread is $46,662.30 across the five bands."
    assert first_sentence(whole) == (whole, "")


@needs_db
def test_present_mode_folds_the_notices_and_normal_mode_does_not(client):
    plain = client.get(DEMO_COMPARE).text
    assert "<details><summary>more</summary>" not in plain

    client.cookies.set("present", "1")
    shown = client.get(DEMO_COMPARE).text
    assert "<details><summary>more</summary>" in shown

    # Folded, not shortened: the sentences hidden behind "more" are still on
    # the page, so the presenter can open one when a grader asks.
    for phrase in (
        "Do not read them as a quote for next year",
        "The comparison between these schools still holds",
    ):
        assert phrase in shown, phrase


@needs_db
def test_the_year_meaning_lines_stay_on_one_line(client):
    """Measured on the page the demo actually shows, not on the functions:
    what matters is the string that reaches the card."""
    page = client.get(DEMO_COMPARE).text
    lines = re.findall(r'<p class="year-meaning">\s*(.*?)\s*</p>', page, re.S)
    assert len(lines) >= 5, "every card should still say what its year means"
    for line in lines:
        assert len(line) <= 110, (len(line), line)
