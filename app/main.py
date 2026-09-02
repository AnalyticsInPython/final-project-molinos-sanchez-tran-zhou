"""The web app: pick schools, pick areas, see the comparison.

Two routes. `/` is the picker, `/compare` renders the chosen areas for the
chosen schools. Every area renders the same way whether one school is selected
or five, so adding an area is filling in a template rather than designing a
screen.

    uv run uvicorn app.main:app --reload
"""

from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import areas
from app.db import connect, year_for
from app.schools import all_schools, selected

app = FastAPI(title="Like for Like")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def money(value: int | None) -> str:
    """Format a dollar figure, with the sign where a reader expects it.

    Registered once here so every area formats money the same way. Negative
    prices are real in this data — grant aid exceeding cost of attendance —
    and "$-1,012" reads as a typo where "-$1,012" reads as a number.
    """
    if value is None:
        return "\u2014"
    return f"-${abs(value):,}" if value < 0 else f"${value:,}"


templates.env.filters["money"] = money

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
):
    if not school:
        return RedirectResponse("/")

    keys = [k for k in (area or []) if k in areas.BY_KEY] or [a.KEY for a in areas.ALL]

    with connect() as conn:
        chosen = selected(conn, school[:MAX_SCHOOLS])
        sections = [
            {
                "area": areas.BY_KEY[key],
                "year": year_for(conn, areas.BY_KEY[key].TABLE),
                "context": areas.BY_KEY[key].load(conn, chosen),
            }
            for key in keys
        ]

    return templates.TemplateResponse(
        request,
        "compare.html",
        {"schools": chosen, "sections": sections},
    )
