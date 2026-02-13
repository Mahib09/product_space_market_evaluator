from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
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

# ✅ simple guardrails
_SOURCES_CAP = 6
_EXTRACT_TIMEOUT_S = 180
_EXTRACT_RETRIES = 1

_FUNDING_KEYWORDS = re.compile(
    r"raised|funding|seed|series\s*[abc]|led\s+by|backed\s+by|round|"
    r"investment|financing|venture",
    re.IGNORECASE,
)

_HIGH_SIGNAL_DOMAINS = {
    "techcrunch.com",
    "crunchbase.com",
    "prnewswire.com",
    "businesswire.com",
    "pitchbook.com",
    "cbinsights.com",
    "venturebeat.com",
    "bloomberg.com",
    "reuters.com",
    "sifted.eu",
    "eu-startups.com",
}

_FUNDING_URL_PATTERN = re.compile(
    r"funding|series-[abc]|seed-round|raises|investment|venture|fundrais",
    re.IGNORECASE,
)


def _has_funding_signal(src: Source) -> bool:
    return bool(_FUNDING_KEYWORDS.search(f"{src.title} {src.snippet}"))


def _is_high_signal_domain(src: Source) -> bool:
    host = str(src.url).lower()
    return any(domain in host for domain in _HIGH_SIGNAL_DOMAINS)


def _has_funding_url(src: Source) -> bool:
    return bool(_FUNDING_URL_PATTERN.search(str(src.url)))


def _is_wikipedia(src: Source) -> bool:
    return "wikipedia.org" in str(src.url).lower()


def _tiered_filter(sources: list[Source], request_id: str) -> tuple[list[Source], str]:
    if not sources:
        return [], "none"

    tier_a: list[Source] = [
        src for src in sources
        if not _is_wikipedia(src) and _has_funding_signal(src)
    ]
    logger.info("[Agent2] TIER_A request_id=%s keyword_match=%d", request_id, len(tier_a))

    if len(tier_a) >= 5:
        return tier_a, "A"

    tier_b_extra: list[Source] = [
        src for src in sources
        if not _is_wikipedia(src)
        and src not in tier_a
        and (_is_high_signal_domain(src) or _has_funding_url(src))
    ]
    combined = tier_a + tier_b_extra
    if combined:
        return combined, "A+B"

    fallback = [src for src in sources if not _is_wikipedia(src)]
    return fallback, "fallback"


def _deduplicate_companies(companies: list) -> list:
    seen: set[str] = set()
    unique: list = []
    for company in companies:
        key = company.name.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(company)
    return unique


async def run_agent2(product_space: str) -> tuple[Startups, list[ErrorItem]]:
    request_id = uuid.uuid4().hex[:12]
    errors: list[ErrorItem] = []
    t_total = time.perf_counter()

    logger.info('[Agent2] START request_id=%s product_space="%s"', request_id, product_space)

    # --- 1. Search (3 queries, concurrent) ---
    query1 = f"{product_space} startup funding Seed Series A Series B 2024 2025"
    query2 = f'{product_space} "raised" "Series A" "Series B" investors'
    query3 = f'{product_space} "led by" investors funding round'

    async def _timed_search(label: str, query: str):
        t0 = time.perf_counter()
        (srcs, errs) = await web_search(query, max_results=12)
        logger.info(
            "[Agent2] %s request_id=%s in %.2fs raw=%d",
            label, request_id, time.perf_counter() - t0, len(srcs) if srcs else 0
        )
        return (srcs, errs)

    (sources1, errs1), (sources2, errs2), (sources3, errs3) = await asyncio.gather(
        _timed_search("QUERY1_DONE", query1),
        _timed_search("QUERY2_DONE", query2),
        _timed_search("QUERY3_DONE", query3),
    )
    errors.extend(errs1)
    errors.extend(errs2)
    errors.extend(errs3)

    merged = sources1 + sources2 + sources3
    cleaned = clean_sources(merged, max_results=40)
    filtered, tier_used = _tiered_filter(cleaned, request_id)

    # fallback search if too few sources
    if len(filtered) < 5 and len(cleaned) > 0:
        fallback_query = (
            f'{product_space} startup raised seed "Series A" "Series B"'
            f' led by investors funding round'
        )
        fb_sources, fb_errs = await web_search(fallback_query, max_results=12)
        errors.extend(fb_errs)

        merged_fb = merged + fb_sources
        cleaned_fb = clean_sources(merged_fb, max_results=40)
        filtered, tier_used = _tiered_filter(cleaned_fb, request_id)

    # ✅ hard cap sources (key speed win)
    sources = filtered[:_SOURCES_CAP]
    logger.info(
        "[Agent2] SOURCES request_id=%s tier=%s sources=%d",
        request_id, tier_used, len(sources)
    )

    # --- 2. Extract (bounded) ---
    instructions = _EXTRACTION_INSTRUCTIONS.replace("{product_space}", product_space)
    logger.info("[Agent2] EXTRACT_START request_id=%s timeout=%ds", request_id, _EXTRACT_TIMEOUT_S)

    t_extract = time.perf_counter()
    try:
        report, extract_errors = await asyncio.wait_for(
            extract_structured(
                agent=_AGENT,
                schema_model=Startups,
                product_space=product_space,
                sources=sources,
                instructions=instructions,
                max_retries=_EXTRACT_RETRIES,  # ✅ fewer retries
            ),
            timeout=_EXTRACT_TIMEOUT_S,  # ✅ cannot hang forever
        )
    except asyncio.TimeoutError:
        logger.warning("[Agent2] EXTRACT_TIMEOUT request_id=%s after %.2fs", request_id, time.perf_counter() - t_extract)
        return Startups(companies=[], sources=sources, startup_count=0), errors

    errors.extend(extract_errors)

    companies_count = len(report.companies) if report and report.companies else 0
    logger.info(
        "[Agent2] EXTRACT_DONE request_id=%s in %.2fs companies=%d extract_errors=%d",
        request_id, time.perf_counter() - t_extract, companies_count, len(extract_errors)
    )

    if report is None:
        if not any(e.agent == _AGENT for e in errors):
            errors.append(ErrorItem(agent=_AGENT, message="No startups extracted"))
        return Startups(companies=[], sources=sources, startup_count=0), errors

    # --- 3. Minimal post-process (keep simple) ---
    report.companies = _deduplicate_companies(report.companies)[:_MAX_COMPANIES]
    report.startup_count = len(report.companies)
    report.sources = sources

    logger.info(
        "[Agent2] TOTAL request_id=%s in %.2fs companies=%d sources=%d errors=%d",
        request_id, time.perf_counter() - t_total, len(report.companies), len(report.sources), len(errors)
    )
    return report, errors
