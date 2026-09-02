"""Saved profiles: who someone is, what they have, and where they are looking.

Extended from scores and a shortlist to the answers a sign-up questionnaire
collects. Every added field earns its place by changing a figure the app
already shows — see FIELDS below. Nothing here is required, and a profile
with every field blank behaves exactly as it did before.

Lives apart from `app/db.py` on purpose. That module opens
`data/likeforlike.db` **read-only** — it is a build artifact of
`scripts/import_ipeds.py`, never state, and the comment there says so. A
profile is the first thing in this app that is actually state, so it gets its
own file, in `data/profiles.db`.

No password. A profile is a username in a cookie, nothing more — a
deliberate choice for a class project comparing public data, not a system
guarding anything a stranger couldn't already ask for by name.
"""

import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "profiles.db"

# A shortlist can hold more schools than a single comparison can show — the
# comparison view already caps at MAX_SCHOOLS in app/main.py. This is a wider
# ceiling on the list itself, not the same number by coincidence.
MAX_SHORTLIST = 10

USERNAME = re.compile(r"^[a-z0-9][a-z0-9_-]{1,18}[a-z0-9]$")

# IPEDS race codes, so an answer here joins straight onto `grad_rates.race`
# and can be used to show completion rates for students of that background
# rather than only the headline. 99 is the published total and is not an
# identity, so it is not offered.
RACES = {
    1: "White",
    2: "Black or African American",
    3: "Hispanic or Latino",
    4: "Asian",
    5: "American Indian or Alaska Native",
    6: "Native Hawaiian or Pacific Islander",
    7: "Two or more races",
    8: "Nonresident",
    9: "Prefer not to say",
}

# IPEDS records sex as men and women only, so those are the codes that can be
# joined to outcome data. A third option is offered and stored as unset,
# because a form that forces a person into a box the data does not have is
# worse than a form that admits the limit.
GENDERS = {1: "Man", 2: "Woman", 0: "Another identity, or prefer not to say"}

# Where someone lives decides whether a public school's in-state or
# out-of-state tuition applies, and the two differ by $38,000 at Michigan.
# This is the field that most changes what the app tells a given person.
STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI",
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN",
    "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH",
    "OK", "OR", "PA", "PR", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA",
    "WA", "WV", "WI", "WY",
]

# Which question someone is actually asking, which decides what leads the
# page: a shortlist of maybes wants selectiveness first, a folder of offers
# wants cost first.
STAGES = {
    "applying": "Deciding where to apply",
    "choosing": "Choosing between offers I have",
}

# Columns added after the first release. SQLite cannot add them inside
# CREATE TABLE IF NOT EXISTS, so `connect` brings an existing profile
# database up to date rather than asking anyone to delete theirs.
ADDED_COLUMNS = {
    "display_name": "TEXT",
    "gpa": "REAL",
    "home_state": "TEXT",
    "race": "INTEGER",
    "gender": "INTEGER",
    "stage": "TEXT",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    username        TEXT PRIMARY KEY,
    sat_score       INTEGER,
    act_score       INTEGER,
    income_bracket  INTEGER,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profile_schools (
    username    TEXT NOT NULL REFERENCES profiles(username),
    unitid      INTEGER NOT NULL,
    added_at    TEXT NOT NULL,
    PRIMARY KEY (username, unitid)
);
"""


def clean_username(value: str | None) -> str | None:
    """A user-supplied name, or None if it doesn't look like one.

    Lowercased and length- and character-bounded before it reaches a cookie
    or a query — the same validate-on-the-way-in posture as
    `schools.clean_color`, which exists because a query param here once went
    straight into an attribute unescaped.
    """
    if not value:
        return None
    candidate = value.strip().lower()
    return candidate if USERNAME.match(candidate) else None


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    """Open the profile store read-write, creating it if this is the first run.

    Unlike the IPEDS database, there is no separate ingest step — the schema
    is created lazily here, the first time anything asks for it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)

    # Bring an older profile database forward. Adding a column is the only
    # migration this app needs, and doing it here keeps the lazy-schema
    # promise above: nobody has to run a step or drop their saved data.
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(profiles)")}
    for column, kind in ADDED_COLUMNS.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE profiles ADD COLUMN {column} {kind}")
    conn.commit()
    return conn


@dataclass(frozen=True)
class Profile:
    username: str
    sat_score: int | None
    act_score: int | None
    income_bracket: int | None
    shortlist: list[int]
    display_name: str | None = None
    gpa: float | None = None
    home_state: str | None = None
    race: int | None = None
    gender: int | None = None
    stage: str | None = None

    @property
    def name(self) -> str:
        """What to call them. The username is a fallback, never blank."""
        return self.display_name or self.username

    @property
    def race_label(self) -> str | None:
        return RACES.get(self.race)

    @property
    def gender_label(self) -> str | None:
        return GENDERS.get(self.gender)

    @property
    def stage_label(self) -> str | None:
        return STAGES.get(self.stage)


def _shortlist(conn: sqlite3.Connection, username: str) -> list[int]:
    rows = conn.execute(
        "SELECT unitid FROM profile_schools WHERE username = ? ORDER BY added_at",
        (username,),
    ).fetchall()
    return [row["unitid"] for row in rows]


def get(conn: sqlite3.Connection, username: str) -> Profile | None:
    row = conn.execute(
        "SELECT * FROM profiles WHERE username = ?", (username,)
    ).fetchone()
    if row is None:
        return None
    return Profile(
        username=row["username"],
        sat_score=row["sat_score"],
        act_score=row["act_score"],
        income_bracket=row["income_bracket"],
        shortlist=_shortlist(conn, username),
        display_name=row["display_name"],
        gpa=row["gpa"],
        home_state=row["home_state"],
        race=row["race"],
        gender=row["gender"],
        stage=row["stage"],
    )


def get_or_create(conn: sqlite3.Connection, username: str) -> Profile:
    """The named profile, creating an empty one on first visit.

    Idempotent: a second call for the same username is a no-op on the row
    that already exists, so a stale cookie for a profile that's still around
    can't reset scores someone already saved.
    """
    conn.execute(
        "INSERT OR IGNORE INTO profiles (username, created_at) VALUES (?, ?)",
        (username, datetime.now(UTC).isoformat()),
    )
    conn.commit()
    return get(conn, username)


def set_scores(
    conn: sqlite3.Connection,
    username: str,
    *,
    sat: int | None,
    act: int | None,
    income_bracket: int | None,
) -> None:
    """Replace the saved scores. A None clears the field back to unset.

    Callers pass already-validated values — a blank or out-of-range field is
    resolved to None before this is called, the same way a missing IPEDS
    figure is a first-class state rather than an error everywhere else in
    this app.
    """
    conn.execute(
        "UPDATE profiles SET sat_score = ?, act_score = ?, income_bracket = ? "
        "WHERE username = ?",
        (sat, act, income_bracket, username),
    )
    conn.commit()


def add_school(conn: sqlite3.Connection, username: str, unitid: int) -> None:
    """Add a school to the shortlist, silently, up to MAX_SHORTLIST.

    Adding a school already on the list, or adding past the cap, is a no-op
    rather than an error — there is no wrong way to click a button twice.
    """
    if unitid in _shortlist(conn, username):
        return
    if len(_shortlist(conn, username)) >= MAX_SHORTLIST:
        return
    conn.execute(
        "INSERT OR IGNORE INTO profile_schools (username, unitid, added_at) "
        "VALUES (?, ?, ?)",
        (username, unitid, datetime.now(UTC).isoformat()),
    )
    conn.commit()


def remove_school(conn: sqlite3.Connection, username: str, unitid: int) -> None:
    conn.execute(
        "DELETE FROM profile_schools WHERE username = ? AND unitid = ?",
        (username, unitid),
    )
    conn.commit()


def clean_name(value: str | None) -> str | None:
    """A display name, trimmed and bounded. Blank is a real answer."""
    if not value:
        return None
    name = " ".join(value.split())[:60]
    return name or None


def clean_choice(value, options) -> int | str | None:
    """One of a fixed set, or None. Anything else is discarded silently.

    The questionnaire's selects all resolve through here, so a hand-posted
    form cannot put a value into the database that the labels above cannot
    render — the row would display as blank and look like a bug.
    """
    if value in (None, "", "none"):
        return None
    if isinstance(next(iter(options), None), int):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return None
    return value if value in options else None


def clean_gpa(value: str | None) -> float | None:
    """A grade point average on the 0-4.0 scale, or None.

    Stored for the person's own reference only. IPEDS publishes no admitted
    GPA for any institution, so unlike a test score this cannot be set
    against a school's range — the form says so rather than implying a
    comparison the data cannot support.
    """
    if not value or not str(value).strip():
        return None
    try:
        gpa = round(float(value), 2)
    except (TypeError, ValueError):
        return None
    return gpa if 0 <= gpa <= 4.0 else None


def set_details(
    conn: sqlite3.Connection,
    username: str,
    *,
    display_name: str | None,
    gpa: float | None,
    home_state: str | None,
    race: int | None,
    gender: int | None,
    stage: str | None,
) -> None:
    """Replace the questionnaire answers. A None clears a field back to unset."""
    conn.execute(
        "UPDATE profiles SET display_name = ?, gpa = ?, home_state = ?, "
        "race = ?, gender = ?, stage = ? WHERE username = ?",
        (display_name, gpa, home_state, race, gender, stage, username),
    )
    conn.commit()
