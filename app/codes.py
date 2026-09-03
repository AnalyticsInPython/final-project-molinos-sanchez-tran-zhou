"""IPEDS code-to-label mappings shared by the areas that read them.

Third copy prevention. These labels were written out once in
`app/areas/enrollment.py` and again in `app/profiles.py`, and retention needs
them too — at which point a shared home is cheaper than keeping three in step.

**`app/profiles.py` deliberately keeps its own and is not migrated here.** Its
list looks almost identical and means something different: code 9 there is
"Prefer not to say", a person declining to answer a form, where code 9 in the
federal data is "Race/ethnicity unknown", a school that did not report. Code 8
is likewise "Nonresident" as a self-description and "International" as a
category of student. Folding those together would produce a mapping that reads
correctly and mislabels half its rows.
"""

# Verified against the Urban Institute API's varlist. 99 is the published
# total across all categories and is not an identity, so it is not here — an
# area that needs the total asks for 99 explicitly.
RACE = {
    1: "White",
    2: "Black",
    3: "Hispanic",
    4: "Asian",
    5: "American Indian or Alaska Native",
    6: "Native Hawaiian or other Pacific Islander",
    7: "Two or more races",
    8: "International",
    9: "Race/ethnicity unknown",
}

# The order a chart stacks or lists them in. Not a codebook order: the two
# categories that describe an absence of information rather than a group of
# people — international students and unreported ethnicity — go last, so a
# reader comparing schools is not led by a gap in the reporting.
RACE_ORDER = [1, 2, 3, 4, 5, 6, 7, 8, 9]

# Groups that describe reporting rather than a background a student would
# recognise as theirs. An equity gap computed across these is measuring the
# registrar, not the school.
NOT_AN_IDENTITY = (8, 9)

# IPEDS records sex as men and women only. 99 is the total.
SEX = {1: "Men", 2: "Women"}

# The total across all categories, in every dimension IPEDS breaks out.
TOTAL = 99
