"""
extract.py — Calls the LLM to extract structured requirements from a job
description, validates the output against extraction_schema.json, and
saves the result.

Usage:
    python3 extract.py data/sample_jds/jd_01_growth_pm.txt

Design notes (for the decisions log / interview talking points):
- The LLM is only ever used for extraction (turning messy text into
  structured data). It never computes the final score — that's a separate,
  deterministic step (see score.py). This is a deliberate separation of
  concerns: LLM for parsing ambiguity, plain code for the actual decision.
- Output is validated against a JSON Schema before being trusted. If the
  LLM returns malformed JSON or violates the schema, this script fails
  loudly rather than silently passing bad data downstream.
- A lightweight "quote check" cross-references every source_quote against
  the original JD text, flagging (not blocking) any quote that doesn't
  actually appear verbatim — a cheap hallucination tripwire.
"""

import json
import sys
from pathlib import Path

import anthropic
from jsonschema import validate, ValidationError

PROJECT_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "extraction_schema.json"
PROMPT_PATH = PROJECT_ROOT / "src" / "extraction_prompt.txt"
OUTPUT_DIR = PROJECT_ROOT / "data" / "extracted"

MODEL = "claude-sonnet-4-5"


def load_schema() -> dict:
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def load_prompt_template() -> str:
    with open(PROMPT_PATH) as f:
        return f.read()


def build_prompt(jd_text: str, schema: dict) -> str:
    template = load_prompt_template()
    return template.format(
        schema=json.dumps(schema, indent=2),
        jd_text=jd_text,
    )


def call_llm(prompt: str) -> str:
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def strip_markdown_fences(text: str) -> str:
    """LLMs sometimes wrap JSON in ```json fences despite instructions not to.
    Strip them defensively rather than relying on the model's compliance."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def check_quotes_verbatim(extraction: dict, jd_text: str) -> list:
    """Cross-reference every source_quote against the original JD text.
    Returns a list of warnings for quotes that don't appear verbatim —
    a cheap, mechanical hallucination check. This does NOT catch every
    hallucination (the LLM could quote real text out of context), but it
    catches the cheapest, most common failure mode: invented quotes."""
    warnings = []
    normalized_jd = " ".join(jd_text.split())

    for req in extraction.get("requirements", []):
        quote = req.get("source_quote", "")
        normalized_quote = " ".join(quote.split())
        if normalized_quote and normalized_quote not in normalized_jd:
            warnings.append(
                f"REQUIREMENT QUOTE NOT FOUND VERBATIM: '{quote}' "
                f"(requirement: '{req.get('text')}')"
            )

    for flag in extraction.get("flags", []):
        quote = flag.get("source_quote", "")
        normalized_quote = " ".join(quote.split())
        if normalized_quote and normalized_quote not in normalized_jd:
            warnings.append(
                f"FLAG QUOTE NOT FOUND VERBATIM: '{quote}' "
                f"(flag: '{flag.get('description')}')"
            )

    return warnings


def extract_from_jd_text(jd_text: str) -> dict:
    """Extract requirements from raw JD text (used by web interface).
    Same logic as extract_from_jd but accepts text directly instead of a file path."""
    schema = load_schema()
    prompt = build_prompt(jd_text, schema)
    raw_response = call_llm(prompt)
    cleaned = strip_markdown_fences(raw_response)

    try:
        extraction = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON: {e}")

    try:
        validate(instance=extraction, schema=schema)
    except ValidationError as e:
        raise ValueError(f"LLM output failed schema validation: {e}")

    quote_warnings = check_quotes_verbatim(extraction, jd_text)
    extraction["_quote_check_warnings"] = quote_warnings

    return extraction


def extract_from_jd(jd_path: Path) -> dict:
    jd_text = jd_path.read_text()
    schema = load_schema()
    prompt = build_prompt(jd_text, schema)

    raw_response = call_llm(prompt)
    cleaned = strip_markdown_fences(raw_response)

    try:
        extraction = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"ERROR: LLM did not return valid JSON.\n{e}\n\nRaw response:\n{raw_response}")
        sys.exit(1)

    try:
        validate(instance=extraction, schema=schema)
    except ValidationError as e:
        print(f"ERROR: LLM output failed schema validation.\n{e}")
        sys.exit(1)

    quote_warnings = check_quotes_verbatim(extraction, jd_text)
    extraction["_quote_check_warnings"] = quote_warnings

    return extraction


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 extract.py <path_to_jd.txt>")
        sys.exit(1)

    jd_path = Path(sys.argv[1])
    if not jd_path.exists():
        print(f"ERROR: File not found: {jd_path}")
        sys.exit(1)

    print(f"Extracting requirements from: {jd_path.name}")
    extraction = extract_from_jd(jd_path)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{jd_path.stem}_extracted.json"
    with open(output_path, "w") as f:
        json.dump(extraction, f, indent=2)

    print(f"\nExtracted {len(extraction['requirements'])} requirements.")
    print(f"Seniority signal: {extraction['seniority_signal']['level']} "
          f"(confidence: {extraction['seniority_signal']['confidence']})")
    print(f"Flags raised: {len(extraction['flags'])}")

    warnings = extraction.get("_quote_check_warnings", [])
    if warnings:
        print(f"\n⚠ {len(warnings)} quote check warning(s):")
        for w in warnings:
            print(f"  - {w}")
    else:
        print("\n✓ All source quotes verified verbatim against JD text.")

    print(f"\nSaved to: {output_path}")


if __name__ == "__main__":
    main()
