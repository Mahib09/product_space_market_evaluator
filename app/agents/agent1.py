from __future__ import annotations

import logging

from app.core.search import web_search
from app.core.clean import clean_sources
from app.core.extract import extract_structured
from app.schemas import ErrorItem, IncumbentsReport, Source

logger = logging.getLogger(__name__)

_AGENT = "agent1"

_EXTRACTION_INSTRUCTIONS = (
    "1. Identify established enterprise players relevant to the product space.\n"
    "2. Return 5-8 incumbents.\n"
    "3. For each player include:\n"
    "   - name\n"
    "   - offerings\n"
    "   - target_customers\n"
    "   - differentiators (null if not supported by evidence)\n"
    "   - sources (list of evidence used for this player)\n"
    "4. Only use evidence provided below.\n"
    "5. If a field isn’t supported, set it null/empty but only include a player if you have evidence for the player existing in this product space. "
    "Do not guess.\n"
)

_MAX_PLAYERS = 8


async def run_agent1(
    product_space: str,
) -> tuple[IncumbentsReport, list[ErrorItem]]:
    """Identify established enterprise incumbents for the given product space.

    Always returns a valid IncumbentsReport, even on failure (with empty players).
    """
    errors: list[ErrorItem] = []

    # --- 1. Search ---
    query = f"{product_space} top vendors competitors market leaders enterprise"
    sources, search_errors = await web_search(query, max_results=10)
    errors.extend(search_errors)
    
    print("\n[DEBUG] Raw sources count:", len(sources))

    # --- 2. Clean ---
    sources = clean_sources(sources, max_results=12)
    print("[DEBUG] Cleaned sources count:", sources[0])
    print(sources[0])

    # --- 3. Extract ---
    report, extract_errors = await extract_structured(
        agent=_AGENT,
        schema_model=IncumbentsReport,
        product_space=product_space,
        sources=sources,
        instructions=_EXTRACTION_INSTRUCTIONS,
    )
    errors.extend(extract_errors)

    # --- 4. Handle extraction failure ---
    if report is None:
        if not any(e.agent == _AGENT for e in errors):
            errors.append(
                ErrorItem(agent=_AGENT, message="No incumbents extracted")
            )
        return IncumbentsReport(players=[], sources=sources), errors

    # --- 5. Post-process ---
    report.players = report.players[:_MAX_PLAYERS]
    report.sources = sources

    return report, errors
