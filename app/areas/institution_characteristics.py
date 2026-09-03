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
share one range (2021-2024). `completions_cip_2` was ingested on a narrower
window (2022-2023, see `scripts/import_ipeds.py`) and does not line up with
that range — asking it for, say, 2024 would silently return nothing. It
always shows its own newest year instead, labelled separately in the
template, rather than going blank whenever the reference table's year
outruns it.

**Everything else backfills to each school's own most recent good year,
rather than going blank.** IPEDS has not finished filling in the newest
years of `directory` and `institutional_characteristics` — checked directly
against this sample: `directory` reports 25/25 schools in 2021-2022, 18/25 in
2023, 12/25 in 2024; `institutional_characteristics` reports 25/25 in every
year except 2023, where it drops to 17/25. A row that exists but carries no
city (or no calendar system) is IPEDS's placeholder for "not received yet,"
not a school without a location.

The considered alternative was pulling a second, non-IPEDS source — a
university's street address does not stop being true because a federal
survey is running behind. Rejected: every one of these 25 schools already
has a complete, IPEDS-sourced row in 2021 or 2022 (checked: none has zero
good years), so a second source would be re-deriving facts already sitting
in this database, on a classification scheme (control type, locale) that
would not agree with IPEDS's own by construction. Backfilling to the same
school's nearest earlier good year keeps one source of truth and costs
nothing when a table is fully current, which is most of them, most years.

Labelled where it matters, silent where it doesn't. Calendar system (a real,
if rare, policy change) gets a small `(IPEDS YYYY)` note plus a page-level
notice when backfilled. `directory` (location, control, size) and housing
backfill without either: none of those meaningfully change year to year for
a school that already exists, and a freshness caveat on a fact that cannot
go stale is a notice nobody reads. `directory_year` and `directory_is_stale`
stay on each row regardless — cheap to keep, useful if that judgment call
ever needs revisiting — the template just doesn't show them.

**Housing backfills on its own schedule, separately from calendar and
religious affiliation, even though all three live in the same
`institutional_characteristics` row.** Checked directly: calendar and
religious affiliation report together (17/25 schools in 2023, 25/25 every
other year), but `oncampus_housing` follows a different pattern and drops to
0 of 25 in 2024 — the exact year calendar is fully reported. Grouping them
under one "good year" check, as an earlier version of this module did, meant
every school's housing showed as unreported the moment the newest year had
no housing data at all, even though the rest of that row was fine.
"""

import sqlite3

import polars as pl

from app.notices import Notice, coverage_notices
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

# IPEDS's usual missing/not-applicable sentinels. `oncampus_housing` in this
# sample only ever takes the values 1 (yes) or -1 (not reported) — no school
# here reports 0 — so `== 1` alone silently reads -1 as "no". Caught by 2024,
# where four of these 25 schools report -1 for both `oncampus_housing` and
# `dormitory_capacity` while every other field on the same row is real data;
# treating -1 as false rendered Caltech, MIT and Stanford as having no
# on-campus housing, which is absurd on its face for any of them.
SENTINELS = {-1, -2, -3}

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

# No `{year}` filter: these three back off to a school's most recent good
# year when the requested one is not yet reported, so each fetches every
# year and `_by_unitid_backfilled` picks per school. The `WHERE` clause is
# what "good" means for that table — the one column that stands for "this
# row has real data," not IPEDS's placeholder for "not received yet."
DIRECTORY_QUERY = """
    SELECT unitid, year, city, state_abbr, url_school, inst_control,
           urban_centric_locale, inst_size, latitude, longitude
    FROM directory
    WHERE city IS NOT NULL
"""

CHARACTERISTICS_QUERY = """
    SELECT unitid, year, calendar_system, religious_affiliation
    FROM institutional_characteristics
    WHERE calendar_system IS NOT NULL
"""

# Housing backfills separately from calendar/religious affiliation — checked
# directly: calendar and religious affiliation report together (17/25 in
# 2023, 25/25 every other year), but `oncampus_housing` follows its own
# schedule and drops to 0/25 in 2024 while calendar that same year is fully
# reported. Grouping them would have shown every school's housing as blank
# in the newest year even though calendar was fine.
HOUSING_QUERY = f"""
    SELECT unitid, year, oncampus_housing, dormitory_capacity
    FROM institutional_characteristics
    WHERE oncampus_housing NOT IN {tuple(SENTINELS)}
"""

RATIO_QUERY = """
    SELECT unitid, year, student_faculty_ratio
    FROM student_faculty_ratio
    WHERE student_faculty_ratio IS NOT NULL
"""

# `completions_cip_2` runs on its own window (see the module docstring) and
# always shows its own newest year, so it keeps a `{year}` filter rather than
# backfilling like the three above.
FIELDS_QUERY = """
    SELECT unitid, cipcode, SUM(awards) AS awards
    FROM completions_cip_2
    WHERE race = 99 AND sex = 99 AND majornum = 1 AND year = {fields_year}
    GROUP BY unitid, cipcode
"""

# No `year` column at all, let alone one to filter or backfill on — Wikidata
# has whatever is on the page right now, not an annual survey's worth of
# history. Joined on `wdt:P1771`, Wikidata's own IPEDS-UNITID property, by
# `scripts/import_ipeds.py`'s `fetch_wikidata_trivia`.
TRIVIA_QUERY = """
    SELECT unitid, motto_la, motto_en, founded_year
    FROM wikidata_trivia
"""


def load(conn: sqlite3.Connection, schools: list[School], year: int) -> dict:
    """One reference row per school, plus a locator map and top fields of study."""
    unitids = [s.unitid for s in schools]
    directory = _by_unitid_backfilled(conn, DIRECTORY_QUERY, unitids, year)
    characteristics = _by_unitid_backfilled(conn, CHARACTERISTICS_QUERY, unitids, year)
    housing_data = _by_unitid_backfilled(conn, HOUSING_QUERY, unitids, year)
    ratios = _by_unitid_backfilled(conn, RATIO_QUERY, unitids, year)
    fields, fields_year = _top_fields(conn, unitids)
    trivia = _by_unitid(conn, TRIVIA_QUERY, unitids)

    rows = []
    backfilled = []
    for school in schools:
        d = directory.get(school.unitid, {})
        c = characteristics.get(school.unitid, {})
        h = housing_data.get(school.unitid, {})
        f = fields.get(school.unitid, {})
        r = ratios.get(school.unitid, {})
        t = trivia.get(school.unitid, {})

        religious = c.get("religious_affiliation")
        religious_label = (
            "None"
            if religious == NOT_RELIGIOUS
            else RELIGIOUS.get(religious, f"Code {religious}")
            if religious is not None
            else None
        )

        # None (not-reported) rather than False: `oncampus_housing` has no
        # real 0 in this sample, only 1 or the sentinel -1, so treating the
        # sentinel as falsy renders a school with unreported housing as
        # having none. See SENTINELS's comment. `h` is already backfilled to
        # a year housing was actually reported (see HOUSING_QUERY) and, like
        # location, shown silently — a bed count is as slow-changing as an
        # address.
        housing = h.get("oncampus_housing") == 1 if h else None
        dormitory_capacity = h.get("dormitory_capacity")
        if dormitory_capacity in SENTINELS:
            dormitory_capacity = None

        directory_year = d.get("year")
        characteristics_year = c.get("year")
        # Only `institutional_characteristics` earns a staleness mark.
        # `directory`'s fields — location, control, size — do not meaningfully
        # change year to year for an existing school, so backfilling them is
        # silent; calling attention to it every time would be a notice nobody
        # reads. Calendar system is a real, if rare, policy change, so it
        # still gets one.
        if characteristics_year is not None and characteristics_year != year:
            backfilled.append((school, characteristics_year))

        motto = _motto(t.get("motto_la"), t.get("motto_en"))

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
                "directory_year": directory_year,
                "directory_is_stale": directory_year is not None and directory_year != year,
                "calendar": _label(CALENDAR, c.get("calendar_system")),
                "housing": housing,
                "dormitory_capacity": dormitory_capacity,
                "characteristics_year": characteristics_year,
                "characteristics_is_stale": (
                    characteristics_year is not None and characteristics_year != year
                ),
                "religious": religious_label,
                "student_faculty_ratio": r.get("student_faculty_ratio"),
                "top_fields": f.get("top", []),
                "founded_year": t.get("founded_year"),
                "motto": motto,
            }
        )

    # After backfilling, a school is only ever truly missing here if it has
    # no good year at all for a given table — which none of these 25 do (see
    # the module docstring), but a widened sample might.
    missing_all = [row["school"] for row in rows if not row["city"]]

    return {
        "rows": rows,
        "map": _map(rows),
        "fields_year": fields_year,
        "notices": (
            coverage_notices(missing_all, [], subject=SUBJECT)
            + _staleness_notice(backfilled, year)
        ),
    }


def _staleness_notice(backfilled: list[tuple[School, int]], year: int) -> list[Notice]:
    """One info notice naming which schools are shown from an earlier year.

    A separate notice from `coverage_notices`, which is written for a school
    reporting nothing at all — this one is for a school reporting *something*,
    just not yet for `year`. Conflating the two would call a one-year-old
    location a "gap in the federal data," which overstates it.
    """
    if not backfilled:
        return []
    names = sorted({school.short for school, _ in backfilled})
    years = sorted({y for _, y in backfilled})
    who = names[0] if len(names) == 1 else ", ".join(names[:-1]) + f" and {names[-1]}"
    when = str(years[0]) if len(years) == 1 else f"{years[0]}–{years[-1]}"
    return [
        Notice(
            "info",
            f"IPEDS has not finished publishing {year} data for {who}. Fields marked "
            f"(IPEDS {when}) below are that school's most recent report instead — "
            f"still accurate for facts like location that rarely change, dated for "
            f"anything that might not be.",
        )
    ]


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


def _by_unitid_backfilled(
    conn: sqlite3.Connection, query: str, unitids: list[int], year: int
) -> dict:
    """Each school's row for `year`, or its nearest earlier good year instead.

    `query` already filters to rows with real data (see the module docstring)
    and carries no `{year}` — every good year for these schools comes back,
    and this picks one per school: `year` itself if that school has it,
    otherwise the closest year at or before it, otherwise (only possible if a
    school's *first* good year is after `year`) the closest one after. The
    chosen row keeps its own `year` column so the caller can tell whether it
    backfilled and say so.
    """
    frame = pl.read_database(query, conn).filter(pl.col("unitid").is_in(unitids))

    by_school: dict[int, list[dict]] = {}
    for r in frame.to_dicts():
        by_school.setdefault(r["unitid"], []).append(r)

    result = {}
    for unitid, group in by_school.items():
        group.sort(key=lambda r: r["year"])
        exact = next((r for r in group if r["year"] == year), None)
        before = [r for r in group if r["year"] <= year]
        result[unitid] = exact or (before[-1] if before else group[0])
    return result


def _by_unitid(conn: sqlite3.Connection, query: str, unitids: list[int]) -> dict:
    """One row per school, no year involved — for `wikidata_trivia`, which
    has none to filter or backfill on. See that query's own comment."""
    frame = pl.read_database(query, conn).filter(pl.col("unitid").is_in(unitids))
    return {r["unitid"]: r for r in frame.to_dicts()}


def _motto(latin: str | None, english: str | None) -> str | None:
    """Both, when Wikidata has both — a translation alone is only half the
    fact, and the Latin alone leaves most readers guessing. Latin only is
    marked as such; English only needs no mark, it reads as a motto either
    way."""
    if latin and english:
        return f"{latin} — {english}"
    if english:
        return english
    if latin:
        return f"{latin} (Latin)"
    return None


# `directory` is the anchor table (TABLE, above), so a usable row there is
# what "renderable" means: everything else in this area degrades gracefully
# to a dash when absent, but no city means no location or map dot. Every year
# from a school's own first good one onward counts as covered, since that is
# exactly what `_by_unitid_backfilled` can produce something for — a school
# whose first good year is 2022 is not claimed as covered in 2021.
def coverage(conn: sqlite3.Connection) -> set[tuple[int, int]]:
    """Every (unitid, year) this area can render, for the year picker."""
    good = conn.execute("SELECT unitid, year FROM directory WHERE city IS NOT NULL").fetchall()
    all_years = {row[0] for row in conn.execute("SELECT DISTINCT year FROM directory")}

    first_good: dict[int, int] = {}
    for unitid, yr in good:
        first_good[unitid] = min(first_good.get(unitid, yr), yr)

    return {
        (unitid, year)
        for unitid, first in first_good.items()
        for year in all_years
        if year >= first
    }


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


def highlights(context: dict) -> list[str]:
    """One line naming the school with the most personal attention here.

    Optional, like `trend`/`coverage` elsewhere — see financial_aid.highlights
    for the shared convention.
    """
    rows = [row for row in context.get("rows", []) if row.get("student_faculty_ratio")]
    if len(rows) < 2:
        return []
    smallest = min(rows, key=lambda row: row["student_faculty_ratio"])
    return [
        f"{smallest['school'].short} has the most personal attention here — "
        f"{smallest['student_faculty_ratio']} students per faculty member."
    ]
