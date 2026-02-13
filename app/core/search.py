import asyncio
import logging
import os
import random

from openai import AsyncOpenAI
from pydantic import ValidationError

from app.config import OPENAI_MODEL_SEARCH, OPENAI_API_KEY
from app.schemas import ErrorItem, Source

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

_MAX_RETRIES = 1

_DEBUG_SHAPE = os.environ.get("DEBUG_WEB_SEARCH_SHAPE", "").lower() in (
    "1", "true", "yes",
)
_shape_logged = False  # only dump once per process

# In-memory cache: query → (sources, errors)
# Avoids re-searching the same query within a pipeline run.
_cache: dict[str, tuple[list[Source], list[ErrorItem]]] = {}


def clear_search_cache() -> None:
    """Clear the search cache (call between pipeline runs if needed)."""
    _cache.clear()


def _resolve_path(obj, path: str):
    """Walk a dotted path (e.g. 'metadata.title') via attribute then dict access."""
    current = obj
    for segment in path.split("."):
        if current is None:
            return None
        val = getattr(current, segment, None)
        if val is None and isinstance(current, dict):
            val = current.get(segment)
        current = val
    return current


def _get_field(obj, *candidates: str) -> str:
    """Return the first non-empty string value found among candidate field paths.

    Supports dotted paths like 'metadata.title'.
    Handles both attribute access (SDK objects) and dict access (raw JSON).
    """
    for path in candidates:
        val = _resolve_path(obj, path)
        if val and isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _extract_sources_from_response(response) -> list[Source]:
    global _shape_logged
    sources: list[Source] = []

    for item in getattr(response, "output", []):
        if getattr(item, "type", None) != "web_search_call":
            continue

        action = getattr(item, "action", None)
        raw_sources = getattr(action, "sources", []) or []

        # --- Debug: dump first source object shape ---
        if _DEBUG_SHAPE and not _shape_logged and raw_sources:
            first = raw_sources[0]
            logger.info("[DEBUG_SHAPE] type=%s", type(first).__name__)
            logger.info("[DEBUG_SHAPE] repr=%s", repr(first)[:1000])
            if hasattr(first, "__dict__"):
                logger.info("[DEBUG_SHAPE] __dict__=%s", first.__dict__)
            elif isinstance(first, dict):
                logger.info("[DEBUG_SHAPE] keys=%s", list(first.keys()))
            _shape_logged = True

        for src in raw_sources:
            try:
                url = _get_field(src, "url", "link", "href")
                title = _get_field(
                    src, "title", "name", "display_name",
                    "metadata.title", "page.title",
                )
                snippet = _get_field(
                    src, "snippet", "text", "description", "content", "summary",
                    "metadata.snippet", "metadata.description",
                    "metadata.summary", "content.text",
                )

                # Guard: if snippet is just the URL repeated, treat as empty
                if snippet and snippet.strip().rstrip("/") == url.strip().rstrip("/"):
                    snippet = ""

                if not url:
                    continue

                sources.append(Source(url=url, title=title, snippet=snippet))
            except ValidationError:
                logger.warning("Skipping invalid source: %s", repr(src)[:200])

    # --- Snippet coverage ---
    if sources:
        with_title = sum(1 for s in sources if s.title)
        with_snippet = sum(1 for s in sources if s.snippet)
        logger.info(
            "[Search] Source coverage: %d total, %d with title, %d with snippet",
            len(sources), with_title, with_snippet,
        )

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
        cached_sources, cached_errors = _cache[cache_key]
        return list(cached_sources), list(cached_errors)

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
            cached_sources = sources[:max_results]
            cached_errors = list(errors)
            _cache[cache_key] = (cached_sources, cached_errors)
            return list(cached_sources), list(cached_errors)

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

        # Jittered delay before next attempt
        if attempt < _MAX_RETRIES:
            jitter = random.uniform(0.5, 1.5)
            logger.info("Retrying web_search in %.1fs...", jitter)
            await asyncio.sleep(jitter)

    return [], errors
