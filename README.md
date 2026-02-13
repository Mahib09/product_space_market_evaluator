# Product Space Market Evaluator

A FastAPI service that evaluates product space market opportunities through a multi-agent system. Given a product space (e.g., "AI sales automation"), it returns a structured JSON report covering incumbents, funded startups, market sizing, and a GO/NO_GO verdict, all grounded in web-sourced evidence.

## Overview

The system orchestrates four specialized agents to produce a comprehensive market evaluation:

- **Agent 1 (Incumbents):** Identifies 5–8 established players, their offerings, target customers, and differentiators.
- **Agent 2 (Startups):** Finds Seed through Series B funded startups with investor details, amounts, and dates, only when supported by evidence.
- **Agent 3 (Market Scan):** Extracts TAM, SAM, and 5-year CAGR from market research sources. Falls back to adjacent markets when direct data is unavailable.
- **Agent 4 (Judgement):** Computes a 1–10 score and GO/NO_GO verdict using a deterministic scoring formula. No API calls pure computation over the outputs of Agents 1–3.

Every extracted field is backed by cited web sources. If evidence doesn't exist, the field is `null` the system does not guess or hallucinate values.

## How to Run

### Prerequisites

- Python 3.11+
- An OpenAI API key with access to `gpt-4.1` (search) and `gpt-5` (extraction)

### Setup

```bash
git clone "https://github.com/Mahib09/product_space_market_evaluator"
cd product_space_market_evaluator

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root:

```
OPENAI_API_KEY=sk-your-key-here
```

Optional overrides:

| Variable                 | Default   | Description                                               |
| ------------------------ | --------- | --------------------------------------------------------- |
| `OPENAI_MODEL_SEARCH`    | `gpt-4.1` | Model used for web search                                 |
| `OPENAI_MODEL_EXTRACT`   | `gpt-5`   | Model used for structured extraction                      |
| `DEBUG_WEB_SEARCH_SHAPE` | `false`   | Log raw web search source object shape (once per process) |

### Run the Server

```bash
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`.

### Example Request

```bash
curl -X POST http://127.0.0.1:8000/evaluate \
  -H "Content-Type: application/json" \
  -d '{"product_space": "AI sales automation"}'
```

## Example Response

```json
{
  "request_id": "a3f1b2c4d5e6",
  "product_space": "AI sales automation",
  "incumbents": {
    "players": [
      {
        "name": "Outreach",
        "offerings": "Sales engagement platform with AI-powered sequences",
        "target_customers": "B2B sales teams, enterprise",
        "differentiators": "ML-driven pipeline management",
        "sources": [{"url": "https://...", "title": "...", "snippet": "..."}]
      }
    ],
    "sources": [...]
  },
  "startups": {
    "companies": [
      {
        "name": "Rox",
        "stage": "Series A",
        "amount_usd": 50000000,
        "date": "2024-11-19",
        "lead_investors": ["Sequoia Capital"],
        "sources": [...]
      }
    ],
    "total_capital_usd": 125000000,
    "startup_count": 4,
    "top_investors": ["Sequoia Capital", "Andreessen Horowitz"],
    "velocity_note": "Moderate",
    "sources": [...]
  },
  "market_scan": {
    "tam_usd": 5400000000,
    "tam_year": 2025,
    "sam_usd": null,
    "sam_year": null,
    "cagr_5y_percent": 14.2,
    "confidence": "medium",
    "notes": "",
    "sources": [...]
  },
  "judgement": {
    "verdict": "GO",
    "score": 6,
    "breakdown": {
      "growth_score": 7,
      "competition_score": 5,
      "white_space": 6
    },
    "summary": "5 incumbents identified. 4 startups ($125M known funding). TAM ~$5.4B. CAGR ~14.2%. Market opportunity supports entry.",
    "confidence": "medium"
  },
  "errors": []
}
```

## Architecture

```
                          POST /evaluate
                               |
                               v
                        +-------------+
                        |   FastAPI    |
                        +------+------+
                               |
                               v
                       +---------------+
                       | Orchestrator  |
                       | run_pipeline  |
                       +---+---+---+---+
                           |   |   |
              asyncio.gather (concurrent)
                           |   |   |
                  +--------+   |   +--------+
                  v            v            v
             +--------+  +--------+  +--------+
             | Agent1 |  | Agent2 |  | Agent3 |
             | Incumb.|  | Start. |  | Market |
             +---+----+  +---+----+  +---+----+
                 |            |            |
                 v            v            v
            web_search   web_search   web_search
            (OpenAI)     (3 queries   (5 queries
                          concurrent)  sequential)
                 |            |            |
                 v            v            v
            clean_sources clean_sources clean_sources
                 |            |            |
                 v            v            v
          extract_structured (OpenAI gpt-5, strict JSON)
                 |            |            |
                 +--------+   |   +--------+
                          v   v   v
                       +---------------+
                       |    Agent4     |
                       |  (sync score) |
                       +-------+-------+
                               |
                               v
                         FinalResult
```

## Scoring Explanation

Agent 4 computes the final verdict using a deterministic formula with no API calls.

### Growth Score (0–10)

Weighted combination of market growth rate and market size:

```
growth = 0.6 * cagr_points + 0.4 * tam_points
```

| CAGR    | Points |     | TAM     | Points |
| ------- | ------ | --- | ------- | ------ |
| < 5%    | 2      |     | < $1B   | 2      |
| 5–10%   | 4      |     | $1–5B   | 4      |
| 10–20%  | 7      |     | $5–20B  | 7      |
| >= 20%  | 9      |     | >= $20B | 9      |
| Unknown | 2      |     | Unknown | 2      |

### Competition Score (0–10)

Weighted combination of incumbent density, startup activity, and capital deployed:

```
competition = 0.4 * incumbent_points + 0.4 * startup_points + 0.2 * capital_points
```

Higher scores indicate more competitive markets.

### White Space and Final Score

```
white_space_raw = growth - competition
score = clamp(5 + white_space_raw / 2, 1, 10)
```

- A high-growth, low-competition market scores above 5.
- A low-growth, high-competition market scores below 5.

### Verdict

| Score | Verdict   |
| ----- | --------- |
| >= 6  | **GO**    |
| < 6   | **NO_GO** |

### Edge Cases

- **Insufficient market data** (LOW confidence, no TAM, no CAGR): score capped at 5.
- **Missing competition data** (0 incumbents, 0 startups): score capped at 6 unless both TAM and CAGR are available.

### Confidence

Inherited from Agent 3's market scan assessment:

- **HIGH:** TAM and CAGR both supported by 2+ independent sources.
- **MEDIUM:** One source or partial data (e.g., TAM present but CAGR missing).
- **LOW:** Most values missing or derived from vague references.

## Design Decisions

**Async multi-agent architecture.** Agents 1–3 run concurrently via `asyncio.gather`. Each agent performs independent web searches and extraction, so concurrent execution cuts wall-clock time roughly to that of the slowest agent rather than the sum of all three.

**Evidence-only extraction.** The extraction prompt explicitly instructs the LLM to use only the provided source snippets. Fields without supporting evidence are set to `null`, not guessed. This trades recall for precision — a deliberate choice for a market evaluation tool where false data is worse than missing data.

**Two-tier source filtering (Agent 2).** Web search often returns sources with empty or short snippets. Rather than dropping them, Agent 2 uses tiered filtering: Tier A selects sources with funding keywords in title or snippet; Tier B (fallback) includes sources from high-signal domains (TechCrunch, Crunchbase, PitchBook, etc.) or URLs with funding-related paths. This prevents the extraction step from receiving zero sources.

**Deterministic scoring (Agent 4).** The judgement agent uses no LLM calls. Scoring is a pure function of structured data from the other agents, making it reproducible, fast, and auditable.

**Graceful degradation.** Each agent is wrapped in an exception handler with a fallback return value. A single agent failure produces an error entry in the response but does not crash the pipeline. The final result always has a valid structure.

**Strict JSON schema extraction.** Pydantic schemas are transformed to OpenAI strict mode, with validation retries that feed error messages back to the model for self-correction (up to 3 attempts).

## ⏱ Runtime Expectations

**Typical runtime:** ~180,000–240,000 ms (≈3–4 minutes) per product space query.

This runtime is expected and primarily driven by the following stages:

### 1. Concurrent Web Search

- Executes 3 parallel search queries
- Fetches up to 12 results per query
- Network latency dominates this phase

### 2. Source Cleaning & Tiered Filtering

- Deduplicates sources
- Detects funding signal keywords
- Prioritizes high-signal funding domains
- Caps sources to control extraction latency

### 3. Structured Extraction (LLM-Based)

- Bounded with a 180s timeout
- Limited to 1 retry
- Hard cap of 6 sources per extraction
- Strict schema validation (no inferred data allowed)

---

### Why It’s Not Instant

The system is optimized for:

- Accuracy over speed
- Verified funding evidence
- Schema-validated structured output
- Guardrails against hallucination

The current configuration prioritizes reliability and structured correctness.  
Runtime can be reduced further by lowering source caps or timeout limits, at the cost of recall and extraction robustness.

## Limitations

- **Null values are expected.** When public evidence doesn't support a field (SAM, investor names, funding dates), the system returns `null` rather than fabricating data.
- **Depends on public web evidence.** The system cannot access paywalled reports, private databases, or proprietary datasets. Market sizing data is only as good as what's publicly available.
- **No persistence.** There is no database. Results are computed per-request and not stored.
- **In-memory cache only.** Search results are cached per-process to avoid duplicate API calls within a pipeline run. The cache does not survive restarts.
- **Model variability.** LLM extraction quality varies across runs. The same product space may yield slightly different results on repeated calls, particularly for edge-case fields like investor names or funding dates.
- **No rate limiting.** The API does not throttle incoming requests or OpenAI API usage. Production deployment would need rate limiting.

## Logging and Observability

The system uses Python's `logging` module at `INFO` level with structured milestone markers.

### Agent-level timing

Each agent logs timing at every stage:

```
[Agent2] SEARCH_TOTAL in 3.42s
[Agent2] Cleaned: 28
[Agent2] Tier A (keyword match): 12
[Agent2] Using Tier A (12 sources)
[Agent2] CLEAN_DONE in 0.15s (sources=12, tier=A)
[Agent2] Sending 12 sources to extraction
[Agent2] EXTRACT_DONE in 4.21s (companies=6)
[Agent2] TOTAL in 7.89s
```

### Search source coverage

Every web search call logs how many sources have populated titles and snippets:

```
[Search] Source coverage: 15 total, 14 with title, 11 with snippet
```

### Debug: raw source shape

Set `DEBUG_WEB_SEARCH_SHAPE=true` to dump the raw OpenAI web search source object structure (logged once per process). Useful for diagnosing field name changes in the SDK:

```
[DEBUG_SHAPE] type=WebSearchSource
[DEBUG_SHAPE] __dict__={'url': '...', 'title': '...', 'snippet': '...'}
```

## Future Improvements

- **Persistent cache.** Replace the in-memory dict with Redis or SQLite to survive restarts and share across workers.
- **Source ranking model.** Rank sources by relevance and recency before sending to extraction, rather than relying solely on keyword/domain heuristics.
- **Deeper market modeling.** Incorporate SOM (Serviceable Obtainable Market), competitive moat analysis, and funding velocity trends over time.
- **Configurable scoring weights.** Expose growth/competition/white_space weights as parameters so different evaluation contexts can tune the model.
- **UI layer.** A frontend that visualizes the report: competitor landscape, funding timeline, market sizing charts, and confidence indicators.
- **Batch evaluation.** Support evaluating multiple product spaces in a single request with shared search cache benefits.
- **Database persistence.** Store evaluation results with timestamps for historical comparison and trend analysis.
