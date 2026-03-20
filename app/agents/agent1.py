from __future__ import annotations

import asyncio
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
    "Identify 5-8 established incumbents that directly compete in the {product_space} space.\n\n"
    "An 'incumbent' means: a company with an existing product, real customers, and meaningful "
    "market presence in this specific category — not a tangentially related platform.\n\n"
    "For each incumbent extract:\n"
    "  - name\n"
    "  - offerings: 1-2 sentences describing specifically what they offer in this space\n"
    "  - target_customers: who buys this product (role, company size, or industry sector)\n"
    "  - differentiators: their stated competitive advantage, or null if not in evidence\n\n"
    "Rules:\n"
    "  - Only include a company if the evidence shows it competes in {product_space} specifically.\n"
    "  - Do not include general-purpose platforms unless they have a dedicated product for this space.\n"
    "  - Include incumbents from any industry — not just technology companies.\n"
    "  - Use only the evidence provided. Do not guess.\n"
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

        # 1. Search — two concurrent queries to avoid enterprise-only bias
        query1 = f"{product_space} companies products solutions providers"
        query2 = f"{product_space} top vendors market leaders competitors"

        (sources1, errs1), (sources2, errs2) = await asyncio.gather(
            self._search(query1, max_results=10),
            self._search(query2, max_results=10),
        )
        errors.extend(errs1)
        errors.extend(errs2)
        merged = sources1 + sources2
        logger.info("[Agent1] SEARCH_DONE request_id=%s raw=%s", request_id, len(merged))

        # 2. Clean
        sources = self._clean(merged, 10)
        logger.info("[Agent1] CLEAN_DONE request_id=%s sources=%s", request_id, len(sources))

        # 3. Extract
        instructions = _EXTRACTION_INSTRUCTIONS.replace("{product_space}", product_space)
        report, extract_errors = await self._extract(
            agent=_AGENT,
            schema_model=IncumbentsReport,
            product_space=product_space,
            sources=sources,
            instructions=instructions,
            max_retries=1,
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
