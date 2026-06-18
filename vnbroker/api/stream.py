"""
vnbroker/api/stream.py

Unified Streaming API for Real-time Market Data.

Provides a unified interface for streaming real-time tick data
from multiple providers (VCI, KBS) with automatic fallback.

Features:
- Provider-agnostic streaming interface
- Automatic fallback between providers
- Subscription management
- Context manager support
"""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator, List, Optional, Union

import pandas as pd

from vnbroker.base import BaseAdapter
from vnbroker.core.types import DataSource
from vnbroker.core.utils.logger import get_logger

logger = get_logger(__name__)

# Backward compatibility
DataSources = DataSource


class TickData:
    """Standardized tick data container."""
    
    def __init__(
        self,
        symbol: str,
        price: float,
        volume: int,
        timestamp: str,  # ISO format string for JSON serialization
        bid_price: Optional[float] = None,
        ask_price: Optional[float] = None,
        bid_volume: Optional[int] = None,
        ask_volume: Optional[int] = None,
        side: Optional[str] = None,
        source: Optional[str] = None,
    ):
        self.symbol = symbol
        self.price = price
        self.volume = volume
        self.timestamp = timestamp
        self.bid_price = bid_price
        self.ask_price = ask_price
        self.bid_volume = bid_volume
        self.ask_volume = ask_volume
        self.side = side
        self.source = source
    
    def __repr__(self):
        return f"TickData({self.symbol} @ {self.price} vol={self.volume} {self.timestamp})"
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "volume": self.volume,
            "timestamp": self.timestamp,
            "bid_price": self.bid_price,
            "ask_price": self.ask_price,
            "bid_volume": self.bid_volume,
            "ask_volume": self.ask_volume,
            "side": self.side,
            "source": self.source,
        }
    
    def to_series(self) -> pd.Series:
        """Convert to pandas Series for DataFrame construction."""
        return pd.Series(self.to_dict())


class Stream(BaseAdapter):
    """
    Unified Streaming Adapter for Real-time Market Data.
    
    Provides async generator interface for streaming tick data
    with automatic provider fallback.
    
    Usage:
        >>> stream = Stream(source="vci", symbols=["VCB", "VNM", "FPT"])
        >>> async for tick in stream.ticks():
        ...     print(f"{tick.symbol}: {tick.price} @ {tick.timestamp}")
        >>> await stream.close()
    
    With fallback:
        >>> stream = Stream(source="auto", symbols=["VCB", "VNM"])
        >>> async for tick in stream.ticks():
        ...     print(tick)
    
    Context manager:
        >>> async with Stream(source="vci", symbols=["VCB"]) as stream:
        ...     async for tick in stream.ticks():
        ...         print(tick)
    """
    
    _module_name = "stream"
    
    def __init__(
        self,
        source: str = DataSources.VCI,
        symbols: Optional[List[str]] = None,
        poll_interval: float = 1.0,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        show_log: bool = False,
        random_agent: bool = False,
        auth_token: Optional[str] = None,
    ):
        """
        Initialize Stream adapter.
        
        Args:
            source: Data source ("vci", "kbs", "auto")
            symbols: List of stock symbols to stream
            poll_interval: Seconds between polls (default 1.0)
            max_retries: Max retries on error
            retry_delay: Seconds between retries
            show_log: Enable debug logging
            random_agent: Use random user agent
            auth_token: Auth token (for future WebSocket auth)
        """
        # Ensure explorer modules are loaded
        from vnbroker import _ensure_explorer_modules_loaded
        _ensure_explorer_modules_loaded()
        
        self.source = source.lower()
        self.symbols = [s.upper() for s in symbols] if symbols else []
        self.poll_interval = poll_interval
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.show_log = show_log
        self.random_agent = random_agent
        self.auth_token = auth_token
        
        # Validate source
        valid_sources = ["vci", "kbs", "auto"]
        if self.source not in valid_sources:
            raise ValueError(f"Stream source must be one of {valid_sources}, got '{source}'")
        
        if not self.symbols:
            raise ValueError("At least one symbol must be provided")
        
        self._stream = None
        self._current_source = None
        self._fallback_sources = ["vci", "kbs"] if self.source == "auto" else [self.source]
        
        super().__init__(
            source=source,
            symbol=self.symbols[0] if self.symbols else "",
            random_agent=random_agent,
            show_log=show_log,
            auth_token=auth_token,
        )
    
    def _create_stream(self, source: str):
        """Create stream instance for given source."""
        if source == "vci":
            from vnbroker.explorer.vci.stream import VCIStream
            return VCIStream(
                symbols=self.symbols,
                poll_interval=self.poll_interval,
                max_retries=self.max_retries,
                retry_delay=self.retry_delay,
                show_log=self.show_log,
                random_agent=self.random_agent,
            )
        elif source == "kbs":
            from vnbroker.explorer.kbs.stream import KBSStream
            return KBSStream(
                symbols=self.symbols,
                poll_interval=self.poll_interval,
                max_retries=self.max_retries,
                retry_delay=self.retry_delay,
                show_log=self.show_log,
                random_agent=self.random_agent,
            )
        else:
            raise ValueError(f"Unknown source: {source}")
    
    async def _try_stream(self, source: str) -> AsyncGenerator[TickData, None]:
        """Try streaming from a specific source."""
        stream = self._create_stream(source)
        self._stream = stream
        self._current_source = source
        
        if self.show_log:
            logger.info(f"Stream started with source: {source}")
        
        try:
            async for tick in stream.ticks():
                # Convert provider tick to unified TickData
                unified_tick = TickData(
                    symbol=tick.symbol,
                    price=tick.price,
                    volume=tick.volume,
                    timestamp=tick.timestamp.isoformat() if hasattr(tick.timestamp, 'isoformat') else str(tick.timestamp),
                    bid_price=tick.bid_price,
                    ask_price=tick.ask_price,
                    bid_volume=tick.bid_volume,
                    ask_volume=tick.ask_volume,
                    side=tick.side,
                    source=source,
                )
                yield unified_tick
        finally:
            await stream.close()
            self._stream = None
            self._current_source = None
    
    async def ticks(self) -> AsyncGenerator[TickData, None]:
        """
        Async generator yielding real-time ticks with automatic fallback.
        
        Yields:
            TickData: Unified tick data from the active provider
        """
        last_error = None
        
        for source in self._fallback_sources:
            try:
                async for tick in self._try_stream(source):
                    yield tick
                # If we get here, stream ended normally
                return
            except Exception as e:
                last_error = e
                if self.show_log:
                    logger.warning(f"Stream source '{source}' failed: {e}. Trying fallback...")
                continue
        
        # All sources failed
        raise RuntimeError(f"All stream sources failed. Last error: {last_error}")
    
    async def close(self):
        """Close the active stream."""
        if self._stream:
            await self._stream.close()
            self._stream = None
            self._current_source = None
    
    async def __aenter__(self) -> "Stream":
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    def get_current_source(self) -> Optional[str]:
        """Get the currently active source."""
        return self._current_source
    
    def is_running(self) -> bool:
        """Check if stream is currently running."""
        return self._stream is not None and self._stream._running


# Convenience function
async def stream_ticks(
    symbols: List[str],
    source: str = "vci",
    poll_interval: float = 1.0,
    max_ticks: Optional[int] = None,
    **kwargs,
) -> AsyncGenerator[TickData, None]:
    """
    Convenience function to stream ticks for symbols.
    
    Args:
        symbols: List of stock symbols
        source: Data source ("vci", "kbs", "auto")
        poll_interval: Seconds between polls
        max_ticks: Maximum ticks to yield (None = unlimited)
        **kwargs: Additional Stream arguments
    
    Yields:
        TickData: Real-time tick data
    """
    async with Stream(source=source, symbols=symbols, poll_interval=poll_interval, **kwargs) as stream:
        count = 0
        async for tick in stream.ticks():
            yield tick
            count += 1
            if max_ticks and count >= max_ticks:
                break