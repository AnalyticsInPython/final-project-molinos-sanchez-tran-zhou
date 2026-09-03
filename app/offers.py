"""Setting a student's actual offer against what the school usually charges.

This is the one comparison in the app that needs something only the student
has. IPEDS says what families at each income band paid on average; the offer
letter says what *this* family was asked for. Neither number alone answers
"is this a good offer".

**The comparison is on discount rate, not dollars.** Published net price stops
at 2021 and an offer letter is for next year, so comparing the two in dollars
compares 2021 money with 2026 money and reports inflation as generosity.
Sticker and net inflate together, so the share of sticker a school forgives is
much steadier than either figure alone.

**Steadier, not stable, and the difference is measurable.** Checked against
2015-2021 across this sample: net price at the lowest income band moved 37% and
at the highest 13%, while the discount rate at those bands drifted 88.3% to
93.0% and 32.6% to 36.6% — roughly 0.7 points a year, consistently upward as
schools have become more generous. So over the five-year gap this comparison
spans, expect the published rate to understate a school's current generosity by
about three or four points. That is small next to the dollar error it avoids,
and it is not nothing: a verdict inside a few points of the threshold should be
read as "about typical" rather than as a finding. `verdict` uses a five-point
band for exactly that reason.
"""

import sqlite3
from dataclasses import dataclass

# tuition_type: 2 in-district, 3 in-state, 4 out-of-state. Identical at every
# private institution; a $38,000 difference at Michigan.
IN_STATE, OUT_OF_STATE = 3, 4

SENTINELS = (-1, -2, -3)


@dataclass(frozen=True)
class Comparison:
    """One school's offer beside its published pattern."""

    unitid: int
    sticker: int
    your_net: int
    your_discount: float
    typical_discount: float | None
    typical_year: int | None
    in_state: bool

    @property
    def gap(self) -> float | None:
        """Positive means the offer forgives more than this school usually does."""
        if self.typical_discount is None:
            return None
        return self.your_discount - self.typical_discount

    @property
    def verdict(self) -> str:
        """What to say about it, hedged to what a rate comparison supports."""
        if self.gap is None:
            return "This school does not publish net price for your income band."
        if self.gap > 0.05:
            return "Better than this school's usual offer at your income."
        if self.gap < -0.05:
            return "Less generous than this school's usual offer at your income."
        return "About what this school usually offers at your income."


def _cost_of_attendance(conn, unitid: int, year: int, tuition_type: int) -> int | None:
    row = conn.execute(
        "SELECT t.tuition_fees_ft + r.room_board + r.books_supplies + r.exp_other AS coa "
        "FROM academic_year_tuition t JOIN academic_year_room_board_other r "
        "  ON r.unitid = t.unitid AND r.year = t.year "
        " AND r.level_of_study = 1 AND r.living_arrangement = 1 "
        "WHERE t.unitid = ? AND t.year = ? AND t.level_of_study = 1 "
        "  AND t.tuition_type = ?",
        (unitid, year, tuition_type),
    ).fetchone()
    return row["coa"] if row and row["coa"] and row["coa"] > 0 else None


def compare(
    conn: sqlite3.Connection,
    unitid: int,
    *,
    net_offer: int,
    income_band: int | None,
    home_state: str | None,
) -> Comparison | None:
    """The student's offer as a discount, beside the published one.

    Returns None when the school publishes no cost of attendance we can put a
    percentage over — a rate needs a denominator, and inventing one would make
    the most confident-looking number on the page the least supported.
    """
    school_state = conn.execute(
        "SELECT state_abbr FROM directory WHERE unitid = ? AND state_abbr IS NOT NULL "
        "AND state_abbr != '' ORDER BY year DESC LIMIT 1",
        (unitid,),
    ).fetchone()
    in_state = bool(
        home_state and school_state and school_state["state_abbr"] == home_state
    )
    tuition_type = IN_STATE if in_state else OUT_OF_STATE

    latest = conn.execute(
        "SELECT MAX(year) AS year FROM academic_year_tuition WHERE unitid = ?",
        (unitid,),
    ).fetchone()
    if not latest or latest["year"] is None:
        return None

    sticker = _cost_of_attendance(conn, unitid, latest["year"], tuition_type)
    if not sticker:
        return None

    typical_discount, typical_year = None, None
    if income_band:
        row = conn.execute(
            "SELECT year, net_price FROM sfa_grants_and_net_price "
            "WHERE unitid = ? AND type_of_aid = 9 AND income_level = ? "
            "  AND net_price NOT IN (-1, -2, -3) ORDER BY year DESC LIMIT 1",
            (unitid, income_band),
        ).fetchone()
        if row:
            # Priced against the sticker of the *same* year, so the ratio is
            # internally consistent even though that year is not this year.
            same_year = _cost_of_attendance(conn, unitid, row["year"], tuition_type)
            if same_year:
                typical_discount = 1 - (row["net_price"] / same_year)
                typical_year = row["year"]

    return Comparison(
        unitid=unitid,
        sticker=sticker,
        your_net=net_offer,
        your_discount=1 - (net_offer / sticker),
        typical_discount=typical_discount,
        typical_year=typical_year,
        in_state=in_state,
    )
