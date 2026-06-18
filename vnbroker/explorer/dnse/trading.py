"""
vnbroker/explorer/dnse/trading.py

DNSE Trading provider - fallback implementation since DNSE OpenAPI
does not provide trading/price_board endpoints.

Returns empty DataFrames with proper schema to maintain API compatibility.
"""

from __future__ import annotations

import os
from typing import List, Optional, Union

import pandas as pd

from vnbroker.core.utils.logger import get_logger

logger = get_logger(__name__)

# Standard column schema for price_board (matching VCI/KBS/TCBS output)
# VCI returns MultiIndex columns with levels like:
# ('listing', 'symbol'), ('listing', 'exchange'), ('match', 'price'), ('match', 'volume'),
# ('bid_ask', 'bid_1_price'), ('bid_ask', 'bid_1_volume'), ('bid_ask', 'ask_1_price'), ('bid_ask', 'ask_1_volume'), ...
_PRICE_BOARD_COLUMNS = [
    ("listing", "symbol"),
    ("listing", "exchange"),
    ("listing", "organ_name"),
    ("listing", "ceiling_price"),
    ("listing", "floor_price"),
    ("listing", "ref_price"),
    ("match", "price"),
    ("match", "volume"),
    ("match", "change"),
    ("match", "pct_change"),
    ("bid_ask", "bid_1_price"),
    ("bid_ask", "bid_1_volume"),
    ("bid_ask", "ask_1_price"),
    ("bid_ask", "ask_1_volume"),
    ("bid_ask", "bid_2_price"),
    ("bid_ask", "bid_2_volume"),
    ("bid_ask", "ask_2_price"),
    ("bid_ask", "ask_2_volume"),
    ("bid_ask", "bid_3_price"),
    ("bid_ask", "bid_3_volume"),
    ("bid_ask", "ask_3_price"),
    ("bid_ask", "ask_3_volume"),
]


class DNSETrading:
    """
    DNSE Trading provider - fallback implementation.

    DNSE OpenAPI does not provide trading/price_board endpoints.
    This provider returns empty DataFrames with standard schemas
    to maintain API compatibility with other providers (VCI, KBS, TCBS).

    Usage:
        >>> trading = DNSETrading("VNM", api_key="...", api_secret="...")
        >>> df = trading.price_board(["VNM", "VCB"])
        >>> print(df.columns)  # Standard MultiIndex columns, empty DataFrame
    """

    def __init__(
        self,
        symbol: str = "VNM",
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        show_log: bool = False,
        **kwargs,
    ):
        """
        Initialize DNSE Trading provider.

        Args:
            symbol: Default stock symbol (e.g., "VNM")
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
                "DNSETrading initialized for %s (fallback mode - DNSE OpenAPI does not support trading endpoints)",
                self.symbol,
            )

    def _empty_price_board(self) -> pd.DataFrame:
        """Return empty DataFrame with standard price_board MultiIndex columns."""
        return pd.DataFrame(columns=pd.MultiIndex.from_tuples(_PRICE_BOARD_COLUMNS))

    def _log_fallback(self, method_name: str, symbols: Optional[List[str]] = None) -> None:
        """Log fallback message."""
        if self.show_log:
            sym_str = ", ".join(symbols) if symbols else self.symbol
            logger.warning(
                "DNSETrading.%s() called for %s - DNSE OpenAPI does not support trading endpoints. "
                "Returning empty DataFrame. Use VCI, KBS, or TCBS for trading data.",
                method_name,
                sym_str,
            )

    def price_board(
        self,
        symbols_list: List[str],
        show_log: Optional[bool] = False,
        flatten_columns: Optional[bool] = False,
        separator: Optional[str] = "_",
        drop_levels: Optional[Union[int, List[int]]] = None,
        price_unit: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Retrieve price board data for multiple symbols.

        Args:
            symbols_list: List of stock symbols
            show_log: Show log messages
            flatten_columns: Flatten MultiIndex columns
            separator: Separator for flattened columns
            drop_levels: Levels to drop when flattening
            price_unit: Target price unit (VND, THOUSAND_VND)

        Returns:
            pd.DataFrame: Empty DataFrame with standard price_board MultiIndex columns.
        """
        self._log_fallback("price_board", symbols_list)
        return self._empty_price_board()


# Register provider
from vnbroker.core.registry import ProviderRegistry  # noqa: E402, F401

ProviderRegistry.register("trading", "dnse", DNSETrading)