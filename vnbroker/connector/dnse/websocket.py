"""
DNSE WebSocket market-data client — implemented against the provider's current
protocol.

Source of truth: https://developers.dnse.com.vn/docs/sdk/build_websocket/
(note the trailing slash; without it the docs URL 301-loops).

What changed and why the previous implementation could never have worked
------------------------------------------------------------------------
Every one of these was wrong before, not merely incomplete:

  | aspect          | previous                          | current protocol                          |
  |-----------------|-----------------------------------|-------------------------------------------|
  | endpoint        | wss://openapi.dnse.com.vn/ws      | wss://ws-openapi.dnse.com.vn/v1/stream   |
  | auth            | REST-style HMAC in the URL query  | in-band `{"action":"auth",...}` message  |
  | signature       | `keyId=...`,`(request-target)`    | HMAC-SHA256(secret,"key:ts:nonce").hex() |
  | nonce           | not sent                          | unix microseconds, unique, new every auth|
  | subscribe       | flat `channels:[str],symbols:[str]`| `channels:[{name,symbols}]`               |
  | channel names   | `quote`, `trade`, `sec_def`       | `top_price.G1.json`, `tick.G1.json`, ... |
  | heartbeat       | WS protocol-level frames          | application-level `{"action":"pong"}`     |
  | classification  | `data.get("channel")`             | control set vs data `T` field             |

The old URL put the api_key and the signature in the query string of every
upgrade request, which is both the wrong auth model and a credential in logs.

Protocol notes that are easy to get wrong, so they are encoded below:

* `welcome` -> auth must succeed within 30s or the server drops the connection.
* `timestamp` is unix **seconds** and must be within +-5 minutes of server time.
* `nonce` is unix **microseconds** as a *string*, never reused for 10 minutes,
  and regenerated on every reconnect.
* subscribe before auth succeeds is rejected.
* symbols must be UPPERCASE.
* the server PINGs every 3 minutes and expects PONG within 60s, otherwise it
  closes with 1008. These are application-level messages, not protocol frames,
  so `ping_interval=None` is passed to `websockets.connect` on purpose.
* `connection_expired` after 8 hours is normal, not an error.
* an inbound message is a control message only when `action` is in
  CONTROL_ACTIONS. Most data messages have no `action` at all, but some (e.g.
  estimated_market_index) have *both* `action` and `T`, so "has an action" is
  not a valid discriminator.
* error payloads carry `message`, not `msg`.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from typing import Any, Callable, Dict, List, Mapping, Optional, Set

import websockets

from .core.config import DNSEConfig

logger = logging.getLogger(__name__)

#: Actions the server uses for connection/subscription lifecycle. Anything else
#: is market data, classified by its ``T`` field.
CONTROL_ACTIONS: frozenset[str] = frozenset(
    {
        "welcome",
        "auth_success",
        "subscribed",
        "unsubscribed",
        "ping",
        "pong",
        "connection_expired",
        "error",
    }
)


class DNSEWebSocketError(RuntimeError):
    """Raised for protocol-level failures (auth rejected, bad subscription)."""


class DNSEWebSocketClient:
    """WebSocket client for DNSE real-time market data.

    Usage::

        config = DNSEConfig(api_key="...", api_secret="...")
        ws = DNSEWebSocketClient(config)

        async def on_message(channel: str, data: dict):
            print(channel, data)

        await ws.connect()                      # performs the auth handshake
        await ws.subscribe(["quote", "trade"], ["VNM", "VCB"])
        await ws.run(on_message)
    """

    WS_BASE_URL = "wss://ws-openapi.dnse.com.vn/v1/stream"

    #: The server closes the connection if auth does not succeed in 30s.
    AUTH_TIMEOUT_SECONDS = 30.0
    #: Server PINGs every 3 minutes; it must be answered within 60s.
    PONG_DEADLINE_SECONDS = 60.0
    #: The provider's own SDK ships `heartbeat_interval=25.0`; keep it.
    CLIENT_PING_INTERVAL_SECONDS = 25.0
    #: Backoff ceiling for reconnects (doc: 1s -> 2s -> ... -> 60s).
    MAX_BACKOFF_SECONDS = 60.0

    #: Friendly alias -> wire channel prefix. The middle and last segments
    #: (board id / resolution, encoding) are added by :meth:`_channel_name`.
    CHANNEL_ALIASES: Dict[str, str] = {
        "trade": "tick",
        "quote": "top_price",
        "trade_extra": "tick_extra",
        "expected_price": "expected_price",
        "sec_def": "security_definition",
        "security_definition": "security_definition",
        "ohlc": "ohlc",
        "ohlc_closed": "ohlc_closed",
"market_index": "market_index",
"estimated_market_index": "estimated_market_index",
"market_index_influence": "market_index_influence",
"foreign_investor": "foreign",
        "foreign": "foreign",
        "session": "session",
    }

    #: Channels whose middle segment is a candle resolution, not a board id.
    _RESOLUTION_CHANNELS = frozenset({"ohlc", "ohlc_closed"})
    #: Channels whose middle segment is a market index name.
    _INDEX_CHANNELS = frozenset({"market_index", "estimated_market_index"})
    #: Channels shaped `{prefix}.{index}.{resolution}.{enc}` - index first,
    #: resolution second. SDK `python/dnse/websocket/client.py:356`:
    #:     f"market_index_influence.{index_name}.{resolution}.json"
    #: Not the same as `_INDEX_CHANNELS` (2 segments, no resolution) nor
    #: `_RESOLUTION_CHANNELS` (resolution is the *middle* segment).
    _INDEX_RESOLUTION_CHANNELS = frozenset({"market_index_influence"})

    #: Kept as a public alias for backwards compatibility with the old,
    #: incorrect vocabulary.
    CHANNELS: Dict[str, str] = {
        "quote": "Real-time quote updates -> top_price.{board}.{enc}",
        "trade": "Real-time trades -> tick.{board}.{enc}",
        "trade_extra": "Extended trade data -> tick_extra.{board}.{enc}",
        "ohlc": "Intraday OHLC -> ohlc.{resolution}.{enc}",
        "ohlc_closed": "Closed candles -> ohlc_closed.{resolution}.{enc}",
        "expected_price": "Expected price (ATO/ATC) -> expected_price.{board}.{enc}",
        "foreign_investor": "Foreign investor flow -> foreign.{board}.{enc}",
        "market_index": "Market index -> market_index.{index}.{enc}",
        "sec_def": "Security definition -> security_definition.{board}.{enc}",
    }

    def __init__(
        self,
        config: DNSEConfig,
        *,
        encoding: str = "json",
        reconnect: bool = True,
    ) -> None:
        if encoding not in ("json", "msgpack"):
            raise ValueError(f"encoding must be 'json' or 'msgpack', got {encoding!r}")
        # `msgpack` is deliberately NOT imported here: constructing a client to
        # inspect its URL or channel names must work without the package. The
        # failure surfaces in `_decode`, and it names the extra.
        self._config = config
        self._encoding = encoding
        self._reconnect_enabled = reconnect

        self._ws: Any = None
        self._running = False
        self._authenticated = asyncio.Event()
        self._reader_task: Optional[asyncio.Task[None]] = None
        self._heartbeat_task: Optional[asyncio.Task[None]] = None
        self._pongs_sent = 0
        self._pongs_received = 0

        #: channel key -> set of symbols, kept so a reconnect can replay them.
        self._subscriptions: Dict[str, Set[str]] = {}
        #: server-assigned capability metadata from `auth_success`.
        self._capabilities: Dict[str, Any] = {}
        self._rate_limit: Dict[str, int] = {}

        self._session_id: Optional[str] = None
        self._message_handler: Optional[Callable[[str, dict], Any]] = None
        self._reconnect_attempts = 0
        self._last_nonce = 0

    # ------------------------------------------------------------------
    # URL / encoding
    # ------------------------------------------------------------------
    @property
    def encoding(self) -> str:
        return self._encoding

    def _build_ws_url(self) -> str:
        """Build the stream URL.

        No credential is ever placed here. Authentication happens in-band after
        the `welcome` message; the previous implementation put api_key and an
        HMAC signature into the query string.
        """
        return f"{self.WS_BASE_URL}?encoding={self._encoding}"

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    def build_auth_message(self, now: Optional[float] = None) -> Dict[str, Any]:
        """Build the in-band `auth` message.

        ``signature = HMAC-SHA256(api_secret, f"{api_key}:{timestamp}:{nonce}")``

        * ``timestamp`` - unix **seconds**, must be within +-5 min of server time.
        * ``nonce`` - unix **microseconds**, a *string*, never reused for 10 min.

        The nonce is derived from the clock and additionally forced to strictly
        increase, so two auths inside the same microsecond (or after an NTP step
        backwards) cannot collide. Reusing it is an explicit replay defence on
        the server side.
        """
        moment = time.time() if now is None else now
        timestamp = int(moment)
        nonce = int(moment * 1_000_000)
        if nonce <= self._last_nonce:
            nonce = self._last_nonce + 1
        self._last_nonce = nonce

        message = f"{self._config.api_key}:{timestamp}:{nonce}"
        signature = hmac.new(
            self._config.api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return {
            "action": "auth",
            "api_key": self._config.api_key,
            "signature": signature,
            "timestamp": timestamp,
            "nonce": str(nonce),
        }

    # ------------------------------------------------------------------
    # Channels
    # ------------------------------------------------------------------
    def _channel_name(
        self,
        channel: str,
        *,
        board_id: str,
        resolution: Optional[str],
        market_index: Optional[str],
        product_group_id: Optional[str],
    ) -> str:
        """Turn a friendly alias into the wire name ``{prefix}.{mid}.{encoding}``.

        A name that already looks like a wire name is passed through untouched,
        so callers who migrated early are not forced through the alias table.
        """
        if channel.count(".") == 2:
            return channel

        prefix = self.CHANNEL_ALIASES.get(channel)
        if prefix is None:
            raise ValueError(
                f"Unknown channel {channel!r}. Supported aliases: "
                f"{sorted(self.CHANNEL_ALIASES)}, or a full wire name "
                "like 'tick.G1.json'."
            )

        if prefix in self._RESOLUTION_CHANNELS:
            mid = resolution or "1"
        elif prefix in self._INDEX_RESOLUTION_CHANNELS:
            # index comes first, resolution second, and board_id is not part
            # of this channel name at all.
            mid = f"{market_index or 'VNINDEX'}.{resolution or '1'}"
        elif prefix in self._INDEX_CHANNELS:
            mid = market_index or "VNINDEX"
        elif prefix == "session":
            mid = f"{product_group_id or 'STO'}.{board_id}"
        else:
            mid = board_id
        return f"{prefix}.{mid}.{self._encoding}"

    @staticmethod
    def _normalise_symbols(symbols: Optional[List[str]]) -> List[str]:
        """Symbols must be uppercase - the provider requires it."""
        if not symbols:
            return []
        return [s.strip().upper() for s in symbols]

    # ------------------------------------------------------------------
    # Codec
    # ------------------------------------------------------------------
    def _decode(self, raw: Any) -> Any:
        """Decode an inbound frame.

        With ``encoding=msgpack`` the server sends binary frames, so decoding
        must not assume text. There is deliberately no silent fallback to JSON:
        if msgpack is requested but unavailable, the caller must know rather
        than silently receive garbage.
        """
        if isinstance(raw, (bytes, bytearray)):
            try:
                import msgpack
            except ImportError as exc:  # pragma: no cover - depends on env
                raise DNSEWebSocketError(
                    "encoding='msgpack' requires the 'msgpack' package, which is "
                    'an optional extra: pip install "vnbroker[msgpack]". '
                    "There is deliberately no fallback to JSON — binary frames "
                    "decoded as text are garbage, and garbage that looks like "
                    "data is worse than a failure. Use encoding='json' to stream "
                    "without it."
                ) from exc
            return msgpack.unpackb(bytes(raw), raw=False)
        if isinstance(raw, str):
            return json.loads(raw)
        return raw

    def _encode(self, message: Dict[str, Any]) -> Any:
        if self._encoding == "msgpack":
            try:
                import msgpack
            except ImportError as exc:  # pragma: no cover - depends on env
                raise DNSEWebSocketError(
                    "encoding='msgpack' requires the 'msgpack' package, which is "
                    'an optional extra: pip install "vnbroker[msgpack]".'
                ) from exc
            return msgpack.packb(message, use_bin_type=True)
        return json.dumps(message)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def connect(self) -> None:
        """Connect and complete the full handshake.

        Open socket -> send `auth` -> receive `auth_success` (and the `welcome`
        that precedes it). Subscribing before `auth_success` is rejected by the
        server, so this cannot be deferred.

        The handshake reads inline instead of waiting on the background reader
        task, because that task is only started once auth succeeds. Anything
        left on the socket during the handshake would otherwise sit in the queue
        forever and `connect()` would always time out.
        """
        from vnbroker.broker.security.redaction import Redactor

        url = self._build_ws_url()
        logger.info(f"Connecting to DNSE WebSocket: {Redactor.redact_url(url)}")

        self._authenticated.clear()
        # ping_interval=None: the provider does application-level PING/PONG
        # ({"action":"ping"}), which protocol-level frames do not satisfy.
        self._ws = await websockets.connect(
            url,
            ping_interval=None,
            ping_timeout=None,
            close_timeout=10,
            max_size=8 * 1024 * 1024,
        )

        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.AUTH_TIMEOUT_SECONDS
        try:
            await self._send(self.build_auth_message())
            while not self._authenticated.is_set():
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise asyncio.TimeoutError
                raw = await asyncio.wait_for(self._ws.recv(), timeout=remaining)
                await self._handle_message(self._decode(raw))
        except asyncio.TimeoutError as exc:
            await self.disconnect()
            raise DNSEWebSocketError(
                f"DNSE WebSocket auth did not complete within "
                f"{self.AUTH_TIMEOUT_SECONDS:.0f}s"
            ) from exc
        except Exception:
            await self.disconnect()
            raise

        self._running = True
        self._reconnect_attempts = 0
        self._reader_task = asyncio.create_task(self._reader_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("DNSE WebSocket authenticated, stream ready")

    async def disconnect(self) -> None:
        """Close the connection and stop background tasks."""
        self._running = False
        for task in (self._heartbeat_task, self._reader_task):
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass
        self._heartbeat_task = None
        self._reader_task = None
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        self._authenticated.clear()
        logger.info("DNSE WebSocket disconnected")

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------
    async def _send(self, message: Dict[str, Any]) -> None:
        if self._ws is None:
            raise RuntimeError("Not connected. Call connect() first.")
        await self._ws.send(self._encode(message))

    async def _heartbeat_loop(self) -> None:
        """Proactive keepalive.

        The server PINGs every 3 minutes and drops us with close code 1008 if we
        do not answer within 60s. Symmetrically, several WS libraries (and
        mobile NATs) drop idle TCP connections, so we also ping proactively -
        the provider's SDK does the same at 25s.
        """
        while self._running:
            try:
                await asyncio.sleep(self.CLIENT_PING_INTERVAL_SECONDS)
                if not self._running:
                    return
                await self._send({"action": "ping"})
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.debug(f"keepalive ping failed: {exc}")

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------
    async def _reader_loop(self) -> None:
        while self._running:
            try:
                raw = await self._ws.recv()
            except asyncio.CancelledError:
                raise
            except websockets.exceptions.ConnectionClosed as exc:
                logger.warning(
                    f"DNSE WebSocket closed: code={exc.code} reason={exc.reason}"
                )
                await self._maybe_reconnect()
                return
            except Exception as exc:
                logger.error(f"DNSE WebSocket receive error: {exc}")
                await self._maybe_reconnect()
                return
            try:
                await self._handle_message(self._decode(raw))
            except Exception as exc:
                logger.error(f"Error handling DNSE WebSocket message: {exc}")

    @staticmethod
    def is_control(message: Dict[str, Any]) -> bool:
        """Control vs data.

        Not "has an action": `estimated_market_index` data messages carry both
        `action` and `T`. Only membership in CONTROL_ACTIONS is authoritative.
        """
        return message.get("action") in CONTROL_ACTIONS

    async def _handle_message(self, data: Any) -> None:
        if not isinstance(data, dict):
            logger.debug(f"Ignoring non-dict frame: {type(data).__name__}")
            return

        if not self.is_control(data):
            await self._dispatch_data(data)
            return

        action = data.get("action")

        if action == "welcome":
            self._session_id = data.get("session_id")
            logger.info(f"DNSE WebSocket session established: {self._session_id}")

        elif action == "auth_success":
            self._capabilities = data
            rate_limit = data.get("rate_limit")
            if isinstance(rate_limit, dict):
                self._rate_limit = dict(rate_limit)
            self._authenticated.set()
            logger.info(f"DNSE WebSocket auth_success, rate_limit={self._rate_limit}")

        elif action == "ping":
            # Must answer within 60s or the server closes with 1008. Echo the
            # timestamp so the server can measure round-trip latency.
            reply: Dict[str, Any] = {"action": "pong"}
            if data.get("timestamp") is not None:
                reply["timestamp"] = data["timestamp"]
            await self._send(reply)
            self._pongs_sent += 1

        elif action == "pong":
            self._pongs_received += 1

        elif action == "subscribed":
            logger.info(f"DNSE WebSocket subscribed: {data.get('channels')}")

        elif action == "unsubscribed":
            logger.info(f"DNSE WebSocket unsubscribed: {data.get('channels')}")

        elif action == "connection_expired":
            # 8-hour limit. Normal, and the server expects a reconnect.
            logger.info(
                "DNSE WebSocket session expired after 8h "
                f"({data.get('code')}); reconnecting"
            )

        elif action == "error":
            # The provider uses `message`, not `msg`.
            code = data.get("code")
            detail = data.get("message", data.get("msg", ""))
            logger.error(f"DNSE WebSocket error [{code}]: {detail}")
            if code in {"AUTH_FAILED", "AUTH_TIMEOUT", "INVALID_TIMESTAMP",
                        "NONCE_REUSED"}:
                raise DNSEWebSocketError(
                    f"DNSE WebSocket auth failed [{code}]: {detail}"
                )

    async def _dispatch_data(self, data: Dict[str, Any]) -> None:
        """Market data is identified by its `T` field, not by `channel`."""
        msg_type = data.get("T")
        if msg_type is None:
            logger.debug("Dropping data frame without a 'T' field")
            return
        if self._message_handler is None:
            return
        result = self._message_handler(str(msg_type), data)
        if asyncio.iscoroutine(result):
            await result

    # ------------------------------------------------------------------
    # Subscriptions
    # ------------------------------------------------------------------
    def _wire_names(
        self,
        channels: List[str],
        *,
        board_id: str,
        resolution: Optional[str],
        market_index: Optional[str],
        product_group_id: Optional[str],
    ) -> List[str]:
        return [
            self._channel_name(
                ch,
                board_id=board_id,
                resolution=resolution,
                market_index=market_index,
                product_group_id=product_group_id,
            )
            for ch in channels
        ]

    @staticmethod
    def _validate_subscription_args(
        channels: List[str],
        symbols: Optional[List[str]],
        *,
        caller: str,
    ) -> None:
        """Reject argument shapes that would silently subscribe to nothing.

        Measured against the live provider (2026-10-09): passing
        `{"quote": ["ACB"]}` as `channels` read the dict keys as channel names,
        left `symbols` at its default, and put this on the wire:

            {"action":"subscribe","channels":[{"name":"top_price.G1.json","symbols":[]}]}

        The server answered `subscribed` / `active` / `symbols: None`. So the
        caller believed two symbols were streaming and received a subscription
        for none — no exception, no warning. A bare string is the same class of
        slip: `"quote"` iterates to five one-letter channel names.

        Type hints do not help here, because a `dict` satisfies no runtime
        check against `List[str]` in plain Python.
        """
        if isinstance(channels, Mapping):
            raise TypeError(
                f"{caller}() takes channels and symbols as two separate "
                f"arguments, not one mapping. Got {type(channels).__name__} "
                f"with keys {sorted(channels)!r}.\n"
                f"Correct call: {caller}({sorted(channels)!r}, "
                f"{[v for v in channels.values()]!r})\n"
                f"A mapping here does not raise - it subscribes to zero symbols "
                f"and the server still reports 'active'."
            )
        if isinstance(channels, str) or not isinstance(channels, (list, tuple)):
            raise TypeError(
                f"{caller}() expects a list of channel names, got "
                f"{type(channels).__name__}. Pass a list: {caller}([{channels!r}], "
                f"[...]) - a bare string would be split into "
                f"{len(channels) if isinstance(channels, str) else 0} channels."
            )
        for channel in channels:
            if not isinstance(channel, str):
                raise TypeError(
                    f"{caller}() channel names must be strings, got "
                    f"{type(channel).__name__}: {channel!r}"
                )
        if symbols is not None and (
            isinstance(symbols, (str, bytes, Mapping))
            or not isinstance(symbols, (list, tuple))
        ):
            raise TypeError(
                f"{caller}() expects symbols as a list of strings, got "
                f"{type(symbols).__name__}. Correct call: "
                f"{caller}({list(channels)!r}, {list(symbols) if isinstance(symbols, (list, tuple)) else symbols!r})"
            )
        for symbol in symbols or ():
            if not isinstance(symbol, str):
                raise TypeError(
                    f"{caller}() symbols must be strings, got "
                    f"{type(symbol).__name__}: {symbol!r}"
                )

    async def subscribe(
        self,
        channels: List[str],
        symbols: Optional[List[str]] = None,
        *,
        board_id: str = "G1",
        resolution: Optional[str] = None,
        market_index: Optional[str] = None,
        product_group_id: Optional[str] = None,
    ) -> None:
        """Subscribe to market-data channels.

        Requires a successful ``auth`` first - the server rejects subscriptions
        made before ``auth_success``.

        Args:
            channels: aliases (``"quote"``, ``"trade"``, ...) or full wire names.
                A **list of strings**; a mapping or a bare string is rejected
                rather than silently subscribing to nothing.
            symbols: symbols; upper-cased automatically.
            board_id: board segment, e.g. ``G1`` for HOSE.
            resolution: candle resolution for ``ohlc``/``ohlc_closed``.
            market_index: index name for the market-index channels.
            product_group_id: product group for the ``session`` channel.

        Example:
            >>> await ws.subscribe(["quote", "trade"], ["ACB", "VNM"])

        For ``encoding="msgpack"`` install the extra first —
        ``pip install "vnbroker[msgpack]"`` — otherwise ``connect()`` raises
        rather than silently decoding as JSON.
        """
        self._validate_subscription_args(channels, symbols, caller="subscribe")

        if self._ws is None or not self._authenticated.is_set():
            raise DNSEWebSocketError(
                "Must complete auth before subscribe (server rejects "
                "pre-auth subscriptions)."
            )

        wire = self._wire_names(
            channels,
            board_id=board_id,
            resolution=resolution,
            market_index=market_index,
            product_group_id=product_group_id,
        )
        normalised = self._normalise_symbols(symbols)

        limit = self._rate_limit.get("subscriptions_max")
        if limit is not None and len(wire) > limit:
            raise DNSEWebSocketError(
                f"{len(wire)} channels requested but the server allows "
                f"{limit} (see rate_limit from auth_success)"
            )

        await self._send(
            {
                "action": "subscribe",
                "channels": [{"name": name, "symbols": normalised} for name in wire],
            }
        )

        for name in wire:
            self._subscriptions.setdefault(name, set()).update(normalised)
        logger.info(f"Subscribed to {wire} for {normalised}")

    async def unsubscribe(
        self,
        channels: List[str],
        symbols: Optional[List[str]] = None,
        *,
        board_id: str = "G1",
        resolution: Optional[str] = None,
        market_index: Optional[str] = None,
        product_group_id: Optional[str] = None,
    ) -> None:
        self._validate_subscription_args(channels, symbols, caller="unsubscribe")
        if self._ws is None:
            return
        wire = self._wire_names(
            channels,
            board_id=board_id,
            resolution=resolution,
            market_index=market_index,
            product_group_id=product_group_id,
        )
        normalised = self._normalise_symbols(symbols)
        await self._send(
            {
                "action": "unsubscribe",
                "channels": [{"name": name, "symbols": normalised} for name in wire],
            }
        )
        for name in wire:
            if symbols:
                self._subscriptions.get(name, set()).difference_update(normalised)
            else:
                self._subscriptions.pop(name, None)
        logger.info(f"Unsubscribed from {wire} for {normalised}")

    # ------------------------------------------------------------------
    # Main loop / reconnect
    # ------------------------------------------------------------------
    async def run(self, handler: Callable[[str, dict], Any]) -> None:
        """Run until the connection ends and reconnection is exhausted."""
        self._message_handler = handler
        while self._running:
            try:
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                raise
        logger.info("DNSE WebSocket run loop finished")

    async def _maybe_reconnect(self) -> None:
        if not self._reconnect_enabled:
            self._running = False
            return
        await self._reconnect()

    async def _reconnect(self) -> None:
        """Reconnect, repeating the *entire* handshake.

        A reconnect needs a brand-new `timestamp` and `nonce` (reusing the old
        nonce is rejected as a replay) and a replay of every subscription.
        """
        if self._reconnect_attempts >= 5:
            logger.error("Max reconnect attempts reached")
            self._running = False
            return

        self._reconnect_attempts += 1
        delay = min(2 ** (self._reconnect_attempts - 1), self.MAX_BACKOFF_SECONDS)
        logger.info(
            f"Reconnecting in {delay}s (attempt {self._reconnect_attempts})"
        )
        await asyncio.sleep(delay)

        replay = {name: list(syms) for name, syms in self._subscriptions.items()}
        try:
            if self._ws is not None:
                await self._ws.close()
            self._ws = None
            await self.connect()
            if replay:
                await self._send(
                    {
                        "action": "subscribe",
                        "channels": [
                            {"name": name, "symbols": syms}
                            for name, syms in replay.items()
                        ],
                    }
                )
            logger.info(f"Reconnect succeeded, replayed {len(replay)} subscriptions")
        except Exception as exc:
            logger.error(f"Reconnect failed: {exc}")
            await self._reconnect()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def get_subscriptions(self) -> Dict[str, List[str]]:
        return {name: sorted(syms) for name, syms in self._subscriptions.items()}

    @property
    def capabilities(self) -> Dict[str, Any]:
        """Raw `auth_success` payload (capabilities, rate_limit, ...)."""
        return dict(self._capabilities)

    @property
    def rate_limit(self) -> Dict[str, int]:
        """`rate_limit` reported by the server on auth_success."""
        return dict(self._rate_limit)

    @property
    def session_id(self) -> Optional[str]:
        return self._session_id

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated.is_set()

    async def __aenter__(self) -> "DNSEWebSocketClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()