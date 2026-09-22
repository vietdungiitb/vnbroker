"""
S6: SSI streaming — subscribe/unsubscribe, parse 10 message types, lifecycle. Mocked WS.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import pytest

from vnbroker.broker.exceptions import (
    BrokerNetworkError,
    BrokerSessionExpiredError,
    BrokerValidationError,
)
from vnbroker.broker.security.credentials import SSICredentialConfig
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.ssi import stream as stream_mod
from vnbroker.broker.ssi.stream import (
    FCOUpdate,
    ForeignRoom,
    Heartbeat,
    IntervalBar,
    MarketStatus,
    OddLotTick,
    OrderUpdate,
    PortfolioUpdate,
    PutDeal,
    QuoteUpdate,
    SSIStreamManager,
    TradeTick,
)

pytestmark = pytest.mark.ssi


class FakeWS:
    """Giả socket thật: yield messages rồi block (như connection mở)."""

    def __init__(self, incoming: List[str]) -> None:
        import threading

        self.sent: List[Dict[str, Any]] = []
        self._incoming = list(incoming)
        self.closed = False
        self.headers: Dict[str, str] = {}
        self._release = threading.Event()

    def send(self, text: str) -> None:
        self.sent.append(json.loads(text))

    def __iter__(self):  # type: ignore[no-untyped-def]
        yield from self._incoming
        self._release.wait(timeout=30)  # block như socket mở; cap chống treo

    def close(self) -> None:
        self.closed = True
        self._release.set()


def make_manager(
    monkeypatch: pytest.MonkeyPatch,
    incoming: Optional[List[str]] = None,
    authed: bool = True,
) -> tuple:
    created: Dict[str, Any] = {}

    def _factory(url: str, **kwargs: Any) -> FakeWS:
        created["url"] = url
        created["kwargs"] = kwargs
        return FakeWS(incoming or [])

    monkeypatch.setattr(stream_mod, "ws_connect", _factory)
    config = SSICredentialConfig.from_dict({"api_key": "K", "api_secret": "S"})
    session = BrokerSession(provider="SSI")
    if authed:
        session.set_token("T")
    return SSIStreamManager(config, session), created


def frame(channel: str, topic: str, data: Dict[str, Any]) -> str:
    return json.dumps({"channel": channel, "topic": topic, "data": data})


class TestLifecycle:
    def test_connect_requires_callback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mgr, _ = make_manager(monkeypatch)
        with pytest.raises(BrokerValidationError) as exc:
            mgr.connect()
        assert exc.value.code == "CALLBACK_REQUIRED"

    def test_connect_requires_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mgr, _ = make_manager(monkeypatch, authed=False)
        mgr.on_data = lambda m: m
        with pytest.raises(BrokerSessionExpiredError):
            mgr.connect()

    def test_connect_bearer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mgr, created = make_manager(monkeypatch)
        mgr.on_data = lambda m: m
        mgr.connect()
        assert created["url"] == "wss://stream.ssi.com.vn/ws/v3"
        assert created["kwargs"]["additional_headers"]["Authorization"] == "Bearer T"
        mgr.disconnect()

    def test_send_without_connect(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mgr, _ = make_manager(monkeypatch)
        mgr.on_data = lambda m: m
        with pytest.raises(BrokerNetworkError):
            mgr.subscribe_symbol(["SSI"])

    def test_wait_no_hang(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mgr, _ = make_manager(monkeypatch, incoming=[])
        received: List[Any] = []
        mgr.on_data = received.append
        mgr.connect()
        assert mgr.is_connected is True
        mgr.wait(timeout=0.2)
        mgr.disconnect()


class TestSubscribe:
    def test_symbol_all_channels(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mgr, _ = make_manager(monkeypatch)
        received: List[Any] = []
        mgr.on_data = received.append
        mgr.connect()
        ws = mgr._ws
        mgr.subscribe_symbol(["SSI", "HPG"])
        methods = [(m["method"], m["topics"]) for m in ws.sent]
        assert methods == [
            ("subscribe", ["trade.SSI", "trade.HPG"]),
            ("subscribe", ["quote.SSI", "quote.HPG"]),
            ("subscribe", ["room.SSI", "room.HPG"]),
        ]
        mgr.disconnect()

    def test_ohlcv(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mgr, _ = make_manager(monkeypatch)
        mgr.on_data = lambda m: m
        mgr.connect()
        mgr.subscribe_symbol_ohlcv(["SSI"], "1m")
        assert mgr._ws.sent[0]["topics"] == ["trade.SSI@1m"]
        with pytest.raises(BrokerValidationError):
            mgr.subscribe_symbol_ohlcv(["SSI"], "2h")
        mgr.disconnect()

    def test_board_index(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mgr, _ = make_manager(monkeypatch)
        mgr.on_data = lambda m: m
        mgr.connect()
        mgr.subscribe_board(["HOSE"])
        assert mgr._ws.sent[0]["topics"] == ["trade.HOSE"]
        mgr.subscribe_index(["VNINDEX"])
        assert mgr._ws.sent[3]["topics"] == ["trade.VNINDEX"]
        with pytest.raises(BrokerValidationError):
            mgr.subscribe_board(["NYSE"])
        mgr.disconnect()

    def test_trading_subs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mgr, _ = make_manager(monkeypatch)
        mgr.on_data = lambda m: m
        mgr.connect()
        mgr.subscribe_order_status()
        mgr.subscribe_fco_order_status("A1")
        mgr.subscribe_portfolio("A1")
        topics = [m["topics"] for m in mgr._ws.sent]
        assert topics[0] == ["order.*"]
        assert topics[1] == ["order.A1"]  # alias cùng topic order.*
        assert topics[2] == ["portfolio.A1"]
        mgr.disconnect()

    def test_unsubscribe(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mgr, _ = make_manager(monkeypatch)
        mgr.on_data = lambda m: m
        mgr.connect()
        mgr.unsubscribe_symbol(["SSI"])
        mgr.unsubscribe_symbol_put_through(["SSI"])
        mgr.unsubscribe_symbol_odd_lot(["SSI"])
        mgr.unsubscribe_symbol_ohlcv(["SSI"], "1m")
        methods = [(m["method"], m["topics"]) for m in mgr._ws.sent]
        assert methods[0] == ("unsubscribe", ["trade.SSI"])
        assert methods[1] == ("unsubscribe", ["quote.SSI"])
        assert methods[2] == ("unsubscribe", ["room.SSI"])
        assert methods[3] == ("unsubscribe", ["put.SSI"])
        assert methods[4] == ("unsubscribe", ["oddlot.SSI"])
        assert methods[5] == ("unsubscribe", ["trade.SSI@1m"])
        mgr.disconnect()

    def test_ping_and_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mgr, _ = make_manager(monkeypatch)
        mgr.on_data = lambda m: m
        mgr.connect()
        mgr.ping()
        mgr.list_subscription()
        assert mgr._ws.sent[0]["method"] == "ping_pong"
        assert mgr._ws.sent[0]["channel"] == "HEARTBEAT"
        assert mgr._ws.sent[1]["method"] == "list_subscription"
        mgr.disconnect()


class TestParsing:
    def test_all_types(self, monkeypatch: pytest.MonkeyPatch) -> None:
        incoming = [
            frame(
                "DATA",
                "trade.SSI",
                {"t": "09:15", "s": "SSI", "p": 25000, "q": 100, "si": "B", "v": 1000},
            ),
            frame(
                "DATA",
                "trade.SSI@1m",
                {
                    "st": "09:15",
                    "t": "09:15",
                    "s": "SSI",
                    "o": 1,
                    "h": 2,
                    "l": 1,
                    "c": 2,
                    "v": 10,
                },
            ),
            frame(
                "DATA",
                "quote.SSI",
                {
                    "t": "09:15",
                    "s": "SSI",
                    "bids": [[24900, 50]],
                    "asks": [[25100, 60]],
                },
            ),
            frame(
                "DATA",
                "room.SSI",
                {
                    "t": "t",
                    "s": "SSI",
                    "tr": 100,
                    "cr": 90,
                    "bq": 1,
                    "bv": 2,
                    "sq": 3,
                    "sv": 4,
                },
            ),
            frame(
                "DATA",
                "put.SSI",
                {"t": "t", "s": "SSI", "p": 1, "q": 2, "tq": 3, "tv": 4},
            ),
            frame("DATA", "oddlot.SSI", {"t": "t", "s": "SSI", "p": 1, "q": 9}),
            frame(
                "DATA",
                "market.HOSE",
                {"market": "HOSE", "status": "OPEN", "tradingDate": "2026/01/05"},
            ),
            frame(
                "TRADING",
                "order.A1",
                {"accountNo": "A1", "orderId": "O1", "orderStatus": "FF"},
            ),
            frame(
                "TRADING",
                "order.A1",
                {"eventType": "fcoEvent", "fcoId": "F1", "processStatus": "TRIT"},
            ),
            frame(
                "TRADING",
                "portfolio.A1",
                {
                    "accountNo": "A1",
                    "totalAsset": 5.0,
                    "cashBalance": 2.0,
                    "stockValue": 3.0,
                },
            ),
            json.dumps({"channel": "HEARTBEAT", "status": "OK", "message": "alive"}),
            frame("DATA", "weird.X", {"a": 1}),
            "not-json{{{",
        ]
        mgr, _ = make_manager(monkeypatch, incoming=incoming)
        data_msgs: List[Any] = []
        trade_msgs: List[Any] = []
        hb_msgs: List[Any] = []
        mgr.on_data = data_msgs.append
        mgr.on_trading = trade_msgs.append
        mgr.on_heartbeat = hb_msgs.append
        mgr.connect()
        import time as _time

        deadline = _time.monotonic() + 5.0
        while len(data_msgs) < 8 and _time.monotonic() < deadline:
            _time.sleep(0.01)

        assert isinstance(data_msgs[0], TradeTick)
        assert data_msgs[0].price == 25000 and data_msgs[0].side == "B"
        assert isinstance(data_msgs[1], IntervalBar)
        assert data_msgs[1].close == 2
        assert isinstance(data_msgs[2], QuoteUpdate)
        assert data_msgs[2].bid_prices == [24900]
        assert isinstance(data_msgs[3], ForeignRoom)
        assert data_msgs[3].current_room == 90
        assert isinstance(data_msgs[4], PutDeal)
        assert isinstance(data_msgs[5], OddLotTick)
        assert isinstance(data_msgs[6], MarketStatus)
        assert data_msgs[6].status == "OPEN"
        assert isinstance(data_msgs[7], dict)  # topic lạ → raw passthrough
        assert isinstance(trade_msgs[0], OrderUpdate)
        assert trade_msgs[0].status == "FF"
        assert isinstance(trade_msgs[1], FCOUpdate)
        assert trade_msgs[1].process_status == "TRIT"
        assert isinstance(trade_msgs[2], PortfolioUpdate)
        assert trade_msgs[2].total_asset == 5.0
        assert isinstance(hb_msgs[0], Heartbeat)
        assert hb_msgs[0].status == "OK"
        mgr.disconnect()

    def test_disconnect_closes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mgr, _ = make_manager(monkeypatch, incoming=[])
        mgr.on_data = lambda m: m
        mgr.connect()
        ws = mgr._ws
        mgr.disconnect()
        assert ws.closed is True
        assert mgr.is_connected is False
