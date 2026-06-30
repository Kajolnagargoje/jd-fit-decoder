"""
test_score_offline.py — Verifies score.py implements the rubric in
scoring_rubric.md correctly, using hand-crafted mock extraction data
(no API calls, no dependency on extract.py having run).

Three scenarios:
1. Strong match — should score high
2. Weak match — several missing must-haves — should score low (tests the
   punishing aggregation penalty)
3. Partial years shortfall — tests the partial-credit ratio logic

Usage:
    python3 test_score_offline.py
"""

import json
from pathlib import Path

from score import compute_overall_score, load_profile

# Use a temporary in-memory profile so this test doesn't depend on the
# real my_profile.json being filled in correctly — keeps the test stable
# even as the user edits their real profile.
TEST_PROFILE = {
    "seniority_level": "mid",
    "total_years_experience": 4,
    "skills": [
        {"name": "Product requirements definition", "years": 4, "proficiency": "strong"},
        {"name": "SQL", "years": 2, "proficiency": "working"},
        {"name": "Stakeholder management", "years": 4, "proficiency": "strong"},
    ],
    "domains": [
        {"name": "EdTech", "years": 4},
    ],
    "tools": [
        {"name": "Jira", "proficiency": "working"},
    ],
    "certifications": [
        {"name": "CSPO", "year_obtained": None},
    ],
}


def scenario_strong_match():
    """All must-haves present and sufficient, seniority matches exactly."""
    extraction = {
        "requirements": [
            {"text": "Product requirements definition", "canonical_skill": "Product requirements definition", "category": "must_have", "skill_type": "skill",
             "minimum_years": 2, "confidence": 0.9, "source_quote": "x"},
            {"text": "Stakeholder management", "canonical_skill": "Stakeholder management", "category": "must_have", "skill_type": "skill",
             "minimum_years": 3, "confidence": 0.9, "source_quote": "x"},
            {"text": "CSPO", "canonical_skill": "CSPO", "category": "nice_to_have", "skill_type": "certification",
             "minimum_years": None, "confidence": 0.9, "source_quote": "x"},
        ],
        "seniority_signal": {"level": "mid", "confidence": 0.9, "reasoning": "x"},
        "domain_signals": [{"domain": "EdTech", "required": True}],
        "flags": [],
    }
    result = compute_overall_score(extraction, TEST_PROFILE)
    print("SCENARIO 1 — Strong match (expect HIGH score, ~90%+)")
    print(f"  Overall: {result['overall_score_pct']}%")
    assert result["overall_score_pct"] > 85, f"Expected >85%, got {result['overall_score_pct']}%"
    print("  ✓ PASSED\n")


def scenario_weak_match():
    """Several missing must-haves + seniority mismatch — should score low."""
    extraction = {
        "requirements": [
            {"text": "Python", "canonical_skill": "Python", "category": "must_have", "skill_type": "skill",  # NOT in profile
             "minimum_years": 3, "confidence": 0.9, "source_quote": "x"},
            {"text": "Machine learning", "canonical_skill": "Machine learning", "category": "must_have", "skill_type": "skill",  # NOT in profile
             "minimum_years": 2, "confidence": 0.9, "source_quote": "x"},
            {"text": "Stakeholder management", "canonical_skill": "Stakeholder management", "category": "must_have", "skill_type": "skill",  # IS in profile
             "minimum_years": 3, "confidence": 0.9, "source_quote": "x"},
        ],
        "seniority_signal": {"level": "principal", "confidence": 0.9, "reasoning": "x"},  # far from "mid"
        "domain_signals": [{"domain": "FinTech", "required": True}],  # not in profile
        "flags": [],
    }
    result = compute_overall_score(extraction, TEST_PROFILE)
    print("SCENARIO 2 — Weak match (expect LOW score, <35%)")
    print(f"  Overall: {result['overall_score_pct']}%")
    print(f"  Must-have weak_ratio: {result['category_breakdown']['must_have']['weak_ratio']}")
    print(f"  Must-have penalty multiplier: {result['category_breakdown']['must_have']['penalty_multiplier']}")
    assert result["overall_score_pct"] < 35, f"Expected <35%, got {result['overall_score_pct']}%"
    print("  ✓ PASSED\n")


def scenario_partial_years():
    """SQL: JD wants 5 years, profile has 2 → should score 2/5 = 0.4 on that item."""
    extraction = {
        "requirements": [
            {"text": "SQL", "canonical_skill": "SQL", "category": "must_have", "skill_type": "skill",
             "minimum_years": 5, "confidence": 0.9, "source_quote": "x"},
        ],
        "seniority_signal": {"level": "unclear", "confidence": 0.3, "reasoning": "x"},
        "domain_signals": [],
        "flags": [],
    }
    result = compute_overall_score(extraction, TEST_PROFILE)
    sql_item_score = result["category_breakdown"]["must_have"]["items"][0]["score"]
    print("SCENARIO 3 — Partial years shortfall (SQL: profile has 2yr, JD wants 5yr)")
    print(f"  SQL item score: {sql_item_score} (expect 0.4)")
    assert sql_item_score == 0.4, f"Expected 0.4, got {sql_item_score}"
    print("  ✓ PASSED\n")


if __name__ == "__main__":
    print("=== Offline Scoring Engine Test ===\n")
    scenario_strong_match()
    scenario_weak_match()
    scenario_partial_years()
    print("All scenarios passed.")
