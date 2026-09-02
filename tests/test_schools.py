"""Tests for school identity — the colour a school carries into a chart.

The colour reaches the app through the query string and is written straight
into a `style` attribute and an SVG `stroke`, so the validation below is the
thing standing between a URL and injected markup. The rest guards the pairing:
`school` and `color` are two parallel lists, and if they ever slip out of step
the chart is wrong in a way that still looks plausible.
"""

import pytest

from app.db import DB_PATH, connect
from app.schools import (
    BRAND_COLORS,
    PALETTE,
    SHORT_NAMES,
    brand_color,
    clean_color,
    selected,
)

DARTMOUTH = 182670
HARVARD = 166027
STANFORD = 243744

needs_db = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="No database — run: uv run python scripts/import_ipeds.py",
)


@pytest.fixture
def conn():
    with connect() as connection:
        yield connection


def test_every_named_school_has_a_brand_color():
    assert set(SHORT_NAMES) == set(BRAND_COLORS)


def test_brand_colors_are_six_digit_hex():
    for unitid, color in BRAND_COLORS.items():
        assert clean_color(color) == color, f"{unitid} has a malformed colour"


def test_unknown_school_falls_back_to_the_palette():
    """The day the sample widens, most schools will have no brand colour."""
    assert brand_color(999999, 0) == PALETTE[0]
    assert brand_color(DARTMOUTH, 0) == BRAND_COLORS[DARTMOUTH]


@pytest.mark.parametrize(
    "value",
    ["", None, "red", "#fff", "#12345", "#1234567", "0b6b57", "#gggggg"],
)
def test_junk_colors_are_rejected(value):
    assert clean_color(value) is None


def test_a_style_injection_is_not_a_color():
    assert clean_color("#000; background: url(//evil.example/x)") is None


@needs_db
def test_selection_defaults_to_brand_colors(conn):
    chosen = selected(conn, [DARTMOUTH, HARVARD])
    assert [s.color for s in chosen] == [
        BRAND_COLORS[DARTMOUTH],
        BRAND_COLORS[HARVARD],
    ]


@needs_db
def test_overrides_apply_in_order(conn):
    """The lists are index-matched; this is the test that catches a slip."""
    chosen = selected(conn, [DARTMOUTH, HARVARD, STANFORD], ["#7b2ff7", "", "#111111"])
    assert [(s.unitid, s.color) for s in chosen] == [
        (DARTMOUTH, "#7b2ff7"),
        (HARVARD, BRAND_COLORS[HARVARD]),  # blank falls back
        (STANFORD, "#111111"),
    ]


@needs_db
def test_a_bad_override_falls_back_rather_than_reaching_the_page(conn):
    chosen = selected(conn, [DARTMOUTH], ["javascript:alert(1)"])
    assert chosen[0].color == BRAND_COLORS[DARTMOUTH]


@needs_db
def test_short_colors_list_does_not_shift_later_schools(conn):
    chosen = selected(conn, [DARTMOUTH, HARVARD], ["#7b2ff7"])
    assert chosen[1].color == BRAND_COLORS[HARVARD]


@needs_db
def test_unknown_unitid_is_dropped_without_shifting_colors(conn):
    """A hand-edited URL must not slide the remaining swatches by one."""
    chosen = selected(conn, [DARTMOUTH, 999999, STANFORD], ["#7b2ff7", "#222222", "#333333"])
    assert [(s.unitid, s.color) for s in chosen] == [
        (DARTMOUTH, "#7b2ff7"),
        (STANFORD, "#333333"),
    ]
