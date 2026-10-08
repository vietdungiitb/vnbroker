"""Tests for SSI Quote.fetch_multiple (bulk operations)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from vnbroker.explorer.ssi.quote import SSIQuote


class TestSSIFetchMultiple:
    """Test SSI fetch_multiple instance method."""

    @pytest.fixture(autouse=True)
    def _ssi_env(self, monkeypatch):
        """Set fake SSI credentials."""
        monkeypatch.setenv("VNBROKER_BROKER_SSI_API_KEY", "test-key")
        monkeypatch.setenv("VNBROKER_BROKER_SSI_API_SECRET", "test-secret")

    def _make_quote(self):
        """Create SSIQuote with _service mocked (no network)."""
        quote = SSIQuote(
            symbol="ACB",
            api_key="test-key",
            api_secret="test-secret",
            show_log=False,
        )
        # Set _service so _market() returns it without network call
        quote._service = MagicMock()
        return quote

    def test_fetch_multiple_empty_symbols(self):
        """Empty symbol list returns empty dict."""
        quote = self._make_quote()
        result = quote.fetch_multiple(symbols_list=[])
        assert result == {}

    def test_fetch_multiple_returns_dict(self):
        """Returns a dict keyed by symbol."""
        quote = self._make_quote()
        with patch.object(
            SSIQuote,
            "history",
            return_value=pd.DataFrame(
                {
                    "time": pd.to_datetime(["2024-01-02"]),
                    "open": [1.0],
                    "high": [1.0],
                    "low": [1.0],
                    "close": [1.0],
                    "volume": [1],
                }
            ),
        ):
            result = quote.fetch_multiple(
                symbols_list=["ACB"], start="2024-01-01", end="2024-01-31"
            )
            assert isinstance(result, dict)
            assert "ACB" in result
            assert isinstance(result["ACB"], pd.DataFrame)

    def test_fetch_multiple_handles_failures(self):
        """Failed symbols have empty DataFrame with error attr."""
        quote = self._make_quote()
        with patch.object(
            SSIQuote,
            "history",
            side_effect=Exception("fail"),
        ):
            result = quote.fetch_multiple(
                symbols_list=["FAIL"], start="2024-01-01", end="2024-01-31"
            )
            assert "FAIL" in result
            assert result["FAIL"].empty
            assert "error" in result["FAIL"].attrs

    def test_fetch_multiple_concurrent(self):
        """Multiple symbols are fetched concurrently."""
        quote = self._make_quote()
        with patch.object(
            SSIQuote,
            "history",
            return_value=pd.DataFrame({"time": [1]}),
        ):
            result = quote.fetch_multiple(
                symbols_list=["ACB", "VNM", "HPG"],
                start="2024-01-01",
                end="2024-01-31",
                max_concurrency=3,
            )
            assert len(result) == 3
