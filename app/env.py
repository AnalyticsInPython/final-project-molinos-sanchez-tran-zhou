"""Loading `.env` — four lines, so a dependency isn't worth it.

Only `MAPTILER_API_KEY` reads from it today, for the locator map on the
institution characteristics area. Get a free key at
https://cloud.maptiler.com/account/keys/, then copy `.env.example` to `.env`
and paste it in. The map figure just doesn't render without one — everything
else in the app works fine.
"""

import os
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load(path: Path = ENV_PATH) -> None:
    """`KEY=value` lines into the environment, without overriding what's already set."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())
