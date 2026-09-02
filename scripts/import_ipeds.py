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
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from schools import SCHOOLS, UNITIDS

BASE = "https://educationdata.urban.org/api/v1/college-university/ipeds"
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "likeforlike.db"

# 2021 is the anchor for anything that still needs one: the last year net price
# exists. Most endpoints now pull a range instead, and discover their own
# ceiling by asking for years past the end and recording the empty answer.
YEAR = 2021

# Ten years, not five. 2020 is a COVID anomaly — Stanford's yield fell from
# 82.3% to 68.4% and back the year after — and a five-year window puts it at
# the edge with nothing to read it against. Ten shows it as the blip it is, and
# reveals the trend underneath: admit rates at these schools have roughly
# halved since 2015.
TREND = range(2015, 2025)

# Reference tables nobody plots over time. Short range rather than a pinned
# year, so the newest available is found rather than assumed.
RECENT = range(2021, 2025)

# completions-cip-2 is 71,010 rows for one year of this sample. It gets a
# narrow window until an area actually uses it.
BULKY = range(2022, 2024)

# The seven comparison areas the interface offers, in the order they are shown.
# Each maps to one or more endpoints. `year` overrides the anchor where an
# endpoint's coverage ends earlier or later — the areas do NOT share a year, and
# the interface has to say which year each one is showing.
AREAS = {
    "institution_characteristics": "Who and where is this school?",
    "admissions_and_test_scores": "Can I get in, and with what scores?",
    "student_charges": "What is the sticker price?",
    "student_financial_aid": "What will I actually pay, at my income?",
    "enrollment": "Who goes here?",
    "retention_and_graduation": "Do students come back, and finish?",
    "academic_libraries": "What are the library holdings?",
}

# table name -> (path after /ipeds/, years, area)
# The path may carry extra segments before the query string; enrollment-headcount
# takes a level_of_study (1 = undergraduate).
#
# Years are a range, not a point. An endpoint is asked for every year in its
# range; years with no data come back as an empty success and are recorded as
# such, which is what lets the app tell "the survey stopped here" apart from
# "we only loaded this much".
ENDPOINTS = {
    "directory": ("directory", RECENT, "institution_characteristics"),
    "institutional_characteristics": (
        "institutional-characteristics",
        RECENT,
        "institution_characteristics",
    ),
    "admissions_enrollment": ("admissions-enrollment", TREND, "admissions_and_test_scores"),
    "admissions_requirements": ("admissions-requirements", RECENT, "admissions_and_test_scores"),
    "academic_year_tuition": ("academic-year-tuition", TREND, "student_charges"),
    "academic_year_room_board_other": (
        "academic-year-room-board-other",
        TREND,
        "student_charges",
    ),
    "sfa_grants_and_net_price": ("sfa-grants-and-net-price", TREND, "student_financial_aid"),
    "enrollment_headcount": ("enrollment-headcount/{year}/1", TREND, "enrollment"),
    "fall_retention": ("fall-retention", TREND, "retention_and_graduation"),
    "grad_rates": ("grad-rates", TREND, "retention_and_graduation"),
    "grad_rates_pell": ("grad-rates-pell", TREND, "retention_and_graduation"),
    "academic_libraries": ("academic-libraries", RECENT, "academic_libraries"),
    "student_faculty_ratio": ("student-faculty-ratio", RECENT, "institution_characteristics"),
    # Not one of the seven areas, but kept: degrees awarded by field.
    "completions_cip_2": ("completions-cip-2", BULKY, None),
}


def fetch(endpoint: str, year: int) -> tuple[list[dict], str]:
    """All rows for our sample from one endpoint-year, plus the first URL.

    The API pages at 10,000 rows and hands back a `next` link. Small result
    sets arrive whole, which makes it easy to conclude there is no pagination
    at all — `completions-cip-2` for these 25 schools is 71,010 rows and would
    silently arrive as 4 schools' worth. Always follow `next`.
    """
    path = endpoint.format(year=year) if "{year}" in endpoint else f"{endpoint}/{year}"
    first = f"{BASE}/{path}/?unitid={','.join(map(str, UNITIDS))}"
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
    """A table shaped like whatever the API sent back, across every year.

    Everything is TEXT/INTEGER/REAL by inference from the first non-null value;
    this is a scratch schema for exploration, not the final one.

    Columns are the union over all rows rather than whatever the first row
    happened to carry, because **the API's schema drifts between years**:
    `directory` gains the Carnegie Classification 2025 columns partway along
    the range, and reading columns off `rows[0]` raised KeyError the moment an
    older year followed a newer one. A column absent from a given year is null
    for that year's rows, which is the honest representation of it.
    """
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for column in row:
            if column not in seen:
                seen.add(column)
                columns.append(column)

    types = {}
    for column in columns:
        sample = next((r.get(column) for r in rows if r.get(column) is not None), None)
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
            tuple(
                json.dumps(r.get(c)) if isinstance(r.get(c), list | dict) else r.get(c)
                for c in columns
            )
            for r in rows
        ],
    )


def fetch_one(job: tuple) -> dict:
    """One endpoint-year, carrying its own failure rather than raising.

    A year that does not exist is not an error — asking for it and recording
    the empty answer is how the database learns where a series stops.
    """
    table, path, year, area = job
    try:
        rows, url = fetch(path, year)
        return {"table": table, "year": year, "area": area, "rows": rows, "url": url, "error": None}
    except urllib.error.HTTPError as error:
        return {
            "table": table,
            "year": year,
            "area": area,
            "rows": [],
            "url": "",
            "error": f"HTTP {error.code}",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument(
        "--years",
        type=int,
        default=None,
        help="Trim every range to this many most recent years (for a quick rebuild).",
    )
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

    # One row per endpoint-year *attempted*, including the ones that came back
    # empty. The empty rows are the point: they are how `db.series_ends` can
    # tell a survey that stopped from an ingest that has not caught up, without
    # anyone maintaining a flag by hand.
    connection.execute("DROP TABLE IF EXISTS ingest_runs")
    connection.execute(
        """
        CREATE TABLE ingest_runs (
            table_name  TEXT NOT NULL,
            area        TEXT,
            year        INTEGER NOT NULL,
            url         TEXT NOT NULL,
            rows        INTEGER NOT NULL,
            schools     INTEGER NOT NULL,
            fetched_at  TEXT NOT NULL,
            question    TEXT
        )
        """
    )

    jobs = []
    for table, (path, years, area) in ENDPOINTS.items():
        wanted = sorted(years)[-args.years :] if args.years else list(years)
        jobs.extend((table, path, year, area) for year in wanted)

    print(f"Fetching {len(jobs)} endpoint-years...\n")
    # The API has no rate limiting and serves responses as immutable, so the
    # years are fetched together. Writing stays on this thread; SQLite
    # connections are not shared across threads.
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(fetch_one, jobs))

    by_table = defaultdict(list)
    for result in results:
        by_table[result["table"]].append(result)

    for table in ENDPOINTS:
        runs = sorted(by_table[table], key=lambda r: r["year"])
        rows = [row for run in runs for row in run["rows"]]

        if not rows:
            print(f"  {table:<34} NO DATA in any year — table not created")
            continue

        create_table(connection, table, rows)

        for run in runs:
            if run["error"]:
                # A transport failure says nothing about whether the survey
                # covers this year, and recording it as an empty year would
                # make the app claim the series had ended.
                print(f"  {table:<34} {run['year']}  {run['error']} — not recorded")
                continue
            covered = len({r["unitid"] for r in run["rows"]})
            connection.execute(
                "INSERT INTO ingest_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    table,
                    run["area"],
                    run["year"],
                    run["url"],
                    len(run["rows"]),
                    covered,
                    datetime.now(UTC).isoformat(),
                    AREAS.get(run["area"], ""),
                ),
            )

        live = [run["year"] for run in runs if run["rows"]]
        empty = [run["year"] for run in runs if not run["rows"] and not run["error"]]
        span = f"{min(live)}-{max(live)}" if len(live) > 1 else str(live[0])
        tail = f"  (empty: {min(empty)}+)" if empty and min(empty) > max(live) else ""
        print(f"  {table:<34} {span:<10} {len(rows):>6} rows  {len(live):>2} yrs{tail}")

    connection.commit()
    connection.close()
    print(f"\nWrote {args.db}")


if __name__ == "__main__":
    main()
