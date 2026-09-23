"""
vnbroker.explorer.tcbs.stream — TCBSStreamService: high-level async stream generators.

Provides typed async generators for OHLC, OrderBook, Ticker, Trade, and Matching streams.
"""
from __future__ import annotations

import logging
from typing import AsyncGenerator, Optional

from vnbroker.explorer.tcbs.ws_models import (
    MatchingEvent,
    OHLC,
    OrderBook,
    Ticker,
    Trade,
)
from vnbroker.explorer.tcbs.websocket import StreamType, TCBSWebSocketClient

_logger = logging.getLogger("vnbroker.explorer.tcbs.stream")


class TCBSStreamService:
    """
    High-level stream service for TCBS iFlash WebSocket data.

    Usage:
        service = TCBSStreamService(jwt_token="...")
        async for ohlc in service.stream_ohlc(["VNM", "HPG"], interval="1m"):
            print(ohlc)
    """

    def __init__(
        self,
        jwt_token: Optional[str] = None,
        use_sit: bool = False,
    ) -> None:
        self._jwt_token = jwt_token
        self._use_sit = use_sit
        self._client: Optional[TCBSWebSocketClient] = None

    async def _ensure_client(self) -> TCBSWebSocketClient:
        """Ensure WebSocket client is connected."""
        if self._client is None:
            self._client = TCBSWebSocketClient(
                jwt_token=self._jwt_token,
                use_sit=self._use_sit,
            )
            await self._client.connect(StreamType.OURANOS)
        return self._client

    async def stream_ohlc(
        self,
        symbols: list[str],
        interval: str = "1m",
    ) -> AsyncGenerator[OHLC, None]:
        """
        Stream OHLC bars for given symbols.

        Args:
            symbols: List of symbols (e.g., ["VNM", "HPG"]).
            interval: Time interval (1m, 5m, 15m, 30m, 1H, 1D).

        Yields:
            OHLC: OHLC bar data.
        """
        client = await self._ensure_client()
        await client.subscribe(symbols, ["ohlc"])

        async for msg in client.messages():
            if msg.channel in ("ohlc", "candle") and isinstance(msg.data, OHLC):
                if msg.data.interval == interval:
                    yield msg.data

    async def stream_orderbook(
        self,
        symbols: list[str],
    ) -> AsyncGenerator[OrderBook, None]:
        """
        Stream order book snapshots for given symbols.

        Args:
            symbols: List of symbols.

        Yields:
            OrderBook: Order book snapshot.
        """
        client = await self._ensure_client()
        await client.subscribe(symbols, ["orderbook"])

        async for msg in client.messages():
            if msg.channel == "orderbook" and isinstance(msg.data, OrderBook):
                yield msg.data

    async def stream_ticker(
        self,
        symbols: list[str],
    ) -> AsyncGenerator[Ticker, None]:
        """
        Stream ticker snapshots for given symbols.

        Args:
            symbols: List of symbols.

        Yields:
            Ticker: Ticker snapshot.
        """
        client = await self._ensure_client()
        await client.subscribe(symbols, ["ticker"])

        async for msg in client.messages():
            if msg.channel == "ticker" and isinstance(msg.data, Ticker):
                yield msg.data

    async def stream_trades(
        self,
        symbols: list[str],
    ) -> AsyncGenerator[Trade, None]:
        """
        Stream individual trade events for given symbols.

        Args:
            symbols: List of symbols.

        Yields:
            Trade: Trade event.
        """
        client = await self._ensure_client()
        await client.subscribe(symbols, ["trade"])

        async for msg in client.messages():
            if msg.channel == "trade" and isinstance(msg.data, Trade):
                yield msg.data

    async def stream_matching(
        self,
        stream_type: StreamType = StreamType.AITHER,
    ) -> AsyncGenerator[MatchingEvent, None]:
        """
        Stream order matching events.

        Args:
            stream_type: AITHER for stock, NESOI for derivatives.

        Yields:
            MatchingEvent: Order matching event.
        """
        client = TCBSWebSocketClient(
            jwt_token=self._jwt_token,
            use_sit=self._use_sit,
        )
        await client.connect(stream_type)

        async for msg in client.messages():
            if msg.channel == "matching" and isinstance(msg.data, MatchingEvent):
                yield msg.data

        await client.disconnect()

    async def close(self) -> None:
        """Close WebSocket connection."""
        if self._client:
            await self._client.disconnect()
            self._client = None

    async def __aenter__(self) -> "TCBSStreamService":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
