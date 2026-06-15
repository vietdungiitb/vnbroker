"""
Unit tests for DNSE Finance provider (fallback implementation).
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pandas as pd
import pytest

from vnbroker.explorer.dnse.finance import DNSEFinance


def _make_finance():
    """Create a DNSEFinance instance with mocked credentials."""
    with patch.dict(os.environ, {"DNSE_API_KEY": "test-key", "DNSE_API_SECRET": "test-secret"}):
        return DNSEFinance("VNM", show_log=True)


class TestDNSEFinanceInit:
    """Tests for DNSEFinance initialization."""

    def test_raises_without_credentials(self, monkeypatch):
        """Should raise ValueError when credentials are missing."""
        monkeypatch.delenv("DNSE_API_KEY", raising=False)
        monkeypatch.delenv("DNSE_API_SECRET", raising=False)
        with pytest.raises(ValueError, match="DNSE cần api_key và api_secret"):
            DNSEFinance("VNM")

    def test_accepts_direct_credentials(self):
        """Should accept api_key and api_secret as direct parameters."""
        finance = DNSEFinance("VNM", api_key="key", api_secret="secret")
        assert finance.symbol == "VNM"

    def test_accepts_env_credentials(self):
        """Should use environment variables when direct params not provided."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "env-key", "DNSE_API_SECRET": "env-secret"}):
            finance = DNSEFinance("VNM")
            assert finance.symbol == "VNM"

    def test_symbol_uppercase(self):
        """Symbol should be converted to uppercase."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            finance = DNSEFinance("vnm")
            assert finance.symbol == "VNM"

    def test_period_stored(self):
        """Period parameter should be stored."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            finance = DNSEFinance("VNM", period="year")
            assert finance.period == "year"

    def test_get_all_stored(self):
        """get_all parameter should be stored."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            finance = DNSEFinance("VNM", get_all=False)
            assert finance.get_all is False

    def test_show_log_flag(self):
        """show_log flag should be stored."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            finance = DNSEFinance("VNM", show_log=True)
            assert finance.show_log is True


class TestDNSEFinanceMethods:
    """Tests for DNSEFinance public methods returning empty DataFrames."""

    def test_balance_sheet_returns_empty_dataframe(self):
        """balance_sheet() should return empty DataFrame with standard columns."""
        finance = _make_finance()
        df = finance.balance_sheet()

        assert isinstance(df, pd.DataFrame)
        assert df.empty
        expected_columns = ["item", "item_en", "item_id"]
        assert list(df.columns) == expected_columns

    def test_income_statement_returns_empty_dataframe(self):
        """income_statement() should return empty DataFrame with standard columns."""
        finance = _make_finance()
        df = finance.income_statement()

        assert isinstance(df, pd.DataFrame)
        assert df.empty
        expected_columns = ["item", "item_en", "item_id"]
        assert list(df.columns) == expected_columns

    def test_cash_flow_returns_empty_dataframe(self):
        """cash_flow() should return empty DataFrame with standard columns."""
        finance = _make_finance()
        df = finance.cash_flow()

        assert isinstance(df, pd.DataFrame)
        assert df.empty
        expected_columns = ["item", "item_en", "item_id"]
        assert list(df.columns) == expected_columns

    def test_ratio_returns_empty_dataframe(self):
        """ratio() should return empty DataFrame with standard columns."""
        finance = _make_finance()
        df = finance.ratio()

        assert isinstance(df, pd.DataFrame)
        assert df.empty
        expected_columns = ["item", "item_en", "item_id"]
        assert list(df.columns) == expected_columns

    def test_financial_ratios_alias(self):
        """financial_ratios() should be an alias for ratio()."""
        finance = _make_finance()
        df1 = finance.ratio()
        df2 = finance.financial_ratios()

        assert isinstance(df1, pd.DataFrame)
        assert isinstance(df2, pd.DataFrame)
        assert list(df1.columns) == list(df2.columns)

    def test_all_methods_accept_kwargs(self):
        """All methods should accept arbitrary kwargs without error."""
        finance = _make_finance()

        # Should not raise any exception
        finance.balance_sheet(period="year", lang="vi", dropna=False, display_mode="all")
        finance.income_statement(period="quarter", lang="en", dropna=True)
        finance.cash_flow(period="year", display_mode="vi")
        finance.ratio(period="quarter", lang="en", dropna=False)


class TestDNSEFinanceLogging:
    """Tests for logging behavior."""

    def test_logs_warning_when_show_log_true(self, caplog):
        """Should log warning when show_log=True and method called."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            finance = DNSEFinance("VNM", show_log=True)

        with caplog.at_level("WARNING"):
            finance.balance_sheet()

        assert any("DNSE OpenAPI does not support financial endpoints" in record.message for record in caplog.records)

    def test_no_warning_when_show_log_false(self, caplog):
        """Should not log warning when show_log=False."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            finance = DNSEFinance("VNM", show_log=False)

        with caplog.at_level("WARNING"):
            finance.balance_sheet()

        assert not any("DNSE OpenAPI does not support financial endpoints" in record.message for record in caplog.records)

    def test_logs_info_on_init_when_show_log_true(self, caplog):
        """Should log info on initialization when show_log=True."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            with caplog.at_level("INFO"):
                DNSEFinance("VNM", show_log=True)

        assert any("DNSEFinance initialized for VNM" in record.message for record in caplog.records)


class TestDNSEFinanceProviderRegistry:
    """Tests for ProviderRegistry integration."""

    def test_provider_registered(self):
        """DNSEFinance should be registered in ProviderRegistry."""
        from vnbroker import _ensure_explorer_modules_loaded
        from vnbroker.core.registry import ProviderRegistry

        _ensure_explorer_modules_loaded()
        assert ProviderRegistry.is_registered("financial", "dnse")

    def test_provider_class_correct(self):
        """Registered provider should be DNSEFinance class."""
        from vnbroker import _ensure_explorer_modules_loaded
        from vnbroker.core.registry import ProviderRegistry

        _ensure_explorer_modules_loaded()
        provider_class = ProviderRegistry.get("financial", "dnse")
        assert provider_class is DNSEFinance