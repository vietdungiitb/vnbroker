"""
vnbroker/explorer/ssi/listing.py

SSI Listing provider - symbols from securitiesByBoard (per-board loop)
normalized to DF[symbol, organ_name].

get_securities_info requires >=1 filter and has no pagination, so
all_symbols() loops HOSE/HNX/UPCOM and dedupes (AC-L1.1).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from vnbroker.broker.ssi.market import SSIMarketService
from vnbroker.core.registry import ProviderRegistry  # noqa: E402, F401
from vnbroker.core.utils.cache import cached_listing
from vnbroker.core.utils.logger import get_logger
from vnbroker.explorer.ssi._auth import get_shared_session, resolve_credentials

logger = get_logger(__name__)

_STOCK_BOARDS = ("HOSE", "HNX", "UPCOM")
_ALL_SYMBOLS_COLUMNS = ["symbol", "organ_name"]

_ALL_SYMBOLS_TTL = 21600  # 6h — listing universe changes slowly (P1 tiered TTL)


class SSIListing:
    """
    SSI Listing provider (market-data lane).

    Args:
        api_key: SSI consumerID (falls back to ``VNBROKER_BROKER_SSI_API_KEY``).
        api_secret: SSI consumerSecret (falls back to ``VNBROKER_BROKER_SSI_API_SECRET``).
        show_log: Show log messages.
        _service: Test hook — inject an ``SSIMarketService`` double (no network).

    Example:
        >>> lst = SSIListing(api_key="...", api_secret="...")
        >>> df = lst.all_symbols()
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
    def _standardize(frame: pd.DataFrame) -> pd.DataFrame:
        """Reduce securities-info output to DF[symbol, organ_name]."""
        if frame.empty:
            return pd.DataFrame(columns=_ALL_SYMBOLS_COLUMNS)
        out = pd.DataFrame(
            {
                "symbol": frame["symbol"].astype(str),
                "organ_name": frame["symbol_name_vi"].astype(str),
            }
        )
        return out

    @cached_listing(ttl_seconds=_ALL_SYMBOLS_TTL)
    def all_symbols(
        self, include_derivatives: bool = False, **kwargs: Any
    ) -> pd.DataFrame:
        """
        All stock symbols (HOSE + HNX + UPCOM, deduped).

        Args:
            include_derivatives: Also query the DERIVATIVES board.

        Returns:
            DataFrame with columns ``[symbol, organ_name]``.
        """
        service = self._market()
        boards: List[str] = list(_STOCK_BOARDS)
        if include_derivatives:
            boards.append("DERIVATIVES")
        frames = []
        for board in boards:
            chunk = service.get_securities_info(board=board)
            if isinstance(chunk, pd.DataFrame) and not chunk.empty:
                frames.append(chunk)
        if not frames:
            return pd.DataFrame(columns=_ALL_SYMBOLS_COLUMNS)
        out = pd.concat(frames, ignore_index=True)
        out = self._standardize(out).drop_duplicates(subset=["symbol"])
        return out.reset_index(drop=True)

    def symbols_by_exchange(
        self, exchange: str = "HOSE", **kwargs: Any
    ) -> pd.DataFrame:
        """
        Symbols of one exchange.

        Args:
            exchange: ``HOSE`` | ``HNX`` | ``UPCOM`` | ``DERIVATIVES``.

        Returns:
            DataFrame with columns ``[symbol, organ_name]``.
        """
        board = (exchange or "").strip().upper()
        frame = self._market().get_securities_info(board=board)
        if not isinstance(frame, pd.DataFrame):
            frame = pd.DataFrame(frame)
        return self._standardize(frame).reset_index(drop=True)

    def symbols_by_group(self, group: str = "VN30", **kwargs: Any) -> pd.Series:
        """
        Symbols of an index group (e.g. VN30).

        Returns:
            Series named ``symbol``.
        """
        frame = self._market().get_securities_info(index=(group or "").strip().upper())
        if not isinstance(frame, pd.DataFrame):
            frame = pd.DataFrame(frame)
        if frame.empty:
            return pd.Series(name="symbol", dtype=str)
        return frame["symbol"].astype(str).rename("symbol").reset_index(drop=True)

    def symbols_by_industries(self, **kwargs: Any) -> pd.DataFrame:
        """
        Symbols with ICB classification (SSI native ``icb_code/icb_name``).

        Returns:
            DataFrame with columns ``[symbol, organ_name, icb_code, icb_name]``.
        """
        service = self._market()
        frames = []
        for board in _STOCK_BOARDS:
            chunk = service.get_securities_info(board=board)
            if isinstance(chunk, pd.DataFrame) and not chunk.empty:
                frames.append(chunk)
        if not frames:
            return pd.DataFrame(columns=["symbol", "organ_name", "icb_code", "icb_name"])
        raw = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["symbol"])
        return pd.DataFrame(
            {
                "symbol": raw["symbol"].astype(str),
                "organ_name": raw["symbol_name_vi"].astype(str),
                "icb_code": raw["icb_code"].astype(str),
                "icb_name": raw["icb_name"].astype(str),
            }
        ).reset_index(drop=True)

    def industries_icb(self, **kwargs: Any) -> pd.DataFrame:
        """
        Distinct ICB industries from SSI native data.

        Returns:
            DataFrame with columns ``[icb_code, icb_name]``.
        """
        frame = self.symbols_by_industries()
        if frame.empty:
            return pd.DataFrame(columns=["icb_code", "icb_name"])
        return frame[["icb_code", "icb_name"]].drop_duplicates().reset_index(drop=True)

    def _unsupported(self, name: str) -> Any:
        raise NotImplementedError(
            f"SSI không cung cấp {name} qua FastConnect Data "
            "(response thiếu SecType); dùng source='KBS'/'VCI'."
        )

    def all_covered_warrant(self, **kwargs: Any) -> pd.Series:
        """Covered warrants (not available via SSI)."""
        return self._unsupported("covered warrant")

    def all_bonds(self, **kwargs: Any) -> pd.Series:
        """Bonds (not available via SSI)."""
        return self._unsupported("bonds")

    def all_future_indices(self, **kwargs: Any) -> pd.Series:
        """Futures indices (not available via SSI)."""
        return self._unsupported("futures indices")

    def all_government_bonds(self, **kwargs: Any) -> pd.Series:
        """Government bonds (not available via SSI)."""
        return self._unsupported("government bonds")


ProviderRegistry.register("listing", "ssi", SSIListing)
