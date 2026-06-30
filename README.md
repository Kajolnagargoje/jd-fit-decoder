# JD Fit Decoder

A tool that parses job descriptions and scores qualification match against a
structured personal profile — built as a portfolio project demonstrating
product thinking (not just code) for PM/BA/AI-adjacent job applications.

## What this does

1. **Extraction** (`src/extract.py`): calls Claude to parse a job description
   into structured requirements (must-have vs nice-to-have, with mandatory
   verbatim source quotes as a hallucination check).
2. **Scoring** (`src/score.py`): a deterministic, non-LLM scoring engine that
   computes a qualification-match score against your profile, using a
   documented, weighted rubric.

The key design principle: the LLM only ever parses messy text into structure.
It never computes the final score. That's plain, auditable code — see
`eval/scoring_rubric.md` for the full rubric spec.

## Project structure

```
profile/my_profile.json       — your editable profile (skills, years, domains)
schemas/profile_schema.json   — the shape of the profile file
schemas/extraction_schema.json — the shape of LLM extraction output
src/extraction_prompt.txt     — the prompt sent to the LLM (kept separate from code)
src/extract.py                — calls the LLM, validates output, checks quotes
src/score.py                  — deterministic scoring engine
src/test_extract_offline.py   — tests extraction validation logic (no API calls)
src/test_score_offline.py     — tests scoring logic against mock data (no API calls)
data/sample_jds/              — sample job descriptions to test against
eval/scoring_rubric.md         — human-readable spec for the scoring rubric
```

## Setup (one-time)

1. Install dependencies:
   ```bash
   pip install anthropic jsonschema
   ```

2. Set your Anthropic API key as an environment variable:
   ```bash
   export ANTHROPIC_API_KEY="your-key-here"
   ```
   (On Windows PowerShell: `$env:ANTHROPIC_API_KEY="your-key-here"`)

## Running it

**Step 1 — Extract requirements from a JD:**
```bash
cd src
python3 extract.py ../data/sample_jds/jd_01_growth_pm.txt
```
This saves a structured extraction to `data/extracted/jd_01_growth_pm_extracted.json`.

**Step 2 — Score the extraction against your profile:**
```bash
python3 score.py ../data/extracted/jd_01_growth_pm_extracted.json
```
This prints a score breakdown and saves the full detail to a `_score.json` file
next to the extraction.

## Running the offline tests (no API key needed)

These confirm the validation and scoring logic work correctly using mock data:
```bash
cd src
python3 test_extract_offline.py
python3 test_score_offline.py
```

## Before using your real data

- Edit `profile/my_profile.json` with your actual skills, years of experience,
  and tools — the placeholder values need correcting (several are set to `0`
  years intentionally, as placeholders, not real assessments).
- Add real job descriptions as `.txt` files in `data/sample_jds/` (or anywhere
  — you just pass the file path to `extract.py`).
