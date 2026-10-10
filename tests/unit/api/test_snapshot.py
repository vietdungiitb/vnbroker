"""
Unit tests for vnbroker API MarketSnapshot adapter.

Tests the MarketSnapshot class for heatmap data aggregation,
DataFrame output, and edge cases.
"""

import pytest
import pandas as pd
from unittest.mock import patch

from vnbroker.api.snapshot import MarketSnapshot


@pytest.mark.unit
@pytest.mark.api
class TestMarketSnapshot:
    """Test suite for MarketSnapshot API adapter."""

    def test_snapshot_init(self):
        """Test MarketSnapshot can be instantiated."""
        snap = MarketSnapshot()
        assert snap is not None
        assert snap.source == "kbs"
        assert snap.random_agent is False
        assert snap.show_log is False

    def test_snapshot_init_with_params(self):
        """Test MarketSnapshot accepts custom parameters."""
        snap = MarketSnapshot(source="kbs", random_agent=True, show_log=True)
        assert snap.source == "kbs"
        assert snap.random_agent is True
        assert snap.show_log is True

    @patch.object(MarketSnapshot, "_build_snapshot_df")
    def test_snapshot_heatmap_data(self, mock_build_df):
        """Test heatmap_data returns list of dicts."""
        mock_df = pd.DataFrame([
            {
                "symbol": "VCB",
                "current_price": 88.5,
                "prev_price": 89.0,
                "change_pct": -0.56,
                "volume": 1234567,
                "market_cap": 315432.1,
                "industry": "Ngân hàng",
                "company_name": "Ngân hàng TMCP Ngoại Thương Việt Nam",
            }
        ])
        mock_build_df.return_value = mock_df

        snap = MarketSnapshot()
        result = snap.heatmap_data(["VCB"])

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["symbol"] == "VCB"
        assert result[0]["current_price"] == 88.5
        assert "industry" in result[0]
        assert "company_name" in result[0]

    @patch.object(MarketSnapshot, "_build_snapshot_df")
    def test_snapshot_heatmap_df(self, mock_build_df):
        """Test heatmap_df returns DataFrame."""
        mock_df = pd.DataFrame([
            {
                "symbol": "VCB",
                "current_price": 88.5,
                "prev_price": 89.0,
                "change_pct": -0.56,
                "volume": 1234567,
                "market_cap": 315432.1,
                "industry": "Ngân hàng",
                "company_name": "Ngân hàng TMCP Ngoại Thương Việt Nam",
            }
        ])
        mock_build_df.return_value = mock_df

        snap = MarketSnapshot()
        result = snap.heatmap_df(["VCB"])

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert "symbol" in result.columns
        assert "current_price" in result.columns
        assert "industry" in result.columns

    def test_snapshot_empty_symbols(self):
        """Test empty symbol list raises ValueError."""
        snap = MarketSnapshot()
        with pytest.raises(ValueError, match="symbols_list"):
            snap.heatmap_data([])

    def test_snapshot_empty_symbols_df(self):
        """Test empty symbol list raises ValueError for heatmap_df."""
        snap = MarketSnapshot()
        with pytest.raises(ValueError, match="symbols_list"):
            snap.heatmap_df([])

    @patch.object(MarketSnapshot, "_build_snapshot_df")
    def test_snapshot_heatmap_data_empty_result(self, mock_build_df):
        """Test heatmap_data returns empty list when no data."""
        mock_build_df.return_value = pd.DataFrame()

        snap = MarketSnapshot()
        result = snap.heatmap_data(["INVALID"])

        assert result == []

    def test_snapshot_refresh_caches(self):
        """Test refresh_caches clears internal cache."""
        snap = MarketSnapshot()
        snap._industry_cache = pd.DataFrame({"symbol": ["VCB"], "industry_name": ["Ngân hàng"]})
        snap._company_cache = pd.DataFrame({"symbol": ["VCB"], "organ_name": ["VCB Bank"]})
        snap._industry_cache_ts = 12345.0
        snap._company_cache_ts = 12345.0

        snap.refresh_caches()

        assert snap._industry_cache is None
        assert snap._company_cache is None
        assert snap._industry_cache_ts == 0.0
        assert snap._company_cache_ts == 0.0
