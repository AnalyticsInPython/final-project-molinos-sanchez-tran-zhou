"""Telling the student what the figures do not cover.

Two ways this app can hand someone a page that looks finished and is not, and
neither one raises an exception:

- **A figure old enough to mislead.** IPEDS runs a couple of years behind by
  design, which is fine. Net price by income band stops at 2021, which is not:
  a family budgeting for 2026 off a 2021 number is budgeting off a number that
  no longer exists anywhere.
- **A school that reports nothing.** A blank cell reads as a zero, or as a bug
  in our table, unless the page says which school is missing and that the gap
  is in the federal data rather than in us.

Both are stated at the top of the area they affect, before the reader has
drawn a conclusion from the chart, rather than in a footnote underneath it.

The wording is deliberately careful about what a stale figure still supports.
2021 net prices are a bad quote for 2026 and a perfectly good comparison
between two schools, because the schools moved together. Saying "out of date"
and stopping would throw away the part that still works.

It is equally careful about who published the figure and whether a newer one
could exist. The caller names the source, because most areas are IPEDS and
After graduation is the College Scorecard, and blaming the wrong agency for a
gap is a factual error on the page rather than a vague one.
"""

from dataclasses import dataclass
from datetime import date

# Years of publication lag that are normal for a federal survey and not worth
# interrupting the reader over.
LAG = 2

# Beyond this the level is likely to mislead, even though the comparison
# between schools usually survives.
STALE = 5


@dataclass(frozen=True)
class Notice:
    """One thing the reader needs to know before trusting the numbers.

    `level` is "warn" when acting on the figures without reading this could
    leave someone with a wrong number, and "info" when it is context.
    """

    level: str
    text: str


def _names(schools) -> str:
    """School names as a person would say the list out loud."""
    names = [school.short for school in schools]
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def age_notice(
    year: int | None,
    *,
    subject: str,
    as_of: int | None = None,
    source: str = "IPEDS",
    series_ends: bool = False,
    single_release: bool = False,
) -> Notice | None:
    """How old these figures are, when that is old enough to matter.

    Silent inside the normal publication lag — a notice on every area every
    time is a notice nobody reads.

    `source` is the agency that publishes this area, named by the caller.
    Thirteen of the fourteen ingest tables are IPEDS, which is why that is the
    default, but After graduation is the College Scorecard and athletics is
    EADA, and a notice that credits IPEDS for either is wrong on its face.

    `series_ends` separates two situations that look identical on the page and
    are not. Net price genuinely stops at 2021: ask IPEDS for 2022 and it
    returns success with no rows, so 2021 really is the newest figure that
    exists. Admissions runs to 2024 and this build ingested 2021, which is our
    limitation rather than the survey's. Telling a student that a stale number
    is the best available, when a newer one exists, is worse than saying
    nothing — so the default is the honest, unflattering branch, and an area
    has to assert that its series has ended.

    `single_release` is the third case, and the reason the second one is not
    enough: After graduation has no series at all. Its table holds one year
    because the Scorecard pools several entry cohorts into a single release,
    not because an ingest stopped early and not because a survey wound down.
    Checked after `series_ends`, so a one-year table with an empty year
    recorded above it is still the survey saying it stops there.
    """
    if year is None:
        return Notice(
            "warn",
            f"We could not determine which year these {subject} figures are from. "
            "Treat them as undated.",
        )

    age = (as_of or date.today().year) - year
    if age <= LAG:
        return None

    if series_ends:
        if age < STALE:
            return Notice(
                "info",
                f"These are {year} figures, the most recent {source} publishes for "
                f"{subject}. Current figures will have moved since.",
            )
        return Notice(
            "warn",
            f"These are {year} figures — {age} years old, and the most recent {source} "
            f"publishes for {subject}. Do not read them as a quote for next year. "
            f"The comparison between these schools still holds, because they have all "
            f"moved since; the amounts have not.",
        )

    if single_release:
        if age < STALE:
            return Notice(
                "info",
                f"These are {year} figures. {source} pools several entry cohorts into "
                f"one release for {subject}; there is no newer year to load.",
            )
        return Notice(
            "warn",
            f"These are {year} figures — {age} years old. {source} pools several entry "
            f"cohorts into one release for {subject}; there is no newer year to load. "
            f"Read them as where each school's graduates stand, not as a quote for "
            f"next year.",
        )

    if age < STALE:
        return Notice(
            "info",
            f"These are {year} figures. {source} publishes newer years for {subject} "
            f"that this build has not loaded yet.",
        )
    return Notice(
        "warn",
        f"These are {year} figures — {age} years old. {source} publishes newer years "
        f"for {subject} that this build has not loaded, so do not read these as a "
        f"quote for next year. The comparison between these schools still holds; "
        f"the amounts are out of date.",
    )


def coverage_notices(missing_all, missing_some, *, subject: str, series: bool = False):
    """Which of the chosen schools do not report this, said by name.

    Named rather than counted: a student who picked four schools needs to know
    it is *their* school that is blank, and a count does not tell them that.

    `series` switches the wording for the trend view, where the gap is a break
    in a line rather than an empty cell. Same fact, and telling a reader to
    look for a blank cell on a page that has no table is how a caveat gets
    skipped.
    """
    notices = []

    if missing_all:
        many = len(missing_all) > 1
        where = "in these years" if series else "below"
        notices.append(
            Notice(
                "warn",
                f"{_names(missing_all)} report{'' if many else 's'} no {subject} data "
                f"at all, so {'they are' if many else 'it is'} absent {where} and from "
                f"the charts. That is a gap in the federal data, not a zero.",
            )
        )

    if missing_some:
        many = len(missing_some) > 1
        detail = (
            "Their lines break where the data does, rather than joining across it."
            if many
            else "Its line breaks where the data does, rather than joining across it."
        )
        notices.append(
            Notice(
                "info",
                f"{_names(missing_some)} {'are' if many else 'is'} missing some years "
                f"in this range. {detail}"
                if series
                else f"{_names(missing_some)} report{'' if many else 's'} only part of "
                f"this data. Blank cells are values the school did not report — they "
                f"are not zeros.",
            )
        )

    return notices


def series_notices(
    schools,
    years: list[int],
    seen: set[tuple[int, int]],
    *,
    subject: str,
    source: str = "IPEDS",
    published: list[int] | None = None,
    ends: bool = False,
) -> list[Notice]:
    """Coverage for a trend view, where the axis is wider than the survey.

    The trend axis is the window the reader asked for, shared by every area on
    the page, and it therefore runs past the year an individual survey stops.
    Net price ends in 2021: ask for 2015–2024 and every school is three years
    short of the axis. Counted naively that is five schools with holes in their
    data, which is what this page used to say — and it is one survey ending,
    which is a fact about IPEDS rather than about Berkeley. Naming schools for
    it is worse than vague: it invites a reader to prefer the school we blamed
    least, on a difference that does not exist.

    So the years the series does not cover are taken off the table before
    anyone is named, and the ending is stated once, with no school in it. A
    school is named only where it lacks a year that another school in the same
    comparison has — that is the only kind of gap that belongs to a school.

    `published` is every year the survey holds (`db.years_available`) and
    `ends` says whether it stopped there or we simply loaded no further
    (`db.series_ends`). Same distinction `age_notice` draws, for the same
    reason: telling a reader a survey has ended when it has not is a factual
    error, and the flattering direction to be wrong in.

    Returns the whole list a trend view needs, so an area calls this instead of
    working out `missing_all` and `missing_some` for itself. Five areas did
    that arithmetic separately and all five got this wrong the same way.
    """
    years = sorted(years)
    held = sorted(published or [])
    covered = {year for _, year in seen}

    notices = []
    if years and held:
        if years[-1] > held[-1]:
            notices.append(
                Notice(
                    "info",
                    f"The {subject} series stops at {held[-1]} for every school here; "
                    + (
                        f"{source} has published nothing newer."
                        if ends
                        else f"that is the newest year this build has loaded, not the "
                        f"newest {source} publishes."
                    )
                    + f" The axis runs to {years[-1]} because other areas do.",
                )
            )
        if years[0] < held[0]:
            notices.append(
                Notice(
                    "info",
                    f"The {subject} series begins in {held[0]}. The years before it are "
                    f"empty for every school here, rather than missing from any one of "
                    f"them.",
                )
            )

    # Only the part of the window the survey covers at all can be anyone's gap.
    within = [year for year in years if not held or held[0] <= year <= held[-1]]

    # `within` empty means the reader asked for a window entirely outside the
    # series. Nobody is missing anything there; the notice above says why the
    # page is blank, and naming every school for it is the bug this fixes.
    missing_all = [
        school
        for school in schools
        if within and not any((school.unitid, year) in seen for year in within)
    ]
    absent = {school.unitid for school in missing_all}

    # A year no school in this comparison reports is a hole in the survey, not
    # in the school. Only years someone here does have can single anyone out.
    shared = [year for year in within if year in covered]
    missing_some = [
        school
        for school in schools
        if school.unitid not in absent and any((school.unitid, year) not in seen for year in shared)
    ]

    return notices + coverage_notices(missing_all, missing_some, subject=subject, series=True)


def for_area(
    year,
    coverage: list[Notice],
    *,
    subject: str,
    as_of: int | None = None,
    source: str = "IPEDS",
    series_ends: bool = False,
    single_release: bool = False,
):
    """Everything an area needs to say, freshness first.

    Age comes first because it qualifies every number on the page, where a
    coverage gap qualifies one row.

    `source`, `series_ends` and `single_release` are passed straight through
    to `age_notice`; the route knows all three because it holds the area
    module and the connection, and this function knows neither.
    """
    age = age_notice(
        year,
        subject=subject,
        as_of=as_of,
        source=source,
        series_ends=series_ends,
        single_release=single_release,
    )
    return ([age] if age else []) + list(coverage)
