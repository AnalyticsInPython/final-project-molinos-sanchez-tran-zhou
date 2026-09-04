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

A passphrase is optional. The profile started as a username in a cookie and
nothing more, which was defensible when it held a shortlist and a test score;
it now holds race, income, and actual aid letters, and a username alone should
not open that. So a profile may carry a salted `hashlib.scrypt` hash, checked
on the way in — see `passphrase_opens`. A profile without one behaves exactly
as it did before, because every profile saved before this existed has none.

The cookie itself is still an unsigned username. That is a known limit, not an
oversight: the passphrase decides who may *obtain* the cookie, and hardening
the cookie itself is a separate change.
"""

import hashlib
import hmac
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app import codes

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

# The sex someone answers with, in IPEDS's own codes, so an answer here joins
# straight onto `admissions_enrollment.sex` and can drive a cut. Read out of
# `app/codes.py` rather than written again, so the word on the questionnaire
# and the word on the comparison card cannot drift apart — they had, and that
# is what this change fixes.
#
# **A third option used to be offered here and has been withdrawn.** Code 0,
# "Another identity, or prefer not to say", was stored as unset, on the
# argument that a form which forces a person into a box the data does not have
# is worse than a form that admits the limit. That is reversed: IPEDS carries
# two sex categories and no third row, so code 0 could never be joined to
# anything and never drove a figure, and the blank "Prefer not to say" option
# both selects already lead with says the same thing without minting a code
# that means nothing to the data. Answering stays optional; only the extra
# code is gone.
#
# A profile still holding 0 from before reads as unset — `GENDERS.get(0)` is
# None, so no label, no cut, no crash — and saving the form again clears it,
# because `clean_choice` discards a code that is not offered. Held by
# tests/test_questionnaire.py and tests/test_cuts.py.
#
# The constant is `GENDERS` and the stored column and `Profile` field are
# `gender` because renaming a SQLite column needs a migration and four modules
# would move with it. The word the reader sees is Sex, everywhere.
GENDERS = dict(codes.SEX)

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
    # Holds the sex code. The column keeps the name it was created with, and
    # renaming it would need a migration every saved profile has to survive;
    # the reader-facing word is Sex. See GENDERS above.
    "gender": "INTEGER",
    "stage": "TEXT",
    # Salt and hash together in one self-describing string; see
    # `hash_passphrase`. NULL — the value every existing row gets when this
    # column is added — means "no passphrase", which is why nothing breaks.
    "passphrase_hash": "TEXT",
}

# scrypt work factors, stored beside each hash so a hash made today still
# verifies if these change. n = 2**14 is the interactive parameter set from
# the scrypt paper and needs 128 * r * n = 16 MB, which fits under the 32 MB
# ceiling `hashlib.scrypt` applies by default (maxmem=0); n = 2**15 raises
# "memory limit exceeded" instead, so this is a real bound rather than a
# taste. Checked: one hash takes well under a tenth of a second here.
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16
KEY_BYTES = 32

# Short enough that a person will actually set one, long enough to be worth
# storing. The cap is there so a hand-posted form cannot hand scrypt a
# megabyte of input to chew on.
MIN_PASSPHRASE = 8
MAX_PASSPHRASE = 200

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    username        TEXT PRIMARY KEY,
    sat_score       INTEGER,
    act_score       INTEGER,
    income_bracket  INTEGER,
    created_at      TEXT NOT NULL
);

-- What a school actually offered this person. Only ever collected from
-- someone who has offers in hand, which is why it is gated on `stage` rather
-- than asked of everyone: a student still deciding where to apply has nothing
-- to put here, and asking implies they should.
CREATE TABLE IF NOT EXISTS aid_offers (
    username    TEXT NOT NULL REFERENCES profiles(username),
    unitid      INTEGER NOT NULL,
    net_offer   INTEGER,
    grant_aid   INTEGER,
    loan_aid    INTEGER,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (username, unitid)
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
    # The sex code, named for the column it comes from. Shown as Sex.
    gender: int | None = None
    stage: str | None = None
    # Whether a passphrase is set, never the hash itself. The hash has no
    # business in a template context, and the page only ever needs to know
    # which of the two things to say about this profile.
    has_passphrase: bool = False

    @property
    def name(self) -> str:
        """What to call them. The username is a fallback, never blank."""
        return self.display_name or self.username

    @property
    def race_label(self) -> str | None:
        return RACES.get(self.race)

    @property
    def gender_label(self) -> str | None:
        """The sex answer as a word, or None for unset — including a profile
        still holding the withdrawn code 0, which has no label to give."""
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
        has_passphrase=bool(row["passphrase_hash"]),
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


def clean_passphrase(value: str | None) -> str | None:
    """A typed passphrase, or None when the field was left blank.

    Deliberately does *not* trim or normalise a passphrase that has content:
    a secret must hash to the same bytes the next time the same person types
    the same thing, and quietly stripping a character they meant to include
    would lock them out of their own profile. A field holding only whitespace
    is treated as blank, because nobody means that.
    """
    if value is None or not value.strip():
        return None
    return value


def passphrase_problem(passphrase: str) -> str | None:
    """Why this passphrase cannot be used, in words, or None if it can.

    Returns the sentence rather than a bool so the route can hand it to the
    template's existing `error` slot — the same shape as the username message
    the profile page already knows how to show.
    """
    if len(passphrase) < MIN_PASSPHRASE:
        return f"A passphrase needs at least {MIN_PASSPHRASE} characters."
    if len(passphrase) > MAX_PASSPHRASE:
        return f"A passphrase can be at most {MAX_PASSPHRASE} characters."
    return None


def hash_passphrase(passphrase: str) -> str:
    """Salt and hash a passphrase into the one string the column holds.

    The format is `scrypt$n$r$p$salt$key`, all hex, self-describing on
    purpose: the work factors travel with the hash, so raising them later
    does not strand every profile saved before the change. The salt is fresh
    per call from `secrets.token_bytes`, so two people who choose the same
    passphrase do not share a hash — verified in the tests.
    """
    salt = secrets.token_bytes(SALT_BYTES)
    key = hashlib.scrypt(
        passphrase.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=KEY_BYTES,
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${key.hex()}"


def verify_passphrase(stored: str | None, passphrase: str | None) -> bool:
    """Whether `passphrase` is the one behind `stored`.

    Compared with `hmac.compare_digest` rather than `==` so the check takes
    the same time whichever byte differs first. Anything unreadable in the
    column — a truncated row, a hash from a scheme this build does not know —
    verifies against nothing rather than raising: a corrupt hash must fail
    closed, and the tests hold that.
    """
    if not stored or passphrase is None:
        return False
    try:
        scheme, n, r, p, salt_hex, key_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = bytes.fromhex(key_hex)
        candidate = hashlib.scrypt(
            passphrase.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, expected)


def set_passphrase(conn: sqlite3.Connection, username: str, passphrase: str | None) -> None:
    """Set, change, or (with None) remove the passphrase on a profile.

    Only the hash is ever written; the passphrase itself is not stored, not
    logged, and not put on the Profile that reaches a template.
    """
    conn.execute(
        "UPDATE profiles SET passphrase_hash = ? WHERE username = ?",
        (hash_passphrase(passphrase) if passphrase is not None else None, username),
    )
    conn.commit()


def has_passphrase(conn: sqlite3.Connection, username: str) -> bool:
    """Whether that profile is protected. False for a name nobody has taken."""
    row = conn.execute(
        "SELECT passphrase_hash FROM profiles WHERE username = ?", (username,)
    ).fetchone()
    return bool(row and row["passphrase_hash"])


def passphrase_opens(
    conn: sqlite3.Connection, username: str, passphrase: str | None
) -> bool:
    """Whether this passphrase may open that profile.

    True for a profile that has no hash, whatever was typed — that is the
    compatibility promise this whole feature rests on, and it is checked here
    rather than in the route so no caller can forget it. True as well for a
    username nobody has taken, because typing a new name is still how a
    profile gets created.

    A wrong passphrase therefore only ever fails for a profile that set one,
    which does tell an outsider that the name exists and is protected. That is
    the accepted cost of a form that has to say something useful when the
    passphrase is wrong.
    """
    row = conn.execute(
        "SELECT passphrase_hash FROM profiles WHERE username = ?", (username,)
    ).fetchone()
    if row is None or not row["passphrase_hash"]:
        return True
    return verify_passphrase(row["passphrase_hash"], passphrase)


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


@dataclass(frozen=True)
class Offer:
    """One school's actual offer, as the student received it."""

    unitid: int
    net_offer: int | None
    grant_aid: int | None
    loan_aid: int | None

    @property
    def gift_share(self) -> float | None:
        """How much of the package is money that is not repaid.

        The number two offers of the same headline size can differ on most:
        $30,000 of grant and $30,000 of loan are not the same offer, and this
        is the only field that tells them apart.
        """
        total = (self.grant_aid or 0) + (self.loan_aid or 0)
        if not total:
            return None
        return (self.grant_aid or 0) / total


def set_offer(
    conn: sqlite3.Connection,
    username: str,
    unitid: int,
    *,
    net_offer: int | None,
    grant_aid: int | None,
    loan_aid: int | None,
) -> None:
    """Record or replace what one school offered. All-None clears the row."""
    if net_offer is None and grant_aid is None and loan_aid is None:
        conn.execute(
            "DELETE FROM aid_offers WHERE username = ? AND unitid = ?",
            (username, unitid),
        )
    else:
        conn.execute(
            "INSERT INTO aid_offers (username, unitid, net_offer, grant_aid, loan_aid, "
            "updated_at) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(username, unitid) DO UPDATE SET "
            "net_offer = excluded.net_offer, grant_aid = excluded.grant_aid, "
            "loan_aid = excluded.loan_aid, updated_at = excluded.updated_at",
            (
                username,
                unitid,
                net_offer,
                grant_aid,
                loan_aid,
                datetime.now(UTC).isoformat(),
            ),
        )
    conn.commit()


def offers(conn: sqlite3.Connection, username: str) -> dict[int, Offer]:
    rows = conn.execute(
        "SELECT unitid, net_offer, grant_aid, loan_aid FROM aid_offers WHERE username = ?",
        (username,),
    ).fetchall()
    return {
        row["unitid"]: Offer(
            row["unitid"], row["net_offer"], row["grant_aid"], row["loan_aid"]
        )
        for row in rows
    }


def clean_money(value: str | None, *, cap: int = 200_000) -> int | None:
    """A dollar figure from a form field, or None.

    Accepts what people actually type — "$42,500" — and rejects the rest.
    Zero is kept, because a full ride is a real offer and the most interesting
    one on the page.
    """
    if value is None or not str(value).strip():
        return None
    cleaned = str(value).replace("$", "").replace(",", "").strip()
    try:
        amount = int(round(float(cleaned)))
    except (TypeError, ValueError):
        return None
    return amount if 0 <= amount <= cap else None
