# DEMO.md — the Friday walkthrough, screen by screen

The running order, the exact URLs, the checklist and the fallbacks for the demo on
**Friday 4 Sep 2026**. Everything below is [ROADMAP.md](ROADMAP.md)'s plan for the
demo, gathered into one file you can hold on a phone while someone else drives.
The roadmap remains the source; this file is the script.

**The demo profile is seeded, not typed.** `scripts/seed_demo.py` creates or resets
`maya` in `data/profiles.db` — display name Maya, *Deciding where to apply*, home
state CA, family income band 2 ($30,001–48,000), SAT 1480, GPA 3.8, Hispanic or
Latino, Female — with a shortlist of exactly five schools in this order: **UC
Berkeley, Stanford, MIT, Carnegie Mellon, Michigan**. Run it as often as you like:

```
uv run python scripts/seed_demo.py
```

It resets rather than tops up, so a second run leaves one profile with exactly those
answers and exactly those five schools in that order, and a stale sixth school from
an earlier run is removed. It prints the compare link for the five in their brand
colours, which is the URL under *Compare* below and the same one the picker builds
after **Use my saved schools**. `--db PATH` points it at another database; the default is `data/profiles.db`.

The account is still created **live on stage as `maya-live`** — creating it is the
demo. `maya` is the fallback that already exists if the live sign-up goes wrong.

## Minute by minute

Nine minutes, four voices. Each person presents the part they can be asked about.

| Time | Screen | What is said | Who |
| --- | --- | --- | --- |
| 0:00–0:45 | Landing page | The two questions a family cannot answer from a ranking site: what will it cost *us*, and is the graduation rate the school or the students it admits. Federal data answers both; nobody makes it easy. | 1 |
| 0:45–2:15 | Create an account | Fill the questionnaire live as Maya. Say out loud that every question is there because it changes a number, and point at the GPA line that admits it changes nothing. Pick the five schools. | 1 |
| 2:15–2:45 | Profile | Answers saved; shortlist of five in brand colours; *Pick areas for your saved schools* goes back to the picker, where **Use my saved schools** fills all five in one click and she still chooses the areas and the years before Compare. | 1 |
| 2:45–4:15 | Financial aid | The band chart, then **Tailor data for me**: Maya's band lit up, −$2,251 to $15,139 at the same income. The sticker that applies to her: Berkeley in-state against Michigan out-of-state. The staleness notice: 2021 figures, published costs up 8% since, and why we do not extrapolate. Flip to *All available years* on this card only: cheap for the poor, dearer for the rich, every year. | 2 |
| 4:15–5:15 | Selectiveness | **Tailor**: admit rate for women beside everyone, five schools, all above the total. Why "everyone" is the published total and never the sum — IPEDS added sex codes in 2022. | 3 |
| 5:15–6:15 | Retention and graduation | **Tailor**: Hispanic completion beside that survey's own total. Carnegie Mellon −10, Berkeley −7, MIT and Stanford within a point. The under-30 rule, and the rule that we describe the school, never the student's odds. | 3 |
| 6:15–7:00 | After graduation, athletics, characteristics | Scroll, do not dwell: earnings and debt, the $0 that is real, the map and the highlights strip. | 4 |
| 7:00–8:00 | "How we built it" card | Four people, one agent each, one branch each, PRs reviewed by a human. 284 tests, ruff. The three traps the agent walked into that we caught: the API paginates at 10,000 and looks like it does not; a negative net price is real and the sentinels are −1/−2/−3; a race chart drawn against a total from a different survey. | 4 |
| 8:00–8:45 | Same card | What we proposed and changed: peer-group outcomes need a stratified sample, and 25 selective schools have no spread, so we pivoted to cuts — the same idea, the reader's own group instead of a synthetic peer. What is next. Questions. | 1 |

A rehearsal tonight decides whether the trend flip at 3:45 stays. If the demo runs
long, it is the first thing cut; the snapshot already carries the staleness notice.

## The URLs, in order

Written for `--port 8001`, the port on the checklist below. The demo **starts signed
out** on the landing page; the sign-up at 0:45 is what signs the presenter in, and
every URL from *Compare* onward needs that cookie for the tailoring to fire.

| Time | Screen | URL |
| --- | --- | --- |
| 0:00 | Landing page | `http://127.0.0.1:8001/` |
| 0:45 | Create an account | `http://127.0.0.1:8001/profile/new` |
| 2:15 | Profile | `http://127.0.0.1:8001/profile` |
| 2:45 | Compare the five | the compare URL below |
| 2:45–6:15 | Financial aid, selectiveness and retention, tailored | the tailored URL below |
| 3:45 | Financial aid on its own, all available years | the trend URL below |

**Compare** — five schools, brand colours, every area. This is the every-area page,
kept as a fallback and printed by the seed script. On stage the route is the picker:
*Pick areas for your saved schools* on the profile, then **Use my saved schools**,
then choose the areas and years and press Compare.

```
http://127.0.0.1:8001/compare?school=110635&color=%23003262&school=243744&color=%238c1515&school=166683&color=%23a31f34&school=211440&color=%23c41230&school=170976&color=%2300274c
```

**Tailored** — the same page with *Tailor data for me* already on for the three
cards the script dwells on. On the day the presenter clicks the button on each card;
this URL is the way back to that state if a click goes astray:

```
http://127.0.0.1:8001/compare?school=110635&color=%23003262&school=243744&color=%238c1515&school=166683&color=%23a31f34&school=211440&color=%23c41230&school=170976&color=%2300274c&tailor=financial_aid&tailor=selectiveness&tailor=retention
```

Maya's race, sex, income band and state are **not** in that URL and never are — it
says `tailor=<area>` and the server reads the profile. A shared link tailors to
whoever opens it. That is the answer to the question in the table at the bottom.

`tailor=selectiveness` and `tailor=retention` draw their cuts today. `tailor=financial_aid`
is written for the aid-tailoring branch (item 1 under *What is missing* in ROADMAP.md)
and does nothing until that merges — until then the financial aid card renders no
*Tailor data for me* button, and the extra parameter is ignored rather than an error.
Re-check this line after the merge.

**Trend** — financial aid alone, 2015 to 2021, the flip at 3:45. One area, seven
years, so the chart is a line rather than a snapshot:

```
http://127.0.0.1:8001/compare?school=110635&color=%23003262&school=243744&color=%238c1515&school=166683&color=%23a31f34&school=211440&color=%23c41230&school=170976&color=%2300274c&area=financial_aid&year=2015&year=2016&year=2017&year=2018&year=2019&year=2020&year=2021
```

If the demo runs long this is the first thing cut, per the rehearsal note above.

## Demo day — Friday morning

- [ ] `git pull`; `uv sync`; `uv run pytest` — 284 or more, all green.
- [ ] `.env` present with the MapTiler key; `ls data/*.db` shows all three databases.
- [ ] `uv run python scripts/seed_demo.py`; open `/profile`, log in as `maya`, see five schools.
- [ ] Log out. The demo starts signed out.
- [ ] `uv run uvicorn app.main:app --port 8001` in a terminal that stays visible in the dock, not in an IDE pane.
- [ ] Browser: one window, one tab, 125% zoom, bookmarks bar hidden, notifications off, other apps closed. Window at the projector's resolution, not the laptop's.
- [ ] Open `DEMO.md` on a phone or second screen for the URLs and the numbers.
- [ ] `docs/demo/` screenshots opened in a second tab, in case.
- [ ] Every presenter has the three "how does this work" answers for their two minutes.

## Fallbacks

- **Typo or hesitation in the live sign-up:** finish it anyway; if it fails, log in as
  `maya` and say why she exists.
- **Server dies:** the terminal is visible; restart is one command, ten seconds.
- **Laptop dies:** the screenshots in `docs/demo/` on a second machine, narrated.
- **Running long at 6:15:** skip the scroll through the last three areas and go to
  the build card. At 7:30, skip the "what we changed" beat and take questions.
- **The map does not load:** say "needs a key" and keep going; the highlights strip is
  above it.

## Questions we expect, and where the answer lives

The grader will ask one. Each presenter owns the ones in their segment.

| Question | Answer, in one breath | Where |
| --- | --- | --- |
| Why is net price 2021 when it is 2026? | IPEDS publishes nothing newer; the ingest asked for 2022–24 and recorded the empty answers, which is how the app tells "nothing newer" from "not loaded". Published costs rose 8% to 2023; we say so and do not extrapolate. | `scripts/import_ipeds.py`, `app/db.py::series_ends`, `app/notices.py` |
| Why is a negative net price shown? Is that a bug? | Grant aid exceeded the cost of attendance at MIT and Stanford at that band. Sentinels are exactly −1, −2, −3; we drop those and only those. | `app/areas/financial_aid.py::SENTINELS`, PROPOSAL limitations |
| Why does "everyone" not equal men plus women? | IPEDS added sex codes in 2022 and 2023; we pin the published total and never sum parts. | `app/areas/selectiveness.py`, the cut's note |
| Why does the race cut's "everyone" differ from the six-year rate in the table? | Different survey, different cohort definition; drawing one against the other was the bug we caught on Wednesday. Rule 1 under *Cuts*. | `app/cuts.py` docstring, `app/areas/retention.py::cut` |
| Why suppress under 30? | One person moves the rate several points. IPEDS publishes anyway; we do not, and we name the school it happened at. | `app/cuts.py::MIN_COHORT` |
| Where does Maya's race go in the URL? | Nowhere. The URL says `tailor=retention`; the server reads the profile. A shared link tailors to whoever opens it. | `tests/test_cuts.py::test_tailoring_reads_the_profile_and_never_the_url` |
| Where is the Polars? | Every area reads one SQL query into a Polars frame and computes its metric there — spread, yield, took-longer, attrition, debt-to-earnings, athlete share. | `app/areas/*.py` |
| What did the agent get wrong? | Pagination that looked absent; a "stable" discount rate that drifts 0.7 points a year; a chart against the wrong survey's total; a watermark-tool artefact committed by accident. All in the history. | ROADMAP *Known constraints*, METRICS-REVIEW, `git log` |
| Why no peer groups, which the proposal promised? | 25 selective schools graduate 91–98% of students; there is no spread to measure against. Cuts answer the same question with a reported row instead of a synthetic peer. | PROPOSAL *What shipped*, ROADMAP *Cuts* |
| Why no password? / Why only a passphrase? | Chosen Tuesday for a class project on public data; revisited today once the profile held aid letters. | `app/profiles.py` docstring, `ROADMAP.md` |
| Is athletic aid of $0 missing data? | No: a reported value. 671 of 2,037 institutions report exactly zero; Division III and the Ivy League do not award athletic scholarships. | `scripts/import_eada.py`, ROADMAP *Athletics* |

## Numbers to reach for

The figures the five schools produce, for the presenter who wants one more. From
ROADMAP.md, *The one path we show*; every one was read from `data/likeforlike.db`
on 3 Sep.

- Highlights strip (computed, on the characteristics card): Stanford has the widest
  price swing by income, $46,662; Stanford is the hardest to get into, 3.6%; Carnegie
  Mellon has the most international students, 18.4%; MIT has 3 students per faculty
  member.
- Earnings six years after entry (Scorecard): MIT $131,633, Carnegie Mellon $105,360,
  Stanford $102,887, Berkeley $74,919, Michigan $73,762. Median debt runs $12,000
  (Stanford) to $21,750 (Carnegie Mellon).
- Athletic aid (EADA 2024): MIT and Carnegie Mellon report **$0** — Division III, a real
  reported value, not a gap. Stanford $39.7M, Michigan $31.2M, Berkeley $23.1M.
- The trend nobody sees in the snapshot: across the sample, net price at the lowest band
  fell 37% from 2015 to 2021 while the highest band rose 13% (METRICS-REVIEW).
