import pandas as pd
import pytest

from vnbroker.common.data import News


def _stub_news_df(symbol):
    return pd.DataFrame([
        {"symbol": "ACB", "source": "VCI", "title": "ACB ket qua kinh doanh",
         "summary": "Doan van 1", "published_at": "2026-04-11T08:00:00Z"},
        {"symbol": "VCB", "source": "KBS", "title": "VCB thong tin co tuc",
         "summary": "Doan van 2", "published_at": "2026-04-11T09:00:00Z"},
    ])


class _StubNews:
    def latest(self, **kwargs):
        return _stub_news_df(None)

    def by_symbol(self, symbol, **kwargs):
        df = _stub_news_df(symbol)
        return df[df["symbol"].str.upper() == symbol.upper()]

    def search(self, query, **kwargs):
        return _stub_news_df(None)


@pytest.mark.unit
class TestNewsFacadeFilter:
    def test_news_filter_by_query_and_symbol(self, monkeypatch):
        monkeypatch.setattr(News, "_load_data_source", lambda self: _StubNews())
        news = News(symbol="ACB", source="VCI")
        out = news.filter(symbol="ACB", query="ket qua", limit=10)
        assert len(out) == 1
        assert out.iloc[0]["symbol"] == "ACB"

    def test_news_query_alias(self, monkeypatch):
        monkeypatch.setattr(News, "_load_data_source", lambda self: _StubNews())
        news = News(symbol="ACB", source="VCI")
        out = news.query("co tuc", symbol="VCB", limit=10)
        assert len(out) == 1
        assert out.iloc[0]["symbol"] == "VCB"
