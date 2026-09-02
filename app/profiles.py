"""Saved profiles: a username, scores, an income bracket, and a shortlist.

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
    return conn


@dataclass(frozen=True)
class Profile:
    username: str
    sat_score: int | None
    act_score: int | None
    income_bracket: int | None
    shortlist: list[int]


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
