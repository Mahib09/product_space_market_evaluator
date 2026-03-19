import pytest
import app.core.persistence as persistence_module
from app.core.persistence import save_result, load_latest
from app.schemas import (
    Breakdown, Confidence, FinalResult, IncumbentsReport,
    Judgement, MarketScan, Startups, Verdict,
)


def _result(product_space: str = "test space") -> FinalResult:
    return FinalResult(
        request_id="abc123",
        product_space=product_space,
        incumbents=IncumbentsReport(players=[], sources=[]),
        startups=Startups(companies=[], startup_count=0),
        market_scan=MarketScan(confidence=Confidence.LOW),
        judgement=Judgement(
            verdict=Verdict.GO,
            score=7,
            breakdown=Breakdown(growth_score=7, competition_score=4, white_space=6),
            summary="Test summary.",
        ),
        errors=[],
    )


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Redirect evaluations.db to a temp file so tests never touch the real DB."""
    monkeypatch.setattr(persistence_module, "_DB_PATH", str(tmp_path / "test_evaluations.db"))


async def test_load_latest_returns_none_when_empty():
    result = await load_latest("no such product space xyz")
    assert result is None


async def test_save_and_load_roundtrip():
    r = _result("test save load roundtrip abc123")
    await save_result(r)
    loaded = await load_latest("test save load roundtrip abc123")
    assert loaded is not None
    assert loaded.request_id == "abc123"
    assert loaded.judgement.score == 7


async def test_normalisation_case_insensitive():
    r = _result("  AI Sales Automation  ")
    await save_result(r)
    loaded = await load_latest("ai sales automation")
    assert loaded is not None
