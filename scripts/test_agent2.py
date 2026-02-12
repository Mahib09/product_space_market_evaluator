import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.agent2 import run_agent2

PRODUCT_SPACE = "AI code review tool"


async def main() -> None:
    print(f"Running agent2 for: {PRODUCT_SPACE!r}")
    print("=" * 60)

    report, errors = await run_agent2(PRODUCT_SPACE)

    print(f"Companies found: {report.startup_count}")
    print(f"Total capital (USD): {report.total_capital_usd}")
    print(f"Top investors: {report.top_investors}")
    print(f"Velocity note: {report.velocity_note}")
    print(f"Global sources: {len(report.sources)}")
    print("=" * 60)

    for i, c in enumerate(report.companies, 1):
        print(f"\n  {i}. {c.name}")
        print(f"     Stage:          {c.stage}")
        print(f"     Amount (USD):   {c.amount_usd}")
        print(f"     Date:           {c.date}")
        print(f"     Lead investors: {c.lead_investors}")
        print(f"     Sources:        {len(c.sources)}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for err in errors:
            print(f"  - [{err.agent}] {err.message}")
    else:
        print("\nNo errors.")

    print("\n" + "=" * 60)
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
