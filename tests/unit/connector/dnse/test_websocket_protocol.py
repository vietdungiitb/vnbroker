"""Protocol conformance tests for the DNSE WebSocket client.

Source of truth: https://developers.dnse.com.vn/docs/sdk/build_websocket/

Everything runs against a fake server - no network, no credentials. Each
assertion encodes one documented rule, so a regression names the rule it broke.

The previous implementation was incompatible with the provider on host, auth
model, signature, nonce, subscribe payload shape, channel vocabulary, heartbeat
and message classification. These tests pin the documented behaviour.

Async is driven with ``asyncio.run`` inside sync tests, matching the rest of
this suite (there is no pytest-asyncio dependency).
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import pathlib

import pytest

from vnbroker.connector.dnse.websocket import (
    CONTROL_ACTIONS,
    DNSEWebSocketClient,
    DNSEWebSocketError,
)

API_KEY = "ak-test"
API_SECRET = "sk-test"
STREAM_URL = "wss://ws-openapi.dnse.com.vn/v1/stream?encoding=json"


def make_client(**kwargs) -> DNSEWebSocketClient:
    from vnbroker.connector.dnse.core.config import DNSEConfig

    return DNSEWebSocketClient(
        DNSEConfig(api_key=API_KEY, api_secret=API_SECRET), **kwargs
    )


@pytest.fixture
def client() -> DNSEWebSocketClient:
    return make_client()


# --------------------------------------------------------------------- fake
class _FakeWS:
    """Records outbound frames and hands back whatever was queued."""

    def __init__(self) -> None:
        self.sent: list = []
        self.queue: asyncio.Queue = asyncio.Queue()
        self.closed = False

    async def send(self, raw):
        self.sent.append(json.loads(raw) if isinstance(raw, (str, bytes)) else raw)

    async def recv(self):
        return await self.queue.get()

    async def close(self):
        self.closed = True

    def push(self, message):
        self.queue.put_nowait(json.dumps(message))


class _HandshakeWS(_FakeWS):
    """A fake server that plays `welcome` + `auth_success`."""

    def __init__(self) -> None:
        super().__init__()
        self.push({"action": "welcome", "session_id": "conn_test",
                   "timestamp": 1750000000, "message": "authenticate"})
        self.push({"action": "auth_success",
                   "rate_limit": {"messages_per_second": 100,
                                  "subscriptions_max": 100}})


async def _connected(client, fake=None, rate_limit=None):
    """Drive a client to the authenticated state without any network."""
    fake = fake or _FakeWS()
    client._ws = fake
    client._authenticated.set()
    if rate_limit is not None:
        await client._handle_message({"action": "auth_success", "rate_limit": rate_limit})
    return fake


# ----------------------------------------------------------------- endpoint
def test_url_uses_the_stream_endpoint_and_carries_no_credential(client):
    """Doc: wss://ws-openapi.dnse.com.vn/v1/stream?encoding={encoding}

    The old client pointed at wss://openapi.dnse.com.vn/ws and put api_key plus
    an HMAC signature in the query string - wrong host, wrong auth model, and a
    credential in every log line."""
    url = client._build_ws_url()
    assert url == STREAM_URL
    assert "api_key" not in url
    assert "signature" not in url
    assert API_KEY not in url
    assert API_SECRET not in url


def test_msgpack_encoding_is_reflected_in_the_url():
    assert make_client(encoding="msgpack")._build_ws_url().endswith("encoding=msgpack")


def test_unknown_encoding_is_rejected_up_front():
    with pytest.raises(ValueError, match="encoding"):
        make_client(encoding="protobuf")


# --------------------------------------------------------------------- auth
def test_signature_is_hmac_sha256_over_key_colon_ts_colon_nonce(client):
    """Doc: signature = HMAC-SHA256(key=api_secret, msg="{api_key}:{timestamp}:{nonce}")"""
    msg = client.build_auth_message(now=1_750_000_000.123456)
    expected = hmac.new(
        API_SECRET.encode(),
        f"{API_KEY}:{msg['timestamp']}:{msg['nonce']}".encode(),
        hashlib.sha256,
    ).hexdigest()
    assert msg["action"] == "auth"
    assert msg["api_key"] == API_KEY
    assert msg["signature"] == expected


def test_timestamp_is_unix_seconds_and_nonce_is_microseconds_as_string(client):
    """Doc: timestamp = unix seconds; nonce = unix microseconds, a string."""
    msg = client.build_auth_message(now=1_750_000_000.5)
    assert isinstance(msg["timestamp"], int)
    assert msg["timestamp"] == 1_750_000_000
    assert isinstance(msg["nonce"], str), "nonce must be a string, not an int"
    assert msg["nonce"] == "1750000000500000"


def test_auth_message_never_carries_the_secret(client):
    assert API_SECRET not in json.dumps(client.build_auth_message())


def test_nonce_is_never_reused_within_a_session(client):
    """Doc: the server keeps nonces for 10 minutes to block replay."""
    nonces = [client.build_auth_message()["nonce"] for _ in range(50)]
    assert len(set(nonces)) == len(nonces), "nonce repeated"


def test_nonce_still_increases_when_the_clock_stands_still(client):
    """Two auths inside the same microsecond must not collide."""
    moment = 1_750_000_000.0
    a = client.build_auth_message(now=moment)["nonce"]
    b = client.build_auth_message(now=moment)["nonce"]
    assert a != b
    assert int(b) > int(a)


def test_nonce_still_increases_when_the_clock_steps_backwards(client):
    """An NTP correction must not hand the server a replayable nonce."""
    first = client.build_auth_message(now=1_750_000_000.0)["nonce"]
    second = client.build_auth_message(now=1_600_000_000.0)["nonce"]
    assert int(second) > int(first)


# ----------------------------------------------------------------- channels
def _name(client, channel, **kwargs):
    kwargs.setdefault("resolution", None)
    kwargs.setdefault("market_index", None)
    kwargs.setdefault("product_group_id", None)
    return client._channel_name(channel, board_id=kwargs.pop("board_id", "G1"), **kwargs)


@pytest.mark.parametrize(
    "alias,expected",
    [
        ("quote", "top_price.G1.json"),
        ("trade", "tick.G1.json"),
        ("trade_extra", "tick_extra.G1.json"),
        ("expected_price", "expected_price.G1.json"),
        ("sec_def", "security_definition.G1.json"),
        ("foreign_investor", "foreign.G1.json"),
    ],
)
def test_alias_maps_to_the_documented_wire_name(client, alias, expected):
    """Doc table: Trade=tick, Quotes=top_price, Foreign=foreign, ..."""
    assert _name(client, alias) == expected


def test_candle_channels_use_a_resolution_not_a_board_id(client):
    assert _name(client, "ohlc", resolution="1") == "ohlc.1.json"
    assert _name(client, "ohlc_closed", resolution="15") == "ohlc_closed.15.json"


def test_index_channels_use_the_market_index_name(client):
    assert _name(client, "market_index", market_index="VNINDEX") == "market_index.VNINDEX.json"
    assert _name(client, "market_index") == "market_index.VNINDEX.json"


def test_session_channel_carries_product_group_then_board(client):
    """Doc: session.{productGroupId}.{boardId}.{encoding} -> session.STO.G1.json"""
    assert _name(client, "session", product_group_id="STO") == "session.STO.G1.json"


def test_channel_name_follows_the_encoding():
    assert _name(make_client(encoding="msgpack"), "trade") == "tick.G1.msgpack"


def test_a_full_wire_name_passes_through(client):
    """Callers who already migrated are not forced through the alias table."""
    assert _name(client, "top_price.G1.json", resolution="99") == "top_price.G1.json"


def test_unknown_alias_raises_with_a_helpful_message(client):
    with pytest.raises(ValueError, match="Unknown channel"):
        _name(client, "nope")


def test_symbols_are_upper_cased(client):
    """Doc: symbols must be uppercase."""
    assert client._normalise_symbols(["acb", " vnm ", "Hpg"]) == ["ACB", "VNM", "HPG"]
    assert client._normalise_symbols(None) == []


# -------------------------------------------------------------- subscription
def test_subscribe_sends_the_documented_nested_payload(client):
    """Doc: {"action":"subscribe","channels":[{"name":"tick.G1.json","symbols":["ACB"]}]}

    The old client sent a flat channels list of plain strings plus a top-level
    symbols list, which the server cannot parse."""

    async def body():
        fake = await _connected(client)
        await client.subscribe(["trade", "quote"], ["acb", "vnm"])

        payload = fake.sent[-1]
        assert payload["action"] == "subscribe"
        assert payload["channels"] == [
            {"name": "tick.G1.json", "symbols": ["ACB", "VNM"]},
            {"name": "top_price.G1.json", "symbols": ["ACB", "VNM"]},
        ]
        assert "symbols" not in payload, "symbols are nested per channel"

    asyncio.run(body())


def test_subscribe_before_auth_is_refused(client):
    """Doc: the server does not accept subscribe before auth succeeds."""

    async def body():
        client._ws = _FakeWS()
        with pytest.raises(DNSEWebSocketError, match="auth"):
            await client.subscribe(["trade"], ["ACB"])

    asyncio.run(body())


def test_subscribe_respects_the_server_reported_subscription_cap(client):
    """auth_success reports subscriptions_max; the client honours it instead of
    discovering the limit by being disconnected."""

    async def body():
        await _connected(client, rate_limit={"messages_per_second": 100,
                                             "subscriptions_max": 2})
        with pytest.raises(DNSEWebSocketError, match="server allows 2"):
            await client.subscribe(["trade", "quote", "ohlc"], ["ACB"])

    asyncio.run(body())


def test_unsubscribe_uses_the_same_nested_shape(client):
    async def body():
        fake = await _connected(client)
        await client.subscribe(["trade"], ["ACB"])
        await client.unsubscribe(["trade"], ["ACB"])
        assert fake.sent[-1] == {
            "action": "unsubscribe",
            "channels": [{"name": "tick.G1.json", "symbols": ["ACB"]}],
        }
        assert client.get_subscriptions()["tick.G1.json"] == []

    asyncio.run(body())


# ------------------------------------------------------------------ heartbeat
def test_server_ping_is_answered_with_pong_echoing_the_timestamp(client):
    """Doc: must answer within 60s or the server closes with 1008. Echo the
    timestamp so the server can measure round-trip latency."""

    async def body():
        fake = await _connected(client)
        await client._handle_message({"action": "ping", "timestamp": 1750000000123})
        assert fake.sent[-1] == {"action": "pong", "timestamp": 1750000000123}
        assert client._pongs_sent == 1

    asyncio.run(body())


def test_pong_without_timestamp_is_still_answered(client):
    async def body():
        fake = await _connected(client)
        await client._handle_message({"action": "ping"})
        assert fake.sent[-1] == {"action": "pong"}

    asyncio.run(body())


def test_connect_uses_application_level_heartbeat_and_in_band_auth(client):
    """The provider's PING/PONG is a JSON message, not a protocol frame, and
    auth goes over the socket. The old client used ping_interval=20 protocol
    frames and put the credential in the URL."""

    async def body():
        import websockets

        captured = {}
        fake = _HandshakeWS()

        async def fake_connect(url, **kwargs):
            captured.update(kwargs)
            captured["url"] = url
            return fake

        original = websockets.connect
        websockets.connect = fake_connect
        try:
            await client.connect()
            # asserted before disconnect(): disconnect() clears the auth flag
            assert captured.get("ping_interval") is None
            assert captured["url"] == STREAM_URL
            assert fake.sent[0]["action"] == "auth"
            assert API_SECRET not in json.dumps(fake.sent)
            assert client.is_authenticated
        finally:
            websockets.connect = original
            await client.disconnect()

    asyncio.run(body())


# ------------------------------------------------------------- classification
def test_control_actions_match_the_documented_set():
    assert CONTROL_ACTIONS == {
        "welcome", "auth_success", "subscribed", "unsubscribed",
        "ping", "pong", "connection_expired", "error",
    }


@pytest.mark.parametrize(
    "message,control",
    [
        ({"action": "ping"}, True),
        ({"action": "error", "code": "X"}, True),
        # estimated_market_index data frames carry BOTH action and T, which is
        # what makes "has an action" an invalid discriminator.
        ({"action": "estimated_market_index", "T": 32}, False),
        ({"T": 4, "symbol": "ACB"}, False),
        ({"T": 15}, False),
    ],
)
def test_classification_uses_the_control_set_not_the_presence_of_action(message, control):
    assert DNSEWebSocketClient.is_control(message) is control


def test_data_messages_reach_the_handler_with_T_as_the_channel(client):
    """Doc: classify data by data["T"] - the old client looked for `channel`."""

    async def body():
        await _connected(client)
        seen = []
        client._message_handler = lambda channel, data: seen.append((channel, data))
        await client._handle_message({"T": 4, "symbol": "ACB", "matchVolume": 100})
        assert seen == [("4", {"T": 4, "symbol": "ACB", "matchVolume": 100})]

    asyncio.run(body())


def test_async_handlers_are_awaited(client):
    async def body():
        await _connected(client)
        seen = []

        async def handler(channel, data):
            seen.append(channel)

        client._message_handler = handler
        await client._handle_message({"T": 4})
        assert seen == ["4"]

    asyncio.run(body())


# ------------------------------------------------------------ control payload
def test_error_message_uses_message_not_msg(client, caplog):
    """Doc: { "action": "error", "code": "...", "message": "..." }"""

    async def body():
        await _connected(client)
        with caplog.at_level("ERROR"):
            await client._handle_message(
                {"action": "error", "code": "BAD_CHANNEL",
                 "message": "unknown channel X"}
            )

    asyncio.run(body())
    assert "unknown channel X" in caplog.text


def test_auth_failure_is_raised_not_silently_accepted(client):
    async def body():
        client._ws = _FakeWS()
        with pytest.raises(DNSEWebSocketError, match="AUTH_FAILED"):
            await client._handle_message(
                {"action": "error", "code": "AUTH_FAILED", "message": "bad signature"}
            )

    asyncio.run(body())


def test_auth_success_captures_capabilities_and_rate_limit(client):
    async def body():
        client._ws = _FakeWS()
        client._authenticated.clear()
        await client._handle_message(
            {"action": "auth_success",
             "capabilities": {"symbols": True},
             "rate_limit": {"messages_per_second": 100, "subscriptions_max": 100}}
        )
        assert client.is_authenticated
        assert client.rate_limit == {"messages_per_second": 100, "subscriptions_max": 100}
        assert client.capabilities["capabilities"] == {"symbols": True}

    asyncio.run(body())


def test_welcome_records_the_session_id(client):
    async def body():
        client._ws = _FakeWS()
        await client._handle_message(
            {"action": "welcome", "session_id": "conn_1782199800969809263"}
        )
        assert client.session_id == "conn_1782199800969809263"

    asyncio.run(body())


def test_connection_expired_is_not_an_error(client, caplog):
    """Doc: hitting the 8h limit is normal and the server expects a reconnect."""

    async def body():
        client._ws = _FakeWS()
        with caplog.at_level("ERROR"):
            await client._handle_message(
                {"action": "connection_expired", "code": "MAX_DURATION_EXCEEDED",
                 "message": "Connection expired after 8 hours."}
            )

    asyncio.run(body())
    assert "ERROR" not in caplog.text


# --------------------------------------------------------------------- drift
def test_the_endpoint_cannot_silently_drift_back():
    """The stale host must not return as the configured base url."""
    import vnbroker.connector.dnse.websocket as mod

    assert DNSEWebSocketClient.WS_BASE_URL == (
        "wss://ws-openapi.dnse.com.vn/v1/stream"
    )
    text = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    assert "developers.dnse.com.vn/docs/sdk/build_websocket/" in text, (
        "the module must keep naming the protocol source it implements"
    )