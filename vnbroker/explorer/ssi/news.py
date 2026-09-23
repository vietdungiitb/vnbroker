"""
vnbroker/explorer/ssi/news.py

SSI News provider - fallback implementation since SSI FastConnect Data
does not provide news endpoints.

Lane stock() wires News-SSI directly to VCI (like DNSE); this class serves
lane api/ with empty standard-schema frames (AC-N1.1).
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from vnbroker.core.registry import ProviderRegistry  # noqa: E402, F401
from vnbroker.core.utils.logger import get_logger
from vnbroker.explorer.ssi._auth import resolve_credentials

logger = get_logger(__name__)

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


class SSINews:
    """
    SSI News provider - fallback implementation.

    SSI FastConnect Data has no news endpoints; every method returns an
    empty DataFrame with the standard schema.

    Args:
        symbol: Stock symbol (optional).
        api_key: SSI consumerID (falls back to ``VNBROKER_BROKER_SSI_API_KEY``).
        api_secret: SSI consumerSecret (falls back to ``VNBROKER_BROKER_SSI_API_SECRET``).
        show_log: Show log messages.
    """

    def __init__(
        self,
        symbol: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        show_log: bool = False,
        **kwargs: object,
    ) -> None:
        self.symbol = (symbol or "").upper() if symbol else None
        self.show_log = show_log
        # Fail fast on missing credentials (consistent with native providers).
        resolve_credentials(api_key, api_secret)
        if self.show_log:
            logger.info("SSINews initialized (fallback mode - no SSI news endpoints)")

    @staticmethod
    def _empty_df() -> pd.DataFrame:
        """Return empty DataFrame with the standard news columns."""
        return pd.DataFrame(columns=_NEWS_COLUMNS)

    def latest(self, symbol: Optional[str] = None, **kwargs: object) -> pd.DataFrame:
        """Latest news (empty - lane stock() serves VCI instead)."""
        return self._empty_df()

    def market_news(self, **kwargs: object) -> pd.DataFrame:
        """Market news alias (empty)."""
        return self._empty_df()

    def search(self, query: str = "", **kwargs: object) -> pd.DataFrame:
        """News search (empty)."""
        return self._empty_df()

    def by_symbol(self, symbol: str = "", **kwargs: object) -> pd.DataFrame:
        """News by symbol (empty)."""
        return self._empty_df()


ProviderRegistry.register("news", "ssi", SSINews)
