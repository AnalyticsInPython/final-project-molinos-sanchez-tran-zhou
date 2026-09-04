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

`/present/on` and `/present/off` are a third rendering, and the only one that
is not about the data: the same page with the charts enlarged and the tables
and footnotes put away, for showing on a projector. It is a cookie, so it
survives the whole walk through the app rather than having to be added to
every link on it.

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
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import areas, cuts, env, offers, profiles
from app.db import connect, latest_year, series_ends, years_available
from app.format import money, number, percent
from app.notices import first_sentence, for_area
from app.schools import all_schools, selected

env.load()

app = FastAPI(title="In League")
# The one asset that isn't generated from data: the front-page hero photo.
# See templates/index.html's comment on `.hero` for sourcing and why it
# replaced the earlier drawn motif.
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
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
# Present mode's one piece of template logic beyond a body class: a notice
# shown as its first sentence, with the rest folded into a <details>. The
# split is in app/notices.py, where it can be tested; the template only
# decides where the two halves go. See `first_sentence` there.
templates.env.filters["first_sentence"] = first_sentence

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

# The cookie is still just the username, unsigned. A profile may now carry an
# optional passphrase, which decides who is allowed to be handed this cookie
# (see app/profiles.py); signing the cookie itself is a separate change and
# has not been made.
PROFILE_COOKIE = "profile"
PROFILE_COOKIE_MAX_AGE = 180 * 24 * 60 * 60

# Present mode: the same pages, sized for a projector. A cookie rather than a
# `present=1` on the URL because the demo walks a path — the picker's form
# submit, then a "Show by" link, then "Tailor data for me" — and each of those
# builds its own next URL. A parameter would have to be threaded through every
# one of them; a cookie is carried by the browser and nothing else has to know
# it exists.
#
# Half a day, not the profile's six months: leaving the class in present mode
# should not still be showing hidden tables next term.
PRESENT_COOKIE = "present"
PRESENT_COOKIE_MAX_AGE = 12 * 60 * 60


def _current_username(request: Request) -> str | None:
    return profiles.clean_username(request.cookies.get(PROFILE_COOKIE))


def present_mode(request: Request) -> bool:
    """Is this browser in present mode?

    Registered as a template global below, so `base.html` can put the class on
    `<body>` and `compare.html` can fold its notices without every route
    having to remember to pass a flag.
    """
    return request.cookies.get(PRESENT_COOKIE) == "1"


templates.env.globals["present_mode"] = present_mode


def safe_next(target: str | None) -> str:
    """The page to return to after toggling, when it is a page of ours.

    The toggle carries wherever the reader was as `?next=`, which is exactly
    the shape an open redirect takes: `/present/on?next=https://elsewhere` puts
    our own domain in front of somebody else's page. So only a path on this
    app is honoured — one leading slash and no more, since `//host` and its
    backslash spelling are both read by browsers as a different site — and
    anything else falls back to the front page rather than being followed.
    """
    target = (target or "").strip()
    if not target.startswith("/"):
        return "/"
    if target.startswith(("//", "/\\")):
        return "/"
    return target


@app.get("/present/on")
def present_on(next_: Annotated[str, Query(alias="next")] = "/"):
    """Turn present mode on and go back where the reader was.

    Back to the page, not to the spot on it: a fragment never reaches the
    server, so toggling from halfway down the comparison lands at its top.
    Turning present mode on is a thing done once, before the demo starts.
    """
    response = RedirectResponse(safe_next(next_), status_code=303)
    response.set_cookie(
        PRESENT_COOKIE,
        "1",
        max_age=PRESENT_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/present/off")
def present_off(next_: Annotated[str, Query(alias="next")] = "/"):
    """Back to the page as everyone else sees it."""
    response = RedirectResponse(safe_next(next_), status_code=303)
    response.delete_cookie(PRESENT_COOKIE)
    return response


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
            headline = None

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
                # The sentence the card leads with, computed from what this
                # area has just worked out and handed the cut context so a
                # tailored card names the reader's own group. Only a
                # snapshot: a trend tells its story in the lines, and the
                # areas return None themselves where one school leaves
                # nothing to compare against.
                headline = module.headline(context, cut_context)
                # The strip on the characteristics card is the page's summary
                # — every card's own opening sentence, gathered where a reader
                # who scrolled past them can still see the lot. That card's
                # own line is left out: it is the sentence directly above the
                # strip, and printing it twice on one card reads as a bug.
                if headline and module.KEY != "institution_characteristics":
                    highlights.append(headline)

            sections.append(
                {
                    "area": module,
                    "year": showing,
                    "mode": "trend" if trending else "snapshot",
                    "context": context,
                    "headline": headline,
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
                "min_passphrase": profiles.MIN_PASSPHRASE,
                "error": error,
                "races": profiles.RACES,
                "genders": profiles.GENDERS,
                "states": profiles.STATES,
                "stages": profiles.STAGES,
                "offer_rows": offer_rows,
            },
        )


@app.post("/profile")
def start_profile(
    username: Annotated[str, Form()],
    passphrase: Annotated[str | None, Form()] = None,
):
    """Sign in, or start a profile by naming one that does not exist yet.

    The passphrase field is only consulted for a profile that set one:
    everything saved before passphrases existed opens on the username alone,
    exactly as it did.
    """
    clean = profiles.clean_username(username)
    if not clean:
        return RedirectResponse(
            "/profile?error=Usernames+are+3-20+letters%2C+numbers%2C+-+or+_.",
            status_code=303,
        )

    with profiles.connect() as pconn:
        # Checked before the row is touched, so a failed attempt leaves no
        # trace on the profile it was aimed at.
        if not profiles.passphrase_opens(pconn, clean, profiles.clean_passphrase(passphrase)):
            return RedirectResponse(
                "/profile?error=That passphrase does not match this profile.",
                status_code=303,
            )
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
                "min_passphrase": profiles.MIN_PASSPHRASE,
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
    passphrase: Annotated[str | None, Form()] = None,
    school: Annotated[list[int] | None, Form()] = None,
):
    clean = profiles.clean_username(username)
    if not clean:
        return RedirectResponse(
            "/profile/new?error=Usernames+are+3-20+letters%2C+numbers%2C+-+or+_.",
            status_code=303,
        )

    secret = profiles.clean_passphrase(passphrase)
    problem = profiles.passphrase_problem(secret) if secret else None
    if problem:
        return RedirectResponse(f"/profile/new?error={problem}", status_code=303)

    with profiles.connect() as pconn:
        # Signing up under a name that is already protected must not be a way
        # around its passphrase: without this, anyone could retake a profile
        # they cannot open by filling this form in with the same username.
        if profiles.has_passphrase(pconn, clean):
            return RedirectResponse(
                "/profile?error=That username is taken and has a passphrase. "
                "Sign in with it below.",
                status_code=303,
            )
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
        if secret:
            profiles.set_passphrase(pconn, clean, secret)
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


@app.post("/profile/passphrase")
def update_passphrase(
    request: Request,
    passphrase: Annotated[str | None, Form()] = None,
):
    """Add or change the passphrase on the profile this browser is signed in to.

    The cookie is the only authority asked for, and it is the same one that
    opened the profile: a protected profile cannot be opened without its
    passphrase, so whoever holds this cookie either gave it or the profile had
    none to give. That is what lets a profile made before this existed — the
    seeded demo one included — be protected without being recreated.
    """
    username = _current_username(request)
    if not username:
        return RedirectResponse("/profile", status_code=303)

    secret = profiles.clean_passphrase(passphrase)
    if secret is None:
        return RedirectResponse(
            "/profile?error=Type a passphrase to set one.", status_code=303
        )
    problem = profiles.passphrase_problem(secret)
    if problem:
        return RedirectResponse(f"/profile?error={problem}", status_code=303)

    with profiles.connect() as pconn:
        profiles.set_passphrase(pconn, username, secret)
    return RedirectResponse("/profile", status_code=303)


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
