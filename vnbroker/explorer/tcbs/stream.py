"""
vnbroker.explorer.tcbs.stream — typed async generators over the thesis streams.

Thin, typed facade over :class:`TCBSWebSocketClient`. The subscription surface is
unchanged (``use_sit`` flag, channel names, ``subscribe(symbols, channels)``
signature); the feeds behind it are the documented ``thesis`` price boards:

* ``/stream/normal`` — stock (HOSE, HNX, UPCOM)
* ``/stream/derivative`` — VN30F and friends
"""
from __future__ import annotations

import logging
from typing import AsyncGenerator, Dict, List, Optional

from vnbroker.explorer.tcbs.websocket import (
    StreamType,
    TCBSWebSocketClient,
    build_order_book,
    endpoint_for,
)
from vnbroker.explorer.tcbs.ws_models import (
    OHLC,
    OrderBook,
    Ticker,
    Trade,
    base_price_from_message,
    foreign_from_message,
    session_from_message,
    ticker_from_messages,
    trade_from_message,
)

_logger = logging.getLogger("vnbroker.explorer.tcbs.stream")

#: Channels carrying a full top-3 book.
_ORDERBOOK_CHANNELS = ("bi", "op")
#: Channels behind a ticker snapshot.
_TICKER_CHANNELS = ("bp", "mp", "tm")
#: Channels behind a session summary.
_SESSION_CHANNELS = ("mp",)


class TCBSStreamService:
    """High-level stream generators for TCBS thesis price-board data.

    Usage::

        service = TCBSStreamService(jwt_token="...")
        async for book in service.stream_orderbook(["FPT", "VCS"]):
            print(book.bids[0])
    """

    def __init__(
        self,
        jwt_token: Optional[str] = None,
        use_sit: bool = False,
        stream_type: StreamType = StreamType.NORMAL,
        heartbeat_interval: float = 2.0,
    ) -> None:
        self._jwt_token = jwt_token
        self._use_sit = use_sit
        self._stream_type = stream_type
        self._heartbeat_interval = heartbeat_interval
        self._client: Optional[TCBSWebSocketClient] = None

    @property
    def endpoint(self) -> str:
        """WSS URL this service connects to."""
        return endpoint_for(self._stream_type)

    @property
    def stream_type(self) -> StreamType:
        return self._stream_type

    async def _ensure_client(self, stream_type: Optional[StreamType] = None) -> TCBSWebSocketClient:
        """Connect (and authenticate) once, then reuse the socket."""
        target = stream_type or self._stream_type
        if self._client is None:
            self._client = TCBSWebSocketClient(
                jwt_token=self._jwt_token,
                use_sit=self._use_sit,
                stream_type=target,
                heartbeat_interval=self._heartbeat_interval,
            )
            await self._client.connect(target)
        return self._client

    async def stream_orderbook(
        self,
        symbols: List[str],
        stream_type: Optional[StreamType] = None,
    ) -> AsyncGenerator[OrderBook, None]:
        """Yield top-3 order books merged from the ``bi`` + ``op`` frames."""
        client = await self._ensure_client(stream_type)
        await client.subscribe(symbols, list(_ORDERBOOK_CHANNELS))
        pending: Dict[str, Dict[str, object]] = {}
        async for msg in client.messages():
            if msg.channel not in ("bid", "offer"):
                continue
            book = pending.setdefault(msg.symbol, {"bid": None, "offer": None})
            book[msg.channel] = msg
            if book["bid"] is not None or book["offer"] is not None:
                merged = build_order_book(book["bid"], book["offer"])  # type: ignore[arg-type]
                if merged is not None:
                    yield merged
                pending.pop(msg.symbol, None)

    async def stream_ticker_match(
        self,
        symbols: List[str],
        stream_type: Optional[StreamType] = None,
    ) -> AsyncGenerator[Trade, None]:
        """Yield each matched trade from the ``tm`` channel (``s|6`` / ``s|21``)."""
        client = await self._ensure_client(stream_type)
        await client.subscribe(symbols, ["tm"])
        async for msg in client.messages():
            trade = trade_from_message(msg)
            if trade is not None:
                yield trade

    async def stream_ticker(
        self,
        symbols: List[str],
        stream_type: Optional[StreamType] = None,
    ) -> AsyncGenerator[Ticker, None]:
        """Yield ticker snapshots assembled from ``bp`` + ``mp`` + ``tm`` frames."""
        client = await self._ensure_client(stream_type)
        await client.subscribe(symbols, list(_TICKER_CHANNELS))
        state: Dict[str, Dict[str, object]] = {}
        async for msg in client.messages():
            if msg.channel not in ("base_price", "session", "day_summary", "ticker_match"):
                continue
            entry = state.setdefault(msg.symbol, {})
            if msg.channel == "base_price":
                entry["bp"] = msg
            elif msg.channel in ("session", "day_summary"):
                entry["mp"] = msg
            else:
                entry["tm"] = msg
            ticker = ticker_from_messages(
                base_price=entry.get("bp"),  # type: ignore[arg-type]
                session=entry.get("mp"),  # type: ignore[arg-type]
                trade=entry.get("tm"),  # type: ignore[arg-type]
            )
            if ticker is not None:
                yield ticker

    async def stream_session(
        self,
        symbols: List[str],
        stream_type: Optional[StreamType] = None,
    ) -> AsyncGenerator[Dict[str, float], None]:
        """Yield session summaries (high/low/avg/open) from ``mp``."""
        client = await self._ensure_client(stream_type)
        await client.subscribe(symbols, list(_SESSION_CHANNELS))
        async for msg in client.messages():
            summary = session_from_message(msg)
            if summary is not None:
                yield summary

    async def stream_foreign(
        self,
        symbols: List[str],
        stream_type: Optional[StreamType] = None,
    ) -> AsyncGenerator[Dict[str, int], None]:
        """Yield foreign-investor room updates (``fe``, stock endpoint only)."""
        client = await self._ensure_client(stream_type)
        await client.subscribe(symbols, ["fe"])
        async for msg in client.messages():
            foreign = foreign_from_message(msg)
            if foreign is not None:
                yield foreign

    async def stream_base_price(
        self,
        symbols: List[str],
        stream_type: Optional[StreamType] = None,
    ) -> AsyncGenerator[Dict[str, float], None]:
        """Yield ceiling/floor/reference prices (``bp``, stock endpoint only)."""
        client = await self._ensure_client(stream_type)
        await client.subscribe(symbols, ["bp"])
        async for msg in client.messages():
            base = base_price_from_message(msg)
            if base is not None:
                yield base

    async def stream_messages(self, symbols: List[str], channels: List[str]) -> AsyncGenerator[object, None]:
        """Yield raw parsed frames for any channel combination (escape hatch)."""
        client = await self._ensure_client()
        await client.subscribe(symbols, channels)
        async for msg in client.messages():
            yield msg

    # -- compatibility shims -------------------------------------------------

    async def stream_trades(
        self,
        symbols: List[str],
        stream_type: Optional[StreamType] = None,
    ) -> AsyncGenerator[Trade, None]:
        """Backwards-compatible alias for :meth:`stream_ticker_match`."""
        async for trade in self.stream_ticker_match(symbols, stream_type):
            yield trade

    async def stream_ohlc(
        self,
        symbols: List[str],
        interval: str = "1m",
    ) -> AsyncGenerator[OHLC, None]:
        """Not available on the thesis price-board feeds.

        ``/stream/normal`` and ``/stream/derivative`` push trades and quotes,
        not candles. Use :func:`vnbroker.explorer.tcbs.quote.TCBSFetcher` for
        OHLC bars, or accumulate trades from :meth:`stream_ticker_match`.
        """
        raise NotImplementedError(
            "The TCBS thesis WebSocket has no OHLC channel. "
            "Use quote.py for bars, or stream_ticker_match() and aggregate."
        )

    async def stream_matching(
        self,
        stream_type: StreamType = StreamType.NORMAL,
    ) -> AsyncGenerator[object, None]:
        """Not available on the thesis price-board feeds.

        The documented streams carry no per-order matching channel; the previous
        aither/nesoi endpoints are not part of the v1.0.0 documentation.
        """
        raise NotImplementedError(
            "The TCBS thesis WebSocket has no per-order matching channel. "
            "Use stream_ticker_match() for public trade tape."
        )

    async def close(self) -> None:
        """Close the underlying connection."""
        if self._client:
            await self._client.disconnect()
            self._client = None

    async def __aenter__(self) -> "TCBSStreamService":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()