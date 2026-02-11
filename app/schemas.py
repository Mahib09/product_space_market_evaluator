from datetime import date

from enum import Enum

from pydantic import BaseModel, Field, HttpUrl
from typing import Annotated


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


class Source(BaseModel):
    url: HttpUrl
    title: str


class Player(BaseModel):
    name: str
    offerings: str
    target_customers: str
    differentiators: str | None = None
    sources: list[Source] = Field(default_factory=list)


class Incumbents(BaseModel):
    players: list[Player] = Field(default_factory=list)


class Company(BaseModel):
    name: str
    stage: str
    amount_usd: float | None = None
    date: date | None = None
    lead_investors: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)


class Startups(BaseModel):
    companies: list[Company] = Field(default_factory=list)
    total_capital_usd: float | None = None
    startup_count: int | None = None
    top_investors: list[str] = Field(default_factory=list)
    velocity_note: str = ""
    sources: list[Source] = Field(default_factory=list)


class MarketScan(BaseModel):
    tam_usd: float | None = None
    tam_year: int | None = None
    sam_usd: float | None = None
    sam_year: int | None = None
    cagr_5y_percent: float | None = None
    confidence: Confidence | None = None
    notes: str = ""
    sources: list[Source] = Field(default_factory=list)


class Breakdown(BaseModel):
    growth_score: Annotated[int, Field(ge=0, le=100)]
    competition_score: Annotated[int, Field(ge=0, le=100)]
    white_space: Annotated[int, Field(ge=0, le=100)]


class Judgement(BaseModel):
    verdict: Verdict
    score: Annotated[int, Field(ge=0, le=100)]
    breakdown: Breakdown
    summary: str = ""
    confidence: Confidence | None = None


class Error(BaseModel):
    agent: AgentName
    message: str


class FinalResult(BaseModel):
    product_space: str
    incumbents: Incumbents | None = None
    startups: Startups | None = None
    market_scan: MarketScan | None = None
    judgement: Judgement | None = None
    errors: list[Error] = Field(default_factory=list)
