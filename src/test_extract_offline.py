"""
test_extract_offline.py — Verifies the extraction pipeline's validation and
quote-checking logic WITHOUT calling the real API. Uses a hand-written mock
LLM response to prove the schema validation, JSON parsing, and verbatim
quote-checking all work correctly before spending API calls on the real thing.

This is also useful as a permanent regression test: if you change the schema
later, run this to confirm the validation logic still behaves correctly.

Usage:
    python3 test_extract_offline.py
"""

import json
from pathlib import Path

from extract import check_quotes_verbatim, load_schema
from jsonschema import validate, ValidationError

PROJECT_ROOT = Path(__file__).parent.parent
JD_PATH = PROJECT_ROOT / "data" / "sample_jds" / "jd_01_growth_pm.txt"

# A realistic mock response, written by hand to resemble what the LLM should
# produce for jd_01_growth_pm.txt. Deliberately includes ONE bad quote
# (a fabricated one) to verify the quote-checker actually catches it.
MOCK_LLM_RESPONSE = {
    "requirements": [
        {
            "text": "Product management experience",
            "canonical_skill": "Product management experience",
            "category": "must_have",
            "skill_type": "years_experience",
            "minimum_years": 3,
            "confidence": 0.95,
            "source_quote": "3+ years of product management experience, ideally in SaaS or EdTech"
        },
        {
            "text": "SQL proficiency",
            "canonical_skill": "SQL",
            "category": "must_have",
            "skill_type": "skill",
            "minimum_years": None,
            "confidence": 0.85,
            "source_quote": "Strong analytical skills; comfortable working with SQL and dashboarding tools"
        },
        {
            "text": "A/B testing experience",
            "canonical_skill": "A/B testing",
            "category": "must_have",
            "skill_type": "skill",
            "minimum_years": None,
            "confidence": 0.9,
            "source_quote": "Proven track record of running experiments (A/B testing) and driving measurable improvements"
        },
        {
            "text": "CSPO certification",
            "canonical_skill": "CSPO",
            "category": "nice_to_have",
            "skill_type": "certification",
            "minimum_years": None,
            "confidence": 0.9,
            "source_quote": "CSPO or similar certification a plus"
        },
        {
            "text": "This quote was fabricated and does not exist in the JD",
            "canonical_skill": "This quote was fabricated and does not exist in the JD",
            "category": "nice_to_have",
            "skill_type": "other",
            "minimum_years": None,
            "confidence": 0.5,
            "source_quote": "This sentence was never actually written in the job description text"
        }
    ],
    "seniority_signal": {
        "level": "mid",
        "confidence": 0.8,
        "reasoning": "3+ years required and individual ownership of a roadmap area suggests mid-level, not senior."
    },
    "domain_signals": [
        {"domain": "EdTech", "required": False},
        {"domain": "SaaS", "required": False}
    ],
    "flags": [
        {
            "type": "vague_scope",
            "description": "Phrase suggests broad, undefined responsibilities beyond the core PM role.",
            "source_quote": "We move fast and wear many hats"
        }
    ]
}


def run_offline_test():
    print("=== Offline Pipeline Test (no API calls) ===\n")

    schema = load_schema()
    jd_text = JD_PATH.read_text()

    print("1. Validating mock response against extraction_schema.json...")
    try:
        validate(instance=MOCK_LLM_RESPONSE, schema=schema)
        print("   ✓ PASSED — mock response is schema-valid.\n")
    except ValidationError as e:
        print(f"   ✗ FAILED — {e}\n")
        return

    print("2. Running verbatim quote check against real JD text...")
    warnings = check_quotes_verbatim(MOCK_LLM_RESPONSE, jd_text)
    print(f"   Found {len(warnings)} warning(s):")
    for w in warnings:
        print(f"   - {w}")

    if len(warnings) == 1 and "fabricated" in warnings[0].lower():
        print("\n   ✓ PASSED — quote checker correctly caught the fabricated quote")
        print("     and did not flag any of the real quotes.\n")
    else:
        print("\n   ✗ UNEXPECTED — expected exactly 1 warning about the fabricated quote.\n")

    print("3. Summary stats (same as what main script would print):")
    print(f"   Requirements extracted: {len(MOCK_LLM_RESPONSE['requirements'])}")
    print(f"   Seniority signal: {MOCK_LLM_RESPONSE['seniority_signal']['level']}")
    print(f"   Flags raised: {len(MOCK_LLM_RESPONSE['flags'])}")


if __name__ == "__main__":
    run_offline_test()
