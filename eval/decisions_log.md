# JD Fit Decoder — Decisions Log

This document records every significant product and technical decision made
during the build, with the reasoning behind each one. It exists because the
interesting part of this project isn't the code — it's the judgment calls.

---

## Product Decisions

### 1. Why build this at all?
**Decision:** Build a JD qualification scorer as a portfolio project.
**Reasoning:** I was evaluating 10-15 job descriptions a week during an active
job search and making inconsistent triage decisions — spending time on
applications I wasn't qualified for and skipping some I was. The project solved
a real, immediate problem (my own job hunt) while demonstrating product and BA
skills: requirements elicitation, structured rubric design, AI-tool judgment,
and scoping discipline. The "why this, why now" story is genuine, not
manufactured.

### 2. Score = explainable rubric, not AI prediction
**Decision:** The final qualification score is computed by a deterministic,
code-based scoring function — not by asking the LLM "how well does this
candidate fit?"
**Reasoning:** LLM-generated scores are a black box. They can't be audited,
debugged, or defended. A documented, weighted rubric (must-haves 50%, seniority
20%, nice-to-haves 15%, domain 15%) means I can explain exactly why a score
is what it is — which item dragged it down, which weight drove it up. This
is the more credible design for a "qualification tool," where the score's
defensibility matters more than its apparent sophistication.

### 3. LLM for extraction only — not scoring
**Decision:** The LLM is only ever used for one thing: parsing unstructured JD
text into structured JSON. Everything downstream (matching, scoring,
aggregation) is plain Python code.
**Reasoning:** This is the core architectural principle of the project. LLMs
are good at turning messy free text into structure. They are unreliable at
making consistent, auditable decisions. Keeping these two responsibilities
separate means: (a) bugs in scoring are findable and fixable, (b) the score
doesn't change every time the LLM has a slightly different "mood," (c) I can
explain every number without needing to explain what the LLM was thinking.

### 4. What the score actually measures (and what it doesn't claim to)
**Decision:** The score measures qualification match against a documented
rubric — not predicted interview likelihood or hiring probability.
**Reasoning:** There is no labeled outcome data ("applied to this role,
got/didn't get an interview"). Claiming predictive accuracy would be
dishonest. Instead, the score is framed as "here is how your documented
qualifications map to this JD's stated requirements, according to a rubric
I designed and can defend." That's a more honest and actually more useful
framing — the score tells you where the gaps are, not whether you'll get
the job.

### 5. Single editable JSON profile — not selectable personas
**Decision:** Your background is represented as a single structured JSON file
you can edit directly. Not multiple "PM persona" vs "BA persona" variants.
**Reasoning:** Multiple personas would require deciding in advance how to
frame yourself in each one — that's a content decision, not a product feature.
A single editable profile is simpler to maintain and makes the system's
behavior fully predictable: you know exactly what's being scored against,
because you wrote it. If you want to test a different framing, you edit the
file — that flexibility is already there without building a persona-picker UI.

### 6. What was explicitly cut from v1
The following were considered and deliberately excluded:
- **LinkedIn/job board scraping** — would have doubled build time for a feature
  that isn't the differentiator. The interesting part is the scoring logic,
  not automation.
- **Cover letter generation** — a different product with a different problem.
  Scope creep disguised as a feature.
- **Multi-user accounts / auth** — not needed for a portfolio tool. Added
  complexity with no value at this stage.
- **Predictive scoring / ML model** — no labeled outcome data to train or
  validate against. Would have been false precision.
- **Fine-tuning or RAG** — overkill for single-document analysis. The LLM
  already handles JD text well without retrieval augmentation.

---

## Technical Decisions

### 7. Mandatory verbatim source quotes on every extraction
**Decision:** Every extracted requirement and flag must carry the exact,
verbatim sentence from the JD it came from — stored as `source_quote`.
**Reasoning:** This is a cheap, mechanical hallucination check. If a
`source_quote` doesn't appear verbatim in the original JD text, the extraction
invented it. We run this check on every extraction and surface warnings for
any mismatches. It doesn't catch every LLM failure, but it catches the most
common one: invented requirements that sound plausible.

### 8. `canonical_skill` field — the biggest schema decision
**Decision:** Added a `canonical_skill` field to the extraction schema,
separate from the human-readable `text` field.
**Context:** The first real extraction run produced 0% on must-haves and
nice-to-haves. Investigation showed the LLM was extracting requirements as
full descriptive phrases ("SQL proficiency", "Running experiments and A/B
testing") while the profile stored bare skill names ("SQL", "A/B testing").
Exact-match scoring failed on every single requirement.
**Reasoning:** The LLM needs two outputs per requirement, serving two different
audiences: a readable label for humans ("SQL proficiency"), and a canonical
short name for matching against the profile ("SQL"). These have different
constraints — readable labels benefit from context, canonical names need to
be stable and brief. Conflating them into one field was the design mistake;
separating them into `text` and `canonical_skill` was the fix.

### 9. Skill/tool cross-section matching
**Decision:** When matching a requirement to the profile, search across both
the `skills` and `tools` sections regardless of the LLM's `skill_type`
classification.
**Context:** SQL was stored under `skills` in the profile, but the LLM
extracted it with `skill_type: "tool"`. The original matcher only looked in
the section matching the `skill_type`, so SQL always scored 0 despite being
in the profile.
**Reasoning:** The skill vs tool distinction is inherently ambiguous (is SQL a
skill or a tool? both answers are defensible). Making this classification a
hard gate on matching means one word of LLM classification determines whether
a real skill gets credit or not — too much leverage for too uncertain a call.
Cross-section search preserves explainability (we still know what section it
matched in) while removing an arbitrary failure mode.

### 10. Aggregation penalty for must-haves
**Decision:** Must-have scores aren't simply averaged — a penalty multiplier
is applied based on how many requirements score below 0.5.
**Reasoning:** Simple averaging is too forgiving. If you score 1.0 on nine
must-haves but 0.0 on one, a simple average gives 90% — which feels like a
strong match. But a single hard missing requirement (e.g. domain expertise,
a specific certification) can be a real disqualifier. The penalty multiplier
makes a "pattern of gaps" meaningfully worse than a single gap, which better
reflects how real hiring screens work.
**The bands:** ≤20% weak → no penalty; ≤40% → 0.85x; ≤60% → 0.60x; >60% → 0.35x.
These are reasoned defaults, not empirically tuned — documented as a known
v1 simplification.

### 11. Work eligibility — separate heuristic, not skill matching
**Decision:** Work eligibility requirements (visa, right to work) are scored
against `profile.location.work_authorization` — not treated as a generic
skill match.
**Context:** "Eligible to work in Ireland without sponsorship" was initially
scoring 0% for everyone, because no profile has a skill entry called "eligible
to work." This was a structural failure — a real, important signal always
returning a meaningless result.
**Reasoning:** Work eligibility isn't a skill. It's a binary status that
belongs in the location section of a profile, checked with a dedicated
heuristic (does the authorization text contain sponsorship-related keywords?).
The heuristic is deliberately coarse — it doesn't attempt to parse specific
visa categories — and that limitation is documented. The flags system
separately surfaces the raw JD text on this topic so the user can make their
own judgment.

### 12. Education — degree-level comparison, not name matching
**Decision:** Education requirements are scored by comparing degree level
(bachelor's < master's < PhD), not by matching degree names.
**Reasoning:** "Bachelor's degree required" should match whether your profile
says "Bachelor of Technology" or "BA" or "BSc" — the field and naming
convention vary too much for exact matching to work. A degree-level comparison
(if you have a master's and the JD requires a bachelor's, you pass) is both
more useful and more honest than trying to parse and normalize every possible
degree title.

### 13. `max_tokens` tuning
**Decision:** Increased `max_tokens` from 4000 to 8000 after a real extraction
run on a longer JD produced truncated JSON.
**Context:** The Optum Sr PM JD, with 35+ atomized requirements, produced a
response that hit the token limit mid-JSON, causing a parse failure on the
last flag's `source_quote`.
**Reasoning:** Token limits are a real operational parameter, not a set-
and-forget value. JD length varies; longer JDs with more atomized requirements
produce larger responses. 8000 is a safe ceiling for any realistic single JD;
the cost difference is negligible since billing is per token used, not per
token allowed.

### 14. Abstract competency language — documented limitation, not over-engineered fix
**Decision:** JDs written in abstract competency language ("executive presence",
"systems thinking", "operates effectively in ambiguity") score lower than
JDs using concrete skill names — and this is documented as a known v1
limitation rather than patched.
**Context:** The Optum Sr PM JD scored 6% on must-haves despite the candidate
having genuine product management experience. The gap was between abstract
competency labels in the JD and concrete skill names in the profile.
**Reasoning:** Fixing this properly would require semantic/fuzzy matching
(e.g. "executive presence" → near-match to "stakeholder management" +
"verbal communication"). That introduces LLM judgment back into the matching
step, which undermines the auditability of the score. The cleaner v1 decision
was to document the limitation honestly: "this tool performs better on
concrete-skill JDs than abstract-competency JDs." A v2 could explore
embedding-based similarity matching with a documented confidence threshold.

---

## What I'd Do Differently in V2

1. **Semantic matching** for the scoring layer — embedding-based similarity
   rather than exact string match, with a confidence threshold and an
   "approximate match" indicator in the UI.
2. **CV auto-parsing on first load** with a guided "confirm your profile"
   step before any JD is scored — better onboarding than asking users to
   edit JSON.
3. **Run-to-run variance tracking** — the same JD extracted twice can produce
   slightly different requirement lists (23 vs 24 requirements in testing).
   A v2 eval harness should run each JD 3-5 times and surface the variance
   range alongside the score.
4. **Importance weighting within must-haves** — currently "SQL" and
   "PowerPoint" count equally if both are classified as must-haves. A v2
   could let requirements carry an importance signal (extracted from JD
   language intensity) to weight them differently within the category.
