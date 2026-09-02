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


def number(value: int | None) -> str:
    """A whole count, grouped so five digits stay readable.

    Not registered as `count`: Jinja already defines that as an alias for
    `length`, and shadowing it would silently break `{{ things | count }}`
    somewhere else in the templates.
    """
    if value is None:
        return "—"
    return f"{value:,}"


def money(value: int | float | None) -> str:
    """A dollar figure, with the sign where a reader expects it.

    Negative prices are real in this data — grant aid exceeding the total cost
    of attendance — and "$-1,012" reads as a typo where "-$1,012" reads as a
    number.
    """
    if value is None:
        return "—"
    return f"-${abs(value):,.0f}" if value < 0 else f"${value:,.0f}"
