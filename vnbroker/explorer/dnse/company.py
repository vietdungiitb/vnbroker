"""
vnbroker/explorer/dnse/company.py

DNSE Company provider - fallback implementation since DNSE OpenAPI
does not provide company information endpoints.

Returns empty DataFrames with proper schema to maintain API compatibility.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import pandas as pd

from vnbroker.core.utils.logger import get_logger

logger = get_logger(__name__)

# Standard column schemas for company data (matching VCI/KBS/TCBS output)
_OVERVIEW_COLUMNS = [
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

_SHAREHOLDERS_COLUMNS = [
    "symbol",
    "shareholder_name",
    "shareholder_type",
    "ownership_percent",
    "shares_held",
    "is_major",
]

_OFFICERS_COLUMNS = [
    "symbol",
    "officer_name",
    "position",
    "position_en",
    "shares_held",
    "ownership_percent",
    "is_insider",
]

_SUBSIDIARIES_COLUMNS = [
    "symbol",
    "organ_name",
    "ownership_percent",
    "sub_organ_code",
]

_AFFILIATE_COLUMNS = [
    "symbol",
    "organ_name",
    "ownership_percent",
    "sub_organ_code",
]

_NEWS_COLUMNS = [
    "symbol",
    "title",
    "content",
    "publish_date",
    "source",
    "url",
]

_EVENTS_COLUMNS = [
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

_TRADING_STATS_COLUMNS = [
    "symbol",
    "avg_volume_10d",
    "avg_volume_30d",
    "avg_volume_90d",
    "volatility_10d",
    "volatility_30d",
    "beta",
    "sharpe_ratio",
]

_RATIO_SUMMARY_COLUMNS = [
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


class DNSECompany:
    """
    DNSE Company provider - fallback implementation.

    DNSE OpenAPI does not provide company information endpoints.
    This provider returns empty DataFrames with standard schemas
    to maintain API compatibility with other providers (VCI, KBS, TCBS).

    Usage:
        >>> company = DNSECompany("VNM", api_key="...", api_secret="...")
        >>> df = company.overview()
        >>> print(df.columns)  # Standard columns, empty DataFrame
    """

    def __init__(
        self,
        symbol: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        show_log: bool = False,
        **kwargs,
    ):
        """
        Initialize DNSE Company provider.

        Args:
            symbol: Stock symbol (e.g., "VNM")
            api_key: DNSE API key (required for consistency with other providers)
            api_secret: DNSE API secret (required for consistency with other providers)
            show_log: Whether to show log messages
            **kwargs: Additional arguments for compatibility with ProviderRegistry
        """
        self.symbol = symbol.upper() if symbol else ""
        self.show_log = show_log

        # Validate credentials (same pattern as Quote/Listing)
        resolved_key = api_key or os.environ.get("DNSE_API_KEY", "")
        resolved_secret = api_secret or os.environ.get("DNSE_API_SECRET", "")

        if not resolved_key or not resolved_secret:
            raise ValueError(
                "DNSE cần api_key và api_secret. "
                "Đặt biến môi trường DNSE_API_KEY và DNSE_API_SECRET hoặc truyền trực tiếp. "
                "Đăng ký tại: https://developers.dnse.com.vn/"
            )

        if self.show_log:
            logger.info(
                "DNSECompany initialized for %s (fallback mode - DNSE OpenAPI does not support company endpoints)",
                self.symbol,
            )

    def _empty_df(self, columns: list[str]) -> pd.DataFrame:
        """Return empty DataFrame with specified columns."""
        return pd.DataFrame(columns=columns)

    def _log_fallback(self, method_name: str) -> None:
        """Log fallback message."""
        if self.show_log:
            logger.warning(
                "DNSECompany.%s() called for %s - DNSE OpenAPI does not support company endpoints. "
                "Returning empty DataFrame. Use VCI, KBS, or TCBS for company data.",
                method_name,
                self.symbol,
            )

    def overview(self, **kwargs) -> pd.DataFrame:
        """
        Retrieve company overview data.

        Returns:
            pd.DataFrame: Empty DataFrame with standard overview columns.
        """
        self._log_fallback("overview")
        return self._empty_df(_OVERVIEW_COLUMNS)

    def shareholders(self, **kwargs) -> pd.DataFrame:
        """
        Retrieve company shareholders data.

        Returns:
            pd.DataFrame: Empty DataFrame with standard shareholders columns.
        """
        self._log_fallback("shareholders")
        return self._empty_df(_SHAREHOLDERS_COLUMNS)

    def officers(self, **kwargs) -> pd.DataFrame:
        """
        Retrieve company officers data.

        Returns:
            pd.DataFrame: Empty DataFrame with standard officers columns.
        """
        self._log_fallback("officers")
        return self._empty_df(_OFFICERS_COLUMNS)

    def subsidiaries(self, **kwargs) -> pd.DataFrame:
        """
        Retrieve company subsidiaries data.

        Returns:
            pd.DataFrame: Empty DataFrame with standard subsidiaries columns.
        """
        self._log_fallback("subsidiaries")
        return self._empty_df(_SUBSIDIARIES_COLUMNS)

    def affiliate(self, **kwargs) -> pd.DataFrame:
        """
        Retrieve company affiliate data.

        Returns:
            pd.DataFrame: Empty DataFrame with standard affiliate columns.
        """
        self._log_fallback("affiliate")
        return self._empty_df(_AFFILIATE_COLUMNS)

    def news(self, **kwargs) -> pd.DataFrame:
        """
        Retrieve company news.

        Returns:
            pd.DataFrame: Empty DataFrame with standard news columns.
        """
        self._log_fallback("news")
        return self._empty_df(_NEWS_COLUMNS)

    def events(self, **kwargs) -> pd.DataFrame:
        """
        Retrieve company events (dividends, splits, etc.).

        Returns:
            pd.DataFrame: Empty DataFrame with standard events columns.
        """
        self._log_fallback("events")
        return self._empty_df(_EVENTS_COLUMNS)

    def trading_stats(self, **kwargs) -> pd.DataFrame:
        """
        Retrieve company trading statistics.

        Returns:
            pd.DataFrame: Empty DataFrame with standard trading stats columns.
        """
        self._log_fallback("trading_stats")
        return self._empty_df(_TRADING_STATS_COLUMNS)

    def ratio_summary(self, **kwargs) -> pd.DataFrame:
        """
        Retrieve company financial ratio summary.

        Returns:
            pd.DataFrame: Empty DataFrame with standard ratio summary columns.
        """
        self._log_fallback("ratio_summary")
        return self._empty_df(_RATIO_SUMMARY_COLUMNS)


# Register provider
from vnbroker.core.registry import ProviderRegistry  # noqa: E402, F401

ProviderRegistry.register("company", "dnse", DNSECompany)