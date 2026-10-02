"""
DNSE WebSocket Market Data Client

Real-time market data streaming via WebSocket.
Supports channels: quote, trade, trade_extra, ohlc, ohlc_closed, expected_price, foreign_investor, market_index, sec_def
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable, Dict, List, Optional, Set
from urllib.parse import urlencode

import websockets

from .core.config import DNSEConfig
from .core.signature import build_signature_header

logger = logging.getLogger(__name__)


class DNSEWebSocketClient:
    """
    WebSocket client for DNSE real-time market data.
    
    Usage:
        config = DNSEConfig(api_key="...", api_secret="...")
        ws = DNSEWebSocketClient(config)
        
        async def on_message(channel: str, data: dict):
            print(f"{channel}: {data}")
        
        await ws.connect()
        await ws.subscribe(["quote", "trade"], ["VNM", "VCB"])
        await ws.run(on_message)
    """

    WS_BASE_URL = "wss://openapi.dnse.com.vn/ws"

    # Supported channels per DNSE documentation
    CHANNELS = {
        "quote": "Real-time quote updates",
        "trade": "Real-time trade execution",
        "trade_extra": "Extended trade data",
        "ohlc": "Real-time OHLC updates",
        "ohlc_closed": "Closed OHLC candles",
        "expected_price": "Expected price (ATO/ATC)",
        "foreign_investor": "Foreign investor trading data",
        "market_index": "Market index updates",
        "sec_def": "Security definition updates",
    }

    def __init__(self, config: DNSEConfig):
        self._config = config
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False
        self._subscriptions: Dict[str, Set[str]] = {}  # channel -> set of symbols
        self._message_handler: Optional[Callable[[str, dict], None]] = None
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._reconnect_delay = 5  # seconds

    def _build_ws_url(self) -> str:
        """Build WebSocket URL with authentication."""
        # For WebSocket, we use query parameters for auth
        # The signature is built for the WebSocket upgrade request
        path = "/ws"
        method = "GET"
        
        date_value, signature_header = build_signature_header(
            api_key=self._config.api_key,
            api_secret=self._config.api_secret,
            method=method,
            path=path,
            algorithm=self._config.algorithm,
            hmac_nonce_enabled=self._config.hmac_nonce_enabled,
            date_header_name="X-Aux-Date",
        )
        
        params = {
            "api_key": self._config.api_key,
            "date": date_value,
            "signature": signature_header,
            "version": self._config.api_version,
        }
        
        return f"{self.WS_BASE_URL}?{urlencode(params)}"

    async def connect(self) -> None:
        """Establish WebSocket connection."""
        url = self._build_ws_url()
        # P2: URL chứa api_key + HMAC signature trong query string.
        # Log nguyên văn ở level INFO là rò credential.
        from vnbroker.broker.security.redaction import Redactor

        logger.info(f"Connecting to DNSE WebSocket: {Redactor.redact_url(url)}")
        
        self._ws = await websockets.connect(
            url,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=10,
        )
        self._running = True
        self._reconnect_attempts = 0
        logger.info("DNSE WebSocket connected")

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None
        logger.info("DNSE WebSocket disconnected")

    async def subscribe(self, channels: List[str], symbols: List[str]) -> None:
        """
        Subscribe to real-time data channels for specific symbols.
        
        Args:
            channels: List of channel names (e.g., ["quote", "trade"])
            symbols: List of symbols (e.g., ["VNM", "VCB"])
        """
        if not self._ws:
            raise RuntimeError("Not connected. Call connect() first.")
        
        # Validate channels
        for ch in channels:
            if ch not in self.CHANNELS:
                raise ValueError(f"Unknown channel: {ch}. Supported: {list(self.CHANNELS.keys())}")
        
        # Build subscription message
        msg = {
            "action": "subscribe",
            "channels": channels,
            "symbols": symbols,
        }
        
        await self._ws.send(json.dumps(msg))
        
        # Track subscriptions
        for ch in channels:
            if ch not in self._subscriptions:
                self._subscriptions[ch] = set()
            self._subscriptions[ch].update(symbols)
        
        logger.info(f"Subscribed to {channels} for {symbols}")

    async def unsubscribe(self, channels: List[str], symbols: List[str]) -> None:
        """Unsubscribe from channels for specific symbols."""
        if not self._ws:
            return
        
        msg = {
            "action": "unsubscribe",
            "channels": channels,
            "symbols": symbols,
        }
        
        await self._ws.send(json.dumps(msg))
        
        # Update tracked subscriptions
        for ch in channels:
            if ch in self._subscriptions:
                self._subscriptions[ch].difference_update(symbols)
        
        logger.info(f"Unsubscribed from {channels} for {symbols}")

    async def run(self, handler: Callable[[str, dict], None]) -> None:
        """
        Run the WebSocket message loop.
        
        Args:
            handler: Async function(channel: str, data: dict) to process messages
        """
        self._message_handler = handler
        
        while self._running:
            try:
                if not self._ws:
                    await self._reconnect()
                    continue
                
                message = await self._ws.recv()
                await self._handle_message(message)
                
            except websockets.ConnectionClosed:
                logger.warning("WebSocket connection closed")
                await self._reconnect()
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await self._reconnect()

    async def _handle_message(self, message: str) -> None:
        """Parse and route incoming WebSocket message."""
        try:
            data = json.loads(message)
            
            # DNSE WS message format: {"channel": "...", "data": {...}, "symbol": "..."}
            channel = data.get("channel")
            payload = data.get("data", {})
            symbol = data.get("symbol")
            
            if channel and self._message_handler:
                # Add symbol to payload if present
                if symbol:
                    payload["symbol"] = symbol
                await self._message_handler(channel, payload)
                
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse WS message: {message[:100]}")
        except Exception as e:
            logger.error(f"Error handling WS message: {e}")

    async def _reconnect(self) -> None:
        """Attempt to reconnect with exponential backoff."""
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error("Max reconnect attempts reached")
            self._running = False
            return
        
        self._reconnect_attempts += 1
        delay = self._reconnect_delay * (2 ** (self._reconnect_attempts - 1))
        logger.info(f"Reconnecting in {delay}s (attempt {self._reconnect_attempts})")
        
        await asyncio.sleep(delay)
        
        try:
            await self.connect()
            # Resubscribe to previous channels
            for channel, symbols in self._subscriptions.items():
                if symbols:
                    await self.subscribe([channel], list(symbols))
        except Exception as e:
            logger.error(f"Reconnect failed: {e}")
            await self._reconnect()

    def get_subscriptions(self) -> Dict[str, List[str]]:
        """Get current subscriptions."""
        return {ch: list(syms) for ch, syms in self._subscriptions.items()}

    async def __aenter__(self) -> "DNSEWebSocketClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()