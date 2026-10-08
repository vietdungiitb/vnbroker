"""
vnbroker.api.bulk — Bulk API for multi-symbol, multi-provider operations.

Integrates BulkRouter, HealthRouter, and ProviderPool to provide a clean
user-facing API for fetching data across multiple symbols and providers.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from vnbroker.core.bulk_router import BulkRouter
from vnbroker.core.health_router import HealthRouter
from vnbroker.core.provider_pool import ProviderPool

logger = logging.getLogger(__name__)


class BulkAPI:
    """Bulk API for multi-symbol, multi-provider operations.

    Example:
        >>> from vnbroker.api.bulk import BulkAPI
        >>> api = BulkAPI(source="AUTO", show_log=False)
        >>> df = api.history(["ACB", "VNM", "FPT"], start="2024-01-01")
        >>> print(df.attrs["sources_used"])
    """

    def __init__(self, source: str = "AUTO", show_log: bool = False):
        self.source = source
        self.show_log = show_log
        self._health_router = HealthRouter()
        self._bulk_router = BulkRouter(self._health_router)
        self._provider_pool = ProviderPool()

    def history(
        self,
        symbols: List[str],
        start: str = None,
        end: str = None,
        interval: str = "1D",
    ) -> pd.DataFrame:
        """Fetch history for multiple symbols using multiple providers.

        Args:
            symbols: List of stock symbols to fetch.
            start: Start date (YYYY-MM-DD).
            end: End date (YYYY-MM-DD).
            interval: Data interval (1D, 1W, 1M, etc.).

        Returns:
            DataFrame with columns: time, open, high, low, close, volume, symbol
            attrs: sources_used, failed, requested, returned
        """
        if not symbols:
            return pd.DataFrame(
                columns=["time", "open", "high", "low", "close", "volume", "symbol"]
            )

        # 1. Get available providers
        providers = self._provider_pool.get_available_providers("quote")
        if not providers:
            raise ConnectionError("No providers available for quote module")

        # 2. Use BulkRouter to fetch concurrently
        result = self._bulk_router.fetch_history(symbols, start, end, "quote")

        # 3. Merge results into single DataFrame
        frames: List[pd.DataFrame] = []
        sources_used: Dict[str, str] = {}

        for provider, provider_results in result.get("results", {}).items():
            if isinstance(provider_results, list):
                for df in provider_results:
                    if isinstance(df, pd.DataFrame) and not df.empty:
                        sym = df.attrs.get("symbol", "unknown")
                        df["symbol"] = sym
                        frames.append(df)
                        sources_used[sym] = provider

        if not frames:
            empty = pd.DataFrame(
                columns=["time", "open", "high", "low", "close", "volume", "symbol"]
            )
            empty.attrs["sources_used"] = {}
            empty.attrs["failed"] = result.get("errors", {})
            empty.attrs["requested"] = len(symbols)
            empty.attrs["returned"] = 0
            return empty

        combined = pd.concat(frames, ignore_index=True)
        combined = combined.sort_values(["symbol", "time"]).reset_index(drop=True)

        # 4. Add metadata
        combined.attrs["sources_used"] = sources_used
        combined.attrs["failed"] = result.get("errors", {})
        combined.attrs["requested"] = len(symbols)
        combined.attrs["returned"] = len(frames)

        return combined

    def price_board(self, symbols: List[str] = None) -> pd.DataFrame:
        """Fetch price board for multiple symbols.

        Uses KBS price_board endpoint which supports bulk requests.

        Args:
            symbols: List of stock symbols. If None, fetches all symbols.

        Returns:
            DataFrame with price board data.
        """
        if symbols is not None and len(symbols) == 0:
            return pd.DataFrame()

        from vnbroker.common.data import Trading

        trading = Trading(source="KBS", show_log=self.show_log)

        if symbols is None:
            from vnbroker.common.data import Listing

            listing = Listing(source="KBS", show_log=self.show_log)
            symbols = listing.all_symbols()["symbol"].tolist()

        return trading.price_board(symbols)
