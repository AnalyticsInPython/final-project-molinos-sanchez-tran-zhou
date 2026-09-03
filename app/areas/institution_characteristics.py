"""Institution characteristics — who and where a school is.

Reference data, not analysis: a table, per SCOPE.md's own note not to force a
chart onto facts that don't compute into anything. The only work this module
does is translate IPEDS's numeric codes into words a family would say —
`urban_centric_locale=33` means nothing on a page; "Town: remote" does.

The codes below are the standard, stable IPEDS codebook (verified here
against facts about these specific schools that don't come from IPEDS at
all: Caltech, Dartmouth, Northwestern, Stanford, UChicago and UCLA all show
`calendar_system=2`, and all six are well known to run on the quarter
system; MIT alone shows `4`, and MIT's "4-1-4" calendar — two four-month
terms bracketing its January Independent Activities Period — is exactly
what that code names). An unrecognised code is shown as-is rather than
guessed at, since the sample will eventually widen past these 25 schools.

`religious_affiliation` deserves its own note: **`-2` here is a real answer,
not a missing one.** Every other IPEDS column in this project uses -1/-2/-3
as sentinels meaning "not reported." This column overloads -2 for "does not
apply" — the school does not have a religious affiliation — and that is
different from not knowing. We render it as "None" for that reason, not as
the em-dash the rest of the app uses for a true unknown.

Two more traps, both in the "top fields of study" figure, computed from
`completions_cip_2` (majornum=1 so a double major isn't counted twice,
race=99/sex=99 for the same reason sex=99 is the total everywhere else in
this project):

**`cipcode = 990000` is not a field.** It is a grand-total pseudo-row the
API adds per school — checked here by summing every other row and getting
exactly that number back, for more than one school. Rank it first and every
school's "top field" is "everything," which is not a finding.

**A raw award count favours a big school over a focused one.** Fifty
computer-science degrees is most of a 300-student college and a rounding
error at a 2,000-a-year one. We show each field's share of that school's
total awards, not the count, so five schools sit on the same scale.

**Top fields runs on its own year, decoupled from everything else on the
page.** `directory`, `institutional_characteristics` and `student_faculty_ratio`
share one range (2021-2024) and are filtered on the `year` this module is
asked to render. `completions_cip_2` was ingested on a narrower window
(2022-2023, see `scripts/import_ipeds.py`) and does not line up with that
range — asking it for, say, 2024 would silently return nothing. It always
shows its own newest year instead, labelled separately in the template,
rather than going blank whenever the reference table's year outruns it.
"""

import sqlite3

import polars as pl

from app.notices import coverage_notices
from app.schools import School

KEY = "institution_characteristics"
TITLE = "Institution characteristics"
QUESTION = "Who and where is this school?"
SUBJECT = "institution characteristics"
TABLE = "directory"
SOURCE = "IPEDS"
TEMPLATE = "areas/institution_characteristics.html"

# Drawn on a 24x24 grid, stroked in the caller's colour. A building: this area
# is about what a school institutionally *is*, not what it costs or offers.
ICON = '<path d="M4 21V9l8-5 8 5v12"/><path d="M9 21v-7h6v7"/>'

CONTROL = {
    1: "Public",
    2: "Private nonprofit",
    3: "Private for-profit",
}

# NCES's 12-value locale scheme: a city/suburb/town/rural axis crossed with a
# large/mid/small (or fringe/distant/remote) size axis.
LOCALE = {
    11: "City: large",
    12: "City: midsize",
    13: "City: small",
    21: "Suburb: large",
    22: "Suburb: midsize",
    23: "Suburb: small",
    31: "Town: fringe",
    32: "Town: distant",
    33: "Town: remote",
    41: "Rural: fringe",
    42: "Rural: distant",
    43: "Rural: remote",
}

# The 4-year breakpoints. IPEDS uses a different scale for 2-year schools,
# which this project does not sample.
SIZE = {
    1: "Under 1,000",
    2: "1,000–4,999",
    3: "5,000–9,999",
    4: "10,000–19,999",
    5: "20,000 and above",
}

CALENDAR = {
    1: "Semester",
    2: "Quarter",
    3: "Trimester",
    4: "4-1-4",
    5: "Differs by program",
    6: "Continuous",
    7: "Other academic year",
}

# Only the codes this sample actually contains. IPEDS's full RELAFFIL list
# runs past fifty specific denominations; guessing at ones we haven't seen a
# real school confirm would be worse than an honest fallback.
RELIGIOUS = {
    30: "Roman Catholic",
    71: "United Methodist",
}
NOT_RELIGIOUS = -2

# The federal CIP taxonomy's 2-digit families, by the numeric prefix on
# `cipcode` (110000 -> family 11). Stable and government-standard, so an
# unmapped family is more likely a data-widening event than a typo — it
# falls back to its number rather than a guessed name.
CIP_FAMILY = {
    1: "Agriculture and related sciences",
    3: "Natural resources and conservation",
    4: "Architecture and related services",
    5: "Area, ethnic, and gender studies",
    9: "Communication and journalism",
    10: "Communications technologies",
    11: "Computer and information sciences",
    12: "Personal and culinary services",
    13: "Education",
    14: "Engineering",
    15: "Engineering technologies",
    16: "Foreign languages and linguistics",
    19: "Family and consumer sciences",
    22: "Legal professions and studies",
    23: "English language and literature",
    24: "Liberal arts and general studies",
    25: "Library science",
    26: "Biological and biomedical sciences",
    27: "Mathematics and statistics",
    29: "Military technologies",
    30: "Multi/interdisciplinary studies",
    31: "Parks, recreation, and fitness studies",
    38: "Philosophy and religious studies",
    39: "Theology and religious vocations",
    40: "Physical sciences",
    41: "Science technologies/technicians",
    42: "Psychology",
    43: "Homeland security and law enforcement",
    44: "Public administration and social services",
    45: "Social sciences",
    50: "Visual and performing arts",
    51: "Health professions",
    52: "Business, management, and marketing",
    54: "History",
}

# Not a field — the grand-total row this API returns alongside every real
# one. See the module docstring. **Two codes, not one**: verified by summing
# every other cipcode and checking it against each candidate, per school, for
# every ingested year — `990000` is the total through 2022, and IPEDS
# switched to `99` in 2023 (checked against all 25 schools: `990000` sums to
# zero rows for 2023, `99` matches the real-fields sum exactly, for every one
# of them). Neither code is guaranteed to be the one a year past 2023 uses.
TOTAL_CIPS = {99, 990000}

# The year filter is not optional: `directory`, `institutional_characteristics`
# and `student_faculty_ratio` now hold 2021-2024. `{year}` is interpolated
# through int(), so it cannot carry anything but a number.
DIRECTORY_QUERY = """
    SELECT unitid, city, state_abbr, url_school, inst_control, urban_centric_locale,
           inst_size, latitude, longitude
    FROM directory
    WHERE year = {year}
"""

CHARACTERISTICS_QUERY = """
    SELECT unitid, calendar_system, oncampus_housing, dormitory_capacity, religious_affiliation
    FROM institutional_characteristics
    WHERE year = {year}
"""

# No `{year}` filter — completions_cip_2 runs on its own window and always
# shows its own newest year. See the module docstring.
FIELDS_QUERY = """
    SELECT unitid, cipcode, SUM(awards) AS awards
    FROM completions_cip_2
    WHERE race = 99 AND sex = 99 AND majornum = 1 AND year = {fields_year}
    GROUP BY unitid, cipcode
"""

RATIO_QUERY = """
    SELECT unitid, student_faculty_ratio
    FROM student_faculty_ratio
    WHERE year = {year}
"""


def load(conn: sqlite3.Connection, schools: list[School], year: int) -> dict:
    """One reference row per school, plus a locator map and top fields of study."""
    unitids = [s.unitid for s in schools]
    directory = _by_unitid(conn, DIRECTORY_QUERY.format(year=int(year)), unitids)
    characteristics = _by_unitid(
        conn, CHARACTERISTICS_QUERY.format(year=int(year)), unitids
    )
    fields, fields_year = _top_fields(conn, unitids)
    ratios = _by_unitid(conn, RATIO_QUERY.format(year=int(year)), unitids)

    rows = []
    for school in schools:
        d = directory.get(school.unitid, {})
        c = characteristics.get(school.unitid, {})
        f = fields.get(school.unitid, {})
        r = ratios.get(school.unitid, {})

        religious = c.get("religious_affiliation")
        religious_label = (
            "None"
            if religious == NOT_RELIGIOUS
            else RELIGIOUS.get(religious, f"Code {religious}")
            if religious is not None
            else None
        )

        rows.append(
            {
                "school": school,
                "city": d.get("city"),
                "state": d.get("state_abbr"),
                "url": _https(d.get("url_school")),
                "lat": d.get("latitude"),
                "lon": d.get("longitude"),
                "control": _label(CONTROL, d.get("inst_control")),
                "locale": _label(LOCALE, d.get("urban_centric_locale")),
                "size": _label(SIZE, d.get("inst_size")),
                "calendar": _label(CALENDAR, c.get("calendar_system")),
                "housing": c.get("oncampus_housing") == 1,
                "dormitory_capacity": c.get("dormitory_capacity"),
                "religious": religious_label,
                "student_faculty_ratio": r.get("student_faculty_ratio"),
                "top_fields": f.get("top", []),
            }
        )

    # A directory row that exists but carries no city is not coverage — IPEDS
    # is still filling in the newest years (12 of 25 schools have a usable
    # 2024 row as of this ingest, 25 of 25 for 2021-2022), and a dict with
    # every value None is still a truthy dict, so this checks the one field
    # that stands for "this row has real data" rather than mere presence.
    missing_all = [row["school"] for row in rows if not row["city"]]
    missing_some = [
        row["school"]
        for row in rows
        if row["city"]
        and (not characteristics.get(row["school"].unitid) or not ratios.get(row["school"].unitid))
    ]

    return {
        "rows": rows,
        "map": _map(rows),
        "fields_year": fields_year,
        "notices": coverage_notices(missing_all, missing_some, subject=SUBJECT),
    }


def _top_fields(conn: sqlite3.Connection, unitids: list[int]) -> tuple[dict[int, dict], int | None]:
    """Per school: the three fields with the most completions, by share.

    On `completions_cip_2`'s own newest year — see the module docstring for
    why that is not necessarily the year the rest of this area is showing.
    """
    fields_year = conn.execute("SELECT MAX(year) FROM completions_cip_2").fetchone()[0]
    if fields_year is None:
        return {}, None

    frame = pl.read_database(FIELDS_QUERY.format(fields_year=int(fields_year)), conn).filter(
        pl.col("unitid").is_in(unitids)
    )

    by_school: dict[int, list[dict]] = {}
    for r in frame.to_dicts():
        by_school.setdefault(r["unitid"], []).append(r)

    result = {}
    for unitid, group in by_school.items():
        total = next((g["awards"] for g in group if g["cipcode"] in TOTAL_CIPS), None)
        fields = sorted(
            (g for g in group if g["cipcode"] not in TOTAL_CIPS and g["awards"]),
            key=lambda g: g["awards"],
            reverse=True,
        )
        top = [
            {
                "label": CIP_FAMILY.get(g["cipcode"] // 10000, f"CIP {g['cipcode'] // 10000:02d}"),
                "awards": g["awards"],
                "share_pct": round(100 * g["awards"] / total) if total else None,
            }
            for g in fields[:3]
        ]
        result[unitid] = {"total": total, "top": top}
    return result, fields_year


def _map(rows: list[dict]) -> dict | None:
    """Each school's raw coordinates, for the client-side map to place and fit.

    No projection math here: the template hands lat/lon straight to the
    MapTiler SDK, which does its own projection and its own `fitBounds` — a
    second, slightly-different implementation of the same job would be a
    second place for it to be wrong.
    """
    points = [
        (row, row["lat"], row["lon"])
        for row in rows
        if row["lat"] is not None and row["lon"] is not None
    ]
    if not points:
        return None

    return {
        "dots": [
            {
                "name": row["school"].short,
                "color": row["school"].color,
                "lat": lat,
                "lon": lon,
            }
            for row, lat, lon in points
        ]
    }


def _by_unitid(conn: sqlite3.Connection, query: str, unitids: list[int]) -> dict:
    frame = pl.read_database(query, conn).filter(pl.col("unitid").is_in(unitids))
    return {r["unitid"]: r for r in frame.to_dicts()}


# `directory` is the anchor table (TABLE, above), so a usable row there is
# what "renderable" means: everything else in this area degrades gracefully
# to a dash when absent, but no city means no location or map dot. `city IS
# NOT NULL` matters more than it looks — IPEDS has not finished filling in
# the newest years: 2021-2022 report all 25 schools, 2023 reports 18, 2024
# reports 12. A row with every column null is still a row.
COVERAGE_QUERY = "SELECT DISTINCT unitid, year FROM directory WHERE city IS NOT NULL"


def coverage(conn: sqlite3.Connection) -> set[tuple[int, int]]:
    """Every (unitid, year) this area can render, for the year picker."""
    return {(row[0], row[1]) for row in conn.execute(COVERAGE_QUERY)}


def _label(table: dict, code: int | None) -> str | None:
    """The code's name, or the code itself if it's outside what we've mapped."""
    if code is None:
        return None
    return table.get(code, f"Unknown ({code})")


def _https(url: str | None) -> str | None:
    """IPEDS stores school URLs without a scheme — `www.brown.edu/`, not a link."""
    if not url:
        return None
    return url if url.startswith("http") else f"https://{url}"
