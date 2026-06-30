# Scoring Rubric v1 — Decision Log

This document is the human-readable spec for the scoring engine. The code in
score.py should be a direct, literal implementation of this document — if they
diverge, this document wins and the code is wrong.

## Top-level weighting

| Category                  | Weight |
|----------------------------|--------|
| Must-have requirements      | 50%    |
| Nice-to-have requirements    | 15%    |
| Seniority alignment         | 20%    |
| Domain alignment           | 15%    |

**Why these weights:** Must-haves dominate because they're the actual
gatekeeping criteria — failing them is the single biggest predictor of
rejection. Seniority is weighted above nice-to-haves because a seniority
mismatch (e.g. JD wants senior, candidate is mid) tends to be a harder
blocker than missing a bonus skill. Domain and nice-to-haves are weighted
lowest because they're the most forgivable / most transferable gaps.

## Per-requirement scoring (must-have and nice-to-have use the same logic)

For each extracted requirement, find the matching entry in the profile
(matched by skill_type: skill→skills, tool→tools, domain→domains,
certification→certifications). EDUCATION is a special case — see below.

- **No match found in profile at all** → score = 0.0
- **Match found, no minimum_years stated in the requirement** → score = 1.0
  if matched (presence is enough; we have no years bar to fall short of)
- **Match found, minimum_years stated, profile years >= minimum_years**
  → score = 1.0
- **Match found, minimum_years stated, profile years < minimum_years**
  → score = max(0.1, profile_years / minimum_years)
  - Floored at 0.1, not 0.0, because *some* relevant experience is never
    worthless — but capped low enough that it's clearly a gap, not a pass.
  - Example: JD wants 5 years SQL, profile has 2 years → score = 0.4

### Education (special case)

Education requirements (skill_type = "education") don't use name-matching —
they use a degree-level comparison: bachelor's < master's < phd. If the JD
states a minimum degree level (parsed from canonical_skill containing
keywords like "bachelor"/"master"/"phd"), the profile passes if it has ANY
degree at that level or higher. If the JD's required level can't be parsed
from canonical_skill, score defaults to 0.5 (neutral, not zero — an
unparseable requirement shouldn't be treated as definitely failed).
This is a deliberately coarse v1 approach (keyword-matching on degree level,
not field-of-study matching) — a JD requiring "Bachelor's in Computer
Science" will currently pass on ANY bachelor's degree, regardless of field.
Flagged as a known limitation.

**Confidence dampening:** each requirement's contribution to the category
average is weighted by its extraction confidence score. A requirement
extracted at confidence 0.4 contributes less to the average than one at
confidence 0.95. This prevents a shaky, ambiguous extraction from swinging
the score as hard as a clearly-stated requirement.

Formula per category:
```
category_score = sum(requirement_score * confidence) / sum(confidence)
```
(weighted average using confidence as the weight)

## Aggregation penalty (what makes must-haves "punishing")

A simple average of must-have scores is NOT punishing enough on its own —
it would let several weak requirements average out against a few strong
ones. To make gaps actually hurt in aggregate, apply a penalty multiplier
based on the proportion of must-haves scoring below 0.5 ("weak"):

```
weak_ratio = count(must_have scores < 0.5) / count(all must_haves)

if weak_ratio <= 0.2:
    penalty_multiplier = 1.0          # a single weak item among many is fine
elif weak_ratio <= 0.4:
    penalty_multiplier = 0.85         # noticeable but not severe
elif weak_ratio <= 0.6:
    penalty_multiplier = 0.6          # a real qualification problem
else:
    penalty_multiplier = 0.35         # most must-haves are weak — score
                                       # should reflect a poor match clearly

must_have_category_score = weighted_average_score * penalty_multiplier
```

This is a deliberately simple step-function rather than a smooth curve —
easier to explain and defend in an interview ("here are the four bands and
why") than a formula that looks more 'rigorous' but is harder to justify
plainly. This is documented as a v1 simplification; a v2 could explore a
smoother decay function if the step boundaries produce visibly odd results
on real JDs.

## Seniority alignment scoring

Ordinal scale: entry=0, associate=1, mid=2, senior=3, lead=4, principal=5

```
distance = abs(profile_level_index - jd_level_index)

if distance == 0: score = 1.0
if distance == 1: score = 0.7
if distance == 2: score = 0.4
if distance >= 3: score = 0.1
```

If the JD's seniority_signal.level is "unclear", seniority alignment is
excluded from the score entirely and that 20% weight is redistributed
proportionally across the other three categories. (Don't penalize the
candidate for the JD being vague about seniority.)

## Domain alignment scoring

For each domain_signal in the extraction marked required=true, check if it
appears in the profile's domains list (any years > 0 counts as a match,
since unlike skills, domain *exposure* matters more than years depth).

- If no domains are marked required=true in the extraction → domain score
  = 1.0 by default (don't penalize for something the JD didn't ask for),
  and that weight is redistributed like the seniority case above.
- If one or more required domains exist → score = (number matched) /
  (number required)

## What this rubric deliberately does NOT do (v1 limitations, for the
decisions log)

- Domain extraction occasionally conflates industry vertical (EdTech, SaaS,
  FinTech — what the profile's domains list is designed to capture) with
  functional specialization (Growth, Activation, B2B vs B2C motion — not
  something the profile models). Observed in a real run where "Growth/
  Activation" was extracted as a required domain and correctly scored 0%
  against a profile with no matching entry — technically correct given the
  schema, but arguably the wrong category for that signal. Not fixed in v1;
  flagged as a known limitation rather than further tuning the prompt, to
  avoid an open-ended edge-case-chasing loop. Worth revisiting if it recurs
  across the eval set.

- Does not weight individual requirements differently within a category
  (e.g. "SQL" and "PowerPoint" count equally as must-haves if both are
  flagged must-have, even though SQL probably matters more). A v2 could
  let requirements carry an importance weight, but that requires either
  more LLM judgment (which we're trying to keep deterministic) or manual
  tagging (which doesn't scale). Flagged as a known simplification.
- Does not consider *recency* of experience (a skill used 4 years ago vs
  last month scores the same). Could be added via a recency field on
  profile skills in v2.
- The penalty bands (0.2 / 0.4 / 0.6 thresholds) are reasoned defaults, not
  empirically tuned — they should be sanity-checked against real JD results
  and adjusted if they produce obviously wrong-feeling scores.
