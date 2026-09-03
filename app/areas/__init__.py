"""The comparison areas, in the order the page shows them.

Adding an area is three files and one line here:

    app/areas/<area>.py               the query and the computed metric
    app/templates/areas/<area>.html   the table
    tests/test_<area>.py              the test

An area module is expected to define:

    KEY       str   url-safe identifier, matches the module name
    TITLE     str   heading shown on the page
    QUESTION  str   the question this area answers, in a family's words
    SUBJECT   str   the data in the reader's words ("net price"), for notices
    SOURCE    str   optional: the survey behind it, default "IPEDS"
    ICON      str   inner markup for a 24x24 <svg>, stroked not filled
    TABLE     str   ingest table the year label is read from
    SOURCE    str   agency/API the year label is credited to, e.g. "IPEDS"
    TEMPLATE  str   path under app/templates/
    load(conn, schools, year) -> dict    the template's context
    trend(conn, schools, years) -> dict   optional: the multi-year view
    coverage(conn) -> set[(unitid, year)]  optional: what the picker may offer

`coverage` is what the year picker greys out against, so it must answer
"could this area draw this school in this year?" rather than "does a row
exist?" — a row of sentinels is not coverage, and offering the year promises a
chart the area cannot deliver.

`load` takes the year it is rendering and must filter on it. The ingest tables
hold every year pulled, so a query without a year filter silently mixes a
decade of rows together and still returns a plausible-looking number.

`load` returns a "notices" key alongside its data: the coverage gaps only it
can see, since only it knows which schools came back empty. Freshness is added
on top of that by the route, which is where the year is known.

`load` does all the work — query, cleaning, computed metric, and any numbers a
chart needs. The template only renders what it is handed, so that reading the
template tells you what is on the page and reading the module tells you where
every number came from.

Academic libraries is deliberately absent. Schools count holdings and
circulations differently enough that putting the columns side by side invites
a comparison the data does not support.
"""

from app.areas import (
    athletics,
    enrollment,
    financial_aid,
    institution_characteristics,
    outcomes,
    retention,
    selectiveness,
)

ALL = [
    # Ordered as a student reads them: what it costs, whether they can get in,
    # what it leads to, who is there, and the reference material last.
    financial_aid,
    selectiveness,
    retention,
    outcomes,
    enrollment,
    athletics,
    institution_characteristics,
    # Claim one and add it here:
    # student_charges,
]

BY_KEY = {area.KEY: area for area in ALL}
