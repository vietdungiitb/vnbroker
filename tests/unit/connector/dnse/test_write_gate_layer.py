"""The write gate must live at the layer that cannot be bypassed.

Finding PM-01 (`docs/PM_AUDIT_REPORT_20261009.md`): `eeb1965` put the gate on
`Trade`, and that gate works — 10/10 money methods raise, 0 requests reach the
network. But `Trade.as_openapi_client()` is **public**, it returns a real
`DNSEClient`, and `DNSEClient` had no gate at all:

    post_order             -> POST   /accounts/orders?marketType=...
    put_order              -> PUT    /accounts/{acc}/orders/{oid}
    cancel_order           -> DELETE /accounts/{acc}/orders/{oid}
    close_position         -> POST   /positions/{pos}/close
    replace_order          -> PATCH  /accounts/{acc}/orders/{oid}
    create_trading_token   -> POST   /registration/trading-token

Six real money requests with `_write_enabled = False`. One line of legitimate
code reaches them. Fixing it by adding `_require_write` to six more
`DNSEClient` methods would reproduce exactly the bug `eeb1965` just fixed:
a gate at the top of the stack, one method added = one hole.

So the gate goes to `DNSEHttpClient.request` — the single choke point every
call passes through, regardless of which service or client reached it. Adding
a new write endpoint cannot forget the gate, because there is nothing to
forget: the verb alone decides.

Assertions are made on **requests that reached the network**, never on the
presence of a guard function. A gate that is called but does nothing still
passes a "did you call the guard" test.
"""
from __future__ import annotations

import pathlib
import re

import pytest
import requests.api
import requests.sessions
from requests import Session

from vnbroker.broker.exceptions import BrokerPermissionError
from vnbroker.connector.dnse.client import DNSEClient
from vnbroker.connector.dnse.core.config import DNSEConfig
from vnbroker.connector.dnse.core.http_client import DNSEHttpClient
from vnbroker.connector.dnse.trade import Trade

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]

WRITE_VERBS = ("POST", "PUT", "PATCH", "DELETE")

# Every money method on DNSEClient, with a minimal valid argument set.
# If a new one is added here and the gate misses it, the test fails.
WRITE_CALLS = {
    "post_order": {"market_type": "STOCK", "payload": {}, "trading_token": "T"},
    "put_order": {
        "account_no": "A", "order_id": "O", "market_type": "STOCK",
        "payload": {}, "trading_token": "T",
    },
    "cancel_order": {
        "account_no": "A", "order_id": "O", "market_type": "STOCK",
        "trading_token": "T",
    },
    "replace_order": {
        "account_no": "A", "order_id": "O", "market_type": "STOCK",
        "payload": {}, "trading_token": "T",
    },
    "close_position": {
        "position_id": "P", "market_type": "STOCK", "trading_token": "T",
    },
    "create_trading_token": {"otp_type": "EMAIL", "passcode": "123456"},
}


@pytest.fixture
def egress():
    """Record every request that actually leaves the process.

    Both `requests.request` and `requests.Session.request` are stubbed:
    `http_client.py` calls the module-level `requests.request(...)`, so
    patching only the Session method would let a real request reach
    openapi.dnse.com.vn and time out after 30s instead of being recorded.

    Returns a stub that does NOT raise: a raising stub aborts the call before
    the test can assert, turning "the gate blocked this" into an
    indistinguishable EGRESS-BLOCKED error.
    """
    seen: list[tuple[str, str]] = []

    class _Resp:
        status_code = 200
        text = "{}"
        headers: dict = {}
        content = b"{}"

        def json(self):
            return {}

        def raise_for_status(self):
            return None

    def spy(self, method, url, *args, **kwargs):
        # Accepts both shapes: requests.request(method=..., url=...) and
        # Session.request(self, method, url, ...).
        seen.append((str(method).upper(), str(url)))
        return _Resp()

    def module_spy(method=None, url=None, *args, **kwargs):
        return spy(None, method if method is not None else kwargs.get("method"),
                   url if url is not None else kwargs.get("url"))

    # `requests.request` is a *re-export* of `requests.api.request`, so
    # rebinding `requests.request` alone leaves the real function reachable
    # and a genuinely network-touching test fails on an SSL timeout rather
    # than on its assertion. Patch the definition site too.
    originals = (
        Session.request,
        requests.sessions.Session.request,
        requests.api.request,
    )
    Session.request = spy
    requests.sessions.Session.request = spy
    requests.api.request = module_spy
    try:
        yield seen
    finally:
        (
            Session.request,
            requests.sessions.Session.request,
            requests.api.request,
        ) = originals


def _writes(seen):
    return [(m, u) for m, u in seen if m in WRITE_VERBS]


def _client() -> DNSEClient:
    return DNSEClient(api_key="k", api_secret="s")


def _drain(client: DNSEClient) -> None:
    for name, kwargs in WRITE_CALLS.items():
        try:
            getattr(client, name)(**kwargs)
        except Exception:
            pass


# --- the exact regression -------------------------------------------------


def test_as_openapi_client_cannot_place_an_order_with_the_gate_off(egress):
    """`Trade` gate OFF, reached through the public `as_openapi_client()`.

    This is the whole finding. Before the fix: one POST to
    `/accounts/orders` reaches the network.
    """
    trade = Trade(api_key="k", api_secret="s")
    assert trade._write_enabled is False

    raw = trade.as_openapi_client("k", "s")
    with pytest.raises(BrokerPermissionError) as caught:
        raw.post_order("STOCK", {}, "T")

    assert caught.value.code == "WRITE_NOT_ENABLED"
    assert _writes(egress) == [], (
        "P0 write gate bypassed via Trade.as_openapi_client(): "
        f"{_writes(egress)}"
    )


def test_every_write_method_of_the_ungated_client_is_blocked(egress):
    """Belt and braces: not just `post_order`.

    A gate added to five of six methods would pass a single-method test.
    """
    client = _client()
    _drain(client)

    assert _writes(egress) == [], (
        f"ungated write requests escaped: {_writes(egress)}"
    )


def test_every_write_method_raises_permission_error(egress):
    client = _client()
    for name, kwargs in WRITE_CALLS.items():
        with pytest.raises(BrokerPermissionError) as caught:
            getattr(client, name)(**kwargs)
        assert caught.value.code == "WRITE_NOT_ENABLED", name
    assert _writes(egress) == []


# --- the gate must actually open, and only then ----------------------------


def test_enabling_write_lets_the_request_through(egress):
    client = _client()
    client.enable_write()
    client.post_order("STOCK", {}, "T")

    writes = _writes(egress)
    assert len(writes) == 1, f"expected exactly one write, got {writes}"
    assert writes[0][0] == "POST"
    assert "/accounts/orders" in writes[0][1]


def test_write_gate_can_be_closed_again(egress):
    client = _client()
    client.enable_write()
    client.enable_write(False)
    _drain(client)

    assert _writes(egress) == []


def test_dry_run_needs_no_permission_and_still_sends_nothing(egress):
    """`dry_run=True` is a way to *inspect* a call, not to make one.

    It must stay reachable without `enable_write()` — otherwise the envelope
    that lets a human verify a payload becomes itself a gated action.
    """
    client = _client()
    payload = client.post_order("STOCK", {"symbol": "ACB"}, "T", dry_run=True, raw=True)

    assert payload["method"] == "POST"
    assert payload["headers"].get("trading-token") == "***REDACTED***"
    assert _writes(egress) == []


# --- reads must stay open --------------------------------------------------


def test_reads_are_not_gated(egress):
    client = _client()
    client.get_accounts()
    client.get_orders("A", "STOCK", "NORMAL")

    assert _writes(egress) == []
    assert len(egress) == 2, f"expected both reads to reach the network, got {egress}"


# --- the auth flow must not be gated (Owner decision 2026-10-08) ----------


def test_send_email_otp_is_not_gated(egress):
    """Gating this breaks login: the OTP request is how you get in.

    Decision recorded in `HANDOFF_DNSE_ROUND2_20261009.md` §1.1. Kept open,
    and kept tested so a later "gate everything non-GET" change fails loudly
    instead of breaking the login flow in production.
    """
    client = _client()
    client.send_email_otp()

    assert ("POST", "https://openapi.dnse.com.vn/registration/send-email-otp") in egress


# --- the gate cannot be forgotten by the next person -----------------------


def test_no_openapi_service_call_site_bypasses_the_http_gate():
    """Structural check: the OpenAPI side may not call `requests` directly.

    If an OpenAPI service could reach the network on its own, the gate at
    `DNSEHttpClient.request` would stop covering everything above it.

    Scope is the OpenAPI stack (`client.py` + `services/` + `core/`) only.
    `trade.py` legitimately calls `requests` itself: it speaks the *legacy*
    `api.dnse.com.vn` family, a different API with its own host, and is gated
    by `Trade._require_write`. `websocket.py` is excluded — the WebSocket
    client is audited separately (PM-13..PM-15).
    """
    offenders = []
    stack = [REPO_ROOT / "vnbroker" / "connector" / "dnse" / "client.py"]
    stack += list((REPO_ROOT / "vnbroker" / "connector" / "dnse" / "services").rglob("*.py"))
    stack += list((REPO_ROOT / "vnbroker" / "connector" / "dnse" / "core").rglob("*.py"))
    for path in stack:
        if path.name in {"http_client.py", "websocket.py"}:
            continue
        source = path.read_text(encoding="utf-8")
        if re.search(r"^\s*import requests\b", source, re.M) or re.search(
            r"\brequests\.(get|post|put|patch|delete|request)\b", source
        ):
            offenders.append(path.relative_to(REPO_ROOT).as_posix())
    assert not offenders, (
        "OpenAPI stack must go through DNSEHttpClient so the write gate covers it; "
        f"found {offenders}"
    )


def test_the_gate_is_at_the_http_layer_not_only_at_the_trade_layer():
    """Pin the *location*, so 'fixing' it by re-adding guards up top fails.

    A future refactor that keeps `Trade._require_write` and deletes the
    lower gate would look fine from `Trade` while reopening PM-01.
    """
    source = (
        REPO_ROOT / "vnbroker" / "connector" / "dnse" / "core" / "http_client.py"
    ).read_text(encoding="utf-8")

    assert "_write_enabled" in source, (
        "the write gate must live in http_client.py, not only in trade.py"
    )


def test_a_brand_new_write_verb_is_blocked_without_any_method_change(egress):
    """The property that justifies putting the gate at the HTTP layer.

    A verb nobody has written a method for is refused anyway. With per-method
    guards there is nothing to enumerate, so a new endpoint ships ungated.
    """
    http = DNSEHttpClient.__new__(DNSEHttpClient)
    http._config = DNSEConfig(api_key="k", api_secret="s")
    http._write_enabled = False

    with pytest.raises(BrokerPermissionError):
        http.request("DELETE", "/accounts/A/orders/O")

    assert _writes(egress) == []
