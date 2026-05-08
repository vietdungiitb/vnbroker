from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from vnstock.explorer.dnse.quote import (
    DNSEQuote,
    _normalize_interval,
    _to_unix_seconds,
    _extract_ohlc_list,
    _parse_ohlc,
    _parse_trades,
)


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

    def test_extract_ohlc_list_none(self):
        assert _extract_ohlc_list(None) == []

    def test_extract_ohlc_list_direct_list(self):
        records = [{"t": 1704067200, "o": 100.0, "h": 110.0, "l": 90.0, "c": 105.0, "v": 1000}]
        assert _extract_ohlc_list(records) == records

    def test_extract_ohlc_list_dict_with_bars_key(self):
        body = {"bars": [{"t": 1, "o": 1.0, "h": 1.0, "l": 1.0, "c": 1.0, "v": 1}]}
        result = _extract_ohlc_list(body)
        assert len(result) == 1

    def test_extract_ohlc_list_dict_with_ohlc_fields_wraps_as_record(self):
        """Dict body với các field OHLC trực tiếp → wrap thành [body]."""
        body = {"t": 1704067200, "o": 67000.0, "h": 68500.0, "l": 66800.0, "c": 68000.0, "v": 1234567}
        result = _extract_ohlc_list(body)
        assert result == [body]

    def test_extract_ohlc_list_dict_no_known_key_returns_empty(self):
        assert _extract_ohlc_list({"unknown": "value"}) == []

    def test_parse_ohlc_empty_records(self):
        df = _parse_ohlc([])
        assert list(df.columns) == ["time", "open", "high", "low", "close", "volume"]
        assert df.empty

    def test_parse_ohlc_string_timestamp(self):
        records = [{"time": "2024-01-01", "open": 100.0, "high": 110.0, "low": 90.0, "close": 105.0, "volume": 1000}]
        df = _parse_ohlc(records)
        # pandas 2+ có thể trả datetime64[us] hoặc datetime64[ns] tuỳ platform
        assert str(df["time"].dtype).startswith("datetime64")

    def test_parse_trades_empty(self):
        df = _parse_trades([])
        assert list(df.columns) == ["time", "price", "volume", "side"]
        assert df.empty

    def test_parse_trades_with_alias_columns(self):
        records = [{"t": 1704067200, "p": 68000.0, "q": 500, "bs": "B"}]
        df = _parse_trades(records)
        assert "time" in df.columns
        assert "price" in df.columns
        assert "volume" in df.columns
        assert "side" in df.columns


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

    def test_history_sorted_ascending(self):
        """history() phải sort tăng dần theo time."""
        quote, _ = _make_quote()
        df = quote.history(start="2024-01-01", end="2024-01-02")
        assert df["time"].is_monotonic_increasing

    def test_history_returns_empty_on_api_error(self):
        """history() trả empty DataFrame khi API lỗi, không raise."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            with patch("vnstock.connector.dnse.client.DNSEClient") as mc:
                m = MagicMock()
                m._market.get_ohlc.side_effect = Exception("network timeout")
                mc.return_value = m
                q = DNSEQuote("VNM")
                df = q.history()
        assert df.empty
        assert list(df.columns) == ["time", "open", "high", "low", "close", "volume"]

    def test_history_with_show_log(self):
        """history() log khi show_log=True."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            with patch("vnstock.connector.dnse.client.DNSEClient") as mc:
                m = MagicMock()
                m._market.get_ohlc.return_value = (200, _SAMPLE_OHLC_BODY)
                mc.return_value = m
                q = DNSEQuote("VNM", show_log=True)
                df = q.history(symbol="VNM", start="2024-01-01")
        assert not df.empty

    def test_intraday_returns_dataframe(self):
        quote, mock_client = _make_quote()
        df = quote.intraday(page_size=50)

        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["time", "price", "volume", "side"]
        assert mock_client._market.get_trades.called

    def test_intraday_empty_on_404(self):
        """intraday() trả empty khi API lỗi (404 live)."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            with patch("vnstock.connector.dnse.client.DNSEClient") as mc:
                m = MagicMock()
                m._market.get_trades.side_effect = Exception("404 not found")
                mc.return_value = m
                q = DNSEQuote("VNM")
                df = q.intraday()
        assert df.empty
        assert list(df.columns) == ["time", "price", "volume", "side"]

    def test_intraday_body_none_returns_empty(self):
        """intraday() trả empty khi body là None."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            with patch("vnstock.connector.dnse.client.DNSEClient") as mc:
                m = MagicMock()
                m._market.get_trades.return_value = (200, None)
                mc.return_value = m
                q = DNSEQuote("VNM")
                df = q.intraday()
        assert df.empty

    def test_intraday_body_list_directly(self):
        """intraday() xử lý body trả về trực tiếp là list."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            with patch("vnstock.connector.dnse.client.DNSEClient") as mc:
                m = MagicMock()
                m._market.get_trades.return_value = (
                    200,
                    [{"t": 1704067200, "p": 68000.0, "v": 500, "s": "B"}],
                )
                mc.return_value = m
                q = DNSEQuote("VNM")
                df = q.intraday()
        assert len(df) == 1

    def test_intraday_show_log(self):
        """intraday() log khi show_log=True."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            with patch("vnstock.connector.dnse.client.DNSEClient") as mc:
                m = MagicMock()
                m._market.get_trades.return_value = (200, _SAMPLE_TRADES_BODY)
                mc.return_value = m
                q = DNSEQuote("VNM", show_log=True)
                df = q.intraday()
        assert not df.empty

    def test_price_depth_returns_dataframe(self):
        quote, _ = _make_quote()
        df = quote.price_depth()

        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert "symbol" in df.columns

    def test_price_depth_with_list_body(self):
        """price_depth() xử lý body list[dict] như live DNSE."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            with patch("vnstock.connector.dnse.client.DNSEClient") as mc:
                m = MagicMock()
                m._market.get_security_definition.return_value = (
                    200,
                    [{"symbol": "VNM", "boardId": "HOSE", "lotSize": 100}],
                )
                mc.return_value = m
                q = DNSEQuote("VNM")
                df = q.price_depth()
        assert len(df) == 1

    def test_price_depth_body_none_returns_empty(self):
        """price_depth() trả empty DataFrame khi body None."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            with patch("vnstock.connector.dnse.client.DNSEClient") as mc:
                m = MagicMock()
                m._market.get_security_definition.return_value = (200, None)
                mc.return_value = m
                q = DNSEQuote("VNM")
                df = q.price_depth()
        assert df.empty

    def test_price_depth_api_error_returns_empty(self):
        """price_depth() trả empty khi API lỗi, không raise."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            with patch("vnstock.connector.dnse.client.DNSEClient") as mc:
                m = MagicMock()
                m._market.get_security_definition.side_effect = Exception("500 error")
                mc.return_value = m
                q = DNSEQuote("VNM")
                df = q.price_depth()
        assert df.empty

    def test_history_uses_symbol_from_init(self):
        """history() dùng symbol từ __init__ nếu không truyền tham số."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            with patch("vnstock.connector.dnse.client.DNSEClient") as mc:
                m = MagicMock()
                m._market.get_ohlc.return_value = (200, _SAMPLE_OHLC_BODY)
                mc.return_value = m
                q = DNSEQuote("HPG")
                df = q.history()
        call_kwargs = m._market.get_ohlc.call_args.kwargs
        assert call_kwargs.get("query", {}).get("symbol") == "HPG"
