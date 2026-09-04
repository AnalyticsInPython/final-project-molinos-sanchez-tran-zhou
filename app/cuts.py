"""Cuts — one metric, one school, one year, for one group of students beside everyone.

The six-year completion rate for Black students at Michigan (83%) drawn next to
the rate for everyone (93%). Nothing is estimated: the IPEDS surveys already
report most figures by group, and a cut is choosing to show one of those rows.

A cut appears in two ways, and they are the same mechanism:

- **Asked for.** The "Show by" menu on an area card sets `cut=<area>:<dimension>`
  in the URL, and every group the survey reports is drawn beside the total.
- **Offered.** `tailor=<area>` in the URL asks the server to look at the
  signed-in profile and, if that area has a cut for a value the profile holds,
  draw it with the reader's own group emphasised. The reader's race or sex
  never enters the URL: a shared link tailors to whoever opens it, or to nobody.

Rules, each learned from a chart that would otherwise have shipped:

1. The reference is everyone *from the same table*. Where the cut's survey is
   not the headline's (race comes from `grad_rates`, the headline from
   `outcome_measures`) the cut carries its own total and says so in `note`.
2. Beside, never instead. The finding is the gap.
3. One dimension at a time. Cells shrink fast.
4. A group below `MIN_COHORT` at a school is not drawn, and the page says
   which. For a small group at a small school the reader's own cell being the
   suppressed one is the normal case, not the edge case.
5. Reporting categories are not identities, except when they are the reader's:
   international students (race code 8) are drawn only when the profile says
   *Nonresident*, because IPEDS files them there regardless of race, and
   "unknown" (9) is never drawn at all.
6. Describe the school, not the student. "How Michigan does for Black
   students", never "your odds".
"""

from dataclasses import dataclass, field
from urllib.parse import urlencode

from app.format import percent
from app.notices import Notice

# Below this many students a rate moves by several points per person.
MIN_COHORT = 30

# The code every IPEDS dimension uses for its published total.
TOTAL = 99

# The three marks a cut draws, in SVG units, sized to carry a similar weight.
# See figure() for why the roles are told apart by shape and not by colour.
OWN_R = 6.5  # radius of the reader's own group, filled with the school's colour
GROUP_W, GROUP_H = 4.6, 4.2  # half-width and half-height of another group's triangle
TOTAL_SIDE = 10.5  # side of the hollow square standing for everyone


@dataclass(frozen=True)
class Cut:
    """One dimension an area can be broken out on, declared in the area's CUTS."""

    key: str  # URL token and CUTS key, e.g. "sex"
    label: str  # menu label, e.g. "Sex"
    metric: str  # what is broken out, e.g. "Admit rate"
    groups: dict[int, str]  # code -> label, the groups drawn for everyone
    profile_field: str | None = None  # Profile attribute holding the reader's code
    own_only: dict[int, str] = field(default_factory=dict)  # drawn only as the reader's own
    note: str = ""  # what survey this is and how "everyone" relates to the headline
    places: int = 1  # decimal places a rate is shown to
    count_noun: str = "students"  # what the count behind each rate counts

    def name(self, code: int | None) -> str | None:
        return self.groups.get(code) or self.own_only.get(code)


@dataclass(frozen=True)
class Selection:
    dimension: str
    emphasis: int | None = None  # the reader's own code, when tailoring


def parse(values: list[str] | None) -> dict[str, str]:
    """`cut=selectiveness:sex` -> {"selectiveness": "sex"}. Anything else is ignored."""
    chosen = {}
    for value in values or []:
        parts = value.split(":")
        if len(parts) == 2 and all(parts):
            chosen[parts[0]] = parts[1]
    return chosen


def choose(module, explicit: str | None, profile) -> Selection | None:
    """What to draw for this area: the reader's explicit choice, else what the
    profile can drive, else nothing.

    `profile` is None when tailoring is off, so the second path never runs
    without the reader having pressed the button.
    """
    cuts = getattr(module, "CUTS", {})
    if not cuts:
        return None
    dimension = explicit if explicit in cuts else None

    if profile is not None:
        # An explicit choice is respected; tailoring only adds the emphasis.
        # Otherwise the first dimension the profile holds a value for.
        for key in [dimension] if dimension else list(cuts):
            code = _own_code(cuts[key], profile)
            if code is not None:
                return Selection(key, code)

    return Selection(dimension) if dimension else None


def _own_code(cut: Cut, profile) -> int | None:
    if profile is None or not cut.profile_field:
        return None
    code = getattr(profile, cut.profile_field, None)
    return code if cut.name(code) else None


def signals(module, profile) -> list[str]:
    """The profile values this area could tailor on, by label."""
    labels: list[str] = []
    for cut in getattr(module, "CUTS", {}).values():
        label = cut.name(_own_code(cut, profile))
        if label and label not in labels:
            labels.append(label)
    # Not every profile field an area can use is a cut. A cut is a breakdown
    # of a survey's own rows, drawn by cut.html; financial aid instead
    # emphasises the reader's income band on an axis it already draws, and
    # reads their home state to pick the published sticker that applies to
    # them. An area declares those as TAILORS — {profile field: (what to call
    # it, code labels or None)} — and the hint names the value found rather
    # than the field, so the reader sees "$30,001–48,000", not "income band".
    for attribute, (_, values) in getattr(module, "TAILORS", {}).items():
        value = getattr(profile, attribute, None) if profile is not None else None
        label = values.get(value) if values else value
        if label and label not in labels:
            labels.append(label)
    return labels


def wants(module) -> list[str]:
    """What a profile would need to hold for this area to tailor: "sex", "race".

    Both sources of tailoring, since the button is drawn from this: a cut that
    names a profile field, and the area's own TAILORS declaration.
    """
    from_cuts = [c.label.lower() for c in getattr(module, "CUTS", {}).values() if c.profile_field]
    return from_cuts + [label for label, _ in getattr(module, "TAILORS", {}).values()]


def parse_tailor(values: list[str] | None) -> set[str]:
    """`tailor=selectiveness` -> {"selectiveness"}. One flag per area."""
    return {v for v in values or [] if v}


def anchor(area_key: str) -> str:
    """The fragment naming one area's card. compare.html gives the section this id.

    Every control on a card is a plain link doing a full navigation — the URL
    is the whole state and there is no JavaScript to preserve the scroll — so
    without the fragment, choosing a breakdown on the third card down answers
    by loading a fresh page at the top and the card the reader was reading
    scrolls out of sight.
    """
    return f"#area-{area_key}"


def link(params: list[tuple[str, str]], area_key: str, dimension: str | None) -> str:
    """The current query with this one area's cut replaced, or removed."""
    kept = [(k, v) for k, v in params if not (k == "cut" and v.split(":")[0] == area_key)]
    if dimension:
        kept.append(("cut", f"{area_key}:{dimension}"))
    return "/compare?" + urlencode(kept) + anchor(area_key)


def tailor_link(params: list[tuple[str, str]], area_key: str, on: bool) -> str:
    """The current query with this one area's tailoring switched on or off."""
    kept = [(k, v) for k, v in params if not (k == "tailor" and v == area_key)]
    if on:
        kept.append(("tailor", area_key))
    return "/compare?" + urlencode(kept) + anchor(area_key)


def context(
    cut: Cut,
    schools,
    records: list[dict],
    *,
    code_field: str,
    value,
    count,
    emphasis: int | None,
    note: str | None = None,
) -> dict:
    """Everything the cut partial renders, from one survey's rows.

    `records` are that survey's rows for the year, one per school and group,
    with the total under code 99. `value(record)` is the rate, `count(record)`
    the number of people behind it. Groups below MIN_COHORT are listed as
    suppressed rather than drawn. `note` replaces the cut's standing note when
    the area can say something more exact for this year.
    """
    drawn = dict(cut.groups)
    if emphasis in cut.own_only:
        drawn[emphasis] = cut.own_only[emphasis]

    by_school: dict[int, dict] = {}
    for record in records:
        code = record[code_field]
        if code != TOTAL and code not in drawn:
            continue
        entry = by_school.setdefault(
            record["unitid"], {"total": None, "rates": {}, "counts": {}, "suppressed": []}
        )
        rate, n = value(record), count(record)
        if rate is None:
            continue
        if code == TOTAL:
            entry["total"] = rate
            entry["counts"][TOTAL] = n
        elif n < MIN_COHORT:
            entry["suppressed"].append(code)
        else:
            entry["rates"][code] = rate
            entry["counts"][code] = n

    rows = []
    for school in schools:
        entry = by_school.get(
            school.unitid, {"total": None, "rates": {}, "counts": {}, "suppressed": []}
        )
        rows.append({"school": school, **entry})

    notices = []
    if emphasis is not None:
        too_small = [r["school"].short for r in rows if emphasis in r["suppressed"]]
        if too_small:
            notices.append(
                Notice(
                    "info",
                    f"Fewer than {MIN_COHORT} {cut.name(emphasis)} {cut.count_noun} at "
                    f"{', '.join(too_small)}, so no rate is drawn there: one person's "
                    f"outcome would move it by several points. IPEDS publishes a figure "
                    f"anyway; we do not.",
                )
            )

    return {
        "cut": cut,
        "note": note or cut.note,
        "emphasis": emphasis,
        "own_label": cut.name(emphasis),
        "title": f"{cut.metric} by {cut.label.lower()}",
        "columns": [(code, label) for code, label in drawn.items()],
        "rows": rows,
        "figure": figure(cut, rows, emphasis),
        "notices": notices,
    }


def _triangle(cx: float, cy: float) -> str:
    """Another group: an upright triangle centred on (cx, cy), as polygon points.

    Centred on its bounding box rather than its circumcircle, so it sits on the
    same optical line as the circle and the square beside it.
    """
    return (
        f"{cx:.1f},{cy - GROUP_H:.1f} "
        f"{cx - GROUP_W:.1f},{cy + GROUP_H:.1f} "
        f"{cx + GROUP_W:.1f},{cy + GROUP_H:.1f}"
    )


def _square(cx: float, cy: float) -> dict:
    """Everyone: a hollow square centred on (cx, cy), as an SVG rect."""
    return {
        "x": round(cx - TOTAL_SIDE / 2, 1),
        "y": round(cy - TOTAL_SIDE / 2, 1),
        "side": TOTAL_SIDE,
    }


def figure(cut: Cut, rows: list[dict], emphasis: int | None) -> dict | None:
    """One row per school: a mark per group, everyone as a hollow marker.

    Tailored, the reader's group is the solid mark and the right-hand text is
    its distance from everyone. Asked for, every group is a mark and the text
    names the lowest and highest.

    **Three roles, three shapes**, and the shape rather than the colour is what
    carries the role. The reader's own group is a circle filled with the
    school's own brand colour — the identity every chart and chip on the page
    uses, and therefore a different colour on every row — so no single swatch
    can stand for it in a key. A shape can: the key draws the same circle,
    triangle and square the chart does, and says the circle takes each school's
    colour. Geometry lives here beside the rest of the layout so the template
    stays declarative and the two agree by construction.
    """
    entries = [r for r in rows if r["total"] is not None and r["rates"]]
    if not entries:
        return None
    labels = {**cut.groups, **cut.own_only}

    if emphasis is not None:
        entries.sort(
            key=lambda r: (r["rates"].get(emphasis) is None, -(r["rates"].get(emphasis) or 0))
        )
    else:

        def spread(r: dict) -> float:
            return max(r["rates"].values()) - min(r["rates"].values())

        entries.sort(key=spread, reverse=True)

    width, row_h = 640, 30
    left, right, top, bottom = 150, 190, 14, 30
    plot_w = width - left - right
    height = top + row_h * len(entries) + bottom

    values = [v for r in entries for v in r["rates"].values()] + [r["total"] for r in entries]
    low = max(min(values) - 0.03, 0.0)
    high = min(max(values) + 0.02, 1.0)
    span = high - low or 1

    def x(value: float) -> float:
        return left + plot_w * (value - low) / span

    def pct(value: float) -> str:
        return percent(value, cut.places)

    bars = []
    for i, row in enumerate(entries):
        y = top + row_h * i + row_h / 2
        own = row["rates"].get(emphasis) if emphasis is not None else None
        if emphasis is not None:
            if own is not None:
                diff = (own - row["total"]) * 100
                sign = "+" if diff >= 0 else "−"
                distance = f"{sign}{abs(diff):.{cut.places}f}"
                text = f"{labels[emphasis]} {pct(own)} vs {pct(row['total'])} ({distance})"
            elif emphasis in row["suppressed"]:
                text = f"{labels[emphasis]}: under {MIN_COHORT} {cut.count_noun}"
            else:
                text = f"{labels[emphasis]}: not reported"
        else:
            lo = min(row["rates"].items(), key=lambda kv: kv[1])
            hi = max(row["rates"].items(), key=lambda kv: kv[1])
            text = (
                f"{labels[lo[0]]} {pct(lo[1])} – {labels[hi[0]]} {pct(hi[1])}"
                if lo[0] != hi[0]
                else f"{labels[lo[0]]} {pct(lo[1])}"
            )
        bars.append(
            {
                "name": row["school"].short,
                "color": row["school"].color,
                "y": round(y, 1),
                "text_y": round(y + 4, 1),
                "everyone": _square(x(row["total"]), y),
                "total": pct(row["total"]),
                "dots": [
                    {
                        "x": round(x(rate), 1),
                        "points": _triangle(x(rate), y),
                        "label": f"{labels[code]}: {pct(rate)}",
                        "own": code == emphasis,
                    }
                    for code, rate in row["rates"].items()
                ],
                "text": text,
                "text_x": width - right + 12,
            }
        )

    ticks = [
        {
            "x": round(x(low + span * i / 4), 1),
            "label": percent(low + span * i / 4, 0),
            "y_end": height - bottom + 6,
        }
        for i in range(5)
    ]

    return {
        "width": width,
        "height": height,
        "bars": bars,
        "ticks": ticks,
        "axis_y": height - bottom + 20,
        "top": top - 6,
        "label_x": left - 14,
    }
