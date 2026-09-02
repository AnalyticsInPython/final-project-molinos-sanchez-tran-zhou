"""The web app: pick schools, pick areas, see the comparison.

Two routes. `/` is the picker, `/compare` renders the chosen areas for the
chosen schools. The picker emits `school` and `color` as index-matched lists,
so a comparison is fully described by its URL and stays shareable.

Every area renders the same way whether one school is selected or five, so
adding an area is filling in a template rather than designing a screen.

There are two of those renderings. Without a year range the page is a snapshot
of the newest year each area has, which is the default and what most people
want. Ask for a range and every area switches to a trend view instead, drawn
from one shared window so the areas stay comparable to each other.

    uv run uvicorn app.main:app --reload
"""

from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import areas
from app.db import connect, latest_year, series_ends, years_available
from app.format import money, number, percent
from app.notices import for_area
from app.schools import all_schools, selected
from app.trend import window

app = FastAPI(title="Like for Like")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.filters["money"] = money
templates.env.filters["percent"] = percent
templates.env.filters["number"] = number

# Five is the practical ceiling: past that the tables stop fitting and the
# chart stops being readable.
MAX_SCHOOLS = 5

# What the year control offers. "" is the default and keeps the snapshot the
# app has always shown; anything else switches every area to the trend view.
SPANS = {
    "": "Most recent year",
    "5": "Last 5 years",
    "10": "Last 10 years",
    "all": "All available years",
}


@app.get("/")
def picker(request: Request):
    with connect() as conn:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"schools": all_schools(conn), "areas": areas.ALL, "spans": SPANS},
        )


@app.get("/compare")
def compare(
    request: Request,
    school: Annotated[list[int] | None, Query()] = None,
    area: Annotated[list[str] | None, Query()] = None,
    color: Annotated[list[str] | None, Query()] = None,
    years: Annotated[str, Query()] = "",
):
    if not school:
        return RedirectResponse("/")

    keys = [k for k in (area or []) if k in areas.BY_KEY] or [a.KEY for a in areas.ALL]
    span = years if years in SPANS else ""

    with connect() as conn:
        # `color` is index-matched to `school`, so both are cut at the same
        # point or the swatches slide onto the wrong schools.
        chosen = selected(conn, school[:MAX_SCHOOLS], (color or [])[:MAX_SCHOOLS])

        # One window across every area on the page rather than each area's own
        # last N years. The shared axis is the point: it is what shows a reader
        # that admissions reaches 2024 while net price stopped in 2021, since
        # both lines are drawn against the same years and one of them simply
        # stops early. Per-area windows would stretch both to the same width
        # and hide exactly that.
        modules = [areas.BY_KEY[key] for key in keys]
        covered = sorted({y for m in modules for y in years_available(conn, m.TABLE)})
        shown = window(covered[-1], span, covered[0]) if span and covered else []

        sections = []
        for module in modules:
            # The newest year this area actually has, not a build-wide anchor.
            year = latest_year(conn, module.TABLE)
            trending = bool(shown) and hasattr(module, "trend")

            if trending:
                context = module.trend(conn, chosen, shown)
                # The chart already draws where the data stops, against an axis
                # that runs to the present. Adding "these are 2021 figures"
                # underneath would restate what the reader can see.
                notices = context.get("notices", [])
            else:
                context = module.load(conn, chosen, year)
                notices = for_area(
                    year,
                    context.get("notices", []),
                    subject=getattr(module, "SUBJECT", module.TITLE.lower()),
                    series_ends=series_ends(conn, module.TABLE),
                )

            sections.append(
                {
                    "area": module,
                    "year": year,
                    "mode": "trend" if trending else "snapshot",
                    "context": context,
                    "notices": notices,
                }
            )

    return templates.TemplateResponse(
        request,
        "compare.html",
        {
            "schools": chosen,
            "sections": sections,
            "years": shown,
            "span": span,
            "spans": SPANS,
        },
    )
