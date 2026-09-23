"""
vnbroker/explorer/ssi/live.py

SSI Live lane (T3 realtime) — tick intraday, depth snapshot and session
snapshot. REST has no tick/depth endpoints, so realtime comes from the
FastConnect WebSocket (DATA channel); session reference prices come from
``masterdata`` REST (no WS round-trip needed).
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from vnbroker.broker.ssi.stream import MarketStatus, QuoteUpdate, TradeTick
from vnbroker.core.registry import ProviderRegistry  # noqa: E402, F401
from vnbroker.core.utils.logger import get_logger
from vnbroker.explorer.ssi._auth import get_shared_session, resolve_credentials

logger = get_logger(__name__)

_TICK_COLUMNS = ["time", "price", "volume", "side"]
_DEPTH_COLUMNS = ["side", "price", "volume"]
_SESSION_COLUMNS = ["symbol", "board", "trading_date", "ceiling", "floor", "ref"]
_FLAG_COLUMNS = ["market", "status", "trading_date"]


class SSILive:
    """
    SSI realtime collector (market-data lane, T3).

    Args:
        symbol: Default symbol (e.g. ``'ACB'``).
        api_key: SSI consumerID (falls back to ``VNBROKER_BROKER_SSI_API_KEY``).
        api_secret: SSI consumerSecret (falls back to ``VNBROKER_BROKER_SSI_API_SECRET``).
        show_log: Show log messages.
        _stream_factory: Test hook — ``callable()`` returning a stream-manager
            double with ``on_data`` setter, ``connect()``, ``subscribe_*``,
            ``wait(timeout)`` and ``disconnect()`` (no network).

    Example:
        >>> live = SSILive("ACB", api_key="...", api_secret="...")
        >>> ticks = live.intraday_ticks(timeout=20.0)  # needs market hours
    """

    def __init__(
        self,
        symbol: Optional[str] = "ACB",
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        show_log: bool = False,
        _stream_factory: Optional[Callable[[], Any]] = None,
        _service: Any = None,
        **kwargs: Any,
    ) -> None:
        self.symbol = (symbol or "").upper()
        self.show_log = show_log
        if not show_log:
            logger.setLevel("CRITICAL")
        key, secret = resolve_credentials(api_key, api_secret)
        self._api_key = key
        self._api_secret = secret
        self._stream_factory = _stream_factory
        self._service = _service

    def _stream(self) -> Any:
        if self._stream_factory is not None:
            return self._stream_factory()
        return get_shared_session(self._api_key, self._api_secret).stream_manager()

    def _market(self) -> Any:
        if self._service is not None:
            return self._service
        return get_shared_session(self._api_key, self._api_secret).market_service()

    def _collect(
        self,
        subscribe: Callable[[Any], None],
        accept: Callable[[Any], Optional[Dict[str, Any]]],
        timeout: float,
    ) -> List[Dict[str, Any]]:
        """Connect, subscribe, gather accepted records until ``timeout``."""
        if timeout is not None and float(timeout) <= 0:
            raise ValueError("timeout phải > 0.")
        stream = self._stream()
        rows: List[Dict[str, Any]] = []
        lock = threading.Lock()

        def _on_msg(msg: Any) -> None:
            record = accept(msg)
            if record is not None:
                with lock:
                    rows.append(record)

        stream.on_data = _on_msg
        stream.connect()
        try:
            subscribe(stream)
            stream.wait(timeout=timeout)
        finally:
            try:
                stream.disconnect()
            except Exception as exc:  # never hide collected rows
                logger.debug("SSI live disconnect: %s", exc)
        with lock:
            return list(rows)

    def intraday_ticks(
        self,
        symbol: Optional[str] = None,
        timeout: float = 20.0,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        Tick-by-tick trades for one symbol (WS ``trade.<SYM>``).

        Args:
            symbol: Defaults to the instance symbol.
            timeout: Collection window in seconds (> 0).

        Returns:
            DataFrame ``[time, price, volume, side]`` (may be empty
            outside market hours).
        """
        code = (symbol or self.symbol or "").strip().upper()
        if not code:
            raise ValueError("symbol không được để trống.")

        def _accept(msg: Any) -> Optional[Dict[str, Any]]:
            if not isinstance(msg, TradeTick) or msg.symbol.upper() != code:
                return None
            return {
                "time": pd.to_datetime(msg.trading_time, errors="coerce"),
                "price": float(msg.price),
                "volume": int(msg.quantity),
                "side": str(msg.side or "U"),
            }

        rows = self._collect(
            lambda stream: stream.subscribe_symbol_trade([code]),
            _accept,
            timeout,
        )
        out = pd.DataFrame(rows, columns=_TICK_COLUMNS)
        if not out.empty:
            out = out.sort_values("time").reset_index(drop=True)
        out.attrs.update({"source": "SSI", "source_used": "SSI", "symbol": code})
        return out

    def depth_snapshot(
        self,
        symbol: Optional[str] = None,
        timeout: float = 15.0,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        Latest bid/ask ladder for one symbol (WS ``quote.<SYM>``).

        Returns:
            DataFrame ``[side, price, volume]`` (``side`` in ``{BID, ASK}``),
            empty outside market hours.
        """
        code = (symbol or self.symbol or "").strip().upper()
        if not code:
            raise ValueError("symbol không được để trống.")
        latest: Dict[str, Any] = {}

        def _accept(msg: Any) -> Optional[Dict[str, Any]]:
            if not isinstance(msg, QuoteUpdate) or msg.symbol.upper() != code:
                return None
            latest["msg"] = msg
            return None  # only the last snapshot is kept

        self._collect(
            lambda stream: stream.subscribe_symbol_quote([code]),
            _accept,
            timeout,
        )
        msg = latest.get("msg")
        rows: List[Dict[str, Any]] = []
        if msg is not None:
            for price, volume in zip(msg.bid_prices, msg.bid_volumes):
                rows.append({"side": "BID", "price": float(price), "volume": int(volume)})
            for price, volume in zip(msg.ask_prices, msg.ask_volumes):
                rows.append({"side": "ASK", "price": float(price), "volume": int(volume)})
        out = pd.DataFrame(rows, columns=_DEPTH_COLUMNS)
        out.attrs.update({"source": "SSI", "source_used": "SSI", "symbol": code})
        return out

    def session_flags(
        self,
        symbols_list: List[str],
        timeout: float = 15.0,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        Session flags for symbols (WS ``market.<SYM>`` — P4a).

        Args:
            symbols_list: Symbols (or boards/indices) to watch.
            timeout: Collection window in seconds (> 0).

        Returns:
            DataFrame ``[market, status, trading_date]`` (may be empty
            outside market hours).
        """
        symbols = [str(s).strip().upper() for s in symbols_list if str(s).strip()]
        if not symbols:
            raise ValueError("symbols_list không được để trống.")

        def _accept(msg: Any) -> Optional[Dict[str, Any]]:
            if not isinstance(msg, MarketStatus):
                return None
            return {
                "market": str(msg.market),
                "status": str(msg.status),
                "trading_date": str(msg.trading_date),
            }

        rows = self._collect(
            lambda stream: stream.subscribe_symbol_market_status(symbols),
            _accept,
            timeout,
        )
        out = pd.DataFrame(rows, columns=_FLAG_COLUMNS)
        out.attrs.update(
            {"source": "SSI", "source_used": "SSI", "symbols": symbols}
        )
        return out

    def session_snapshot(
        self,
        symbols_list: List[str],
        trading_date: Optional[str] = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        Session reference prices (REST ``masterdata`` — no WS needed).

        Args:
            symbols_list: Symbols to keep (empty → all).
            trading_date: ``YYYY/MM/DD`` (or ``YYYY-MM-DD``); None = latest.

        Returns:
            DataFrame ``[symbol, board, trading_date, ceiling, floor, ref]``.
        """
        day = trading_date.strip().replace("-", "/") if trading_date else None
        frame = self._market().get_master_data(from_date=day, to_date=day)
        if not isinstance(frame, pd.DataFrame):
            frame = pd.DataFrame(frame)
        if frame.empty:
            return pd.DataFrame(columns=_SESSION_COLUMNS)
        rename = {
            "exchange": "board",
            "ref_price": "ref",
        }
        for src, dst in rename.items():
            if src in frame.columns and dst not in frame.columns:
                frame = frame.rename(columns={src: dst})
        wanted = [str(s).upper() for s in (symbols_list or [])]
        if wanted:
            frame = frame[frame["symbol"].astype(str).str.upper().isin(wanted)]
        cols = [c for c in _SESSION_COLUMNS if c in frame.columns]
        out = frame[cols].reset_index(drop=True)
        out.attrs.update({"source": "SSI", "source_used": "SSI"})
        return out


ProviderRegistry.register("live", "ssi", SSILive)
