from app.agents.agent2 import _has_funding_signal, _is_high_signal_domain
from app.schemas import Source


def _src(title="", snippet="", url="https://example.com"):
    return Source(url=url, title=title, snippet=snippet)


def test_funding_signal_detects_grant():
    src = _src(title="Company receives $2M USDA grant for precision agriculture research")
    assert _has_funding_signal(src)


def test_funding_signal_detects_acquisition():
    src = _src(title="MedTech startup acquired by Abbott for $85M")
    assert _has_funding_signal(src)


def test_high_signal_domain_includes_wsj():
    src = _src(url="https://wsj.com/articles/company-raises-50m")
    assert _is_high_signal_domain(src)
