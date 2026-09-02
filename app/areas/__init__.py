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
    SERIES_ENDS bool  True only if IPEDS publishes nothing newer than TABLE's year
    ICON      str   inner markup for a 24x24 <svg>, stroked not filled
    TABLE     str   ingest table the year label is read from
    TEMPLATE  str   path under app/templates/
    load(conn, schools) -> dict    the template's context

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

from app.areas import financial_aid, selectiveness

ALL = [
    financial_aid,
    selectiveness,
    # Claim one and add it here:
    # student_charges,
    # retention,
    # enrollment,
    # institution_characteristics,
]

BY_KEY = {area.KEY: area for area in ALL}
