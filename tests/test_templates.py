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
"""

import re
from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"
HTML = sorted(TEMPLATES.rglob("*.html"))


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
