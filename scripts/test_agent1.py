import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.agent1 import run_agent1

PRODUCT_SPACE = "AI code review tool"


async def main() -> None:
    print(f"Running agent1 for: {PRODUCT_SPACE!r}")
    print("=" * 60)

    report, errors = await run_agent1(PRODUCT_SPACE)

    print(f"Players found: {len(report.players)}")
    print(f"Global sources: {len(report.sources)}")
    print("=" * 60)

    for i, p in enumerate(report.players, 1):
        print(f"\n  {i}. {p.name}")
        print(f"     Offerings:        {p.offerings}")
        print(f"     Target customers: {p.target_customers}")
        print(f"     Differentiators:  {p.differentiators}")
        print(f"     Sources:          {len(p.sources)}")

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
