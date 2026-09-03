# Roadmap

A running tally: what is built, what is next, what we decided not to do and why.
[PROPOSAL.md](PROPOSAL.md) says what the project is for; this says where it is.

Add to it rather than rewriting it. An idea that was rejected is worth more written
down with its reason than deleted, because the same idea comes back.

**Rewritten 3 Sep 2026, 15:30, around one thing: the demo on Friday 4 Sep.** The first
half of this file is the plan for that, down to who runs which agent on which branch.
Everything that was here before is kept below it, under *After the demo*, unchanged
except where today's decisions closed a question.

---

See also [METRICS-REVIEW.md](METRICS-REVIEW.md) — whether the numbers we show
are the ones worth knowing, checked against the data rather than assumed.

## The demo — Friday 4 Sep 2026

What the course asks for, from `AnalyticsInPython/Fall2026/GROUP_PROJECT.md` and the
syllabus, pulled 3 Sep:

- **8–10 minutes per group, live, then a question.** Any format. We are doing a live
  walkthrough; no slides except a title card and a "how we built it" card.
- **Graded on** whether the application works, whether the analysis answers a real
  question and is defensible, the quality of the repository, the demo itself, and
  **whether the group can explain the code it shipped** — how it works, how it was
  developed, how the agent interactions went. Expect that question.
- **Every member** must have made an agentic-coding contribution visible in the history.
- Day 4 (today) is the last time everyone is in a room with Julian before presenting.

### The one path we show

A student creates an account, tells the app who she is, and the same five schools
answer differently because of it. That is the whole demo. Nothing else gets clicked.

**The sample student.** Chosen so that every question on the questionnaire moves a
number she will see, and so that no cut she triggers is suppressed at any of her schools.

| Field | Value | Why this value |
| --- | --- | --- |
| Display name | Maya | — |
| Username | `maya` (seeded) / `maya-live` (typed on the day) | The seeded one is the fallback; item 5 under *What is missing* |
| Where she is | Deciding where to apply | Leads with selectiveness; asks for scores, not offers |
| Home state | **CA** | Makes Berkeley in-state and Michigan out-of-state on the same screen |
| Family income | **Band 2, $30,001–48,000** | The band where the five schools disagree by $17,390 |
| SAT / GPA | 1480 / 3.8 | GPA is saved and compared to nothing, and the form says so — an honesty moment worth thirty seconds |
| Race | **Hispanic or Latino** | ≥ 30 in the cohort at all five schools, so no cell is suppressed |
| Gender | **Woman** | Every school reports admits by sex |

**The five schools.** All 25 schools in the sample are complete on every table (checked
3 Sep: six net-price bands, admissions by sex, race-by-sex graduation rows, outcome
measures, Scorecard, EADA and characteristics for every one), so completeness does not
pick the five. What picks them is that Maya's own cuts are drawn everywhere and the
numbers tell a story. **Caltech is the one to keep out**: four Black students in the
cohort, no two-or-more-races row, test-blind.

| School | unitid | Net price, band 2 (2021) | Admit rate, women vs men (2024) | Six-year completion, Hispanic vs everyone | Sticker that applies to Maya (2023) |
| --- | --- | ---: | --- | --- | --- |
| MIT | 166683 | **−$2,251** | 6.8% vs 3.5% | 94% vs 95% | $60,156 |
| Stanford | 243744 | **−$1,876** | 3.8% vs 3.4% | 94% vs 95% | $62,484 |
| Michigan | 170976 | $7,376 | 17.3% vs 13.9% | 89% vs 93% | **$60,107 out-of-state** (in-state $18,309) |
| UC Berkeley | 110635 | $10,294 | 12.8% vs 9.0% | 87% vs 94% | **$14,850 in-state** (out-of-state $45,627) |
| Carnegie Mellon | 211440 | **$15,139** | 14.7% vs 9.8% | **82% vs 92%** | $63,274 |

Every figure above was read from `data/likeforlike.db` on 3 Sep, and the two cut columns
are what the app actually drew for a profile with Maya's answers. Two of the five
schools pay *her* to attend at her income; one charges $15,000. The two publics land
on opposite sides of the residency line. Women are admitted at a higher rate than men
at all five, by three points at Carnegie Mellon. Carnegie Mellon also graduates its
Hispanic students ten points behind its headline. That is a demo.

Other numbers the five produce, for the presenter to reach for:

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

### Minute by minute

Nine minutes, four voices. Each person presents the part they can be asked about.

| Time | Screen | What is said | Who |
| --- | --- | --- | --- |
| 0:00–0:45 | Landing page | The two questions a family cannot answer from a ranking site: what will it cost *us*, and is the graduation rate the school or the students it admits. Federal data answers both; nobody makes it easy. | 1 |
| 0:45–2:15 | Create an account | Fill the questionnaire live as Maya. Say out loud that every question is there because it changes a number, and point at the GPA line that admits it changes nothing. Pick the five schools. | 1 |
| 2:15–2:45 | Profile | Answers saved; shortlist of five in brand colours; *Compare your saved schools*. | 1 |
| 2:45–4:15 | Financial aid | The band chart, then **Tailor data for me**: Maya's band lit up, −$2,251 to $15,139 at the same income. The sticker that applies to her: Berkeley in-state against Michigan out-of-state. The staleness notice: 2021 figures, published costs up 8% since, and why we do not extrapolate. Flip to *All available years* on this card only: cheap for the poor, dearer for the rich, every year. | 2 |
| 4:15–5:15 | Selectiveness | **Tailor**: admit rate for women beside everyone, five schools, all above the total. Why "everyone" is the published total and never the sum — IPEDS added sex codes in 2022. | 3 |
| 5:15–6:15 | Retention and graduation | **Tailor**: Hispanic completion beside that survey's own total. Carnegie Mellon −10, Berkeley −7, MIT and Stanford within a point. The under-30 rule, and the rule that we describe the school, never the student's odds. | 3 |
| 6:15–7:00 | After graduation, athletics, characteristics | Scroll, do not dwell: earnings and debt, the $0 that is real, the map and the highlights strip. | 4 |
| 7:00–8:00 | "How we built it" card | Four people, one agent each, one branch each, PRs reviewed by a human. 284 tests, ruff. The three traps the agent walked into that we caught: the API paginates at 10,000 and looks like it does not; a negative net price is real and the sentinels are −1/−2/−3; a race chart drawn against a total from a different survey. | 4 |
| 8:00–8:45 | Same card | What we proposed and changed: peer-group outcomes need a stratified sample, and 25 selective schools have no spread, so we pivoted to cuts — the same idea, the reader's own group instead of a synthetic peer. What is next. Questions. | 1 |

A rehearsal tonight decides whether the trend flip at 3:45 stays. If the demo runs
long, it is the first thing cut; the snapshot already carries the staleness notice.

### Verified working, 3 Sep 15:00

Run against `main` at `a9ff0ff` with the server on :8001, by script and by hand:

- `uv run pytest`: **284 passed**. `uv run ruff check .`: clean.
- Account creation by POST with every questionnaire field and five schools → 303 →
  profile shows the five in brand colours and the *Compare your saved schools* link
  carries the colours.
- Compare page for the five: every area renders, no notices about missing schools,
  snapshot in 0.08 s, ten-year trend in 0.05 s, cuts on both areas in 0.05 s.
- Signed in as Maya with `tailor=selectiveness&tailor=retention`: both cards show
  *Tailored to you · stop*, the cut heads read *Tailored to you: Women* and *Tailored
  to you: Hispanic*, the distances printed are the ones in the table above, and no
  small-cell notice fires.
- Year meaning lines render on every card.

### What is missing for exactly that path

Ranked. P0 blocks a sentence in the script; P1 is something the presenter would
otherwise have to apologise for; P2 is polish. Each has an owner in the *Parallel plan*.

**P0 — must merge today**

1. **The profile's income band changes nothing on the compare page.** Financial aid
   has no *Tailor data for me* button at all (checked: the card renders no control),
   and the questionnaire's first promise is that the income band picks the net price
   that is hers. Emphasise the reader's band when tailored: her band's column bold in
   the table, her band's dot solid on the range chart, and one computed sentence —
   *At $30,001–48,000, MIT −$2,251 … Carnegie Mellon $15,139: a $17,390 gap*. This is
   item 4 in the *Cuts* order below and the cheapest remaining win. → **Agent A**
2. **Home state changes nothing on the compare page.** The questionnaire calls it "the
   answer that moves the numbers most" and today it is read only by the offer
   comparison, which Maya never sees (she is not choosing between offers). When
   tailored, financial aid should print the published sticker that applies to her at
   each school: in-state at Berkeley, out-of-state at Michigan, one price at the
   privates. 2023 figures, from `academic_year_tuition`, `level_of_study = 1`,
   `tuition_type` 3 or 4, `tuition_fees_ft`; shown **beside** the 2021 net price, never
   subtracted from it, with both years on the line (known constraint: never blend
   years). `app/offers.py` already resolves in-state from `directory.state_abbr` —
   the newest non-empty row, because the 2024 directory rows for Stanford and Carnegie
   Mellon carry a blank state — so reuse that query rather than writing a second one.
   → **Agent A**
3. **Stage does not lead the page.** The questionnaire says the stage "decides what
   leads the comparison". `compare()` renders `areas.ALL` in fixed order regardless.
   When no `area` is chosen explicitly: *applying* puts selectiveness first, *choosing*
   puts financial aid first (which it already is). Eight lines and a route test. →
   **Agent C**
4. **The "After graduation" notice is wrong.** It reads *"IPEDS publishes newer years
   for post-graduation earnings that this build has not loaded"*. The source is the
   College Scorecard, not IPEDS, and METRICS-REVIEW argues the snapshot is correct by
   design — three pooled cohorts with no year axis. `notices.for_area` hard-codes
   "IPEDS" and assumes a series exists. Take the source from the area and, for an area
   with no series, say what the figures are instead of what was not loaded. → **Agent C**
5. **A seeded demo profile and a written script.** `scripts/seed_demo.py` creates
   `maya` with the answers above and the five schools, idempotently, so a wiped
   `data/profiles.db` is back in a second and the live account creation has a
   fallback that already exists. `DEMO.md` holds the minute-by-minute above, the
   exact URLs, the Friday checklist, and the fallback plan. → **Agent D**
6. **A MapTiler key in `.env`.** There is no `.env`, so the characteristics card renders
   a "no key" note where the map should be. Free key, five minutes, one line. A human
   does this; agents must not. If nobody has one by the rehearsal, the demo selects
   six areas and leaves characteristics out — the highlights strip moves with it,
   though, so get the key. → **Human**
7. **PR #5 (`areas-and-hero`) is open against a dropdown that no longer exists** and
   conflicts with `main` (checked with `git merge-tree`). The areas became a searchable
   picker in `0a61673`. Close it with a comment naming that commit; the drawn hero
   motif can come back on its own PR after Friday if anyone wants it. → **Human**

**P1 — should merge today; if not, the presenter says it out loud**

8. **The profile has no password** and now holds race, income and (for *choosing*
   profiles) aid letters. The *Risk worth naming* section below has said since Tuesday
   that this must change before anyone demonstrates it in a room. Add an **optional
   passphrase**: asked on the questionnaire and on the log-in form, stored as a salted
   hash with `hashlib.scrypt` (standard library, no dependency), checked on log-in
   only for profiles that set one. Profiles without one keep working, so every existing
   test and fixture stands. Drop the "there is no password" copy from both templates.
   If this does not merge by 20:00, the line in the script becomes: *"a username is the
   only key, which is a limitation we chose on Tuesday and would not ship."* → **Agent B**
9. **README is stale.** Its status paragraph says four areas are wired in and that
   *After graduation* is "deliberately not wired in". Seven are, and it is. Graders read
   the README first. Rewrite that paragraph only. → **Agent C**
10. **PROPOSAL promises what did not ship.** Peer-group outcomes, `app/models.py`,
    `app/routers/`, `app/analysis/`. The spec allows changing direction; it does not
    allow the grader to discover the change by diffing. Add a short *What shipped, and
    what changed* section at the top: peer groups need a stratified sample and the 25
    selective schools have no spread (that finding is already in the proposal's own
    limitations), so the analysis moved to cuts and computed gaps; the architecture is
    one module per area over the ingest tables, no ORM. Six lines, with links. →
    **Agent C**

**P2 — only if every P0 and P1 is merged by 20:00**

11. Enrollment's staleness notice is generic; METRICS-REVIEW asks for one that says
    demographics move slowly but 2021 is still 2021. Small, in `enrollment.py`.
12. Screenshots of every screen in the path, at the demo window size, into
    `docs/demo/`, as the fallback if the laptop dies. → **Agent D**, after everything
    else merges.

**Cut for the demo.** Not touched before Friday, whatever the temptation: majors,
student charges as an area, early-decision intent, score-submission question, the
stratified sample, loan default, endowment, financial aid opening in trend mode by
default (the presenter flips it by hand, which is a better story anyway), any new
area, any new data source. They are all still in *After the demo*.

### Parallel plan — four agents, four branches, one merge order

One person drives one agent on one branch. That satisfies the course's "every member
makes an agentic contribution" line and keeps the diffs explainable by the person who
will be asked about them. Suggested pairing follows the code each person already
knows; swap freely, but keep one human per agent.

| Agent | Branch | Driver | Owns — may edit | Must not touch |
| --- | --- | --- | --- | --- |
| **A** Financial aid tailoring (P0 1, 2) | `demo/aid-tailoring` | Martin (built the area) | `app/areas/financial_aid.py`, `app/templates/areas/financial_aid.html`, `tests/test_financial_aid.py`; in `app/cuts.py` only `wants()` and `signals()`; in `app/main.py` only the `context.update(...)` hook inside `compare()` | `app/profiles.py`, every other area, `app/notices.py` |
| **B** Optional passphrase (P1 8) | `demo/passphrase` | Rebecca (built profiles) | `app/profiles.py`, `app/templates/profile.html`, `app/templates/questionnaire.html`, `tests/test_profiles.py`, `tests/test_questionnaire.py`; in `app/main.py` only the `/profile` and `/profile/new` routes | `app/areas/`, `app/cuts.py`, `compare()` |
| **C** Stage order, notice, docs (P0 3, 4; P1 9, 10) | `demo/copy-and-docs` | Jenny (built outcomes and characteristics) | `app/notices.py`, `tests/test_notices.py`, `README.md`, `PROPOSAL.md`; in `app/main.py` only the ordering of `modules` inside `compare()` | `app/areas/`, `app/profiles.py`, templates |
| **D** Seed, script, checklist, fallback (P0 5; P2 12) | `demo/seed-and-script` | Rafa | `scripts/seed_demo.py`, `tests/test_seed_demo.py`, `DEMO.md`, `docs/demo/` | `app/` entirely |

`app/main.py` is the one file three agents touch, in three different functions.
Merging in the order below keeps every rebase trivial; a rebase that is not trivial is a
sign an agent left its lane.

**Merge order: C → A → B → D.** C first because it is small and moves the ordering
line that A's hook sits next to. D last because the screenshots must show the merged app.

**Gates, per branch, no exceptions:**

1. `uv run pytest` and `uv run ruff check .` clean, run by the agent and again by the
   driver.
2. A PR whose description says what changed and what was checked, opened from the
   branch — the history is graded.
3. **The driver reads the whole diff before merging and can say what each hunk does.**
   That is the course's actual test, and it is also where an agent's invented
   function or quiet scope creep gets caught. Anything the driver cannot explain is
   reverted, not merged.
4. After each merge to `main`: `uv run pytest` on `main`, then a hand click through
   the path against the seeded `maya` profile.

**Timeline for today.** Agents launched by 16:30; C merged by 17:30; A and B by
19:00; D by 19:30; full rehearsal 20:00 with the clock running; a second one at 21:00
if the first ran over eight and a half minutes.

### Agent briefs

Paste each one into a fresh session, from the repository root, on a fresh branch off
`main`. Every brief ends with the same reporting rule.

**Agent A — financial aid tailoring**

> Repository: this directory, branch `demo/aid-tailoring` off `main`. Read
> `ROADMAP.md` sections *The one path we show* and *What is missing*, items 1 and 2,
> then `app/cuts.py`, `app/areas/financial_aid.py`, `app/templates/areas/financial_aid.html`,
> `app/templates/compare.html`, `app/offers.py` (the in-state resolution), and how
> `compare()` and `_tailor_state()` in `app/main.py` use `cuts.wants` and `cuts.signals`.
>
> Build: when `tailor=financial_aid` is in the URL and the signed-in profile holds an
> income bracket, the financial aid card (1) marks the reader's band in the table and
> as the solid dot on the range chart, (2) prints one computed sentence naming the
> lowest and highest net price at that band among the chosen schools and the gap
> between them, and (3) if the profile also holds a home state, lists the published
> 2023 sticker that applies to the reader at each school — in-state or out-of-state
> for a public, one price for a private — beside, not subtracted from, the 2021 net
> price, with both years stated on that line. The *Tailor data for me* button must
> appear on this card for a signed-in reader whose profile holds either field, with
> the hint naming what it uses (the band label and the state), and must not appear
> signed out. Existing `tailor=` and `cut=` URL contracts stay exactly as they are.
>
> Do it by giving the area a `tailor(conn, schools, year, profile) -> dict` hook that
> `compare()` merges into the card's context when tailoring is on, and by teaching
> `cuts.wants()` and `cuts.signals()` about a module-level declaration of which profile
> fields an area can tailor on. Do not route this through `cut.html`, which is built
> for rates. Reuse the in-state query from `app/offers.py` rather than writing a second
> one; the 2024 directory rows for Stanford and Carnegie Mellon carry a blank state.
> Never blend the 2023 sticker into the 2021 net price. Keep `load()`'s signature.
>
> Tests, in `tests/test_financial_aid.py`: the tailored context for a band-2 profile
> over unitids 166683, 243744, 170976, 110635, 211440 names MIT at −2,251 and Carnegie
> Mellon at 15,139 with a gap of 17,390; a CA profile gets Berkeley in-state at 14,850
> and Michigan out-of-state at 60,107; a route test that the card shows the button
> signed in with a band and not signed out, and that the reader's band never appears
> in any link on the page. `uv run pytest` and `uv run ruff check .` must be clean.
>
> Do not edit `app/profiles.py`, any other area, `app/notices.py`, or any template but
> your own. Open a PR. Report: files changed, tests added, what you verified by hand,
> and anything you could not verify.

**Agent B — optional passphrase**

> Repository: this directory, branch `demo/passphrase` off `main`. Read `ROADMAP.md`
> items 8 under *What is missing* and *Risk worth naming*, then `app/profiles.py`, the
> profile routes in `app/main.py`, `app/templates/profile.html`,
> `app/templates/questionnaire.html`, `tests/test_profiles.py`, `tests/test_questionnaire.py`.
>
> Build: an optional passphrase on a profile. The questionnaire asks for one (optional,
> with copy saying what it protects); `/profile/new` stores a salted hash made with
> `hashlib.scrypt` from the standard library in a new `passphrase_hash` column added
> through the existing `ADDED_COLUMNS` migration path; the log-in form on `/profile`
> gains a passphrase field; `POST /profile` refuses to set the cookie for a profile
> that has a hash unless the passphrase verifies, and redirects back with an error
> message the template already knows how to show. Profiles with no hash keep working
> exactly as today, so every existing test and the `cuts_demo` and `rafa_test`
> fixtures stand. Remove the "there is no password" copy from both templates and
> replace it with one sentence that says what a passphrase does and that it is
> optional. The cookie stays as it is.
>
> Tests: a profile with a passphrase cannot be opened without it and can with it; a
> profile without one opens as before; a wrong passphrase leaves no cookie; the hash
> never appears in any rendered page; the migration adds the column to an older
> database. No new dependency. `uv run pytest` and `uv run ruff check .` clean.
>
> Do not edit `app/areas/`, `app/cuts.py`, `compare()`, or any template but the two
> named. Open a PR. Report: files changed, tests added, what you verified by hand, and
> anything you could not verify.

**Agent C — stage order, the outcomes notice, README, PROPOSAL**

> Repository: this directory, branch `demo/copy-and-docs` off `main`. Read `ROADMAP.md`
> items 3, 4, 9 and 10 under *What is missing*, `METRICS-REVIEW.md` (the section on why
> After graduation has no trend), `app/notices.py`, `tests/test_notices.py`, the
> `compare()` route in `app/main.py`, `app/areas/outcomes.py`'s header constants,
> `README.md`, and `PROPOSAL.md`.
>
> Four changes. (1) In `compare()`, when the request names no `area` and the signed-in
> profile's stage is `applying`, render selectiveness first and the rest in their usual
> order; `choosing` keeps financial aid first. Touch only the line that builds
> `modules`. Add a route test using a temporary profiles database, following
> `tests/test_cuts.py::test_tailoring_reads_the_profile_and_never_the_url`. (2) In
> `notices.for_area`, take the source name from the caller (the areas already expose
> `SOURCE`; default "IPEDS") instead of hard-coding it, and when an area has no series
> at all — one year held and no empty years recorded after it — say what the figures
> are ("College Scorecard pools several entry cohorts into one release; there is no
> newer year to load") rather than claiming something was not loaded. Update the tests
> and add one for the outcomes case. (3) Rewrite only the *Status* paragraph of
> `README.md` to say seven areas are wired in, name them, and drop the sentence about
> After graduation being unwired. (4) Add a *What shipped, and what changed* section at
> the top of `PROPOSAL.md`, six to ten lines, linking to `ROADMAP.md` and
> `METRICS-REVIEW.md`, that says peer-group outcomes were not built and why (the
> proposal's own limitation about the 25-school spread), that the analysis moved to
> reported cuts and computed gaps, and that the architecture is one module per area
> over the ingest tables with no ORM, `app/models.py`, `app/routers/` or `app/analysis/`.
> Do not rewrite any other part of either document.
>
> `uv run pytest` and `uv run ruff check .` clean. Do not edit `app/areas/`,
> `app/profiles.py`, or any template. Open a PR. Report: files changed, tests added,
> what you verified by hand, and anything you could not verify.

**Agent D — seed, script, checklist, fallback**

> Repository: this directory, branch `demo/seed-and-script` off `main`. Read
> `ROADMAP.md` from the top through *Agent briefs*, `app/profiles.py`, `scripts/schools.py`,
> and `tests/test_profiles.py` for how a temporary profiles database is used in tests.
>
> Build: (1) `scripts/seed_demo.py`, run as `uv run python scripts/seed_demo.py`, which
> creates or resets the `maya` profile exactly as the table under *The sample student*
> specifies — display name, stage `applying`, home state CA, income bracket 2, SAT 1480,
> GPA 3.8, race 3, gender 2 — with the shortlist 110635, 243744, 166683, 211440, 170976
> in that order, using only functions from `app/profiles.py`, idempotently, printing the
> compare URL with brand colours at the end. `--db PATH` points it at another database
> for tests. (2) `tests/test_seed_demo.py` against a temporary database. (3) `DEMO.md`:
> the *Minute by minute* table copied in, then the exact URLs for every screen in order,
> the *Demo day* checklist and *Fallbacks* from `ROADMAP.md`, and a *Questions we
> expect* section copied from the roadmap with the file each answer lives in. Once
> branches A, B and C are merged to `main` and you are told so, rebase, run the seed,
> and (4) take a screenshot of every screen in the path at 1280×800 into `docs/demo/`,
> numbered in order, and reference them from `DEMO.md`. Do not take screenshots before
> the merge notice.
>
> `uv run pytest` and `uv run ruff check .` clean. Do not edit anything under `app/`.
> Open a PR. Report: files changed, tests added, what you verified by hand, and
> anything you could not verify.

**After the four merge — the integration pass.** Not an agent; a person with the clock
running. Start the server fresh, run the seed, delete the cookie, and go through the
path as written, timing each row of the table. Note every place the copy on screen
contradicts what the presenter is about to say. Fix copy on `main` directly if it is
one line; anything larger goes back to the owning branch.

### Decisions the humans make today

Listed with a recommendation; the group decides, in the room, before the agents start.

| Decision | Recommendation | Why |
| --- | --- | --- |
| Close PR #5? | **Close it**, comment naming `0a61673`. | It conflicts with `main` and removes a dropdown that is already gone. The hero motif is a separate idea and can return on its own PR. |
| Passphrase before the demo? | **Yes, optional, Agent B.** | Showing a classmate's race and aid package by typing their name is the thing that gets remembered. Optional keeps every fixture and test working. |
| MapTiler key? | **Get one now**; one person, five minutes. | The map is the only feature that does not degrade; the highlights strip sits on that card. |
| Live account creation, or the seeded one? | **Live, as `maya-live`**, with `maya` seeded as the fallback. | Creating the account *is* the demo. The seeded one exists so a typo at minute one is not the end. |
| Who says what? | The table under *Minute by minute*; each person presents the code they drove today. | The grader asks the presenter how it works. |
| Delete the five fully merged local branches and the `final-project-enrollment-worktree` directory? | **After Friday.** | Nothing there blocks the demo; the worktree has uncommitted leftovers of already-merged work that someone should glance at before it goes. |

### Demo day — Friday morning

- [ ] `git pull`; `uv sync`; `uv run pytest` — 284 or more, all green.
- [ ] `.env` present with the MapTiler key; `ls data/*.db` shows all three databases.
- [ ] `uv run python scripts/seed_demo.py`; open `/profile`, log in as `maya`, see five schools.
- [ ] Log out. The demo starts signed out.
- [ ] `uv run uvicorn app.main:app --port 8001` in a terminal that stays visible in the dock, not in an IDE pane.
- [ ] Browser: one window, one tab, 125% zoom, bookmarks bar hidden, notifications off, other apps closed. Window at the projector's resolution, not the laptop's.
- [ ] Open `DEMO.md` on a phone or second screen for the URLs and the numbers.
- [ ] `docs/demo/` screenshots opened in a second tab, in case.
- [ ] Every presenter has the three "how does this work" answers for their two minutes.

### Fallbacks

- **Typo or hesitation in the live sign-up:** finish it anyway; if it fails, log in as
  `maya` and say why she exists.
- **Server dies:** the terminal is visible; restart is one command, ten seconds.
- **Laptop dies:** the screenshots in `docs/demo/` on a second machine, narrated.
- **Running long at 6:15:** skip the scroll through the last three areas and go to
  the build card. At 7:30, skip the "what we changed" beat and take questions.
- **The map does not load:** say "needs a key" and keep going; the highlights strip is
  above it.

### Questions we expect, and where the answer lives

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
| Why no password? / Why only a passphrase? | Chosen Tuesday for a class project on public data; revisited today once the profile held aid letters. | `app/profiles.py` docstring, this file |
| Is athletic aid of $0 missing data? | No: a reported value. 671 of 2,037 institutions report exactly zero; Division III and the Ivy League do not award athletic scholarships. | `scripts/import_eada.py`, *Athletics* below |

### The Lowlights One-Pager — 20%, individual, due end of week

Not group work, and two people in one group must not hand in the same page. Each
person picks incidents they were personally in the loop for. Candidates from this
week, so that four people do not all write about pagination:

- The API that paginates at 10,000 rows and looks like it does not (Martin, the ingest).
- The by-race chart drawn against a total from a different survey (whoever reviewed
  retention on Wednesday).
- "Stable" discount rate that turned out to drift 0.7 points a year (the offers work).
- The picker that locked years when an area was chosen, and the rename that caused it
  (`5316d45`).
- The staleness notice that credited IPEDS for College Scorecard data (found today).
- The questionnaire that promised home state and stage would change the page when
  neither did (found today).
- A watermark-tool artefact committed by accident (`1f4b846`).
- An agent that reported "no pagination" as a verified fact on Monday and was corrected
  on Tuesday.

For each: how you noticed, what actually went wrong, what you did. The noticing is the
point.

---

## After the demo — the standing tally

Everything below is what this file held before 3 Sep 15:30, kept as it was. Nothing
in *Next* ships before Friday.

## Built

- **Ingest** — fourteen IPEDS endpoints, a year range each, into a gitignored SQLite
  build artifact. Records every endpoint-year attempted *including the empty ones*,
  which is how the app tells "IPEDS publishes nothing newer" from "we have not loaded
  it yet".
- **Picker** — searchable school combobox, per-school brand colours the user can
  override, clash detection when two colours are too close to tell apart.
- **Year control** — span buttons plus a per-year availability map, green / amber /
  grey, hover naming which school is missing what.
- **Snapshot and trend views** — no years is a snapshot of each area's newest year,
  one year pins it, two or more draw a trend across a window shared by every area.
- **Data-quality notices** — how old the figures are and which schools report nothing,
  stated above the charts rather than in a footnote.
- **Areas** — student financial aid, selectiveness, retention and graduation, after
  graduation (earnings and debt), enrollment, athletics, institution characteristics.
- **Profiles** — username-only, cookie, shortlist. Merged (PR #4).
- **Questionnaire** — sign-up questions gated by whether someone is pre- or
  post-application, and an offer comparison that prices a real aid letter against
  what the school usually gives at that income. Merged.
- **Cuts** — a metric broken out by sex or race, asked for from a menu or tailored to
  the profile with one button. See the section below.

---

## Next

Ordered by value per hour. Build downward — after Friday.

### Areas

1. ~~**Retention and graduation.**~~ **Built.** Four-year against six-year completion,
   and the share of a first-year class that does not come back. It was first built
   around the Pell gap and a by-race spread; both were cut on 3 Sep 2026 — Pell because
   it is not a question this tool's users are asking, race because a breakdown nobody
   asked for was leading the area. The by-race data was the best in the project, though
   (Michigan is 83% for Black students against 95% for Asian, behind 93% overall), and
   it is the first case for [Cuts](#cuts--breaking-a-metric-out-by-who-you-are) below.
2. **Student charges.** Cheapest to build; joins the table financial aid already reads.
   Sticker against net at the lowest band: Penn is $83,298 published against $344 paid.
   **Decide first:** `tuition_type` 2/3/4 is in-district / in-state / out-of-state, and
   the four publics differ by $38,000 between them. A profile's home state settles it
   for a signed-in user; something has to be picked for everyone else. *Partly
   absorbed by the demo work: the tailored financial aid card now shows the sticker
   that applies to the reader.*
3. **Majors.** 145,620 rows of `completions_cip_2` sitting unused. `award_level = 7` is
   Bachelor's, and the totals row is `cipcode = 990000` — exclude it or every school
   double-counts.
4. ~~**Enrollment / demographics**~~ **Built.**
5. ~~**Institution characteristics.**~~ **Built.**

### Questionnaire

- **Intended major** *(pre-application)*. The strongest metric not yet collected.
  Answers "does this school actually graduate people in the thing I want" — Michigan
  awards 1,142 computer science degrees a year, Dartmouth around 90. Needs 2-digit CIP
  labels hardcoded, roughly 38 of them.
- **Early decision intent** *(pre-application)*. ED admit rates run several times
  higher, and ED is binding — a student who applies ED cannot use the offer comparison
  at all. Worth surfacing as a tradeoff rather than a checkbox.
- **Whether they will submit scores** *(pre-application)*. Submission rates run 26–49%
  at these schools, so "should I send this 1480" is a live question the percentile data
  answers.
- **On-campus or commuting** *(post-application)*. `living_arrangement` changes the
  cost of attendance the discount is measured against. Mechanically identical to
  `home_state`, which is already done.
- **Is the aid renewable** *(post-application)*. IPEDS cannot answer it. Asking makes
  the student go and check, which is the useful part.

### Athletics — a third source, and the widest spread we have found

Scoped 2 Sep 2026 while pulling athletics data for an unrelated piece of work. The
headline metric a prospective athlete wants is **what share of the student body is a
varsity athlete**, and it separates schools harder than anything else in the project:
**2.1% at UCLA to 26.6% at Caltech**, a twelve-fold range, against graduation rates that
span 91–98% across the same 25 schools.

**It is not in IPEDS.** IPEDS carries only membership flags — `member_ncaa`,
`conf_number_football` and similar in `institutional-characteristics`. No participation,
no athletics money.

**It is also not a scrape.** It is EADA, the Equity in Athletics Disclosure Act
collection, published as bulk files by the Department of Education:

    https://ope.ed.gov/athletics/api/dataFiles/file?fileName=EADA_2024-2025.zip

- `instLevel.xlsx` — one row per institution, 168 columns
- `schools.xlsx` — one row per sport per institution
- 2,037 institutions in 2024-25; **25/25 of our sample**, joined on `unitid`
- Survey years 2003 through 2025, one zip each

Do **not** use EADA's own JSON API for this: it ignores its year parameter entirely, so
`?year=2020` and `?surveyYear=2020` both return the newest survey. The bulk files are the
only route to history.

Metrics worth building, all from `instLevel.xlsx`:

| Metric | Why it earns its place |
| --- | --- |
| Athlete share of the student body | `UNDUP_CT_PARTIC_MEN + _WOMEN` over `EFTotalCount`. The headline. |
| Athletic aid per athlete | $0 to ~$54,000. Encodes scholarship policy, not just money. |
| Men's / women's participation and aid split | The Title IX comparison, already computed in the file. |
| Sports offered | From `schools.xlsx`, one row per sport. |
| NCAA classification | `classification_name`, e.g. "NCAA Division I-FCS". |

Four traps, each of which produces a plausible wrong number:

- **`PARTIC_*` double-counts multi-sport athletes; `UNDUP_CT_PARTIC_*` does not.** A
  cross-country runner who also runs track appears twice in the first. Using the wrong one
  overstates Furman's athlete share as 19.6% when it is 15.9% — one in five rather than
  one in six.
- **$0 athletic aid is a reported value, not a missing one.** Across 2,037 institutions
  the column is 1,366 positive, 671 exactly zero and never null. The zeros are almost all
  Division III (223 of 235 D-III-with-football) plus the Ivy League, none of which awards
  athletic scholarships. Treating $0 as missing deletes a real and decision-changing fact:
  an Ivy at $0 means need-based aid only.
- **Revenues always equal expenses.** Institutional support is booked as revenue, so every
  filing balances and EADA's own summary line reads $0. **EADA cannot show an athletics
  deficit** and nothing built from it may imply one.
- **`EFTotalCount` is EADA's own full-time undergraduate count**, not an IPEDS figure.
  Use it as the denominator so the ratio is internally consistent, and label it as EADA's.

Cost: xlsx-in-zip rather than JSON, so the ingest needs `openpyxl` and a second fetch
shape. That is the only structural difference — the join key and the per-year table
pattern are identical to what `import_ipeds.py` already does.

### Infrastructure

- **Per-area ingest years.** Several endpoints run to 2023 or 2024 and are pulled to
  2024 already, but anything added later should not inherit a hardcoded anchor.
- **A stratified sample.** The peer-group comparison in PROPOSAL.md cannot be exercised
  on 25 selective schools — graduation rates span 91–98%, which is no spread at all.
  Needs open-access institutions in the sample before that analysis means anything.
- **README currency.** It has drifted behind twice now. *Third time: fixed by Agent C
  on 3 Sep.*

## Cuts — breaking a metric out by who you are

Proposed 3 Sep 2026; the first two cuts and the tailoring button were built the same day
(see *What is built* at the end of this section). The by-race completion spread that was
cut from retention that morning is the first case and the reason this section exists.

A *cut* is the same metric, at the same school, in the same year, reported for one group
of students rather than all of them: the six-year completion rate for Black students at
Michigan (83%) rather than for everyone (93%). Nothing is estimated. IPEDS surveys
already report most figures by group; a cut is choosing to show one of those rows. The
UI should never use the word — it says **Show by race** when the reader asks, and
**for students like you** when the profile does the asking.

### The two ways one appears

The request was that a breakdown by race should only show up if the student asks for it,
or if the tool knows their race and can be more precise on their behalf. That is two
triggers for one mechanism:

1. **Asked for.** A row of chips in an area's header — *Show by: sex · race · how you
   entered* — listing only the dimensions that area's own table carries. Picking one
   redraws the area with every group beside the total. Nothing is pre-selected.
2. **Offered.** A signed-in profile with a value on a dimension the area supports gets
   that cut applied on arrival, with the reader's own group emphasised and the rest
   faded. It is labelled (*Showing Hispanic students — everyone · hide*), removed with
   one click, and the removal is remembered on the profile.

Both set the same URL parameter — `cut=race` for the full breakdown, `cut=race:3` to
emphasise one group. The profile only supplies a default. That keeps the state
shareable, keeps tests trivial, and means the second trigger is one line in `main.py`
once the first exists.

### What the tables actually carry

Checked against the database on 3 Sep 2026, not the codebooks.

| Area | Table | Groups the table reports | Same cohort as the headline? |
| --- | --- | --- | --- |
| Selectiveness | `admissions_enrollment` | sex | **Yes** — one table, one row per sex |
| Retention and graduation | `outcome_measures` | first-time vs transfer-in (`class_level`); Pell / direct loan / neither | **Yes** |
| | `grad_rates` | race, and race × sex (150%-of-time rate) | **No** — a different survey with its own cohort |
| | `fall_retention` | full- or part-time only | no identity cut exists |
| Financial aid | `sfa_grants_and_net_price` | income band (already the area's axis); residency | **Yes** |
| Enrollment | `enrollment_headcount` | race, sex | it *is* the cut — a share of the student body |
| After graduation | College Scorecard | sex, income tercile, first-generation, Pell; field of study | **No** — see the Scorecard trap below |
| Athletics | EADA | sex | **Yes** — men's and women's columns in one row |
| Majors *(unbuilt)* | `completions_cip_2` | field, race, sex | **Yes** |

Watch `sex` in admissions: codes are `1, 2, 99` through 2021, then `9` appears in 2022
and `3` in 2023. Pin the total, never sum the parts — the same rule selectiveness already
follows.

### The numbers that make it worth doing

- **Admit rate by sex, 2024.** Carnegie Mellon admits 9.8% of men and 14.7% of women.
  MIT 3.5% and 6.8%; Caltech 1.8% and 4.3%; Berkeley 9.0% and 12.8%. Brown runs the
  other way, 7.0% and 4.4%. All 25 schools report both. This is the cheapest cut in the
  project — same table as the headline, no cohort question — and the one with the widest
  audience, since every applicant has a sex code in IPEDS and only some will enter a race.
- **Six-year completion by race, 2023.** Berkeley graduates 78% of its Black students
  against 93% overall (118 in the cohort); Michigan 83% against 93% (263); Georgetown 85%
  against 95%. UNC reports 73% for 30 American Indian students against 91%. Same finding
  the old chart showed, but this time the reader chose to look.
- **Athletic aid by sex, 2024.** Vanderbilt spends $59,796 per male athlete and $36,110
  per female athlete. Already computed in the EADA file; no work beyond a chip.
- **Field of study, the one that dwarfs the rest.** Michigan's bachelor's programmes
  report median earnings two years after completion from **$16,169** (CIP 2605, 28
  awards) to **$94,281** (computer science, 1,215 awards); 57 of its 88 bachelor's
  programmes carry the figure. The whole 25-school headline runs $57,057 (UNC) to
  $132,140 (Caltech). Major spreads earnings inside one school nearly as far as the
  school does across the entire sample. It needs *intended major* on the questionnaire,
  which is already the first item on that list.
- **Transfer-in completion, 2021.** Carnegie Mellon reports 20% of its 80 full-time
  transfer entrants finishing in six years against 93% of first-time entrants; Michigan
  90% against 93%. The CMU figure is either the most important number in the area for a
  transfer student or an artefact of how CMU files, and nothing in the table says which.
  That is what a cut does: it surfaces a row nobody was reading, and someone has to
  check it before it ships.

### The rules

Each of these was learned from a chart that would otherwise have shipped.

1. **The reference is everyone, from the same table.** A group is drawn beside that
   table's own total, never beside a headline from a different survey. The old race chart
   drew `grad_rates` dots against the `outcome_measures` six-year rate — different
   surveys, different cohort definitions — and got away with it because they happened to
   agree. When the cut's table is not the headline's, the caption says the cohort differs,
   exactly as the retention page now says of attrition against completion.
2. **Beside, never instead.** The finding is the gap. A page that replaces 93% with 83%
   has hidden the thing the reader came to see.
3. **One cut at a time.** Cells shrink fast, and IPEDS only crosses race with sex anyway.
4. **Suppress small cells and say so.** 52 of the 175 race-by-school cells in this sample
   are under `MIN_COHORT`; Caltech has four of seven. For a small group at a small school,
   *the reader's own cell being the suppressed one is the normal case*, and the page has
   to say "fewer than 30 Native American students in this cohort at Caltech — a rate
   would move several points per person" rather than fall back to the total silently.
5. **Reporting categories are not identities, except when they are yours.** International
   (8) and unknown (9) never enter a best-or-worst across groups. But IPEDS files an
   international student under 8 regardless of their race, so a profile that says
   *Nonresident* is mapped to 8 and shown that row. It is the only honest comparator.
6. **"Prefer not to say" produces nothing.** No cut, and no *add your race to see more*.
   The profile has no password; the app should not be coaxing anyone to put more in it.
7. **Describe the school, not the student.** *How Michigan does for Black students*, never
   *your odds*. A group's 78% is the school's record with that group, not a forecast
   for a reader, and copy that slides from one to the other is the fastest way to lose
   the trust the financial aid area has earned.
8. **A cut is a reported row, never an estimate.** No interpolating between income
   bands, no imputing a suppressed cell from its neighbours, no blending two surveys into
   one number. Where the survey has no row, the page has no figure.
9. **Snapshot first.** A trend with a cut is one school with a line per group, not five
   schools times seven groups. Defer it; nothing in the snapshot design blocks it.

### The Scorecard trap

The Scorecard's by-sex and by-income earnings fields are **means from a different
vintage than the headline median** and cannot be drawn against it. Michigan:
`6_yrs_after_entry.median` is $73,762; `mean_earnings.female_students` is $47,900 and
`.male_students` $64,300. A combined mean near $56,000 sitting $18,000 *below* the
median is not one cohort — earnings distributions skew the other way. The first-generation
and Pell splits come back empty for Michigan. Skip sex and income cuts on earnings
entirely; field of study is the cut that matters there, and it is a different endpoint
(`programs.cip_4_digit`, 363 rows for Michigan alone).

### What the profile can already drive

| Profile field | Cut | Note |
| --- | --- | --- |
| `race` (1–8) | race | Codes match IPEDS exactly; 8 *Nonresident* is right (see rule 5); 9 drives nothing |
| `gender` (1, 2) | sex | 0 drives nothing |
| `income_bracket` (1–5) | income band | Financial aid already draws all five bands. "You" is emphasising one — the same pattern, on a chart that exists. *Agent A, 3 Sep.* |
| `home_state` | residency | Already planned for student charges. *Agent A, 3 Sep: the sticker that applies, on the tailored financial aid card.* |
| *not collected:* intended major | field of study | The largest payoff; on the questionnaire list |
| *not collected:* first-time or transfer | entrant type | One radio button; `outcome_measures` has the rows |
| *not collected:* athlete | — | No federal collection reports outcomes by athlete status. The NCAA's GSR is not public data |

### Where it lives in the code

Each area declares its cuts next to its other constants — `CUTS = {"sex": Cut(label,
query, codes, same_cohort)}` — empty for the areas that have none. `load()` grows an
optional `cut` argument. `main.py` collects them exactly as it collects `coverage()` now,
the template draws the chips from that, and the profile supplies the default. The chart is
the retention range chart turned inside out: every group a faded dot, everyone a solid
marker, the selected group in colour with the gap printed at the right. One shape serves
both triggers.

The Pell / direct-loan split lives in the same `outcome_measures` rows. It is not going
back in as a headline. Whether it earns a chip is not a decision for now.

### What is built

The UI decision, taken 3 Sep 2026 and corrected the same evening: every area card
carries a **Show by** menu at the top right of its head — listing the breakdowns that
area's survey has, or saying that it has none — and, beside it, its own **Tailor data
for me** button, which draws the cut matching what the profile holds: the reader's own
group in colour, everyone as a hollow marker, the distance printed at the right. The
button exists only for a signed-in reader and only on cards that could use the profile;
signed out there is nothing to see. Both are plain links: `cut=<area>:<dimension>` for
the menu, `tailor=<area>` for the button. The reader's race or sex is resolved from the
profile on the server and never enters a URL, so a shared link tailors to whoever opens
it. Snapshot view only; on the trend view both controls say so.

Every card also now says **what its year means** under the question — read from the
table where the table knows (`outcome_measures.cohort_year`: the 2021 graduation figures
follow students who started in fall 2014) and stated per survey elsewhere (admissions
2024 is the class entering fall 2024; net price 2021 is the 2021–22 academic year).

- `app/cuts.py` — the `Cut` declaration, URL parsing and links, suppression, the chart.
- **Admit rate by sex** on selectiveness, from the profile's gender.
- **Six-year completion by race** on retention, from the profile's race, drawn against
  the Graduation Rates survey's own total (rule 1) with international students shown only
  as someone's own group (rule 5).
- `tests/test_cuts.py`, including a route test that the tailored page never carries a
  code for the reader in any link.

What the button cannot use yet: SAT and ACT (the percentile columns exist in
`admissions_requirements`, 2021–22 only, and would be a *marker* on a score band rather
than a cut — a different chart, not yet drawn), intended major (not collected), income
band (financial aid already draws all five; emphasising the reader's is a small change to
Martin's chart — *Agent A's job today*).

### Order for the rest, by value per hour

1. ~~**Sex on selectiveness.**~~ Built.
2. ~~**Race on completion.**~~ Built.
3. ~~**Profile defaults.**~~ Built, as the button.
4. **Income band emphasis on financial aid** when tailored — the cheapest remaining win.
   *P0 for the demo; Agent A.*
5. **Entrant type on completion** — after someone has explained Carnegie Mellon's 20%.
6. **Field of study on earnings** — after intended major is on the questionnaire. The
   biggest payoff and the most work, because it is program-level rows rather than one
   more column.

Not doing: earnings by sex or income from the Scorecard (vintage mismatch); any cut
across two dimensions; any estimated cell.

---

## Parking lot

Not rejected, just not now.

- ~~**Post-graduation earnings** via the Urban API.~~ **Built, by a different route.**
  The Urban path is the wrong one — it serves a single 2018 snapshot. `app/areas/outcomes.py`
  calls the College Scorecard API directly instead and gets current pooled cohorts. The
  placement-rate finding still stands: `count_not_working` is null, so no such rate can be
  computed from any route.
- **Loan default rate.** `scorecard/default`, one row per school, near-free to add.
- **Athletics deficit / institutional subsidy.** Not in EADA, not in IPEDS, not in any
  federal collection. It lives only in a university's audited financial statements or its
  IRS Form 990. Worth writing down so nobody goes looking for it twice.
- **Endowment per student.** `nacubo/endowments`. Explains *why* a school can discount
  to near zero.
- **Missing-data summary block.** A standing list of every gap, complementing the
  per-year hover. Scope it to selected schools and areas or it becomes a wall of text.
- **Saved comparisons.** PROPOSAL.md floats analysing which schools users weigh against
  each other. Needs traffic to be worth anything.
- **Financial aid opening in trend mode by default.** METRICS-REVIEW makes the case; the
  demo flips it by hand instead. Decide after Friday.
- **The hero motif from PR #5**, on its own PR, if anyone still wants it.

---

## Decided against

- **Academic libraries.** Harvard holds 14.5M physical books to MIT's 1.3M but reports
  786k circulations to MIT's 6.3M. That is a difference in counting method, not in use,
  and publishing the columns side by side invites a comparison the data does not
  support.
- **Campus photos.** IPEDS has none; sourcing them means per-image licensing or
  copyright infringement, and no decision changes because someone saw a quad. The job a
  photo would do — helping the eye track which column is which school — is done by the
  colour chips.
- **Average admitted GPA.** IPEDS does not collect it. `reqt_hs_gpa` is a flag for
  whether a school *requires* one, not a value. It lives in the Common Data Set, which
  is not a public API.
- **Merit versus need-based aid.** IPEDS reports institutional grant aid as one figure
  with no split. Publishing a merit share would mean inventing it.
- **A GMAT field.** This tool compares undergraduate institutions on undergraduate
  data. A GMAT score has no counterpart in any table here.
- **Extrapolating a current net price.** The trend invites it and aid policy moves
  discontinuously. Draw the trend, draw the gap, let the eye finish it — do not print a
  number IPEDS never published.
- **Routing income-band emphasis through `cut.html`.** That partial is built for rates
  by group; net price by band is money on an axis the area already draws. A separate
  `tailor()` hook is less code than bending the cut chart. (3 Sep, Agent A's brief.)

---

## Open decisions

Someone has to choose. Listed with a recommendation, not a decision.

| Question | Recommendation |
| --- | --- |
| Areas as a dropdown or a plain list? (PR #5 removes the dropdown) | **Overtaken, 3 Sep:** the areas became a searchable picker in `0a61673`. Close PR #5. |
| Should profiles have a password? | **Decided 3 Sep: an optional passphrase, before the demo.** Agent B. |
| Which tuition type for a signed-out user? | Out-of-state, and say so. It is the figure that is wrong for fewer people. Signed in, the home state decides — Agent A. |
| Does a profile apply a cut without being asked? | **Decided 3 Sep:** only when the reader presses *Tailor data for me*; then labelled, one click to stop. Never for *prefer not to say*. See [Cuts](#cuts--breaking-a-metric-out-by-who-you-are). |
| Does the comparison screen ask for income up front? | Already answered by showing all five bands, but never decided deliberately. |
| Does the stage reorder the page? | **Decided 3 Sep: yes**, when no area was chosen explicitly. Agent C. |

---

## Known constraints

The things that produce a plausible-looking wrong answer rather than an error.

- **Every ingest table holds many years. Every query needs a year filter.** Without one
  a pivot silently averages a decade and still returns a believable number.
- **Negative values are sentinels (-1, -2, -3) — except `net_price`,** where a negative
  is real and means grant aid exceeded the cost of attendance. Drop the exact sentinels,
  never "anything below zero".
- **The API's schema drifts between years.** `directory` gains Carnegie 2025 columns
  partway along the range, and its 2024 rows carry a blank `state_abbr` for some
  schools; `sex` runs `[1, 2, 99]` through 2021, gains 9 in 2022 and 3 in 2023. Pin the
  total, never sum the parts, take table columns as the union across years, and read a
  school's state from its newest non-empty row.
- **`number_enrolled_pt` is a sentinel at 13 of 25 schools.** Deriving enrolments as
  full-time plus part-time is wrong in the third significant figure — enough to reorder
  schools, small enough to pass review.
- **Rates are fractions.** `completion_rate_150pct` is 0.98, not 98.
- **The endpoints paginate at 10,000 rows.** Small result sets arrive whole, which makes
  it look like they do not. Follow `next` and assert against the reported `count`.
- **Two surveys, two cohorts.** The retention card's year is `outcome_measures`; the
  race cut on it is `grad_rates`, whose cohort started in a different fall. The cut's
  note says so. Never draw one against the other's total.

---

## Risk worth naming

The profile is a username in a cookie with **no password**. It now holds a home state,
an income bracket, race, gender, GPA, and — since the questionnaire — actual financial
aid packages. Anyone who types a username sees all of it.

That was a deliberate call for a class project, and it is a much larger call than it was
when the profile held a shortlist and a test score. An aid letter is the most sensitive
thing in the app. Either add a signed cookie or drop the sensitive fields before anyone
demonstrates this in a room; showing a classmate's race and aid package by typing their
name is the kind of thing that is remembered.

It also cuts against the project's own argument. This tool's credibility rests on being
straight with families about money.

**3 Sep:** the optional passphrase (Agent B, P1) is the answer we chose. A signed cookie
alone would not do it — the username form would still open any profile — and dropping
the fields would remove the demo.
