"""
vnbroker/explorer/ssi/financial.py

SSI Financial provider - fallback implementation since SSI FastConnect Data
does not provide financial statement endpoints.

Returns empty DataFrames with standard schemas so that
BaseComponent._call_with_fallback skips to KBS/VCI (AC-CFN-2).
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from vnbroker.core.registry import ProviderRegistry  # noqa: E402, F401
from vnbroker.core.utils.logger import get_logger

logger = get_logger(__name__)

# Long-format report schema: item, item_en, item_id (+ period columns when filled).
_BALANCE_SHEET_COLUMNS = ["item", "item_en", "item_id"]
_INCOME_STATEMENT_COLUMNS = ["item", "item_en", "item_id"]
_CASH_FLOW_COLUMNS = ["item", "item_en", "item_id"]
_RATIO_COLUMNS = ["item", "item_en", "item_id"]


class SSIFinancial:
    """
    SSI Financial provider - fallback implementation.

    SSI FastConnect Data has no financial statement endpoints; every method
    returns an empty DataFrame with the standard schema so facade fallback
    serves KBS/VCI data transparently.

    Args:
        symbol: Stock symbol (e.g. 'VNM').
        api_key: SSI consumerID (falls back to ``VNBROKER_BROKER_SSI_API_KEY``).
        api_secret: SSI consumerSecret (falls back to ``VNBROKER_BROKER_SSI_API_SECRET``).
        show_log: Show log messages.
    """

    def __init__(
        self,
        symbol: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        show_log: bool = False,
        **kwargs: object,
    ) -> None:
        self.symbol = (symbol or "").upper()
        self.show_log = show_log
        # No SSI financial endpoints exist, so credentials are never used here.
        # Do NOT fail fast: keep init lazy (W4) so facade fallback to KBS/VCI
        # works even when no SSI key is configured.
        self._api_key = api_key
        self._api_secret = api_secret
        if self.show_log:
            logger.info(
                "SSIFinancial initialized for %s (fallback mode - no SSI financial endpoints)",
                self.symbol,
            )

    @staticmethod
    def _empty_df(columns: list[str]) -> pd.DataFrame:
        """Return empty DataFrame with specified columns."""
        return pd.DataFrame(columns=columns)

    def _log_fallback(self, method_name: str) -> None:
        """Log fallback message."""
        if self.show_log:
            logger.warning(
                "SSIFinancial.%s() called for %s - no SSI financial endpoints. "
                "Returning empty DataFrame (facade falls back to KBS/VCI).",
                method_name,
                self.symbol,
            )

    def balance_sheet(self, **kwargs: object) -> pd.DataFrame:
        """Balance sheet (empty - falls back to KBS/VCI)."""
        self._log_fallback("balance_sheet")
        return self._empty_df(_BALANCE_SHEET_COLUMNS)

    def income_statement(self, **kwargs: object) -> pd.DataFrame:
        """Income statement (empty - falls back to KBS/VCI)."""
        self._log_fallback("income_statement")
        return self._empty_df(_INCOME_STATEMENT_COLUMNS)

    def cash_flow(self, **kwargs: object) -> pd.DataFrame:
        """Cash flow statement (empty - falls back to KBS/VCI)."""
        self._log_fallback("cash_flow")
        return self._empty_df(_CASH_FLOW_COLUMNS)

    def ratio(self, **kwargs: object) -> pd.DataFrame:
        """Financial ratios (empty - falls back to KBS/VCI)."""
        self._log_fallback("ratio")
        return self._empty_df(_RATIO_COLUMNS)

    def financial_ratios(self, **kwargs: object) -> pd.DataFrame:
        """Alias of ratio (matches KBS/VCI explorer convention)."""
        return self.ratio(**kwargs)


ProviderRegistry.register("financial", "ssi", SSIFinancial)
