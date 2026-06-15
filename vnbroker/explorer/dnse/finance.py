"""
vnbroker/explorer/dnse/finance.py

DNSE Finance provider - fallback implementation since DNSE OpenAPI
does not provide financial statement endpoints.

Returns empty DataFrames with proper schema to maintain API compatibility.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import pandas as pd

from vnbroker.core.utils.logger import get_logger

logger = get_logger(__name__)

# Standard column schemas for financial data (matching VCI/KBS/TCBS output)
# Financial reports have: item, item_en, item_id, period1, period2, ...
_BALANCE_SHEET_COLUMNS = [
    "item",
    "item_en",
    "item_id",
]

_INCOME_STATEMENT_COLUMNS = [
    "item",
    "item_en",
    "item_id",
]

_CASH_FLOW_COLUMNS = [
    "item",
    "item_en",
    "item_id",
]

_RATIO_COLUMNS = [
    "item",
    "item_en",
    "item_id",
]


class DNSEFinance:
    """
    DNSE Finance provider - fallback implementation.

    DNSE OpenAPI does not provide financial statement endpoints.
    This provider returns empty DataFrames with standard schemas
    to maintain API compatibility with other providers (VCI, KBS, TCBS).

    Usage:
        >>> finance = DNSEFinance("VNM", api_key="...", api_secret="...")
        >>> df = finance.balance_sheet()
        >>> print(df.columns)  # Standard columns, empty DataFrame
    """

    def __init__(
        self,
        symbol: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        period: str = "quarter",
        get_all: bool = True,
        show_log: bool = False,
        **kwargs,
    ):
        """
        Initialize DNSE Finance provider.

        Args:
            symbol: Stock symbol (e.g., "VNM")
            api_key: DNSE API key (required for consistency with other providers)
            api_secret: DNSE API secret (required for consistency with other providers)
            period: Report period ('year' or 'quarter') - kept for compatibility
            get_all: Whether to get all fields - kept for compatibility
            show_log: Whether to show log messages
            **kwargs: Additional arguments for compatibility with ProviderRegistry
        """
        self.symbol = symbol.upper() if symbol else ""
        self.period = period
        self.get_all = get_all
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
                "DNSEFinance initialized for %s (fallback mode - DNSE OpenAPI does not support financial endpoints)",
                self.symbol,
            )

    def _empty_df(self, columns: list[str]) -> pd.DataFrame:
        """Return empty DataFrame with specified columns."""
        return pd.DataFrame(columns=columns)

    def _log_fallback(self, method_name: str) -> None:
        """Log fallback message."""
        if self.show_log:
            logger.warning(
                "DNSEFinance.%s() called for %s - DNSE OpenAPI does not support financial endpoints. "
                "Returning empty DataFrame. Use VCI, KBS, or TCBS for financial data.",
                method_name,
                self.symbol,
            )

    def balance_sheet(
        self,
        period: Optional[str] = None,
        lang: Optional[str] = "en",
        dropna: Optional[bool] = True,
        show_log: Optional[bool] = False,
        display_mode=None,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Retrieve balance sheet data.

        Args:
            period: Report period ('year' or 'quarter')
            lang: Language ('vi' or 'en')
            dropna: Drop columns with all zero values
            show_log: Show log messages
            display_mode: Display mode for columns (compatibility with KBS FieldDisplayMode)

        Returns:
            pd.DataFrame: Empty DataFrame with standard balance sheet columns.
        """
        self._log_fallback("balance_sheet")
        return self._empty_df(_BALANCE_SHEET_COLUMNS)

    def income_statement(
        self,
        period: Optional[str] = None,
        lang: Optional[str] = "en",
        dropna: Optional[bool] = True,
        show_log: Optional[bool] = False,
        display_mode=None,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Retrieve income statement data.

        Args:
            period: Report period ('year' or 'quarter')
            lang: Language ('vi' or 'en')
            dropna: Drop columns with all zero values
            show_log: Show log messages
            display_mode: Display mode for columns

        Returns:
            pd.DataFrame: Empty DataFrame with standard income statement columns.
        """
        self._log_fallback("income_statement")
        return self._empty_df(_INCOME_STATEMENT_COLUMNS)

    def cash_flow(
        self,
        period: Optional[str] = None,
        lang: Optional[str] = "en",
        dropna: Optional[bool] = True,
        show_log: Optional[bool] = False,
        display_mode=None,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Retrieve cash flow statement data.

        Args:
            period: Report period ('year' or 'quarter')
            lang: Language ('vi' or 'en')
            dropna: Drop columns with all zero values
            show_log: Show log messages
            display_mode: Display mode for columns

        Returns:
            pd.DataFrame: Empty DataFrame with standard cash flow columns.
        """
        self._log_fallback("cash_flow")
        return self._empty_df(_CASH_FLOW_COLUMNS)

    def ratio(
        self,
        period: Optional[str] = None,
        lang: Optional[str] = "en",
        dropna: Optional[bool] = True,
        show_log: Optional[bool] = False,
        display_mode=None,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Retrieve financial ratios data.

        Args:
            period: Report period ('year' or 'quarter')
            lang: Language ('vi' or 'en')
            dropna: Drop columns with all zero values
            show_log: Show log messages
            display_mode: Display mode for columns

        Returns:
            pd.DataFrame: Empty DataFrame with standard ratio columns.
        """
        self._log_fallback("ratio")
        return self._empty_df(_RATIO_COLUMNS)

    def financial_ratios(self, *args, **kwargs) -> pd.DataFrame:
        """Alias for ratio() for backward compatibility."""
        return self.ratio(*args, **kwargs)


# Register provider
from vnbroker.core.registry import ProviderRegistry  # noqa: E402, F401

ProviderRegistry.register("financial", "dnse", DNSEFinance)