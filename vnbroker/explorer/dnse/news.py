"""
vnbroker/explorer/dnse/news.py

DNSE News provider - fallback implementation since DNSE OpenAPI
does not provide news endpoints.

Returns empty DataFrames with proper schema to maintain API compatibility.
"""

from __future__ import annotations

import os
from typing import Optional

import pandas as pd

from vnbroker.core.utils.logger import get_logger

logger = get_logger(__name__)

# Standard column schema for news data (matching VCI/KBS/TCBS/RSS output)
_NEWS_COLUMNS = [
    "symbol",
    "title",
    "summary",
    "content",
    "publish_date",
    "source",
    "url",
    "image_url",
    "category",
]


class DNSENews:
    """
    DNSE News provider - fallback implementation.

    DNSE OpenAPI does not provide news endpoints.
    This provider returns empty DataFrames with standard schemas
    to maintain API compatibility with other providers (VCI, KBS, TCBS, RSS).

    Usage:
        >>> news = DNSENews(api_key="...", api_secret="...")
        >>> df = news.latest(symbol="VNM")
        >>> print(df.columns)  # Standard columns, empty DataFrame
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        show_log: bool = False,
        **kwargs,
    ):
        """
        Initialize DNSE News provider.

        Args:
            api_key: DNSE API key (required for consistency with other providers)
            api_secret: DNSE API secret (required for consistency with other providers)
            show_log: Whether to show log messages
            **kwargs: Additional arguments for compatibility with ProviderRegistry
        """
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
                "DNSENews initialized (fallback mode - DNSE OpenAPI does not support news endpoints)"
            )

    def _empty_df(self) -> pd.DataFrame:
        """Return empty DataFrame with standard news columns."""
        return pd.DataFrame(columns=_NEWS_COLUMNS)

    def _log_fallback(self, method_name: str, symbol: Optional[str] = None) -> None:
        """Log fallback message."""
        if self.show_log:
            sym_str = f" for {symbol}" if symbol else ""
            logger.warning(
                "DNSENews.%s() called%s - DNSE OpenAPI does not support news endpoints. "
                "Returning empty DataFrame. Use VCI, KBS, TCBS, RSS_CafeF, or RSS_VnEconomy for news data.",
                method_name,
                sym_str,
            )

    def latest(
        self,
        symbol: str = "",
        limit: int = 100,
        page: int = 1,
        page_size: int = 50,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Retrieve latest news.

        Args:
            symbol: Stock symbol (optional, for filtering)
            limit: Maximum number of news items
            page: Page number (for compatibility)
            page_size: Page size (for compatibility)

        Returns:
            pd.DataFrame: Empty DataFrame with standard news columns.
        """
        self._log_fallback("latest", symbol)
        return self._empty_df()

    def search(
        self,
        query: str,
        symbol: str = "",
        limit: int = 100,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Search news by query.

        Args:
            query: Search query string
            symbol: Stock symbol (optional)
            limit: Maximum number of news items

        Returns:
            pd.DataFrame: Empty DataFrame with standard news columns.
        """
        self._log_fallback("search", symbol)
        return self._empty_df()

    def by_symbol(
        self,
        symbol: str,
        limit: int = 100,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Retrieve news for a specific symbol.

        Args:
            symbol: Stock symbol
            limit: Maximum number of news items

        Returns:
            pd.DataFrame: Empty DataFrame with standard news columns.
        """
        self._log_fallback("by_symbol", symbol)
        return self._empty_df()

    def market_news(
        self,
        page: int = 1,
        page_size: int = 10,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Retrieve general market news.

        Args:
            page: Page number
            page_size: Page size

        Returns:
            pd.DataFrame: Empty DataFrame with standard news columns.
        """
        self._log_fallback("market_news")
        return self._empty_df()


# Register provider
from vnbroker.core.registry import ProviderRegistry  # noqa: E402, F401

ProviderRegistry.register("news", "dnse", DNSENews)