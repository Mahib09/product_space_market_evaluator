import pytest
from app.agents.agent4 import JudgementAgent
from app.schemas import Confidence, IncumbentsReport, MarketScan, Player, Startups, Company, Verdict


def _market(tam=None, cagr=None, confidence=Confidence.MEDIUM):
    return MarketScan(tam_usd=tam, cagr_5y_percent=cagr, confidence=confidence)


def _incumbents(n=0):
    players = [Player(name=f"Co{i}", offerings="x", target_customers="y") for i in range(n)]
    return IncumbentsReport(players=players, sources=[])


def _startups(n=0, capital=None):
    companies = [Company(name=f"S{i}", stage="Seed") for i in range(n)]
    return Startups(companies=companies, startup_count=n, total_capital_usd=capital)


# --- CAGR point thresholds ---

def test_cagr_below_5_gives_low_score():
    j = JudgementAgent().run(_incumbents(3), _startups(3), _market(tam=5e9, cagr=3.0))
    assert j.breakdown.growth_score < 6

def test_cagr_10_to_20_gives_mid_score():
    j = JudgementAgent().run(_incumbents(3), _startups(3), _market(tam=5e9, cagr=15.0))
    assert j.breakdown.growth_score >= 6

def test_cagr_above_20_gives_high_score():
    j = JudgementAgent().run(_incumbents(3), _startups(3), _market(tam=5e9, cagr=25.0))
    assert j.breakdown.growth_score >= 7

# --- TAM point thresholds ---

def test_tam_below_1b_gives_low_growth():
    j = JudgementAgent().run(_incumbents(0), _startups(0), _market(tam=500_000_000, cagr=15.0))
    assert j.breakdown.growth_score < 7

def test_tam_above_20b_gives_high_growth():
    j = JudgementAgent().run(_incumbents(0), _startups(0), _market(tam=25_000_000_000, cagr=15.0))
    assert j.breakdown.growth_score >= 8

# --- Verdict boundary ---

def test_score_matches_verdict():
    j = JudgementAgent().run(_incumbents(1), _startups(1), _market(tam=5e9, cagr=12.0))
    assert (j.verdict == Verdict.GO) == (j.score >= 6)

def test_high_competition_gives_no_go():
    j = JudgementAgent().run(_incumbents(8), _startups(10, capital=500_000_000), _market(tam=500_000_000, cagr=3.0))
    assert j.verdict == Verdict.NO_GO
    assert j.score < 6

# --- Edge case: LOW confidence cap ---

def test_low_data_caps_score_at_5():
    j = JudgementAgent().run(
        _incumbents(0), _startups(0),
        _market(tam=None, cagr=None, confidence=Confidence.LOW)
    )
    assert j.score <= 5

# --- Edge case: zero competition cap ---

def test_zero_competition_without_market_data_caps_at_6():
    j = JudgementAgent().run(
        _incumbents(0), _startups(0),
        _market(tam=None, cagr=None, confidence=Confidence.MEDIUM)
    )
    assert j.score <= 6

def test_zero_competition_with_strong_market_can_exceed_6():
    j = JudgementAgent().run(
        _incumbents(0), _startups(0),
        _market(tam=25_000_000_000, cagr=25.0, confidence=Confidence.HIGH)
    )
    # Both TAM and CAGR present — cap does NOT apply
    assert j.score > 6
