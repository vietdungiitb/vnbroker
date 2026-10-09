"""Two defects the live probe found that 1414 server-fake tests could not.

1. `subscribe` accepts a Mapping silently. The real signature is
   `subscribe(channels: List[str], symbols: Optional[List[str]])`, but passing
   `{"quote": ["ACB"]}` reads the dict keys as channels, leaves `symbols` at
   `None`, and the wire frame carries `"symbols": []`.

   Measured against the live provider (2026-10-09):
       sent     {"action":"subscribe","channels":[{"name":"top_price.G1.json","symbols":[]}]}
       replied  {'action':'subscribed','channel':'top_price.G1.msgpack',
                 'status':'active','symbols':None}

   The caller believes they are streaming two symbols and receives a
   subscription for none. No exception, no warning, server says `active`.

2. `msgpack` is not declared anywhere in `pyproject.toml`, so
   `encoding="msgpack"` raises at connect time for anyone who did not happen to
   install it by hand. The client deliberately refuses to fall back to JSON, so
   this is a hard failure rather than silent garbage — which makes the missing
   declaration more visible, not less.
"""
from __future__ import annotations

import asyncio
import json
import pathlib
import tomllib

import pytest

from vnbroker.connector.dnse.core.config import DNSEConfig
from vnbroker.connector.dnse.websocket import DNSEWebSocketClient

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]


class _FakeWS:
    def __init__(self):
        self.sent: list[dict] = []

    async def send(self, message):
        self.sent.append(message)


@pytest.fixture
def client():
    ws = DNSEWebSocketClient(DNSEConfig(api_key="k", api_secret="s"), encoding="json")
    fake = _FakeWS()
    ws._ws = fake
    ws._authenticated.set()
    return ws


# --- defect 1: a Mapping is silently accepted -----------------------------


def test_subscribing_with_a_mapping_is_refused(client):
    """The exact live-probe mistake: `subscribe({"quote": ["ACB", "VNM"]})`."""

    async def body():
        with pytest.raises(TypeError):
            await client.subscribe({"quote": ["ACB", "VNM"]})

    asyncio.run(body())


def test_the_refusal_names_both_arguments(client):
    """The message must show the correct call, not just say "wrong type".

    The whole cost of the bug was not knowing which argument the symbols
    belonged in.
    """

    async def body():
        with pytest.raises(TypeError) as caught:
            await client.subscribe({"quote": ["ACB"]})
        message = str(caught.value)
        assert "subscribe(" in message, message
        assert "channels" in message and "symbols" in message, message

    asyncio.run(body())


def test_nothing_is_sent_when_the_call_is_wrong(client):
    """A rejected call must not half-subscribe on its way out."""

    async def body():
        with pytest.raises(TypeError):
            await client.subscribe({"quote": ["ACB"]})

    asyncio.run(body())
    assert client._ws.sent == [], f"a refused call still sent {client._ws.sent}"


def test_the_refusal_does_not_record_a_local_subscription(client):
    """The local mirror must not claim a subscription the wire never got."""

    async def body():
        with pytest.raises(TypeError):
            await client.subscribe({"quote": ["ACB"]})

    asyncio.run(body())
    assert client.get_subscriptions() == {}


def test_the_correct_two_argument_form_still_works(client):
    """Guard against "fixing" this by banning mappings somewhere else."""

    async def body():
        await client.subscribe(["quote"], ["ACB", "VNM"])

    asyncio.run(body())
    # `_send` runs the message through `_encode`, so the wire form is the
    # encoded payload, not the dict.
    assert [json.loads(m) for m in client._ws.sent] == [
        {
            "action": "subscribe",
            "channels": [
                {"name": "top_price.G1.json", "symbols": ["ACB", "VNM"]}
            ],
        }
    ]


def test_a_single_string_is_rejected_not_split_into_letters(client):
    """`subscribe("quote", [...])` is the same class of slip: it is iterable.

    Left alone it becomes five one-letter channel names.
    """

    async def body():
        with pytest.raises(TypeError):
            await client.subscribe("quote", ["ACB"])

    asyncio.run(body())
    assert client._ws.sent == []


def test_symbols_of_the_wrong_type_are_rejected(client):
    """A dict of symbols is as silent as a dict of channels."""

    async def body():
        with pytest.raises(TypeError):
            await client.subscribe(["quote"], {"ACB": 1})

    asyncio.run(body())
    assert client._ws.sent == []


# --- defect 2: msgpack is undeclared --------------------------------------


def test_msgpack_is_declared_as_an_installable_extra():
    """`encoding="msgpack"` must be reachable via a documented install.

    `pip install -e ".[msgpack]"` — not "pip install msgpack, if you read the
    source".
    """
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    extras = data["project"].get("optional-dependencies", {})

    assert "msgpack" in extras, (
        f"msgpack missing from [project.optional-dependencies]; got {sorted(extras)}"
    )
    assert any("msgpack" in dep for dep in extras["msgpack"])


def test_the_extra_is_documented_where_the_encoding_is_offered():
    """Someone reading the docstring must learn how to turn it on."""
    source = (
        REPO_ROOT / "vnbroker" / "connector" / "dnse" / "websocket.py"
    ).read_text(encoding="utf-8")
    assert "[msgpack]" in source, (
        "the msgpack extra is not mentioned in websocket.py; nobody will know "
        "to install it"
    )
