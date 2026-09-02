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


def age_notice(year: int | None, *, subject: str, as_of: int | None = None) -> Notice | None:
    """How old these figures are, when that is old enough to matter.

    Silent inside the normal publication lag — a notice on every area every
    time is a notice nobody reads.
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

    if age < STALE:
        return Notice(
            "info",
            f"These are {year} figures, the most recent IPEDS publishes for {subject}. "
            f"Current costs will be somewhat higher.",
        )

    return Notice(
        "warn",
        f"These are {year} figures — {age} years old, and the most recent IPEDS "
        f"publishes for {subject}. Do not read them as a quote for next year. "
        f"The comparison between these schools still holds, because they have all "
        f"moved since; the amounts have not.",
    )


def coverage_notices(missing_all, missing_some, *, subject: str) -> list[Notice]:
    """Which of the chosen schools do not report this, said by name.

    Named rather than counted: a student who picked four schools needs to know
    it is *their* school that is blank, and a count does not tell them that.
    """
    notices = []

    if missing_all:
        many = len(missing_all) > 1
        notices.append(
            Notice(
                "warn",
                f"{_names(missing_all)} report{'' if many else 's'} no {subject} data "
                f"at all, so {'they are' if many else 'it is'} blank below and absent "
                f"from the charts. That is a gap in the federal data, not a zero.",
            )
        )

    if missing_some:
        many = len(missing_some) > 1
        notices.append(
            Notice(
                "info",
                f"{_names(missing_some)} report{'' if many else 's'} only part of this "
                f"data. Blank cells are values the school did not report — they are "
                f"not zeros.",
            )
        )

    return notices


def for_area(year, coverage: list[Notice], *, subject: str, as_of: int | None = None):
    """Everything an area needs to say, freshness first.

    Age comes first because it qualifies every number on the page, where a
    coverage gap qualifies one row.
    """
    age = age_notice(year, subject=subject, as_of=as_of)
    return ([age] if age else []) + list(coverage)
