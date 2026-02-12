import asyncio

from app.core.search import web_search

QUERIES = [
    "AI code review tools market size 2025",
    "top CRM startups Series A funding 2024",
]


async def main() -> None:
    for query in QUERIES:
        print(f"\n{'=' * 60}")
        print(f"Query: {query}")
        print("=" * 60)

        sources, errors = await web_search(query, max_results=10)

        print(f"Sources returned: {len(sources)}")

        for i, src in enumerate(sources[:3], 1):
            print(f"  {i}. {src.title}")
            print(f"     {src.url}")

        if errors:
            print(f"Errors ({len(errors)}):")
            for err in errors:
                print(f"  - [{err.agent}] {err.message}")


if __name__ == "__main__":
    asyncio.run(main())
