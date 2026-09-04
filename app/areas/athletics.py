"""Athletics — how big a part of this place a varsity sport is.

The area exists for one number: **what share of the student body plays a
varsity sport**. It separates schools harder than anything else in this
project. Across the sample it runs from 2.1% at UCLA to 26.6% at Caltech, a
twelvefold range, where graduation rates over the same 25 schools span 91 to 98
and say almost nothing. For someone being recruited, that is the difference
between a campus where one person in four is on a roster and one where it is
one in fifty.

None of this is IPEDS. IPEDS carries membership flags — `member_ncaa`, a
conference number — and no participation or money whatsoever. Everything here
comes from EADA (see `scripts/import_eada.py`).

Two traps, and both return a number that looks fine:

**Count athletes once.** EADA publishes `PARTIC_*` per sport and
`UNDUP_CT_PARTIC_*` per person. A cross-country runner who also runs track is
in the first twice. Using it would report Furman as one student in five rather
than one in six.

**A school reporting $0 of athletic aid is telling the truth.** Of 2,037
institutions the column is 1,366 positive, 671 exactly zero and never null. The
zeros are Division III and the Ivy League, neither of which awards athletic
scholarships at all. Treating $0 as missing would hide the single most useful
fact an Ivy can tell a recruit: the money here is need-based or nothing.
"""

import sqlite3

import polars as pl

from app.db import series_ends, years_available
from app.format import join_names, money, one_in, percent, times
from app.notices import coverage_notices, series_notices
from app.schools import School
from app.trend import chart as line_chart

KEY = "athletics"
TITLE = "Athletics"
QUESTION = "If I play a sport, how big a part of this place is that?"
SUBJECT = "athletics"
TABLE = "eada_institutions"
TEMPLATE = "areas/athletics.html"
# Not IPEDS. The year chip says so, because a reader who checks a figure
# against IPEDS and cannot find it has been misled by our own label.
SOURCE = "EADA"

# A figure mid-stride.
ICON = (
    '<circle cx="13.5" cy="4.5" r="2"/>'
    '<path d="M12 21l1.5-5.5L10 13l1-5 3.5 2.5 3 .5"/>'
    '<path d="M11 8L7.5 9 6 12"/><path d="M13.5 15.5L17 19"/>'
)

QUERY = """
    SELECT unitid,
           EFTotalCount            AS enrolled,
           UNDUP_CT_PARTIC_MEN     AS men,
           UNDUP_CT_PARTIC_WOMEN   AS women,
           STUDENTAID_TOTAL        AS aid,
           STUDENTAID_MEN          AS aid_men,
           STUDENTAID_WOMEN        AS aid_women,
           classification_name     AS division
    FROM eada_institutions
    WHERE year = {year}
"""

TREND_QUERY = """
    SELECT year, unitid,
           EFTotalCount          AS enrolled,
           UNDUP_CT_PARTIC_MEN   AS men,
           UNDUP_CT_PARTIC_WOMEN AS women,
           STUDENTAID_TOTAL      AS aid
    FROM eada_institutions
    WHERE year BETWEEN {first} AND {last}
"""

COVERAGE_QUERY = """
    SELECT DISTINCT unitid, year
    FROM eada_institutions
    WHERE EFTotalCount > 0
      AND (UNDUP_CT_PARTIC_MEN + UNDUP_CT_PARTIC_WOMEN) > 0
"""


def _rows(frame: pl.DataFrame, schools: list[School]) -> list[dict]:
    by_id = {r["unitid"]: r for r in frame.to_dicts()}
    out = []
    for school in schools:
        record = by_id.get(school.unitid)
        if not record or not record.get("enrolled"):
            out.append({"school": school, "enrolled": None, "athletes": None,
                        "share": None, "aid": None, "per_athlete": None,
                        "men": None, "women": None, "division": None})
            continue
        athletes = (record.get("men") or 0) + (record.get("women") or 0)
        aid = record.get("aid")
        out.append({
            "school": school,
            "enrolled": record["enrolled"],
            "athletes": athletes,
            "men": record.get("men"),
            "women": record.get("women"),
            "share": athletes / record["enrolled"] if athletes else None,
            "aid": aid,
            # Kept at zero rather than None when a school awards none: the
            # distinction between "no athletic money" and "did not report" is
            # the point.
            "per_athlete": (aid / athletes) if aid is not None and athletes else None,
            "division": record.get("division"),
        })
    return out


def year_meaning(conn: sqlite3.Connection, year: int, trend: bool = False) -> str:
    if trend:
        return "Each year is an EADA reporting year: 2024 means the 2024–25 report."
    return f"Figures labelled {year} are from EADA's {year}–{str(year + 1)[-2:]} reporting year."


def load(conn: sqlite3.Connection, schools: list[School], year: int) -> dict:
    """Athlete share, the aid behind it, and who it goes to."""
    frame = pl.read_database(QUERY.format(year=int(year)), conn)
    if frame.is_empty():
        return {"rows": [], "share_chart": None, "aid_chart": None,
                "notices": coverage_notices(list(schools), [], subject=SUBJECT)}

    rows = _rows(frame, schools)
    missing = [r["school"] for r in rows if r["share"] is None]

    return {
        "rows": rows,
        "share_chart": _bars(rows, "share", fmt=percent, lead=_lead(rows)),
        "aid_chart": _bars(rows, "per_athlete", fmt=money),
        "notices": coverage_notices(missing, [], subject=SUBJECT),
    }


def _lead(rows: list[dict]) -> set[int]:
    """The school the headline names: the largest share of it on a roster."""
    shares = [row for row in rows if row["share"] is not None]
    if len(shares) < 2:
        return set()
    return {max(shares, key=lambda row: row["share"])["school"].unitid}


def _bars(rows: list[dict], key: str, *, fmt, lead: set[int] | None = None) -> dict | None:
    """One bar per school in its own colour, widest first.

    `lead` is the school the card's headline names, marked so the template can
    draw the other bars faint — see the `.headline` note in base.html. No lead
    marks every bar instead of none: a page with one school has no sentence
    naming anybody, and drawing its only bar faint would say the opposite.
    """
    entries = sorted(
        (r for r in rows if r[key] is not None), key=lambda r: r[key], reverse=True
    )
    if not entries:
        return None

    width, row_h = 640, 26
    label_w, value_w = 150, 74
    top, bottom = 10, 10
    plot_w = width - label_w - value_w
    largest = max(r[key] for r in entries) or 1

    bars = []
    for i, row in enumerate(entries):
        y = top + row_h * i + row_h / 2
        # A zero-width bar still needs to be visible, because zero is a real
        # answer here and an empty row reads as missing data.
        length = plot_w * (row[key] / largest)
        bars.append({
            "name": row["school"].short,
            "color": row["school"].color,
            "y": round(y - 7, 1),
            "text_y": round(y + 4, 1),
            "width": round(max(length, 2), 1),
            "label_x": round(label_w + max(length, 2) + 8, 1),
            "value": fmt(row[key]),
            "lead": not lead or row["school"].unitid in lead,
        })

    return {"width": width, "height": top + row_h * len(entries) + bottom,
            "bars": bars, "label_x": label_w - 10, "plot_x": label_w}


def trend(conn: sqlite3.Connection, schools: list[School], years: list[int]) -> dict:
    """Athlete share and aid per athlete across the requested window."""
    # Where the survey itself starts and stops, so a year past the end of it is
    # not read as a hole in a school's reporting. EADA begins in 2019 here, and
    # a window opened for an IPEDS area starts four years earlier than that.
    published = years_available(conn, TABLE)
    stopped = series_ends(conn, TABLE)

    frame = pl.read_database(
        TREND_QUERY.format(first=int(min(years)), last=int(max(years))), conn
    )
    if frame.is_empty():
        return {"panels": [],
                "notices": series_notices(schools, years, set(), subject=SUBJECT,
                                          source=SOURCE, published=published, ends=stopped)}

    frame = frame.filter(pl.col("unitid").is_in([s.unitid for s in schools]))
    records = frame.to_dicts()

    share, per_athlete = {}, {}
    seen = set()
    for r in records:
        athletes = (r.get("men") or 0) + (r.get("women") or 0)
        if not r.get("enrolled") or not athletes:
            continue
        key = (r["unitid"], r["year"])
        seen.add(key)
        share[key] = athletes / r["enrolled"]
        if r.get("aid") is not None:
            per_athlete[key] = r["aid"] / athletes

    panels = [
        {"title": "Share of the student body playing a varsity sport",
         "subtitle": "Athletes counted once, however many teams they are on.",
         "chart": line_chart(schools, years, share, fmt=percent)},
        {"title": "Athletic aid per athlete",
         "subtitle": "Zero is a real answer: Division III and the Ivy League award none.",
         "chart": line_chart(schools, years, per_athlete, fmt=money)},
    ]

    return {
        "panels": [p for p in panels if p["chart"]],
        "notices": series_notices(schools, years, seen, subject=SUBJECT, source=SOURCE,
                                  published=published, ends=stopped),
    }


def coverage(conn: sqlite3.Connection) -> set[tuple[int, int]]:
    """Every (unitid, year) this area can render, for the year picker."""
    return {(row[0], row[1]) for row in conn.execute(COVERAGE_QUERY)}


def headline(context: dict, cut: dict | None = None) -> str | None:
    """The card's finding, in a sentence: athlete share, and the $0 that is real.

    Two facts, because the second one is the trap this module exists to keep
    out of the page. A school reporting no athletic aid has told the truth —
    Division III awards none — so the sentence says which schools those are
    and why, rather than leaving a bar at zero to read as missing data.

    This survey carries no breakdowns, so `cut` is always None here.
    """
    shares = [row for row in context.get("rows", []) if row["share"] is not None]
    if len(shares) < 2:
        return None

    most = max(shares, key=lambda row: row["share"])
    least = min(shares, key=lambda row: row["share"])
    phrase = one_in(most["share"])
    plays = (
        f"{phrase[0].upper()}{phrase[1:]} {most['school'].short} undergrads plays a varsity sport"
        if phrase
        else f"{percent(most['share'])} of {most['school'].short} undergrads play a varsity sport"
    )
    multiple = times(most["share"], least["share"])
    against = (
        f"{multiple} {least['school'].short}'s share"
        if multiple
        else f"against {percent(least['share'])} at {least['school'].short}"
    )
    sentence = f"{plays}, {against}."

    free = [row for row in context.get("rows", []) if row["aid"] == 0]
    if not free:
        return sentence
    names = join_names([row["school"].short for row in free])
    gives = "gives" if len(free) == 1 else "give"
    # Named only when every school at zero is in the division that explains
    # it. Where one of them is not, the $0 still stands on its own and the
    # sentence stops short of a reason it cannot give.
    because = (
        ": Division III"
        if all("Division III" in (row["division"] or "") for row in free)
        else ""
    )
    return f"{sentence} {names} {gives} {money(0)} in athletic aid{because}."
