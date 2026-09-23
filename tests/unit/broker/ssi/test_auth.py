"""
S1: SSIAuthService — OTP/Smart-OTP/refresh, market-only, poll pending. Mocked.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest

from vnbroker.broker.exceptions import BrokerAuthError, BrokerValidationError
from vnbroker.broker.security.credentials import SSICredentialConfig
from vnbroker.broker.session import BrokerSession, SessionState
from vnbroker.broker.ssi._transport import SSIHttpClient
from vnbroker.broker.ssi.auth import _SmartOTPPending, SSIAuthService

pytestmark = pytest.mark.ssi

TOKEN_BODY = {
    "accessToken": "TEST_ACCESS",
    "tokenType": "Bearer",
    "expiresAt": 9999999999,
    "refreshToken": "TEST_REFRESH",
    "refreshExpiresAt": 9999999999,
}


class FakeResponse:
    def __init__(self, status_code: int, payload: Any = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers: Dict[str, str] = {}
        self.text = json.dumps(payload or {})

    def json(self) -> Any:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
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


def make_auth(
    script: List[Any], monkeypatch: pytest.MonkeyPatch, **cfg: Any
) -> tuple[SSIAuthService, SSIHttpClient, FakeSession, BrokerSession]:
    fake = FakeSession(script)
    monkeypatch.setattr("vnbroker.broker.ssi._transport.requests.Session", lambda: fake)
    base = {"api_key": "K", "api_secret": "S", "client_id": "C"}
    base.update(cfg)
    config = SSICredentialConfig.from_dict(base)
    session = BrokerSession(provider="SSI")
    transport = SSIHttpClient(base_url="https://api.ssi.com.vn", rate_limit_rps=0)
    return SSIAuthService(config, session, transport), transport, fake, session


class TestAuthenticate:
    def test_market_only_no_otp(self, monkeypatch: pytest.MonkeyPatch) -> None:
        auth, transport, fake, session = make_auth(
            [FakeResponse(200, dict(TOKEN_BODY))], monkeypatch
        )
        token = auth.authenticate()
        assert token == "TEST_ACCESS"
        body = fake.calls[0]["json"]
        assert body == {"apiKey": "K", "apiSecret": "S"}
        assert transport._session.headers["Authorization"] == "Bearer TEST_ACCESS"
        assert session.state == SessionState.AUTHENTICATED_READ
        assert session.token_expires_at == datetime.fromtimestamp(
            9999999999, tz=timezone.utc
        )

    def test_otp_flow(self, monkeypatch: pytest.MonkeyPatch) -> None:
        auth, _, fake, _ = make_auth([FakeResponse(200, dict(TOKEN_BODY))], monkeypatch)
        auth.authenticate(otp="123456")
        assert fake.calls[0]["json"]["otp"] == "123456"
        assert "transactionId" not in fake.calls[0]["json"]

    def test_both_otp_and_transaction_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        auth, _, fake, _ = make_auth([], monkeypatch)
        with pytest.raises(BrokerValidationError) as exc:
            auth.authenticate(otp="1", transaction_id="t")
        assert exc.value.code == "MUTUALLY_EXCLUSIVE"
        assert fake.calls == []

    def test_empty_otp_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        auth, _, fake, _ = make_auth([], monkeypatch)
        with pytest.raises(BrokerValidationError):
            auth.authenticate(otp="   ")
        assert fake.calls == []

    def test_nested_data_payload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        auth, _, _, session = make_auth(
            [FakeResponse(200, {"data": dict(TOKEN_BODY)})], monkeypatch
        )
        assert auth.authenticate(otp="1") == "TEST_ACCESS"
        assert session.state == SessionState.AUTHENTICATED_READ

    def test_expires_zero_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        body = dict(TOKEN_BODY, expiresAt=0)
        auth, _, _, session = make_auth([FakeResponse(200, body)], monkeypatch)
        assert auth.authenticate() == "TEST_ACCESS"
        assert session.state == SessionState.AUTHENTICATED_READ

    def test_missing_token_revokes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        auth, _, _, session = make_auth([FakeResponse(200, {})], monkeypatch)
        with pytest.raises(BrokerAuthError) as exc:
            auth.authenticate()
        assert exc.value.code == "TOKEN_MISSING"
        assert session.state == SessionState.REVOKED

    def test_pending_raises_signal_no_revoke(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        auth, _, _, session = make_auth(
            [FakeResponse(202, {"code": 401114, "msg": "Push-approval is pending"})],
            monkeypatch,
        )
        with pytest.raises(_SmartOTPPending) as exc:
            auth.authenticate(transaction_id="tx1")
        assert exc.value.code == "SMART_OTP_PENDING"
        assert session.state == SessionState.AUTHENTICATING

    def test_401_revokes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        auth, _, _, session = make_auth(
            [FakeResponse(401, {"msg": "Bad OTP"})], monkeypatch
        )
        with pytest.raises(BrokerAuthError):
            auth.authenticate(otp="wrong")
        assert session.state == SessionState.REVOKED

    def test_missing_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        auth, _, fake, _ = make_auth([], monkeypatch, api_key="", api_secret="")
        with pytest.raises(BrokerAuthError) as exc:
            auth.authenticate()
        assert exc.value.code == "MISSING_CREDENTIALS"
        assert fake.calls == []


class TestOtpRefresh:
    def test_request_otp(self, monkeypatch: pytest.MonkeyPatch) -> None:
        auth, _, fake, _ = make_auth(
            [FakeResponse(200, {"transactionId": "tx9"})], monkeypatch
        )
        out = auth.request_otp()
        assert out == {"transactionId": "tx9"}
        assert fake.calls[0]["json"] == {"apiKey": "K", "apiSecret": "S"}

    def test_refresh_without_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        auth, _, fake, _ = make_auth([], monkeypatch)
        with pytest.raises(BrokerAuthError) as exc:
            auth.refresh()
        assert exc.value.code == "NO_REFRESH_TOKEN"
        assert fake.calls == []

    def test_refresh_flow(self, monkeypatch: pytest.MonkeyPatch) -> None:
        auth, _, fake, _ = make_auth(
            [
                FakeResponse(200, dict(TOKEN_BODY)),
                FakeResponse(200, dict(TOKEN_BODY, accessToken="NEW")),
            ],
            monkeypatch,
        )
        auth.authenticate()
        assert auth.refresh() == "NEW"
        assert fake.calls[1]["json"] == {"refreshToken": "TEST_REFRESH"}


class TestEnsureAuthenticated:
    def test_valid_token_no_http(self, monkeypatch: pytest.MonkeyPatch) -> None:
        auth, _, fake, session = make_auth(
            [FakeResponse(200, dict(TOKEN_BODY))], monkeypatch
        )
        auth.authenticate()
        assert auth.ensure_authenticated() == "TEST_ACCESS"
        assert len(fake.calls) == 1
        assert session.state == SessionState.AUTHENTICATED_READ

    def test_refresh_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        auth, _, fake, _ = make_auth(
            [
                FakeResponse(200, dict(TOKEN_BODY)),
                FakeResponse(200, dict(TOKEN_BODY, accessToken="R2")),
            ],
            monkeypatch,
        )
        auth.authenticate()
        auth.revoke()
        # Giả lập refresh token còn nhớ sau revoke? revoke xóa — set lại tay:
        auth._refresh_token = "TEST_REFRESH"
        assert auth.ensure_authenticated() == "R2"
        assert len(fake.calls) == 2

    def test_otp_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        auth, _, fake, _ = make_auth([FakeResponse(200, dict(TOKEN_BODY))], monkeypatch)
        assert auth.ensure_authenticated(otp="999") == "TEST_ACCESS"
        assert fake.calls[0]["json"]["otp"] == "999"

    def test_poll_then_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        pending = {"code": 401114, "msg": "pending"}
        auth, _, fake, _ = make_auth(
            [
                FakeResponse(202, pending),
                FakeResponse(202, pending),
                FakeResponse(200, dict(TOKEN_BODY)),
            ],
            monkeypatch,
        )
        out = auth.ensure_authenticated(
            transaction_id="tx", poll_interval=0, poll_max_retries=5
        )
        assert out == "TEST_ACCESS"
        assert len(fake.calls) == 3

    def test_poll_exhausted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        pending = {"code": 401114, "msg": "pending"}
        auth, _, fake, _ = make_auth([FakeResponse(202, pending)] * 3, monkeypatch)
        with pytest.raises(BrokerAuthError) as exc:
            auth.ensure_authenticated(
                transaction_id="tx", poll_interval=0, poll_max_retries=3
            )
        assert exc.value.code == "SMART_OTP_TIMEOUT"
        assert len(fake.calls) == 3

    def test_no_way(self, monkeypatch: pytest.MonkeyPatch) -> None:
        auth, _, _, _ = make_auth([], monkeypatch)
        with pytest.raises(BrokerAuthError) as exc:
            auth.ensure_authenticated()
        assert exc.value.code == "NO_CREDENTIALS"

    def test_bad_poll_params(self, monkeypatch: pytest.MonkeyPatch) -> None:
        auth, _, _, _ = make_auth([], monkeypatch)
        with pytest.raises(BrokerValidationError):
            auth.ensure_authenticated(transaction_id="t", poll_max_retries=0)


class TestSessionLifecycle:
    def test_is_token_valid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        auth, _, _, _ = make_auth([], monkeypatch)
        assert auth.is_token_valid() is False

    def test_revoke(self, monkeypatch: pytest.MonkeyPatch) -> None:
        auth, transport, _, session = make_auth(
            [FakeResponse(200, dict(TOKEN_BODY))], monkeypatch
        )
        auth.authenticate()
        assert auth.is_token_valid() is True
        auth.revoke()
        assert auth.is_token_valid() is False
        assert session.state == SessionState.REVOKED
        assert "Authorization" not in transport._session.headers

    def test_set_token_manual(self, monkeypatch: pytest.MonkeyPatch) -> None:
        auth, _, _, session = make_auth([], monkeypatch)
        assert auth.set_token_manual("MANUAL") == "MANUAL"
        assert session.state == SessionState.AUTHENTICATED_READ
        with pytest.raises(BrokerValidationError):
            auth.set_token_manual("  ")

    def test_no_secret_in_logs(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        auth, _, _, _ = make_auth([FakeResponse(200, dict(TOKEN_BODY))], monkeypatch)
        with caplog.at_level(logging.DEBUG, logger="vnbroker.broker.ssi.auth"):
            auth.authenticate(otp="SECRET_OTP_123")
        assert "SECRET_OTP_123" not in caplog.text
        assert "TEST_ACCESS" not in caplog.text
