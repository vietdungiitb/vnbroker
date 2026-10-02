"""
vnbroker/explorer/ssi/indices.py

SSI Indices provider (T2 enhanced) — index list/members/summary/history
from FastConnect Data (indexList / indexSummary / securitiesByBoard /
securitiesSummary). No equivalent depth in KBS/VCI scrape lane.
"""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from vnbroker.broker.ssi.market import SSIMarketService
from vnbroker.core.registry import ProviderRegistry  # noqa: E402, F401
from vnbroker.core.utils.cache import cached_listing
from vnbroker.core.utils.logger import get_logger
from vnbroker.explorer.ssi._auth import get_shared_session, resolve_credentials

logger = get_logger(__name__)

_INDEX_LIST_TTL = 21600  # 6h — index universe rarely changes
_INDEX_SUMMARY_TTL = 300  # 5m — session totals move intraday


class SSIIndices:
    """
    SSI Indices provider (market-data lane, T2 enhanced).

    Args:
        api_key: SSI consumerID (falls back to ``VNBROKER_BROKER_SSI_API_KEY``).
        api_secret: SSI consumerSecret (falls back to ``VNBROKER_BROKER_SSI_API_SECRET``).
        show_log: Show log messages.
        _service: Test hook — inject an ``SSIMarketService`` double (no network).

    Example:
        >>> idx = SSIIndices(api_key="...", api_secret="...")
        >>> df = idx.index_list()
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

    @cached_listing(ttl_seconds=_INDEX_LIST_TTL)
    def index_list(self, board: Optional[str] = None, **kwargs: Any) -> pd.DataFrame:
        """
        All market indices, optionally filtered by board.

        Args:
            board: ``HOSE`` | ``HNX`` | ``UPCOM`` (None = all boards).

        Returns:
            DataFrame ``[index, index_name, board]`` with ``source_used=SSI``.
        """
        frame = self._market().get_indexes(
            board=board.strip().upper() if board else None
        )
        if not isinstance(frame, pd.DataFrame):
            frame = pd.DataFrame(frame)
        if not frame.empty:
            frame.attrs.update({"source": "SSI", "source_used": "SSI"})
        return frame

    def index_members(self, index: str, **kwargs: Any) -> pd.Series:
        """
        Constituent symbols of an index (e.g. ``VN30``).

        Returns:
            Series named ``symbol``.
        """
        frame = self._market().get_securities_info(index=(index or "").strip().upper())
        if not isinstance(frame, pd.DataFrame):
            frame = pd.DataFrame(frame)
        if frame.empty:
            return pd.Series(name="symbol", dtype=str)
        out = frame["symbol"].astype(str).rename("symbol").reset_index(drop=True)
        out.attrs.update({"source": "SSI", "source_used": "SSI", "index": index.upper()})
        return out

    @cached_listing(ttl_seconds=_INDEX_SUMMARY_TTL)
    def index_summary(
        self,
        index: Optional[str] = None,
        board: Optional[str] = None,
        trading_date: Optional[str] = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        Session totals for one index (or board).

        Args:
            index: Index code (e.g. ``VNINDEX``) — exactly one of index/board.
            board: ``HOSE`` | ``HNX`` | ``UPCOM``.
            trading_date: ``YYYY/MM/DD`` (or ``YYYY-MM-DD``); None = latest.

        Returns:
            Single-row DataFrame (advance/decline, match/deal totals, prop).
        """
        service = self._market()
        day = trading_date.strip().replace("-", "/") if trading_date else None
        if index:
            frame = service.get_index_summary(
                index=index.strip().upper(), trading_date=day
            )
        elif board:
            frame = service.get_board_summary(
                board=board.strip().upper(), trading_date=day
            )
        else:
            raise ValueError("Cần chính xác một trong hai: index hoặc board.")
        if not isinstance(frame, pd.DataFrame):
            frame = pd.DataFrame(frame)
        if not frame.empty:
            frame.attrs.update({"source": "SSI", "source_used": "SSI"})
        return frame

    def index_history(
        self,
        index: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        Daily OHLC + totals for an index over ``[start, end]``.

        Backed by ``securitiesSummary(index=...)`` (bulk, no N+1).

        Args:
            index: Index code (e.g. ``VN30``).
            start/end: ``YYYY/MM/DD`` (or ``YYYY-MM-DD``); None = today.

        Returns:
            DataFrame sorted by ``trading_date`` with ``source_used=SSI``.
        """
        service = self._market()
        code = (index or "").strip().upper()
        if not code:
            raise ValueError("index không được để trống.")
        norm = lambda v: v.strip().replace("-", "/") if v else None  # noqa: E731
        frame = service.get_securities_summary(
            index=code, from_date=norm(start), to_date=norm(end)
        )
        if not isinstance(frame, pd.DataFrame):
            frame = pd.DataFrame(frame)
        if frame.empty:
            return frame
        out = frame.sort_values("trading_date").reset_index(drop=True)
        out.attrs.update(
            {"source": "SSI", "source_used": "SSI", "index": code}
        )
        return out


ProviderRegistry.register("indices", "ssi", SSIIndices)
