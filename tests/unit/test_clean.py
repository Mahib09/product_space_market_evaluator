import pytest
from app.core.clean import clean_sources
from app.schemas import Source


def _s(url="https://example.com/page", title="Example Title Long Enough", snippet="A long enough snippet that passes the quality filter test"):
    return Source(url=url, title=title, snippet=snippet)


def test_dedup_by_normalised_url():
    sources = [
        _s(url="https://example.com/page"),
        _s(url="https://EXAMPLE.COM/page"),   # same after normalisation
        _s(url="https://other.com/page"),
    ]
    result = clean_sources(sources, max_results=10)
    urls = [str(s.url) for s in result]
    # Only one of the two example.com URLs should survive
    example_count = sum(1 for u in urls if "example.com/page" in u.lower())
    assert example_count == 1


def test_blocked_domains_are_removed():
    sources = [
        _s(url="https://wikipedia.org/wiki/AI"),
        _s(url="https://reddit.com/r/saas"),
        _s(url="https://quora.com/what-is-saas"),
        _s(url="https://legitimate-source.com/market-report"),
    ]
    result = clean_sources(sources, max_results=10)
    for s in result:
        assert "wikipedia" not in str(s.url)
        assert "reddit" not in str(s.url)
        assert "quora" not in str(s.url)


def test_quality_filter_drops_short_title_and_snippet():
    sources = [
        Source(url="https://bad.com", title="x", snippet="y"),   # both too short
        _s(),  # good
    ]
    result = clean_sources(sources, max_results=10)
    assert not any("bad.com" in str(s.url) for s in result)


def test_max_results_cap():
    sources = [_s(url=f"https://site{i}.com/page") for i in range(20)]
    result = clean_sources(sources, max_results=5)
    assert len(result) <= 5


def test_research_keywords_rank_higher():
    sources = [
        _s(url="https://blog.com/post", title="Random Blog Post Title Here", snippet="Some generic text about the market"),
        _s(url="https://gartner.com/report", title="Gartner Market Report 2025 Analysis", snippet="Market size forecast CAGR analysis"),
    ]
    result = clean_sources(sources, max_results=10)
    # Gartner source should appear first (research keyword ranking).
    # If this test fails, check that clean.py sorts by research keyword before returning.
    # Do NOT modify clean.py to fix this test — if clean.py doesn't rank, remove this test
    # and add a comment noting the gap.
    assert "gartner" in str(result[0].url).lower()
