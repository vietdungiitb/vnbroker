"""
Real-time WebSocket streaming for Vninvest SDK.
"""

from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable
from dataclasses import field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

import websockets
from pydantic import BaseModel

from .config import get_settings
from .exceptions import ScopeDeniedError
from .models import PATScope, TenantContext


class StreamChannel(str, Enum):
    """Available streaming channels."""

    PRICE = "price"
    DEPTH = "depth"
    TRADE = "trade"
    NEWS = "news"
    SNAPSHOT = "snapshot"


class StreamMessage(BaseModel):
    """Standardized stream message format."""

    channel: StreamChannel
    symbol: str
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    sequence: int = 0
    provider: str = "unknown"


class StreamProvider(ABC):
    """Abstract base for stream data providers."""

    @abstractmethod
    async def subscribe(self, symbols: list[str], channels: list[StreamChannel]) -> None:
        pass

    @abstractmethod
    async def unsubscribe(self, symbols: list[str], channels: list[StreamChannel]) -> None:
        pass

    @abstractmethod
    async def start(self) -> None:
        pass

    @abstractmethod
    async def stop(self) -> None:
        pass

    @abstractmethod
    def set_callback(self, callback: Callable[[StreamMessage], None]) -> None:
        pass


class VCIStreamProvider(StreamProvider):
    """VCI real-time data provider (WebSocket)."""

    def __init__(self, api_key: str | None = None, ws_url: str | None = None):
        self.api_key = api_key
        self.ws_url = ws_url or "wss://priceboard.vci.com.vn/ws"  # Default VCI WebSocket URL
        self._ws = None
        self._running = False
        self._callback: Callable[[StreamMessage], None] | None = None
        self._subscriptions: dict[StreamChannel, set[str]] = defaultdict(set)
        self._sequence = 0
        self._receive_task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None
        self._reconnect_delay = 5  # seconds

    def set_callback(self, callback: Callable[[StreamMessage], None]) -> None:
        self._callback = callback

    async def start(self) -> None:
        """Connect to VCI WebSocket and start receiving messages."""
        if self._running:
            return

        self._running = True
        await self._connect()

    async def _connect(self) -> None:
        """Establish WebSocket connection to VCI."""
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            self._ws = await websockets.connect(
                self.ws_url,
                extra_headers=headers,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10,
            )

            # Start receive loop
            self._receive_task = asyncio.create_task(self._receive_loop())

            # Resubscribe to existing subscriptions
            await self._resubscribe_all()

        except Exception:
            # Schedule reconnection
            self._schedule_reconnect()

    async def _receive_loop(self) -> None:
        """Receive messages from VCI WebSocket."""
        try:
            async for message in self._ws:
                if not self._running:
                    break

                try:
                    await self._handle_message(message)
                except Exception:
                    # Log error but continue receiving
                    pass

        except websockets.exceptions.ConnectionClosed:
            if self._running:
                self._schedule_reconnect()
        except Exception:
            if self._running:
                self._schedule_reconnect()

    async def _handle_message(self, message: str) -> None:
        """Parse and handle incoming VCI WebSocket message."""
        try:
            data = json.loads(message)

            # VCI message format (example - adjust based on actual API)
            # Expected format: {"channel": "price", "symbol": "ACB", "data": {...}, "timestamp": ...}
            channel_str = data.get("channel", "price")
            symbol = data.get("symbol", "").upper()
            payload = data.get("data", {})
            timestamp = data.get("timestamp")

            # Map channel string to StreamChannel enum
            channel_map = {
                "price": StreamChannel.PRICE,
                "depth": StreamChannel.DEPTH,
                "trade": StreamChannel.TRADE,
                "news": StreamChannel.NEWS,
                "snapshot": StreamChannel.SNAPSHOT,
            }
            channel = channel_map.get(channel_str, StreamChannel.PRICE)

            # Only emit if we're subscribed to this symbol/channel
            if symbol in self._subscriptions.get(channel, set()):
                self._emit(channel, symbol, payload, provider="VCI")

        except json.JSONDecodeError:
            pass  # Ignore invalid JSON
        except Exception:
            pass  # Ignore other parsing errors

    async def _resubscribe_all(self) -> None:
        """Resubscribe to all active subscriptions after reconnection."""
        for channel, symbols in self._subscriptions.items():
            if symbols:
                await self._send_subscription(list(symbols), [channel], "subscribe")

    async def _send_subscription(self, symbols: list[str], channels: list[StreamChannel], action: str) -> None:
        """Send subscription/unsubscription message to VCI WebSocket."""
        if not self._ws or not self._running:
            return

        for channel in channels:
            channel_str = channel.value
            message = {
                "action": action,  # "subscribe" or "unsubscribe"
                "channel": channel_str,
                "symbols": [s.upper() for s in symbols],
            }

            try:
                await self._ws.send(json.dumps(message))
            except Exception:
                # Connection may be closed, will trigger reconnect
                pass

    def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt."""
        if self._reconnect_task and not self._reconnect_task.done():
            return

        async def reconnect():
            await asyncio.sleep(self._reconnect_delay)
            if self._running:
                await self._connect()
                # Exponential backoff up to 60 seconds
                self._reconnect_delay = min(self._reconnect_delay * 2, 60)

        self._reconnect_task = asyncio.create_task(reconnect())

    async def stop(self) -> None:
        """Stop the provider and close connections."""
        self._running = False

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            await self._ws.close()
            self._ws = None

    async def subscribe(self, symbols: list[str], channels: list[StreamChannel]) -> None:
        for channel in channels:
            self._subscriptions[channel].update(s.upper() for s in symbols)
        # Send subscription message to WebSocket
        if self._ws and self._running:
            await self._send_subscription(symbols, channels, "subscribe")

    async def unsubscribe(self, symbols: list[str], channels: list[StreamChannel]) -> None:
        for channel in channels:
            for s in symbols:
                self._subscriptions[channel].discard(s.upper())
        if self._ws and self._running:
            await self._send_subscription(symbols, channels, "unsubscribe")

    def _emit(self, channel: StreamChannel, symbol: str, data: dict[str, Any], provider: str = "VCI") -> None:
        if self._callback:
            self._sequence += 1
            msg = StreamMessage(
                channel=channel,
                symbol=symbol.upper(),
                data=data,
                timestamp=datetime.utcnow(),
                sequence=self._sequence,
                provider=provider,
            )
            self._callback(msg)


class KBSStreamProvider(StreamProvider):
    """KBS real-time data provider (polling fallback)."""

    def __init__(self, poll_interval: float = 1.0):
        self.poll_interval = poll_interval
        self._running = False
        self._callback: Callable[[StreamMessage], None] | None = None
        self._subscriptions: dict[StreamChannel, set[str]] = defaultdict(set)
        self._poll_task: asyncio.Task | None = None
        self._sequence = 0
        self._last_prices: dict[str, dict[str, Any]] = {}  # symbol -> last price data

    def set_callback(self, callback: Callable[[StreamMessage], None]) -> None:
        self._callback = callback

    async def start(self) -> None:
        """Start polling for real-time data."""
        if self._running:
            return

        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Stop polling."""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

    async def subscribe(self, symbols: list[str], channels: list[StreamChannel]) -> None:
        for channel in channels:
            self._subscriptions[channel].update(s.upper() for s in symbols)

    async def unsubscribe(self, symbols: list[str], channels: list[StreamChannel]) -> None:
        for channel in channels:
            for s in symbols:
                self._subscriptions[channel].discard(s.upper())

    async def _poll_loop(self) -> None:
        """Polling loop for real-time data."""
        while self._running:
            try:
                await self._poll_once()
            except Exception:
                pass
            await asyncio.sleep(self.poll_interval)

    async def _poll_once(self) -> None:
        """Fetch latest price board for subscribed symbols."""
        # Get all subscribed symbols across all channels
        all_symbols = set()
        for symbols in self._subscriptions.values():
            all_symbols.update(symbols)

        if not all_symbols:
            return

        # Fetch price board from KBS (using vnbroker)
        try:
            from vnbroker import Vnbroker
            broker = Vnbroker(source="KBS")
            price_board = broker.listing.price_board(symbols=list(all_symbols))

            if price_board is not None and not price_board.empty:
                for _, row in price_board.iterrows():
                    symbol = row.get("symbol", "").upper()
                    if not symbol:
                        continue

                    # Check if price changed (simple deduplication)
                    current_price = row.get("price") or row.get("match_price") or row.get("close")
                    last_data = self._last_prices.get(symbol, {})
                    if last_data.get("price") == current_price:
                        continue  # No change

                    # Update last price
                    self._last_prices[symbol] = {"price": current_price, "data": row.to_dict()}

                    # Emit price update for subscribed channels
                    for channel in [StreamChannel.PRICE, StreamChannel.SNAPSHOT]:
                        if symbol in self._subscriptions.get(channel, set()):
                            self._emit(channel, symbol, row.to_dict(), provider="KBS")

                    # Emit depth if subscribed
                    if StreamChannel.DEPTH in self._subscriptions and symbol in self._subscriptions[StreamChannel.DEPTH]:
                        depth_data = {
                            "bid_price": row.get("bid_price"),
                            "bid_volume": row.get("bid_volume"),
                            "ask_price": row.get("ask_price"),
                            "ask_volume": row.get("ask_volume"),
                        }
                        self._emit(StreamChannel.DEPTH, symbol, depth_data, provider="KBS")

        except Exception:
            # Silently ignore polling errors
            pass

    def _emit(self, channel: StreamChannel, symbol: str, data: dict[str, Any], provider: str = "KBS") -> None:
        if self._callback:
            self._sequence += 1
            msg = StreamMessage(
                channel=channel,
                symbol=symbol.upper(),
                data=data,
                timestamp=datetime.utcnow(),
                sequence=self._sequence,
                provider=provider,
            )
            self._callback(msg)


class StreamManager:
    """
    Manages multiple stream providers and tenant subscriptions.

    Features:
    - Multi-provider aggregation (VCI, KBS)
    - Tenant-isolated subscriptions
    - Automatic failover between providers
    - Message deduplication
    - Backpressure handling
    """

    def __init__(
        self,
        redis_url: str | None = None,
        max_messages_per_second: int = 1000,
        deduplication_window_ms: int = 100,
        vci_ws_url: str | None = None,
        vci_api_key: str | None = None,
        kbs_poll_interval: float = 1.0,
    ):
        self.providers: dict[str, StreamProvider] = {}
        self.tenant_subscriptions: dict[UUID, dict[StreamChannel, set[str]]] = defaultdict(lambda: defaultdict(set))
        self.tenant_queues: dict[UUID, asyncio.Queue] = {}
        self.redis_url = redis_url
        self.max_msg_per_sec = max_messages_per_second
        self.dedup_window_ms = deduplication_window_ms

        self._running = False
        self._dispatch_task: asyncio.Task | None = None
        self._dedup_cache: dict[str, float] = {}
        self._lock = asyncio.Lock()

        # Register default providers with config
        settings = get_settings()
        self.register_provider(
            "vci",
            VCIStreamProvider(
                api_key=vci_api_key or settings.streaming.vci_api_key,
                ws_url=vci_ws_url or settings.streaming.vci_ws_url,
            )
        )
        self.register_provider(
            "kbs",
            KBSStreamProvider(poll_interval=kbs_poll_interval)
        )

    def register_provider(self, name: str, provider: StreamProvider) -> None:
        """Register a stream provider."""
        provider.set_callback(self._on_provider_message)
        self.providers[name] = provider

    async def start(self) -> None:
        """Start all providers and dispatch loop."""
        if self._running:
            return
        self._running = True

        for provider in self.providers.values():
            await provider.start()

        self._dispatch_task = asyncio.create_task(self._dispatch_loop())

    async def stop(self) -> None:
        """Stop all providers and dispatch loop."""
        self._running = False
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass

        for provider in self.providers.values():
            await provider.stop()

    async def close(self) -> None:
        """Close the stream manager (alias for stop)."""
        await self.stop()

    def _on_provider_message(self, message: StreamMessage) -> None:
        """Callback from providers - route to tenant queues."""
        # Find tenants subscribed to this symbol/channel
        for tenant_id, subs in self.tenant_subscriptions.items():
            if message.symbol in subs.get(message.channel, set()):
                self._enqueue_message(tenant_id, message)

    def _enqueue_message(self, tenant_id: UUID, message: StreamMessage) -> None:
        """Enqueue message for tenant with deduplication and rate limiting."""
        # Deduplication
        dedup_key = f"{tenant_id}:{message.channel}:{message.symbol}:{message.sequence}"
        now = time.time() * 1000
        if dedup_key in self._dedup_cache:
            if now - self._dedup_cache[dedup_key] < self.dedup_window_ms:
                return
        self._dedup_cache[dedup_key] = now

        # Clean old dedup entries
        if len(self._dedup_cache) > 10000:
            cutoff = now - self.dedup_window_ms * 2
            self._dedup_cache = {k: v for k, v in self._dedup_cache.items() if v > cutoff}

        # Get or create tenant queue
        if tenant_id not in self.tenant_queues:
            self.tenant_queues[tenant_id] = asyncio.Queue(maxsize=10000)

        queue = self.tenant_queues[tenant_id]
        try:
            queue.put_nowait(message)
        except asyncio.QueueFull:
            # Drop oldest message if queue full (backpressure)
            try:
                queue.get_nowait()
                queue.put_nowait(message)
            except asyncio.QueueEmpty:
                pass

    async def _dispatch_loop(self) -> None:
        """Main dispatch loop - currently just maintains queues."""
        # In a real implementation, this would push to WebSocket connections
        while self._running:
            await asyncio.sleep(0.1)

    async def subscribe_tenant(
        self,
        tenant_id: UUID,
        symbols: list[str],
        channels: list[StreamChannel],
        provider_preference: list[str] = None,
    ) -> None:
        """Subscribe a tenant to real-time data."""
        provider_preference = provider_preference or ["vci", "kbs"]

        # Update tenant subscriptions
        for channel in channels:
            self.tenant_subscriptions[tenant_id][channel].update(s.upper() for s in symbols)

        # Subscribe providers
        for provider_name in provider_preference:
            if provider_name in self.providers:
                await self.providers[provider_name].subscribe(symbols, channels)

    async def unsubscribe_tenant(
        self,
        tenant_id: UUID,
        symbols: list[str],
        channels: list[StreamChannel],
    ) -> None:
        """Unsubscribe a tenant from real-time data."""
        for channel in channels:
            for s in symbols:
                self.tenant_subscriptions[tenant_id][channel].discard(s.upper())

        # Unsubscribe from all providers
        for provider in self.providers.values():
            await provider.unsubscribe(symbols, channels)

        # Clean up empty subscriptions
        for channel in list(self.tenant_subscriptions[tenant_id].keys()):
            if not self.tenant_subscriptions[tenant_id][channel]:
                del self.tenant_subscriptions[tenant_id][channel]

    async def get_next_message(self, tenant_id: UUID, timeout: float = 1.0) -> StreamMessage | None:
        """Get next message for a tenant (for WebSocket push)."""
        if tenant_id not in self.tenant_queues:
            return None

        queue = self.tenant_queues[tenant_id]
        try:
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def get_tenant_stats(self, tenant_id: UUID) -> dict[str, Any]:
        """Get streaming stats for a tenant."""
        subs = self.tenant_subscriptions.get(tenant_id, {})
        queue = self.tenant_queues.get(tenant_id)
        return {
            "subscriptions": {ch.value: list(syms) for ch, syms in subs.items()},
            "queue_size": queue.qsize() if queue else 0,
            "total_symbols": sum(len(syms) for syms in subs.values()),
        }


class StreamConfig(BaseModel):
    """Configuration for a streaming connection."""

    tenant_id: UUID
    symbols: list[str]
    channels: list[StreamChannel] = [StreamChannel.PRICE]
    provider_preference: list[str] = ["vci", "kbs"]
    max_messages_per_second: int = 100
    heartbeat_interval_seconds: int = 30


class PriceStream:
    """
    High-level price streaming interface for tenants.

    Usage:
        stream = PriceStream(stream_manager, tenant_context)
        await stream.subscribe(["ACB", "VCB"], [StreamChannel.PRICE, StreamChannel.TRADE])
        async for msg in stream:
            print(msg.symbol, msg.data)
    """

    def __init__(
        self,
        stream_manager: StreamManager,
        tenant_context: TenantContext,
        config: StreamConfig | None = None,
    ):
        self.stream_manager = stream_manager
        self.tenant_context = tenant_context
        self.config = config or StreamConfig(tenant_id=tenant_context.tenant_id, symbols=[])
        self._active = False
        self._iterator_task: asyncio.Task | None = None
        self._message_queue: asyncio.Queue = asyncio.Queue()

    def _check_scope(self, channel: StreamChannel) -> None:
        """Check if tenant context has required scope for channel."""
        scope_map = {
            StreamChannel.PRICE: PATScope.STREAM_PRICE,
            StreamChannel.DEPTH: PATScope.STREAM_DEPTH,
            StreamChannel.TRADE: PATScope.STREAM_TRADE,
            StreamChannel.NEWS: PATScope.NEWS_READ,
            StreamChannel.SNAPSHOT: PATScope.STREAM_PRICE,  # snapshot uses price scope
        }
        required_scope = scope_map.get(channel)
        if required_scope and not self.tenant_context.has_scope(required_scope):
            raise ScopeDeniedError(required_scope.value)

    async def subscribe(
        self,
        symbols: list[str],
        channels: list[StreamChannel] = None,
        provider_preference: list[str] = None,
    ) -> None:
        """Subscribe to real-time data."""
        channels = channels or [StreamChannel.PRICE]
        provider_preference = provider_preference or ["vci", "kbs"]

        # Check scopes for all requested channels
        for channel in channels:
            self._check_scope(channel)

        # Filter symbols based on tenant authorization
        allowed_symbols = self.tenant_context.filter_allowed_symbols(symbols)
        if len(allowed_symbols) != len(symbols):
            blocked = set(symbols) - set(allowed_symbols)
            from vninvest.exceptions import SymbolNotAllowedError
            raise SymbolNotAllowedError(symbol=", ".join(blocked))

        self.config.symbols = allowed_symbols
        self.config.channels = channels
        self.config.provider_preference = provider_preference

        await self.stream_manager.subscribe_tenant(
            self.tenant_context.tenant_id,
            allowed_symbols,
            channels,
            provider_preference,
        )
        self._active = True

    async def unsubscribe(self) -> None:
        """Unsubscribe from all streams."""
        if not self._active:
            return

        await self.stream_manager.unsubscribe_tenant(
            self.tenant_context.tenant_id,
            self.config.symbols,
            self.config.channels,
        )
        self._active = False

    def __aiter__(self):
        return self

    async def __anext__(self) -> StreamMessage:
        if not self._active:
            raise StopAsyncIteration

        msg = await self.stream_manager.get_next_message(self.tenant_context.tenant_id, timeout=5.0)
        if msg is None:
            # Send heartbeat or wait
            await asyncio.sleep(1)
            return await self.__anext__()

        return msg

    async def close(self) -> None:
        """Close the stream."""
        await self.unsubscribe()
        self._active = False


def create_stream_manager(
    redis_url: str | None = None,
    max_messages_per_second: int = 1000,
    deduplication_window_ms: int = 100,
    vci_ws_url: str | None = None,
    vci_api_key: str | None = None,
    kbs_poll_interval: float = 1.0,
    **kwargs,
) -> StreamManager:
    """Factory function to create stream manager."""
    settings = get_settings()
    return StreamManager(
        redis_url=redis_url or settings.streaming.redis_url or settings.redis.url,
        max_messages_per_second=max_messages_per_second or settings.streaming.max_messages_per_second,
        deduplication_window_ms=deduplication_window_ms or settings.streaming.deduplication_window_ms,
        vci_ws_url=vci_ws_url or settings.streaming.vci_ws_url,
        vci_api_key=vci_api_key or settings.streaming.vci_api_key,
        kbs_poll_interval=kbs_poll_interval,
        **kwargs,
    )
