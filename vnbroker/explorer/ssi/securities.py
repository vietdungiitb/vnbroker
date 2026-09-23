"""
vnbroker/explorer/ssi/securities.py

SSI Securities helpers (T2 enhanced) — thin normalized wrappers around
``securitiesSummary`` / ``masterdata`` for foreign-room analysis and
board enrichment. Used directly and by ``SSIScreener`` / ``SSITrading``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

import pandas as pd

from vnbroker.broker.ssi.market import SSIMarketService
from vnbroker.core.registry import ProviderRegistry  # noqa: E402, F401
from vnbroker.core.utils.cache import cached_listing
from vnbroker.core.utils.logger import get_logger
from vnbroker.explorer.ssi._auth import get_shared_session, resolve_credentials

logger = get_logger(__name__)

_MASTER_TTL = 60  # match SSITrading._master_frame cadence


class SSISecurities:
    """
    SSI securities helpers (market-data lane, T2 enhanced).

    Args:
        api_key: SSI consumerID (falls back to ``VNBROKER_BROKER_SSI_API_KEY``).
        api_secret: SSI consumerSecret (falls back to ``VNBROKER_BROKER_SSI_API_SECRET``).
        show_log: Show log messages.
        _service: Test hook — inject an ``SSIMarketService`` double (no network).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        show_log: bool = False,
        _service: Optional[SSIMarketService] = None,
        **kwargs: Any,
    ) -> None:
        self.show_log = show_log
        if not show_log:
            logger.setLevel("CRITICAL")
        key, secret = resolve_credentials(api_key, api_secret)
        self._api_key = key
        self._api_secret = secret
        self._service = _service

    def _market(self) -> SSIMarketService:
        """Lazy service construction (first network use authenticates)."""
        if self._service is None:
            self._service = get_shared_session(
                self._api_key, self._api_secret
            ).market_service()
        return self._service

    @staticmethod
    def _norm_day(value: Optional[str]) -> Optional[str]:
        return value.strip().replace("-", "/") if value else None

    def summary(
        self,
        symbol: Optional[str] = None,
        index: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        Daily trading summary for one symbol — or bulk for an index.

        Args:
            symbol: Stock code (mutually exclusive with ``index``).
            index: Index code for bulk member summaries (e.g. ``VN30``).
            start/end: ``YYYY/MM/DD`` (or ``YYYY-MM-DD``); None = today.

        Returns:
            DataFrame with OHLC/average, match/deal totals and foreign
            columns, ``source_used=SSI``.
        """
        frame = self._market().get_securities_summary(
            symbol=symbol.strip().upper() if symbol else None,
            index=index.strip().upper() if index else None,
            from_date=self._norm_day(start),
            to_date=self._norm_day(end),
        )
        if not isinstance(frame, pd.DataFrame):
            frame = pd.DataFrame(frame)
        if not frame.empty:
            frame.attrs.update({"source": "SSI", "source_used": "SSI"})
        return frame

    @cached_listing(ttl_seconds=_MASTER_TTL)
    def master(
        self, trading_date: Optional[str] = None, **kwargs: Any
    ) -> pd.DataFrame:
        """
        Whole-market ceiling/floor/ref snapshot for one day.

        Args:
            trading_date: ``YYYY/MM/DD`` (or ``YYYY-MM-DD``); None = latest.

        Returns:
            DataFrame ``[board, symbol, trading_date, ceiling, floor, ref_price]``.
        """
        day = self._norm_day(trading_date)
        frame = self._market().get_master_data(from_date=day, to_date=day)
        if not isinstance(frame, pd.DataFrame):
            frame = pd.DataFrame(frame)
        if not frame.empty:
            frame.attrs.update({"source": "SSI", "source_used": "SSI"})
        return frame

    def foreign_room(
        self,
        symbol: Optional[str] = None,
        index: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        Foreign flow + room subset of :meth:`summary`.

        Returns:
            Columns ``[symbol, trading_date, total_foreign_buy,
            total_foreign_buy_value, total_foreign_sell,
            total_foreign_sell_value, remain_foreign_room, total_foreign_room]``.
        """
        frame = self.summary(
            symbol=symbol, index=index, start=start, end=end, **kwargs
        )
        cols = [
            "symbol",
            "trading_date",
            "total_foreign_buy",
            "total_foreign_buy_value",
            "total_foreign_sell",
            "total_foreign_sell_value",
            "remain_foreign_room",
            "total_foreign_room",
        ]
        if frame.empty:
            out = pd.DataFrame(columns=cols)
        else:
            out = frame[[c for c in cols if c in frame.columns]].copy()
        out.attrs.update(getattr(frame, "attrs", {}))
        return out


ProviderRegistry.register("securities", "ssi", SSISecurities)
