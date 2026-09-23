"""
vnbroker.explorer.tcbs.websocket — TCBSWebSocketClient: async WebSocket client.

Handles connection management, heartbeat, reconnection, subscribe/unsubscribe,
and message parsing for TCBS iFlash WebSocket streams.

Streams:
  - ouranos: /ws/ouranos/v1/stream (market data: OHLC, OrderBook, Ticker, Trade)
  - aither:  /ws/aither (real-time matching info for stock)
  - nesoi:   /ws/nesoi (real-time matching info for derivatives)
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncGenerator, Optional

import websockets

from vnbroker.explorer.tcbs.ws_models import (
    MatchingEvent,
    OHLC,
    OrderBook,
    OrderBookLevel,
    StreamMessage,
    Ticker,
    Trade,
)

_logger = logging.getLogger("vnbroker.explorer.tcbs.websocket")

# WebSocket endpoint URLs
_WS_ENDPOINTS = {
    "ouranos": "wss://openapi.tcbs.com.vn/ws/ouranos/v1/stream",
    "aither": "wss://openapi.tcbs.com.vn/ws/aither",
    "nesoi": "wss://openapi.tcbs.com.vn/ws/nesoi",
}

# SIT endpoints
_WS_ENDPOINTS_SIT = {
    "ouranos": "wss://openapisit.tcbs.com.vn/ws/ouranos/v1/stream",
    "aither": "wss://openapisit.tcbs.com.vn/ws/aither",
    "nesoi": "wss://openapisit.tcbs.com.vn/ws/nesoi",
}


class StreamType(Enum):
    """Available WebSocket stream types."""
    OURANOS = "ouranos"
    AITHER = "aither"
    NESOI = "nesoi"


class TCBSWebSocketClient:
    """
    Async WebSocket client for TCBS iFlash OpenAPI.

    Usage:
        async with TCBSWebSocketClient() as client:
            await client.connect()
            await client.subscribe(["VNM", "HPG"], ["ohlc", "ticker"])
            async for msg in client.messages():
                print(msg)
    """

    def __init__(
        self,
        jwt_token: Optional[str] = None,
        use_sit: bool = False,
        heartbeat_interval: float = 2.0,
        reconnect_max_attempts: int = 10,
        reconnect_base_delay: float = 1.0,
        reconnect_max_delay: float = 60.0,
    ) -> None:
        self._jwt_token = jwt_token
        self._use_sit = use_sit
        self._heartbeat_interval = heartbeat_interval
        self._reconnect_max_attempts = reconnect_max_attempts
        self._reconnect_base_delay = reconnect_base_delay
        self._reconnect_max_delay = reconnect_max_delay

        self._ws: Optional[Any] = None
        self._connected = False
        self._subscriptions: list[dict[str, Any]] = []
        self._message_queue: asyncio.Queue[Optional[StreamMessage]] = asyncio.Queue()
        self._heartbeat_task: Optional[asyncio.Task[None]] = None
        self._receive_task: Optional[asyncio.Task[None]] = None
        self._reconnect_attempt = 0
        self._last_message_time = 0.0

    async def connect(self, stream_type: StreamType = StreamType.OURANOS) -> None:
        """
        Establish WebSocket connection.

        Args:
            stream_type: Which stream to connect to (ouranos, aither, nesoi).
        """
        endpoints = _WS_ENDPOINTS_SIT if self._use_sit else _WS_ENDPOINTS
        url = endpoints[stream_type.value]

        headers = {}
        if self._jwt_token:
            headers["Authorization"] = f"Bearer {self._jwt_token}"

        _logger.info("Connecting to TCBS WebSocket: %s", url)

        try:
            self._ws = await websockets.connect(
                url,
                additional_headers=headers,
                ping_interval=None,  # We handle heartbeat manually
                close_timeout=5,
            )
            self._connected = True
            self._reconnect_attempt = 0
            self._last_message_time = time.time()

            # Start heartbeat and receive loops
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self._receive_task = asyncio.create_task(self._message_handler_loop())

            _logger.info("TCBS WebSocket connected successfully")
        except Exception as exc:
            _logger.error("Failed to connect to TCBS WebSocket: %s", exc)
            raise

    async def disconnect(self) -> None:
        """Close WebSocket connection gracefully."""
        self._connected = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            await self._ws.close()
            self._ws = None

        _logger.info("TCBS WebSocket disconnected")

    async def subscribe(self, symbols: list[str], channels: list[str]) -> None:
        """
        Subscribe to symbols and channels.

        Args:
            symbols: List of symbols (e.g., ["VNM", "HPG", "FPT"]).
            channels: List of channels (e.g., ["ohlc", "ticker", "trade", "orderbook"]).
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        sub_msg = {
            "cmd": "subscribe",
            "symbols": symbols,
            "channels": channels,
        }
        self._subscriptions.append(sub_msg)

        await self._require_ws().send(json.dumps(sub_msg))
        _logger.info("Subscribed to symbols=%s channels=%s", symbols, channels)

    async def unsubscribe(self, symbols: list[str], channels: list[str]) -> None:
        """
        Unsubscribe from symbols and channels.

        Args:
            symbols: List of symbols to unsubscribe.
            channels: List of channels to unsubscribe.
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        unsub_msg = {
            "cmd": "unsubscribe",
            "symbols": symbols,
            "channels": channels,
        }
        await self._require_ws().send(json.dumps(unsub_msg))
        _logger.info("Unsubscribed from symbols=%s channels=%s", symbols, channels)

    async def messages(self) -> AsyncGenerator[StreamMessage, None]:
        """
        Async generator yielding parsed StreamMessage objects.

        Yields:
            StreamMessage: Parsed WebSocket message.
        """
        while True:
            msg = await self._message_queue.get()
            if msg is None:
                break
            yield msg

    async def _heartbeat_loop(self) -> None:
        """Send ping every heartbeat_interval seconds."""
        try:
            while self._connected:
                await asyncio.sleep(self._heartbeat_interval)
                if self._ws and self._connected:
                    try:
                        await self._ws.send(json.dumps({"cmd": "ping"}))
                        self._last_message_time = time.time()
                    except Exception as exc:
                        _logger.warning("Heartbeat failed: %s", exc)
                        break
        except asyncio.CancelledError:
            pass

    def _require_ws(self) -> Any:
        """Return the live connection or raise if not connected."""
        if self._ws is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._ws

    async def _message_handler_loop(self) -> None:
        """Receive and parse WebSocket messages."""
        try:
            while self._connected:
                try:
                    raw = await asyncio.wait_for(self._require_ws().recv(), timeout=30.0)
                    self._last_message_time = time.time()
                    msg = self._parse_message(raw)
                    if msg:
                        await self._message_queue.put(msg)
                except asyncio.TimeoutError:
                    # Check if we need to reconnect
                    if time.time() - self._last_message_time > 30:
                        _logger.warning("No messages received for 30s, reconnecting...")
                        await self._reconnect()
                except websockets.exceptions.ConnectionClosed:
                    _logger.warning("WebSocket connection closed")
                    await self._reconnect()
                    break
        except asyncio.CancelledError:
            pass

    def _parse_message(self, raw: str) -> Optional[StreamMessage]:
        """Parse raw WebSocket message into StreamMessage."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            _logger.warning("Invalid JSON message: %s", raw[:200])
            return None

        # Handle ping/pong
        if data.get("cmd") == "pong":
            return None

        channel = data.get("channel", data.get("type", "unknown"))
        symbol = data.get("symbol", "")
        timestamp = datetime.now(tz=timezone.utc)

        parsed_data = self._parse_channel_data(channel, data)

        return StreamMessage(
            channel=channel,
            symbol=symbol,
            data=parsed_data or data,
            timestamp=timestamp,
        )

    def _parse_channel_data(self, channel: str, data: dict[str, Any]) -> Any:
        """Parse channel-specific data into typed objects."""
        if channel in ("ohlc", "candle"):
            return self._parse_ohlc(data)
        elif channel == "orderbook":
            return self._parse_orderbook(data)
        elif channel == "ticker":
            return self._parse_ticker(data)
        elif channel == "trade":
            return self._parse_trade(data)
        elif channel == "matching":
            return self._parse_matching(data)
        return None

    def _parse_ohlc(self, data: dict[str, Any]) -> Optional[OHLC]:
        """Parse OHLC data."""
        try:
            return OHLC(
                symbol=data.get("symbol", ""),
                time=datetime.fromisoformat(data.get("time", "")) if data.get("time") else datetime.now(tz=timezone.utc),
                interval=data.get("interval", "1m"),
                open=float(data.get("open", 0)),
                high=float(data.get("high", 0)),
                low=float(data.get("low", 0)),
                close=float(data.get("close", 0)),
                volume=int(data.get("volume", 0)),
            )
        except (ValueError, TypeError):
            return None

    def _parse_orderbook(self, data: dict[str, Any]) -> Optional[OrderBook]:
        """Parse OrderBook data."""
        try:
            bids = [
                OrderBookLevel(price=float(b[0]), volume=int(b[1]))
                for b in data.get("bids", [])
            ]
            asks = [
                OrderBookLevel(price=float(a[0]), volume=int(a[1]))
                for a in data.get("asks", [])
            ]
            return OrderBook(
                symbol=data.get("symbol", ""),
                time=datetime.now(tz=timezone.utc),
                bids=bids,
                asks=asks,
            )
        except (ValueError, TypeError, IndexError):
            return None

    def _parse_ticker(self, data: dict[str, Any]) -> Optional[Ticker]:
        """Parse Ticker data."""
        try:
            return Ticker(
                symbol=data.get("symbol", ""),
                time=datetime.now(tz=timezone.utc),
                last_price=float(data.get("lastPrice", data.get("price", 0))),
                volume=int(data.get("volume", 0)),
                change=float(data.get("change", 0)),
                change_percent=float(data.get("changePercent", 0)),
                high=float(data.get("high", 0)),
                low=float(data.get("low", 0)),
                open=float(data.get("open", 0)),
                ref_price=float(data.get("refPrice", 0)),
                ceiling=float(data.get("ceiling", 0)),
                floor=float(data.get("floor", 0)),
            )
        except (ValueError, TypeError):
            return None

    def _parse_trade(self, data: dict[str, Any]) -> Optional[Trade]:
        """Parse Trade data."""
        try:
            return Trade(
                symbol=data.get("symbol", ""),
                time=datetime.fromisoformat(data.get("time", "")) if data.get("time") else datetime.now(tz=timezone.utc),
                price=float(data.get("price", 0)),
                volume=int(data.get("volume", 0)),
                match_type=data.get("matchType", data.get("a", "")),
            )
        except (ValueError, TypeError):
            return None

    def _parse_matching(self, data: dict[str, Any]) -> Optional[MatchingEvent]:
        """Parse MatchingEvent data (Aither/Nesoi streams)."""
        try:
            return MatchingEvent(
                order_id=data.get("orderId", data.get("orderID", "")),
                symbol=data.get("symbol", ""),
                side=data.get("side", data.get("execType", "")),
                quantity=int(data.get("quantity", data.get("orderQtty", 0))),
                price=float(data.get("price", 0)),
                status=data.get("status", ""),
                filled_quantity=int(data.get("filledQuantity", data.get("execQtty", 0))),
                account_no=data.get("accountNo", ""),
            )
        except (ValueError, TypeError):
            return None

    async def _reconnect(self) -> None:
        """Reconnect with exponential backoff."""
        if self._reconnect_attempt >= self._reconnect_max_attempts:
            _logger.error("Max reconnect attempts reached (%d)", self._reconnect_max_attempts)
            self._connected = False
            await self._message_queue.put(None)  # Signal end of stream
            return

        delay = min(
            self._reconnect_base_delay * (2 ** self._reconnect_attempt),
            self._reconnect_max_delay,
        )
        self._reconnect_attempt += 1

        _logger.info("Reconnecting in %.1fs (attempt %d/%d)", delay, self._reconnect_attempt, self._reconnect_max_attempts)
        await asyncio.sleep(delay)

        try:
            await self.connect()
            # Re-subscribe to previous subscriptions
            for sub in self._subscriptions:
                await self._require_ws().send(json.dumps(sub))
            _logger.info("Re-subscribed to %d subscriptions", len(self._subscriptions))
        except Exception as exc:
            _logger.error("Reconnect failed: %s", exc)
            await self._reconnect()

    async def __aenter__(self) -> "TCBSWebSocketClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.disconnect()

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._connected
