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
    """Return True if title or snippet mentions funding-related keywords."""
    return bool(_FUNDING_KEYWORDS.search(f"{src.title} {src.snippet}"))


def _is_high_signal_domain(src: Source) -> bool:
    """Return True if the source URL belongs to a high-signal domain."""
    host = str(src.url).lower()
    return any(domain in host for domain in _HIGH_SIGNAL_DOMAINS)


def _has_funding_url(src: Source) -> bool:
    """Return True if the URL path contains funding-related terms."""
    return bool(_FUNDING_URL_PATTERN.search(str(src.url)))


def _is_wikipedia(src: Source) -> bool:
    return "wikipedia.org" in str(src.url).lower()


def _tiered_filter(sources: list[Source]) -> tuple[list[Source], str]:
    """Two-tier filtering: keyword match first, domain/URL fallback second.

    Returns (filtered_sources, tier_used).
    """
    if not sources:
        return [], "none"

    empty_snippets = sum(1 for s in sources if len(s.snippet.strip()) == 0)
    logger.info(
        "[Agent2] Filter diagnostics: total=%d, empty_snippets=%d",
        len(sources), empty_snippets,
    )

    # --- Tier A: funding keywords in title+snippet, no snippet length gate ---
    tier_a: list[Source] = [
        src for src in sources
        if not _is_wikipedia(src) and _has_funding_signal(src)
    ]
    keyword_match_count = len(tier_a)
    logger.info("[Agent2] Tier A (keyword match): %d", keyword_match_count)

    if len(tier_a) >= 5:
        logger.info("[Agent2] Using Tier A (%d sources)", len(tier_a))
        return tier_a, "A"

    # --- Tier B: high-signal domain OR funding URL pattern ---
    tier_b_extra: list[Source] = [
        src for src in sources
        if not _is_wikipedia(src)
        and src not in tier_a
        and (_is_high_signal_domain(src) or _has_funding_url(src))
    ]
    logger.info("[Agent2] Tier B extras (domain/URL): %d", len(tier_b_extra))

    combined = tier_a + tier_b_extra
    if combined:
        logger.info("[Agent2] Using Tier A+B (%d sources)", len(combined))
        return combined, "A+B"

    # --- Ultimate fallback: return all non-wikipedia sources ---
    fallback = [src for src in sources if not _is_wikipedia(src)]
    logger.info("[Agent2] Fallback: returning all non-wiki sources (%d)", len(fallback))
    return fallback, "fallback"


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
    logger.info("[Agent2] Raw merged: %d", len(merged))

    # --- 2. Clean + two-tier funding filter ---
    t_clean = time.perf_counter()
    cleaned = clean_sources(merged, max_results=40)
    logger.info("[Agent2] Cleaned: %d", len(cleaned))

    filtered, tier_used = _tiered_filter(cleaned)
    logger.info("[Agent2] Tiered filter (%s): %d", tier_used, len(filtered))

    # --- 2b. Fallback search if too few sources ---
    if len(filtered) < 5 and len(cleaned) > 0:
        logger.info("[Agent2] Filtered < 5 — running fallback search")
        fallback_query = (
            f'{product_space} startup raised seed "Series A" "Series B"'
            f' led by investors funding round'
        )
        t_fb = time.perf_counter()
        fb_sources, fb_errs = await web_search(fallback_query, max_results=12)
        logger.info("[Agent2] FALLBACK_DONE in %.2fs (raw=%d)", time.perf_counter() - t_fb, len(fb_sources))
        errors.extend(fb_errs)

        merged_fb = merged + fb_sources
        cleaned_fb = clean_sources(merged_fb, max_results=40)
        filtered, tier_used = _tiered_filter(cleaned_fb)
        logger.info("[Agent2] Tiered filter after fallback (%s): %d", tier_used, len(filtered))

    sources = filtered[:15]
    logger.info("[Agent2] CLEAN_DONE in %.2fs (sources=%d, tier=%s)", time.perf_counter() - t_clean, len(sources), tier_used)

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
