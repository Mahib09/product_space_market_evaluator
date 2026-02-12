import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.agent3 import run_agent3

PRODUCT_SPACE = "AI code review tool"


async def main() -> None:
    print(f"Running agent3 for: {PRODUCT_SPACE!r}")
    print("=" * 60)

    report, errors = await run_agent3(PRODUCT_SPACE)

    print(f"TAM (USD):       {report.tam_usd}")
    print(f"TAM year:        {report.tam_year}")
    print(f"SAM (USD):       {report.sam_usd}")
    print(f"SAM year:        {report.sam_year}")
    print(f"CAGR 5y (%):     {report.cagr_5y_percent}")
    print(f"Confidence:      {report.confidence}")
    print(f"Notes:           {report.notes}")
    print(f"Global sources:  {len(report.sources)}")
    print("=" * 60)

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
