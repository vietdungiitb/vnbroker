"""Tests for DNSE Quote.fetch_multiple (bulk operations)."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from vnbroker.explorer.dnse.quote import DNSEQuote


class TestDNSEFetchMultiple:
    """Test DNSE fetch_multiple classmethod."""

    def test_fetch_multiple_empty_symbols(self):
        """Empty symbol list returns empty list."""
        result = DNSEQuote.fetch_multiple(symbols=[])
        assert result == []

    def test_fetch_multiple_returns_list(self):
        """Returns a list of DataFrames."""
        with patch.object(DNSEQuote, "__init__", lambda self, **kw: None):
            with patch.object(
                DNSEQuote,
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
                result = DNSEQuote.fetch_multiple(
                    symbols=["ACB"], start="2024-01-01", end="2024-01-31"
                )
                assert isinstance(result, list)
                assert len(result) == 1
                assert isinstance(result[0], pd.DataFrame)

    def test_fetch_multiple_handles_failures(self):
        """Failed symbols return None and are filtered out."""
        with patch.object(DNSEQuote, "__init__", lambda self, **kw: None):
            with patch.object(
                DNSEQuote,
                "history",
                side_effect=[Exception("fail"), pd.DataFrame({"time": [1]})],
            ):
                result = DNSEQuote.fetch_multiple(
                    symbols=["FAIL", "OK"], start="2024-01-01", end="2024-01-31"
                )
                assert len(result) == 1

    def test_fetch_multiple_concurrent(self):
        """Multiple symbols are fetched concurrently."""
        with patch.object(DNSEQuote, "__init__", lambda self, **kw: None):
            with patch.object(
                DNSEQuote,
                "history",
                return_value=pd.DataFrame({"time": [1]}),
            ):
                result = DNSEQuote.fetch_multiple(
                    symbols=["ACB", "VNM", "HPG"],
                    start="2024-01-01",
                    end="2024-01-31",
                    max_concurrency=3,
                )
                assert len(result) == 3
