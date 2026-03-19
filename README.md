# Product Space Market Evaluator

[![CI](https://github.com/Mahib09/product_space_market_evaluator/actions/workflows/ci.yml/badge.svg)](https://github.com/Mahib09/product_space_market_evaluator/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A FastAPI service that evaluates product-space market opportunities through a **multi-agent AI pipeline**. Given a product space (e.g., "AI sales automation"), it returns a structured JSON report covering incumbents, funded startups, market sizing, and a GO/NO_GO verdict — all grounded in web-sourced evidence.

## Quick demo (no API key needed)

```bash
# Clone and install
git clone https://github.com/Mahib09/product_space_market_evaluator
cd product_space_market_evaluator
pip install -r requirements.txt -r requirements-dev.txt

# Rich terminal demo using pre-built sample outputs
python demos/demo.py "AI sales automation" --cached
python demos/demo.py "vertical SaaS for restaurants" --cached
python demos/demo.py "developer observability tools" --cached
```

Sample output:

```
+------- Market Evaluation -------+
|                                 |
|    AI sales automation          |
|                                 |
|    Verdict:   GO                |
|    ############-------- 6/10    |
|                                 |
+---------------------------------+
```

See [demos/](demos/) for the full CLI, sample outputs, and a Jupyter notebook walkthrough.

## Architecture

```
POST /evaluate
       │
       ▼
  run_pipeline()
       │
       ├─── Agent 1 (IncumbentsAgent)  ─┐
       ├─── Agent 2 (StartupsAgent)    ─┼─ asyncio.gather  (concurrent)
       └─── Agent 3 (MarketScanAgent)  ─┘
                                        │
              Each agent:  web_search → clean_sources → extract_structured
                                        │
                                        ▼
                              Agent 4 (JudgementAgent)
                              pure deterministic maths — no API calls
                                        │
                                        ▼
                                  FinalResult (JSON)
                                        │
                                        ▼
                           SQLite persistence (evaluations.db)
```

- **Agent 1** — Identifies 5–8 established incumbents: offerings, target customers, differentiators.
- **Agent 2** — Finds Seed–Series B startups with investor details and funding amounts, backed by evidence only.
- **Agent 3** — Extracts TAM, SAM, and 5-year CAGR from market research sources.
- **Agent 4** — Scores 1–10 and returns GO/NO_GO using a transparent formula. Zero API calls.

Every extracted field is backed by cited sources. If evidence doesn't exist, the field is `null` — the system does not guess.

## Setup

### Prerequisites

- Python 3.11+
- An OpenAI API key with access to `gpt-4.1` (search) and `gpt-5` (extraction)

### Install

```bash
git clone https://github.com/Mahib09/product_space_market_evaluator
cd product_space_market_evaluator

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
```

### Environment

```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | **Required.** OpenAI API key |
| `OPENAI_MODEL_SEARCH` | `gpt-4.1` | Model used for web search |
| `OPENAI_MODEL_EXTRACT` | `gpt-5` | Model used for structured extraction |
| `DEBUG_WEB_SEARCH_SHAPE` | `false` | Log raw web search source shape once per process |

### Run the server

```bash
uvicorn app.main:app --reload
```

### Docker (one command)

```bash
cp .env.example .env   # add your API key
docker compose up --build
```

The API is available at `http://localhost:8000`. SQLite databases are stored in named Docker volumes and persist across restarts.

## API

### `POST /evaluate`

**Request:**

```json
{ "product_space": "AI sales automation" }
```

**Response:** [`FinalResult`](#data-models) — see below.

**Example:**

```bash
curl -X POST http://127.0.0.1:8000/evaluate \
  -H "Content-Type: application/json" \
  -d '{"product_space": "AI sales automation"}'
```

### Example response

```json
{
  "request_id": "3a7f1b9c2e4d",
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
    "sources": []
  },
  "startups": {
    "companies": [
      {
        "name": "AiSDR",
        "stage": "Series A",
        "amount_usd": 15000000,
        "date": "2024-09-01",
        "lead_investors": ["Andreessen Horowitz"],
        "sources": []
      }
    ],
    "total_capital_usd": 117000000,
    "startup_count": 5,
    "top_investors": ["Andreessen Horowitz", "Benchmark"],
    "velocity_note": "",
    "sources": []
  },
  "market_scan": {
    "tam_usd": 6800000000,
    "tam_year": 2024,
    "sam_usd": 1700000000,
    "sam_year": 2024,
    "cagr_5y_percent": 21.3,
    "confidence": "medium",
    "notes": "",
    "sources": []
  },
  "judgement": {
    "verdict": "GO",
    "score": 6,
    "breakdown": {
      "growth_score": 8,
      "competition_score": 8,
      "white_space": 5
    },
    "summary": "6 incumbents identified. 5 startups ($117M known funding). TAM ~$6.8B. CAGR ~21.3%. Market opportunity supports entry.",
    "confidence": "medium"
  },
  "errors": []
}
```

Pre-built sample outputs for three product spaces live in [`demos/sample_outputs/`](demos/sample_outputs/).

## Scoring formula

Agent 4 runs no API calls — pure deterministic maths over the outputs of Agents 1–3.

```
growth      = 0.6 × cagr_pts + 0.4 × tam_pts
competition = 0.4 × inc_pts  + 0.4 × startup_pts + 0.2 × capital_pts
score       = clamp(5 + (growth − competition) / 2, 1, 10)
verdict     = GO if score >= 6
```

| CAGR | Points | | TAM | Points |
|---|---|---|---|---|
| < 5% | 2 | | < $1B | 2 |
| 5–10% | 4 | | $1–5B | 4 |
| 10–20% | 7 | | $5–20B | 7 |
| >= 20% | 9 | | >= $20B | 9 |
| Unknown | 2 | | Unknown | 2 |

**Edge cases:**
- Score capped at **5** when confidence=LOW and both TAM and CAGR are null.
- Score capped at **6** when 0 incumbents and 0 startups (unless both TAM and CAGR are available).

## Testing

```bash
pip install -r requirements-dev.txt
pytest tests/unit/ -v --cov=app --cov-report=term-missing
```

35 unit tests, no API key required. Tests use dependency injection to mock all external calls.

```
tests/unit/
├── test_agent1.py        # IncumbentsAgent — 4 tests
├── test_agent2.py        # StartupsAgent — 4 tests
├── test_agent3.py        # MarketScanAgent — 3 tests
├── test_agent4.py        # JudgementAgent scoring — 10 tests
├── test_cache.py         # SQLite search cache — 2 tests
├── test_clean.py         # Source cleaning pipeline — 5 tests
├── test_orchestrator.py  # Pipeline integration — 4 tests
└── test_persistence.py   # SQLite result store — 3 tests
```

GitHub Actions runs the full unit suite on every push to `main` and `feat/*`.

## Demos

```bash
# Rich terminal demo (live)
python demos/demo.py "AI sales automation"

# Rich terminal demo (offline, using sample_outputs/)
python demos/demo.py "AI sales automation" --cached

# Jupyter notebook walkthrough
cd demos && jupyter notebook notebook.ipynb

# Regenerate sample outputs (requires real API key)
python demos/generate_samples.py
```

## Data models

All Pydantic schemas live in [`app/schemas.py`](app/schemas.py). Top-level response is `FinalResult`:

| Field | Type | Description |
|---|---|---|
| `request_id` | `str` | Unique 12-char hex ID per request |
| `product_space` | `str` | Echo of input |
| `incumbents` | `IncumbentsReport` | Players, offerings, differentiators |
| `startups` | `Startups` | Funded companies, capital, investors |
| `market_scan` | `MarketScan` | TAM, SAM, CAGR, confidence |
| `judgement` | `Judgement` | Verdict, score 1–10, breakdown |
| `errors` | `list[ErrorItem]` | Per-agent errors; never crashes pipeline |

## Project structure

```
app/
├── agents/
│   ├── agent1.py          # IncumbentsAgent class
│   ├── agent2.py          # StartupsAgent class (tiered source filtering)
│   ├── agent3.py          # MarketScanAgent class (follow-up search)
│   └── agent4.py          # JudgementAgent — pure scoring, no I/O
├── core/
│   ├── cache.py           # SQLite search cache (aiosqlite)
│   ├── clean.py           # Source dedup, domain blocklist, quality filter
│   ├── extract.py         # LLM structured extraction with Pydantic retry
│   ├── orchestrator.py    # run_pipeline() — concurrency + error handling
│   ├── persistence.py     # SQLite result store (aiosqlite)
│   └── search.py          # OpenAI web_search tool wrapper
├── main.py                # FastAPI app — single POST /evaluate endpoint
├── schemas.py             # All Pydantic models
└── config.py              # Env var loading

demos/
├── demo.py                # Rich CLI demo
├── generate_samples.py    # Regenerate sample outputs via live pipeline
├── notebook.ipynb         # Jupyter walkthrough
└── sample_outputs/        # Pre-built JSON results (3 product spaces)

tests/
├── unit/                  # 35 tests, no API key required
└── integration/           # 1 test, skipped without real API key

.github/workflows/ci.yml   # GitHub Actions CI
Dockerfile                 # Production container
docker-compose.yml         # One-command startup with volume persistence
```

## Design decisions

**Dependency injection for testability.** Each agent takes `search_fn`, `extract_fn`, and `clean_fn` as constructor arguments defaulting to real implementations. Tests inject mocks — no monkeypatching, no environment hacks.

**Evidence-only extraction.** The extraction prompt instructs the LLM to set fields to `null` rather than guess. Hallucinated market data is worse than missing data.

**Two-tier source filtering (Agent 2).** Tier A selects sources with funding keywords in title/snippet; Tier B falls back to high-signal domains (TechCrunch, Crunchbase, PitchBook). A 4th fallback query runs if neither tier yields 5+ sources.

**Follow-up search (Agent 3).** If both TAM and CAGR come back null after the first pass, a targeted follow-up query runs and extraction repeats.

**Deterministic scoring (Agent 4).** No LLM calls — reproducible, fast, and fully auditable. Formula weights are visible in the source.

**Graceful degradation.** Each agent is wrapped with timeout + exception handling. A single agent failure writes to `errors[]` but never crashes the pipeline.

**SQLite persistence.** Search results are cached in `cache.db` (survives restarts, shared across requests). Evaluation results are stored in `evaluations.db` for the `--cached` demo flag and future retrieval.

## Runtime

Typical: **3–4 minutes** per request. The bottleneck is LLM extraction (bounded at ~180–240 s/agent). Agents 1–3 run concurrently, so wall-clock time ≈ slowest agent, not the sum.

## Limitations

- Null values are expected — public evidence doesn't always exist.
- Depends on public web data; no access to paywalled reports.
- Model output varies run-to-run, especially for edge-case fields.
- No rate limiting — add a reverse proxy for production.
