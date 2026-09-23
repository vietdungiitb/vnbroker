"""Unit tests for SSI explorer ProviderRegistry registration."""

from __future__ import annotations

import vnbroker.explorer.ssi  # noqa: F401 - triggers registration
from vnbroker.core.registry import ProviderRegistry


class TestSSIRegistry:
    """AC-W1.3(a): registry contains SSI providers (extended per phase)."""

    def test_quote_registered(self) -> None:
        assert ProviderRegistry.is_registered("quote", "ssi")
        assert ProviderRegistry.get("quote", "ssi") is vnbroker.explorer.ssi.SSIQuote

    def test_listing_registered(self) -> None:
        assert ProviderRegistry.is_registered("listing", "ssi")
        assert ProviderRegistry.get("listing", "ssi") is vnbroker.explorer.ssi.SSIListing

    def test_trading_registered(self) -> None:
        assert ProviderRegistry.is_registered("trading", "ssi")
        assert ProviderRegistry.get("trading", "ssi") is vnbroker.explorer.ssi.SSITrading

    def test_company_registered(self) -> None:
        assert ProviderRegistry.is_registered("company", "ssi")
        assert ProviderRegistry.get("company", "ssi") is vnbroker.explorer.ssi.SSICompany

    def test_financial_registered(self) -> None:
        assert ProviderRegistry.is_registered("financial", "ssi")
        assert ProviderRegistry.get("financial", "ssi") is vnbroker.explorer.ssi.SSIFinancial

    def test_news_registered(self) -> None:
        assert ProviderRegistry.is_registered("news", "ssi")
        assert ProviderRegistry.get("news", "ssi") is vnbroker.explorer.ssi.SSINews
