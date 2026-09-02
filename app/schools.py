"""The 25 schools, and the colour each one keeps everywhere it appears.

A school's colour is assigned once, here, from its position in the sample, so
the chip beside its name in the picker is the same colour as its line in the
chart. That consistency is the job a campus photo would have done — helping
the eye track which column is which school — at none of the cost.
"""

import sqlite3
from dataclasses import dataclass

# Distinguishable at 5 lines on one chart, and legible on both themes.
PALETTE = [
    "#0B6B57",
    "#8C5514",
    "#2F5D9E",
    "#A03A54",
    "#5B4B8A",
]


@dataclass(frozen=True)
class School:
    unitid: int
    name: str
    color: str


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
