import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schemas import Incumbents, MarketScan, Source
from app.core.extract import extract_structured

# --- Hardcoded sources (simulating cleaned web_search output) ---
CRM_SOURCES = [
    Source(
        url="https://www.gartner.com/en/articles/crm-market-report-2025",
        title="Gartner CRM Market Report 2025 - Full Analysis",
        snippet="The global CRM market is expected to reach $80B by 2026, growing at a 12% CAGR. Salesforce leads with 23% share, followed by Microsoft Dynamics (5.8%) and HubSpot (4.1%).",
    ),
    Source(
        url="https://www.forrester.com/report/crm-wave-2025",
        title="The Forrester Wave: CRM Suites 2025",
        snippet="Salesforce remains the leader in CRM suites with its broad platform and AI capabilities. Microsoft and Oracle are strong performers. HubSpot targets SMBs with freemium model.",
    ),
    Source(
        url="https://techcrunch.com/2025/03/15/crm-startups-funding",
        title="CRM Startups Raise Record Funding in Q1 2025",
        snippet="Attio raised $30M Series B for modern CRM. Folk CRM secured $15M Series A targeting European SMBs. Clay raised $40M for data enrichment layer on top of CRMs.",
    ),
    Source(
        url="https://www.salesforce.com/blog/state-of-crm",
        title="State of CRM 2025 - Salesforce Blog",
        snippet="Salesforce offers Sales Cloud, Service Cloud, and Marketing Cloud. It differentiates through its AppExchange ecosystem with 5000+ integrations and Einstein AI.",
    ),
    Source(
        url="https://www.mckinsey.com/industries/tech/crm-deep-dive",
        title="McKinsey CRM Deep Dive: Market Forecast",
        snippet="The CRM TAM stood at $69B in 2024 and is forecast to reach $96B by 2028. SAM for cloud CRM is roughly $45B. Growth is driven by AI-powered automation and vertical-specific solutions.",
    ),
]

PRODUCT_SPACE = "CRM Software"


async def test_incumbents() -> None:
    print("=" * 60)
    print("TEST 1: Extract Incumbents")
    print("=" * 60)

    result, errors = await extract_structured(
        agent="agent1",
        schema_model=Incumbents,
        product_space=PRODUCT_SPACE,
        sources=CRM_SOURCES,
        instructions="Identify the major incumbent players in this product space. For each, extract their name, offerings, target customers, and differentiators.",
    )

    if result:
        print(f"Players found: {len(result.players)}")
        for p in result.players:
            print(f"\n  Name: {p.name}")
            print(f"  Offerings: {p.offerings}")
            print(f"  Target customers: {p.target_customers}")
            print(f"  Differentiators: {p.differentiators}")
            print(f"  Sources: {len(p.sources)}")
    else:
        print("No result returned.")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for err in errors:
            print(f"  - [{err.agent}] {err.message}")


async def test_market_scan() -> None:
    print("\n" + "=" * 60)
    print("TEST 2: Extract MarketScan")
    print("=" * 60)

    result, errors = await extract_structured(
        agent="agent3",
        schema_model=MarketScan,
        product_space=PRODUCT_SPACE,
        sources=CRM_SOURCES,
        instructions="Extract market sizing data: TAM, SAM, CAGR, and confidence level. Only use figures explicitly stated in the evidence.",
    )

    if result:
        print(f"  TAM:  ${result.tam_usd:,.0f}" if result.tam_usd else "  TAM:  N/A")
        print(f"  Year: {result.tam_year}" if result.tam_year else "  Year: N/A")
        print(f"  SAM:  ${result.sam_usd:,.0f}" if result.sam_usd else "  SAM:  N/A")
        print(f"  CAGR: {result.cagr_5y_percent}%" if result.cagr_5y_percent else "  CAGR: N/A")
        print(f"  Confidence: {result.confidence}")
        print(f"  Notes: {result.notes}")
        print(f"  Sources: {len(result.sources)}")
    else:
        print("No result returned.")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for err in errors:
            print(f"  - [{err.agent}] {err.message}")


async def test_empty_sources() -> None:
    print("\n" + "=" * 60)
    print("TEST 3: Empty sources (should return None + error)")
    print("=" * 60)

    result, errors = await extract_structured(
        agent="agent1",
        schema_model=Incumbents,
        product_space=PRODUCT_SPACE,
        sources=[],
        instructions="Extract incumbents.",
    )

    print(f"  Result: {result}")
    print(f"  Errors ({len(errors)}):")
    for err in errors:
        print(f"    - [{err.agent}] {err.message}")


async def main() -> None:
    await test_empty_sources()
    await test_incumbents()
    await test_market_scan()

    print("\n" + "=" * 60)
    print("All tests complete.")


if __name__ == "__main__":
    asyncio.run(main())
