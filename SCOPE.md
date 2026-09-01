# Scope note — the seven comparison areas

Status: **open questions, not decisions.** Written 1 Sep 2026 after building the ingest and
looking at real data. Three things need a group answer before we build screens; they are at
the bottom.

A formatted version of this note, with charts:
<https://claude.ai/code/artifact/eeaa1886-2e12-4f9f-8b40-83a84a087723>

## The UX under discussion

User picks 1–5 schools, then picks 1–7 data areas, then sees the corresponding data. Areas
taken from the [NCES Compare Institutions](https://nces.ed.gov/ipeds/compare-institutions)
tool: institution characteristics, admission and test scores, student charges, student
financial aid, enrollment, retention and graduation, academic libraries.

## Feasibility: settled

All seven areas are backed by real data in `data/likeforlike.db`. Fourteen tables, 25/25
school coverage on every one, rebuilt in ~80 seconds with `uv run python
scripts/import_ipeds.py`.

| Area | Endpoint(s) | Year |
| --- | --- | --- |
| Institution characteristics | `directory`, `institutional-characteristics` | 2021 |
| Admission and test scores | `admissions-enrollment`, `admissions-requirements` | 2021, 2022 |
| Student charges | `academic-year-tuition`, `academic-year-room-board-other` | 2021 |
| Student financial aid | `sfa-grants-and-net-price` | 2021 |
| Enrollment | `enrollment-headcount` | 2021 |
| Retention and graduation | `fall-retention`, `grad-rates`, `grad-rates-pell` | 2021 |
| Academic libraries | `academic-libraries` | 2021 |

## The risk worth reading

**The UX as written describes the NCES tool we linked.** That tool is free, official, more
complete than anything we can build in three days, and maintained by the agency that
collects the data.

It also drops both ideas `PROPOSAL.md` was built on: net price *at your income*, and
outcomes *against a peer group*. Here financial aid is one of seven equal categories rather
than a question the user answers about themselves.

The fix is small: keep the seven-area browse, and add **one input to the selection screen —
family income bracket**. Net price at the same school, lowest bracket to highest (2021):

| School | Lowest income | Highest income |
| --- | ---: | ---: |
| Yale | $341 | $45,628 |
| Penn | $344 | $48,881 |
| Washington U | $194 | $45,503 |
| Stanford | −$1,386 | $45,276 |
| Michigan | $5,713 | $27,711 |

Stanford's figure is negative because grant aid exceeds cost of attendance. It is a real
number. A comparison tool that shows a $56,000 sticker price and not this is actively
misleading the family reading it.

## The areas are not worth equal effort

Ranked by what helps someone choosing a college. If we run short, build downward and stop.

1. **Student financial aid** — the whole point. Net price by income bracket.
2. **Retention and graduation** — breaks out by race and Pell status, so we can show an
   equity gap rather than a headline rate. CMU: 92% overall, 90% Pell. Princeton: 98%, 100%.
3. **Student charges** — stacks into total cost of attendance, which makes net price legible
   by contrast.
4. **Admission and test scores** — see the caveat below.
5. **Enrollment** — size and composition. UCLA has 34,082 undergraduates; Caltech has a few
   hundred. Context, not a decision driver.
6. **Institution characteristics** — reference table. No analysis, but cheap to ship.
7. **Academic libraries** — *recommend cutting.* Physical volumes, e-books, serials,
   preservation expenditure. Nobody chooses a school on library subscription spend, and the
   numbers are not comparable: Harvard holds 14.5M physical books to MIT's 1.3M but reports
   786k circulations to MIT's 6.3M. That is a difference in counting method, not in use.
   Publishing it invites a false comparison.

### Test score caveat

In 2022 only **49%** of Stanford's admits and **48%** of Penn's submitted an SAT. A quartile
range shown without that percentage describes half a class while implying it describes all
of it. Print `sat_percent_submitting` next to the score, always.

**Caltech reports no test scores at all** — test-blind that year. Missing has to be a state
the interface can draw, with a reason, not an empty cell. Designing for it now means it is
right later, when we widen past 25 well-resourced schools and gaps become normal.

## No campus photos

Asked and answered: no.

- IPEDS has no images. We would need Wikimedia Commons (per-image licensing and attribution)
  or the schools' own sites (copyright infringement). A new external dependency with a new
  failure mode, three days out.
- No decision a user makes changes because they saw a quad.
- It works against the argument. This tool's credibility rests on being the un-brochure.
  Glossy campus photography is the register we are arguing against.

The job a photo would do is help the eye track which column is which school. Cheaper, using
fields already in `directory`: a colour chip plus short name used identically everywhere;
`latitude`/`longitude` for a locator map; `url_school` for a link out.

## Visualisation

One form per area, legible at one school and at five without changing shape.

| Area | Form |
| --- | --- |
| Financial aid | Slope, one line per school across the five income brackets — the hero chart |
| Student charges | Stacked bar with net price marked on it |
| Retention & graduation | Paired dots, all students against Pell — the gap is the finding |
| Admissions | Applied → admitted → enrolled, with admit % and yield % |
| Enrollment | Sized bar with composition |
| Institution characteristics | Table. Don't force a chart onto reference data. |
| Academic libraries | — |

## Layout, decide before anyone writes CSS

Five schools × seven areas is 127 combinations and a very tall page. If each area gets a
bespoke layout we run out of time around area four and ship something visibly uneven.

Proposal: **a collapsible section per area, fixed order, each rendering the same way whether
one school is selected or five.** Adding an area becomes filling a template, and cutting one
costs nothing.

## Open questions for the group

1. Does the selection screen ask for a **family income bracket**? (Recommended: yes. It is
   the difference between duplicating a federal tool and not.)
2. Do we **cut academic libraries** and spend that time on the aid view?
3. **Per-area year labels, or force everything to 2021?** The areas do not share a year — net
   price ends 2021, test scores 2022, retention and enrollment run to 2024. Recommended:
   label each area with its own year. `ingest_runs` already records the year per table, so
   the interface can read it rather than hard-coding a caption.

## Still to do

- Peer-group logic needs a **sample stratified across sectors and selectivity**. Across these
  25 selective schools, graduation rates span 91–98% and retention 96–99% — there is no
  spread for a peer-adjusted outcome to measure. The selective sample stays useful as a
  fixture for the comparison interface.
- No schema, API, or front end yet. `scripts/` is ingest only.
