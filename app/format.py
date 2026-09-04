"""Formatting shared by every area.

Lives on its own so that the templates and the modules that lay out charts
format a number the same way. Anything an area needs to display in a second
place belongs here rather than being written twice.
"""


def percent(value: float | None, places: int = 1) -> str:
    """A rate as a percentage.

    Rates are computed and stored as fractions throughout, matching how IPEDS
    stores the ones it publishes — `completion_rate_150pct` is 0.98, not 98 —
    so that nothing has to remember which convention a given number follows.
    The conversion happens here, once, on the way to the page.
    """
    if value is None:
        return "—"
    return f"{value * 100:.{places}f}%"


def number(value: int | float | None) -> str:
    """A whole count, grouped so five digits stay readable.

    Rounds rather than assuming an integer: chart axis ticks are interpolated
    between the extremes, so they arrive as floats, and formatting one
    unrounded put "105,654.32" applications on an axis.

    Not registered as `count`: Jinja already defines that as an alias for
    `length`, and shadowing it would silently break `{{ things | count }}`
    somewhere else in the templates.
    """
    if value is None:
        return "—"
    return f"{round(value):,}"


def money(value: int | float | None) -> str:
    """A dollar figure, with the sign where a reader expects it.

    Negative prices are real in this data — grant aid exceeding the total cost
    of attendance — and "$-1,012" reads as a typo where "-$1,012" reads as a
    number.
    """
    if value is None:
        return "—"
    return f"-${abs(value):,.0f}" if value < 0 else f"${value:,.0f}"


# --- Words, for the sentence at the top of each card -------------------------
#
# The headlines (see any area's `headline`) are read out loud off a projector,
# and a small number reads faster as a word than as a numeral: "six times
# Michigan's share" lands where "6.4×" asks the reader to do the comparison
# themselves. Only small whole numbers are spelled — past twelve a numeral is
# clearer, and a ratio that large is better stated as the two figures.

WORDS = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
    11: "eleven",
    12: "twelve",
}


def spell(value: int) -> str:
    """A small whole number as a word, or the grouped numeral past twelve."""
    return WORDS.get(value, f"{value:,}")


def times(bigger: float | None, smaller: float | None) -> str | None:
    """How many times over one figure covers another — "twice", "six times".

    None rather than a phrase when the multiple is not worth stating: below
    1.5 the two figures are the finding on their own, and above twelve the
    word is longer than the numbers it stands for. Rounded, because the
    sentence is a comparison a reader repeats out loud and a decimal invites a
    precision the underlying rounding does not support.
    """
    if not bigger or not smaller or smaller <= 0 or bigger <= 0:
        return None
    ratio = round(bigger / smaller)
    if ratio < 2 or ratio > 12:
        return None
    return "twice" if ratio == 2 else f"{spell(ratio)} times"


def reciprocal(share: float | None) -> int | None:
    """The n in "one in n", or None where that phrasing would mislead.

    Only a small whole number earns the phrase: "one in six" is exact enough
    to say out loud at 17.8% and meaningless at 1.4%, where the reader hears a
    rounder number than the data supports.
    """
    if not share or share <= 0 or share > 1:
        return None
    denominator = round(1 / share)
    return denominator if 2 <= denominator <= 12 else None


def one_in(share: float | None) -> str | None:
    """A share as "one in six". None where `reciprocal` declines to say it."""
    denominator = reciprocal(share)
    return f"one in {spell(denominator)}" if denominator else None


def join_names(names: list[str]) -> str:
    """Names in a sentence: "MIT", "MIT and Stanford", "A, B and C".

    No serial comma, matching the prose everywhere else in this project.
    """
    if len(names) < 3:
        return " and ".join(names)
    return f"{', '.join(names[:-1])} and {names[-1]}"
