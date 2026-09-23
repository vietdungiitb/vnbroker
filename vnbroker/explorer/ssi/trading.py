"""
vnbroker/explorer/ssi/trading.py

SSI Trading provider - price_board from 1x master data (ceiling/floor/ref,
cached 60s) + Nx securities summary, mapped to the KBS
_PRICE_BOARD_STANDARD_COLUMNS subset (no bid/ask: SSI REST has none).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd

from vnbroker.broker.ssi.market import SSIMarketService
from vnbroker.core.registry import ProviderRegistry  # noqa: E402, F401
from vnbroker.core.utils.cache import cached_listing
from vnbroker.core.utils.logger import get_logger
from vnbroker.explorer.ssi._auth import get_shared_session, resolve_credentials

logger = get_logger(__name__)

PRICE_BOARD_COLUMNS = [
    "symbol",
    "time",
    "exchange",
    "ceiling_price",
    "floor_price",
    "reference_price",
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "average_price",
    "volume_accumulated",
    "total_value",
    "price_change",
    "percent_change",
    "foreign_buy_volume",
    "foreign_sell_volume",
]

_LARGE_BATCH = 20


class SSITrading:
    """
    SSI Trading provider (market-data lane).

    Args:
        symbol: Default symbol (kept for facade compatibility).
        api_key: SSI consumerID (falls back to ``VNBROKER_BROKER_SSI_API_KEY``).
        api_secret: SSI consumerSecret (falls back to ``VNBROKER_BROKER_SSI_API_SECRET``).
        show_log: Show log messages.
        _service: Test hook — inject an ``SSIMarketService`` double (no network).

    Example:
        >>> t = SSITrading("ACB", api_key="...", api_secret="...")
        >>> df = t.price_board(["ACB", "VNM"])
    """

    def __init__(
        self,
        symbol: Optional[str] = "ACB",
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        show_log: bool = False,
        _service: Optional[SSIMarketService] = None,
        **kwargs: Any,
    ) -> None:
        self.symbol = (symbol or "").upper()
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

    @cached_listing(ttl_seconds=60)
    def _master_frame(self, trading_day: str) -> pd.DataFrame:
        """Whole-market ceiling/floor/ref snapshot (1 request, cached 60s)."""
        frame = self._market().get_master_data(from_date=trading_day, to_date=trading_day)
        if not isinstance(frame, pd.DataFrame):
            return pd.DataFrame()
        return frame

    def price_board(self, symbols_list: List[str], **kwargs: Any) -> pd.DataFrame:
        """
        Realtime board for a symbol list (SSI-native loop).

        Cost: N ``securities_summary`` requests + 1 cached ``master_data``
        request. Batches > 20 log a warning (10 rps quota — use KBS instead).

        Args:
            symbols_list: Stock symbols (e.g. ``["ACB", "VNM"]``).

        Returns:
            DataFrame with the 17 KBS-compatible columns (no bid/ask).
        """
        if not symbols_list:
            raise ValueError("symbols_list không được để trống.")
        symbols = [str(s).upper() for s in symbols_list]
        if len(symbols) > _LARGE_BATCH:
            logger.warning(
                "SSI price_board batch %d mã: chậm/quota 10 rps — "
                "dùng source='KBS' cho batch lớn.",
                len(symbols),
            )
        service = self._market()
        today = date.today().strftime("%Y/%m/%d")
        master = self._master_frame(today)
        master_by_symbol: Dict[str, Any] = {}
        if not master.empty:
            for _, row in master.iterrows():
                master_by_symbol[str(row.get("symbol", ""))] = row

        rows: List[Dict[str, Any]] = []
        for symbol in symbols:
            summary = service.get_securities_summary(
                symbol=symbol, from_date=today, to_date=today
            )
            if not isinstance(summary, pd.DataFrame) or summary.empty:
                continue
            last = summary.iloc[-1]
            ref = master_by_symbol.get(symbol)
            rows.append(
                {
                    "symbol": symbol,
                    "time": pd.to_datetime(last.get("trading_date"), errors="coerce"),
                    "exchange": str(ref.get("board", "")) if ref is not None else "",
                    "ceiling_price": float(ref.get("ceiling")) if ref is not None else float("nan"),
                    "floor_price": float(ref.get("floor")) if ref is not None else float("nan"),
                    "reference_price": float(ref.get("ref_price")) if ref is not None else float("nan"),
                    "open_price": float(last.get("open", 0) or 0),
                    "high_price": float(last.get("high", 0) or 0),
                    "low_price": float(last.get("low", 0) or 0),
                    "close_price": float(last.get("close", 0) or 0),
                    "average_price": float(last.get("average", 0) or 0),
                    "volume_accumulated": int(last.get("total_match", 0) or 0),
                    "total_value": float(last.get("total_match_value", 0) or 0),
                    "price_change": float(last.get("price_change", 0) or 0),
                    "percent_change": float(last.get("price_change_percent", 0) or 0),
                    "foreign_buy_volume": int(last.get("total_foreign_buy", 0) or 0),
                    "foreign_sell_volume": int(last.get("total_foreign_sell", 0) or 0),
                }
            )
        out = pd.DataFrame(rows, columns=PRICE_BOARD_COLUMNS)
        out.attrs.update(
            {
                "symbols": symbols,
                "source": "SSI",
                "source_used": "SSI",
            }
        )
        return out


ProviderRegistry.register("trading", "ssi", SSITrading)
