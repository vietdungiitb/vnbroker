"""
vnbroker.explorer.tcbs.websocket — async client for the TCBS ``thesis`` streams.

Endpoints (official docs, v1.0.0):

* ``wss://openapi.tcbs.com.vn/ws/thesis/v1/stream/normal``   — stock price board
* ``wss://openapi.tcbs.com.vn/ws/thesis/v1/stream/derivative`` — derivative board

Wire protocol — TEXT frames delimited by ``|``, never JSON envelopes:

======================  ===========================================  ==========
Direction                Frame                                        Where
======================  ===========================================  ==========
client → server          ``d|a|||base64(token)``                      auth
client → server          ``d|s|tk|<codes>|<symbols>``                subscribe
client → server          ``d|u|tk|<codes>|<symbols>``                unsubscribe
client → server          ``d|r|tk||<symbols>``                       snapshot
client → server          ``d|p|||``                                  heartbeat, 2s
server → client          ``d|0|{"success":true,"error":null}``       auth ack
server → client          ``d|33|15``                                 heartbeat timeout
server → client          ``d|34|1``                                  subscribe ack
server → client          ``s|<CHANNEL_ID>|<JSON>``                   data
======================  ===========================================  ==========

Two hard requirements that are easy to get wrong:

1. **Library auto-ping must be off.** The server only accepts the text-frame
   heartbeat ``d|p|||``; an RFC 6455 ping from the library gets close code
   ``1002 Protocol Error``. Hence ``ping_interval=None, ping_timeout=None``.
2. **Auth is a frame, not a header, and it must be acknowledged.** ``connect()``
   blocks until ``d|0|{...success:true...}`` arrives; subscribing before that is
   rejected by the server.

There is no SIT host: ``openapisit.tcbs.com.vn`` does not resolve, so no SIT
endpoint table exists here.

References: developers.tcbs.com.vn/docs/v1.0.0/stock/ws-price-board/ and
.../derivative/ws-price-board
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional, Sequence, Tuple

import websockets

from vnbroker.explorer.tcbs.ws_models import (
    ControlFrame,
    OHLC,
    OrderBook,
    OrderBookLevel,
    StreamMessage,
    Ticker,
    Trade,
    trade_from_message,
    to_float,
    to_int,
    to_str,
)

_logger = logging.getLogger("vnbroker.explorer.tcbs.websocket")

# ── Endpoints ────────────────────────────────────────────────────────────────

_WS_BASE = "wss://openapi.tcbs.com.vn/ws/thesis/v1/stream"

_NORMAL_URL = f"{_WS_BASE}/normal"
_DERIVATIVE_URL = f"{_WS_BASE}/derivative"

# Server disconnects after this many seconds without a heartbeat. The server
# also announces it with `d|33|15`; this is the pre-connection default.
_DEFAULT_HEARTBEAT_TIMEOUT = 15.0


class StreamType(Enum):
    """Price-board endpoint selector.

    ``OURANOS``/``AITHER``/``NESOI`` are retained as aliases so existing callers
    (including ``stream.py``) keep working; they now resolve to the thesis
    endpoints, because the thesis feeds are the only ones the official docs
    describe.
    """

    NORMAL = "normal"
    DERIVATIVE = "derivative"
    OURANOS = "normal"  # deprecated alias -> NORMAL
    AITHER = "normal"  # deprecated alias -> NORMAL
    NESOI = "derivative"  # deprecated alias -> DERIVATIVE


def endpoint_for(stream_type: StreamType = StreamType.NORMAL) -> str:
    """Resolve the WSS URL for a stream type."""
    if stream_type is StreamType.DERIVATIVE:
        return _DERIVATIVE_URL
    if stream_type is StreamType.NORMAL:
        return _NORMAL_URL
    raise ValueError(f"Unknown stream type: {stream_type!r}")


# ── Channel registries (separate per endpoint — AC6) ─────────────────────────

#: ``channel code`` (subscribe token) -> ``channel id`` for ``/stream/normal``.
STOCK_CHANNEL_IDS: Dict[str, str] = {
    "bi": "1",
    "op": "2",
    "fe": "3",
    "bp": "4",
    "mp": "5",
    "tm": "6",
    "rt": "8",
    "pta": "16",
    "ptm": "17",
    "tmh": "22",
}

#: ``channel code`` (subscribe token) -> ``channel id`` for ``/stream/derivative``.
DERIVATIVE_CHANNEL_IDS: Dict[str, str] = {
    "tm": "21",
    "bi": "23",
    "op": "24",
    "mp": "27",
}

#: ``channel id`` -> semantic name for ``/stream/normal``.
_NORMAL_CHANNEL_NAMES: Dict[str, str] = {
    "1": "bid",
    "2": "offer",
    "3": "foreign",
    "4": "base_price",
    "5": "session",
    "6": "ticker_match",
    "8": "stock_index",
    "16": "pt_advertisement",
    "17": "pt_match",
    "22": "ticker_match_history",
}

#: ``channel id`` -> semantic name for ``/stream/derivative``.
_DERIVATIVE_CHANNEL_NAMES: Dict[str, str] = {
    "21": "ticker_match",
    "23": "bid",
    "24": "offer",
    "27": "day_summary",
}

# Channel codes the derivative endpoint accepts but never emits frames for.
_DERIVATIVE_SILENT_CODES = frozenset({"bp", "fe"})

#: Legacy channel names accepted by :meth:`TCBSWebSocketClient.subscribe`.
LEGACY_CHANNEL_CODES: Dict[str, Tuple[str, ...]] = {
    "orderbook": ("bi", "op"),
    "bid": ("bi",),
    "offer": ("op",),
    "foreign": ("fe",),
    "base_price": ("bp",),
    "session": ("mp",),
    "day_summary": ("mp",),
    "ticker": ("bp", "mp"),
    "trade": ("tm",),
    "ticker_match": ("tm",),
    "ticker_match_history": ("tmh",),
    "stock_index": ("rt",),
    "pt_advertisement": ("pta",),
    "pt_match": ("ptm",),
}


class TCBSProtocolError(RuntimeError):
    """Raised when the peer violates the documented wire protocol."""


class TCBSAuthError(TCBSProtocolError):
    """Raised when the server answers the auth frame with ``success:false``."""


# ── Frame construction (client → server) ─────────────────────────────────────


def encode_auth_token(token: str) -> str:
    """Base64-encode an OpenAPI token, as the protocol requires."""
    return base64.b64encode(token.encode("utf-8")).decode("ascii")


def build_auth_frame(token: str) -> str:
    """``d|a|||<base64(token)>`` — sent as a TEXT frame, never as a header."""
    if not token:
        raise ValueError("token is required for TCBS WebSocket auth")
    return f"d|a|||{encode_auth_token(token)}"


def build_heartbeat_frame() -> str:
    """``d|p|||`` — text-frame heartbeat; the server cuts us off after 15s."""
    return "d|p|||"


def _frame(action: str, object_type: str, properties: str, objects: Sequence[str]) -> str:
    if not objects:
        raise ValueError("at least one object is required")
    if not properties:
        raise ValueError("at least one property (channel code) is required")
    return f"d|{action}|{object_type}|{properties}|{','.join(objects)}"


def build_subscribe_frame(
    symbols: Sequence[str],
    channels: Sequence[str],
    object_type: str = "tk",
) -> str:
    """``d|s|tk|bp+bi+tm+mp+op+fe|FPT,VCS``."""
    return _frame("s", object_type, "+".join(channels), symbols)


def build_unsubscribe_frame(
    symbols: Sequence[str],
    channels: Sequence[str],
    object_type: str = "tk",
) -> str:
    """``d|u|tk|bp+bi+tm+mp+op+fe|TCB``."""
    return _frame("u", object_type, "+".join(channels), symbols)


def build_request_frame(symbols: Sequence[str], object_type: str = "tk") -> str:
    """``d|r|tk||TCB,VCB`` — one-shot snapshot; properties must stay empty."""
    if not symbols:
        raise ValueError("at least one object is required")
    return f"d|r|{object_type}||{','.join(symbols)}"


def resolve_channel_codes(channels: Sequence[str]) -> Tuple[str, ...]:
    """Normalise channel names/codes, accepting legacy English names.

    Unknown names raise instead of being silently forwarded: the thesis feeds
    have no OHLC or per-order matching channel, and a silent forward would look
    like a successful subscription that never delivers anything.
    """
    codes: List[str] = []
    for name in channels:
        key = str(name).strip()
        if key in LEGACY_CHANNEL_CODES:
            codes.extend(LEGACY_CHANNEL_CODES[key])
            continue
        if key in STOCK_CHANNEL_IDS or key in _DERIVATIVE_SILENT_CODES:
            if key not in codes:
                codes.append(key)
            continue
        raise ValueError(
            f"Unknown TCBS channel {name!r}. Valid codes: "
            f"{sorted(set(STOCK_CHANNEL_IDS) | set(_DERIVATIVE_SILENT_CODES))}; "
            f"legacy names: {sorted(LEGACY_CHANNEL_CODES)}"
        )
    if not codes:
        raise ValueError("at least one channel is required")
    return tuple(codes)


# ── Frame parsing (server → client) ──────────────────────────────────────────


def parse_control_frame(raw: Any) -> Optional[ControlFrame]:
    """Parse a ``d|...`` control frame. Returns None for anything else."""
    if not isinstance(raw, str) or not raw.startswith("d|"):
        return None
    parts = raw.split("|")
    code = parts[1] if len(parts) > 1 else ""
    tail = "|".join(parts[2:])

    if code == "0":
        try:
            body = json.loads(tail) if tail else {}
        except json.JSONDecodeError:
            body = {"success": False, "error": {"message": tail}}
        success = bool(body.get("success")) if isinstance(body, dict) else False
        error = body.get("error") if isinstance(body, dict) else None
        kind = "auth_response"
        value: Any = {"success": success, "error": error, "body": body}
        if not success:
            kind = "auth_failure"
        return ControlFrame(kind=kind, code=code, value=value, raw=raw)
    if code == "33":
        return ControlFrame(
            kind="heartbeat_timeout", code=code, value=to_float(tail, 0.0), raw=raw
        )
    if code == "34":
        return ControlFrame(kind="subscribe_ack", code=code, value=to_int(tail, 0), raw=raw)
    if code == "p":
        return ControlFrame(kind="heartbeat_pong", code=code, value=None, raw=raw)
    return ControlFrame(kind="unknown", code=code, value=tail, raw=raw)


def _parse_data_payload(channel_id: str, channel: str, raw: str) -> Optional[StreamMessage]:
    _, _, payload_text = raw.partition("|")
    _, _, payload_text = payload_text.partition("|")
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        _logger.warning("Malformed payload on channel %s: %s", channel_id, raw[:200])
        return None
    if not isinstance(payload, dict):
        _logger.warning("Non-object payload on channel %s: %s", channel_id, raw[:200])
        return None
    return StreamMessage(
        channel=channel,
        channel_id=channel_id,
        symbol=to_str(payload.get("symbol")),
        payload=payload,
        raw=raw,
        timestamp=datetime.now(tz=timezone.utc),
    )


def parse_normal_frame(raw: Any) -> Optional[StreamMessage]:
    """Parse ``s|<id>|<json>`` for ``/stream/normal`` only."""
    if not isinstance(raw, str) or not raw.startswith("s|"):
        return None
    parts = raw.split("|", 2)
    if len(parts) != 3 or not parts[2]:
        _logger.warning("Malformed data frame: %s", str(raw)[:200])
        return None
    channel_id = parts[1]
    channel = _NORMAL_CHANNEL_NAMES.get(channel_id)
    if channel is None:
        _logger.warning("Unknown normal channel id %r — frame dropped", channel_id)
        return None
    return _parse_data_payload(channel_id, channel, raw)


def parse_derivative_frame(raw: Any) -> Optional[StreamMessage]:
    """Parse ``s|<id>|<json>`` for ``/stream/derivative`` only.

    Deliberately not shared with :func:`parse_normal_frame`: the two endpoints
    number their channels differently and disagree on scalar types, so one
    combined parser would silently mis-read one of them.
    """
    if not isinstance(raw, str) or not raw.startswith("s|"):
        return None
    parts = raw.split("|", 2)
    if len(parts) != 3 or not parts[2]:
        _logger.warning("Malformed data frame: %s", str(raw)[:200])
        return None
    channel_id = parts[1]
    channel = _DERIVATIVE_CHANNEL_NAMES.get(channel_id)
    if channel is None:
        _logger.warning("Unknown derivative channel id %r — frame dropped", channel_id)
        return None
    return _parse_data_payload(channel_id, channel, raw)


def parse_data_frame(raw: Any, stream_type: StreamType = StreamType.NORMAL) -> Optional[StreamMessage]:
    """Dispatch to the parser that owns ``stream_type``'s channel namespace."""
    if stream_type is StreamType.DERIVATIVE:
        return parse_derivative_frame(raw)
    if stream_type is StreamType.NORMAL:
        return parse_normal_frame(raw)
    raise ValueError(f"Unknown stream type: {stream_type!r}")


def build_order_book(
    bid_message: Optional[StreamMessage] = None,
    offer_message: Optional[StreamMessage] = None,
) -> Optional[OrderBook]:
    """Merge the ``bid`` and ``offer`` top-3 frames into one :class:`OrderBook`."""
    if bid_message is None and offer_message is None:
        return None

    def _levels(
        message: Optional[StreamMessage], channel: str, price_key: str, qtty_key: str
    ) -> List[OrderBookLevel]:
        if message is None or message.channel != channel:
            return []
        data = message.payload
        levels = []
        for i in range(1, 4):
            raw_price = data.get(f"{price_key}{i:02d}")
            if raw_price in (None, ""):
                continue
            levels.append(
                OrderBookLevel(price=to_float(raw_price), volume=to_int(data.get(f"{qtty_key}{i:02d}")))
            )
        return levels

    bids = _levels(bid_message, "bid", "bidPrice", "bidQtty")
    asks = _levels(offer_message, "offer", "offerPrice", "offerQtty")
    symbol = ""
    for candidate in (bid_message, offer_message):
        if candidate is not None and candidate.symbol:
            symbol = candidate.symbol
            break
    stamp = (bid_message or offer_message).timestamp  # type: ignore[union-attr]
    return OrderBook(symbol=symbol, time=stamp, bids=bids, asks=asks)


# Re-exported so callers can keep importing from one module.
__all__ = [
    "OHLC",
    "OrderBook",
    "OrderBookLevel",
    "STOCK_CHANNEL_IDS",
    "DERIVATIVE_CHANNEL_IDS",
    "StreamType",
    "TCBSAuthError",
    "TCBSProtocolError",
    "TCBSWebSocketClient",
    "Ticker",
    "Trade",
    "build_auth_frame",
    "build_heartbeat_frame",
    "build_order_book",
    "build_request_frame",
    "build_subscribe_frame",
    "build_unsubscribe_frame",
    "encode_auth_token",
    "endpoint_for",
    "parse_control_frame",
    "parse_data_frame",
    "parse_derivative_frame",
    "parse_normal_frame",
    "resolve_channel_codes",
    "trade_from_message",
]


# ── Client ───────────────────────────────────────────────────────────────────


class TCBSWebSocketClient:
    """Async client for the TCBS thesis price-board streams.

    Usage::

        async with TCBSWebSocketClient(jwt_token=tok) as client:
            await client.subscribe(["FPT", "VCS"], ["bp", "bi", "tm", "mp", "op", "fe"])
            async for msg in client.messages():
                print(msg.channel, msg.payload)
    """

    def __init__(
        self,
        jwt_token: Optional[str] = None,
        use_sit: bool = False,
        stream_type: StreamType = StreamType.NORMAL,
        heartbeat_interval: float = 2.0,
        auth_timeout: float = 10.0,
        reconnect_max_attempts: int = 10,
        reconnect_base_delay: float = 1.0,
        reconnect_max_delay: float = 30.0,
    ) -> None:
        self._jwt_token = jwt_token
        # Kept for call compatibility. There is no SIT host for the thesis
        # streams (openapisit.tcbs.com.vn does not resolve).
        self._use_sit = use_sit
        if use_sit:
            _logger.warning("use_sit=True is ignored: no SIT thesis endpoint exists")
        self._stream_type = stream_type
        self._heartbeat_interval = heartbeat_interval
        self._auth_timeout = auth_timeout
        self._reconnect_max_attempts = reconnect_max_attempts
        self._reconnect_base_delay = reconnect_base_delay
        self._reconnect_max_delay = reconnect_max_delay

        self._ws: Optional[Any] = None
        self._connected = False
        self._authenticated = False
        self._subscriptions: List[Tuple[Tuple[str, ...], Tuple[str, ...]]] = []
        self._message_queue: asyncio.Queue[Any] = asyncio.Queue()
        self._heartbeat_task: Optional[asyncio.Task[None]] = None
        self._receive_task: Optional[asyncio.Task[None]] = None
        self._reconnect_attempt = 0
        self._last_message_time = 0.0
        self._server_heartbeat_timeout = _DEFAULT_HEARTBEAT_TIMEOUT
        self._replaying = False

    # -- properties ---------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated

    @property
    def stream_type(self) -> StreamType:
        return self._stream_type

    @property
    def heartbeat_interval(self) -> float:
        return self._heartbeat_interval

    @property
    def server_heartbeat_timeout(self) -> float:
        """Seconds of silence the server tolerates; default 15, set by ``d|33|15``."""
        return self._server_heartbeat_timeout

    @property
    def subscriptions(self) -> List[Tuple[Tuple[str, ...], Tuple[str, ...]]]:
        return list(self._subscriptions)

    # -- lifecycle ----------------------------------------------------------

    async def connect(self, stream_type: Optional[StreamType] = None) -> None:
        """Open the socket, authenticate, and only then allow subscribing.

        Args:
            stream_type: Overrides the type given to ``__init__``.
        """
        if stream_type is not None:
            self._stream_type = stream_type
        url = endpoint_for(self._stream_type)
        if not self._jwt_token:
            raise TCBSAuthError("jwt_token is required for TCBS WebSocket auth")

        _logger.info("Connecting to TCBS thesis stream: %s", url)
        try:
            self._ws = await websockets.connect(
                url,
                # Auto-ping must stay OFF: the server only accepts the text
                # heartbeat `d|p|||` and answers library pings with close 1002.
                ping_interval=None,
                ping_timeout=None,
                close_timeout=5,
            )
        except Exception as exc:
            _logger.error("Failed to connect to TCBS WebSocket: %s", exc)
            raise

        self._connected = True
        self._authenticated = False
        self._reconnect_attempt = 0
        self._last_message_time = time.time()

        # Receive loop first, so the auth ack can be awaited through the socket.
        self._receive_task = asyncio.create_task(self._receive_loop())
        try:
            await self._authenticate()
        except Exception:
            self._connected = False
            await self._shutdown_tasks()
            if self._ws is not None:
                await self._ws.close()
                self._ws = None
            raise

        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        _logger.info("TCBS thesis stream connected and authenticated")

    async def _authenticate(self) -> None:
        """Send ``d|a|||base64(token)`` and block until the server acknowledges."""
        await self._require_ws().send(build_auth_frame(self._jwt_token or ""))
        deadline = time.monotonic() + self._auth_timeout
        while True:
            control = await self._message_queue.get()
            if control is None:
                raise TCBSAuthError("Connection closed while waiting for auth ack")
            if isinstance(control, ControlFrame) and control.kind in (
                "auth_response",
                "auth_failure",
            ):
                body = control.value or {}
                if body.get("success"):
                    self._authenticated = True
                    _logger.info("TCBS WebSocket auth succeeded")
                    return
                error = body.get("error") or {}
                code = error.get("code", "unknown") if isinstance(error, dict) else "unknown"
                detail = error.get("message", "") if isinstance(error, dict) else str(error)
                raise TCBSAuthError(f"TCBS WebSocket auth failed (code={code}): {detail}")
            if time.monotonic() > deadline:
                raise TCBSAuthError(
                    f"TCBS WebSocket auth timed out after {self._auth_timeout:.1f}s"
                )

    async def disconnect(self) -> None:
        """Close the socket and stop background tasks."""
        self._connected = False
        self._authenticated = False
        await self._shutdown_tasks()
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception as exc:  # pragma: no cover - best effort
                _logger.debug("Error while closing socket: %s", exc)
            self._ws = None
        await self._message_queue.put(None)
        _logger.info("TCBS WebSocket disconnected")

    async def _shutdown_tasks(self) -> None:
        for name in ("_heartbeat_task", "_receive_task"):
            task = getattr(self, name)
            if task is not None and not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):  # noqa: B014
                    pass
            setattr(self, name, None)

    def _require_ws(self) -> Any:
        if self._ws is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._ws

    # -- subscriptions ------------------------------------------------------

    async def subscribe(self, symbols: Sequence[str], channels: Sequence[str]) -> None:
        """Subscribe to symbols and channels.

        Args:
            symbols: e.g. ``["FPT", "VCS"]``.
            channels: TCBS channel codes (``bi``, ``op``, …) or legacy names
                (``orderbook``, ``trade``, …).
        """
        ws = self._require_ws()
        if not self._authenticated:
            raise RuntimeError(
                "Not authenticated. Await connect() until d|0| success before subscribing."
            )
        codes = resolve_channel_codes(channels)
        self._record_subscription(tuple(symbols), codes)
        await ws.send(build_subscribe_frame(symbols, codes))

    async def unsubscribe(self, symbols: Sequence[str], channels: Sequence[str]) -> None:
        """Unsubscribe from symbols and channels (same syntax as subscribe)."""
        ws = self._require_ws()
        if not self._authenticated:
            raise RuntimeError(
                "Not authenticated. Await connect() until d|0| success before unsubscribing."
            )
        codes = resolve_channel_codes(channels)
        self._subscriptions = [
            sub for sub in self._subscriptions if not (set(symbols) <= set(sub[0]) and set(codes) <= set(sub[1]))
        ]
        await ws.send(build_unsubscribe_frame(symbols, codes))

    async def request_snapshot(self, symbols: Sequence[str], object_type: str = "tk") -> None:
        """Ask for a one-shot snapshot (``d|r|<objectType>||<objects>``)."""
        ws = self._require_ws()
        if not self._authenticated:
            raise RuntimeError(
                "Not authenticated. Await connect() until d|0| success before requesting."
            )
        await ws.send(build_request_frame(symbols, object_type))

    def _record_subscription(self, symbols: Tuple[str, ...], codes: Tuple[str, ...]) -> None:
        merged_symbols = set(symbols)
        merged_codes = set(codes)
        for index, (old_symbols, old_codes) in enumerate(self._subscriptions):
            if set(old_symbols) & merged_symbols and set(old_codes) & merged_codes:
                merged_symbols |= set(old_symbols)
                merged_codes |= set(old_codes)
                self._subscriptions.pop(index)
                break
        if symbols and codes:
            self._subscriptions.append((tuple(merged_symbols), tuple(merged_codes)))

    # -- message pump -------------------------------------------------------

    async def messages(
        self, max_messages: Optional[int] = None, timeout: Optional[float] = None
    ) -> AsyncGenerator[StreamMessage, None]:
        """Yield parsed data frames. Control frames are consumed internally."""
        count = 0
        while True:
            if timeout is None:
                item = await self._message_queue.get()
            else:
                try:
                    item = await asyncio.wait_for(self._message_queue.get(), timeout=timeout)
                except asyncio.TimeoutError:
                    return
            if item is None:
                return
            count += 1
            if isinstance(item, StreamMessage):
                yield item
            if max_messages is not None and count >= max_messages:
                return

    async def _heartbeat_loop(self) -> None:
        """Send the ``d|p|||`` text frame every ``heartbeat_interval`` seconds."""
        try:
            while self._connected:
                await asyncio.sleep(self._heartbeat_interval)
                if not self._connected or self._ws is None:
                    break
                try:
                    await self._ws.send(build_heartbeat_frame())
                    self._last_message_time = time.time()
                except Exception as exc:
                    _logger.warning("Heartbeat failed: %s", exc)
                    break
        except asyncio.CancelledError:  # pragma: no cover - shutdown path
            pass

    async def _receive_loop(self) -> None:
        """Read frames, route control frames, and queue data frames."""
        try:
            while self._connected:
                ws = self._ws
                if ws is None:
                    break
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                except asyncio.TimeoutError:
                    continue
                except Exception as exc:
                    _logger.warning("WebSocket receive ended: %s", exc)
                    break
                self._last_message_time = time.time()
                await self._handle_raw(raw)
        except asyncio.CancelledError:  # pragma: no cover - shutdown path
            pass

    async def _handle_raw(self, raw: Any) -> None:
        control = parse_control_frame(raw)
        if control is not None:
            await self._handle_control(control)
            return
        message = parse_data_frame(raw, self._stream_type)
        if message is None:
            return
        await self._message_queue.put(message)

    async def _handle_control(self, control: ControlFrame) -> None:
        if control.kind == "heartbeat_timeout":
            self._server_heartbeat_timeout = to_float(control.value, _DEFAULT_HEARTBEAT_TIMEOUT)
            _logger.debug("TCBS heartbeat timeout: %.0fs", self._server_heartbeat_timeout)
        elif control.kind == "heartbeat_pong":
            self._last_message_time = time.time()
        elif control.kind in ("auth_response", "auth_failure"):
            # Only reaches the queue when it arrives outside the auth handshake.
            await self._message_queue.put(control)

    async def _replay_subscriptions(self) -> None:
        """Re-send every subscription after a reconnect, without re-recording."""
        ws = self._require_ws()
        replaying, self._replaying = self._replaying, True
        try:
            for symbols, codes in list(self._subscriptions):
                await ws.send(build_subscribe_frame(symbols, codes))
        finally:
            self._replaying = replaying

    async def _reconnect(self) -> None:
        """Exponential backoff reconnect, capped at ``reconnect_max_delay``."""
        if self._reconnect_attempt >= self._reconnect_max_attempts:
            _logger.error(
                "Max reconnect attempts reached (%d)", self._reconnect_max_attempts
            )
            self._connected = False
            await self._message_queue.put(None)
            return
        delay = min(
            self._reconnect_base_delay * (2 ** self._reconnect_attempt),
            self._reconnect_max_delay,
        )
        self._reconnect_attempt += 1
        _logger.info(
            "Reconnecting in %.1fs (attempt %d/%d)",
            delay,
            self._reconnect_attempt,
            self._reconnect_max_attempts,
        )
        await asyncio.sleep(delay)
        await self._shutdown_tasks()
        try:
            await self.connect(self._stream_type)
            await self._replay_subscriptions()
        except Exception as exc:  # pragma: no cover - depends on live server
            _logger.error("Reconnect failed: %s", exc)
            await self._reconnect()

    async def __aenter__(self) -> "TCBSWebSocketClient":
        await self.connect(self._stream_type)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.disconnect()

    # -- typed accessors ----------------------------------------------------
    # Thin aliases over the module-level converters, kept so callers holding a
    # client do not have to import the free functions as well.

    to_trade = staticmethod(trade_from_message)
    to_order_book = staticmethod(build_order_book)