from __future__ import annotations

import logging
import time
import uuid

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
    request_id = uuid.uuid4().hex[:12]
    total_start = time.perf_counter()

    errors: list[ErrorItem] = []
    logger.info('[Agent1] START request_id=%s product_space="%s"', request_id, product_space)

    # --- 1. Search ---
    logger.info("[Agent1] SEARCH_START request_id=%s", request_id)
    query = f"{product_space} top vendors competitors market leaders enterprise"

    search_start = time.perf_counter()
    sources, search_errors = await web_search(query, max_results=10)
    search_s = time.perf_counter() - search_start

    errors.extend(search_errors)
    raw_count = len(sources) if sources else 0
    logger.info("[Agent1] SEARCH_DONE request_id=%s in %.2fs raw=%s", request_id, search_s, raw_count)

    # --- 2. Clean ---
    clean_start = time.perf_counter()
    sources = clean_sources(sources, max_results=12)
    clean_s = time.perf_counter() - clean_start

    cleaned_count = len(sources) if sources else 0
    logger.info("[Agent1] CLEAN_DONE request_id=%s in %.2fs sources=%s", request_id, clean_s, cleaned_count)

    # keep your existing debug lines, just add request_id
    logger.info("[Agent1] Cleaned sources request_id=%s count=%d", request_id, len(sources))
    for s in sources[:3]:
        logger.info("[Agent1] SOURCE request_id=%s title=%s url=%s", request_id, s.title[:60], s.url)

    # --- 3. Extract ---
    sent_count = len(sources)
    logger.info("[Agent1] EXTRACT_START request_id=%s sources=%s", request_id, sent_count)

    extract_start = time.perf_counter()
    report, extract_errors = await extract_structured(
        agent=_AGENT,
        schema_model=IncumbentsReport,
        product_space=product_space,
        sources=sources,
        instructions=_EXTRACTION_INSTRUCTIONS,
    )
    extract_s = time.perf_counter() - extract_start

    errors.extend(extract_errors)

    players_count = len(report.players) if report and report.players else 0
    logger.info("[Agent1] EXTRACT_DONE request_id=%s in %.2fs players=%s", request_id, extract_s, players_count)

    # --- 4. Handle extraction failure ---
    if report is None:
        if not any(e.agent == _AGENT for e in errors):
            errors.append(ErrorItem(agent=_AGENT, message="No incumbents extracted"))

        total_s = time.perf_counter() - total_start
        logger.info("[Agent1] TOTAL request_id=%s in %.2fs status=fallback errors=%s", request_id, total_s, len(errors))
        return IncumbentsReport(players=[], sources=sources), errors

    # --- 5. Post-process ---
    report.players = report.players[:_MAX_PLAYERS]
    report.sources = sources

    total_s = time.perf_counter() - total_start
    logger.info(
        "[Agent1] TOTAL request_id=%s in %.2fs players=%s sources=%s errors=%s",
        request_id,
        total_s,
        len(report.players),
        len(report.sources),
        len(errors),
    )

    return report, errors
