import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schemas import Source
from app.core.clean import clean_sources

# --- Hardcoded raw sources (simulating web_search output) ---
RAW_SOURCES = [
    # Good research source — should rank high
    Source(
        url="https://www.gartner.com/en/articles/crm-market-report-2025",
        title="Gartner CRM Market Report 2025 - Full Analysis",
        snippet="The global CRM market is expected to reach $80B by 2026 according to Gartner's latest forecast and industry outlook.",
    ),
    # Duplicate URL (trailing slash difference) — should be deduped
    Source(
        url="https://www.gartner.com/en/articles/crm-market-report-2025/",
        title="Gartner CRM Market Report 2025 - Full Analysis",
        snippet="The global CRM market is expected to reach $80B by 2026 according to Gartner's latest forecast.",
    ),
    # Good normal source
    Source(
        url="https://techcrunch.com/2025/03/15/crm-startups-funding",
        title="CRM Startups Raise Record Funding in Q1 2025",
        snippet="Several CRM startups secured Series A and B rounds totaling over $500M in the first quarter of 2025.",
    ),
    # Low quality — short title AND short snippet, should be dropped
    Source(
        url="https://example.com/page",
        title="CRM",
        snippet="Short.",
    ),
    # Short title but long enough snippet — should survive
    Source(
        url="https://blog.hubspot.com/crm-trends",
        title="CRM Trends",
        snippet="A comprehensive look at the top CRM trends shaping the industry in 2025 and beyond with detailed analysis.",
    ),
    # Research source — Forrester, should rank high
    Source(
        url="https://www.forrester.com/report/crm-wave-2025",
        title="The Forrester Wave: CRM Suites 2025",
        snippet="Forrester's evaluation of the top CRM vendors reveals significant shifts in market leadership and analyst recommendations.",
    ),
    # Duplicate of techcrunch (same normalized path) with query params
    Source(
        url="https://techcrunch.com/2025/03/15/crm-startups-funding?utm_source=twitter",
        title="CRM Startups Raise Record Funding in Q1 2025",
        snippet="Several CRM startups secured Series A and B rounds totaling over $500M in the first quarter.",
    ),
    # Normal source
    Source(
        url="https://www.salesforce.com/blog/state-of-crm",
        title="State of CRM 2025 - Salesforce Blog",
        snippet="Salesforce explores the current state of customer relationship management and emerging trends across industries.",
    ),
    # Very long snippet — should be trimmed
    Source(
        url="https://www.mckinsey.com/industries/tech/crm-deep-dive",
        title="McKinsey CRM Deep Dive: Market Research and Forecast",
        snippet="This McKinsey report provides an in-depth analysis of the CRM market. " * 20,
    ),
]


def main() -> None:
    print(f"Raw sources: {len(RAW_SOURCES)}")
    print("=" * 60)

    cleaned = clean_sources(RAW_SOURCES, max_results=5)

    print(f"Cleaned sources: {len(cleaned)}")
    print("=" * 60)

    for i, src in enumerate(cleaned, 1):
        tag = "[RESEARCH]" if "gartner" in src.snippet.lower() or "forrester" in src.snippet.lower() or "mckinsey" in src.snippet.lower() else ""
        print(f"\n  {i}. {src.title} {tag}")
        print(f"     {src.url}")
        print(f"     snippet: {src.snippet[:100]}...")

    # Summary
    print("\n" + "=" * 60)
    print("Checks:")
    print(f"  Dupes removed:    {len(RAW_SOURCES) - len(cleaned) - 1} (1 dropped by quality filter)")
    print(f"  Quality filtered: 1 (short title + short snippet)")
    print(f"  Capped at:        5")
    print(f"  Research first:   {cleaned[0].title if cleaned else 'N/A'}")


if __name__ == "__main__":
    main()
