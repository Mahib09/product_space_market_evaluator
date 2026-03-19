from unittest.mock import AsyncMock
import pytest
from app.agents.agent3 import MarketScanAgent
from app.schemas import Confidence, ErrorItem, MarketScan, Source


def _source(url="https://gartner.com/market-report", title="Gartner Market Report 2025", snippet="TAM estimated at $5.4B with CAGR of 14%"):
    return Source(url=url, title=title, snippet=snippet)


def _scan(tam=5_400_000_000.0, cagr=14.2):
    return MarketScan(tam_usd=tam, cagr_5y_percent=cagr, confidence=Confidence.HIGH)


async def test_happy_path():
    mock_search = AsyncMock(return_value=([_source()], []))
    mock_extract = AsyncMock(return_value=(_scan(), []))
    agent = MarketScanAgent(search_fn=mock_search, extract_fn=mock_extract)
    result, errors = await agent.run("AI sales automation")
    assert result.tam_usd == 5_400_000_000.0
    assert errors == []


async def test_followup_search_triggered_when_tam_and_cagr_both_null():
    no_data = MarketScan(tam_usd=None, cagr_5y_percent=None, confidence=Confidence.LOW)
    with_data = _scan()
    mock_search = AsyncMock(return_value=([_source()], []))
    # First extract returns null data → triggers follow-up search
    # Second extract (after follow-up) returns real data
    mock_extract = AsyncMock(side_effect=[(no_data, []), (with_data, [])])
    agent = MarketScanAgent(search_fn=mock_search, extract_fn=mock_extract)
    result, errors = await agent.run("AI sales automation")
    # Follow-up adds 1 more search call (5 initial + 1 follow-up = 6 total calls to search_fn)
    assert mock_search.call_count == 6
    assert mock_extract.call_count == 2


async def test_followup_skipped_when_tam_present():
    mock_search = AsyncMock(return_value=([_source()], []))
    mock_extract = AsyncMock(return_value=(_scan(), []))
    agent = MarketScanAgent(search_fn=mock_search, extract_fn=mock_extract)
    await agent.run("AI sales automation")
    assert mock_search.call_count == 5   # exactly 5 initial queries, no followup
    assert mock_extract.call_count == 1
