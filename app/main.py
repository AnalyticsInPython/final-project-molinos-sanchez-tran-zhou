"""The web app: pick schools, pick areas, see the comparison.

Two routes. `/` is the picker, `/compare` renders the chosen areas for the
chosen schools. The picker emits `school` and `color` as index-matched lists,
so a comparison is fully described by its URL and stays shareable.

Every area renders the same way whether one school is selected or five, so
adding an area is filling in a template rather than designing a screen.

There are two of those renderings, chosen by how many years were asked for.
None or one is a snapshot, which is the default and what most people want.
Two or more is a trend, drawn against a single window shared by every area so
the areas stay comparable to each other.

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

app = FastAPI(title="Like for Like")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.filters["money"] = money
templates.env.filters["percent"] = percent
templates.env.filters["number"] = number

# Five is the practical ceiling: past that the tables stop fitting and the
# chart stops being readable.
MAX_SCHOOLS = 5

# The quick spans, offered as buttons. They are shortcuts that tick year
# boxes rather than a separate mode: the form submits explicit years either
# way, so a comparison is always fully described by its URL.
SPANS = [
    ("recent", "Most recent year"),
    ("5", "Last 5 years"),
    ("10", "Last 10 years"),
    ("all", "All available years"),
]


@app.get("/")
def picker(request: Request):
    with connect() as conn:
        # What each area can actually draw, per school per year. The picker
        # greys years out against this, so a year is offered only when the
        # chart behind it exists.
        coverage = {
            module.KEY: sorted(module.coverage(conn))
            for module in areas.ALL
            if hasattr(module, "coverage")
        }
        span = sorted({year for pairs in coverage.values() for _, year in pairs})
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "schools": all_schools(conn),
                "areas": areas.ALL,
                "spans": SPANS,
                "coverage": coverage,
                "all_years": span,
            },
        )


@app.get("/compare")
def compare(
    request: Request,
    school: Annotated[list[int] | None, Query()] = None,
    area: Annotated[list[str] | None, Query()] = None,
    color: Annotated[list[str] | None, Query()] = None,
    year: Annotated[list[int] | None, Query()] = None,
):
    if not school:
        return RedirectResponse("/")

    keys = [k for k in (area or []) if k in areas.BY_KEY] or [a.KEY for a in areas.ALL]
    # No years is the snapshot the app has always shown. One year is that
    # snapshot pinned to a year the reader chose. Two or more is a trend.
    wanted = sorted(set(year or []))

    with connect() as conn:
        # `color` is index-matched to `school`, so both are cut at the same
        # point or the swatches slide onto the wrong schools.
        chosen = selected(conn, school[:MAX_SCHOOLS], (color or [])[:MAX_SCHOOLS])

        # The trend axis spans exactly what was asked for, shared by every
        # area on the page. The shared axis is the point: it is what shows a
        # reader that admissions reaches 2024 while net price stopped in 2021,
        # since both are drawn against the same years and one visibly stops
        # early. Per-area windows would stretch both to the same width and
        # hide exactly that.
        modules = [areas.BY_KEY[key] for key in keys]
        shown = wanted if len(wanted) > 1 else []

        sections = []
        for module in modules:
            # The year the reader pinned, if this area has it; otherwise the
            # newest this area holds. Areas end in different years, so one
            # pinned year cannot be right for all of them.
            available = years_available(conn, module.TABLE)
            pinned = wanted[0] if len(wanted) == 1 and wanted[0] in available else None
            showing = pinned or latest_year(conn, module.TABLE)
            trending = bool(shown) and hasattr(module, "trend")

            if trending:
                context = module.trend(conn, chosen, shown)
                # The chart already draws where the data stops, against an axis
                # that runs to the present. Adding "these are 2021 figures"
                # underneath would restate what the reader can see.
                notices = context.get("notices", [])
            else:
                context = module.load(conn, chosen, showing)
                notices = for_area(
                    showing,
                    context.get("notices", []),
                    subject=getattr(module, "SUBJECT", module.TITLE.lower()),
                    series_ends=series_ends(conn, module.TABLE),
                )

            sections.append(
                {
                    "area": module,
                    "year": showing,
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
        },
    )
