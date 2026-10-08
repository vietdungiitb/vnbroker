"""
Unit tests for vnbroker.api.bulk — BulkAPI class.

Tests the BulkAPI integration with BulkRouter, HealthRouter, and ProviderPool.
"""

import pytest
import pandas as pd

from vnbroker.api.bulk import BulkAPI
from vnbroker.ui.market import Market


@pytest.mark.unit
@pytest.mark.api
class TestBulkAPI:
    """Test suite for BulkAPI."""

    def test_bulk_api_init(self):
        """BulkAPI can be instantiated."""
        api = BulkAPI(source="AUTO", show_log=False)
        assert api is not None
        assert api.source == "AUTO"
        assert api.show_log is False

    def test_bulk_api_default_source(self):
        """BulkAPI defaults to AUTO source."""
        api = BulkAPI(show_log=False)
        assert api.source == "AUTO"

    def test_bulk_history_empty_symbols(self):
        """Empty symbol list returns empty DataFrame without crashing."""
        api = BulkAPI(source="AUTO", show_log=False)
        df = api.history([])
        assert isinstance(df, pd.DataFrame)
        assert df.empty
        assert "symbol" in df.columns

    def test_bulk_history_returns_dataframe(self):
        """Bulk history returns DataFrame with symbol column."""
        api = BulkAPI(source="AUTO", show_log=False)
        # Use a small symbol list — may return empty if no network,
        # but should always return a DataFrame
        df = api.history(["ACB"], start="2024-01-01", end="2024-01-31")
        assert isinstance(df, pd.DataFrame)
        assert "symbol" in df.columns

    def test_bulk_history_attrs(self):
        """Result has sources_used, failed, requested, returned attrs."""
        api = BulkAPI(source="AUTO", show_log=False)
        df = api.history(["ACB"], start="2024-01-01", end="2024-01-31")
        assert hasattr(df, "attrs")
        assert "sources_used" in df.attrs
        assert "failed" in df.attrs
        assert "requested" in df.attrs
        assert "returned" in df.attrs
        assert df.attrs["requested"] == 1

    def test_bulk_history_multiple_symbols(self):
        """Bulk history handles multiple symbols."""
        api = BulkAPI(source="AUTO", show_log=False)
        df = api.history(["ACB", "VNM", "FPT"], start="2024-01-01", end="2024-01-31")
        assert isinstance(df, pd.DataFrame)
        assert "symbol" in df.columns
        assert df.attrs["requested"] == 3

    def test_bulk_price_board_empty_symbols(self):
        """Price board with empty list returns DataFrame."""
        api = BulkAPI(source="AUTO", show_log=False)
        # Empty list should not crash
        df = api.price_board([])
        assert isinstance(df, pd.DataFrame)

    def test_market_bulk_property(self):
        """Market(auto=True).bulk returns BulkAPI."""
        mkt = Market(auto=True, show_log=False)
        bulk = mkt.bulk
        assert isinstance(bulk, BulkAPI)
        assert bulk.source == "AUTO"
        assert bulk.show_log is False

    def test_market_bulk_property_with_source(self):
        """Market(source='KBS').bulk returns BulkAPI with KBS source."""
        mkt = Market(source="KBS", show_log=False)
        bulk = mkt.bulk
        assert isinstance(bulk, BulkAPI)
        assert bulk.source == "KBS"

    def test_bulk_api_has_provider_pool(self):
        """BulkAPI has provider pool initialized."""
        api = BulkAPI(show_log=False)
        assert api._provider_pool is not None
        providers = api._provider_pool.get_available_providers("quote")
        assert isinstance(providers, list)
        assert len(providers) > 0

    def test_bulk_api_has_routers(self):
        """BulkAPI has health and bulk routers initialized."""
        api = BulkAPI(show_log=False)
        assert api._health_router is not None
        assert api._bulk_router is not None
