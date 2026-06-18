"""
vnbroker/explorer/vci/screener.py

VCI Stock Screener - fallback implementation since VCI
does not currently provide a dedicated screener endpoint.

Returns empty DataFrame with proper schema to maintain API compatibility.
"""

from __future__ import annotations

from typing import Dict, Any, Optional

import pandas as pd

from vnbroker.core.utils.logger import get_logger
from vnbroker.core.utils.execution import optimize_execution

logger = get_logger(__name__)

# Standard column schema for screener output (matching TCBS output)
_SCREENER_COLUMNS = [
    "symbol",
    "exchange",
    "industry",
    "close_price",
    "change_pct",
    "volume",
    "market_cap",
    "pe",
    "pb",
    "roe",
    "roa",
    "eps",
    "bvps",
    "dividend_yield",
    "foreign_ownership_pct",
    "foreign_room_pct",
    "price_vs_sma20",
    "price_vs_sma50",
    "price_vs_sma200",
    "rsi14",
    "macd_signal",
    "bollinger_signal",
    "tcbs_recommend",
    "tcbs_buy_sell_signal",
]


class VCIScreener:
    """
    VCI Stock Screener - fallback implementation.

    VCI does not currently provide a dedicated stock screener endpoint.
    This provider returns empty DataFrame with standard schema
    to maintain API compatibility with TCBS screener.

    Usage:
        >>> screener = VCIScreener()
        >>> df = screener.stock(params={"exchangeName": "HOSE,HNX,UPCOM"}, limit=50)
        >>> print(df.columns)  # Standard columns, empty DataFrame
    """

    def __init__(
        self,
        random_agent: bool = False,
        show_log: bool = False,
        auth_token: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize VCI Screener.

        Args:
            random_agent: Whether to use random user agent
            show_log: Whether to show log messages
            auth_token: Auth token (for compatibility)
            **kwargs: Additional arguments for compatibility
        """
        self.data_source = "VCI"
        self.show_log = show_log
        self.auth_token = auth_token

        if self.show_log:
            logger.info(
                "VCIScreener initialized (fallback mode - VCI does not support screener endpoints). "
                "Use TCBS for stock screening."
            )

    def _empty_df(self) -> pd.DataFrame:
        """Return empty DataFrame with standard screener columns."""
        return pd.DataFrame(columns=_SCREENER_COLUMNS)

    def _log_fallback(self, method_name: str) -> None:
        """Log fallback message."""
        if self.show_log:
            logger.warning(
                "VCIScreener.%s() called - VCI does not support screener endpoints. "
                "Returning empty DataFrame. Use TCBS for stock screening.",
                method_name,
            )

    @optimize_execution("VCI")
    def stock(
        self,
        params: Dict[str, Any] = {"exchangeName": "HOSE,HNX,UPCOM"},
        limit: int = 50,
        id: Optional[str] = None,
        lang: str = "vi",
    ) -> pd.DataFrame:
        """
        Get stock screening insights (fallback).

        Args:
            params: Screening parameters (ignored in fallback)
            limit: Number of results (ignored in fallback)
            id: Optional screener ID (ignored in fallback)
            lang: Language (ignored in fallback)

        Returns:
            pd.DataFrame: Empty DataFrame with standard screener columns.
        """
        self._log_fallback("stock")
        return self._empty_df()


# Register provider
from vnbroker.core.registry import ProviderRegistry  # noqa: E402, F401

ProviderRegistry.register("screener", "vci", VCIScreener)