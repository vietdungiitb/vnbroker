"""Write-gate and legacy-base-URL tests for the DNSE connector.

Proven defect these lock down: with `Trade(...)` and no `enable_write()`, ten
money methods each emitted a real outbound HTTP request -- including
`POST /accounts/orders` (place an order), `DELETE .../orders/{id}` and
`POST .../positions/{id}/close`. The four older gated methods emitted nothing.

The assertion is on the OUTBOUND REQUEST, never on "a guard call appeared".
An earlier test of this work spied on the guard function itself and stayed green
while the circuit breaker was inert.

Session/OTP is deliberately NOT gated (Owner decision 2026-10-08): gating it
would break the login flow. There is a test pinning that too.
"""
from __future__ import annotations

import pytest
import requests

from vnbroker.broker.exceptions import BrokerPermissionError
from vnbroker.connector.dnse.trade import Trade

WRITE_VERBS = {"POST", "PUT", "DELETE", "PATCH"}

# (name, call) for the ten methods that move money or configure risk
MONEY_CALLS = {
    "set_deal_pnl_config": lambda t, dry_run=False: t.set_deal_pnl_config(
        1, {}, dry_run=dry_run
    ),
    "set_account_pnl_config": lambda t, dry_run=False: t.set_account_pnl_config(
        "ACC", {}, dry_run=dry_run
    ),
    "close_deal": lambda t, dry_run=False: t.close_deal(1, dry_run=dry_run),
    "place_conditional_order": lambda t, dry_run=False: t.place_conditional_order(
        "ACC", "ACB", "cond", {}, {}, {}, dry_run=dry_run
    ),
    "cancel_conditional_order": lambda t, dry_run=False: t.cancel_conditional_order(
        "OID", dry_run=dry_run
    ),
    "post_order": lambda t, dry_run=False: t.post_order(
        "STOCK", {"accountNo": "ACC"}, "TOK", dry_run=dry_run
    ),
    "put_order": lambda t, dry_run=False: t.put_order(
        "ACC", "OID", "STOCK", {}, "TOK", dry_run=dry_run
    ),
    "cancel_order_openapi": lambda t, dry_run=False: t.cancel_order_openapi(
        "ACC", "OID", "STOCK", "TOK", dry_run=dry_run
    ),
    "create_trading_token": lambda t, dry_run=False: t.create_trading_token(
        "EMAIL", "123456", dry_run=dry_run
    ),
    "close_position": lambda t, dry_run=False: t.close_position(
        "POS", "STOCK", "TOK", dry_run=dry_run
    ),
}

SESSION_CALLS = {
    "send_email_otp": lambda t, dry_run=False: t.send_email_otp(),
}


class _Resp:
    status_code = 200
    text = "{}"
    headers: dict = {}
    content = b"{}"

    def json(self):
        return {}

    def raise_for_status(self):
        return None


@pytest.fixture
def egress():
    """Record outbound requests; return a fake response so calls complete."""
    seen: list[tuple[str, str]] = []
    original = requests.Session.request

    def spy(self, method, url, *a, **kw):
        seen.append((str(method).upper(), str(url)))
        return _Resp()

    requests.Session.request = spy
    try:
        yield seen
    finally:
        requests.Session.request = original


def _trade(**kw):
    return Trade(
        api_key="FAKE", api_secret="FAKE", base_url="https://blocked.invalid", **kw
    )


@pytest.mark.parametrize("name", sorted(MONEY_CALLS))
def test_money_write_is_blocked_without_enable_write(name, egress):
    trade = _trade()
    with pytest.raises(BrokerPermissionError):
        MONEY_CALLS[name](trade)
    writes = [w for w in egress if w[0] in WRITE_VERBS]
    assert not writes, (
        f"{name} sent a write request without enable_write(): {writes}"
    )


@pytest.mark.parametrize("name", sorted(MONEY_CALLS))
def test_money_write_goes_through_after_enable_write(name, egress):
    trade = _trade()
    trade.enable_write()
    MONEY_CALLS[name](trade)
    writes = [w for w in egress if w[0] in WRITE_VERBS]
    assert writes, f"{name} sent nothing after enable_write(); the gate over-blocks"


@pytest.mark.parametrize("name", sorted(MONEY_CALLS))
def test_dry_run_returns_envelope_and_sends_nothing(name, egress):
    trade = _trade()
    trade.enable_write()  # permission granted, but still a dry run
    result = MONEY_CALLS[name](trade, dry_run=True)
    assert not [w for w in egress if w[0] in WRITE_VERBS], (
        f"{name} sent a write despite dry_run=True"
    )
    if isinstance(result, dict):
        assert result.get("dry_run") is True, f"unexpected envelope: {result!r}"


@pytest.mark.parametrize("name", sorted(SESSION_CALLS))
def test_session_calls_are_not_gated(name, egress):
    """Owner decision 2026-10-08: the login/OTP flow must keep working.

    Pinning this prevents a later "helpful" change from gating it.
    """
    trade = _trade()
    SESSION_CALLS[name](trade)  # must not raise BrokerPermissionError
    assert egress, f"{name} issued no request at all; the test proves nothing"


# ---------- legacy base URL is settable per instance ----------
def test_legacy_base_url_defaults_to_the_class_constant():
    trade = _trade()
    assert trade._api_base_url == Trade.BASE_URL
    assert "api.dnse.com.vn" in trade._api_base_url, (
        "the default must stay on the legacy host the provider uses for this API "
        "family; changing it would break real derivative calls"
    )


def test_legacy_base_url_can_be_overridden(egress):
    """The real defect was that BASE_URL was class-level, so none of the 32
    legacy URLs could be intercepted or pointed at a sandbox."""
    trade = _trade(api_base_url="https://sandbox.invalid")
    trade.enable_write()
    trade.close_deal(123)
    assert egress, "close_deal issued no request"
    assert all(url.startswith("https://sandbox.invalid") for _, url in egress), (
        f"legacy URL ignored the override: {egress}"
    )


def test_new_openapi_host_is_independent_of_the_legacy_one(egress):
    """`base_url` (new OpenAPI) and `api_base_url` (legacy) must not collide."""
    trade = _trade(api_base_url="https://sandbox.invalid")
    trade.enable_write()
    trade.close_deal(1)          # legacy family
    trade.close_position("P", "DERIVATIVE", "TOK")  # new OpenAPI
    hosts = {url.split("/")[2] for _, url in egress}
    assert hosts == {"sandbox.invalid", "blocked.invalid"}, (
        f"the two API families leaked into each other: {hosts}"
    )