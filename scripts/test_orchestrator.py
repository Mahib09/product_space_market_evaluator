import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.orchestrator import run_pipeline

PRODUCT_SPACE = "AI code review tool"


async def main() -> None:
    print(f"Running pipeline for: {PRODUCT_SPACE!r}")
    print("=" * 60)

    result = await run_pipeline(PRODUCT_SPACE)

    print(f"Request ID:      {result.request_id}")
    print(f"Product space:   {result.product_space}")
    print("=" * 60)

    # --- Incumbents ---
    inc = result.incumbents
    if inc:
        print(f"\nIncumbents: {len(inc.players)} players, {len(inc.sources)} sources")
        for i, p in enumerate(inc.players, 1):
            print(f"  {i}. {p.name} — {p.offerings}")
    else:
        print("\nIncumbents: None (failed)")

    # --- Startups ---
    st = result.startups
    if st:
        print(f"\nStartups: {st.startup_count} companies")
        print(f"  Total capital:  {st.total_capital_usd}")
        print(f"  Top investors:  {st.top_investors}")
        print(f"  Velocity:       {st.velocity_note}")
        for i, c in enumerate(st.companies, 1):
            print(f"  {i}. {c.name} ({c.stage}) — ${c.amount_usd} — {c.lead_investors}")
    else:
        print("\nStartups: None (failed)")

    # --- Market Scan ---
    ms = result.market_scan
    if ms:
        print(f"\nMarket Scan:")
        print(f"  TAM (USD):     {ms.tam_usd}")
        print(f"  TAM year:      {ms.tam_year}")
        print(f"  SAM (USD):     {ms.sam_usd}")
        print(f"  CAGR 5y (%):   {ms.cagr_5y_percent}")
        print(f"  Confidence:    {ms.confidence}")
        print(f"  Notes:         {ms.notes}")
        print(f"  Sources:       {len(ms.sources)}")
    else:
        print("\nMarket Scan: None (failed)")

    # --- Judgement ---
    j = result.judgement
    if j:
        print(f"\nJudgement:")
        print(f"  Verdict:       {j.verdict.value}")
        print(f"  Score:         {j.score}")
        print(f"  Growth:        {j.breakdown.growth_score}")
        print(f"  Competition:   {j.breakdown.competition_score}")
        print(f"  White space:   {j.breakdown.white_space}")
        print(f"  Confidence:    {j.confidence}")
        print(f"  Summary:       {j.summary}")
    else:
        print("\nJudgement: None (failed)")

    # --- Errors ---
    if result.errors:
        print(f"\nErrors ({len(result.errors)}):")
        for err in result.errors:
            print(f"  - [{err.agent}] {err.message}")
    else:
        print("\nNo errors.")

    print("\n" + "=" * 60)
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
