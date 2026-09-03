"""Which area leads the comparison, and who gets to decide it.

The questionnaire tells someone that the stage they picked "decides what
leads the comparison". Until this test existed that sentence was a promise
the page did not keep: `compare()` rendered `areas.ALL` in one fixed order
for everybody.

Two rules, and the second is the one worth guarding. The stage moves one
area to the front and leaves every other area in its usual order — a page
that reshuffles itself per reader is a page nobody can give directions
around. And an explicit `area=` list is an order the reader chose, so it
outranks the profile: a link someone shares must open the same way for the
person who receives it.
"""

import re

import pytest

from app import areas
from app.db import DB_PATH

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="No database — run: uv run python scripts/import_ipeds.py",
)

MIT, CARNEGIE_MELLON = 166683, 243744

USUAL = [area.TITLE for area in areas.ALL]


def _titles(html: str) -> list[str]:
    """The area headings, top to bottom. The card's own <h2> carries no
    class; every other heading in the app does."""
    return re.findall(r"<h2>([^<]+)</h2>", html)


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A TestClient over a throwaway profiles database.

    Same shape as tests/test_cuts.py::test_tailoring_reads_the_profile_and_
    never_the_url — the real one belongs to whoever is running the app.
    """
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app import profiles
    from app.main import app

    real_connect = profiles.connect
    monkeypatch.setattr(profiles, "connect", lambda: real_connect(tmp_path / "profiles.db"))

    def make(username: str | None = None, stage: str | None = None):
        if username:
            with profiles.connect() as pconn:
                profiles.get_or_create(pconn, username)
                pconn.execute(
                    "UPDATE profiles SET stage = ? WHERE username = ?", (stage, username)
                )
                pconn.commit()
        cookies = {"profile": username} if username else {}
        return TestClient(app, cookies=cookies)

    return make


BASE = f"/compare?school={MIT}&school={CARNEGIE_MELLON}"


def test_signed_out_the_order_is_the_one_the_areas_declare():
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app.main import app

    assert _titles(TestClient(app).get(BASE).text) == USUAL


def test_applying_leads_with_selectiveness_and_moves_nothing_else(client):
    """Someone deciding where to apply is asking whether they can get in."""
    titles = _titles(client("maya", "applying").get(BASE).text)
    assert titles[0] == "Selectiveness"
    assert titles == ["Selectiveness"] + [t for t in USUAL if t != "Selectiveness"]


def test_choosing_leads_with_financial_aid(client):
    """Someone holding offers is asking what they will pay. That is already
    first in areas.ALL, so this guards a promise rather than a change."""
    titles = _titles(client("sam", "choosing").get(BASE).text)
    assert titles[0] == "Student financial aid"
    assert titles == USUAL


def test_a_profile_without_a_stage_changes_nothing(client):
    assert _titles(client("blank").get(BASE).text) == USUAL


def test_an_area_the_reader_named_outranks_the_stage(client):
    """A shared link opens the same way for whoever receives it, which is
    the whole reason the comparison lives in the URL."""
    asked = client("maya", "applying").get(BASE + "&area=outcomes&area=selectiveness")
    assert _titles(asked.text) == ["After graduation", "Selectiveness"]


def test_the_stage_never_reaches_the_url(client):
    """Same rule as tailoring: the server reads the profile, the link says
    nothing about the reader."""
    page = client("maya", "applying").get(BASE).text
    assert "applying" not in page
    assert "stage=" not in page
