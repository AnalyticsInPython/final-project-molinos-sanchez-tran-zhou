"""Formatting shared by every area.

Lives on its own so that the templates and the modules that lay out charts
format a number the same way. Anything an area needs to display in a second
place belongs here rather than being written twice.
"""


def money(value: int | float | None) -> str:
    """A dollar figure, with the sign where a reader expects it.

    Negative prices are real in this data — grant aid exceeding the total cost
    of attendance — and "$-1,012" reads as a typo where "-$1,012" reads as a
    number.
    """
    if value is None:
        return "—"
    return f"-${abs(value):,.0f}" if value < 0 else f"${value:,.0f}"
