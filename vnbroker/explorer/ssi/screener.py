"""
vnbroker/explorer/ssi/screener.py

SSI Screener (T2 enhanced) — local filtering over ``securitiesByBoard``
(+ bulk ``securitiesSummary`` when an index is given). SSI has no server
screener endpoint, so filtering happens client-side.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

import pandas as pd

from vnbroker.broker.ssi.market import SSIMarketService
from vnbroker.core.registry import ProviderRegistry  # noqa: E402, F401
from vnbroker.core.utils.logger import get_logger
from vnbroker.explorer.ssi._auth import get_shared_session, resolve_credentials

logger = get_logger(__name__)

_STOCK_BOARDS = ("HOSE", "HNX", "UPCOM")

# Params honored from info rows alone (no per-symbol calls).
_INFO_FILTERS = {
    "min_listed_shares": "listed_shares",
    "icb": None,  # substring over icb_code + icb_name
}


class SSIScreener:
    """
    SSI stock screener (market-data lane, T2 enhanced).

    Args:
        api_key: SSI consumerID (falls back to ``VNBROKER_BROKER_SSI_API_KEY``).
        api_secret: SSI consumerSecret (falls back to ``VNBROKER_BROKER_SSI_API_SECRET``).
        show_log: Show log messages.
        _service: Test hook — inject an ``SSIMarketService`` double (no network).

    Example:
        >>> s = SSIScreener(api_key="...", api_secret="...")
        >>> df = s.stock(params={"exchangeName": "HOSE", "icb": "Ngân hàng"}, limit=20)
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

    def _universe(self, params: Dict[str, Any]) -> pd.DataFrame:
        service = self._market()
        index_name = str(params.get("indexName", "") or "").strip().upper()
        if index_name:
            frame = service.get_securities_info(index=index_name)
            return frame if isinstance(frame, pd.DataFrame) else pd.DataFrame(frame)
        raw_boards = str(params.get("exchangeName", "") or "").strip().upper()
        boards = (
            [b.strip() for b in raw_boards.split(",") if b.strip()]
            if raw_boards
            else list(_STOCK_BOARDS)
        )
        frames = []
        for board in boards:
            chunk = service.get_securities_info(board=board)
            if isinstance(chunk, pd.DataFrame) and not chunk.empty:
                frames.append(chunk)
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True).drop_duplicates(subset=["symbol"])

    def stock(
        self,
        params: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        Filter stocks by universe + info-level criteria.

        Supported ``params`` keys:
            - ``exchangeName``: e.g. ``"HOSE,HNX,UPCOM"`` (default all).
            - ``indexName``: e.g. ``"VN30"`` (uses index universe).
            - ``icb``: substring matched against ``icb_code``/``icb_name``.
            - ``min_listed_shares``: minimum ``listed_shares``.

        Liquidity filters (``min_total_match``/``min_total_match_value``)
        need bulk summaries, hence require ``indexName``.

        Returns:
            DataFrame (max ``limit`` rows) with ``source_used=SSI``.
        """
        filters = dict(params or {})
        for key in ("min_total_match", "min_total_match_value"):
            if filters.get(key) is not None and not str(
                filters.get("indexName", "") or ""
            ).strip():
                raise ValueError(
                    f"Lọc {key!r} cần indexName (bulk securitiesSummary); "
                    "hoặc dùng source='KBS'/'VCI' cho toàn thị trường."
                )
        frame = self._universe(filters)
        if frame.empty:
            return frame
        out = frame
        icb = str(filters.get("icb", "") or "").strip().lower()
        if icb and {"icb_code", "icb_name"} <= set(out.columns):
            mask = out["icb_code"].astype(str).str.lower().str.contains(
                icb, na=False
            ) | out["icb_name"].astype(str).str.lower().str.contains(icb, na=False)
            out = out[mask]
        min_shares = filters.get("min_listed_shares")
        if min_shares is not None and "listed_shares" in out.columns:
            out = out[
                pd.to_numeric(out["listed_shares"], errors="coerce")
                >= float(min_shares)
            ]
        for key in ("min_total_match", "min_total_match_value"):
            threshold = filters.get(key)
            if threshold is None:
                continue
            col = "total_match" if key == "min_total_match" else "total_match_value"
            service = self._market()
            index_name = str(filters.get("indexName", "") or "").strip().upper()
            summary = service.get_securities_summary(index=index_name)
            if not isinstance(summary, pd.DataFrame) or summary.empty:
                break
            liquid = set(
                summary.loc[
                    pd.to_numeric(summary[col], errors="coerce") >= float(threshold),
                    "symbol",
                ].astype(str)
            )
            out = out[out["symbol"].astype(str).isin(liquid)]
        out = out.head(int(limit)).reset_index(drop=True)
        out.attrs.update({"source": "SSI", "source_used": "SSI"})
        return out


ProviderRegistry.register("screener", "ssi", SSIScreener)
