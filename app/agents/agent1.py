from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable, Awaitable

from app.core.search import web_search
from app.core.clean import clean_sources
from app.core.extract import extract_structured
from app.schemas import ErrorItem, IncumbentsReport, Source

logger = logging.getLogger(__name__)

_AGENT = "agent1"
_MAX_PLAYERS = 8

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
    "5. If a field isn't supported, set it null/empty but only include a player if you have evidence for the player existing in this product space. "
    "Do not guess.\n"
)


class IncumbentsAgent:
    def __init__(
        self,
        search_fn: Callable[..., Awaitable[tuple[list[Source], list[ErrorItem]]]] = web_search,
        extract_fn: Callable[..., Awaitable[tuple[IncumbentsReport | None, list[ErrorItem]]]] = extract_structured,
        clean_fn: Callable[[list[Source], int], list[Source]] = clean_sources,
    ) -> None:
        self._search = search_fn
        self._extract = extract_fn
        self._clean = clean_fn

    async def run(self, product_space: str) -> tuple[IncumbentsReport, list[ErrorItem]]:
        """Identify established enterprise incumbents. Always returns a valid report."""
        request_id = uuid.uuid4().hex[:12]
        total_start = time.perf_counter()
        errors: list[ErrorItem] = []

        logger.info('[Agent1] START request_id=%s product_space="%s"', request_id, product_space)

        # 1. Search
        query = f"{product_space} top vendors competitors market leaders enterprise"
        sources, search_errors = await self._search(query, max_results=20)
        errors.extend(search_errors)
        logger.info("[Agent1] SEARCH_DONE request_id=%s raw=%s", request_id, len(sources))

        # 2. Clean
        sources = self._clean(sources, 12)
        logger.info("[Agent1] CLEAN_DONE request_id=%s sources=%s", request_id, len(sources))

        # 3. Extract
        report, extract_errors = await self._extract(
            agent=_AGENT,
            schema_model=IncumbentsReport,
            product_space=product_space,
            sources=sources,
            instructions=_EXTRACTION_INSTRUCTIONS,
        )
        errors.extend(extract_errors)

        # 4. Handle failure
        if report is None:
            if not any(e.agent == _AGENT for e in errors):
                errors.append(ErrorItem(agent=_AGENT, message="No incumbents extracted"))
            logger.info("[Agent1] TOTAL request_id=%s status=fallback", request_id)
            return IncumbentsReport(players=[], sources=sources), errors

        # 5. Post-process
        report.players = report.players[:_MAX_PLAYERS]
        report.sources = sources
        logger.info(
            "[Agent1] TOTAL request_id=%s in %.2fs players=%s",
            request_id, time.perf_counter() - total_start, len(report.players),
        )
        return report, errors
