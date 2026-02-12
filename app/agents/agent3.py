from __future__ import annotations

import logging

from app.core.search import web_search
from app.core.clean import clean_sources
from app.core.extract import extract_structured
from app.schemas import Confidence, ErrorItem, MarketScan, Source

logger = logging.getLogger(__name__)

_AGENT = "agent3"

_EXTRACTION_INSTRUCTIONS = (
    "You are extracting market metrics for: {product_space}.\n\n"
    "Use ONLY the evidence provided (title/url/snippet). Do not use outside knowledge.\n\n"
    "Extract:\n"
    "  - tam_usd (number, USD) and tam_year (int)\n"
    "  - sam_usd and sam_year if available (else null)\n"
    "  - cagr_5y_percent (number, percent) if available (else null)\n\n"
    "If multiple conflicting numbers appear:\n"
    "  - prefer the most specific + most recent year\n"
    "  - explain conflict briefly in notes\n\n"
    "Confidence rules:\n"
    "  - high = at least 2 independent sources support TAM and CAGR "
    "(or TAM + forecast)\n"
    "  - medium = only one strong source for TAM, and either CAGR missing "
    "or only one source\n"
    "  - low = values missing OR only vague/unsourced snippets\n\n"
    "If you cannot support a field from evidence, set it to null.\n"
    "Do NOT guess. Do NOT round wildly. Keep numbers reasonable.\n"
    "If the exact product_space does not have published market sizing, you may use the closest clearly defined adjacent market, but explicitly state the category used in the notes.\n"
)


async def _search_and_collect(
    queries: list[str],
    max_results_per_query: int,
) -> tuple[list[Source], list[ErrorItem]]:
    """Run multiple web searches and return merged sources + errors."""
    all_sources: list[Source] = []
    all_errors: list[ErrorItem] = []
    for query in queries:
        sources, errs = await web_search(query, max_results=max_results_per_query)
        all_sources.extend(sources)
        all_errors.extend(errs)
    return all_sources, all_errors


async def run_agent3(
    product_space: str,
) -> tuple[MarketScan, list[ErrorItem]]:
    """Return quantitative market metrics (TAM, SAM, CAGR) for the product space.

    Always returns a valid MarketScan, even on failure.
    """
    errors: list[ErrorItem] = []

    # --- 1. Search (4 targeted queries) ---
    queries = [
    # Direct market sizing
    f"{product_space} market size 2024 2025 CAGR",

    # “Industry report” phrasing (often used by publishers)
    f"{product_space} market report market size forecast",

    # TAM + CAGR keywords together
    f"{product_space} TAM SAM CAGR forecast",

    # Analyst/report brands (works across categories)
    f"{product_space} market size Gartner Forrester IDC",

    # “Software/tools” framing (helps when product_space is a tool)
    f"{product_space} software market size forecast CAGR",
]


    raw_sources, search_errors = await _search_and_collect(queries, max_results_per_query=10)
    errors.extend(search_errors)

    # --- 2. Clean ---
    sources = clean_sources(raw_sources, max_results=25)

    # --- 3. Extract ---
    instructions = _EXTRACTION_INSTRUCTIONS.replace("{product_space}", product_space)

    report, extract_errors = await extract_structured(
        agent=_AGENT,
        schema_model=MarketScan,
        product_space=product_space,
        sources=sources,
        instructions=instructions,
    )
    errors.extend(extract_errors)

    # --- 4. Handle extraction failure ---
    if report is None:
        if not any(e.agent == _AGENT for e in errors):
            errors.append(
                ErrorItem(agent=_AGENT, message="No market metrics extracted")
            )
        return MarketScan(
            confidence=Confidence.LOW,
            notes="No usable market metrics found",
            sources=sources,
        ), errors

    # --- 5. Optional follow-up if both TAM and CAGR are missing ---
    if report.tam_usd is None and report.cagr_5y_percent is None:
        logger.info("TAM and CAGR both missing — running follow-up search")
        followup_query = f"{product_space} industry market size billion forecast CAGR"
        followup_sources, followup_errors = await web_search(followup_query, max_results=8)
        errors.extend(followup_errors)

        if followup_sources:
            merged = raw_sources + followup_sources
            sources = clean_sources(merged, max_results=25)

            report2, extract_errors2 = await extract_structured(
                agent=_AGENT,
                schema_model=MarketScan,
                product_space=product_space,
                sources=sources,
                instructions=instructions,
            )
            errors.extend(extract_errors2)

            if report2 is not None:
                report = report2

    # --- 6. Attach global sources and return ---
    report.sources = sources

    return report, errors
