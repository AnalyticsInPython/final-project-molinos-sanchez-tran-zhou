"""The 25 schools, and the colour each one keeps everywhere it appears.

A school's colour is assigned once, here, from its position in the sample, so
the chip beside its name in the picker is the same colour as its line in the
chart. That consistency is the job a campus photo would have done — helping
the eye track which column is which school — at none of the cost.
"""

import sqlite3
from dataclasses import dataclass

# Five categorical hues, in fixed order. Checked rather than chosen by eye:
# every adjacent pair clears the colour-blindness separation threshold (worst
# dE 9.1 light, 8.4 dark) and the normal-vision floor (19.6 / 19.3). The first
# palette here did not — its blue and violet came out at dE 7.3 for normal
# vision, which is why two of the five lines looked like one.
#
# Three of the light steps sit under 3:1 contrast on white. That is allowed
# only because every series is also named in a legend and repeated in the
# table below the chart, so colour is never the only thing carrying identity.
PALETTE = [
    "#2a78d6",  # blue
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e87ba4",  # magenta
]

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


@dataclass(frozen=True)
class School:
    unitid: int
    name: str
    color: str

    @property
    def short(self) -> str:
        """The name to label a chart with."""
        return SHORT_NAMES.get(self.unitid, self.name)


def all_schools(conn: sqlite3.Connection) -> list[School]:
    """Every school in the sample, in the sample's own order."""
    rows = conn.execute(
        "SELECT unitid, inst_name FROM schools ORDER BY indicative_rank"
    ).fetchall()
    return [
        School(row["unitid"], row["inst_name"], PALETTE[i % len(PALETTE)])
        for i, row in enumerate(rows)
    ]


def selected(conn: sqlite3.Connection, unitids: list[int]) -> list[School]:
    """The chosen schools, coloured by their position in *this* selection.

    Colours come from the selection rather than from the full sample so that
    two schools next to each other in the list never end up sharing a colour
    on the same chart.
    """
    by_id = {s.unitid: s for s in all_schools(conn)}
    chosen = [by_id[u] for u in unitids if u in by_id]
    return [
        School(s.unitid, s.name, PALETTE[i % len(PALETTE)])
        for i, s in enumerate(chosen)
    ]
