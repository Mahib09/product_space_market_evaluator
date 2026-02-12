import asyncio
import logging
import random

from openai import AsyncOpenAI
from pydantic import ValidationError

from app.config import OPENAI_MODEL_SEARCH, OPENAI_API_KEY
from app.schemas import ErrorItem, Source

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

_MAX_RETRIES = 1

# In-memory cache: query → (sources, errors)
# Avoids re-searching the same query within a pipeline run.
_cache: dict[str, tuple[list[Source], list[ErrorItem]]] = {}


def clear_search_cache() -> None:
    """Clear the search cache (call between pipeline runs if needed)."""
    _cache.clear()


def _extract_sources_from_response(response) -> list[Source]:
    sources: list[Source] = []

    for item in getattr(response, "output", []):
        if getattr(item, "type", None) != "web_search_call":
            continue

        action = getattr(item, "action", None)
        for src in getattr(action, "sources", []) or []:
            try:
                sources.append(
                    Source(
                        url=str(getattr(src, "url", "")),
                        title=getattr(src, "title", "") or "",
                        snippet=getattr(src, "snippet", "") or "",
                    )
                )
            except ValidationError:
                logger.warning("Skipping invalid source: %s", src)

    return sources


async def web_search(
    query: str,
    max_results: int = 10,
) -> tuple[list[Source], list[ErrorItem]]:
    """Search the web via OpenAI Responses API with the web_search tool.

    Returns raw (title, url, snippet) results only — no cleaning or dedup.

    Raises:
        ValueError: If query is empty.
    """
    if not query or not query.strip():
        raise ValueError("query must be a non-empty string")

    # Check cache first
    cache_key = f"{query.strip().lower()}|{max_results}"
    if cache_key in _cache:
        logger.debug("Cache hit for query: %s", query[:60])
        return _cache[cache_key]

    errors: list[ErrorItem] = []

    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = await client.responses.create(
                model=OPENAI_MODEL_SEARCH,
                tools=[{"type": "web_search"}],
                include=["web_search_call.action.sources"],
                input=f"Search the web for: {query}",
            )

            sources = _extract_sources_from_response(response)
            result = sources[:max_results], errors
            _cache[cache_key] = result
            return result

        except Exception as exc:
            logger.error(
                "web_search failed (attempt %d/%d): %s",
                attempt + 1,
                _MAX_RETRIES + 1,
                exc,
            )
            if attempt == _MAX_RETRIES:
                errors.append(
                    ErrorItem(
                        agent="search",
                        message=f"web_search failed after {_MAX_RETRIES + 1} attempts: {exc}",
                    )
                )
                return [], errors

        # Jittered delay before retry
        jitter = random.uniform(0.5, 1.5)
        logger.info("Retrying web_search in %.1fs...", jitter)
        await asyncio.sleep(jitter)

    return [], errors
