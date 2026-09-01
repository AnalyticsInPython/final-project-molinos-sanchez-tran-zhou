"""Pull IPEDS data for the sample schools into SQLite.

Deliberately thin: each endpoint lands in its own table with the columns the
API returned, so we can explore in SQL and decide what the real schema should
be. No cleaning, no reshaping — that comes once we know what we are keeping.

The API takes comma-separated unitids, so it is one request per endpoint plus
however many pages that endpoint needs (see `fetch`).

    uv run python scripts/import_ipeds.py

Two things about missing values, both learned the hard way:

- IPEDS uses negative sentinels (-1, -2, -3) for missing and not-applicable in
  most columns. Rows are stored here exactly as returned, so anything that
  averages a column without stripping them will be wrong.
- But a negative `net_price` is NOT a sentinel. Grant aid can exceed the total
  cost of attendance, and the sample contains five such values (-1012 to
  -2251), none of them -1/-2/-3. A blanket "drop negatives" rule deletes real
  data — and deletes the most striking fact in the dataset.
"""

import argparse
import json
import sqlite3
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from schools import SCHOOLS, UNITIDS

BASE = "https://educationdata.urban.org/api/v1/college-university/ipeds"
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "likeforlike.db"

# 2021 is the anchor: the last year net price exists, so it is the only year
# where cost and outcomes can be read off the same cross-section.
YEAR = 2021

# endpoint -> what an incoming undergraduate is actually asking
ENDPOINTS = {
    "directory": "Who and where is this school?",
    "admissions-enrollment": "Can I get in? (applications, admits, test scores)",
    "academic-year-tuition": "What is the sticker price?",
    "academic-year-room-board-other": "What does living there cost?",
    "sfa-grants-and-net-price": "What will I actually pay, at my income?",
    "grad-rates": "Do students finish?",
    "grad-rates-pell": "Do students on Pell grants finish?",
    "fall-retention": "Do first-years come back?",
    "student-faculty-ratio": "How big are classes, roughly?",
    "completions-cip-2": "What can I study?",
}


def fetch(endpoint: str, year: int) -> tuple[list[dict], str]:
    """All rows for our sample from one endpoint-year, plus the first URL.

    The API pages at 10,000 rows and hands back a `next` link. Small result
    sets arrive whole, which makes it easy to conclude there is no pagination
    at all — `completions-cip-2` for these 25 schools is 71,010 rows and would
    silently arrive as 4 schools' worth. Always follow `next`.
    """
    first = f"{BASE}/{endpoint}/{year}/?unitid={','.join(map(str, UNITIDS))}"
    rows: list[dict] = []
    url = first

    while url:
        with urllib.request.urlopen(url, timeout=300) as response:
            payload = json.load(response)
        rows.extend(payload["results"])
        url = payload.get("next")

    expected = payload["count"]
    if len(rows) != expected:
        raise RuntimeError(f"{endpoint} {year}: got {len(rows)} rows, API reported {expected}")

    return rows, first


def create_table(connection: sqlite3.Connection, name: str, rows: list[dict]) -> None:
    """A table shaped like whatever the API sent back.

    Everything is TEXT/INTEGER/REAL by inference from the first non-null value;
    this is a scratch schema for exploration, not the final one.
    """
    columns = list(rows[0])
    types = {}
    for column in columns:
        sample = next((r[column] for r in rows if r[column] is not None), None)
        types[column] = (
            "INTEGER"
            if isinstance(sample, bool | int)
            else "REAL"
            if isinstance(sample, float)
            else "TEXT"
        )

    definition = ", ".join(f'"{c}" {types[c]}' for c in columns)
    connection.execute(f'DROP TABLE IF EXISTS "{name}"')
    connection.execute(f'CREATE TABLE "{name}" ({definition})')
    connection.executemany(
        f'INSERT INTO "{name}" VALUES ({",".join("?" * len(columns))})',
        [
            tuple(json.dumps(r[c]) if isinstance(r[c], list | dict) else r[c] for c in columns)
            for r in rows
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=YEAR)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()

    args.db.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(args.db)

    # The curated sample itself, so the database is self-describing.
    connection.execute("DROP TABLE IF EXISTS schools")
    connection.execute(
        """
        CREATE TABLE schools (
            unitid          INTEGER PRIMARY KEY,
            inst_name       TEXT NOT NULL,
            indicative_rank INTEGER NOT NULL
        )
        """
    )
    connection.executemany("INSERT INTO schools VALUES (?, ?, ?)", SCHOOLS)

    connection.execute("DROP TABLE IF EXISTS ingest_runs")
    connection.execute(
        """
        CREATE TABLE ingest_runs (
            endpoint    TEXT NOT NULL,
            year        INTEGER NOT NULL,
            url         TEXT NOT NULL,
            rows        INTEGER NOT NULL,
            schools     INTEGER NOT NULL,
            fetched_at  TEXT NOT NULL,
            question    TEXT
        )
        """
    )

    for endpoint, question in ENDPOINTS.items():
        table = endpoint.replace("-", "_")
        try:
            rows, url = fetch(endpoint, args.year)
        except urllib.error.HTTPError as error:
            print(f"  {endpoint:<32} HTTP {error.code} — skipped")
            continue

        if not rows:
            # An empty 200 is a failure here, not a success: it means the year
            # has no data and anything downstream would silently see nothing.
            print(f"  {endpoint:<32} 0 rows — NO DATA for {args.year}")
            continue

        create_table(connection, table, rows)
        covered = len({r["unitid"] for r in rows})
        connection.execute(
            "INSERT INTO ingest_runs VALUES (?, ?, ?, ?, ?, ?, ?)",
            (endpoint, args.year, url, len(rows), covered, datetime.now(UTC).isoformat(), question),
        )
        print(f"  {endpoint:<32} {len(rows):>6} rows  {covered:>2}/25 schools")

    connection.commit()
    connection.close()
    print(f"\nWrote {args.db}")


if __name__ == "__main__":
    main()
