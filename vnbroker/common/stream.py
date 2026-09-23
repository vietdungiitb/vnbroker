"""
vnbroker/common/stream.py

Unified Streaming Interface for Real-time Market Data.

Provides a common interface for streaming tick data from multiple providers
(VCI, KBS) with automatic fallback and provider selection.
"""

from __future__ import annotations

from typing import AsyncGenerator, List, Optional, Dict, Any
from abc import ABC, abstractmethod

from vnbroker.core.utils.logger import get_logger

logger = get_logger(__name__)


class TickData:
    """Standardized tick data container."""
    
    def __init__(
        self,
        symbol: str,
        price: float,
        volume: int,
        timestamp: Any,  # datetime or string
        bid_price: Optional[float] = None,
        ask_price: Optional[float] = None,
        bid_volume: Optional[int] = None,
        ask_volume: Optional[int] = None,
        side: Optional[str] = None,
        raw_response: Optional[Dict] = None,
        source: str = "unknown",
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
        self.raw_response = raw_response
        self.source = source
    
    def __repr__(self):
        return f"TickData({self.symbol} @ {self.price} vol={self.volume} {self.timestamp} [{self.source}])"
    
    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "volume": self.volume,
            "timestamp": self.timestamp.isoformat() if hasattr(self.timestamp, 'isoformat') else str(self.timestamp),
            "bid_price": self.bid_price,
            "ask_price": self.ask_price,
            "bid_volume": self.bid_volume,
            "ask_volume": self.ask_volume,
            "side": self.side,
            "source": self.source,
        }


class BaseStream(ABC):
    """Abstract base class for market data streams."""
    
    def __init__(
        self,
        symbols: List[str],
        poll_interval: float = 1.0,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        show_log: bool = False,
        random_agent: bool = False,
    ):
        self.symbols = symbols
        self.poll_interval = poll_interval
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.show_log = show_log
        self.random_agent = random_agent
        self._running = False
    
    @abstractmethod
    async def ticks(self) -> AsyncGenerator[TickData, None]:
        """Async generator yielding real-time ticks."""
        pass
    
    @abstractmethod
    async def close(self):
        """Stop the stream and cleanup."""
        pass
    
    async def __aenter__(self) -> "BaseStream":
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class StreamManager:
    """
    Unified stream manager with automatic provider fallback.
    
    Usage:
        >>> manager = StreamManager(preferred_sources=["VCI", "KBS"])
        >>> async for tick in manager.stream_ticks(["VCB", "VNM"]):
        ...     print(tick)
    """
    
    PROVIDER_CLASSES = {
        "VCI": "vnbroker.explorer.vci.stream.VCIStream",
        "KBS": "vnbroker.explorer.kbs.stream.KBSStream",
    }
    
    def __init__(
        self,
        preferred_sources: Optional[List[str]] = None,
        poll_interval: float = 1.0,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        show_log: bool = False,
        random_agent: bool = False,
    ):
        self.preferred_sources = preferred_sources or ["VCI", "KBS"]
        self.poll_interval = poll_interval
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.show_log = show_log
        self.random_agent = random_agent
        self._current_stream: Optional[BaseStream] = None
        self._current_source: Optional[str] = None
    
    def _get_provider_class(self, source: str):
        """Dynamically import provider stream class."""
        if source not in self.PROVIDER_CLASSES:
            raise ValueError(f"Unsupported streaming source: {source}")
        
        module_path, class_name = self.PROVIDER_CLASSES[source].rsplit(".", 1)
        module = __import__(module_path, fromlist=[class_name])
        return getattr(module, class_name)
    
    async def _create_stream(self, source: str, symbols: List[str]) -> BaseStream:
        """Create a stream instance for the given source."""
        provider_class = self._get_provider_class(source)
        return provider_class(
            symbols=symbols,
            poll_interval=self.poll_interval,
            max_retries=self.max_retries,
            retry_delay=self.retry_delay,
            show_log=self.show_log,
            random_agent=self.random_agent,
        )
    
    async def stream_ticks(
        self,
        symbols: List[str],
        max_ticks: Optional[int] = None,
    ) -> AsyncGenerator[TickData, None]:
        """
        Stream ticks with automatic provider fallback.
        
        Args:
            symbols: List of stock symbols to stream
            max_ticks: Maximum ticks to yield (None = unlimited)
            
        Yields:
            TickData: Real-time tick data
        """
        last_error = None
        
        for source in self.preferred_sources:
            try:
                if self.show_log:
                    logger.info(f"Attempting to stream from {source}")
                
                stream = await self._create_stream(source, symbols)
                self._current_stream = stream
                self._current_source = source
                
                count = 0
                async for tick in stream.ticks():
                    # Add source info to tick
                    tick.source = source
                    yield tick
                    count += 1
                    if max_ticks and count >= max_ticks:
                        return
                
                # If we get here, stream ended normally
                if self.show_log:
                    logger.info(f"Stream from {source} ended normally")
                return
                
            except Exception as e:
                last_error = e
                if self.show_log:
                    logger.warning(f"Stream from {source} failed: {e}. Trying next provider...")
                await self._cleanup_stream()
                continue
        
        # All providers failed
        raise ConnectionError(
            f"All streaming providers failed. Last error: {last_error}"
        )
    
    async def _cleanup_stream(self):
        """Cleanup current stream."""
        if self._current_stream:
            try:
                await self._current_stream.close()
            except Exception as e:
                if self.show_log:
                    logger.warning(f"Error closing stream: {e}")
            self._current_stream = None
            self._current_source = None
    
    async def close(self):
        """Close the stream manager."""
        await self._cleanup_stream()


# Convenience function for simple usage
async def stream_ticks(
    symbols: List[str],
    preferred_sources: Optional[List[str]] = None,
    poll_interval: float = 1.0,
    max_ticks: Optional[int] = None,
    **kwargs,
) -> AsyncGenerator[TickData, None]:
    """
    Convenience function to stream ticks with automatic fallback.
    
    Args:
        symbols: List of stock symbols
        preferred_sources: Preferred data sources in order (default: ["VCI", "KBS"])
        poll_interval: Seconds between polls
        max_ticks: Maximum ticks to yield (None = unlimited)
        **kwargs: Additional StreamManager arguments
        
    Yields:
        TickData: Real-time tick data
    """
    manager = StreamManager(
        preferred_sources=preferred_sources,
        poll_interval=poll_interval,
        **kwargs,
    )
    async for tick in manager.stream_ticks(symbols, max_ticks):
        yield tick
    await manager.close()