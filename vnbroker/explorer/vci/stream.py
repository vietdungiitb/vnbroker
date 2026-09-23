"""
vnbroker/explorer/vci/stream.py

VCI Real-time Market Data Streaming (Polling-based).

Since VCI does not provide a public WebSocket API for market data,
this module implements a high-frequency polling mechanism that
provides a WebSocket-like async generator interface.

Features:
- Configurable poll interval (default 1 second)
- Automatic reconnection on errors
- Subscription management for multiple symbols
- Tick data normalization to standard schema
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import AsyncGenerator, Dict, List, Optional, Set

import pandas as pd

from vnbroker.core.utils.logger import get_logger
from vnbroker.core.utils.client import send_request
from vnbroker.core.utils.user_agent import get_headers
from vnbroker.core.utils.validation import validate_symbol
from vnbroker.core.utils.transform import intraday_to_df
from vnbroker.core.utils.parser import convert_time_flexible
from vnbroker.explorer.vci.const import _INTRADAY_URL, _TRADING_URL, _INTRADAY_MAP, _INTRADAY_DTYPE

logger = get_logger(__name__)


class TickData:
    """Standardized tick data container."""
    
    def __init__(
        self,
        symbol: str,
        price: float,
        volume: int,
        timestamp: datetime,
        bid_price: Optional[float] = None,
        ask_price: Optional[float] = None,
        bid_volume: Optional[int] = None,
        ask_volume: Optional[int] = None,
        side: Optional[str] = None,
        raw_response: Optional[Dict] = None,
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
    
    def __repr__(self):
        return f"TickData({self.symbol} @ {self.price} vol={self.volume} {self.timestamp})"
    
    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "volume": self.volume,
            "timestamp": self.timestamp.isoformat(),
            "bid_price": self.bid_price,
            "ask_price": self.ask_price,
            "bid_volume": self.bid_volume,
            "ask_volume": self.ask_volume,
            "side": self.side,
        }


class VCIStream:
    """
    VCI Real-time Market Data Stream (Polling-based).
    
    Provides async generator interface for real-time tick data
    by polling VCI's intraday API at high frequency.
    
    Usage:
        >>> stream = VCIStream(symbols=["VCB", "VNM", "FPT"], poll_interval=1.0)
        >>> async for tick in stream.ticks():
        ...     print(f"{tick.symbol}: {tick.price} @ {tick.timestamp}")
        >>> await stream.close()
    
    Or with context manager:
        >>> async with VCIStream(symbols=["VCB", "VNM"]) as stream:
        ...     async for tick in stream.ticks():
        ...         print(tick)
    """
    
    def __init__(
        self,
        symbols: List[str],
        poll_interval: float = 1.0,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        show_log: bool = False,
        random_agent: bool = False,
    ):
        """
        Initialize VCI Stream.
        
        Args:
            symbols: List of stock symbols to stream
            poll_interval: Seconds between polls (default 1.0)
            max_retries: Max retries on error before giving up
            retry_delay: Seconds to wait between retries
            show_log: Enable debug logging
            random_agent: Use random user agent
        """
        self.symbols = [validate_symbol(s) for s in symbols]
        self.poll_interval = poll_interval
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.show_log = show_log
        self.random_agent = random_agent
        
        self._running = False
        self._last_ticks: Dict[str, Dict] = {}  # Track last seen tick per symbol
        self._tasks: Set[asyncio.Task] = set()
        self._headers = get_headers(data_source="VCI", random_agent=random_agent)
        self._base_url = _TRADING_URL
        
        if self.show_log:
            logger.info(f"VCIStream initialized for {len(self.symbols)} symbols, poll_interval={poll_interval}s")
    
    async def _fetch_intraday(self, symbol: str) -> Optional[pd.DataFrame]:
        """Fetch latest intraday data for a symbol."""
        url = f"{self._base_url}{_INTRADAY_URL}"
        params = {"symbol": symbol, "pageSize": 50}
        
        try:
            response = await asyncio.to_thread(
                send_request,
                url=url,
                headers=self._headers,
                method="GET",
                params=params,
                show_log=self.show_log,
            )
            
            if not response or "data" not in response:
                return None
            
            data = response["data"]
            if not data:
                return None
            
            df = intraday_to_df(
                data=data,
                column_map=_INTRADAY_MAP,
                dtype_map=_INTRADAY_DTYPE,
            )
            return df
            
        except Exception as e:
            if self.show_log:
                logger.warning(f"VCIStream fetch error for {symbol}: {e}")
            return None
    
    def _normalize_tick(self, symbol: str, row: pd.Series) -> Optional[TickData]:
        """Normalize a row to TickData."""
        try:
            timestamp = row["time"]
            if isinstance(timestamp, str):
                timestamp = convert_time_flexible(timestamp)
            elif hasattr(timestamp, "to_pydatetime"):
                timestamp = timestamp.to_pydatetime()
            
            return TickData(
                symbol=symbol,
                price=float(row["price"]),
                volume=int(row["volume"]),
                timestamp=timestamp,
                side=row.get("match_type"),
                raw_response=row.to_dict(),
            )
        except Exception as e:
            if self.show_log:
                logger.warning(f"VCIStream normalize error for {symbol}: {e}")
            return None
    
    async def _poll_symbol(self, symbol: str) -> List[TickData]:
        """Poll a single symbol and return new ticks."""
        df = await self._fetch_intraday(symbol)
        if df is None or df.empty:
            return []
        
        new_ticks = []
        last_seen = self._last_ticks.get(symbol)
        
        # Get latest ticks (most recent first)
        for _, row in df.iterrows():
            tick_time = row["time"]
            if isinstance(tick_time, str):
                tick_time = convert_time_flexible(tick_time)
            elif hasattr(tick_time, "to_pydatetime"):
                tick_time = tick_time.to_pydatetime()
            
            # Skip if we've seen this tick before
            if last_seen and tick_time <= last_seen.get("time", datetime.min):
                continue
            
            tick = self._normalize_tick(symbol, row)
            if tick:
                new_ticks.append(tick)
        
        # Update last seen
        if not df.empty:
            latest_time = df.iloc[-1]["time"]
            if isinstance(latest_time, str):
                latest_time = convert_time_flexible(latest_time)
            elif hasattr(latest_time, "to_pydatetime"):
                latest_time = latest_time.to_pydatetime()
            self._last_ticks[symbol] = {"time": latest_time}
        
        return new_ticks
    
    async def _poll_all(self) -> List[TickData]:
        """Poll all symbols and return all new ticks."""
        all_ticks = []
        
        # Poll all symbols concurrently
        tasks = [self._poll_symbol(symbol) for symbol in self.symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for symbol, result in zip(self.symbols, results):
            if isinstance(result, Exception):
                if self.show_log:
                    logger.warning(f"VCIStream poll error for {symbol}: {result}")
                continue
            all_ticks.extend(result)
        
        return all_ticks
    
    async def ticks(self) -> AsyncGenerator[TickData, None]:
        """
        Async generator yielding real-time ticks.
        
        Yields:
            TickData: Normalized tick data for each new trade
        """
        self._running = True
        
        if self.show_log:
            logger.info(f"VCIStream started for {self.symbols}")
        
        try:
            while self._running:
                start_time = time.perf_counter()
                
                try:
                    new_ticks = await self._poll_all()
                    
                    for tick in new_ticks:
                        yield tick
                        
                except Exception as e:
                    if self.show_log:
                        logger.error(f"VCIStream poll cycle error: {e}")
                    
                    # Retry logic
                    for attempt in range(self.max_retries):
                        await asyncio.sleep(self.retry_delay)
                        try:
                            new_ticks = await self._poll_all()
                            for tick in new_ticks:
                                yield tick
                            break
                        except Exception as retry_e:
                            if self.show_log:
                                logger.warning(f"VCIStream retry {attempt+1}/{self.max_retries} failed: {retry_e}")
                            if attempt == self.max_retries - 1:
                                raise
                
                # Maintain poll interval
                elapsed = time.perf_counter() - start_time
                sleep_time = max(0, self.poll_interval - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    
        finally:
            self._running = False
            if self.show_log:
                logger.info("VCIStream stopped")
    
    async def close(self):
        """Stop the stream and cleanup."""
        self._running = False
        
        # Cancel any pending tasks
        for task in self._tasks:
            task.cancel()
        
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        self._tasks.clear()
        
        if self.show_log:
            logger.info("VCIStream closed")
    
    async def __aenter__(self) -> "VCIStream":
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# Convenience function for simple usage
async def stream_ticks(
    symbols: List[str],
    poll_interval: float = 1.0,
    max_ticks: Optional[int] = None,
    **kwargs,
) -> AsyncGenerator[TickData, None]:
    """
    Convenience function to stream ticks for symbols.
    
    Args:
        symbols: List of stock symbols
        poll_interval: Seconds between polls
        max_ticks: Maximum ticks to yield (None = unlimited)
        **kwargs: Additional VCIStream arguments
    
    Yields:
        TickData: Real-time tick data
    """
    async with VCIStream(symbols=symbols, poll_interval=poll_interval, **kwargs) as stream:
        count = 0
        async for tick in stream.ticks():
            yield tick
            count += 1
            if max_ticks and count >= max_ticks:
                break