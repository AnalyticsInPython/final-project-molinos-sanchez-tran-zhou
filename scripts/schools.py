"""The working sample: 25 well-known, highly selective national universities.

`indicative_rank` is a rough ordering drawn from where these schools generally
sit in widely-cited national rankings. It is NOT US News's list — we do not
license or reproduce their rankings, and the exact ordering between adjacent
schools is not meaningful. It exists only so the sample is easy to eyeball
while we scope; nothing in the product should depend on it.

Sample bias, stated up front: these are 25 of the most selective and best
resourced universities in the country. They are useful for building because
they have near-complete IPEDS reporting, and useless as a picture of American
higher education. Any coverage number measured here is a best case.

unitids resolved against the IPEDS 2022 directory.
"""

SCHOOLS = [
    (186131, "Princeton University", 1),
    (166683, "Massachusetts Institute of Technology", 2),
    (166027, "Harvard University", 3),
    (243744, "Stanford University", 4),
    (130794, "Yale University", 5),
    (215062, "University of Pennsylvania", 6),
    (110404, "California Institute of Technology", 7),
    (198419, "Duke University", 8),
    (217156, "Brown University", 9),
    (162928, "Johns Hopkins University", 10),
    (147767, "Northwestern University", 11),
    (190150, "Columbia University in the City of New York", 12),
    (190415, "Cornell University", 13),
    (144050, "University of Chicago", 14),
    (110635, "University of California-Berkeley", 15),
    (110662, "University of California-Los Angeles", 16),
    (227757, "Rice University", 17),
    (182670, "Dartmouth College", 18),
    (221999, "Vanderbilt University", 19),
    (152080, "University of Notre Dame", 20),
    (170976, "University of Michigan-Ann Arbor", 21),
    (131496, "Georgetown University", 22),
    (199120, "University of North Carolina at Chapel Hill", 23),
    (211440, "Carnegie Mellon University", 24),
    (179867, "Washington University in St Louis", 25),
]

UNITIDS = [unitid for unitid, _, _ in SCHOOLS]
