"""
Unit tests for DNSE Company provider (fallback implementation).
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pandas as pd
import pytest

from vnbroker.explorer.dnse.company import DNSECompany


def _make_company():
    """Create a DNSECompany instance with mocked credentials."""
    with patch.dict(os.environ, {"DNSE_API_KEY": "test-key", "DNSE_API_SECRET": "test-secret"}):
        return DNSECompany("VNM", show_log=True)


class TestDNSECompanyInit:
    """Tests for DNSECompany initialization."""

    def test_raises_without_credentials(self, monkeypatch):
        """Should raise ValueError when credentials are missing."""
        monkeypatch.delenv("DNSE_API_KEY", raising=False)
        monkeypatch.delenv("DNSE_API_SECRET", raising=False)
        with pytest.raises(ValueError, match="DNSE cần api_key và api_secret"):
            DNSECompany("VNM")

    def test_accepts_direct_credentials(self):
        """Should accept api_key and api_secret as direct parameters."""
        company = DNSECompany("VNM", api_key="key", api_secret="secret")
        assert company.symbol == "VNM"

    def test_accepts_env_credentials(self):
        """Should use environment variables when direct params not provided."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "env-key", "DNSE_API_SECRET": "env-secret"}):
            company = DNSECompany("VNM")
            assert company.symbol == "VNM"

    def test_symbol_uppercase(self):
        """Symbol should be converted to uppercase."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            company = DNSECompany("vnm")
            assert company.symbol == "VNM"

    def test_show_log_flag(self):
        """show_log flag should be stored."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            company = DNSECompany("VNM", show_log=True)
            assert company.show_log is True


class TestDNSECompanyMethods:
    """Tests for DNSECompany public methods returning empty DataFrames."""

    def test_overview_returns_empty_dataframe(self):
        """overview() should return empty DataFrame with standard columns."""
        company = _make_company()
        df = company.overview()

        assert isinstance(df, pd.DataFrame)
        assert df.empty
        expected_columns = [
            "symbol",
            "organ_name",
            "organ_name_en",
            "organ_code",
            "icb_code",
            "icb_name",
            "icb_level",
            "listing_date",
            "charter_capital",
            "outstanding_shares",
            "no_shareholders",
            "foreign_ownership",
            "foreign_room",
            "business_description",
            "website",
            "email",
            "phone",
            "address",
            "tax_code",
            "ceo",
            "chairman",
        ]
        assert list(df.columns) == expected_columns

    def test_shareholders_returns_empty_dataframe(self):
        """shareholders() should return empty DataFrame with standard columns."""
        company = _make_company()
        df = company.shareholders()

        assert isinstance(df, pd.DataFrame)
        assert df.empty
        expected_columns = [
            "symbol",
            "shareholder_name",
            "shareholder_type",
            "ownership_percent",
            "shares_held",
            "is_major",
        ]
        assert list(df.columns) == expected_columns

    def test_officers_returns_empty_dataframe(self):
        """officers() should return empty DataFrame with standard columns."""
        company = _make_company()
        df = company.officers()

        assert isinstance(df, pd.DataFrame)
        assert df.empty
        expected_columns = [
            "symbol",
            "officer_name",
            "position",
            "position_en",
            "shares_held",
            "ownership_percent",
            "is_insider",
        ]
        assert list(df.columns) == expected_columns

    def test_subsidiaries_returns_empty_dataframe(self):
        """subsidiaries() should return empty DataFrame with standard columns."""
        company = _make_company()
        df = company.subsidiaries()

        assert isinstance(df, pd.DataFrame)
        assert df.empty
        expected_columns = [
            "symbol",
            "organ_name",
            "ownership_percent",
            "sub_organ_code",
        ]
        assert list(df.columns) == expected_columns

    def test_affiliate_returns_empty_dataframe(self):
        """affiliate() should return empty DataFrame with standard columns."""
        company = _make_company()
        df = company.affiliate()

        assert isinstance(df, pd.DataFrame)
        assert df.empty
        expected_columns = [
            "symbol",
            "organ_name",
            "ownership_percent",
            "sub_organ_code",
        ]
        assert list(df.columns) == expected_columns

    def test_news_returns_empty_dataframe(self):
        """news() should return empty DataFrame with standard columns."""
        company = _make_company()
        df = company.news()

        assert isinstance(df, pd.DataFrame)
        assert df.empty
        expected_columns = [
            "symbol",
            "title",
            "content",
            "publish_date",
            "source",
            "url",
        ]
        assert list(df.columns) == expected_columns

    def test_events_returns_empty_dataframe(self):
        """events() should return empty DataFrame with standard columns."""
        company = _make_company()
        df = company.events()

        assert isinstance(df, pd.DataFrame)
        assert df.empty
        expected_columns = [
            "symbol",
            "event_code",
            "event_name",
            "public_date",
            "record_date",
            "exright_date",
            "issue_date",
            "cash_dividend",
            "stock_dividend",
            "ratio",
            "note",
        ]
        assert list(df.columns) == expected_columns

    def test_trading_stats_returns_empty_dataframe(self):
        """trading_stats() should return empty DataFrame with standard columns."""
        company = _make_company()
        df = company.trading_stats()

        assert isinstance(df, pd.DataFrame)
        assert df.empty
        expected_columns = [
            "symbol",
            "avg_volume_10d",
            "avg_volume_30d",
            "avg_volume_90d",
            "volatility_10d",
            "volatility_30d",
            "beta",
            "sharpe_ratio",
        ]
        assert list(df.columns) == expected_columns

    def test_ratio_summary_returns_empty_dataframe(self):
        """ratio_summary() should return empty DataFrame with standard columns."""
        company = _make_company()
        df = company.ratio_summary()

        assert isinstance(df, pd.DataFrame)
        assert df.empty
        expected_columns = [
            "symbol",
            "pe",
            "pb",
            "roe",
            "roa",
            "ros",
            "eps",
            "bvps",
            "dividend_yield",
            "payout_ratio",
            "current_ratio",
            "quick_ratio",
            "debt_to_equity",
            "interest_coverage",
        ]
        assert list(df.columns) == expected_columns

    def test_all_methods_accept_kwargs(self):
        """All methods should accept arbitrary kwargs without error."""
        company = _make_company()

        # Should not raise any exception
        company.overview(extra_param="test")
        company.shareholders(filter_by="major")
        company.officers(filter_by="working")
        company.subsidiaries(filter_by="all")
        company.affiliate(some_param=123)
        company.news(page=1, size=10)
        company.events(event_codes="DIV", from_date="2024-01-01")
        company.trading_stats(period="1M")
        company.ratio_summary(period="quarter")


class TestDNSECompanyLogging:
    """Tests for logging behavior."""

    def test_logs_warning_when_show_log_true(self, caplog):
        """Should log warning when show_log=True and method called."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            company = DNSECompany("VNM", show_log=True)

        with caplog.at_level("WARNING"):
            company.overview()

        assert any("DNSE OpenAPI does not support company endpoints" in record.message for record in caplog.records)

    def test_no_warning_when_show_log_false(self, caplog):
        """Should not log warning when show_log=False."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            company = DNSECompany("VNM", show_log=False)

        with caplog.at_level("WARNING"):
            company.overview()

        assert not any("DNSE OpenAPI does not support company endpoints" in record.message for record in caplog.records)

    def test_logs_info_on_init_when_show_log_true(self, caplog):
        """Should log info on initialization when show_log=True."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            with caplog.at_level("INFO"):
                DNSECompany("VNM", show_log=True)

        assert any("DNSECompany initialized for VNM" in record.message for record in caplog.records)


class TestDNSECompanyProviderRegistry:
    """Tests for ProviderRegistry integration."""

    def test_provider_registered(self):
        """DNSECompany should be registered in ProviderRegistry."""
        from vnbroker import _ensure_explorer_modules_loaded
        from vnbroker.core.registry import ProviderRegistry

        _ensure_explorer_modules_loaded()
        assert ProviderRegistry.is_registered("company", "dnse")

    def test_provider_class_correct(self):
        """Registered provider should be DNSECompany class."""
        from vnbroker import _ensure_explorer_modules_loaded
        from vnbroker.core.registry import ProviderRegistry

        _ensure_explorer_modules_loaded()
        provider_class = ProviderRegistry.get("company", "dnse")
        assert provider_class is DNSECompany