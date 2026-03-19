"""
Full pipeline integration test.
Skipped automatically when no real OpenAI API key is present.
Run manually: OPENAI_API_KEY=sk-... pytest tests/integration/ -v
"""
import os
import pytest
from app.core.orchestrator import run_pipeline
from app.schemas import FinalResult

pytestmark = pytest.mark.skipif(
    os.getenv("OPENAI_API_KEY", "test-key") == "test-key",
    reason="real OPENAI_API_KEY required for integration tests",
)


async def test_full_pipeline_returns_valid_final_result():
    result = await run_pipeline("AI sales automation")
    assert isinstance(result, FinalResult)
    assert result.product_space == "AI sales automation"
    assert result.request_id != ""
    # At least one agent should return non-empty data
    has_data = (
        (result.incumbents and result.incumbents.players)
        or (result.startups and result.startups.startup_count)
        or (result.market_scan and result.market_scan.tam_usd)
    )
    assert has_data, "Expected at least one agent to return data"
    assert result.judgement is not None
    assert 1 <= result.judgement.score <= 10
