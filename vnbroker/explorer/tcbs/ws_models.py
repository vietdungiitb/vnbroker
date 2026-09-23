"""
vnbroker.explorer.tcbs.ws_models — WebSocket data models for TCBS iFlash streams.

Dataclasses for OHLC, OrderBook, Ticker, Trade, and Matching events.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass(frozen=True)
class OHLC:
    """OHLC bar from WebSocket stream."""
    symbol: str
    time: datetime
    interval: str  # 1m, 5m, 15m, 30m, 1H, 1D
    open: float
    high: float
    low: float
    close: float
    volume: int = 0


@dataclass(frozen=True)
class OrderBookLevel:
    """Single level in order book."""
    price: float
    volume: int


@dataclass(frozen=True)
class OrderBook:
    """Order book snapshot from WebSocket stream."""
    symbol: str
    time: datetime
    bids: list[OrderBookLevel] = field(default_factory=list)
    asks: list[OrderBookLevel] = field(default_factory=list)


@dataclass(frozen=True)
class Ticker:
    """Ticker snapshot from WebSocket stream."""
    symbol: str
    time: datetime
    last_price: float
    volume: int
    change: float = 0.0
    change_percent: float = 0.0
    high: float = 0.0
    low: float = 0.0
    open: float = 0.0
    ref_price: float = 0.0
    ceiling: float = 0.0
    floor: float = 0.0


@dataclass(frozen=True)
class Trade:
    """Individual trade event from WebSocket stream."""
    symbol: str
    time: datetime
    price: float
    volume: int
    match_type: str = ""  # A=Buy up, B=Sell down, C=Regular


@dataclass(frozen=True)
class MatchingEvent:
    """Order matching event from Aither/Nesoi streams."""
    order_id: str
    symbol: str
    side: str  # NB/NS for stock, BUY/SELL for derivatives
    quantity: int
    price: float
    status: str
    filled_quantity: int = 0
    time: Optional[datetime] = None
    account_no: str = ""


@dataclass(frozen=True)
class StreamMessage:
    """Parsed WebSocket message envelope."""
    channel: str  # ohlc, orderbook, ticker, trade, matching
    symbol: str
    data: OHLC | OrderBook | Ticker | Trade | MatchingEvent | dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
