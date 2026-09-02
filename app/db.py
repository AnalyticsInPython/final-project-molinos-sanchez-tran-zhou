"""Opening the database, and asking it which year an area is showing.

There is no ORM and no models layer. Every area reads the ingest tables
directly with one SQL query and does its thinking in Polars, because the
ingest tables are the only schema we have and a week is not long enough to
earn a second one.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "likeforlike.db"


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    """Open the sample database read-only.

    Read-only because nothing in the web app should ever write to it: the
    database is a build artifact of `scripts/import_ipeds.py`, not state.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"No database at {path}. Build it first:\n"
            "    uv run python scripts/import_ipeds.py"
        )
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def year_for(conn: sqlite3.Connection, table: str) -> int | None:
    """The year the given ingest table was pulled for.

    The areas do not share a year — net price ends 2021, test scores run to
    2022 — so each area asks for its own rather than the interface hard-coding
    a caption that is wrong for half the page.
    """
    row = conn.execute(
        "SELECT year FROM ingest_runs WHERE table_name = ?", (table,)
    ).fetchone()
    return row["year"] if row else None
