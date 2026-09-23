"""
S0: SSI foundation — paths/enums/signing/transport/credentials/redaction.
Mocked hoàn toàn (không mạng, không creds thật).
"""

from __future__ import annotations

import base64
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.etree.ElementTree import Element, SubElement, tostring

import pytest
import requests

from vnbroker.broker import ssi as ssi_pkg
from vnbroker.broker.exceptions import (
    BrokerAuthError,
    BrokerError,
    BrokerNetworkError,
    BrokerRateLimitError,
    BrokerValidationError,
)
from vnbroker.broker.security.credentials import SSICredentialConfig
from vnbroker.broker.security.redaction import Redactor
from vnbroker.broker.ssi import _enums, _paths, _signing, _transport, _utils
from vnbroker.broker.ssi._transport import SSIHttpClient

pytestmark = pytest.mark.ssi

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "ssi"


# ─── Helpers ────────────────────────────────────────────────────────────────


def _b64_int(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.b64encode(raw).decode("ascii")


def make_test_rsa_key() -> tuple[str, Any]:
    """Sinh RSA-1024 test-only → (private_key base64-XML SDK-format, public_key)."""
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    nums = key.private_numbers()
    root = Element("RSAKeyValue")
    for tag, val in (
        ("Modulus", nums.public_numbers.n),
        ("Exponent", nums.public_numbers.e),
        ("D", nums.d),
    ):
        node = SubElement(root, tag)
        node.text = _b64_int(val)
    xml = tostring(root, encoding="unicode")
    private_key = base64.b64encode(xml.encode("utf-8")).decode("ascii")
    return private_key, key.public_key()


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload: Any = None,
        headers: Optional[Dict[str, str]] = None,
        raw_text: str = "",
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = raw_text or json.dumps(payload or {})

    def json(self) -> Any:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    """Fake requests.Session: trả response theo kịch bản, ghi lại calls."""

    def __init__(self, script: List[Any]) -> None:
        self._script = list(script)
        self.headers: Dict[str, str] = {}
        self.calls: List[Dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        assert isinstance(item, FakeResponse)
        return item

    def close(self) -> None:
        return None


def make_client(
    monkeypatch: pytest.MonkeyPatch,
    script: List[Any],
    **kwargs: Any,
) -> tuple[SSIHttpClient, FakeSession]:
    fake = FakeSession(script)
    monkeypatch.setattr(_transport.requests, "Session", lambda: fake)
    params: Dict[str, Any] = {"base_url": "https://api.ssi.com.vn", "rate_limit_rps": 0}
    params.update(kwargs)
    return SSIHttpClient(**params), fake


# ─── Paths ──────────────────────────────────────────────────────────────────


class TestPaths:
    def test_twenty_distinct_paths_all_v3(self) -> None:
        paths = [
            _paths.EP_ACCESS_TOKEN,
            _paths.EP_REFRESH_TOKEN,
            _paths.EP_REQUEST_OTP,
            _paths.EP_DATA_OHLC,
            _paths.EP_DATA_OHLC_DOWNLOAD,
            _paths.EP_DATA_MASTER_DATA,
            _paths.EP_DATA_INDEX_LIST,
            _paths.EP_DATA_INDEX_SUMMARY,
            _paths.EP_DATA_SECURITIES_BY_BOARD,
            _paths.EP_DATA_SECURITIES_SUMMARY,
            _paths.EP_ACCOUNT_INFO,
            _paths.EP_ACCOUNT_BALANCE,
            _paths.EP_ACCOUNT_PPMMR,
            _paths.EP_POSITIONS,
            _paths.EP_ORDER_HISTORY,
            _paths.EP_TRADING_ORDER,
            _paths.EP_TRADING_MAX_BUY_SELL,
            _paths.EP_TRADING_FCO_ORDER,
            _paths.EP_TRADING_FCO_LIST,
            _paths.EP_TRADING_FCO_ORDER_BOOK,
        ]
        assert len(set(paths)) == 20
        assert all(p.startswith("/api/v3/") for p in paths)

    def test_smart_otp_pending_constants(self) -> None:
        assert _paths.SMART_OTP_PENDING_STATUS == 202
        assert _paths.SMART_OTP_PENDING_CODE == 401114

    def test_default_urls(self) -> None:
        assert _paths.DEFAULT_API_URL == "https://api.ssi.com.vn"
        assert _paths.DEFAULT_STREAMING_URL == "wss://stream.ssi.com.vn/ws/v3"


# ─── Enums ──────────────────────────────────────────────────────────────────


class TestEnums:
    def test_parse_side(self) -> None:
        assert _enums.parse_side("BUY") is _enums.OrderSide.BUY
        assert _enums.parse_side("sell") is _enums.OrderSide.SELL
        assert _enums.parse_side("b") is _enums.OrderSide.BUY
        assert _enums.parse_side("S") is _enums.OrderSide.SELL

    def test_parse_side_invalid(self) -> None:
        with pytest.raises(BrokerValidationError) as exc:
            _enums.parse_side("HOLD")
        assert exc.value.code == "INVALID_SIDE"

    def test_safe_parse_unknown_returns_none(self) -> None:
        assert _enums.safe_parse(_enums.OrderStatus, "ZZ") is None
        assert _enums.safe_parse(_enums.OrderStatus, "FF") is _enums.OrderStatus.FILLED

    def test_wire_values(self) -> None:
        assert _enums.OrderSide.BUY.value == "B"
        assert _enums.OrderType.LO.value == "LO"
        assert _enums.Timeframe.DAY_1.value == "1d"
        assert _enums.Board.HOSE.value == "HOSE"
        assert _enums.AccountType.EQUITY.value == "Cash"
        assert _enums.FCOType.BULL_BEAR.value == "bullbear"
        assert _enums.FCOOperator.GREATER_OR_EQUAL.value == "greater_or_equal"
        assert _enums.FCOStatus.TRIT.value == "TRIT"


# ─── Utils ──────────────────────────────────────────────────────────────────


class TestUtils:
    def test_require_non_empty(self) -> None:
        assert _utils.require_non_empty("  x ", "f") == "x"
        with pytest.raises(BrokerValidationError):
            _utils.require_non_empty("   ", "f")

    def test_require_positive(self) -> None:
        assert _utils.require_positive(5, "q") == 5
        with pytest.raises(BrokerValidationError):
            _utils.require_positive(0, "q")
        with pytest.raises(BrokerValidationError):
            _utils.require_positive(True, "q")

    def test_require_non_negative(self) -> None:
        assert _utils.require_non_negative(0, "p") == 0
        with pytest.raises(BrokerValidationError):
            _utils.require_non_negative(-1, "p")

    def test_require_empty(self) -> None:
        _utils.require_empty(None, "price")
        with pytest.raises(BrokerValidationError) as exc:
            _utils.require_empty(1, "price")
        assert exc.value.code == "MUTUALLY_EXCLUSIVE"

    def test_ssi_date(self) -> None:
        assert _utils.validate_ssi_date("2026/01/15", "d") == "2026/01/15"
        with pytest.raises(BrokerValidationError):
            _utils.validate_ssi_date("2026-01-15", "d")
        with pytest.raises(BrokerValidationError):
            _utils.validate_ssi_date("15/01/2026", "d")

    def test_ssi_datetime(self) -> None:
        assert (
            _utils.validate_ssi_datetime("2026/01/15 09:00:00", "d")
            == "2026/01/15 09:00:00"
        )
        with pytest.raises(BrokerValidationError):
            _utils.validate_ssi_datetime("2026/01/15", "d")

    def test_coercion(self) -> None:
        assert _utils.to_int("10") == 10
        assert _utils.to_int("x", 7) == 7
        assert _utils.to_float("10.5") == 10.5
        assert _utils.to_number("10.0") == 10
        assert _utils.to_number("10.5") == 10.5
        assert _utils.to_price("66800.0") == 66800
        assert _utils.opt_str("  ") is None
        assert _utils.today_date_str()[4] == "/"


# ─── Signing ────────────────────────────────────────────────────────────────


class TestSigning:
    def test_rsa_sign_verifies(self) -> None:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        private_key, public_key = make_test_rsa_key()
        body = '{"accountNo":"TEST123","symbol":"SSI"}'
        sig_hex = _signing.rsa_sign_hex(body, private_key)
        assert len(sig_hex) == 256  # 1024-bit → 128 bytes → 256 hex
        public_key.verify(
            bytes.fromhex(sig_hex),
            body.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        assert InvalidSignature is not None

    def test_rsa_empty_key(self) -> None:
        with pytest.raises(BrokerValidationError) as exc:
            _signing.rsa_sign_hex("x", "  ")
        assert exc.value.code == "MISSING_PRIVATE_KEY"

    def test_rsa_bad_key(self) -> None:
        with pytest.raises(BrokerValidationError) as exc:
            _signing.rsa_sign_hex("x", "bm90LXhtbA==")  # "not-xml"
        assert exc.value.code == "INVALID_PRIVATE_KEY"

    def test_nanoid(self) -> None:
        ids = {_signing.generate_request_id() for _ in range(100)}
        assert len(ids) == 100
        sample = next(iter(ids))
        assert len(sample) == 20
        assert all(
            c in "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
            for c in sample
        )


# ─── Transport ──────────────────────────────────────────────────────────────


class TestTransport:
    def test_ok_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client, fake = make_client(monkeypatch, [FakeResponse(200, {"a": 1})])
        assert client.request("GET", "/api/v3/x") == {"a": 1}
        assert fake.calls[0]["method"] == "GET"
        assert fake.calls[0]["url"] == "https://api.ssi.com.vn/api/v3/x"

    def test_no_content(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client, _ = make_client(monkeypatch, [FakeResponse(204, None)])
        assert client.request("DELETE", "/api/v3/x") == {}

    def test_auth_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client, _ = make_client(
            monkeypatch, [FakeResponse(401, {"code": 401001, "msg": "Bad OTP"})]
        )
        with pytest.raises(BrokerAuthError) as exc:
            client.request("POST", "/api/v3/auth/token")
        assert exc.value.http_status == 401
        assert exc.value.code == "401001"  # BrokerError.code luôn là str
        assert "Bad OTP" in exc.value.message

    def test_rate_limit_keeps_retry_after(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, _ = make_client(
            monkeypatch,
            [FakeResponse(429, {}, headers={"Retry-After": "7"})],
        )
        with pytest.raises(BrokerRateLimitError) as exc:
            client.request("GET", "/api/v3/x")
        assert exc.value.code == "RATE_LIMITED"
        assert "7" in exc.value.message

    def test_server_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client, _ = make_client(monkeypatch, [FakeResponse(500, {"message": "Boom"})])
        with pytest.raises(BrokerError) as exc:
            client.request("GET", "/api/v3/x")
        assert exc.value.http_status == 500
        assert "Boom" in exc.value.message

    def test_bad_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        resp = FakeResponse(200, ValueError("no json"), raw_text="<html>")
        client, _ = make_client(monkeypatch, [resp])
        with pytest.raises(BrokerError) as exc:
            client.request("GET", "/api/v3/x")
        assert exc.value.code == "BAD_RESPONSE"

    def test_timeout_single_attempt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client, fake = make_client(
            monkeypatch, [requests.exceptions.Timeout("t")], max_retries=1
        )
        with pytest.raises(BrokerNetworkError) as exc:
            client.request("GET", "/api/v3/x")
        assert exc.value.http_status == 0
        assert len(fake.calls) == 1

    def test_retry_then_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client, fake = make_client(
            monkeypatch,
            [
                requests.exceptions.ConnectionError("down"),
                FakeResponse(200, {"ok": True}),
            ],
            max_retries=2,
        )
        assert client.request("GET", "/api/v3/x") == {"ok": True}
        assert len(fake.calls) == 2

    def test_bearer_header(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client, fake = make_client(monkeypatch, [FakeResponse(200, {})])
        client.set_token("TEST_TOKEN")
        assert fake.headers.get("Authorization") == "Bearer TEST_TOKEN"
        client.clear_token()
        assert "Authorization" not in fake.headers

    def test_signed_request(self, monkeypatch: pytest.MonkeyPatch) -> None:
        private_key, public_key = make_test_rsa_key()
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        client, fake = make_client(monkeypatch, [FakeResponse(200, {"orderId": "1"})])
        body = '{"symbol":"SSI"}'
        out = client.request_signed("POST", "/api/v3/trading/order", body, private_key)
        assert out == {"orderId": "1"}
        headers = fake.calls[0]["headers"]
        assert "X-Signature" in headers
        public_key.verify(
            bytes.fromhex(headers["X-Signature"]),
            body.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        assert fake.calls[0]["data"] == body.encode("utf-8")

    def test_signed_missing_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client, fake = make_client(monkeypatch, [FakeResponse(200, {})])
        with pytest.raises(BrokerValidationError):
            client.request_signed("POST", "/api/v3/trading/order", "{}", "")
        assert fake.calls == []

    def test_no_secret_in_logs(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        secret = "TEST_API_SECRET_XYZ"
        client, _ = make_client(monkeypatch, [FakeResponse(200, {"ok": True})])
        with caplog.at_level(logging.DEBUG, logger="vnbroker.broker.ssi.transport"):
            client.request(
                "POST", "/api/v3/auth/token", json_body={"apiSecret": secret}
            )
        assert secret not in caplog.text

    def test_rate_limit_spacing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client, _ = make_client(
            monkeypatch,
            [FakeResponse(200, {}), FakeResponse(200, {})],
            rate_limit_rps=20.0,
        )
        start = time.monotonic()
        client.request("GET", "/a")
        client.request("GET", "/b")
        assert time.monotonic() - start >= 0.04

    def test_unlimited_no_throttle(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client, _ = make_client(
            monkeypatch,
            [FakeResponse(200, {}), FakeResponse(200, {})],
            rate_limit_rps=0,
        )
        start = time.monotonic()
        client.request("GET", "/a")
        client.request("GET", "/b")
        assert time.monotonic() - start < 0.5


# ─── Credentials ────────────────────────────────────────────────────────────


class TestCredentials:
    def test_from_env(self, ssi_env: dict) -> None:
        cfg = SSICredentialConfig.from_env()
        assert cfg.api_key == "TEST_API_KEY"
        assert cfg.api_secret == "TEST_API_SECRET"
        assert cfg.client_id == "TEST_CLIENT"
        assert cfg.private_key == "TEST_PRIVATE_KEY"
        assert cfg.api_url == "https://api.ssi.com.vn"

    def test_from_env_missing(self, clean_ssi_env: None) -> None:
        with pytest.raises(ValueError, match="VNBROKER_BROKER_SSI_API_KEY"):
            SSICredentialConfig.from_env()

    def test_repr_redacted(self, ssi_env: dict) -> None:
        text = repr(SSICredentialConfig.from_env())
        assert "TEST_API_KEY" not in text
        assert "TEST_API_SECRET" not in text
        assert "TEST_PRIVATE_KEY" not in text
        assert "REDACTED" in text

    def test_from_dict(self) -> None:
        cfg = SSICredentialConfig.from_dict({"api_key": "k", "api_secret": "s"})
        assert cfg.timeout_seconds == 60.0
        assert cfg.rate_limit_rps == 10.0


# ─── Redaction ──────────────────────────────────────────────────────────────


class TestRedaction:
    def test_ssi_keys_redacted(self) -> None:
        payload = {
            "apiKey": "K",
            "apiSecret": "S",
            "privateKey": "P",
            "transactionId": "T",
            "nested": {"api_secret": "S2"},
            "symbol": "SSI",
        }
        safe = Redactor.redact_dict(payload)
        assert safe["apiSecret"] == Redactor.REDACTED
        assert safe["privateKey"] == Redactor.REDACTED
        assert safe["transactionId"] == Redactor.REDACTED
        assert safe["nested"]["api_secret"] == Redactor.REDACTED
        assert safe["symbol"] == "SSI"
        assert payload["apiSecret"] == "S"  # không mutate gốc


# ─── Package & env ──────────────────────────────────────────────────────────


class TestPackageEnv:
    def test_package_imports(self) -> None:
        assert ssi_pkg._paths.EP_TRADING_ORDER == "/api/v3/trading/order"
        assert "BrokerAuthError" in ssi_pkg.__all__

    def test_websockets_sync_available(self) -> None:
        import websockets.sync.client  # noqa: F401 — yêu cầu websockets>=12 (S6)

    def test_fixtures_valid_no_secrets(self) -> None:
        for name in ("token", "ohlc", "balance", "order", "fco"):
            path = FIXTURES_DIR / f"{name}.json"
            assert path.exists(), name
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
            assert data is not None
            assert "BEGIN PRIVATE" not in text
            assert "PRIVATE KEY" not in text
