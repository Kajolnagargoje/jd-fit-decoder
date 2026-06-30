# JD Fit Decoder — Interview Narrative

This document is not a technical spec. It's a structured story you can tell
verbally in a PM/BA interview when asked about this project. Read it, make it
your own, and don't recite it — use it as a memory scaffold.

---

## The 60-second version (for "tell me about a side project")

"I built a tool called JD Fit Decoder during my job search. The problem it
solves is real and immediate: when you're evaluating 10-15 job descriptions
a week, you make inconsistent triage decisions — spending time on applications
you're not actually qualified for, or skipping roles where you meet the bar
but missed it on a skim.

The tool takes a job description, extracts the requirements using an LLM,
and scores your qualification match using a deterministic scoring engine I
designed — not more AI. The interesting product decision was keeping those
two things separate: the LLM handles the messy text parsing because it's good
at that, but it never touches the actual score, because I wanted the score to
be explainable and auditable. Anyone can look at the rubric and understand
exactly why a score is what it is.

The project is live, it's on GitHub, and I've been using it on real job
descriptions during my own search."

---

## The deeper version (for "walk me through a key decision you made")

Use this when an interviewer asks you to go deeper on the product thinking.

### Setup
"The most interesting decision in this project was about where to use AI and
where not to. The obvious thing to do would be to ask the LLM to evaluate the
job description and tell you how well you fit. That's a one-API-call solution.
But it has a serious problem: you can't audit it. You don't know what the LLM
weighted, why it gave you a 72% instead of a 68%, or whether it was picking
up on something real or hallucinating a skill requirement that wasn't in the
JD.

### The decision
So I separated the system into two components. The LLM does one thing:
read messy free text and output structured data — a JSON object with every
requirement, classified as must-have or nice-to-have, with the exact source
quote from the JD it came from. That last part — mandatory verbatim quotes —
is the hallucination check. If the quote doesn't appear in the JD, the system
flags it.

Then a completely separate, plain Python scoring function computes the actual
match score using a weighted rubric I documented before writing a line of code:
must-haves are 50% of the score, seniority alignment 20%, nice-to-haves 15%,
domain fit 15%. That rubric is a file in the repo. It's not the AI's opinion —
it's mine."

### The tradeoff
"The tradeoff I made was precision vs coverage. Exact-string matching is
completely auditable but it misses things — if the JD says 'executive
presence' and your profile says 'stakeholder management,' those don't match,
even though they're related. I documented that as a v1 limitation rather than
trying to fix it with fuzzy matching, because the fix would reintroduce AI
judgment into the scoring step, and I'd lose the auditability I was trying
to preserve. A v2 could use embedding similarity with a documented confidence
threshold — that's in the decisions log."

---

## When they ask "what would you do differently?"

"Two things. First, I'd add semantic/embedding-based matching in the scoring
layer — the current exact-string matching fails on abstract competency language
like 'systems thinking' or 'executive presence,' which are common in senior
PM JDs. I documented this as a known limitation rather than over-engineering a
fix in v1, but it's the most significant functional gap.

Second, I'd add run-to-run variance measurement. The same JD can extract
slightly differently across runs — I saw 22 vs 23 vs 24 requirements on the
same input across three runs. That's LLM non-determinism, not a bug, but a
production-quality tool should surface the variance range alongside the score
rather than presenting a single number as if it's stable."

---

## When they ask "how do you know the score is right?"

"Honestly, I don't — not in a statistically validated sense. There's no ground
truth dataset of 'applied to this job, got/didn't get an interview.' What I
can say is: the score is explainable. I can point to every item that
contributed to it and why. I can show you the rubric that drove the weights.
I deliberately avoided framing the score as predictive of hiring outcomes —
it's a qualification match score against a documented rubric, nothing more.

The validation I did was qualitative: I ran the tool on a JD I knew was a
stretch role for me (Optum Sr PM — healthcare domain, senior level), and it
scored 21% with a seniority gap and visa flag correctly identified. I ran it on
a mid-level growth PM role closer to my background, and it scored 52%. Both
felt right relative to my own assessment. That's not statistical validation,
and I didn't pretend it was."

---

## When they ask "why not just use ChatGPT for this?"

"You could ask ChatGPT 'how well do I fit this job description?' and get an
answer. But you'd have no idea how it weighted the requirements, whether it
was consistent across different JDs, or whether it was telling you what you
wanted to hear. It would also change its answer if you rephrased the question.

What I built does something different: it produces a score that's consistent,
documented, and arguable. If you disagree with the score, you can point to
the rubric and say 'I think must-haves should be weighted 60%, not 50%' and
we can have that conversation. You can't have that conversation with a
ChatGPT answer."

---

## Numbers to remember

- **4 real bugs found and fixed through live testing** (canonical_skill field,
  skill/tool cross-section matching, education degree-level comparison,
  work-eligibility heuristic)
- **2 prompt iterations** driven by real extraction failures
- **3 real JDs tested** (1 placeholder growth PM, 1 placeholder senior BA
  with deliberate contradiction, 1 real Optum Sr PM posting)
- **Score range observed:** 21% (stretch/senior role, wrong domain) to 52%
  (closer match, same domain, appropriate seniority)
- **Rubric weights:** must-haves 50%, seniority 20%, nice-to-haves 15%,
  domain 15%
