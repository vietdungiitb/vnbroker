import pytest

from vnstock.api.news import News
from vnstock.core import source_router
from vnstock.core.registry import ProviderRegistry


class _HealthyNewsProvider:
    def __init__(self, symbol=None, **kwargs):
        self.symbol = symbol

    def latest(self, **kwargs):
        return {"items": [], "source": "healthy", "kwargs": kwargs}

    def search(self, **kwargs):
        return {"items": [], "source": "healthy", "kwargs": kwargs}

    def by_symbol(self, **kwargs):
        return {"items": [], "source": "healthy", "kwargs": kwargs}


class _FailingNewsProvider:
    def __init__(self, symbol=None, **kwargs):
        self.symbol = symbol

    def latest(self, **kwargs):
        raise ConnectionError("429 too many requests")

    def search(self, **kwargs):
        raise ConnectionError("429 too many requests")

    def by_symbol(self, **kwargs):
        raise ConnectionError("429 too many requests")


@pytest.mark.unit
@pytest.mark.api
class TestNewsAdapter:
    def setup_method(self):
        source_router.reset_router_state()

    def teardown_method(self):
        source_router.reset_router_state()

    def test_auto_news_fails_over_when_primary_errors(self, monkeypatch):
        providers = {
            ("news", "vci"): _FailingNewsProvider,
            ("news", "kbs"): _HealthyNewsProvider,
        }

        def fake_get(module_name, source_name):
            return providers[(module_name, source_name)]

        monkeypatch.setattr("vnstock.base.build_source_order", lambda *args, **kwargs: ["vci", "kbs"])
        monkeypatch.setattr(ProviderRegistry, "get", fake_get)

        news = News(source="AUTO", symbol="ACB", show_log=False)
        result = news.latest(limit=5)

        assert result["source_used"] == "KBS"

    def test_explicit_source_news_calls_provider(self, monkeypatch):
        def fake_get(module_name, source_name):
            assert module_name == "news"
            assert source_name == "vci"
            return _HealthyNewsProvider

        monkeypatch.setattr(ProviderRegistry, "get", fake_get)

        news = News(source="vci", symbol="ACB", show_log=False)
        result = news.search(query="bank", limit=3)

        assert result["source"] == "healthy"
