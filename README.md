# JD Fit Decoder

A tool that parses job descriptions and scores qualification match against a
structured personal profile  built as a portfolio project demonstrating
product thinking for PM/BA/AI-adjacent roles.

**Live demo:** paste your CV and any PM/BA job description → get a structured
qualification-match score with per-requirement breakdown.

---

## What this does

1. **Extract** — an LLM reads the job description and outputs structured
   requirements (must-have vs nice-to-have, with mandatory verbatim source
   quotes as a hallucination check)
2. **Score** — a deterministic, non-LLM scoring engine computes a
   qualification-match score against your profile using a documented,
   weighted rubric

**Core design principle:** the LLM only ever parses text into structure. It
never computes the score. That's plain, auditable Python — see
`eval/scoring_rubric.md` for the full rubric spec.

---

## Running it (web interface)

```bash
git clone https://github.com/Kajolnagargoje/jd-fit-decoder.git
cd jd-fit-decoder
pip install anthropic flask jsonschema
export ANTHROPIC_API_KEY="your-key-here"
python3 app.py
```

Open **http://127.0.0.1:5000** in your browser. Paste your CV and any job
description, click Score.

---

## Running it (command line)

```bash
cd src
python3 extract.py ../data/sample_jds/jd_01_growth_pm.txt
python3 score.py ../data/extracted/jd_01_growth_pm_extracted.json
```

---

## Project structure

```
app.py                          - Flask web interface (paste CV + JD → score)
profile/my_profile.json         -your editable qualification profile
schemas/profile_schema.json     - schema for the profile file
schemas/extraction_schema.json  - schema for LLM extraction output
src/extraction_prompt.txt       -the prompt sent to the LLM (versioned separately)
src/extract.py                  - LLM extraction + schema validation + quote check
src/score.py                    - deterministic scoring engine (no LLM)
src/test_extract_offline.py     - extraction pipeline tests (no API calls needed)
src/test_score_offline.py       - scoring logic tests (no API calls needed)
data/sample_jds/                - sample job descriptions
eval/scoring_rubric.md          - human-readable rubric spec (source of truth)
eval/decisions_log.md           - every significant product/technical decision + reasoning
eval/interview_narrative.md     - structured story for talking about this project
```

---

## Scoring rubric (summary)

| Category       | Weight | Notes |
|----------------|--------|-------|
| Must-haves     | 50%    | With aggregation penalty if multiple gaps exist |
| Seniority      | 20%    | Ordinal distance between your level and JD signal |
| Nice-to-haves  | 15%    | Same per-item logic as must-haves, no penalty |
| Domain fit     | 15%    | Only scores required domains, not contextual ones |

Full rubric with all edge cases: `eval/scoring_rubric.md`

---

## Key design decisions

- **Mandatory source quotes** on every extraction - mechanical hallucination check
- **`canonical_skill` field** separates human-readable labels from machine-matchable names
- **Cross-section skill/tool matching** - prevents skill_type misclassification from zeroing real matches
- **Punishing aggregation** - a pattern of must-have gaps compounds, not just averages
- **Work eligibility as a separate heuristic** - not treated as a generic skill match

Full decision log with reasoning: `eval/decisions_log.md`

---

## Known v1 limitations

- Abstract competency language ("executive presence", "systems thinking") scores
  lower than concrete skill names  the scoring layer uses exact matching, not
  semantic similarity. This is documented rather than over-engineered in v1.
- Run-to-run extraction variance  the same JD can produce 22-24 requirements
  across runs due to LLM non-determinism. The score is not perfectly reproducible.
- Work eligibility matching is a coarse keyword heuristic, not real visa-rule parsing.
- No empirical validation against actual hiring outcomes (no labeled dataset exists).

---

## Portfolio context

Built during an active PM/BA job search in Dublin, Ireland (2026). The project
solves a real problem I had: inconsistent JD triage across a high-volume
application process. The interesting part isn't the code, it's the product
decisions: what to build, what to cut, where to use AI, and where not to.

Key artifact for interviews: `eval/decisions_log.md`

---

## How this was built

This project was built with Claude (Anthropic) as a coding partner. Here is what that means precisely:

**What I did:**
- Defined the problem and decided this was worth building
- Wrote the one-page spec before any code was written
- Designed the scoring rubric, the weights, the penalty logic, the partial credit rules
- Made every scoping decision: what's in v1, what's cut, what's a known limitation
- Chose where to use AI (extraction) and where not to (scoring)
- Tested the tool on real job descriptions and diagnosed every bug
- Decided how to fix each bug when options were presented
- Wrote the decisions log and interview narrative

**What Claude did:**
- Wrote the Python code based on my spec and decisions
- Suggested options when I hit a decision point I chose between them
- Packaged and structured files

**Why I'm being transparent about this:**

Using AI as a coding partner is a real skill  knowing what to build, how to scope it, where AI judgment is reliable and where it isn't, and how to validate output are exactly the competencies this project is trying to demonstrate. Hiding the AI involvement would undermine the honest framing the tool itself is built around.

The product decisions, the rubric design, the scoping tradeoffs, and the "why this, why now" story are mine. The Python is Claude's. That is an accurate description of how this was built.
