"""The 25 schools, and the colour each one carries everywhere it appears.

A school's colour defaults to its own brand colour, because a reader who knows
these schools already associates Dartmouth with green and Michigan with navy,
and fighting that association costs comprehension for no gain.

Brand colours collide, though — this sample alone holds four dark reds and six
navies — so the colour is an editable default, not a fixed property. The picker
hands the user a swatch per selection and `selected()` takes whatever they
chose. Anything not overridden falls back to the brand colour, and any school
without one falls back to PALETTE.
"""

import re
import sqlite3
from dataclasses import dataclass

# Five categorical hues, in fixed order. Checked rather than chosen by eye:
# every adjacent pair clears the colour-blindness separation threshold (worst
# dE 9.1 light, 8.4 dark) and the normal-vision floor (19.6 / 19.3). The first
# palette here did not — its blue and violet came out at dE 7.3 for normal
# vision, which is why two of the five lines looked like one.
#
# No longer the default: it is the fallback for a school with no brand colour
# on file, which is every school the day we widen past this sample.
PALETTE = [
    "#2a78d6",  # blue
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e87ba4",  # magenta
]

# Official primary brand colours, transcribed from each school's published
# identity guidelines.
#
# Where a school's best-known colour is too light to read as a line on white —
# Michigan maize, Columbia blue, Vanderbilt gold — this takes the darker half
# of its official pair instead. A chart is not a pennant; the colour has to
# survive being a two-pixel stroke.
#
# These are hand-entered and worth a check before the demo.
BRAND_COLORS = {
    186131: "#e77500",  # Princeton — orange
    166683: "#a31f34",  # MIT — cardinal red
    166027: "#a51c30",  # Harvard — crimson
    243744: "#8c1515",  # Stanford — cardinal
    130794: "#00356b",  # Yale — Yale blue
    215062: "#011f5b",  # Penn — Penn blue
    110404: "#ff6c0c",  # Caltech — orange
    198419: "#012169",  # Duke — Duke blue
    217156: "#4e3629",  # Brown — seal brown
    162928: "#002d72",  # Johns Hopkins — Hopkins blue
    147767: "#4e2a84",  # Northwestern — purple
    190150: "#1d4f91",  # Columbia — darker of the two official blues
    190415: "#b31b1b",  # Cornell — carnelian
    144050: "#800000",  # Chicago — maroon
    110635: "#003262",  # UC Berkeley — Berkeley blue
    110662: "#2774ae",  # UCLA — UCLA blue
    227757: "#00205b",  # Rice — Rice blue
    182670: "#00693e",  # Dartmouth — Dartmouth green
    221999: "#866d4b",  # Vanderbilt — darker of gold/black
    152080: "#0c2340",  # Notre Dame — navy
    170976: "#00274c",  # Michigan — Michigan blue, not maize
    131496: "#041e42",  # Georgetown — Georgetown blue
    199120: "#4b9cd3",  # UNC Chapel Hill — Carolina blue
    211440: "#c41230",  # Carnegie Mellon — CMU red
    179867: "#016936",  # WashU — green
}

# Institution names as IPEDS records them are too long to label a chart with.
# These are the names a person would say out loud.
SHORT_NAMES = {
    186131: "Princeton",
    166683: "MIT",
    166027: "Harvard",
    243744: "Stanford",
    130794: "Yale",
    215062: "Penn",
    110404: "Caltech",
    198419: "Duke",
    217156: "Brown",
    162928: "Johns Hopkins",
    147767: "Northwestern",
    190150: "Columbia",
    190415: "Cornell",
    144050: "Chicago",
    110635: "UC Berkeley",
    110662: "UCLA",
    227757: "Rice",
    182670: "Dartmouth",
    221999: "Vanderbilt",
    152080: "Notre Dame",
    170976: "Michigan",
    131496: "Georgetown",
    199120: "UNC Chapel Hill",
    211440: "Carnegie Mellon",
    179867: "WashU",
}

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def clean_color(value: str | None) -> str | None:
    """A user-supplied colour, or None if it is not a six-digit hex.

    The colour reaches us through the query string and goes straight into a
    `style` attribute and an SVG `stroke`, so it is validated on the way in
    rather than trusted and escaped later.
    """
    if value and HEX.match(value):
        return value.lower()
    return None


@dataclass(frozen=True)
class School:
    unitid: int
    name: str
    color: str

    @property
    def short(self) -> str:
        """The name to label a chart with."""
        return SHORT_NAMES.get(self.unitid, self.name)


def brand_color(unitid: int, index: int) -> str:
    """The school's own colour, or a palette hue if we do not have one."""
    return BRAND_COLORS.get(unitid) or PALETTE[index % len(PALETTE)]


def all_schools(conn: sqlite3.Connection) -> list[School]:
    """Every school in the sample, alphabetically.

    By name as displayed, not by `indicative_rank`. A search box needs an order
    the reader can predict when they scroll it instead of typing, and a ranking
    nobody can see is not one — it also quietly asserts a pecking order the
    project has no business publishing. NOCASE so the sort does not depend on
    SQLite comparing bytes.
    """
    rows = conn.execute(
        "SELECT unitid, inst_name FROM schools ORDER BY inst_name COLLATE NOCASE"
    ).fetchall()
    return [
        School(row["unitid"], row["inst_name"], brand_color(row["unitid"], i))
        for i, row in enumerate(rows)
    ]


def selected(
    conn: sqlite3.Connection,
    unitids: list[int],
    colors: list[str] | None = None,
) -> list[School]:
    """The chosen schools, each in its overridden colour or its brand colour.

    `colors` is index-matched to `unitids` — the picker emits the two lists in
    step. An entry that is missing, blank or not a hex triple falls back to the
    brand colour, so a hand-typed URL still renders.
    """
    by_id = {s.unitid: s for s in all_schools(conn)}
    overrides = colors or []

    chosen = []
    for i, unitid in enumerate(unitids):
        school = by_id.get(unitid)
        if school is None:
            continue
        override = clean_color(overrides[i] if i < len(overrides) else None)
        chosen.append(School(school.unitid, school.name, override or school.color))
    return chosen
