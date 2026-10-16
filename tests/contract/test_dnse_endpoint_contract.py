"""Contract tests: DNSE endpoint paths must match the provider's own SDK.

Source of truth: https://github.com/dnse-tech/openapi-sdk
  -> python/dnse/api/client.py (665 lines, the official Python SDK)

These tests exist because three paths were wrong and nothing caught it:
  close_position      had `/accounts` in front; the SDK has none
  get_position_by_id  had `/accounts` in front; the SDK has none
  send_email_otp      posted to `/registration/otp` with a trading-token body;
                      the SDK posts to `/registration/send-email-otp` with no body

The assertion is made on the **final URL the HTTP layer emits**, not on the
string the service passes down. Asserting the intermediate argument would keep
passing if the base-URL or query assembly changed underneath.

Each expectation quotes the SDK line it came from. If DNSE changes their API,
these fail loudly instead of silently 404-ing in production.
"""
from __future__ import annotations

import pathlib

import pytest
import requests

from vnbroker.connector.dnse.core.config import DNSEConfig
from vnbroker.connector.dnse.core.http_client import DNSEHttpClient
from vnbroker.connector.dnse.services.position_service import PositionService
from vnbroker.connector.dnse.services.token_service import TokenService

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture
def capture():
    """Record the outbound request and return a synthetic response.

    It must NOT raise: a raising stub aborts the service call before the test
    gets to assert anything, which turns a path assertion into a meaningless
    "EGRESS-BLOCKED" error.
    """
    seen: dict = {}

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
        seen["method"] = str(method).upper()
        seen["url"] = str(url)
        seen["body"] = kwargs.get("data", kwargs.get("json"))
        seen["headers"] = dict(kwargs.get("headers") or {})
        return _Resp()

    original = requests.Session.request
    requests.Session.request = spy
    try:
        yield seen
    finally:
        requests.Session.request = original


@pytest.fixture
def http():
    # `write_enabled=True` because this suite asserts on the path a *write*
    # call emits (`close_position`, `create_trading_token`). The gate added in
    # `http_client.py` would otherwise raise before the assertion is reached,
    # turning a path regression into an unrelated permission error.
    #
    # Safe here: `base_url` is `blocked.invalid` and `capture` stubs the
    # socket, so no request can leave the process regardless of the flag.
    # Whether the gate itself holds is asserted in
    # `tests/unit/connector/dnse/test_write_gate_layer.py`.
    return DNSEHttpClient(
        DNSEConfig(
            api_key="FAKE",
            api_secret="FAKE",
            base_url="https://blocked.invalid",
            show_log=False,
        ),
        write_enabled=True,
    )


# SDK client.py:90   get_positions      -> GET  /accounts/{account_no}/positions
# SDK client.py:98   get_position_by_id  -> GET  /positions/{position_id}
# SDK client.py:556  close_position      -> POST /positions/{position_id}/close
def test_position_paths_match_provider_sdk(http, capture):
    svc = PositionService(http)

    svc.get_positions(account_no="ACC", market_type="STOCK")
    assert capture["url"] == (
        "https://blocked.invalid/accounts/ACC/positions?marketType=STOCK"
    )
    assert capture["method"] == "GET"

    # `position_id` phải là SỐ: đo production 2026-10-16 cho thấy
    # `GET /positions/fake` -> `500 For input string: "fake"`. Vnbroker chặn
    # sai hình thức ngay ở client, nên test này dùng giá trị số hợp lệ.
    # Không sửa *nghĩa* của phép kiểm: path vẫn là `/positions/{id}`.
    svc.get_position_by_id(market_type="DERIVATIVE", position_id="1")
    assert capture["url"] == (
        "https://blocked.invalid/positions/1?marketType=DERIVATIVE"
    )
    assert capture["method"] == "GET"

    svc.close_position(
        position_id="POS1", market_type="DERIVATIVE", trading_token="TOK"
    )
    assert capture["url"] == (
        "https://blocked.invalid/positions/POS1/close?marketType=DERIVATIVE"
    )
    assert capture["method"] == "POST"
    assert capture["headers"].get("trading-token") == "TOK"


def test_by_id_form_is_not_account_scoped(http, capture):
    """The exact regression: both forms used to be account-scoped.

    Guarded separately so merging the two shapes back is a test failure.
    """
    svc = PositionService(http)

    svc.get_positions(account_no="ACC", market_type="STOCK")
    listing = capture["url"]
    svc.get_position_by_id(market_type="DERIVATIVE", position_id="1")
    by_id = capture["url"]

    assert listing.startswith("https://blocked.invalid/accounts/")
    assert by_id.startswith("https://blocked.invalid/positions/")
    assert "/accounts/positions/" not in by_id


# SDK client.py:532  create_trading_token -> POST /registration/trading-token (with body)
# SDK client.py:549  send_email_otp        -> POST /registration/send-email-otp (no body)
def test_token_paths_match_provider_sdk(http, capture):
    svc = TokenService(http)

    svc.send_email_otp()
    assert capture["url"] == "https://blocked.invalid/registration/send-email-otp"
    assert capture["method"] == "POST"
    assert not capture["body"], (
        f"send_email_otp must send no body, got {capture['body']!r}"
    )

    svc.create_trading_token(otp_type="EMAIL", passcode="123456")
    assert capture["url"] == "https://blocked.invalid/registration/trading-token"
    assert "EMAIL" in (capture["body"] or "")


def test_no_registration_otp_path_remains():
    """`/registration/otp` was a conflation of the trading-token call.

    Nothing should call it any more; if a future change reintroduces it, fail
    here rather than 404 in production.
    """
    offenders = [
        p.relative_to(REPO_ROOT).as_posix()
        for p in (REPO_ROOT / "vnbroker").rglob("*.py")
        if '"/registration/otp"' in p.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        f"/registration/otp is not an endpoint in the provider SDK; found in {offenders}"
    )