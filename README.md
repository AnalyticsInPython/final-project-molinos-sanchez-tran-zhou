# Like for Like

Final project for the MBAxMS Python Bootcamp (Fall 2026).

A college comparison tool that answers what a school will actually cost you at your
family's income, and whether it does better than the schools it resembles.

- [PROPOSAL.md](PROPOSAL.md) — the full proposal, data sources and known limitations
- [ROADMAP.md](ROADMAP.md) — what is built, what is next, and what we decided against
- [METRICS-REVIEW.md](METRICS-REVIEW.md) — whether the numbers we show are the ones worth knowing
- [SCOPE.md](SCOPE.md) — where the seven comparison areas landed, and **three open questions
  the group needs to answer** before we build screens

## Status

Four areas wired in — **student financial aid**, **selectiveness**, **enrollment**
(race/ethnicity, gender, international share), and **institution characteristics** (locator
map, founding year and motto from Wikidata) — over a FastAPI app with a searchable school
picker. A fifth, **after graduation** (post-grad earnings and debt via College Scorecard), is
built and tested but deliberately not wired in — see `app/areas/__init__.py` for why. The
ingest pulls a range of years per endpoint, and each area shows the newest year it actually
has, which is not the same year for every area.

## Setup

Needs Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
```

## Building the sample database

```sh
uv run python scripts/import_ipeds.py
uv run python scripts/import_eada.py
```

The first script pulls fourteen IPEDS endpoints from the Urban Institute Education Data
Explorer, plus two non-IPEDS tables — post-graduation earnings and debt from the College
Scorecard API, and founding year and motto from Wikidata — into `data/likeforlike.db`.

The second adds athletics from a **third** source: EADA, the Equity in Athletics
Disclosure Act collection. IPEDS has no athletics participation or spending at all, only
membership flags. Run it after the IPEDS ingest — that one drops and recreates
`ingest_runs`, so running it afterwards erases EADA's year metadata (the app falls back to
the table's own years, so it degrades rather than breaks).

The database is gitignored — it is rebuilt from these scripts, never committed.

**Each IPEDS endpoint gets a range of years, not one anchor year.** Comparison areas pull ten
years (2015–2024) so a trend can be drawn; reference tables pull four. Every endpoint-year
asked for is recorded in `ingest_runs`, *including the ones that came back empty* — that is
how the app tells "IPEDS publishes nothing newer" apart from "we have not loaded it yet",
without anyone maintaining a flag by hand. Net price stops at 2021 and says so; admissions
runs to 2024 and does not warn.

`--years N` trims every IPEDS range to its N most recent years for a faster rebuild.

**College Scorecard and Wikidata are the odd ones out: a snapshot, not a range.** Scorecard's
three fields are three different entry/completion cohorts rather than one collection year —
see `outcomes.py`'s docstring for exactly which. Wikidata has no year at all, just whatever is
on the page now, joined on `wdt:P1771` — Wikidata's own IPEDS-UNITID property — rather than by
name, so a school like Hunter College can't get matched into a query meant for Caltech. No API
key is required to build the database: Scorecard falls back to the public `DEMO_KEY`, which is
rate-limited but enough for this 25-school sample, and Wikidata's query service needs none at
all. Copy `.env.example` to `.env` if you want a `COLLEGE_SCORECARD_API_KEY` of your own (free:
<https://api.data.gov/signup/>), or a `MAPTILER_API_KEY` for the locator map on institution
characteristics (free: <https://cloud.maptiler.com/account/keys/>) — the map is the one
feature that doesn't degrade gracefully without a key.

```
scripts/schools.py        the 25-school working sample
scripts/import_ipeds.py   API -> SQLite, one table per endpoint, no cleaning
data/likeforlike.db       generated
scripts/import_eada.py    EADA athletics -> SQLite, one bulk file per survey year
app/areas/                one module per comparison area
app/notices.py            what to tell the reader the figures do not cover
```

## Two views

Without a year range the page is a **snapshot** of the newest year each area has.
Ask for a range and every area switches to a **trend**: one line per school per metric,
drawn against a single window shared by every area on the page. The shared axis is the
point — it is what shows a reader that admissions reaches 2024 while net price stopped
in 2021, since both are drawn against the same years and one of them visibly stops early.

## Running the app

```sh
uv run uvicorn app.main:app --reload --port 8001
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
- **Every table holds several years, so every query needs a year filter.** Without one a
  pivot silently averages a decade and still returns a plausible number. Areas take the year
  as an argument for exactly this reason.
- **The API's columns and codes drift between years.** `directory` gains the Carnegie 2025
  classification partway along the range, so table columns are the union across years rather
  than whatever the first row carried. The `sex` dimension goes `[1, 2, 99]` through 2021,
  gains `9` in 2022 and `3` in 2023 — pin the total (`99`) and never sum the parts, or the
  meaning of a series changes halfway along it.
- **A null Scorecard debt figure means too few borrowers to report, not zero.** NSLDS
  suppresses `median_debt.completers.overall` below a minimum cohort size (Caltech, in this
  sample) — a different missingness rule from IPEDS's -1/-2/-3 sentinels above.

## Team

- Martin Molinos ([@mmolinos95](https://github.com/mmolinos95))
- Rafael Sanchez ([@rasf120](https://github.com/rasf120))
- Jenny Tran ([@jtran-blip](https://github.com/jtran-blip))
- Rebecca Zhou ([@taiyangrebecca](https://github.com/taiyangrebecca))
