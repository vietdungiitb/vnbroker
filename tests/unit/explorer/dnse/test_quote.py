from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from vnstock.explorer.dnse.quote import DNSEQuote, _normalize_interval, _to_unix_seconds


_SAMPLE_OHLC_BODY = {
    "bars": [
        {"t": 1704067200, "o": 67000.0, "h": 68500.0, "l": 66800.0, "c": 68000.0, "v": 1234567},
        {"t": 1704153600, "o": 68000.0, "h": 69000.0, "l": 67500.0, "c": 68500.0, "v": 987654},
    ]
}

_SAMPLE_TRADES_BODY = {
    "trades": [
        {"t": 1704067200, "p": 68000.0, "v": 500, "s": "B"},
        {"t": 1704067260, "p": 67900.0, "v": 300, "s": "S"},
    ]
}

_SAMPLE_SECDEF_BODY = {
    "symbol": "VNM",
    "name": "CTCP Sua Viet Nam",
    "boardId": "HOSE",
    "lotSize": 100,
}


def _make_quote():
    with patch.dict(os.environ, {"DNSE_API_KEY": "test-key", "DNSE_API_SECRET": "test-secret"}):
        with patch("vnstock.connector.dnse.client.DNSEClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client._market.get_ohlc.return_value = (200, _SAMPLE_OHLC_BODY)
            mock_client._market.get_trades.return_value = (200, _SAMPLE_TRADES_BODY)
            mock_client._market.get_security_definition.return_value = (200, _SAMPLE_SECDEF_BODY)
            mock_client_cls.return_value = mock_client
            return DNSEQuote("VNM"), mock_client


class TestDNSEQuoteHelpers:
    def test_normalize_interval_aliases(self):
        assert _normalize_interval("daily") == "1D"
        assert _normalize_interval("1h") == "1H"
        assert _normalize_interval("5m") == "5m"

    def test_to_unix_seconds(self):
        assert _to_unix_seconds("2024-01-01") == 1704067200


class TestDNSEQuote:
    def test_raises_without_credentials(self, monkeypatch):
        monkeypatch.delenv("DNSE_API_KEY", raising=False)
        monkeypatch.delenv("DNSE_API_SECRET", raising=False)
        with pytest.raises(ValueError):
            DNSEQuote("VNM")

    def test_history_returns_dataframe(self):
        quote, mock_client = _make_quote()
        df = quote.history(start="2024-01-01", end="2024-01-02")

        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["time", "open", "high", "low", "close", "volume"]
        assert df["time"].dtype == "datetime64[ns]"
        assert str(df["volume"].dtype) == "Int64"
        assert mock_client._market.get_ohlc.called

    def test_intraday_returns_dataframe(self):
        quote, mock_client = _make_quote()
        df = quote.intraday(page_size=50)

        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["time", "price", "volume", "side"]
        assert mock_client._market.get_trades.called

    def test_price_depth_returns_dataframe(self):
        quote, _ = _make_quote()
        df = quote.price_depth()

        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert "symbol" in df.columns
