from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

from app.schemas import Source

logger = logging.getLogger(__name__)

_MIN_TITLE_LEN = 10
_MIN_SNIPPET_LEN = 30
_MAX_TEXT_LEN = 500

_RESEARCH_KEYWORDS = re.compile(
    r"gartner|forrester|mckinsey|idc|statista|deloitte|bain|bcg|"
    r"market\s*report|industry\s*report|market\s*size|market\s*research|"
    r"research\s*report|analyst|forecast|outlook",
    re.IGNORECASE,
)


_BLOCKED_DOMAINS = {
    "wikipedia.org",
    "en.wikipedia.org",
    "en.m.wikipedia.org",
    "simple.wikipedia.org",
    "wikidata.org",
    "wikimedia.org",
    "quora.com",
    "reddit.com",
    "pinterest.com",
    "youtube.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "instagram.com",
    "tiktok.com",
}


def _is_blocked_domain(url: str) -> bool:
    """Return True if the URL belongs to a low-signal domain."""
    try:
        host = urlparse(str(url)).netloc.lower()
        # Strip www. prefix for matching
        if host.startswith("www."):
            host = host[4:]
        return host in _BLOCKED_DOMAINS
    except Exception:
        return False


def _is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(str(url))
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def _trim(text: str, max_len: int = _MAX_TEXT_LEN) -> str:
    text = " ".join(text.split())
    if len(text) > max_len:
        return text[:max_len].rsplit(" ", 1)[0] + "..."
    return text


def _research_score(source: Source) -> int:
    """Return 1 if the source looks like a research/report, else 0."""
    combined = f"{source.title} {source.snippet}"
    return 1 if _RESEARCH_KEYWORDS.search(combined) else 0


def clean_sources(
    sources: list[Source],
    max_results: int = 10,
) -> list[Source]:
    """Normalize, filter, dedupe, and rank a raw Source list.

    Steps:
      1. Trim whitespace and cap text length
      2. Drop bad URLs
      3. Quality filter (title / snippet too short)
      4. Dedupe by normalized URL
      5. Sort: research-like sources first, then original order
      6. Cap at max_results
    """
    # Normalize www. URLs by prepending https://
    normalized: list[Source] = []
    for src in sources:
        url = str(src.url).strip()
        if url.lower().startswith("www."):
            url = f"https://{url}"
            src = Source(url=url, title=src.title, snippet=src.snippet)
        normalized.append(src)

    cleaned: list[Source] = []

    for src in normalized:
        url = str(src.url).strip()

        if not _is_valid_url(url):
            logger.debug("Dropping bad URL: %s", url)
            continue

        if _is_blocked_domain(url):
            logger.debug("Dropping blocked domain: %s", url)
            continue

        # Use trimmed text only for length checks — don't mutate the original
        title_trimmed = _trim(src.title)
        snippet_trimmed = _trim(src.snippet)

        if len(title_trimmed) < _MIN_TITLE_LEN and len(snippet_trimmed) < _MIN_SNIPPET_LEN:
            logger.debug("Dropping low-quality source: %s", src.title)
            continue

        cleaned.append(src)

    # Dedupe by normalized URL (scheme + netloc + path, ignore query/fragment)
    seen: set[str] = set()
    deduped: list[Source] = []
    for src in cleaned:
        parsed = urlparse(str(src.url))
        key = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".lower().rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(src)

    # Stable sort: research sources float up, rest keeps original order
    deduped.sort(key=lambda s: -_research_score(s))

    # Fallback: never return empty when input was non-empty
    if not deduped and sources:
        fallback = cleaned if cleaned else normalized
        return fallback[:max_results]

    return deduped[:max_results]
