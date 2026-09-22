"""
vnbroker.broker.ssi.stream — SSIStreamManager: realtime WebSocket native.

Giao thức (đối chiếu ssi-sdk-python + ssi-sdk-go/stream/client.go):
  - Connect wss://stream.ssi.com.vn/ws/v3 + header Authorization Bearer token.
  - Frame gửi: {method: subscribe|unsubscribe|ping_pong|list_subscription,
    channel: DATA|HEARTBEAT|TRADING, topics: [...]}.
  - Nhận dispatch theo `channel`; parse theo topic:
    DATA: trade.<SYM>[@tf] / quote. / room. / market. / put. / oddlot.
    TRADING: order.<acct> (eventType fcoEvent → FCO) / portfolio.<acct>.
  - KHÔNG tồn tại topic FCO riêng: subscribe_fco_order_status là alias của
    subscribe_order_status (xác minh Go SDK) — ghi rõ docstring.
  - Dùng websockets.sync (yêu cầu websockets>=12) + listener thread.

RULE: callbacks (ít nhất on_data) PHẢI gán trước connect(), else validation error.
wait(timeout) bắt buộc có timeout sử dụng thực tế để chống treo.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from websockets.sync.client import connect as ws_connect

from vnbroker.broker.exceptions import BrokerNetworkError, BrokerValidationError
from vnbroker.broker.security.credentials import SSICredentialConfig
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.ssi._enums import Board, Timeframe, safe_parse

_logger = logging.getLogger("vnbroker.broker.ssi.stream")

_CHANNEL_DATA = "DATA"
_CHANNEL_HEARTBEAT = "HEARTBEAT"
_CHANNEL_TRADING = "TRADING"


# ─── Message dataclasses (frozen, from_dict theo key rút gọn wire) ──────────


@dataclass(frozen=True)
class TradeTick:
    symbol: str = ""
    trading_time: str = ""
    price: float = 0.0
    quantity: int = 0
    side: str = "U"
    total_volume: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradeTick":
        return cls(
            symbol=str(data.get("s", "")),
            trading_time=str(data.get("t", "")),
            price=_num(data.get("p")),
            quantity=_int(data.get("q")),
            side=str(data.get("si", "") or "U"),
            total_volume=_int(data.get("v")),
        )


@dataclass(frozen=True)
class IntervalBar:
    symbol: str = ""
    interval_time: str = ""
    trading_time: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IntervalBar":
        return cls(
            symbol=str(data.get("s", "")),
            interval_time=str(data.get("st", "")),
            trading_time=str(data.get("t", "")),
            open=_num(data.get("o")),
            high=_num(data.get("h")),
            low=_num(data.get("l")),
            close=_num(data.get("c")),
            volume=_int(data.get("v")),
        )


@dataclass(frozen=True)
class QuoteUpdate:
    symbol: str = ""
    trading_time: str = ""
    bid_prices: List[float] = field(default_factory=list)
    bid_volumes: List[int] = field(default_factory=list)
    ask_prices: List[float] = field(default_factory=list)
    ask_volumes: List[int] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QuoteUpdate":
        bids = data.get("bids", []) or []
        asks = data.get("asks", []) or []
        return cls(
            symbol=str(data.get("s", "")),
            trading_time=str(data.get("t", "")),
            bid_prices=[_num(p[0]) for p in bids if len(p) > 0],
            bid_volumes=[_int(p[1]) for p in bids if len(p) > 1],
            ask_prices=[_num(p[0]) for p in asks if len(p) > 0],
            ask_volumes=[_int(p[1]) for p in asks if len(p) > 1],
        )


@dataclass(frozen=True)
class ForeignRoom:
    symbol: str = ""
    trading_time: str = ""
    total_room: int = 0
    current_room: int = 0
    buy_quantity: int = 0
    buy_value: int = 0
    sell_quantity: int = 0
    sell_value: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ForeignRoom":
        return cls(
            symbol=str(data.get("s", "")),
            trading_time=str(data.get("t", "")),
            total_room=_int(data.get("tr")),
            current_room=_int(data.get("cr")),
            buy_quantity=_int(data.get("bq")),
            buy_value=_int(data.get("bv")),
            sell_quantity=_int(data.get("sq")),
            sell_value=_int(data.get("sv")),
        )


@dataclass(frozen=True)
class PutDeal:
    symbol: str = ""
    trading_time: str = ""
    price: float = 0.0
    quantity: int = 0
    total_quantity: int = 0
    total_value: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PutDeal":
        return cls(
            symbol=str(data.get("s", "")),
            trading_time=str(data.get("t", "")),
            price=_num(data.get("p")),
            quantity=_int(data.get("q")),
            total_quantity=_int(data.get("tq")),
            total_value=_int(data.get("tv")),
        )


@dataclass(frozen=True)
class OddLotTick:
    symbol: str = ""
    trading_time: str = ""
    price: float = 0.0
    quantity: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OddLotTick":
        return cls(
            symbol=str(data.get("s", "")),
            trading_time=str(data.get("t", "")),
            price=_num(data.get("p")),
            quantity=_int(data.get("q")),
        )


@dataclass(frozen=True)
class MarketStatus:
    market: str = ""
    status: str = ""
    trading_date: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MarketStatus":
        return cls(
            market=str(data.get("market", "")),
            status=str(data.get("status", "")),
            trading_date=str(data.get("tradingDate", "")),
        )


@dataclass(frozen=True)
class OrderUpdate:
    account_no: str = ""
    order_id: str = ""
    client_request_id: str = ""
    symbol: str = ""
    side: str = ""
    order_type: str = ""
    price: float = 0.0
    quantity: int = 0
    filled_quantity: int = 0
    status: str = ""
    message: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrderUpdate":
        return cls(
            account_no=str(data.get("accountNo", "")),
            order_id=str(data.get("orderId", "")),
            client_request_id=str(data.get("clientRequestId", "")),
            symbol=str(data.get("symbol", "")),
            side=str(data.get("side", "")),
            order_type=str(data.get("orderType", "")),
            price=_num(data.get("price")),
            quantity=_int(data.get("quantity")),
            filled_quantity=_int(data.get("filledQty")),
            status=str(data.get("orderStatus", "")),
            message=str(data.get("rejectReason", "")),
        )


@dataclass(frozen=True)
class FCOUpdate:
    fco_id: str = ""
    account_no: str = ""
    symbol: str = ""
    process_status: str = ""
    matched_quantity: int = 0
    message: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FCOUpdate":
        return cls(
            fco_id=str(data.get("fcoId", "")),
            account_no=str(data.get("accountNo", "")),
            symbol=str(data.get("symbol", "")),
            process_status=str(data.get("processStatus", "")),
            matched_quantity=_int(data.get("matchedQuantity")),
            message=str(data.get("message", "")),
        )


@dataclass(frozen=True)
class PortfolioUpdate:
    account_no: str = ""
    total_asset: float = 0.0
    cash_balance: float = 0.0
    stock_value: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PortfolioUpdate":
        return cls(
            account_no=str(data.get("accountNo", "")),
            total_asset=_num(data.get("totalAsset")),
            cash_balance=_num(data.get("cashBalance")),
            stock_value=_num(data.get("stockValue")),
        )


@dataclass(frozen=True)
class Heartbeat:
    status: str = ""
    message: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Heartbeat":
        return cls(
            status=str(data.get("status", "")),
            message=str(data.get("message", "")),
        )


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


# ─── Manager ────────────────────────────────────────────────────────────────

MessageHandler = Callable[[Any], Any]


class SSIStreamManager:
    """
    Quản lý 1 WebSocket connection SSI (sync, listener thread nền).

    Luồng dùng: gán on_data (+on_trading/on_heartbeat tùy chọn) →
    connect() → subscribe_* → wait(timeout) → disconnect().
    """

    def __init__(self, config: SSICredentialConfig, session: BrokerSession) -> None:
        self._config = config
        self._session = session
        self._ws: Any = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._handlers: Dict[str, List[MessageHandler]] = {}
        self._on_data: Optional[MessageHandler] = None
        self._on_trading: Optional[MessageHandler] = None
        self._on_heartbeat: Optional[MessageHandler] = None
        self._ping_stop = threading.Event()
        self._ping_thread: Optional[threading.Thread] = None

    # ── Callbacks (gán trước connect) ──────────────────────────────────

    @property
    def on_data(self) -> Optional[MessageHandler]:
        return self._on_data

    @on_data.setter
    def on_data(self, callback: Optional[MessageHandler]) -> None:
        self._on_data = callback
        self._set_channel_handler(
            _CHANNEL_DATA, _wrap_data(callback) if callback else None
        )

    @property
    def on_trading(self) -> Optional[MessageHandler]:
        return self._on_trading

    @on_trading.setter
    def on_trading(self, callback: Optional[MessageHandler]) -> None:
        self._on_trading = callback
        self._set_channel_handler(
            _CHANNEL_TRADING, _wrap_trading(callback) if callback else None
        )

    @property
    def on_heartbeat(self) -> Optional[MessageHandler]:
        return self._on_heartbeat

    @on_heartbeat.setter
    def on_heartbeat(self, callback: Optional[MessageHandler]) -> None:
        self._on_heartbeat = callback

        def _hb(msg: Dict[str, Any]) -> Any:
            data = msg.get("data", msg)
            payload = data if isinstance(data, dict) else {}
            return callback(Heartbeat.from_dict(payload)) if callback else None

        self._set_channel_handler(_CHANNEL_HEARTBEAT, _hb if callback else None)

    # ── Lifecycle ──────────────────────────────────────────────────────

    def connect(self, max_retries: Optional[int] = None) -> None:
        """
        Mở WS + chạy listener thread. Yêu cầu on_data đã gán + session có token.

        Raises:
            BrokerValidationError: chưa gán on_data.
            BrokerSessionExpiredError: session hết hạn (từ session.token).
            BrokerNetworkError: connect thất bại sau hết retry.
        """
        if self._on_data is None:
            raise BrokerValidationError(
                message="Gán on_data trước khi connect().",
                code="CALLBACK_REQUIRED",
                http_status=400,
            )
        if self._running:
            return
        token = self._session.token  # raise nếu hết hạn
        url = self._config.stream_url
        headers = {"Authorization": f"Bearer {token}"}
        tries = max_retries if max_retries is not None else self._config.max_retries
        tries = max(1, tries)
        last_error: Optional[Exception] = None
        for attempt in range(tries):
            try:
                self._ws = ws_connect(url, additional_headers=headers)
                break
            except Exception as exc:
                last_error = exc
                if attempt < tries - 1:
                    time.sleep(min(2.0**attempt, 8.0))
        else:
            raise BrokerNetworkError(
                message=f"WS connect thất bại sau {tries} lần: {last_error}.",
                code="WS_CONNECT_FAILED",
                http_status=0,
            ) from last_error
        self._running = True
        self._thread = threading.Thread(
            target=self._listen, daemon=True, name="vnbroker-ssi-ws"
        )
        self._thread.start()
        _logger.info("SSI WS connected.")

    def disconnect(self) -> None:
        """Đóng WS + dừng listener/ping."""
        self._running = False
        self._ping_stop.set()
        ws, self._ws = self._ws, None
        if ws is not None:
            try:
                ws.close()
            except Exception as exc:
                _logger.debug("SSI WS close: %s", exc)
        thread, self._thread = self._thread, None
        if thread is not None and thread.is_alive():
            thread.join(timeout=5.0)
        _logger.info("SSI WS disconnected.")

    def wait(self, timeout: Optional[float] = None) -> None:
        """
        Chờ connection đóng hoặc hết timeout giây (None = vô hạn —
        caller chịu trách nhiệm ngắt; khuyến nghị luôn truyền timeout).
        """
        thread = self._thread
        if thread is None or not thread.is_alive():
            return
        if timeout is None:
            while thread.is_alive():
                thread.join(timeout=0.5)
            return
        deadline = time.monotonic() + max(0.0, timeout)
        while thread.is_alive():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            thread.join(timeout=min(0.5, remaining))

    @property
    def is_connected(self) -> bool:
        """True nếu socket mở và listener đang chạy."""
        return (
            self._ws is not None
            and self._running
            and self._thread is not None
            and self._thread.is_alive()
        )

    def ping(
        self,
        on_response: Optional[MessageHandler] = None,
        interval: Optional[float] = None,
    ) -> None:
        """Ping 1 lần (interval=None) hoặc loop nền mỗi interval giây."""
        self._require_connected()

        def _send_once() -> None:
            self._send(
                {"method": "ping_pong", "channel": _CHANNEL_HEARTBEAT, "topics": []},
                on_response,
                _CHANNEL_HEARTBEAT,
            )

        if interval is None:
            _send_once()
            return
        self._ping_stop.set()
        if self._ping_thread and self._ping_thread.is_alive():
            self._ping_thread.join(timeout=interval + 1)
        self._ping_stop.clear()

        def _loop() -> None:
            while not self._ping_stop.wait(timeout=interval):
                try:
                    _send_once()
                except Exception as exc:
                    _logger.debug("SSI WS ping: %s", exc)

        self._ping_thread = threading.Thread(
            target=_loop, daemon=True, name="vnbroker-ssi-ping"
        )
        self._ping_thread.start()

    def list_subscription(self, on_response: Optional[MessageHandler] = None) -> None:
        """Liệt kê subscription server đang giữ (method list_subscription)."""
        self._require_connected()
        self._send(
            {"method": "list_subscription", "channel": _CHANNEL_DATA, "topics": []},
            on_response,
            _CHANNEL_DATA,
        )

    # ── Subscribe (DATA) ───────────────────────────────────────────────

    def subscribe_symbol(
        self, symbols: List[str], on_response: Optional[MessageHandler] = None
    ) -> None:
        """Subscribe trade + quote + room cho danh sách mã."""
        self.subscribe_symbol_trade(symbols, on_response)
        self.subscribe_symbol_quote(symbols, on_response)
        self.subscribe_symbol_room(symbols, on_response)

    def subscribe_symbol_trade(
        self, symbols: List[str], on_response: Optional[MessageHandler] = None
    ) -> None:
        self._require_connected()
        self._send(
            _topics_msg("subscribe", _CHANNEL_DATA, "trade", symbols),
            on_response,
            _CHANNEL_DATA,
        )

    def subscribe_symbol_quote(
        self, symbols: List[str], on_response: Optional[MessageHandler] = None
    ) -> None:
        self._require_connected()
        self._send(
            _topics_msg("subscribe", _CHANNEL_DATA, "quote", symbols),
            on_response,
            _CHANNEL_DATA,
        )

    def subscribe_symbol_room(
        self, symbols: List[str], on_response: Optional[MessageHandler] = None
    ) -> None:
        self._require_connected()
        self._send(
            _topics_msg("subscribe", _CHANNEL_DATA, "room", symbols),
            on_response,
            _CHANNEL_DATA,
        )

    def subscribe_symbol_put_through(
        self, symbols: List[str], on_response: Optional[MessageHandler] = None
    ) -> None:
        self._require_connected()
        self._send(
            _topics_msg("subscribe", _CHANNEL_DATA, "put", symbols),
            on_response,
            _CHANNEL_DATA,
        )

    def subscribe_symbol_odd_lot(
        self, symbols: List[str], on_response: Optional[MessageHandler] = None
    ) -> None:
        self._require_connected()
        self._send(
            _topics_msg("subscribe", _CHANNEL_DATA, "oddlot", symbols),
            on_response,
            _CHANNEL_DATA,
        )

    def subscribe_symbol_ohlcv(
        self,
        symbols: List[str],
        interval: str = "1m",
        on_response: Optional[MessageHandler] = None,
    ) -> None:
        """Subscribe OHLCV: topic trade.<SYM>@<tf>."""
        tf = safe_parse(Timeframe, (interval or "").strip())
        if tf is None:
            raise BrokerValidationError(
                message=f"timeframe không hỗ trợ: {interval!r}.",
                code="INVALID_TIMEFRAME",
                http_status=400,
            )
        self._require_connected()
        topics = [f"trade.{s.strip().upper()}@{tf.value}" for s in symbols if s.strip()]
        self._send(
            {"method": "subscribe", "channel": _CHANNEL_DATA, "topics": topics},
            on_response,
            _CHANNEL_DATA,
        )

    def subscribe_board(
        self, boards: List[str], on_response: Optional[MessageHandler] = None
    ) -> None:
        """Subscribe theo sàn (dùng giá trị board như symbol)."""
        values = [_parse_board(b) for b in boards]
        self.subscribe_symbol_trade(values, on_response)
        self.subscribe_symbol_quote(values, on_response)
        self.subscribe_symbol_room(values, on_response)

    def subscribe_index(
        self, indices: List[str], on_response: Optional[MessageHandler] = None
    ) -> None:
        """Subscribe theo chỉ số (dùng mã index như symbol)."""
        values = [i.strip().upper() for i in indices if i.strip()]
        self.subscribe_symbol_trade(values, on_response)
        self.subscribe_symbol_quote(values, on_response)
        self.subscribe_symbol_room(values, on_response)

    # ── Unsubscribe ────────────────────────────────────────────────────

    def unsubscribe_symbol(self, symbols: List[str]) -> None:
        self.unsubscribe_symbol_trade(symbols)
        self.unsubscribe_symbol_quote(symbols)
        self.unsubscribe_symbol_room(symbols)

    def unsubscribe_symbol_trade(self, symbols: List[str]) -> None:
        self._require_connected()
        self._raw_send(_topics_msg("unsubscribe", _CHANNEL_DATA, "trade", symbols))

    def unsubscribe_symbol_quote(self, symbols: List[str]) -> None:
        self._require_connected()
        self._raw_send(_topics_msg("unsubscribe", _CHANNEL_DATA, "quote", symbols))

    def unsubscribe_symbol_room(self, symbols: List[str]) -> None:
        self._require_connected()
        self._raw_send(_topics_msg("unsubscribe", _CHANNEL_DATA, "room", symbols))

    def unsubscribe_symbol_put_through(self, symbols: List[str]) -> None:
        self._require_connected()
        self._raw_send(_topics_msg("unsubscribe", _CHANNEL_DATA, "put", symbols))

    def unsubscribe_symbol_odd_lot(self, symbols: List[str]) -> None:
        self._require_connected()
        self._raw_send(_topics_msg("unsubscribe", _CHANNEL_DATA, "oddlot", symbols))

    def unsubscribe_symbol_ohlcv(
        self, symbols: List[str], interval: str = "1m"
    ) -> None:
        tf = safe_parse(Timeframe, (interval or "").strip())
        if tf is None:
            raise BrokerValidationError(
                message=f"timeframe không hỗ trợ: {interval!r}.",
                code="INVALID_TIMEFRAME",
                http_status=400,
            )
        self._require_connected()
        topics = [f"trade.{s.strip().upper()}@{tf.value}" for s in symbols if s.strip()]
        self._raw_send(
            {"method": "unsubscribe", "channel": _CHANNEL_DATA, "topics": topics}
        )

    def unsubscribe_board(self, boards: List[str]) -> None:
        values = [_parse_board(b) for b in boards]
        self.unsubscribe_symbol_trade(values)
        self.unsubscribe_symbol_quote(values)
        self.unsubscribe_symbol_room(values)

    def unsubscribe_index(self, indices: List[str]) -> None:
        values = [i.strip().upper() for i in indices if i.strip()]
        self.unsubscribe_symbol_trade(values)
        self.unsubscribe_symbol_quote(values)
        self.unsubscribe_symbol_room(values)

    # ── Subscribe (TRADING) ────────────────────────────────────────────

    def subscribe_order_status(
        self, account_no: str = "*", on_response: Optional[MessageHandler] = None
    ) -> None:
        """Subscribe trạng thái lệnh. "*" = mọi tài khoản (server-side wildcard)."""
        self._require_connected()
        self._send(
            {
                "method": "subscribe",
                "channel": _CHANNEL_TRADING,
                "topics": [f"order.{account_no or '*'}"],
            },
            on_response,
            _CHANNEL_TRADING,
        )

    def subscribe_fco_order_status(
        self, account_no: str = "*", on_response: Optional[MessageHandler] = None
    ) -> None:
        """
        ALIAS của subscribe_order_status (cùng topic order.*).
        Không tồn tại topic FCO riêng — update FCO nhận diện qua
        eventType=="fcoEvent". Ghi rõ để tránh ngộ nhận.
        """
        self.subscribe_order_status(account_no, on_response)

    def subscribe_portfolio(
        self, account_no: str = "*", on_response: Optional[MessageHandler] = None
    ) -> None:
        """Subscribe thay đổi danh mục."""
        self._require_connected()
        self._send(
            {
                "method": "subscribe",
                "channel": _CHANNEL_TRADING,
                "topics": [f"portfolio.{account_no or '*'}"],
            },
            on_response,
            _CHANNEL_TRADING,
        )

    # ── Internals ──────────────────────────────────────────────────────

    def _require_connected(self) -> None:
        if self._ws is None or not self._running:
            raise BrokerNetworkError(
                message="Chưa connect WS. Gọi connect() trước.",
                code="WS_NOT_CONNECTED",
                http_status=0,
            )

    def _set_channel_handler(
        self, channel: str, handler: Optional[MessageHandler]
    ) -> None:
        if handler is None:
            self._handlers.pop(channel, None)
        else:
            self._handlers[channel] = [handler]

    def _send(
        self,
        message: Dict[str, Any],
        on_response: Optional[MessageHandler],
        channel: str,
    ) -> None:
        if on_response is not None:
            self._set_channel_handler(channel, on_response)
        self._raw_send(message)

    def _raw_send(self, message: Dict[str, Any]) -> None:
        assert self._ws is not None
        try:
            self._ws.send(json.dumps(message))
        except Exception as exc:
            raise BrokerNetworkError(
                message=f"WS send thất bại: {exc}.",
                code="WS_SEND_FAILED",
                http_status=0,
            ) from exc

    def _listen(self) -> None:
        ws = self._ws
        if ws is None:
            return
        try:
            for raw in ws:
                if not self._running:
                    break
                try:
                    message = json.loads(raw)
                except (ValueError, TypeError):
                    _logger.warning("SSI WS: message không phải JSON.")
                    continue
                if not isinstance(message, dict):
                    continue
                channel = str(message.get("channel", ""))
                for handler in self._handlers.get(channel, []):
                    try:
                        handler(message)
                    except Exception as exc:
                        _logger.warning("SSI WS handler lỗi: %s", exc)
        except Exception as exc:
            _logger.info("SSI WS listen dừng: %s", exc)
        finally:
            self._running = False


# ─── Topic wrapping ─────────────────────────────────────────────────────────

_TIMEFRAMES = {tf.value for tf in Timeframe}


def _wrap_data(callback: MessageHandler) -> MessageHandler:
    def _wrap(msg: Dict[str, Any]) -> Any:
        topic = str(msg.get("topic", ""))
        data = msg.get("data", {})
        payload = data if isinstance(data, dict) else {}
        if topic.startswith("trade."):
            if any(topic.endswith(f"@{tf}") for tf in _TIMEFRAMES):
                return callback(IntervalBar.from_dict(payload))
            return callback(TradeTick.from_dict(payload))
        if topic.startswith("quote."):
            return callback(QuoteUpdate.from_dict(payload))
        if topic.startswith("room."):
            return callback(ForeignRoom.from_dict(payload))
        if topic.startswith("market."):
            return callback(MarketStatus.from_dict(payload))
        if topic.startswith("put."):
            return callback(PutDeal.from_dict(payload))
        if topic.startswith("oddlot."):
            return callback(OddLotTick.from_dict(payload))
        return callback(msg)

    return _wrap


def _wrap_trading(callback: MessageHandler) -> MessageHandler:
    def _wrap(msg: Dict[str, Any]) -> Any:
        topic = str(msg.get("topic", ""))
        data = msg.get("data", {})
        payload = data if isinstance(data, dict) else {}
        if topic.startswith("order."):
            if payload.get("eventType") == "fcoEvent":
                return callback(FCOUpdate.from_dict(payload))
            return callback(OrderUpdate.from_dict(payload))
        if topic.startswith("portfolio."):
            return callback(PortfolioUpdate.from_dict(payload))
        return callback(msg)

    return _wrap


def _topics_msg(
    method: str, channel: str, prefix: str, symbols: List[str]
) -> Dict[str, Any]:
    topics = [f"{prefix}.{s.strip().upper()}" for s in symbols if s.strip()]
    return {"method": method, "channel": channel, "topics": topics}


def _parse_board(board: str) -> str:
    parsed = safe_parse(Board, (board or "").strip().upper())
    if parsed is None:
        raise BrokerValidationError(
            message=f"board không hỗ trợ: {board!r}.",
            code="INVALID_BOARD",
            http_status=400,
        )
    return parsed.value
