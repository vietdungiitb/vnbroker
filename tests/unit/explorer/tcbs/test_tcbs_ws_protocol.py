"""
Offline protocol tests for the TCBS ``thesis`` price-board WebSocket layer.

Every frame used here is copied verbatim from the official TCBS developer docs
(``developers.tcbs.com.vn/docs/v1.0.0/stock/ws-price-board/`` and
``.../derivative/ws-price-board``). No test in this module opens a socket.

Source refs
-----------
AC1 auth is a TEXT frame ``d|a|||base64(token)``, not an HTTP header
AC2 must wait for ``d|0|{"success":true}`` before subscribing
AC3 subscribe ``d|s|tk|<codes>|<symbols>`` / unsubscribe ``d|u|...``
AC4 heartbeat ``d|p|||`` every 2s, server sends ``d|33|15``
AC5 parse ``s|<CHANNEL>|<JSON>`` and keep the raw text
AC6 ``thesis/normal`` and ``thesis/derivative`` have separate channel IDs
AC7 ``_WS_ENDPOINTS_SIT`` is gone (openapisit.tcbs.com.vn fails DNS)
AC8 offline tests only
AC9 ``stream.py`` compatibility is preserved
"""
from __future__ import annotations

import asyncio
import functools
import inspect
import json
import re
from typing import Any, Dict, List, Optional

import pytest

from vnbroker.explorer.tcbs import websocket as ws
from vnbroker.explorer.tcbs.stream import TCBSStreamService
from vnbroker.explorer.tcbs.ws_models import (
    OrderBook,
    OrderBookLevel,
    StreamMessage,
    Ticker,
    Trade,
    trade_from_message,
)
from vnbroker.explorer.tcbs.websocket import (
    StreamType,
    TCBSAuthError,
    TCBSWebSocketClient,
    build_auth_frame,
    build_heartbeat_frame,
    build_subscribe_frame,
    build_unsubscribe_frame,
    encode_auth_token,
    parse_control_frame,
    parse_data_frame,
)

pytestmark = [pytest.mark.unit, pytest.mark.tcbs, pytest.mark.explorer]

# ── Fixtures: verbatim frames from the TCBS docs ──────────────────────────────

# Docs: "Ví dụ cụ thể với một token thực tế"
DOC_TOKEN = "igwfUq9M2IqWVhrFrYybEYKWxAxDbYzxz1RzOkp0L0S95lrMtrJDbMgFwy86r8Ir"
DOC_TOKEN_B64 = "aWd3ZlVxOU0ySXFXVmhyRnJZeWJFWUtXeEF4RGJZenh6MVJ6T2twMEwwUzk1bHJNdHJKRGJNZ0Z3eTg2cjhJcg=="

AUTH_OK = 'd|0|{"success":true,"error":null}'
AUTH_FAIL = 'd|0|{"success":false,"error":{"code":"211110","message":"Invalid JWT"}}'
HEARTBEAT_TIMEOUT_FRAME = "d|33|15"
SUBSCRIBE_ACK = "d|34|1"
HEARTBEAT_PONG = "d|p|||"

FRAME_STOCK_BID = (
    's|1|{"symbol":"TCB","bidPrice01":"24550","bidPrice02":"24500","bidPrice03":"24450",'
    '"bidQtty01":"137200","bidQtty02":"354000","bidQtty03":"292900"}'
)
FRAME_STOCK_OFFER = (
    's|2|{"symbol":"TCB","offerPrice01":"24600","offerPrice02":"24650","offerPrice03":"24700",'
    '"offerQtty01":"294000","offerQtty02":"163400","offerQtty03":"743600"}'
)
FRAME_STOCK_FOREIGN = (
    's|3|{"symbol":"HPG","buyForeignQtty":"112400","sellForeignQtty":"17380","room":"1773708397"}'
)
FRAME_STOCK_BASE_PRICE = 's|4|{"symbol":"VPD","ceilPrice":25000,"floorPrice":24100,"refPrice":24300}'
FRAME_STOCK_SESSION = 's|5|{"symbol":"VPD","high":25000,"low":24100,"avg":24300.0,"open":24600}'
FRAME_STOCK_TICKER_MATCH = (
    's|6|{"symbol":"TCB","matchPrice":"24550","matchQtty":"5000","change":200.0,'
    '"changePercent":0.8213552361396304,"totalVolume":"9745500","totalValue":"240774655000"}'
)
FRAME_STOCK_INDEX = (
    's|8|{"indexNumber":5,"index":91.43,"change":1.75,"changePercent":1.96,"volume":5.5936E7,'
    '"value":7.287094199E11,"increase":246,"decrease":58,"notChange":63,"session":"5",'
    '"ceilIncrease":19,"floorDecrease":8}'
)
FRAME_STOCK_PT_AD = (
    's|16|{"symbol":"VIC124003","price":1.00528E8,"vol":1000.0,"time":"20250808-04:10:33.917",'
    '"status":1,"color":5,"orderId":"92025080800181048","side":"B"}'
)
FRAME_STOCK_PT_MATCH = (
    's|17|{"symbol":"VND","price":23500.0,"vol":200000.0,"val":4.7E9,"time":"10:56:50",'
    '"color":4,"accumulatedValue":4.7E9}'
)
FRAME_STOCK_TMH = (
    's|22|{"symbol":"TCB","time":"14:29:30","matchPrice":"24550","matchQtty":"5000","change":200.0}'
)
FRAME_DERIV_TICKER_MATCH = (
    's|21|{"symbol":"41I1G8000","matchPrice":1870.5,"matchQtty":2,"change":-4.5,'
    '"changePercent":-0.24,"totalVolume":15234}'
)
FRAME_DERIV_BID = (
    's|23|{"symbol":"41I1G8000","bidPrice01":1870.5,"bidPrice02":1870.3,"bidPrice03":1870.0,'
    '"bidQtty01":15,"bidQtty02":8,"bidQtty03":22}'
)
FRAME_DERIV_OFFER = (
    's|24|{"symbol":"41I1G8000","offerPrice01":1870.8,"offerPrice02":1871.0,"offerPrice03":1871.5,'
    '"offerQtty01":10,"offerQtty02":5,"offerQtty03":30}'
)
FRAME_DERIV_DAY = 's|27|{"symbol":"41I1G8000","high":1885.0,"low":1862.5,"avg":1873.2,"open":1875.0}'

STOCK_FRAMES = [
    FRAME_STOCK_BID,
    FRAME_STOCK_OFFER,
    FRAME_STOCK_FOREIGN,
    FRAME_STOCK_BASE_PRICE,
    FRAME_STOCK_SESSION,
    FRAME_STOCK_TICKER_MATCH,
    FRAME_STOCK_INDEX,
    FRAME_STOCK_PT_AD,
    FRAME_STOCK_PT_MATCH,
    FRAME_STOCK_TMH,
]
DERIV_FRAMES = [
    FRAME_DERIV_TICKER_MATCH,
    FRAME_DERIV_BID,
    FRAME_DERIV_OFFER,
    FRAME_DERIV_DAY,
]


def _offline_async(fn):
    """Run a coroutine test body without pytest-asyncio (not a dependency here)."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return wrapper


# ── Offline fake socket ──────────────────────────────────────────────────────


class FakeSocket:
    """Minimal stand-in for a ``websockets`` client connection.

    Records every frame sent by the client and replays a scripted server side.
    """

    def __init__(self, server_frames: Optional[List[str]] = None) -> None:
        self.sent: List[str] = []
        self._inbox: List[str] = list(server_frames or [])
        self.closed = False
        self._recv_gate = asyncio.Event()

    async def send(self, frame: str) -> None:
        assert isinstance(frame, str), f"TCBS requires TEXT frames, got {type(frame)!r}"
        self.sent.append(frame)

    async def recv(self) -> str:
        while not self._inbox:
            self._recv_gate.clear()
            await self._recv_gate.wait()
        return self._inbox.pop(0)

    def push(self, frame: str) -> None:
        self._inbox.append(frame)
        self._recv_gate.set()

    async def close(self) -> None:
        self.closed = True
        self._recv_gate.set()


def make_client(
    monkeypatch: pytest.MonkeyPatch,
    socket: FakeSocket,
    **kwargs: Any,
) -> tuple[TCBSWebSocketClient, Dict[str, Any]]:
    """Patch ``websockets.connect`` and return (client, captured connect kwargs)."""
    captured: Dict[str, Any] = {}

    async def fake_connect(url: str, **options: Any) -> FakeSocket:
        captured["url"] = url
        captured["options"] = options
        return socket

    monkeypatch.setattr(ws.websockets, "connect", fake_connect)
    client = TCBSWebSocketClient(jwt_token=DOC_TOKEN, **kwargs)
    return client, captured


# ── AC1 — auth is a text frame, not an HTTP header ───────────────────────────


def test_ac1_auth_token_is_base64_encoded():
    assert encode_auth_token(DOC_TOKEN) == DOC_TOKEN_B64


def test_ac1_auth_frame_shape_is_pipe_delimited():
    assert build_auth_frame(DOC_TOKEN) == f"d|a|||{DOC_TOKEN_B64}"
    assert build_auth_frame(DOC_TOKEN).split("|") == ["d", "a", "", "", DOC_TOKEN_B64]


@_offline_async
async def test_ac1_connect_sends_auth_frame_and_no_authorization_header(monkeypatch):
    sock = FakeSocket([AUTH_OK])
    client, captured = make_client(monkeypatch, sock)
    await client.connect(StreamType.NORMAL)
    try:
        assert sock.sent[0] == f"d|a|||{DOC_TOKEN_B64}"
        headers = captured["options"].get("additional_headers") or {}
        assert "Authorization" not in headers
        assert "Bearer" not in json.dumps(headers)
    finally:
        await client.disconnect()


# ── AC2 / library safety — auto-ping disabled (1002 otherwise) ───────────────


@_offline_async
async def test_ac_auto_ping_is_disabled_on_connect(monkeypatch):
    sock = FakeSocket([AUTH_OK])
    client, captured = make_client(monkeypatch, sock)
    await client.connect(StreamType.NORMAL)
    try:
        options = captured["options"]
        assert options.get("ping_interval") is None
        assert options.get("ping_timeout") is None
    finally:
        await client.disconnect()


@_offline_async
async def test_ac2_auth_failure_raises_and_never_subscribes(monkeypatch):
    sock = FakeSocket([AUTH_FAIL])
    client, _ = make_client(monkeypatch, sock)
    with pytest.raises(TCBSAuthError) as excinfo:
        await client.connect(StreamType.NORMAL)
    assert "211110" in str(excinfo.value)
    assert not any(f.startswith("d|s|") for f in sock.sent)


@_offline_async
async def test_ac2_subscribe_before_auth_is_rejected(monkeypatch):
    sock = FakeSocket([])
    client, _ = make_client(monkeypatch, sock)
    with pytest.raises(RuntimeError):
        await client.subscribe(["FPT"], ["bi"])
    assert sock.sent == []


@_offline_async
async def test_ac2_client_waits_for_auth_ack_before_returning_connect(monkeypatch):
    """connect() must not resolve until the d|0| success frame arrives."""
    sock = FakeSocket([])
    client, _ = make_client(monkeypatch, sock)

    task = asyncio.ensure_future(client.connect(StreamType.NORMAL))
    await asyncio.sleep(0.05)
    assert not task.done(), "connect() returned before the auth ack arrived"
    assert sock.sent == [f"d|a|||{DOC_TOKEN_B64}"]

    sock.push(AUTH_OK)
    await asyncio.wait_for(task, timeout=2.0)
    assert client.is_connected
    assert client.is_authenticated
    await client.disconnect()


# ── AC3 — subscribe / unsubscribe wire format ────────────────────────────────


def test_ac3_subscribe_frame_matches_doc_example():
    assert (
        build_subscribe_frame(["FPT", "VCS"], ["bp", "bi", "tm", "mp", "op", "fe"])
        == "d|s|tk|bp+bi+tm+mp+op+fe|FPT,VCS"
    )


def test_ac3_subscribe_frame_single_symbol():
    assert build_subscribe_frame(["FPT"], ["bi"]) == "d|s|tk|bi|FPT"


def test_ac3_unsubscribe_frame_matches_doc_example():
    assert (
        build_unsubscribe_frame(["TCB"], ["bp", "bi", "tm", "mp", "op", "fe"])
        == "d|u|tk|bp+bi+tm+mp+op+fe|TCB"
    )


def test_ac3_subscribe_rejects_empty_input():
    with pytest.raises(ValueError):
        build_subscribe_frame([], ["bi"])
    with pytest.raises(ValueError):
        build_subscribe_frame(["FPT"], [])


@_offline_async
async def test_ac3_client_sends_pipe_frames_over_the_socket(monkeypatch):
    sock = FakeSocket([AUTH_OK])
    client, _ = make_client(monkeypatch, sock)
    await client.connect(StreamType.NORMAL)
    try:
        await client.subscribe(["FPT", "VCS"], ["bp", "bi", "tm", "mp", "op", "fe"])
        await client.unsubscribe(["TCB"], ["bp", "bi", "tm", "mp", "op", "fe"])
    finally:
        await client.disconnect()
    assert sock.sent[1] == "d|s|tk|bp+bi+tm+mp+op+fe|FPT,VCS"
    assert sock.sent[2] == "d|u|tk|bp+bi+tm+mp+op+fe|TCB"


def test_ac3_snapshot_request_frame_matches_doc_example():
    assert ws.build_request_frame(["TCB", "VCB"]) == "d|r|tk||TCB,VCB"
    assert ws.build_request_frame(["2"], object_type="ro") == "d|r|ro||2"


# ── AC4 — heartbeat ──────────────────────────────────────────────────────────


def test_ac4_heartbeat_frame_shape():
    assert build_heartbeat_frame() == "d|p|||"


def test_ac4_heartbeat_default_interval_is_two_seconds():
    assert TCBSWebSocketClient().heartbeat_interval == 2.0


@_offline_async
async def test_ac4_heartbeat_task_emits_text_frame(monkeypatch):
    sock = FakeSocket([AUTH_OK])
    client, _ = make_client(monkeypatch, sock, heartbeat_interval=0.05)
    await client.connect(StreamType.NORMAL)
    try:
        await asyncio.sleep(0.2)
    finally:
        await client.disconnect()
    assert "d|p|||" in sock.sent
    assert sock.sent.count("d|p|||") >= 2


def test_ac4_server_timeout_frame_is_understood():
    control = parse_control_frame(HEARTBEAT_TIMEOUT_FRAME)
    assert control is not None
    assert control.kind == "heartbeat_timeout"
    assert control.value == 15


def test_ac4_subscribe_ack_and_pong_are_understood():
    ack = parse_control_frame(SUBSCRIBE_ACK)
    assert ack is not None and ack.kind == "subscribe_ack"
    pong = parse_control_frame(HEARTBEAT_PONG)
    assert pong is not None and pong.kind == "heartbeat_pong"


@_offline_async
async def test_ac4_timeout_frame_updates_client_state(monkeypatch):
    sock = FakeSocket([AUTH_OK, HEARTBEAT_TIMEOUT_FRAME])
    client, _ = make_client(monkeypatch, sock)
    await client.connect(StreamType.NORMAL)
    try:
        await asyncio.sleep(0.1)
        assert client.server_heartbeat_timeout == 15
    finally:
        await client.disconnect()


# ── AC5 — data frame parsing, raw text preserved ─────────────────────────────


def test_ac5_data_frame_splits_on_pipe_and_keeps_raw_text():
    msg = parse_data_frame(FRAME_STOCK_BID, StreamType.NORMAL)
    assert isinstance(msg, StreamMessage)
    assert msg.channel_id == "1"
    assert msg.channel == "bid"
    assert msg.symbol == "TCB"
    assert msg.raw == FRAME_STOCK_BID
    assert msg.payload == {
        "symbol": "TCB",
        "bidPrice01": "24550",
        "bidPrice02": "24500",
        "bidPrice03": "24450",
        "bidQtty01": "137200",
        "bidQtty02": "354000",
        "bidQtty03": "292900",
    }


def test_ac5_control_frames_are_not_parsed_as_data():
    for frame in (AUTH_OK, HEARTBEAT_TIMEOUT_FRAME, SUBSCRIBE_ACK, HEARTBEAT_PONG):
        assert parse_data_frame(frame, StreamType.NORMAL) is None


def test_ac5_malformed_data_frame_returns_none():
    assert parse_data_frame("s|1|", StreamType.NORMAL) is None
    assert parse_data_frame("s|1|not-json", StreamType.NORMAL) is None
    assert parse_data_frame("", StreamType.NORMAL) is None


def test_ac5_stock_prices_and_volumes_stay_strings():
    """Docs: bi/op/fe/tm return string prices and volumes; bp/mp/rt return numbers."""
    bid = parse_data_frame(FRAME_STOCK_BID, StreamType.NORMAL)
    match = parse_data_frame(FRAME_STOCK_TICKER_MATCH, StreamType.NORMAL)
    base = parse_data_frame(FRAME_STOCK_BASE_PRICE, StreamType.NORMAL)
    session = parse_data_frame(FRAME_STOCK_SESSION, StreamType.NORMAL)

    assert isinstance(bid.payload["bidPrice01"], str)
    assert isinstance(bid.payload["bidQtty01"], str)
    assert isinstance(match.payload["matchPrice"], str)
    assert isinstance(match.payload["matchQtty"], str)
    assert isinstance(base.payload["ceilPrice"], int)
    assert isinstance(session.payload["high"], int)


def test_ac5_symbol_defaults_to_empty_for_index_channel():
    index = parse_data_frame(FRAME_STOCK_INDEX, StreamType.NORMAL)
    assert index.channel == "stock_index"
    assert index.symbol == ""
    assert index.payload["index"] == 91.43


def test_ac5_every_documented_stock_frame_parses():
    expected = {
        FRAME_STOCK_BID: "bid",
        FRAME_STOCK_OFFER: "offer",
        FRAME_STOCK_FOREIGN: "foreign",
        FRAME_STOCK_BASE_PRICE: "base_price",
        FRAME_STOCK_SESSION: "session",
        FRAME_STOCK_TICKER_MATCH: "ticker_match",
        FRAME_STOCK_INDEX: "stock_index",
        FRAME_STOCK_PT_AD: "pt_advertisement",
        FRAME_STOCK_PT_MATCH: "pt_match",
        FRAME_STOCK_TMH: "ticker_match_history",
    }
    for frame, channel in expected.items():
        msg = parse_data_frame(frame, StreamType.NORMAL)
        assert msg is not None, frame
        assert msg.channel == channel, frame


def test_ac5_every_documented_derivative_frame_parses():
    expected = {
        FRAME_DERIV_TICKER_MATCH: "ticker_match",
        FRAME_DERIV_BID: "bid",
        FRAME_DERIV_OFFER: "offer",
        FRAME_DERIV_DAY: "day_summary",
    }
    for frame, channel in expected.items():
        msg = parse_data_frame(frame, StreamType.DERIVATIVE)
        assert msg is not None, frame
        assert msg.channel == channel, frame


# ── AC6 — stock and derivative channel IDs are disjoint ──────────────────────


@pytest.mark.parametrize("frame", STOCK_FRAMES)
def test_ac6_stock_channel_ids_are_unknown_on_derivative(frame):
    assert parse_data_frame(frame, StreamType.DERIVATIVE) is None


@pytest.mark.parametrize("frame", DERIV_FRAMES)
def test_ac6_derivative_channel_ids_are_unknown_on_stock(frame):
    assert parse_data_frame(frame, StreamType.NORMAL) is None


def test_ac6_channel_registries_are_separate_objects():
    stock_ids = set(ws.STOCK_CHANNEL_IDS.values())
    deriv_ids = set(ws.DERIVATIVE_CHANNEL_IDS.values())
    assert stock_ids.isdisjoint(deriv_ids)
    assert stock_ids == {"1", "2", "3", "4", "5", "6", "8", "16", "17", "22"}
    assert deriv_ids == {"21", "23", "24", "27"}


def test_ac6_derivative_numbers_stay_numbers_where_stock_returns_strings():
    deriv_bid = parse_data_frame(FRAME_DERIV_BID, StreamType.DERIVATIVE)
    stock_bid = parse_data_frame(FRAME_STOCK_BID, StreamType.NORMAL)
    assert isinstance(deriv_bid.payload["bidPrice01"], float)
    assert isinstance(deriv_bid.payload["bidQtty01"], int)
    assert isinstance(stock_bid.payload["bidPrice01"], str)


def test_ac6_parser_functions_are_not_shared():
    assert ws.parse_normal_frame is not ws.parse_derivative_frame


# ── AC7 — SIT endpoints removed ──────────────────────────────────────────────


def test_ac7_sit_endpoint_table_is_gone():
    assert not hasattr(ws, "_WS_ENDPOINTS_SIT")
    assert not hasattr(ws, "_WS_ENDPOINTS")


def test_ac7_no_sit_host_anywhere_in_module_source():
    """No wss:// URL may point at the SIT host (it does not resolve)."""
    source = inspect.getsource(ws)
    assert not re.search(r"wss://[^\\s\"']*sit", source, re.IGNORECASE)


def test_ac7_production_urls_are_the_documented_ones():
    assert ws.endpoint_for(StreamType.NORMAL) == "wss://openapi.tcbs.com.vn/ws/thesis/v1/stream/normal"
    assert ws.endpoint_for(StreamType.DERIVATIVE) == "wss://openapi.tcbs.com.vn/ws/thesis/v1/stream/derivative"


# ── AC8 — offline guarantee ──────────────────────────────────────────────────


def test_ac8_endpoint_urls_never_talk_to_the_sit_host():
    for stream_type in StreamType:
        assert ws.endpoint_for(stream_type).startswith("wss://openapi.tcbs.com.vn/ws/thesis/v1/")


# ── AC9 — stream.py compatibility ────────────────────────────────────────────


def test_ac9_legacy_stream_type_names_still_resolve():
    assert StreamType.OURANOS is StreamType.NORMAL
    assert StreamType.AITHER is StreamType.NORMAL
    assert StreamType.NESOI is StreamType.DERIVATIVE
    assert StreamType.NORMAL.value == "normal"
    assert StreamType.DERIVATIVE.value == "derivative"


def test_ac9_subscribe_signature_unchanged():
    sig = inspect.signature(TCBSWebSocketClient.subscribe)
    assert list(sig.parameters) == ["self", "symbols", "channels"]
    unsig = inspect.signature(TCBSWebSocketClient.unsubscribe)
    assert list(unsig.parameters) == ["self", "symbols", "channels"]


def test_ac9_use_sit_flag_is_still_accepted():
    service = TCBSStreamService(jwt_token=DOC_TOKEN, use_sit=True)
    assert service is not None


def test_ac9_legacy_channel_names_are_accepted():
    assert ws.resolve_channel_codes(["orderbook"]) == ("bi", "op")
    assert ws.resolve_channel_codes(["trade"]) == ("tm",)
    assert ws.resolve_channel_codes(["ticker"]) == ("bp", "mp")
    with pytest.raises(ValueError):
        ws.resolve_channel_codes(["ohlc"])
    with pytest.raises(ValueError):
        ws.resolve_channel_codes(["matching"])


@_offline_async
async def test_ac9_legacy_channel_name_subscribe_still_sends_tcbs_codes(monkeypatch):
    sock = FakeSocket([AUTH_OK])
    client, _ = make_client(monkeypatch, sock)
    await client.connect(StreamType.NORMAL)
    try:
        await client.subscribe(["FPT"], ["orderbook"])
    finally:
        await client.disconnect()
    assert sock.sent[1] == "d|s|tk|bi+op|FPT"


def test_ac9_ws_models_legacy_dataclasses_are_intact():
    """test_tcbs_full_acb.py constructs these by keyword — do not break them."""
    import datetime as _dt

    ob = OrderBook(
        symbol="TCB",
        time=_dt.datetime.now(),
        bids=[OrderBookLevel(price=25000, volume=100)],
        asks=[OrderBookLevel(price=25100, volume=200)],
    )
    assert len(ob.bids) == 1 and len(ob.asks) == 1

    ticker = Ticker(
        symbol="TCB", time=_dt.datetime.now(), last_price=25100, volume=100000,
        high=25500, low=24800, open=25000,
    )
    assert ticker.last_price == 25100

    trade = Trade(symbol="TCB", time=_dt.datetime.now(), price=25100, volume=100)
    assert trade.price == 25100 and trade.volume == 100


# ── Typed conversions on top of raw frames ───────────────────────────────────


def test_trade_from_stock_ticker_match_frame():
    msg = parse_data_frame(FRAME_STOCK_TICKER_MATCH, StreamType.NORMAL)
    trade = trade_from_message(msg)
    assert isinstance(trade, Trade)
    assert trade.symbol == "TCB"
    assert trade.price == 24550.0
    assert trade.volume == 5000
    assert trade.total_value == 240774655000.0


def test_trade_from_derivative_ticker_match_frame():
    msg = parse_data_frame(FRAME_DERIV_TICKER_MATCH, StreamType.DERIVATIVE)
    trade = trade_from_message(msg)
    assert trade.symbol == "41I1G8000"
    assert trade.price == 1870.5
    assert trade.volume == 2


def test_trade_from_non_trade_channel_returns_none():
    msg = parse_data_frame(FRAME_STOCK_BID, StreamType.NORMAL)
    assert trade_from_message(msg) is None


def test_order_book_built_from_stock_bid_and_offer_frames():
    bid = parse_data_frame(FRAME_STOCK_BID, StreamType.NORMAL)
    offer = parse_data_frame(FRAME_STOCK_OFFER, StreamType.NORMAL)
    book = ws.build_order_book(bid, offer)
    assert isinstance(book, OrderBook)
    assert book.symbol == "TCB"
    assert [lvl.price for lvl in book.bids] == [24550.0, 24500.0, 24450.0]
    assert [lvl.volume for lvl in book.bids] == [137200, 354000, 292900]
    assert [lvl.price for lvl in book.asks] == [24600.0, 24650.0, 24700.0]


def test_order_book_from_derivative_frames():
    bid = parse_data_frame(FRAME_DERIV_BID, StreamType.DERIVATIVE)
    offer = parse_data_frame(FRAME_DERIV_OFFER, StreamType.DERIVATIVE)
    book = ws.build_order_book(bid, offer)
    assert [lvl.price for lvl in book.bids] == [1870.5, 1870.3, 1870.0]
    assert [lvl.volume for lvl in book.bids] == [15, 8, 22]
    assert [lvl.price for lvl in book.asks] == [1870.8, 1871.0, 1871.5]


# ── Offline end-to-end: message pump over a scripted socket ──────────────────


@_offline_async
async def test_offline_end_to_end_pump(monkeypatch):
    sock = FakeSocket([AUTH_OK, HEARTBEAT_TIMEOUT_FRAME, SUBSCRIBE_ACK] + STOCK_FRAMES)
    client, _ = make_client(monkeypatch, sock)
    await client.connect(StreamType.NORMAL)
    try:
        await client.subscribe(["TCB", "VPD"], ["bp", "bi", "tm", "mp", "op", "fe"])
        seen: List[StreamMessage] = []
        async for msg in client.messages(max_messages=len(STOCK_FRAMES)):
            seen.append(msg)
            if len(seen) >= len(STOCK_FRAMES):
                break
        assert client.server_heartbeat_timeout == 15
    finally:
        await client.disconnect()

    assert [m.channel_id for m in seen] == ["1", "2", "3", "4", "5", "6", "8", "16", "17", "22"]
    assert [m.raw for m in seen] == STOCK_FRAMES
    assert seen[0].raw.startswith("s|1|{"), "raw wire text must be preserved verbatim"


@_offline_async
async def test_offline_derivative_pump(monkeypatch):
    sock = FakeSocket([AUTH_OK] + DERIV_FRAMES)
    client, _ = make_client(monkeypatch, sock)
    await client.connect(StreamType.DERIVATIVE)
    try:
        await client.subscribe(["41I1G8000"], ["bp", "bi", "tm", "mp", "op", "fe"])
        seen = []
        async for msg in client.messages(max_messages=len(DERIV_FRAMES)):
            seen.append(msg)
            if len(seen) >= len(DERIV_FRAMES):
                break
    finally:
        await client.disconnect()
    assert [m.channel_id for m in seen] == ["21", "23", "24", "27"]