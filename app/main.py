"""The web app: pick schools, pick areas, see the comparison.

`/` is the picker, `/compare` renders the chosen areas for the chosen
schools. The picker emits `school` and `color` as index-matched lists, so a
comparison is fully described by its URL and stays shareable — with no
profile and no cookie required.

Every area renders the same way whether one school is selected or five, so
adding an area is filling in a template rather than designing a screen.

There are two of those renderings, chosen by how many years were asked for.
None or one is a snapshot, which is the default and what most people want.
Two or more is a trend, drawn against a single window shared by every area so
the areas stay comparable to each other.

`/profile` and its POST routes are a second, optional layer on top: a
username-only profile (see app/profiles.py) that remembers scores, an income
bracket, and a shortlist, so a returning visitor doesn't retype them. Nothing
above this line depends on it.

    uv run uvicorn app.main:app --reload
"""

import os
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import areas, cuts, env, offers, profiles
from app.db import connect, latest_year, series_ends, years_available
from app.format import money, number, percent
from app.notices import for_area
from app.schools import all_schools, selected

env.load()

app = FastAPI(title="In League")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.filters["money"] = money
templates.env.filters["percent"] = percent
templates.env.filters["number"] = number
# `tojson` comes from FastAPI's Jinja2Templates itself (Starlette registers
# it), not from plain Jinja2 — so the institution-characteristics map, the
# one template that needs it, can drop data straight into a <script> block
# without anyone here having to add it.
#
# Empty string, not missing, when unset — the map template checks truthiness
# and renders a "no key" note rather than a broken map.
templates.env.globals["maptiler_key"] = os.environ.get("MAPTILER_API_KEY", "")

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

# Which area leads the page, per the stage the profile named. The
# questionnaire promises the stage "decides what leads the comparison":
# someone still deciding where to apply is asking whether they can get in,
# someone holding offers is asking what they will pay. `choosing` names
# financial aid, which is already first in areas.ALL — written down anyway,
# so the promise is kept by the code rather than by a coincidence of order.
STAGE_LEADS = {
    "applying": "selectiveness",
    "choosing": "financial_aid",
}

# No password, so no signing library — the cookie is just the username, and
# that tradeoff was made deliberately (see app/profiles.py).
PROFILE_COOKIE = "profile"
PROFILE_COOKIE_MAX_AGE = 180 * 24 * 60 * 60


def _current_username(request: Request) -> str | None:
    return profiles.clean_username(request.cookies.get(PROFILE_COOKIE))


@app.get("/")
def picker(request: Request):
    username = _current_username(request)
    profile = None
    if username:
        with profiles.connect() as pconn:
            profile = profiles.get_or_create(pconn, username)

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
                "profile": profile,
            },
        )


@app.get("/compare")
def compare(
    request: Request,
    school: Annotated[list[int] | None, Query()] = None,
    area: Annotated[list[str] | None, Query()] = None,
    color: Annotated[list[str] | None, Query()] = None,
    year: Annotated[list[int] | None, Query()] = None,
    cut: Annotated[list[str] | None, Query()] = None,
    tailor: Annotated[list[str] | None, Query()] = None,
):
    if not school:
        return RedirectResponse("/")

    # Cuts: `cut=<area>:<dimension>` breaks one area out by a group the survey
    # reports; `tailor=<area>` lets the profile choose for that area, with the
    # reader's own group emphasised. The reader's race or sex never enters the
    # URL — see app/cuts.py.
    explicit = cuts.parse(cut)
    tailored = cuts.parse_tailor(tailor)
    params = list(request.query_params.multi_items())

    picked = [k for k in (area or []) if k in areas.BY_KEY]
    keys = picked or [a.KEY for a in areas.ALL]
    # The comparison itself never needs a profile; this is only so the nav can
    # say who is signed in instead of offering to sign them up again.
    signed_in = _current_username(request)
    profile = None
    if signed_in:
        with profiles.connect() as pconn:
            profile = profiles.get_or_create(pconn, signed_in)

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
        # The profile's stage decides what leads, but only when the reader
        # named no area: an explicit `area=` list is an order they chose, and
        # it outranks anything the profile implies. Stable sort, so the rest
        # follow in their usual order behind whichever one is pulled forward.
        lead = STAGE_LEADS.get(profile.stage) if profile and not picked else None
        if lead:
            modules.sort(key=lambda module: lead != module.KEY)
        shown = wanted if len(wanted) > 1 else []

        sections = []
        highlights = []
        for module in modules:
            # The year the reader pinned, if this area has it; otherwise the
            # newest this area holds. Areas end in different years, so one
            # pinned year cannot be right for all of them.
            available = years_available(conn, module.TABLE)
            pinned = wanted[0] if len(wanted) == 1 and wanted[0] in available else None
            showing = pinned or latest_year(conn, module.TABLE)
            trending = bool(shown) and hasattr(module, "trend")
            tailoring = module.KEY in tailored
            cut_context = None

            if trending:
                context = module.trend(conn, chosen, shown)
                # The chart already draws where the data stops, against an axis
                # that runs to the present. Adding "these are 2021 figures"
                # underneath would restate what the reader can see.
                notices = context.get("notices", [])
            else:
                context = module.load(conn, chosen, showing)
                # An area can also tailor on a profile field that is not a
                # breakdown of any survey row — financial aid marks the
                # reader's own income band on an axis it already draws, and
                # names the sticker their home state qualifies them for. That
                # is a change to the card's own context rather than a second
                # chart above it, so it is merged in here rather than routed
                # through cut.html.
                if tailoring and profile is not None and hasattr(module, "tailor"):
                    context.update(module.tailor(conn, chosen, showing, profile))
                selection = cuts.choose(
                    module, explicit.get(module.KEY), profile if tailoring else None
                )
                if selection:
                    cut_context = module.cut(conn, chosen, showing, selection)
                notices = for_area(
                    showing,
                    context.get("notices", []),
                    subject=getattr(module, "SUBJECT", module.TITLE.lower()),
                    # Same source the card is credited to below: a staleness
                    # notice that blames IPEDS for a College Scorecard gap is
                    # wrong about who publishes what.
                    source=getattr(module, "SOURCE", "IPEDS"),
                    series_ends=series_ends(conn, module.TABLE),
                    # One year held is not a series that stopped — After
                    # graduation is a single pooled release, and "not loaded
                    # yet" would describe a year that does not exist.
                    single_release=len(available) == 1,
                )
                # Only a snapshot, and only with something to contrast: a
                # trend already tells its own story in the lines, and a
                # highlight naming "the widest gap" needs more than one
                # school to be a gap at all.
                if len(chosen) > 1 and hasattr(module, "highlights"):
                    highlights.extend(module.highlights(context))

            sections.append(
                {
                    "area": module,
                    "year": showing,
                    "mode": "trend" if trending else "snapshot",
                    "context": context,
                    "notices": notices,
                    # Almost always IPEDS; outcomes.py is the one area whose
                    # TABLE comes from a different agency's API entirely, and
                    # crediting it to IPEDS would be wrong, not just vague.
                    "source": getattr(module, "SOURCE", "IPEDS"),
                    "cut": cut_context,
                    # The "Show by" menu: one link per dimension this area's
                    # survey carries. Drawn on every card; where there is
                    # nothing to offer the menu says why.
                    "cut_menu": [
                        {
                            "label": c.label,
                            "href": cuts.link(params, module.KEY, c.key),
                            "on": bool(cut_context) and cut_context["cut"].key == c.key,
                        }
                        for c in getattr(module, "CUTS", {}).values()
                    ]
                    if not trending
                    else [],
                    "cut_menu_note": (
                        "Available on the single-year view"
                        if trending
                        else None
                        if getattr(module, "CUTS", {})
                        else "This survey has no breakdowns"
                    ),
                    "cut_clear": cuts.link(params, module.KEY, None),
                    "tailor": _tailor_state(module, profile, tailoring, trending, params),
                    # What the year on the chip means for this survey, since
                    # "2021" is the class that started in 2014 in one table
                    # and the class that entered in 2021 in another.
                    "year_meaning": (
                        module.year_meaning(conn, shown[-1] if trending else showing, trending)
                        if hasattr(module, "year_meaning")
                        else None
                    ),
                }
            )

    return templates.TemplateResponse(
        request,
        "compare.html",
        {
            "schools": chosen,
            "sections": sections,
            "years": shown,
            "profile": profile,
            "highlights": highlights,
        },
    )


def _tailor_state(module, profile, tailoring: bool, trending: bool, params) -> dict | None:
    """The per-card "Tailor data for me" button, or None to draw no button.

    Nothing is drawn signed out or where the area has no cut a profile could
    drive; a family comparing schools without an account should not see a
    control that does nothing for them.
    """
    wants = cuts.wants(module)
    if profile is None or not wants:
        return None
    if trending:
        return {"state": "trend", "hint": "Available on the single-year view"}
    signals = cuts.signals(module, profile)
    if not signals:
        return {
            "state": "empty",
            "hint": f"Add your {' or '.join(wants)} to your profile to tailor this area",
        }
    return {
        "state": "on" if tailoring else "off",
        "signals": signals,
        "href": cuts.tailor_link(params, module.KEY, not tailoring),
    }


# --- Profile: a username, scores, an income bracket, and a shortlist -------
#
# Additive, not a gate. Everything above this line works with no cookie at
# all; a profile only ever makes the picker a little less repetitive for
# someone who comes back.


def _clean_score(value: str | None, *, low: int, high: int) -> int | None:
    """A form field's score, or None if it's blank or out of range.

    Silently clearing an out-of-range value, rather than rejecting the whole
    form, matches how a missing IPEDS figure is handled everywhere else in
    this app: a blank is a real state, not an error to bounce the user over.
    """
    if not value or not value.strip():
        return None
    try:
        number_ = int(value)
    except ValueError:
        return None
    return number_ if low <= number_ <= high else None


@app.get("/profile")
def profile_page(request: Request):
    username = _current_username(request)
    profile = None
    shortlist = []
    error = request.query_params.get("error")

    offer_rows = []
    if username:
        with profiles.connect() as pconn:
            profile = profiles.get_or_create(pconn, username)
            saved = profiles.offers(pconn, username)
        with connect() as conn:
            shortlist = selected(conn, profile.shortlist)
            # Only computed for someone who has offers to compare. A student
            # still deciding where to apply has nothing to put here.
            if profile.stage == "choosing":
                for school in shortlist:
                    offer = saved.get(school.unitid)
                    comparison = None
                    if offer and offer.net_offer is not None:
                        comparison = offers.compare(
                            conn,
                            school.unitid,
                            net_offer=offer.net_offer,
                            income_band=profile.income_bracket,
                            home_state=profile.home_state,
                        )
                    offer_rows.append({"school": school, "offer": offer, "comparison": comparison})

    with connect() as conn:
        return templates.TemplateResponse(
            request,
            "profile.html",
            {
                "profile": profile,
                "shortlist": shortlist,
                "all_schools": all_schools(conn),
                "max_shortlist": profiles.MAX_SHORTLIST,
                "error": error,
                "races": profiles.RACES,
                "genders": profiles.GENDERS,
                "states": profiles.STATES,
                "stages": profiles.STAGES,
                "offer_rows": offer_rows,
            },
        )


@app.post("/profile")
def start_profile(username: Annotated[str, Form()]):
    clean = profiles.clean_username(username)
    if not clean:
        return RedirectResponse(
            "/profile?error=Usernames+are+3-20+letters%2C+numbers%2C+-+or+_.",
            status_code=303,
        )

    with profiles.connect() as pconn:
        profiles.get_or_create(pconn, clean)

    response = RedirectResponse("/profile", status_code=303)
    response.set_cookie(
        PROFILE_COOKIE,
        clean,
        max_age=PROFILE_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/profile/new")
def new_profile_form(request: Request):
    """The sign-up questionnaire.

    Every question here changes something the app shows. Home state decides
    whether a public school's in-state or out-of-state tuition applies, which
    is a $38,000 difference at Michigan. Income bracket picks the net price
    band. Race and gender join onto outcome data broken out the same way, so
    a graduation rate can be the one for students like you rather than the
    headline. Stage decides which area leads the page.

    GPA is the exception and the form says so: IPEDS publishes no admitted
    GPA for any institution, so it is recorded for the person's own reference
    and compared against nothing.
    """
    with connect() as conn:
        return templates.TemplateResponse(
            request,
            "questionnaire.html",
            {
                "schools": all_schools(conn),
                "races": profiles.RACES,
                "genders": profiles.GENDERS,
                "states": profiles.STATES,
                "stages": profiles.STAGES,
                "bands": areas.financial_aid.BANDS,
                "error": request.query_params.get("error"),
            },
        )


@app.post("/profile/new")
def create_profile(
    username: Annotated[str, Form()],
    display_name: Annotated[str | None, Form()] = None,
    sat: Annotated[str | None, Form()] = None,
    act: Annotated[str | None, Form()] = None,
    gpa: Annotated[str | None, Form()] = None,
    income_bracket: Annotated[str | None, Form()] = None,
    home_state: Annotated[str | None, Form()] = None,
    race: Annotated[str | None, Form()] = None,
    gender: Annotated[str | None, Form()] = None,
    stage: Annotated[str | None, Form()] = None,
    school: Annotated[list[int] | None, Form()] = None,
):
    clean = profiles.clean_username(username)
    if not clean:
        return RedirectResponse(
            "/profile/new?error=Usernames+are+3-20+letters%2C+numbers%2C+-+or+_.",
            status_code=303,
        )

    with profiles.connect() as pconn:
        profiles.get_or_create(pconn, clean)
        profiles.set_scores(
            pconn,
            clean,
            sat=_clean_score(sat, low=400, high=1600),
            act=_clean_score(act, low=1, high=36),
            income_bracket=_clean_score(income_bracket, low=1, high=5),
        )
        profiles.set_details(
            pconn,
            clean,
            display_name=profiles.clean_name(display_name),
            gpa=profiles.clean_gpa(gpa),
            home_state=profiles.clean_choice(home_state, profiles.STATES),
            race=profiles.clean_choice(race, profiles.RACES),
            gender=profiles.clean_choice(gender, profiles.GENDERS),
            stage=profiles.clean_choice(stage, profiles.STAGES),
        )
        for unitid in (school or [])[: profiles.MAX_SHORTLIST]:
            profiles.add_school(pconn, clean, unitid)

    response = RedirectResponse("/profile", status_code=303)
    response.set_cookie(
        PROFILE_COOKIE,
        clean,
        max_age=PROFILE_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return response


@app.post("/profile/details")
def update_details(
    request: Request,
    display_name: Annotated[str | None, Form()] = None,
    gpa: Annotated[str | None, Form()] = None,
    home_state: Annotated[str | None, Form()] = None,
    race: Annotated[str | None, Form()] = None,
    gender: Annotated[str | None, Form()] = None,
    stage: Annotated[str | None, Form()] = None,
):
    """Change the answers later. Same validation as the questionnaire."""
    username = _current_username(request)
    if not username:
        return RedirectResponse("/profile", status_code=303)

    with profiles.connect() as pconn:
        profiles.set_details(
            pconn,
            username,
            display_name=profiles.clean_name(display_name),
            gpa=profiles.clean_gpa(gpa),
            home_state=profiles.clean_choice(home_state, profiles.STATES),
            race=profiles.clean_choice(race, profiles.RACES),
            gender=profiles.clean_choice(gender, profiles.GENDERS),
            stage=profiles.clean_choice(stage, profiles.STAGES),
        )
    return RedirectResponse("/profile", status_code=303)


@app.post("/profile/offers")
def save_offer(
    request: Request,
    unitid: Annotated[int, Form()],
    net_offer: Annotated[str | None, Form()] = None,
    grant_aid: Annotated[str | None, Form()] = None,
    loan_aid: Annotated[str | None, Form()] = None,
):
    """Record what one school offered. Blanking every field clears it again."""
    username = _current_username(request)
    if username:
        with profiles.connect() as pconn:
            profiles.set_offer(
                pconn,
                username,
                unitid,
                net_offer=profiles.clean_money(net_offer),
                grant_aid=profiles.clean_money(grant_aid),
                loan_aid=profiles.clean_money(loan_aid),
            )
    return RedirectResponse("/profile", status_code=303)


@app.post("/profile/logout")
def logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(PROFILE_COOKIE)
    return response


@app.post("/profile/scores")
def update_scores(
    request: Request,
    sat: Annotated[str | None, Form()] = None,
    act: Annotated[str | None, Form()] = None,
    income_bracket: Annotated[str | None, Form()] = None,
):
    username = _current_username(request)
    if not username:
        return RedirectResponse("/profile", status_code=303)

    with profiles.connect() as pconn:
        profiles.set_scores(
            pconn,
            username,
            sat=_clean_score(sat, low=400, high=1600),
            act=_clean_score(act, low=1, high=36),
            income_bracket=_clean_score(income_bracket, low=1, high=5),
        )

    return RedirectResponse("/profile", status_code=303)


@app.post("/profile/schools")
def add_shortlist_school(request: Request, unitid: Annotated[int, Form()]):
    username = _current_username(request)
    if username:
        with profiles.connect() as pconn:
            profiles.add_school(pconn, username, unitid)
    return RedirectResponse("/profile", status_code=303)


@app.post("/profile/schools/{unitid}/remove")
def remove_shortlist_school(request: Request, unitid: int):
    username = _current_username(request)
    if username:
        with profiles.connect() as pconn:
            profiles.remove_school(pconn, username, unitid)
    return RedirectResponse("/profile", status_code=303)
