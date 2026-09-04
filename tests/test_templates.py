"""Static checks on the template JavaScript.

There is no browser in this suite, so nothing here executes. These are cheap
greps that would have caught three real regressions in a row, all from one
refactor and all invisible to every other test:

1. `renderYears()` kept calling a `hidden()` helper after it moved into the
   picker partial's closure, so the year chips threw ReferenceError partway
   through drawing and looked like they were deleting themselves.
2. The picker's menu rows still called `add(item.unitid)` after items were
   re-keyed to `id`, so areas silently failed to add while schools kept
   working — schools happen to have a `unitid` field.
3. `absences()` still looked up `covered[key].has(school.unitid + ...)`, got
   `undefined` for every school, matched no coverage, and disabled every year
   the moment an area was selected.

All three are the same shape: an identifier that no longer exists, in a
language that fails silently rather than at import. A grep is a poor substitute
for running the code, and it is much better than nothing.

The last three render `/` and `/profile/new` and check what is in the HTML,
which is as far as a suite without a browser can follow the *Use my saved
schools* button: that it is offered to the right reader, on the right picker,
carrying the right ids. Whether clicking it works was checked by hand.
"""

import json
import re
from pathlib import Path

import pytest

from app.db import DB_PATH

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"
HTML = sorted(TEMPLATES.rglob("*.html"))

# Berkeley, Stanford, MIT — three of the five the demo profile saves.
BERKELEY, STANFORD, MIT = 110635, 243744, 166683

needs_db = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="No database — run: uv run python scripts/import_ipeds.py",
)


def scripts(path: Path) -> str:
    """Just the <script> bodies, minus Jinja expressions.

    Jinja emits the server-side values, so `{{ s.unitid }}` inside a data blob
    is correct and must not trip these checks — only what the browser executes
    is in scope here.
    """
    pattern = r"<script(?![^>]*application/json)[^>]*>(.*?)</script>"
    blocks = re.findall(pattern, path.read_text(), re.S)
    return re.sub(r"\{\{.*?\}\}|\{%.*?%\}", "", "\n".join(blocks), flags=re.S)


def test_there_are_templates_to_check():
    assert HTML, "no templates found — this suite would pass vacuously"


@pytest.mark.parametrize("path", HTML, ids=lambda p: p.name)
def test_no_stale_unitid_in_browser_code(path):
    """Picker items are keyed `id`. `unitid` in JS is always a stale rename."""
    assert ".unitid" not in scripts(path), (
        f"{path.name} reads .unitid in JavaScript. Picker items use .id — this is "
        "the rename that silently broke areas and the year chips twice."
    )


@pytest.mark.parametrize("path", HTML, ids=lambda p: p.name)
def test_every_helper_called_is_defined_in_the_same_script(path):
    """Catches a helper that moved into a partial and left its callers behind.

    Only checks the handful of helpers the pickers and year grid share, since a
    general call-graph check would need a JS parser.
    """
    body = scripts(path)
    for helper in ("hidden", "marker", "openMenu", "closeMenu", "renderYears", "activeAreas"):
        called = re.search(rf"(?<![\w.]){helper}\s*\(", body)
        defined = re.search(rf"function\s+{helper}\s*\(", body)
        if called and not defined:
            pytest.fail(
                f"{path.name} calls {helper}() but does not define it. If it moved "
                "into a partial, this file needs its own copy or the call removed."
            )


def test_the_picker_is_included_rather_than_copied():
    """Three pickers, one component. A fourth copy is how they drift apart."""
    partial = TEMPLATES / "_school_picker.html"
    assert partial.exists()
    includes = [p for p in HTML if "_school_picker.html" in p.read_text()]
    assert len(includes) >= 2, "the shared picker should be included by more than one page"
    # Nobody else should be hand-rolling a combobox.
    for path in HTML:
        if path == partial:
            continue
        assert 'role="combobox"' not in path.read_text(), (
            f"{path.name} declares its own combobox; include _school_picker.html instead"
        )


def test_the_picker_takes_a_preset_without_knowing_where_it_came_from():
    """The way in is an event, and it stays as anonymous as the way out.

    A shortlist is a profile's business. The moment the partial reads one, the
    questionnaire copy of it starts carrying code it can never run.
    """
    partial = (TEMPLATES / "_school_picker.html").read_text()
    assert 's-preset"' in partial, "the picker no longer accepts a preset"
    assert re.search(r"s-preset[\s\S]{0,400}?add\(", partial), (
        "the preset must go through add(), or colours, chips, hidden fields, the "
        "count, the clash check and schools-changed all drift out of step"
    )
    assert "profile" not in partial.lower(), (
        "the shared picker must not know what a profile is"
    )


def _shortlist_ids(html: str) -> list[int]:
    match = re.search(r'id="shortlist-data"[^>]*>(.*?)</script>', html, re.S)
    return json.loads(match.group(1)) if match else []


@needs_db
def test_the_saved_schools_button_is_offered_only_to_a_signed_in_shortlist(
    tmp_path, monkeypatch
):
    """`/` offers the shortlist as a preset, and never as a finished comparison.

    The link this replaces went straight to /compare with no areas and no
    years, which the compare page reads as *every* area at its latest year —
    the one shape of the page nobody asked for.
    """
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app import profiles
    from app.main import app

    real_connect = profiles.connect
    monkeypatch.setattr(profiles, "connect", lambda: real_connect(tmp_path / "profiles.db"))
    with profiles.connect() as pconn:
        profiles.get_or_create(pconn, "reader")
        for unitid in (BERKELEY, STANFORD, MIT):
            profiles.add_school(pconn, "reader", unitid)
        profiles.get_or_create(pconn, "newcomer")

    page = TestClient(app, cookies={"profile": "reader"}).get("/").text
    assert "Use my saved schools" in page
    assert re.search(r'<button[^>]*type="button"[^>]*id="use-shortlist"', page), (
        "the button must be type=button or it submits the empty form"
    )
    assert _shortlist_ids(page) == [BERKELEY, STANFORD, MIT], "ids, in shortlist order"

    # The picker is the only route to /compare now: no link may skip it.
    assert 'href="/compare' not in page

    # A profile without a shortlist has nothing to preset, and neither has a
    # reader who is not signed in. The click handler is in the page either way;
    # what must not be there is the button it binds to or the ids it would read.
    blank = TestClient(app, cookies={"profile": "newcomer"}).get("/").text
    assert "Use my saved schools" not in blank and 'id="shortlist-data"' not in blank

    out = TestClient(app).get("/").text
    assert "Use my saved schools" not in out and 'id="shortlist-data"' not in out


@needs_db
def test_the_questionnaire_never_offers_the_saved_schools_button():
    """It includes the same picker, and is where a shortlist is built."""
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app.main import app

    page = TestClient(app).get("/profile/new").text
    assert 'role="combobox"' in page, "the questionnaire should still have the picker"
    assert "Use my saved schools" not in page
    assert "shortlist" not in page.lower(), "no trace of a saved list on the sign-up form"
