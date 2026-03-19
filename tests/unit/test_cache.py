import pytest
import app.core.cache as cache_module
from app.core.cache import get_cached, set_cached
from app.schemas import Source


def _source(url="https://example.com", title="Example Title", snippet="Some relevant snippet text here"):
    return Source(url=url, title=title, snippet=snippet)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Redirect cache.db to a temp file so tests never touch the real cache."""
    monkeypatch.setattr(cache_module, "_DB_PATH", str(tmp_path / "test_cache.db"))


async def test_cache_miss_returns_none():
    result = await get_cached("nonexistent query|10")
    assert result is None


async def test_cache_roundtrip():
    key = "test cache roundtrip|5"
    sources = [_source()]
    await set_cached(key, sources)
    result = await get_cached(key)
    assert result is not None
    assert len(result) == 1
    assert result[0].title == "Example Title"
