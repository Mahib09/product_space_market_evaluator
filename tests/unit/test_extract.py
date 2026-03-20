from app.core.extract import _build_evidence_block
from app.schemas import Source


def _src(snippet: str) -> Source:
    return Source(url="https://example.com", title="T", snippet=snippet)


def test_evidence_block_includes_full_snippet():
    """Snippets must NOT be truncated — Agent 2 needs full text to find investor/funding data."""
    long = "x" * 400
    block = _build_evidence_block([_src(long)])
    assert "x" * 400 in block


def test_evidence_block_contains_title_and_url():
    block = _build_evidence_block([_src("some snippet")])
    assert "T" in block
    assert "example.com" in block
