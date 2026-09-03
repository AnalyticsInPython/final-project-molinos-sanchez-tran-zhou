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


def _own_years(conn: sqlite3.Connection, table: str) -> list[int]:
    """Years the table itself holds, for a source outside the IPEDS ingest.

    `scripts/import_ipeds.py` drops and recreates `ingest_runs`, which erases
    the rows `scripts/import_eada.py` wrote. Rather than make the athletics
    area disappear whenever someone rebuilds in the wrong order, fall back to
    asking the table. The cost is that `series_ends` cannot be answered this
    way — an absent row is not evidence a survey stopped — so it stays False.

    The table name is checked against `sqlite_master` before it reaches the
    query, because it cannot be passed as a parameter.
    """
    known = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()
    if not known:
        return []
    rows = conn.execute(f'SELECT DISTINCT year FROM "{table}" ORDER BY year').fetchall()
    return [row["year"] for row in rows if row["year"] is not None]


def latest_year(conn: sqlite3.Connection, table: str) -> int | None:
    """The newest year this table actually holds data for.

    The areas do not share a year — net price stops at 2021, admissions runs to
    2024 — so each asks for its own rather than the interface hard-coding a
    caption that is wrong for half the page.
    """
    row = conn.execute(
        "SELECT MAX(year) AS year FROM ingest_runs WHERE table_name = ? AND rows > 0",
        (table,),
    ).fetchone()
    if row and row["year"] is not None:
        return row["year"]
    years = _own_years(conn, table)
    return years[-1] if years else None


def years_available(conn: sqlite3.Connection, table: str) -> list[int]:
    """Every year with data, oldest first. The x axis of any trend view."""
    rows = conn.execute(
        "SELECT year FROM ingest_runs WHERE table_name = ? AND rows > 0 ORDER BY year",
        (table,),
    ).fetchall()
    return [row["year"] for row in rows] or _own_years(conn, table)


def series_ends(conn: sqlite3.Connection, table: str) -> bool:
    """Whether IPEDS publishes nothing newer, as opposed to us not loading it.

    Answered from evidence rather than from a flag someone has to remember to
    update: the ingest asks for years past the end of each series and records
    the empty answers, so a zero-row year above the newest live one is the
    survey saying it stops there. Net price has one; admissions does not,
    because it runs to 2024 and we simply asked for no more.

    Transport failures are never recorded, so a zero row here always means the
    API answered successfully with nothing.
    """
    newest = latest_year(conn, table)
    if newest is None:
        return False
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM ingest_runs "
        "WHERE table_name = ? AND year > ? AND rows = 0",
        (table, newest),
    ).fetchone()
    return row["n"] > 0
