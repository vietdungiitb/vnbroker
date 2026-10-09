"""
vnbroker.explorer.tcbs.ws_models — data models for the TCBS ``thesis`` streams.

Wire protocol (official docs, v1.0.0):
  * TEXT frames delimited by ``|`` — never JSON envelopes.
  * Client → server: ``d|a|||base64(token)``, ``d|s|tk|<codes>|<symbols>``,
    ``d|u|tk|<codes>|<symbols>``, ``d|r|tk||<symbols>``, ``d|p|||``.
  * Server → client control: ``d|0|{auth json}``, ``d|33|15``, ``d|34|1``,
    ``d|p|||``.
  * Server → client data: ``s|<CHANNEL_ID>|<JSON payload>``.

Two endpoints with **disjoint** channel IDs and different scalar types:

===============  =========  ==========  ======================
Data             normal     derivative  notes
===============  =========  ==========  ======================
ticker match     ``s|6``    ``s|21``    stock str / deriv num
bid              ``s|1``    ``s|23``    stock str / deriv num
offer            ``s|2``    ``s|24``    stock str / deriv num
foreign          ``s|3``    —           strings
base price       ``s|4``    —           numbers
session summary  ``s|5``    ``s|27``    numbers
stock index      ``s|8``    —           numbers
pt advertisement ``s|16``   —           numbers
pt match         ``s|17``   —           numbers
match history    ``s|22``   —           price/qtty strings
===============  =========  ==========  ======================

References: developers.tcbs.com.vn/docs/v1.0.0/stock/ws-price-board/ and
.../derivative/ws-price-board
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

# ── Legacy domain objects kept for backwards compatibility ───────────────────
# test_tcbs_full_acb.py constructs these by keyword; stream.py narrows on them.


@dataclass(frozen=True)
class OHLC:
    """OHLC bar. Not produced by the thesis price-board feeds (no OHLC channel)."""

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
    """Single level in an order book."""

    price: float
    volume: int


@dataclass(frozen=True)
class OrderBook:
    """Top-3 order book snapshot assembled from ``bi`` + ``op`` channels."""

    symbol: str
    time: datetime
    bids: list[OrderBookLevel] = field(default_factory=list)
    asks: list[OrderBookLevel] = field(default_factory=list)


@dataclass(frozen=True)
class Ticker:
    """Ticker snapshot assembled from ``bp`` + ``mp`` + ``tm`` channels."""

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
    """Single matched trade, from the ``tm`` channel (``s|6`` / ``s|21``)."""

    symbol: str
    time: datetime
    price: float
    volume: int
    match_type: str = ""
    change: float = 0.0
    change_percent: float = 0.0
    total_volume: int = 0
    total_value: float = 0.0


@dataclass(frozen=True)
class MatchingEvent:
    """Retained for import compatibility. The thesis price-board feeds carry no
    per-order matching stream, so nothing in this module produces it."""

    order_id: str
    symbol: str
    side: str
    quantity: int
    price: float
    status: str
    filled_quantity: int = 0
    time: Optional[datetime] = None
    account_no: str = ""


# ── Protocol-level models ────────────────────────────────────────────────────


@dataclass(frozen=True)
class ControlFrame:
    """A parsed ``d|...`` control frame."""

    kind: str  # auth_response | heartbeat_timeout | subscribe_ack | heartbeat_pong | unknown
    code: str  # the pipe field right after "d"
    value: Any = None  # trailing field, coerced where meaningful
    raw: str = ""


@dataclass(frozen=True)
class StreamMessage:
    """A parsed ``s|<CHANNEL_ID>|<JSON>`` data frame.

    ``raw`` keeps the wire text verbatim so callers can audit or re-parse a
    frame the normalizer did not understand.
    """

    channel: str  # semantic name, e.g. bid / offer / ticker_match
    channel_id: str  # "1", "21", …
    symbol: str
    payload: Dict[str, Any]
    raw: str = ""
    stream_type: str = "normal"
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def raw_payload(self) -> str:
        """The JSON text as sent on the wire, untouched."""
        _, _, tail = self.raw.partition("|")
        _, _, payload_text = tail.partition("|")
        return payload_text


# ── Scalar coercion ──────────────────────────────────────────────────────────
# Stock frames carry prices/volumes as JSON strings ("24550"); derivative
# frames carry numbers. Coerce defensively without assuming which arrived.


def to_float(value: Any, default: float = 0.0) -> float:
    """Coerce a doc-declared numeric field, tolerating the string variant."""
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def to_int(value: Any, default: int = 0) -> int:
    """Coerce a doc-declared integer field, tolerating the string variant."""
    return int(to_float(value, float(default)))


def to_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


# ── Typed conversions on top of raw frames ───────────────────────────────────


def trade_from_message(message: StreamMessage) -> Optional[Trade]:
    """Build a :class:`Trade` from a ``ticker_match`` frame, or return None."""
    if message is None or message.channel != "ticker_match":
        return None
    data = message.payload
    return Trade(
        symbol=to_str(data.get("symbol"), message.symbol),
        time=message.timestamp,
        price=to_float(data.get("matchPrice")),
        volume=to_int(data.get("matchQtty")),
        match_type=to_str(data.get("matchType")),
        change=to_float(data.get("change")),
        change_percent=to_float(data.get("changePercent")),
        total_volume=to_int(data.get("totalVolume")),
        total_value=to_float(data.get("totalValue")),
    )


def base_price_from_message(message: Optional[StreamMessage]) -> Optional[Dict[str, float]]:
    """``base_price`` (normal ``s|4``) → ceiling / floor / reference."""
    if message is None or message.channel != "base_price":
        return None
    data = message.payload
    return {
        "ceiling": to_float(data.get("ceilPrice")),
        "floor": to_float(data.get("floorPrice")),
        "reference": to_float(data.get("refPrice")),
    }


def session_from_message(message: Optional[StreamMessage]) -> Optional[Dict[str, float]]:
    """Session summary: normal ``s|5`` or derivative ``s|27``."""
    if message is None or message.channel not in ("session", "day_summary"):
        return None
    data = message.payload
    return {
        "high": to_float(data.get("high")),
        "low": to_float(data.get("low")),
        "avg": to_float(data.get("avg")),
        "open": to_float(data.get("open")),
    }


def foreign_from_message(message: StreamMessage) -> Optional[Dict[str, int]]:
    """``foreign`` (normal ``s|3``) → foreign buy/sell volume and remaining room."""
    if message is None or message.channel != "foreign":
        return None
    data = message.payload
    return {
        "buy_quantity": to_int(data.get("buyForeignQtty")),
        "sell_quantity": to_int(data.get("sellForeignQtty")),
        "room": to_int(data.get("room")),
    }


def ticker_from_messages(
    base_price: Optional[StreamMessage] = None,
    session: Optional[StreamMessage] = None,
    trade: Optional[StreamMessage] = None,
) -> Optional[Ticker]:
    """Assemble a :class:`Ticker` from whichever of ``bp``/``mp``/``tm`` arrived."""
    bp = base_price_from_message(base_price) or {}
    mp = session_from_message(session) or {}
    if not bp and not mp and trade is None:
        return None
    symbol = ""
    reference = bp.get("reference", 0.0)
    for candidate in (base_price, session, trade):
        if candidate is not None and candidate.symbol:
            symbol = candidate.symbol
            break
    parsed_trade = trade_from_message(trade) if trade is not None else None
    return Ticker(
        symbol=symbol,
        time=(session or base_price or trade).timestamp,  # type: ignore[union-attr]
        last_price=parsed_trade.price if parsed_trade else 0.0,
        volume=parsed_trade.total_volume if parsed_trade else 0,
        change=parsed_trade.change if parsed_trade else 0.0,
        change_percent=parsed_trade.change_percent if parsed_trade else 0.0,
        high=mp.get("high", 0.0),
        low=mp.get("low", 0.0),
        open=mp.get("open", 0.0),
        ref_price=reference,
        ceiling=bp.get("ceiling", 0.0),
        floor=bp.get("floor", 0.0),
    )