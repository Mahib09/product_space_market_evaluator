from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import Counter

from app.core.search import web_search
from app.core.clean import clean_sources
from app.core.extract import extract_structured
from app.schemas import ErrorItem, Startups, Source

logger = logging.getLogger(__name__)

_AGENT = "agent2"

_EXTRACTION_INSTRUCTIONS = (
    "Extract Seed through Series B startups relevant to {product_space}.\n"
    "Return 5-10 companies if evidence supports; otherwise fewer.\n"
    "Only use evidence from the provided snippets and URLs.\n\n"
    "For each company extract:\n"
    "  - name (required)\n"
    "  - stage (Seed/Series A/Series B/etc.) or null if not explicitly stated\n"
    "  - amount_usd as a numeric value in USD (e.g., 25000000) or null\n"
    "  - date in YYYY-MM-DD format if explicitly stated, otherwise null\n"
    "  - lead_investors: a list of investor or VC firm names ONLY if explicitly mentioned\n"
    "    Look for phrases such as 'led by', 'backed by', 'investors include', "
    "'raised from', or 'participated'.\n"
    "    Extract firm names exactly as written. If not stated, return an empty list [].\n\n"
    "Important rules:\n"
    "  - Do NOT guess missing amounts, dates, or investors.\n"
    "  - Do NOT infer investor names from general knowledge.\n"
    "  - Only include a company if there is clear funding evidence in the snippets.\n"
    "  - Prefer funding announcement articles (e.g., TechCrunch, press releases, "
    "company blogs) that explicitly mention funding rounds and investors.\n"
)

_MAX_COMPANIES = 10

_FUNDING_KEYWORDS = re.compile(
    r"raised|funding|seed|series\s*[abc]|led\s+by|round|backed\s+by|venture",
    re.IGNORECASE,
)


def _has_funding_signal(src: Source) -> bool:
    """Return True if title or snippet mentions funding-related keywords."""
    return bool(_FUNDING_KEYWORDS.search(f"{src.title} {src.snippet}"))


def _deduplicate_companies(companies: list) -> list:
    """Deduplicate companies by name (case-insensitive), keeping first occurrence."""
    seen: set[str] = set()
    unique: list = []
    for company in companies:
        key = company.name.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(company)
    return unique


def _compute_top_investors(companies: list, top_n: int = 5) -> list[str]:
    """Return the most frequent investor names across companies (case-insensitive)."""
    counter: Counter[str] = Counter()
    for company in companies:
        for inv in company.lead_investors:
            counter[inv.strip().lower()] += 1

    # Return original-cased names for the top investors
    # Build a map from lowered name -> first-seen original name
    original_name: dict[str, str] = {}
    for company in companies:
        for inv in company.lead_investors:
            key = inv.strip().lower()
            if key not in original_name:
                original_name[key] = inv.strip()

    return [original_name[name] for name, _ in counter.most_common(top_n)]


def _compute_velocity_note(companies: list) -> str:
    """Compute velocity note based on number of funded companies."""
    count = len(companies)
    if count >= 5:
        return "High funding velocity"
    elif count >= 2:
        return "Moderate"
    else:
        return "Low / limited public funding evidence"


async def run_agent2(
    product_space: str,
) -> tuple[Startups, list[ErrorItem]]:
    """Find recent funded startups (Seed-Series B) relevant to the product space.

    Always returns a valid Startups report, even on failure (with empty companies).
    """
    errors: list[ErrorItem] = []
    t_total = time.perf_counter()

    # --- 1. Search (3 queries, concurrent) ---
    query1 = f"{product_space} startup funding Seed Series A Series B 2024 2025"
    query2 = f'{product_space} "raised" "Series A" "Series B" investors'
    query3 = f'{product_space} "led by" investors funding round'

    async def _timed_search(label: str, query: str):
        t0 = time.perf_counter()
        result = await web_search(query, max_results=12)
        logger.info("[Agent2] %s in %.2fs", label, time.perf_counter() - t0)
        return result

    t_search = time.perf_counter()
    (sources1, errs1), (sources2, errs2), (sources3, errs3) = await asyncio.gather(
        _timed_search("QUERY1_DONE", query1),
        _timed_search("QUERY2_DONE", query2),
        _timed_search("QUERY3_DONE", query3),
    )
    logger.info("[Agent2] SEARCH_TOTAL in %.2fs", time.perf_counter() - t_search)
    errors.extend(errs1)
    errors.extend(errs2)
    errors.extend(errs3)

    merged = sources1 + sources2 + sources3

    # --- 2. Clean + prioritise funding-relevant sources ---
    t_clean = time.perf_counter()
    cleaned = clean_sources(merged, max_results=40)
    funding_hits = [s for s in cleaned if _has_funding_signal(s)]
    others = [s for s in cleaned if not _has_funding_signal(s)]
    sources = (funding_hits + others)[:15]
    logger.info("[Agent2] CLEAN_DONE in %.2fs (sources=%d)", time.perf_counter() - t_clean, len(sources))

    # --- 3. Extract ---
    logger.info("[Agent2] Sending %d sources to extraction", len(sources))
    instructions = _EXTRACTION_INSTRUCTIONS.replace("{product_space}", product_space)

    t_extract = time.perf_counter()
    report, extract_errors = await extract_structured(
        agent=_AGENT,
        schema_model=Startups,
        product_space=product_space,
        sources=sources,
        instructions=instructions,
    )
    companies_count = len(report.companies) if report else 0
    logger.info("[Agent2] EXTRACT_DONE in %.2fs (companies=%d)", time.perf_counter() - t_extract, companies_count)
    errors.extend(extract_errors)

    # --- 4. Handle extraction failure ---
    if report is None:
        if not any(e.agent == _AGENT for e in errors):
            errors.append(
                ErrorItem(agent=_AGENT, message="No startups extracted")
            )
        logger.info("[Agent2] TOTAL in %.2fs (extraction failed)", time.perf_counter() - t_total)
        return Startups(companies=[], sources=sources, startup_count=0), errors

    # --- 5. Post-process ---
    t_post = time.perf_counter()
    report.companies = _deduplicate_companies(report.companies)
    report.companies = report.companies[:_MAX_COMPANIES]

    report.startup_count = len(report.companies)
    report.total_capital_usd = sum(
        c.amount_usd for c in report.companies if c.amount_usd is not None
    )
    report.top_investors = _compute_top_investors(report.companies)
    report.velocity_note = _compute_velocity_note(report.companies)
    report.sources = sources
    logger.info("[Agent2] POST_DONE in %.2fs", time.perf_counter() - t_post)

    logger.info("[Agent2] TOTAL in %.2fs", time.perf_counter() - t_total)
    return report, errors
