from __future__ import annotations

from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    company_name: str
    industry: str
    region: str = "global"


class Evidence(BaseModel):
    source: str
    snippet: str
    relevance_score: float


class Incumbent(BaseModel):
    name: str
    market_share: float | None = None
    strengths: list[str] = []
    weaknesses: list[str] = []
    evidence: list[Evidence] = []


class StartupFundingEvent(BaseModel):
    startup_name: str
    stage: str
    amount_usd: float | None = None
    date: str | None = None
    investors: list[str] = []
    evidence: list[Evidence] = []


class MarketMetric(BaseModel):
    metric_name: str
    value: str
    year: int | None = None
    evidence: list[Evidence] = []


class IncumbentsResult(BaseModel):
    incumbents: list[Incumbent] = []


class StartupsResult(BaseModel):
    funding_events: list[StartupFundingEvent] = []


class MarketScanResult(BaseModel):
    metrics: list[MarketMetric] = []
    trends: list[str] = []


class JudgementResult(BaseModel):
    opportunity_score: float
    summary: str
    risks: list[str] = []
    recommendations: list[str] = []


class FullReport(BaseModel):
    company_name: str
    industry: str
    region: str
    incumbents: IncumbentsResult
    startups: StartupsResult
    market_scan: MarketScanResult
    judgement: JudgementResult
