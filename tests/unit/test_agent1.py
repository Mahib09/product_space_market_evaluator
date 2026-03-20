from unittest.mock import AsyncMock
import pytest
from app.agents.agent1 import IncumbentsAgent
from app.schemas import IncumbentsReport, Player, Source, ErrorItem


def _source(url="https://example.com", title="Example Title", snippet="Some relevant snippet text here"):
    return Source(url=url, title=title, snippet=snippet)


def _player(name="Salesforce"):
    return Player(name=name, offerings="CRM platform", target_customers="Enterprise B2B")


def _report(players=None):
    return IncumbentsReport(players=players or [_player()], sources=[_source()])


async def test_happy_path():
    mock_search = AsyncMock(return_value=([_source()], []))
    mock_extract = AsyncMock(return_value=(_report(), []))
    agent = IncumbentsAgent(search_fn=mock_search, extract_fn=mock_extract)
    result, errors = await agent.run("AI sales automation")
    assert len(result.players) >= 1
    assert errors == []
    assert mock_search.call_count == 2
    mock_extract.assert_called_once()


async def test_empty_sources_returns_empty_report():
    mock_search = AsyncMock(return_value=([], []))
    mock_extract = AsyncMock(return_value=(IncumbentsReport(players=[], sources=[]), []))
    agent = IncumbentsAgent(search_fn=mock_search, extract_fn=mock_extract)
    result, errors = await agent.run("niche space")
    assert result.players == []


async def test_extraction_failure_returns_empty_report_with_error():
    mock_search = AsyncMock(return_value=([_source()], []))
    mock_extract = AsyncMock(return_value=(None, [ErrorItem(agent="agent1", message="parse fail")]))
    agent = IncumbentsAgent(search_fn=mock_search, extract_fn=mock_extract)
    result, errors = await agent.run("AI sales automation")
    assert result.players == []
    assert any(e.agent == "agent1" for e in errors)


async def test_two_search_queries_are_made():
    """Agent 1 must run 2 queries to avoid enterprise-only bias."""
    mock_search = AsyncMock(return_value=([_source()], []))
    mock_extract = AsyncMock(return_value=(_report(), []))
    agent = IncumbentsAgent(search_fn=mock_search, extract_fn=mock_extract)
    await agent.run("AI sales automation")
    assert mock_search.call_count == 2


async def test_extract_called_with_max_retries_1():
    mock_search = AsyncMock(return_value=([_source()], []))
    mock_extract = AsyncMock(return_value=(_report(), []))
    agent = IncumbentsAgent(search_fn=mock_search, extract_fn=mock_extract)
    await agent.run("AI sales automation")
    _, kwargs = mock_extract.call_args
    assert kwargs.get("max_retries") == 1


async def test_search_error_propagates():
    err = ErrorItem(agent="search", message="network error")
    mock_search = AsyncMock(return_value=([], [err]))
    mock_extract = AsyncMock(return_value=(IncumbentsReport(players=[], sources=[]), []))
    agent = IncumbentsAgent(search_fn=mock_search, extract_fn=mock_extract)
    result, errors = await agent.run("AI sales automation")
    assert any(e.agent == "search" for e in errors)
