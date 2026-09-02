"""The web app: pick schools, pick areas, see the comparison.

Two routes. `/` is the picker, `/compare` renders the chosen areas for the
chosen schools. The picker emits `school` and `color` as index-matched lists,
so a comparison is fully described by its URL and stays shareable.

Every area renders the same way whether one school is selected or five, so
adding an area is filling in a template rather than designing a screen.

    uv run uvicorn app.main:app --reload
"""

from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import areas
from app.db import connect, latest_year, series_ends
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


@app.get("/")
def picker(request: Request):
    with connect() as conn:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"schools": all_schools(conn), "areas": areas.ALL},
        )


@app.get("/compare")
def compare(
    request: Request,
    school: Annotated[list[int] | None, Query()] = None,
    area: Annotated[list[str] | None, Query()] = None,
    color: Annotated[list[str] | None, Query()] = None,
):
    if not school:
        return RedirectResponse("/")

    keys = [k for k in (area or []) if k in areas.BY_KEY] or [a.KEY for a in areas.ALL]

    with connect() as conn:
        # `color` is index-matched to `school`, so both are cut at the same
        # point or the swatches slide onto the wrong schools.
        chosen = selected(
            conn, school[:MAX_SCHOOLS], (color or [])[:MAX_SCHOOLS]
        )
        sections = []
        for key in keys:
            # Not `area`: that is the query parameter, and shadowing it here
            # would read as a bug even though `keys` is already resolved.
            module = areas.BY_KEY[key]
            # The newest year this area actually has, not a build-wide anchor.
            # Areas end in different years and each shows its own.
            year = latest_year(conn, module.TABLE)
            context = module.load(conn, chosen, year)
            sections.append(
                {
                    "area": module,
                    "year": year,
                    "context": context,
                    # Coverage comes from the area, which is the only thing
                    # that knows which schools came back empty; freshness is
                    # added here, which is where the year is known.
                    "notices": for_area(
                        year,
                        context.get("notices", []),
                        subject=getattr(module, "SUBJECT", module.TITLE.lower()),
                        series_ends=series_ends(conn, module.TABLE),
                    ),
                }
            )

    return templates.TemplateResponse(
        request,
        "compare.html",
        {"schools": chosen, "sections": sections},
    )
