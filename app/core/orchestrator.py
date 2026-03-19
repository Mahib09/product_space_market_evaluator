from __future__ import annotations

import asyncio
import logging
import uuid
import time

from app.agents.agent1 import IncumbentsAgent
from app.agents.agent2 import StartupsAgent
from app.agents.agent3 import MarketScanAgent
from app.agents.agent4 import JudgementAgent
from app.config import AGENT1_TIMEOUT, AGENT2_TIMEOUT, AGENT3_TIMEOUT
from app.core.persistence import save_result
from app.schemas import (
    Breakdown,
    Confidence,
    ErrorItem,
    FinalResult,
    IncumbentsReport,
    Judgement,
    MarketScan,
    Startups,
    Verdict,
)

logger = logging.getLogger(__name__)


# -- Fallbacks (always valid, always safe) ----------------------------------

def _fallback_incumbents() -> IncumbentsReport:
    return IncumbentsReport(players=[], sources=[])


def _fallback_startups() -> Startups:
    return Startups(companies=[], startup_count=0, total_capital_usd=None, sources=[])


def _fallback_market() -> MarketScan:
    return MarketScan(
        tam_usd=None,
        cagr_5y_percent=None,
        confidence=Confidence.LOW,
        sources=[],
        notes="Agent 3 failed",
    )


def _fallback_judgement() -> Judgement:
    return Judgement(
        verdict=Verdict.NO_GO,
        score=1,
        breakdown=Breakdown(growth_score=0, competition_score=0, white_space=0),
        summary="Judgement could not be computed due to upstream failures.",
        confidence=Confidence.LOW,
    )


# -- Agent wrappers with exception handling ---------------------------------

async def _run_agent1_safe(
    agent: IncumbentsAgent, product_space: str
) -> tuple[IncumbentsReport, list[ErrorItem]]:
    try:
        logger.info("[Agent1] START")
        return await asyncio.wait_for(agent.run(product_space), timeout=AGENT1_TIMEOUT)
    except asyncio.TimeoutError:
        logger.error("agent1 timed out after %ss", AGENT1_TIMEOUT)
        return _fallback_incumbents(), [
            ErrorItem(agent="agent1", message=f"timed out after {AGENT1_TIMEOUT}s"),
        ]
    except Exception as exc:
        logger.error("agent1 crashed: %s", exc)
        return _fallback_incumbents(), [
            ErrorItem(agent="agent1", message=f"unexpected error: {exc}"),
        ]


async def _run_agent2_safe(
    agent: StartupsAgent, product_space: str
) -> tuple[Startups, list[ErrorItem]]:
    try:
        logger.info("[Agent2] START")
        return await asyncio.wait_for(agent.run(product_space), timeout=AGENT2_TIMEOUT)
    except asyncio.TimeoutError:
        logger.error("agent2 timed out after %ss", AGENT2_TIMEOUT)
        return _fallback_startups(), [
            ErrorItem(agent="agent2", message=f"timed out after {AGENT2_TIMEOUT}s"),
        ]
    except Exception as exc:
        logger.error("agent2 crashed: %s", exc)
        return _fallback_startups(), [
            ErrorItem(agent="agent2", message=f"unexpected error: {exc}"),
        ]


async def _run_agent3_safe(
    agent: MarketScanAgent, product_space: str
) -> tuple[MarketScan, list[ErrorItem]]:
    try:
        logger.info("[Agent3] START")
        return await asyncio.wait_for(agent.run(product_space), timeout=AGENT3_TIMEOUT)
    except asyncio.TimeoutError:
        logger.error("agent3 timed out after %ss", AGENT3_TIMEOUT)
        return _fallback_market(), [
            ErrorItem(agent="agent3", message=f"timed out after {AGENT3_TIMEOUT}s"),
        ]
    except Exception as exc:
        logger.error("agent3 crashed: %s", exc)
        return _fallback_market(), [
            ErrorItem(agent="agent3", message=f"unexpected error: {exc}"),
        ]


# -- Pipeline ---------------------------------------------------------------

async def run_pipeline(
    product_space: str,
    agent1: IncumbentsAgent | None = None,
    agent2: StartupsAgent | None = None,
    agent3: MarketScanAgent | None = None,
    agent4: JudgementAgent | None = None,
) -> FinalResult:
    """Orchestrate all agents and return a complete FinalResult.

    Agents 1-3 run concurrently. Agent 4 (judgement) runs synchronously
    after the first three complete. No single agent failure kills the pipeline.
    """
    a1 = agent1 or IncumbentsAgent()
    a2 = agent2 or StartupsAgent()
    a3 = agent3 or MarketScanAgent()
    a4 = agent4 or JudgementAgent()

    request_id = uuid.uuid4().hex[:12]
    start = time.perf_counter()

    logger.info('[Orchestrator] START request_id=%s product_space="%s"', request_id, product_space)

    # --- Step 0: Validate input ---
    if not product_space or not product_space.strip():
        logger.info('[Orchestrator] DONE request_id=%s status=400 total=%.2fs errors=1', request_id, time.perf_counter() - start)
        return FinalResult(
            request_id=request_id,
            product_space=product_space or "",
            errors=[ErrorItem(agent="pipeline", message="product_space is empty")],
        )

    # --- Step 1: Run agents 1-3 concurrently ---
    logger.info("[Orchestrator] LAUNCH request_id=%s agents=3 mode=concurrent", request_id)

    (incumbents, errs1), (startups, errs2), (market, errs3) = await asyncio.gather(
        _run_agent1_safe(a1, product_space),
        _run_agent2_safe(a2, product_space),
        _run_agent3_safe(a3, product_space),
    )
    logger.info("[Orchestrator] GATHER_DONE request_id=%s", request_id)

    # --- Step 2: Merge errors ---
    all_errors: list[ErrorItem] = errs1 + errs2 + errs3

    # --- Step 3: Run judgement (sync, no API calls) ---
    judgement = None
    try:
        logger.info("[Orchestrator] JUDGEMENT_START request_id=%s", request_id)
        judgement = a4.run(incumbents=incumbents, startups=startups, market_scan=market)
        logger.info(
            "[Orchestrator] JUDGEMENT request_id=%s verdict=%s score=%s",
            request_id, judgement.verdict, judgement.score
        )
    except Exception as exc:
        logger.error("agent4 crashed: %s", exc)
        all_errors.append(
            ErrorItem(agent="agent4", message=f"unexpected error: {exc}"),
        )

    # --- Step 4: Build FinalResult ---
    result = FinalResult(
        request_id=request_id,
        product_space=product_space,
        incumbents=incumbents,
        startups=startups,
        market_scan=market,
        judgement=judgement or _fallback_judgement(),
        errors=all_errors,
    )

    if judgement is not None:
        await save_result(result)

    return result
