from __future__ import annotations

from app.schemas import (
    Breakdown,
    Confidence,
    IncumbentsReport,
    Judgement,
    MarketScan,
    Startups,
    Verdict,
)

import logging
logger = logging.getLogger(__name__)


def _clamp(value: float, lo: int = 0, hi: int = 10) -> int:
    return max(lo, min(hi, round(value)))


# ---------------------------------------------------------------------------
# Sub-score A: Growth (CAGR + TAM)
# ---------------------------------------------------------------------------

def _cagr_points(cagr: float | None) -> float:
    if cagr is None:
        return 2
    if cagr < 5:
        return 2
    if cagr < 10:
        return 4
    if cagr < 20:
        return 7
    return 9  # >= 20%


def _tam_points(tam: float | None) -> float:
    if tam is None:
        return 2
    if tam < 1_000_000_000:          # < $1B
        return 2
    if tam < 5_000_000_000:          # $1-5B
        return 4
    if tam < 20_000_000_000:         # $5-20B
        return 7
    return 9  # >= $20B


def _growth_score(market: MarketScan) -> int:
    raw = 0.6 * _cagr_points(market.cagr_5y_percent) + 0.4 * _tam_points(market.tam_usd)
    return _clamp(raw)


# ---------------------------------------------------------------------------
# Sub-score B: Competition (incumbents + startups + capital)
# ---------------------------------------------------------------------------

def _incumbent_points(count: int) -> float:
    if count <= 2:
        return 2
    if count <= 5:
        return 5
    if count <= 10:
        return 8
    return 9  # > 10


def _startup_points(count: int) -> float:
    if count <= 2:
        return 2
    if count <= 6:
        return 5
    if count <= 12:
        return 8
    return 9  # > 12


def _capital_points(total: float | None) -> float:
    if total is None:
        return 3
    if total < 50_000_000:           # < $50M
        return 4
    if total < 200_000_000:          # $50-200M
        return 6
    return 8  # >= $200M


def _competition_score(incumbents: IncumbentsReport, startups: Startups) -> int:
    inc = _incumbent_points(len(incumbents.players))
    stp = _startup_points(startups.startup_count or 0)
    cap = _capital_points(startups.total_capital_usd)
    raw = 0.4 * inc + 0.4 * stp + 0.2 * cap
    return _clamp(raw)


# ---------------------------------------------------------------------------
# Final score + verdict
# ---------------------------------------------------------------------------

def run_agent4(
    incumbents: IncumbentsReport,
    startups: Startups,
    market: MarketScan,
) -> Judgement:
    """Compute a 1-10 score and GO/NO_GO verdict. Pure computation, no API calls."""

    growth = _growth_score(market)
    competition = _competition_score(incumbents, startups)

    # White space: growth minus competition, mapped to 1-10
    white_space_raw = growth - competition          # range ~ -10 to +10
    score_raw = 5 + (white_space_raw / 2)           # +10 → 10, -10 → 0
    score = _clamp(score_raw, lo=1, hi=10)

    white_space_metric = 5+(white_space_raw /2)
    white_space = _clamp(white_space_metric,0,10)

    # --- Edge case: insufficient market data ---
    low_data = (
        market.confidence == Confidence.LOW
        and market.tam_usd is None
        and market.cagr_5y_percent is None
    )
    if low_data and score > 5:
        score = 5

    # --- Edge case: missing competition data ---
    no_competition = len(incumbents.players) == 0 and (startups.startup_count or 0) == 0
    if no_competition and score > 6:
        # Don't assume low competition; cap conservatively unless market is strong
        if not (market.tam_usd is not None and market.cagr_5y_percent is not None):
            score = 6

    verdict = Verdict.GO if score >= 6 else Verdict.NO_GO
    confidence = market.confidence

    # --- Summary ---
    parts: list[str] = []

    parts.append(f"{len(incumbents.players)} incumbents identified")
    sc = startups.startup_count or 0
    funding_str = (
        f"${startups.total_capital_usd / 1_000_000:,.0f}M known funding"
        if startups.total_capital_usd
        else "funding data limited"
    )
    parts.append(f"{sc} startups ({funding_str})")

    if market.tam_usd is not None:
        tam_b = market.tam_usd / 1_000_000_000
        parts.append(f"TAM ~${tam_b:,.1f}B")
    if market.cagr_5y_percent is not None:
        parts.append(f"CAGR ~{market.cagr_5y_percent:.1f}%")

    if low_data:
        parts.append("Insufficient verified market data")
    elif verdict == Verdict.GO:
        parts.append("Market opportunity supports entry")
    else:
        parts.append("Competitive density or weak growth limits opportunity")

    summary = ". ".join(parts) + "."
    logger.info(
    "[Agent4] SCORE_DONE",
)

    return Judgement(
        verdict=verdict,
        score=score,
        breakdown=Breakdown(
            growth_score=growth,
            competition_score=competition,
            white_space=white_space,
        ),
        summary=summary,
        confidence=confidence,
    )
