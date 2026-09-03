"""Create or reset `maya`, the sample student the Friday demo signs in as.

    uv run python scripts/seed_demo.py

The account is created live on stage as `maya-live` — creating it *is* the
demo. This profile is the fallback that already exists, so a typo in the first
minute is not the end of the run, and so a wiped `data/profiles.db` is back in
a second. Her answers are the table under *The sample student* in ROADMAP.md,
chosen so that every question on the questionnaire moves a number she will see
and no cut she triggers is suppressed at any of her five schools.

**Idempotent, by resetting rather than topping up.** Running it twice leaves
one profile holding exactly these answers and exactly these five schools in
this order. The shortlist is emptied and rebuilt every run because
`profiles.add_school` ignores a school already on the list and the list is
ordered by when a school was added: a stale sixth school from an earlier run
would otherwise survive, and a school added out of order would stay out of
order. `set_scores` and `set_details` each replace their whole group of
fields, so every field is passed on every run, including the ACT she does not
have.

Writes to `data/profiles.db` — the profile store, created lazily by
`app/profiles.py`, and the only state this app keeps. `--db PATH` points it at
another database, which is how `tests/test_seed_demo.py` runs it. Nothing here
reads or touches `data/likeforlike.db`, the read-only IPEDS build artifact, so
this is safe to run before the ingest scripts have ever been run.
"""

import argparse
import sys
from pathlib import Path
from urllib.parse import urlencode

# `pyproject.toml` sets `package = false`, so there is no installed `app` to
# import, and running a file in `scripts/` puts that directory on the path
# rather than the repository root. Tests get the root for free from pytest;
# this line is what makes the command in the docstring work.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import profiles  # noqa: E402
from app.areas.financial_aid import BANDS  # noqa: E402
from app.schools import SHORT_NAMES, brand_color  # noqa: E402

USERNAME = "maya"

# The sample student, field by field. The codes are IPEDS's own, as
# `profiles.RACES` and `profiles.GENDERS` hold them, and the labels below are
# read back out of those maps rather than repeated here.
DISPLAY_NAME = "Maya"
STAGE = "applying"  # Deciding where to apply: leads with selectiveness
HOME_STATE = "CA"  # Berkeley in-state and Michigan out-of-state, one screen
INCOME_BRACKET = 2  # $30,001-48,000, the band where the five disagree most
SAT = 1480
ACT = None  # She has an SAT and no ACT; set_scores replaces both
GPA = 3.8  # Saved, compared to nothing, and the form says so
RACE = 3  # Hispanic or Latino: >= 30 in the cohort at all five schools
GENDER = 2  # Woman: every school reports admits by sex

# Berkeley, Stanford, MIT, Carnegie Mellon, Michigan — in the order the
# comparison should read them, which is the order they are added in. Five is
# also `main.MAX_SCHOOLS`, the cap on one comparison, so the whole shortlist
# fits on the compare page with nothing dropped.
SHORTLIST = [110635, 243744, 166683, 211440, 170976]


def seed(conn) -> profiles.Profile:
    """Write the sample student's answers over whatever is already there."""
    profiles.get_or_create(conn, USERNAME)
    profiles.set_scores(
        conn, USERNAME, sat=SAT, act=ACT, income_bracket=INCOME_BRACKET
    )
    profiles.set_details(
        conn,
        USERNAME,
        display_name=DISPLAY_NAME,
        gpa=GPA,
        home_state=HOME_STATE,
        race=RACE,
        gender=GENDER,
        stage=STAGE,
    )

    for unitid in profiles.get(conn, USERNAME).shortlist:
        profiles.remove_school(conn, USERNAME, unitid)
    for unitid in SHORTLIST:
        profiles.add_school(conn, USERNAME, unitid)

    return profiles.get(conn, USERNAME)


def compare_url(unitids: list[int]) -> str:
    """The compare link for a shortlist, as `profile.html` builds it.

    Same shape, same order, same colours — `school=` and `color=` in matched
    pairs, the hash of a hex colour percent-encoded — because the demo either
    clicks *Compare your saved schools* on the profile page or pastes this,
    and the two must land on identical pages. Every school here has a brand
    colour, so `brand_color`'s palette fallback never fires.
    """
    pairs = []
    for index, unitid in enumerate(unitids):
        pairs.append(("school", unitid))
        pairs.append(("color", brand_color(unitid, index)))
    return "/compare?" + urlencode(pairs)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create or reset the `maya` demo profile.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=profiles.DB_PATH,
        help="profile database to write to (default: %(default)s)",
    )
    args = parser.parse_args()

    with profiles.connect(args.db) as conn:
        profile = seed(conn)

    print(f"Seeded `{profile.username}` in {args.db}\n")
    print(f"  Name           {profile.name}")
    print(f"  Stage          {profile.stage_label}")
    print(f"  Home state     {profile.home_state}")
    print(f"  Family income  band {profile.income_bracket}, {BANDS[profile.income_bracket]}")
    print(f"  SAT / GPA      {profile.sat_score} / {profile.gpa}")
    print(f"  Race           {profile.race_label}")
    print(f"  Gender         {profile.gender_label}")
    print(f"\n  Shortlist ({len(profile.shortlist)}), in order:")
    for position, unitid in enumerate(profile.shortlist, start=1):
        color = brand_color(unitid, position - 1)
        print(f"    {position}. {unitid}  {SHORT_NAMES.get(unitid, '?'):<15} {color}")

    print("\nCompare your saved schools:\n")
    print(f"  {compare_url(profile.shortlist)}")


if __name__ == "__main__":
    main()
