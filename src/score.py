"""
score.py — Deterministic scoring engine. Takes a profile and an extraction
result (output of extract.py) and computes a qualification-match score.

CRITICAL DESIGN PRINCIPLE: this file contains ZERO calls to any LLM. Every
number here is computed by plain, auditable code, following the rubric
documented in eval/scoring_rubric.md. If this file and that document ever
disagree, the document is the source of truth and this code has a bug.

Usage:
    python3 score.py data/extracted/jd_01_growth_pm_extracted.json
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
PROFILE_PATH = PROJECT_ROOT / "profile" / "my_profile.json"

SENIORITY_ORDER = ["entry", "associate", "mid", "senior", "lead", "principal"]

CATEGORY_WEIGHTS = {
    "must_have": 0.50,
    "nice_to_have": 0.15,
    "seniority": 0.20,
    "domain": 0.15,
}

WEAK_THRESHOLD = 0.5  # a requirement scoring below this counts as "weak"

PENALTY_BANDS = [
    (0.2, 1.0),
    (0.4, 0.85),
    (0.6, 0.6),
    (1.0, 0.35),  # anything above 0.6 weak_ratio falls here
]


def load_profile() -> dict:
    with open(PROFILE_PATH) as f:
        return json.load(f)


def load_extraction(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def find_profile_match(requirement: dict, profile: dict):
    """Find a matching entry in the profile for a given extracted requirement.
    Returns the matched entry (dict) or None. Matching is by exact, case-
    insensitive name match within the correct profile section — deliberately
    simple (no fuzzy matching) so results stay explainable. Fuzzy/semantic
    matching is a known v1 limitation, see scoring_rubric.md.

    IMPORTANT: matches against canonical_skill, NOT text. canonical_skill is
    the LLM's normalized, profile-matchable name for the requirement (e.g.
    "SQL" rather than "SQL proficiency"); text is just the human-readable
    label. This split exists because exact-match scoring needs a stable,
    short name, while displaying "SQL proficiency" to the user is more
    readable than displaying "SQL" alone. See decisions log: this schema
    change was made after the first real extraction run produced 0% scores
    across the board because every requirement was a full descriptive
    phrase with no bare-skill-name field to match against.

    NOTE on skill_type "skill" vs "tool": the LLM's classification of a
    requirement as a "skill" vs a "tool" is inherently fuzzy (is SQL a skill
    or a tool? reasonable people disagree). Rather than gate matching on
    that classification, requirements typed as either "skill" or "tool"
    are checked against BOTH the profile's skills and tools sections. This
    was added after a real run showed SQL (extracted as skill_type="tool")
    failing to match a profile entry that existed under "skills", purely
    because of which section each side happened to file it under."""
    skill_type = requirement.get("skill_type")
    req_text = requirement.get("canonical_skill", requirement.get("text", "")).strip().lower()

    if skill_type in ("skill", "tool"):
        sections_to_search = ["skills", "tools"]
    elif skill_type == "certification":
        sections_to_search = ["certifications"]
    elif skill_type == "domain":
        sections_to_search = ["domains"]
    else:
        return None

    for section_key in sections_to_search:
        for entry in profile.get(section_key, []):
            if entry.get("name", "").strip().lower() == req_text:
                return entry

    return None


def score_education_requirement(requirement: dict, profile: dict) -> float:
    """Education needs different matching logic than skills/tools/domains:
    it's about degree LEVEL (does a Bachelor's/Master's exist), not an exact
    name match. canonical_skill for education entries should contain the
    degree level (e.g. "Bachelor's degree", "Master's degree").

    Simple rule: if the JD's canonical_skill mentions "bachelor" and the
    profile has ANY degree at bachelor's level or higher (bachelor's,
    master's/msc/mba, or phd), full credit. Same logic for "master".
    This is deliberately coarse (string-matching on degree level keywords)
    rather than a full taxonomy — a known v1 simplification."""
    canonical = requirement.get("canonical_skill", "").lower()
    profile_degrees = [e.get("degree", "").lower() for e in profile.get("education", [])]

    degree_rank = {"bachelor": 1, "bachelors": 1, "ba": 1, "bsc": 1,
                   "master": 2, "masters": 2, "msc": 2, "mba": 2,
                   "phd": 3, "doctorate": 3}

    def rank_of(degree_str):
        for keyword, rank in degree_rank.items():
            if keyword in degree_str:
                return rank
        return 0

    profile_max_rank = max([rank_of(d) for d in profile_degrees], default=0)

    required_rank = 0
    for keyword, rank in degree_rank.items():
        if keyword in canonical:
            required_rank = max(required_rank, rank)

    if required_rank == 0:
        return 0.5  # JD mentioned education but we couldn't parse the level; neutral score, not zero

    return 1.0 if profile_max_rank >= required_rank else 0.0


def score_work_eligibility_requirement(requirement: dict, profile: dict) -> float:
    """Work eligibility/visa requirements shouldn't be scored as a generic
    skill match (they'd always fail — no profile has a 'skills' entry
    called "eligible to work in Ireland"). Instead, check the profile's
    location.work_authorization field as free text.

    This is a coarse v1 heuristic, not real visa-rule parsing:
    - Empty/unset work_authorization -> 0.5 (unknown, neutral — don't
      penalize for an unanswered profile field)
    - Text suggesting sponsorship IS needed (keywords: "sponsorship",
      "visa required", "requires sponsorship") -> 0.1, NOT 0.0. A JD
      requiring "no sponsorship" against a candidate who needs sponsorship
      is a real, serious mismatch, but flooring at 0.1 rather than 0.0
      keeps it consistent with how every other gap is scored elsewhere
      in this rubric (see the years-shortfall floor) rather than creating
      a special instant-disqualifying zero.
    - Any other non-empty text (e.g. "EU/EEA citizen", "Stamp 4",
      "permanent residency") -> 1.0, treated as eligible.
    This does NOT parse specific visa categories or match them against
    what a specific JD requires — flagged as a known v1 limitation. The
    flags system (separate from scoring) already surfaces the raw JD
    text on this topic for the user to read and judge for themselves."""
    work_auth = profile.get("location", {}).get("work_authorization", "").strip().lower()

    if not work_auth:
        return 0.5

    needs_sponsorship_keywords = ["requires visa sponsorship", "requires sponsorship", "visa required", "needs sponsorship"]
    if any(kw in work_auth for kw in needs_sponsorship_keywords):
        return 0.1

    return 1.0


def score_single_requirement(requirement: dict, profile: dict) -> float:
    """Implements the per-requirement scoring rule from scoring_rubric.md."""
    canonical = requirement.get("canonical_skill", "").lower()
    is_work_eligibility = (
        requirement.get("skill_type") == "other"
        and any(kw in canonical for kw in ["sponsorship", "eligib", "visa", "work permit", "right to work"])
    )
    if is_work_eligibility:
        return score_work_eligibility_requirement(requirement, profile)

    if requirement.get("skill_type") == "education":
        return score_education_requirement(requirement, profile)

    match = find_profile_match(requirement, profile)

    if match is None:
        return 0.0

    min_years = requirement.get("minimum_years")
    if min_years is None:
        return 1.0

    profile_years = match.get("years", 0)
    if profile_years >= min_years:
        return 1.0

    if min_years <= 0:
        return 1.0  # avoid division by zero on malformed data

    ratio = profile_years / min_years
    return max(0.1, ratio)


def weighted_average(scored_requirements: list) -> float:
    """scored_requirements: list of (score, confidence) tuples."""
    if not scored_requirements:
        return None
    total_weight = sum(conf for _, conf in scored_requirements)
    if total_weight == 0:
        return None
    return sum(score * conf for score, conf in scored_requirements) / total_weight


def apply_penalty_multiplier(weak_ratio: float) -> float:
    for threshold, multiplier in PENALTY_BANDS:
        if weak_ratio <= threshold:
            return multiplier
    return PENALTY_BANDS[-1][1]


def score_must_haves(requirements: list, profile: dict) -> dict:
    must_haves = [r for r in requirements if r["category"] == "must_have"]
    if not must_haves:
        return {"score": None, "detail": "No must-have requirements extracted.", "items": []}

    scored = []
    items = []
    for req in must_haves:
        s = score_single_requirement(req, profile)
        scored.append((s, req["confidence"]))
        items.append({"text": req["text"], "score": round(s, 2), "confidence": req["confidence"]})

    raw_avg = weighted_average(scored)
    weak_count = sum(1 for s, _ in scored if s < WEAK_THRESHOLD)
    weak_ratio = weak_count / len(scored)
    multiplier = apply_penalty_multiplier(weak_ratio)
    final_score = raw_avg * multiplier

    return {
        "score": round(final_score, 3),
        "raw_average_before_penalty": round(raw_avg, 3),
        "weak_ratio": round(weak_ratio, 2),
        "penalty_multiplier": multiplier,
        "items": items,
    }


def score_nice_to_haves(requirements: list, profile: dict) -> dict:
    nice_haves = [r for r in requirements if r["category"] == "nice_to_have"]
    if not nice_haves:
        return {"score": None, "detail": "No nice-to-have requirements extracted.", "items": []}

    scored = []
    items = []
    for req in nice_haves:
        s = score_single_requirement(req, profile)
        scored.append((s, req["confidence"]))
        items.append({"text": req["text"], "score": round(s, 2), "confidence": req["confidence"]})

    avg = weighted_average(scored)
    return {"score": round(avg, 3) if avg is not None else None, "items": items}


def score_seniority(extraction: dict, profile: dict) -> dict:
    jd_level = extraction["seniority_signal"]["level"]
    profile_level = profile["seniority_level"]

    if jd_level == "unclear" or jd_level not in SENIORITY_ORDER:
        return {"score": None, "detail": "JD seniority signal unclear; excluded from score."}

    distance = abs(SENIORITY_ORDER.index(profile_level) - SENIORITY_ORDER.index(jd_level))

    if distance == 0:
        score = 1.0
    elif distance == 1:
        score = 0.7
    elif distance == 2:
        score = 0.4
    else:
        score = 0.1

    return {
        "score": score,
        "profile_level": profile_level,
        "jd_level": jd_level,
        "distance": distance,
    }


def score_domain(extraction: dict, profile: dict) -> dict:
    required_domains = [d["domain"] for d in extraction.get("domain_signals", []) if d.get("required")]

    if not required_domains:
        return {"score": None, "detail": "No required domains stated in JD; excluded from score."}

    profile_domain_names = {d["name"].strip().lower() for d in profile.get("domains", [])}
    matched = [d for d in required_domains if d.strip().lower() in profile_domain_names]

    score = len(matched) / len(required_domains)

    return {
        "score": round(score, 3),
        "required_domains": required_domains,
        "matched_domains": matched,
    }


def redistribute_weights(category_scores: dict) -> dict:
    """If seniority and/or domain were excluded (None), redistribute their
    weight proportionally across the remaining categories, per the rubric."""
    active = {k: v for k, v in CATEGORY_WEIGHTS.items() if category_scores.get(k) is not None}
    excluded_weight = sum(w for k, w in CATEGORY_WEIGHTS.items() if k not in active)

    if not active:
        return {}

    active_total = sum(active.values())
    adjusted = {}
    for k, w in active.items():
        adjusted[k] = w + (w / active_total) * excluded_weight

    return adjusted


def compute_overall_score(extraction: dict, profile: dict) -> dict:
    requirements = extraction.get("requirements", [])

    must_have_result = score_must_haves(requirements, profile)
    nice_have_result = score_nice_to_haves(requirements, profile)
    seniority_result = score_seniority(extraction, profile)
    domain_result = score_domain(extraction, profile)

    category_scores = {
        "must_have": must_have_result["score"],
        "nice_to_have": nice_have_result["score"],
        "seniority": seniority_result["score"],
        "domain": domain_result["score"],
    }

    adjusted_weights = redistribute_weights(category_scores)

    overall = 0.0
    for category, score in category_scores.items():
        if score is not None and category in adjusted_weights:
            overall += score * adjusted_weights[category]

    return {
        "overall_score": round(overall, 3),
        "overall_score_pct": round(overall * 100, 1),
        "category_breakdown": {
            "must_have": must_have_result,
            "nice_to_have": nice_have_result,
            "seniority": seniority_result,
            "domain": domain_result,
        },
        "adjusted_weights_used": {k: round(v, 3) for k, v in adjusted_weights.items()},
        "flags": extraction.get("flags", []),
    }


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 score.py <path_to_extracted_jd.json>")
        sys.exit(1)

    extraction_path = Path(sys.argv[1])
    if not extraction_path.exists():
        print(f"ERROR: File not found: {extraction_path}")
        sys.exit(1)

    profile = load_profile()
    extraction = load_extraction(extraction_path)

    result = compute_overall_score(extraction, profile)

    print(f"\n=== Fit Score: {result['overall_score_pct']}% ===\n")
    for category, detail in result["category_breakdown"].items():
        weight = result["adjusted_weights_used"].get(category)
        score = detail["score"]
        if score is None:
            print(f"{category.upper()}: excluded ({detail.get('detail', '')})")
        else:
            print(f"{category.upper()}: {round(score * 100, 1)}% (weight: {round(weight * 100, 1) if weight else 0}%)")

    if result["flags"]:
        print(f"\nFlags ({len(result['flags'])}):")
        for f in result["flags"]:
            print(f"  [{f['type']}] {f['description']}")

    output_path = extraction_path.parent / f"{extraction_path.stem}_score.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nFull breakdown saved to: {output_path}")


if __name__ == "__main__":
    main()
