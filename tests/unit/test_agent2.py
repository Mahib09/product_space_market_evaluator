from unittest.mock import AsyncMock
import pytest
from app.agents.agent2 import StartupsAgent
from app.schemas import Company, ErrorItem, Source, Startups


def _source(url="https://techcrunch.com/series-a", title="TechCrunch Series A", snippet="raised $10M Series A led by"):
    return Source(url=url, title=title, snippet=snippet)


def _company(name="Acme"):
    return Company(name=name, stage="Series A", amount_usd=10_000_000, lead_investors=["Sequoia"])


def _startups(companies=None):
    comps = companies or [_company()]
    return Startups(companies=comps, startup_count=len(comps), total_capital_usd=10_000_000)


async def test_happy_path():
    mock_search = AsyncMock(return_value=([_source()], []))
    mock_extract = AsyncMock(return_value=(_startups(), []))
    agent = StartupsAgent(search_fn=mock_search, extract_fn=mock_extract)
    result, errors = await agent.run("AI sales automation")
    assert result.startup_count >= 1
    assert errors == []


async def test_dedup_removes_duplicate_company_names():
    dupe_companies = [_company("Acme"), _company("acme"), _company("ACME")]
    mock_search = AsyncMock(return_value=([_source()], []))
    mock_extract = AsyncMock(return_value=(_startups(dupe_companies), []))
    agent = StartupsAgent(search_fn=mock_search, extract_fn=mock_extract)
    result, errors = await agent.run("niche SaaS")
    assert result.startup_count == 1


async def test_fallback_query_triggered_when_sparse_sources():
    # First 3 calls return sources with no funding keywords — Tier A and B both < 5
    # 4th call (fallback) returns a funding-keyword source
    sparse = Source(url="https://generic.com", title="Generic Article", snippet="some generic text")
    funding = _source()
    mock_search = AsyncMock(side_effect=[
        ([sparse], []),   # query 1
        ([sparse], []),   # query 2
        ([], []),          # query 3
        ([funding], []),   # query 4 — fallback
    ])
    mock_extract = AsyncMock(return_value=(_startups(), []))
    agent = StartupsAgent(search_fn=mock_search, extract_fn=mock_extract)
    result, errors = await agent.run("niche SaaS")
    assert mock_search.call_count == 4


async def test_extraction_failure_returns_empty_startups():
    mock_search = AsyncMock(return_value=([_source()], []))
    mock_extract = AsyncMock(return_value=(None, [ErrorItem(agent="agent2", message="failed")]))
    agent = StartupsAgent(search_fn=mock_search, extract_fn=mock_extract)
    result, errors = await agent.run("AI space")
    assert result.startup_count == 0
    assert len(errors) > 0
