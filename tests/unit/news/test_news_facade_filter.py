import pandas as pd
import pytest

from vnstock.common.data import News


class _StubNews:
    def __init__(self, symbol="", **kwargs):
        self.symbol = symbol

    def latest(self, limit=100, **kwargs):
        return pd.DataFrame([
            {
                "symbol": "ACB",
                "source": "VCI",
                "title": "ACB ket qua kinh doanh",
                "summary": "Doan van 1",
                "published_at": "2026-04-11T08:00:00Z",
            },
            {
                "symbol": "VCB",
                "source": "KBS",
                "title": "VCB thong tin co tuc",
                "summary": "Doan van 2",
                "published_at": "2026-04-11T09:00:00Z",
            },
        ]).head(limit)

    def by_symbol(self, symbol="", limit=100, **kwargs):
        data = self.latest(limit=100)
        out = data[data["symbol"].str.upper() == symbol.upper()]
        return out.head(limit)


@pytest.mark.unit
class TestNewsFacadeFilter:
    def test_news_filter_by_query_and_symbol(self, monkeypatch):
        monkeypatch.setattr("vnstock.api.news.News", _StubNews)

        news = News(symbol="ACB", source="AUTO")
        out = news.filter(symbol="ACB", query="ket qua", limit=10)

        assert len(out) == 1
        assert out.iloc[0]["symbol"] == "ACB"

    def test_news_query_alias(self, monkeypatch):
        monkeypatch.setattr("vnstock.api.news.News", _StubNews)

        news = News(symbol="ACB", source="AUTO")
        out = news.query("co tuc", symbol="VCB", limit=10)

        assert len(out) == 1
        assert out.iloc[0]["symbol"] == "VCB"
