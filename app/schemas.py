from __future__ import annotations

import datetime
from enum import Enum

from typing import Annotated, Any

from pydantic import BaseModel, Field, HttpUrl


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Verdict(str, Enum):
    GO = "GO"
    NO_GO = "NO_GO"


class AgentName(str, Enum):
    AGENT1 = "agent1"
    AGENT2 = "agent2"
    AGENT3 = "agent3"

# --- Evidence ---

class Source(BaseModel):
    url: HttpUrl
    title: str
    snippet: str

# --- Incumbents ---

class Player(BaseModel):
    name: str
    offerings: str
    target_customers: str
    differentiators: str | None = None
    sources: list[Source] = Field(default_factory=list)


class Incumbents(BaseModel):
    players: list[Player] = Field(default_factory=list)


class IncumbentsReport(BaseModel):
    players: list[Player] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)

# --- Startups ---

class Company(BaseModel):
    name: str
    stage: str
    amount_usd: float | None = None
    date: datetime.date | None = None
    lead_investors: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)


class Startups(BaseModel):
    companies: list[Company] = Field(default_factory=list)
    total_capital_usd: float | None = None
    startup_count: int | None = None
    top_investors: list[str] = Field(default_factory=list)
    velocity_note: str = ""
    sources: list[Source] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        if self.startup_count is None:
            self.startup_count = len(self.companies)

# --- Market scan ---

class MarketScan(BaseModel):
    tam_usd: float | None = None
    tam_year: int | None = None
    sam_usd: float | None = None
    sam_year: int | None = None
    cagr_5y_percent: float | None = None
    confidence: Confidence | None = None
    notes: str = ""
    sources: list[Source] = Field(default_factory=list)

# --- Judgement ---
Score10 = Annotated[int, Field(ge=0, le=10)]

class Breakdown(BaseModel):
    growth_score: Score10
    competition_score: Score10
    white_space: Score10


class Judgement(BaseModel):
    verdict: Verdict
    score: Score10
    breakdown: Breakdown
    summary: str = ""
    confidence: Confidence | None = None

# --- Errors ---

class ErrorItem(BaseModel):
    agent: str
    message: str

# --- Final API result ---

class FinalResult(BaseModel):
    request_id: str
    product_space: str
    incumbents: Incumbents | None = None
    startups: Startups | None = None
    market_scan: MarketScan | None = None
    judgement: Judgement | None = None
    errors: list[ErrorItem] = Field(default_factory=list)
