# Like for Like

Final project for the MBAxMS Python Bootcamp (Fall 2026).

A college comparison tool that answers what a school will actually cost you at your
family's income, and whether it does better than the schools it resembles.

See [PROPOSAL.md](PROPOSAL.md) for the full proposal.

## Status

Data scaffolding. The ingest runs and a 25-school sample database is reproducible; the
schema, API and front end are not built yet.

## Setup

Needs Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
```

## Building the sample database

```sh
uv run python scripts/import_ipeds.py
```

Pulls ten IPEDS endpoints for 2021 from the Urban Institute Education Data Explorer into
`data/likeforlike.db` (~3 MB, about 80 seconds, no API key). The database is gitignored —
it is rebuilt from this script, never committed.

2021 is the anchor year because it is the last year net price by income bracket exists,
so it is the only year where cost and outcomes can be read off the same cross-section.

```
scripts/schools.py        the 25-school working sample
scripts/import_ipeds.py   API -> SQLite, one table per endpoint, no cleaning
data/likeforlike.db       generated
```

Each endpoint lands in its own table with whatever columns the API returned. This is a
scratch schema for deciding what the real one should be, not the real one. An
`ingest_runs` table records the URL, row count and timestamp for each pull.

### Poking at it

```sh
sqlite3 data/likeforlike.db "SELECT name FROM sqlite_master WHERE type='table'"
```

Net price at each income bracket for one school:

```sql
SELECT s.inst_name, n.income_level, n.net_price
FROM sfa_grants_and_net_price n JOIN schools s USING (unitid)
WHERE s.inst_name LIKE 'Yale%' AND n.income_level BETWEEN 1 AND 5 AND n.type_of_aid = 9
ORDER BY n.income_level;
```

## Gotchas

Three that will bite anyone reading this data for the first time — all three are written
up in [PROPOSAL.md](PROPOSAL.md#known-limitations):

- **The API paginates at 10,000 rows.** Follow `next` and check the row count against the
  `count` the API reports, or large pulls truncate without an error.
- **Not every negative is missing.** `-1`, `-2` and `-3` are IPEDS sentinels, but a
  negative `net_price` is real — grant aid exceeding cost of attendance. Never drop a
  value just because it is below zero.
- **Rates are fractions.** `completion_rate_150pct` is 0.98, not 98.

## Team

- Martin Molinos ([@mmolinos95](https://github.com/mmolinos95))
- Rafael Sanchez ([@rasf120](https://github.com/rasf120))
- Jenny Tran ([@jtran-blip](https://github.com/jtran-blip))
- Rebecca Zhou ([@taiyangrebecca](https://github.com/taiyangrebecca))
