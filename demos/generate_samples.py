"""
demos/generate_samples.py — Generate real sample outputs using the live pipeline.

Requires a valid OPENAI_API_KEY in .env.

Usage:
    python demos/generate_samples.py

Writes JSON files to demos/sample_outputs/<slug>.json for use with
    python demos/demo.py "<product space>" --cached
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.orchestrator import run_pipeline

_OUTPUT_DIR = Path(__file__).parent / "sample_outputs"

_PRODUCT_SPACES = [
    "AI sales automation",
    "vertical SaaS for restaurants",
    "developer observability tools",
]


def _slug(product_space: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", product_space.lower()).strip("-")


async def _generate_one(product_space: str) -> None:
    print(f"\n[{product_space}] Running pipeline...")
    result = await run_pipeline(product_space)
    slug = _slug(product_space)
    out_path = _OUTPUT_DIR / f"{slug}.json"
    out_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    verdict = result.judgement.verdict if result.judgement else "unknown"
    score = result.judgement.score if result.judgement else "—"
    print(f"[{product_space}] Done — {verdict} (score {score}) → {out_path.name}")


async def main() -> None:
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for ps in _PRODUCT_SPACES:
        await _generate_one(ps)
    print("\nAll samples generated.")


if __name__ == "__main__":
    asyncio.run(main())
