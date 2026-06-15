import pandas as pd
import pytest
from unittest.mock import MagicMock

from vnbroker.common.data import News


class _StubGatewayNews:
    """Mock GatewayNewsAdapter for testing."""
    def __init__(self, symbol="", gateway_request_func=None, **kwargs):
        self.symbol = symbol
        self.gateway_request_func = gateway_request_func

    def market_news(self, limit=100, **kwargs):
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

    def symbol_news(self, symbol="", limit=100, **kwargs):
        data = self.market_news(limit=100)
        out = data[data["symbol"].str.upper() == symbol.upper()]
        return out.head(limit)

    def by_symbol(self, symbol="", limit=100, **kwargs):
        return self.symbol_news(symbol=symbol, limit=limit)

    def filter(self, symbol=None, query=None, limit=100, **kwargs):
        if symbol:
            return self.symbol_news(symbol=symbol, limit=limit)
        return self.market_news(limit=limit)


@pytest.mark.unit
class TestNewsFacadeFilter:
    def test_news_filter_by_query_and_symbol(self, monkeypatch):
        monkeypatch.setattr("vnbroker.common.data.GatewayNewsAdapter", _StubGatewayNews)

        # Create News with mock gateway
        mock_gateway = MagicMock()
        news = News(symbol="ACB", source="GATEWAY", gateway_request_func=mock_gateway)
        out = news.filter(symbol="ACB", query="ket qua", limit=10)

        assert len(out) == 1
        assert out.iloc[0]["symbol"] == "ACB"

    def test_news_query_alias(self, monkeypatch):
        monkeypatch.setattr("vnbroker.common.data.GatewayNewsAdapter", _StubGatewayNews)

        # Create News with mock gateway
        mock_gateway = MagicMock()
        news = News(symbol="ACB", source="GATEWAY", gateway_request_func=mock_gateway)
        out = news.query("co tuc", symbol="VCB", limit=10)

        assert len(out) == 1
        assert out.iloc[0]["symbol"] == "VCB"
