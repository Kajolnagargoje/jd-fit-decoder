"""
app.py — JD Fit Decoder web interface.

A simple local web app that accepts a CV and job description as text input,
runs extraction + scoring, and returns a clean breakdown.

Usage:
    cd ~/Downloads/jd-fit-decoder
    pip install flask
    python3 app.py

Then open http://localhost:5000 in your browser.
"""

import json
import os
import sys
from pathlib import Path

from flask import Flask, render_template_string, request, jsonify

# Add src/ to path so we can import extract and score modules
sys.path.insert(0, str(Path(__file__).parent / "src"))

from extract import extract_from_jd_text
from score import compute_overall_score, load_profile

app = Flask(__name__)
PROJECT_ROOT = Path(__file__).parent
PROFILE_PATH = PROJECT_ROOT / "profile" / "my_profile.json"

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>JD Fit Decoder</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg: #0f1117;
    --surface: #1a1d27;
    --surface2: #22263a;
    --border: #2e3347;
    --accent: #6c8fff;
    --accent-dim: #3d52a8;
    --green: #4ade80;
    --yellow: #fbbf24;
    --red: #f87171;
    --text: #e2e8f0;
    --text-muted: #64748b;
    --text-dim: #94a3b8;
    --mono: 'DM Mono', monospace;
    --sans: 'Inter', sans-serif;
  }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    font-size: 14px;
    line-height: 1.6;
    min-height: 100vh;
  }

  header {
    border-bottom: 1px solid var(--border);
    padding: 20px 40px;
    display: flex;
    align-items: baseline;
    gap: 12px;
  }

  header h1 {
    font-size: 16px;
    font-weight: 600;
    letter-spacing: -0.01em;
  }

  header span {
    font-size: 12px;
    color: var(--text-muted);
    font-family: var(--mono);
  }

  .tag {
    font-size: 10px;
    font-family: var(--mono);
    background: var(--accent-dim);
    color: var(--accent);
    padding: 2px 8px;
    border-radius: 3px;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  main {
    max-width: 1100px;
    margin: 0 auto;
    padding: 32px 40px;
  }

  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-bottom: 20px;
  }

  .input-block label {
    display: block;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 8px;
  }

  textarea {
    width: 100%;
    height: 280px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text);
    font-family: var(--mono);
    font-size: 12px;
    line-height: 1.6;
    padding: 14px;
    resize: vertical;
    outline: none;
    transition: border-color 0.15s;
  }

  textarea:focus { border-color: var(--accent); }
  textarea::placeholder { color: var(--text-muted); }

  .hint {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 6px;
  }

  .actions {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 32px;
  }

  button {
    background: var(--accent);
    color: #fff;
    border: none;
    border-radius: 6px;
    font-family: var(--sans);
    font-size: 13px;
    font-weight: 500;
    padding: 10px 24px;
    cursor: pointer;
    transition: opacity 0.15s;
  }

  button:hover { opacity: 0.85; }
  button:disabled { opacity: 0.4; cursor: not-allowed; }

  .status {
    font-size: 12px;
    font-family: var(--mono);
    color: var(--text-muted);
  }

  /* Results */
  #results { display: none; }

  .score-hero {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 28px 32px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 32px;
  }

  .score-number {
    font-size: 56px;
    font-weight: 300;
    font-family: var(--mono);
    letter-spacing: -0.03em;
    line-height: 1;
    min-width: 120px;
  }

  .score-number.high { color: var(--green); }
  .score-number.mid { color: var(--yellow); }
  .score-number.low { color: var(--red); }

  .score-meta { flex: 1; }
  .score-meta h2 { font-size: 15px; font-weight: 500; margin-bottom: 4px; }
  .score-meta p { font-size: 12px; color: var(--text-dim); }

  .categories {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 20px;
  }

  .category-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 16px;
  }

  .category-card .cat-label {
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 8px;
  }

  .category-card .cat-score {
    font-size: 28px;
    font-weight: 300;
    font-family: var(--mono);
    line-height: 1;
    margin-bottom: 6px;
  }

  .category-card .cat-weight {
    font-size: 11px;
    color: var(--text-muted);
    font-family: var(--mono);
  }

  .bar-track {
    height: 3px;
    background: var(--border);
    border-radius: 2px;
    margin-top: 10px;
  }

  .bar-fill {
    height: 100%;
    border-radius: 2px;
    background: var(--accent);
    transition: width 0.6s ease;
  }

  .bar-fill.high { background: var(--green); }
  .bar-fill.mid { background: var(--yellow); }
  .bar-fill.low { background: var(--red); }

  .section {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    margin-bottom: 16px;
    overflow: hidden;
  }

  .section-header {
    padding: 14px 20px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .section-header h3 {
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-dim);
  }

  .section-header .count {
    font-size: 11px;
    font-family: var(--mono);
    color: var(--text-muted);
  }

  .req-list { padding: 8px 0; }

  .req-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 20px;
    border-bottom: 1px solid var(--border);
    transition: background 0.1s;
  }

  .req-item:last-child { border-bottom: none; }
  .req-item:hover { background: var(--surface2); }

  .req-score {
    font-family: var(--mono);
    font-size: 12px;
    font-weight: 500;
    min-width: 38px;
    text-align: right;
  }

  .req-score.full { color: var(--green); }
  .req-score.partial { color: var(--yellow); }
  .req-score.zero { color: var(--red); }

  .req-text {
    flex: 1;
    font-size: 13px;
    color: var(--text);
  }

  .req-conf {
    font-family: var(--mono);
    font-size: 11px;
    color: var(--text-muted);
  }

  .flags-list { padding: 8px 0; }

  .flag-item {
    padding: 10px 20px;
    border-bottom: 1px solid var(--border);
    display: flex;
    gap: 12px;
    align-items: flex-start;
  }

  .flag-item:last-child { border-bottom: none; }

  .flag-type {
    font-size: 10px;
    font-family: var(--mono);
    padding: 2px 8px;
    border-radius: 3px;
    white-space: nowrap;
    margin-top: 2px;
  }

  .flag-type.location_or_visa { background: #1e293b; color: #60a5fa; }
  .flag-type.vague_scope { background: #1c1917; color: #a8a29e; }
  .flag-type.contradictory_signals { background: #2d1b1b; color: #f87171; }
  .flag-type.unrealistic_combination { background: #2d1b1b; color: #f87171; }
  .flag-type.other { background: #1e293b; color: #94a3b8; }

  .flag-desc { font-size: 13px; color: var(--text-dim); line-height: 1.5; }

  .seniority-row {
    padding: 14px 20px;
    display: flex;
    gap: 24px;
    font-size: 13px;
  }

  .seniority-row span { color: var(--text-muted); }
  .seniority-row strong { color: var(--text); }

  .quote-check {
    padding: 12px 20px;
    font-size: 12px;
    font-family: var(--mono);
  }

  .quote-check.pass { color: var(--green); }
  .quote-check.warn { color: var(--yellow); }

  .error-box {
    background: #2d1b1b;
    border: 1px solid #7f1d1d;
    border-radius: 6px;
    padding: 16px 20px;
    font-family: var(--mono);
    font-size: 12px;
    color: var(--red);
    margin-bottom: 16px;
    display: none;
  }
</style>
</head>
<body>

<header>
  <h1>JD Fit Decoder</h1>
  <span>qualification match scorer</span>
  <div class="tag">v1</div>
</header>

<main>
  <div class="grid">
    <div class="input-block">
      <label>Your CV</label>
      <textarea id="cv-input" placeholder="Paste your full CV text here..."></textarea>
      <p class="hint">Paste plain text from your CV. Used to build your qualification profile.</p>
    </div>
    <div class="input-block">
      <label>Job Description</label>
      <textarea id="jd-input" placeholder="Paste the full job description here..."></textarea>
      <p class="hint">Paste the full JD. Requirements will be extracted and scored against your profile.</p>
    </div>
  </div>

  <div class="actions">
    <button id="score-btn" onclick="runScoring()">Score this JD</button>
    <span class="status" id="status-text"></span>
  </div>

  <div class="error-box" id="error-box"></div>

  <div id="results">

    <div class="score-hero">
      <div class="score-number" id="hero-score">—</div>
      <div class="score-meta">
        <h2 id="hero-label">Overall qualification match</h2>
        <p id="hero-sub"></p>
      </div>
    </div>

    <div class="categories" id="cat-grid"></div>

    <div class="section" id="seniority-section">
      <div class="section-header"><h3>Seniority Signal</h3></div>
      <div class="seniority-row" id="seniority-row"></div>
    </div>

    <div class="section" id="flags-section">
      <div class="section-header">
        <h3>Flags</h3>
        <span class="count" id="flags-count"></span>
      </div>
      <div class="flags-list" id="flags-list"></div>
    </div>

    <div class="section">
      <div class="section-header">
        <h3>Must-Have Requirements</h3>
        <span class="count" id="mh-count"></span>
      </div>
      <div class="req-list" id="mh-list"></div>
    </div>

    <div class="section">
      <div class="section-header">
        <h3>Nice-to-Have Requirements</h3>
        <span class="count" id="nth-count"></span>
      </div>
      <div class="req-list" id="nth-list"></div>
    </div>

    <div class="section">
      <div class="section-header"><h3>Extraction Quality</h3></div>
      <div class="quote-check" id="quote-check"></div>
    </div>

  </div>
</main>

<script>
async function runScoring() {
  const cv = document.getElementById('cv-input').value.trim();
  const jd = document.getElementById('jd-input').value.trim();
  const btn = document.getElementById('score-btn');
  const status = document.getElementById('status-text');
  const errorBox = document.getElementById('error-box');

  if (!jd) { alert('Please paste a job description.'); return; }

  btn.disabled = true;
  errorBox.style.display = 'none';
  document.getElementById('results').style.display = 'none';

  const steps = [
    'Extracting requirements from JD...',
    'Validating extraction schema...',
    'Checking source quotes verbatim...',
    'Computing qualification match score...',
  ];
  let i = 0;
  status.textContent = steps[0];
  const interval = setInterval(() => {
    i = Math.min(i + 1, steps.length - 1);
    status.textContent = steps[i];
  }, 2500);

  try {
    const res = await fetch('/score', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cv, jd })
    });
    const data = await res.json();
    clearInterval(interval);

    if (data.error) {
      errorBox.textContent = 'Error: ' + data.error;
      errorBox.style.display = 'block';
      status.textContent = 'Something went wrong.';
    } else {
      renderResults(data);
      status.textContent = '';
    }
  } catch (e) {
    clearInterval(interval);
    errorBox.textContent = 'Network error: ' + e.message;
    errorBox.style.display = 'block';
    status.textContent = '';
  }

  btn.disabled = false;
}

function scoreClass(s) {
  if (s === null) return '';
  if (s >= 0.7) return 'high';
  if (s >= 0.4) return 'mid';
  return 'low';
}

function reqScoreClass(s) {
  if (s >= 0.9) return 'full';
  if (s > 0) return 'partial';
  return 'zero';
}

function pct(v) {
  if (v === null || v === undefined) return '—';
  return Math.round(v * 100) + '%';
}

function renderResults(data) {
  const overall = data.overall_score;
  const pctVal = Math.round(overall * 100);

  const hero = document.getElementById('hero-score');
  hero.textContent = pctVal + '%';
  hero.className = 'score-number ' + scoreClass(overall);

  document.getElementById('hero-label').textContent = 'Overall qualification match';
  document.getElementById('hero-sub').textContent =
    pctVal >= 70 ? 'Strong fit — worth applying.' :
    pctVal >= 45 ? 'Moderate fit — gaps exist but role is reachable.' :
    'Stretch role — significant gaps or eligibility blockers present.';

  // Categories
  const cats = [
    { key: 'must_have', label: 'Must-Haves', defaultWeight: 0.50 },
    { key: 'nice_to_have', label: 'Nice-to-Haves', defaultWeight: 0.15 },
    { key: 'seniority', label: 'Seniority', defaultWeight: 0.20 },
    { key: 'domain', label: 'Domain', defaultWeight: 0.15 },
  ];
  const grid = document.getElementById('cat-grid');
  grid.innerHTML = '';
  const weights = data.adjusted_weights_used || {};
  cats.forEach(c => {
    const detail = data.category_breakdown[c.key];
    const score = detail ? detail.score : null;
    const weight = weights[c.key] || c.defaultWeight;
    const cls = scoreClass(score);
    const fillPct = score !== null ? Math.round(score * 100) : 0;
    grid.innerHTML += `
      <div class="category-card">
        <div class="cat-label">${c.label}</div>
        <div class="cat-score ${cls}">${pct(score)}</div>
        <div class="cat-weight">weight: ${Math.round(weight * 100)}%</div>
        <div class="bar-track"><div class="bar-fill ${cls}" style="width:${fillPct}%"></div></div>
      </div>`;
  });

  // Seniority
  const sen = data.category_breakdown.seniority;
  document.getElementById('seniority-row').innerHTML = sen.score !== null
    ? `<span>JD targets:</span> <strong>${sen.jd_level}</strong>
       <span>Your level:</span> <strong>${sen.profile_level}</strong>
       <span>Distance:</span> <strong>${sen.distance} level${sen.distance !== 1 ? 's' : ''}</strong>`
    : `<span>${sen.detail || 'Seniority signal unclear in JD'}</span>`;

  // Flags
  const flags = data.flags || [];
  document.getElementById('flags-count').textContent = flags.length + ' found';
  const flagsList = document.getElementById('flags-list');
  if (flags.length === 0) {
    flagsList.innerHTML = '<div class="flag-item"><div class="flag-desc" style="color:var(--text-muted)">No flags raised.</div></div>';
  } else {
    flagsList.innerHTML = flags.map(f => `
      <div class="flag-item">
        <div class="flag-type ${f.type}">${f.type.replace(/_/g,' ')}</div>
        <div class="flag-desc">${f.description}</div>
      </div>`).join('');
  }

  // Must-haves
  const mh = data.category_breakdown.must_have;
  const mhItems = mh ? mh.items || [] : [];
  document.getElementById('mh-count').textContent = mhItems.length + ' requirements';
  document.getElementById('mh-list').innerHTML = mhItems.map(r => `
    <div class="req-item">
      <div class="req-score ${reqScoreClass(r.score)}">${pct(r.score)}</div>
      <div class="req-text">${r.text}</div>
      <div class="req-conf">conf ${Math.round(r.confidence * 100)}%</div>
    </div>`).join('');

  // Nice-to-haves
  const nth = data.category_breakdown.nice_to_have;
  const nthItems = nth ? nth.items || [] : [];
  document.getElementById('nth-count').textContent = nthItems.length + ' requirements';
  document.getElementById('nth-list').innerHTML = nthItems.map(r => `
    <div class="req-item">
      <div class="req-score ${reqScoreClass(r.score)}">${pct(r.score)}</div>
      <div class="req-text">${r.text}</div>
      <div class="req-conf">conf ${Math.round(r.confidence * 100)}%</div>
    </div>`).join('');

  // Quote check
  const warnings = data.quote_check_warnings || [];
  const qc = document.getElementById('quote-check');
  if (warnings.length === 0) {
    qc.textContent = '✓ All source quotes verified verbatim against JD text.';
    qc.className = 'quote-check pass';
  } else {
    qc.textContent = `⚠ ${warnings.length} quote check warning(s) — some extractions may be imprecise.`;
    qc.className = 'quote-check warn';
  }

  document.getElementById('results').style.display = 'block';
  document.getElementById('results').scrollIntoView({ behavior: 'smooth' });
}
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/score", methods=["POST"])
def score():
    try:
        body = request.get_json()
        jd_text = body.get("jd", "").strip()
        cv_text = body.get("cv", "").strip()

        if not jd_text:
            return jsonify({"error": "No job description provided."}), 400

        # Import here to avoid circular issues
        import anthropic
        from extract import extract_from_jd_text as extract_fn
        from score import compute_overall_score

        # If CV provided, generate profile from it; otherwise use saved profile
        if cv_text:
            profile = generate_profile_from_cv(cv_text)
        else:
            profile = load_profile()

        extraction = extract_fn(jd_text)
        result = compute_overall_score(extraction, profile)
        result["quote_check_warnings"] = extraction.get("_quote_check_warnings", [])

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def generate_profile_from_cv(cv_text: str) -> dict:
    """Use the LLM to extract a structured profile from CV text.
    Falls back to the saved profile if extraction fails."""
    import anthropic

    client = anthropic.Anthropic()

    prompt = f"""Extract a structured qualification profile from this CV text and return ONLY valid JSON.
No preamble, no markdown fences, just the JSON object.

Return this exact structure:
{{
  "seniority_level": "entry|associate|mid|senior|lead|principal",
  "total_years_experience": <number>,
  "skills": [
    {{"name": "<canonical skill name>", "years": <number>, "proficiency": "familiar|working|strong|expert", "evidence": "<one-line proof point>"}}
  ],
  "domains": [
    {{"name": "<domain>", "years": <number>}}
  ],
  "tools": [
    {{"name": "<tool name>", "proficiency": "familiar|working|strong|expert"}}
  ],
  "certifications": [
    {{"name": "<cert name>", "year_obtained": <year or null>}}
  ],
  "education": [
    {{"degree": "<degree level>", "field": "<field of study>"}}
  ],
  "location": {{
    "city": "<city>",
    "country": "<country>",
    "work_authorization": "<visa/authorization status if mentioned>",
    "open_to_relocation": false,
    "open_to_remote": true
  }}
}}

Use short, canonical skill names (e.g. "SQL" not "SQL proficiency", "A/B testing" not "A/B experimentation").
Infer years from work history dates where possible.

CV TEXT:
---
{cv_text}
---

Return ONLY the JSON object."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        lines = text.split("\n")[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    return json.loads(text)


if __name__ == "__main__":
    print("\nJD Fit Decoder")
    print("──────────────")
    print("Open http://localhost:5000 in your browser\n")
    app.run(debug=False, port=5000)
