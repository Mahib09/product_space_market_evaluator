"""
demos/demo.py — Rich terminal demo for the Market Evaluator pipeline.

Usage:
    python demos/demo.py "AI sales automation"
    python demos/demo.py "AI sales automation" --cached
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

# Allow running from project root or from demos/ directory
_HERE = Path(__file__).parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich import box

from app.schemas import FinalResult, Verdict, Confidence
from app.core.persistence import load_latest
from app.core.orchestrator import run_pipeline

console = Console()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slug(product_space: str) -> str:
    """Convert product space to a safe filename slug."""
    return re.sub(r"[^a-z0-9]+", "-", product_space.lower()).strip("-")


def _score_bar(score: int, width: int = 20) -> str:
    filled = round(score / 10 * width)
    bar = "#" * filled + "-" * (width - filled)
    return f"[{'green' if score >= 6 else 'red'}]{bar}[/] {score}/10"


def _fmt_usd(amount: float | None) -> str:
    if amount is None:
        return "—"
    if amount >= 1_000_000_000:
        return f"${amount / 1_000_000_000:,.1f}B"
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:,.0f}M"
    return f"${amount:,.0f}"


def _confidence_color(confidence: Confidence | None) -> str:
    if confidence == Confidence.HIGH:
        return "green"
    if confidence == Confidence.MEDIUM:
        return "yellow"
    return "red"


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_result(result: FinalResult) -> None:
    j = result.judgement

    # --- Verdict banner ---
    if j and j.verdict == Verdict.GO:
        verdict_text = "[bold green]  GO  [/]"
        banner_style = "green"
    else:
        verdict_text = "[bold red] NO GO [/]"
        banner_style = "red"

    console.print()
    console.print(
        Panel(
            f"[bold]{result.product_space}[/]\n\n"
            f"Verdict: {verdict_text}\n"
            + (_score_bar(j.score) if j else "score unavailable"),
            title="[bold]Market Evaluation[/]",
            border_style=banner_style,
            expand=False,
            padding=(1, 4),
        )
    )

    # --- Breakdown panel ---
    if j:
        conf_color = _confidence_color(j.confidence)
        bd = j.breakdown
        breakdown_lines = (
            f"Growth score:      {_score_bar(bd.growth_score)}\n"
            f"Competition score: {_score_bar(bd.competition_score)}\n"
            f"White space:       {_score_bar(bd.white_space)}\n"
            f"\nConfidence: [{conf_color}]{(j.confidence or 'unknown').upper()}[/]\n"
            f"\n{j.summary}"
        )
        console.print(Panel(breakdown_lines, title="Score Breakdown", border_style="blue"))

    # --- Market sizing panel ---
    ms = result.market_scan
    if ms:
        market_lines = []
        if ms.tam_usd is not None:
            year = f" ({ms.tam_year})" if ms.tam_year else ""
            market_lines.append(f"TAM:   {_fmt_usd(ms.tam_usd)}{year}")
        if ms.sam_usd is not None:
            year = f" ({ms.sam_year})" if ms.sam_year else ""
            market_lines.append(f"SAM:   {_fmt_usd(ms.sam_usd)}{year}")
        if ms.cagr_5y_percent is not None:
            market_lines.append(f"CAGR:  {ms.cagr_5y_percent:.1f}% (5-year)")
        if ms.notes:
            market_lines.append(f"\n[dim]{ms.notes}[/]")
        if market_lines:
            console.print(Panel("\n".join(market_lines), title="Market Sizing", border_style="cyan"))

    # --- Incumbents table ---
    incumbents = result.incumbents
    if incumbents and incumbents.players:
        tbl = Table(box=box.SIMPLE_HEAD, show_lines=True, title="Incumbent Competitors")
        tbl.add_column("Name", style="bold")
        tbl.add_column("Offerings")
        tbl.add_column("Target Customers")
        for p in incumbents.players:
            tbl.add_row(p.name, p.offerings, p.target_customers)
        console.print(tbl)

    # --- Startups table ---
    startups = result.startups
    if startups and startups.companies:
        tbl = Table(box=box.SIMPLE_HEAD, show_lines=True, title="Notable Startups")
        tbl.add_column("Name", style="bold")
        tbl.add_column("Stage")
        tbl.add_column("Raised")
        tbl.add_column("Lead Investors")
        for c in startups.companies:
            investors = ", ".join(c.lead_investors) if c.lead_investors else "—"
            tbl.add_row(c.name, c.stage or "—", _fmt_usd(c.amount_usd), investors)
        if startups.total_capital_usd is not None:
            tbl.caption = f"Total known funding: {_fmt_usd(startups.total_capital_usd)}"
        console.print(tbl)

    # --- Errors ---
    if result.errors:
        console.print(f"\n[yellow]Warnings ({len(result.errors)}):[/]")
        for err in result.errors:
            console.print(f"  [dim]• [{err.agent}] {err.message}[/]")

    console.print()


# ---------------------------------------------------------------------------
# Cache lookup
# ---------------------------------------------------------------------------

async def _load_cached(product_space: str) -> FinalResult | None:
    """Try evaluations.db, then demos/sample_outputs/<slug>.json."""
    result = await load_latest(product_space)
    if result is not None:
        return result

    slug = _slug(product_space)
    sample_path = _HERE / "sample_outputs" / f"{slug}.json"
    if sample_path.exists():
        try:
            return FinalResult.model_validate_json(sample_path.read_text(encoding="utf-8"))
        except Exception as exc:
            console.print(f"[red]Failed to parse sample output: {exc}[/]")

    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def _main(product_space: str, cached: bool) -> int:
    if cached:
        console.print(f"[dim]Looking up cached result for:[/] [bold]{product_space}[/]")
        result = await _load_cached(product_space)
        if result is None:
            console.print(
                f"[red]No cached result found for '{product_space}'.[/]\n"
                "Run without --cached to evaluate live, or generate sample outputs first."
            )
            return 1
        console.print("[dim]Loaded from cache.[/]")
        render_result(result)
        return 0

    # Live evaluation with spinner
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Running pipeline (3–4 min)...", total=None)
        result = await run_pipeline(product_space)
        progress.update(task, description="Done.")

    render_result(result)
    return 0 if not result.errors or result.judgement is not None else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Market Evaluator — rich terminal demo"
    )
    parser.add_argument("product_space", help='e.g. "AI sales automation"')
    parser.add_argument(
        "--cached",
        action="store_true",
        help="Load from evaluations.db or sample_outputs/ instead of running the pipeline",
    )
    args = parser.parse_args()

    sys.exit(asyncio.run(_main(args.product_space, args.cached)))


if __name__ == "__main__":
    main()
