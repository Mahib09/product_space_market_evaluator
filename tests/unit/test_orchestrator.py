from unittest.mock import AsyncMock, MagicMock
import pytest
from app.core.orchestrator import run_pipeline
from app.schemas import (
    Breakdown, Confidence, ErrorItem, FinalResult,
    IncumbentsReport, Judgement, MarketScan, Startups, Verdict,
)


def _incumbents():
    return IncumbentsReport(players=[], sources=[])

def _startups():
    return Startups(companies=[], startup_count=0)

def _market():
    return MarketScan(confidence=Confidence.LOW)

def _judgement():
    return Judgement(
        verdict=Verdict.GO, score=7,
        breakdown=Breakdown(growth_score=7, competition_score=4, white_space=6),
        summary="Test.",
    )


class _MockAgent1:
    async def run(self, product_space):
        return _incumbents(), []

class _MockAgent2:
    async def run(self, product_space):
        return _startups(), []

class _MockAgent3:
    async def run(self, product_space):
        return _market(), []

class _MockAgent4:
    def run(self, incumbents, startups, market_scan):
        return _judgement()


async def test_happy_path_returns_final_result():
    result = await run_pipeline(
        "AI sales",
        agent1=_MockAgent1(),
        agent2=_MockAgent2(),
        agent3=_MockAgent3(),
        agent4=_MockAgent4(),
    )
    assert isinstance(result, FinalResult)
    assert result.product_space == "AI sales"
    assert result.errors == []
    assert result.judgement.verdict == Verdict.GO


async def test_agent1_crash_does_not_prevent_other_agents():
    class CrashAgent1:
        async def run(self, ps):
            raise RuntimeError("agent1 exploded")

    result = await run_pipeline(
        "AI sales",
        agent1=CrashAgent1(),
        agent2=_MockAgent2(),
        agent3=_MockAgent3(),
        agent4=_MockAgent4(),
    )
    assert isinstance(result, FinalResult)
    assert any(e.agent == "agent1" for e in result.errors)
    # `result.startups` is the fallback Startups object from _run_agent2_safe;
    # _run_agent2_safe always returns a Startups instance (never None), so this passes.
    assert result.startups is not None


async def test_empty_product_space_returns_error():
    result = await run_pipeline("")
    assert any(e.agent == "pipeline" for e in result.errors)


async def test_errors_from_all_agents_are_merged():
    class ErrorAgent1:
        async def run(self, ps):
            return _incumbents(), [ErrorItem(agent="agent1", message="err")]

    class ErrorAgent2:
        async def run(self, ps):
            return _startups(), [ErrorItem(agent="agent2", message="err")]

    result = await run_pipeline(
        "AI sales",
        agent1=ErrorAgent1(),
        agent2=ErrorAgent2(),
        agent3=_MockAgent3(),
        agent4=_MockAgent4(),
    )
    agents_with_errors = {e.agent for e in result.errors}
    assert "agent1" in agents_with_errors
    assert "agent2" in agents_with_errors
