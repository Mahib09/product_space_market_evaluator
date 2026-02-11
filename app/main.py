from fastapi import FastAPI

from app.schemas import (
    AnalyzeRequest,
    Evidence,
    FullReport,
    Incumbent,
    IncumbentsResult,
    JudgementResult,
    MarketMetric,
    MarketScanResult,
    StartupFundingEvent,
    StartupsResult,
)

app = FastAPI(title="Product Space Market Evaluator")


@app.post("/analyze", response_model=FullReport)
async def analyze(request: AnalyzeRequest) -> FullReport:
    dummy_evidence = Evidence(
        source="demo", snippet="placeholder data", relevance_score=0.9
    )

    return FullReport(
        company_name=request.company_name,
        industry=request.industry,
        region=request.region,
        incumbents=IncumbentsResult(
            incumbents=[
                Incumbent(
                    name="Acme Corp",
                    market_share=35.0,
                    strengths=["brand recognition", "distribution network"],
                    weaknesses=["slow innovation"],
                    evidence=[dummy_evidence],
                )
            ]
        ),
        startups=StartupsResult(
            funding_events=[
                StartupFundingEvent(
                    startup_name="NovaTech",
                    stage="Series A",
                    amount_usd=12_000_000,
                    date="2025-06-15",
                    investors=["Sequoia", "a16z"],
                    evidence=[dummy_evidence],
                )
            ]
        ),
        market_scan=MarketScanResult(
            metrics=[
                MarketMetric(
                    metric_name="TAM",
                    value="$4.2B",
                    year=2025,
                    evidence=[dummy_evidence],
                )
            ],
            trends=["AI-driven automation", "vertical SaaS consolidation"],
        ),
        judgement=JudgementResult(
            opportunity_score=7.5,
            summary="Moderate opportunity with strong tailwinds in AI adoption.",
            risks=["regulatory uncertainty", "incumbent response"],
            recommendations=["target underserved SMB segment", "build API-first"],
        ),
    )
