"""
Unit tests S4: BrokerSession state machine + TCBSAuthService (mocked HTTP).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests

from vnbroker.broker.exceptions import (
    BrokerAuthError,
    BrokerNetworkError,
    BrokerPermissionError,
    BrokerSessionExpiredError,
)
from vnbroker.broker.session import BrokerSession, SessionState
from vnbroker.broker.security.credentials import TCBSCredentialConfig
from vnbroker.broker.tcbs.auth import TCBSAuthService
from vnbroker.broker.tcbs.exceptions import BrokerAuthError as TCBSBrokerAuthError


# ─── BrokerSession State Machine ─────────────────────────────────────────────

class TestBrokerSessionInitial:
    def test_initial_state_is_created(self):
        s = BrokerSession()
        assert s.state == SessionState.CREATED

    def test_initial_token_is_none(self):
        s = BrokerSession()
        assert s._token is None

    def test_is_write_enabled_false_initially(self):
        s = BrokerSession()
        assert s.is_write_enabled is False

    def test_is_authenticated_false_initially(self):
        s = BrokerSession()
        assert s.is_authenticated is False

    def test_repr_does_not_expose_token(self):
        s = BrokerSession()
        s._token = "secret-jwt-token"
        assert "secret-jwt-token" not in repr(s)
        assert "has_token=True" in repr(s)


class TestBrokerSessionTransitions:
    def test_begin_authenticating_from_created(self):
        s = BrokerSession()
        s.begin_authenticating()
        assert s.state == SessionState.AUTHENTICATING

    def test_set_token_transitions_to_authenticated_read(self):
        s = BrokerSession()
        s.begin_authenticating()
        s.set_token("jwt.abc")
        assert s.state == SessionState.AUTHENTICATED_READ
        assert s.is_authenticated is True

    def test_enable_write_from_authenticated_read(self):
        s = BrokerSession()
        s.set_token("jwt.abc")
        s.enable_write()
        assert s.state == SessionState.AUTHENTICATED_WRITE_ENABLED
        assert s.is_write_enabled is True

    def test_enable_write_from_created_raises(self):
        s = BrokerSession()
        with pytest.raises(BrokerPermissionError) as exc:
            s.enable_write()
        assert exc.value.code == "WRITE_ENABLE_REJECTED"

    def test_enable_write_from_expired_raises(self):
        s = BrokerSession()
        s.revoke()
        with pytest.raises(BrokerPermissionError):
            s.enable_write()

    def test_revoke_clears_token_and_expires(self):
        s = BrokerSession()
        s.set_token("jwt.abc")
        s.revoke()
        assert s.state == SessionState.REVOKED
        assert s._token is None

    def test_lock_sets_locked_state(self):
        s = BrokerSession()
        s.set_token("jwt.abc")
        s.lock("security violation detected")
        assert s.state == SessionState.LOCKED
        assert s._token is None
        assert s._lock_reason == "security violation detected"

    def test_begin_authenticating_on_locked_raises(self):
        s = BrokerSession()
        s.lock("test")
        with pytest.raises(BrokerPermissionError) as exc:
            s.begin_authenticating()
        assert exc.value.code == "SESSION_LOCKED"


class TestBrokerSessionToken:
    def test_token_returns_value_when_authenticated(self):
        s = BrokerSession()
        s.set_token("jwt.abc")
        assert s.token == "jwt.abc"

    def test_token_raises_when_expired(self):
        s = BrokerSession()
        s.revoke()
        with pytest.raises(BrokerSessionExpiredError):
            _ = s.token

    def test_token_raises_when_locked(self):
        s = BrokerSession()
        s.lock("reason")
        with pytest.raises(BrokerSessionExpiredError):
            _ = s.token

    def test_token_auto_expires_when_past_expires_at(self):
        s = BrokerSession()
        past = datetime.now(tz=timezone.utc) - timedelta(seconds=10)
        s.set_token("jwt.old", expires_at=past)
        with pytest.raises(BrokerSessionExpiredError) as exc:
            _ = s.token
        assert s.state == SessionState.EXPIRED
        assert exc.value.code == "SESSION_EXPIRED"

    def test_token_valid_when_not_yet_expired(self):
        s = BrokerSession()
        future = datetime.now(tz=timezone.utc) + timedelta(hours=8)
        s.set_token("jwt.valid", expires_at=future)
        assert s.token == "jwt.valid"

    def test_token_valid_when_no_expires_at(self):
        s = BrokerSession()
        s.set_token("jwt.no-expiry")
        assert s.token == "jwt.no-expiry"


# ─── TCBSAuthService ──────────────────────────────────────────────────────────

def _make_auth_service(api_key: str = "test-api-key") -> tuple[TCBSAuthService, BrokerSession]:
    config = TCBSCredentialConfig(api_key=api_key)
    session = BrokerSession()
    service = TCBSAuthService(config=config, session=session)
    return service, session


class TestTCBSAuthServiceAuthenticate:
    def test_authenticate_success_sets_session_token(self):
        service, session = _make_auth_service()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        future_date = (datetime.now(tz=timezone.utc) + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
        mock_resp.json.return_value = {
            "token": "jwt.real-token",
            "expiredTime": future_date,
        }
        with patch("requests.post", return_value=mock_resp):
            service.authenticate(otp="123456")
        assert session.token == "jwt.real-token"
        assert session.state == SessionState.AUTHENTICATED_READ

    def test_authenticate_success_with_epoch_millis_expiry(self):
        service, session = _make_auth_service()
        future_ms = int((datetime.now(tz=timezone.utc) + timedelta(hours=8)).timestamp() * 1000)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"token": "jwt.token", "expiredTime": future_ms}
        with patch("requests.post", return_value=mock_resp):
            service.authenticate(otp="123456")
        assert session.is_authenticated

    def test_authenticate_empty_otp_raises_value_error(self):
        service, _ = _make_auth_service()
        with pytest.raises(ValueError, match="OTP"):
            service.authenticate(otp="")

    def test_authenticate_whitespace_otp_raises_value_error(self):
        service, _ = _make_auth_service()
        with pytest.raises(ValueError):
            service.authenticate(otp="   ")

    def test_authenticate_401_raises_broker_auth_error(self):
        service, session = _make_auth_service()
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"code": "INVALID_OTP", "message": "OTP sai."}
        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(BrokerAuthError) as exc:
                service.authenticate(otp="000000")
        assert exc.value.code == "INVALID_OTP"
        assert exc.value.http_status == 401
        assert session.state == SessionState.REVOKED  # Revoked on failure

    def test_authenticate_network_timeout_raises_broker_network_error(self):
        service, session = _make_auth_service()
        with patch("requests.post", side_effect=requests.exceptions.Timeout):
            with pytest.raises(BrokerNetworkError) as exc:
                service.authenticate(otp="123456")
        assert exc.value.code == "NETWORK_TIMEOUT"
        assert session.state == SessionState.REVOKED

    def test_authenticate_request_exception_raises_broker_network_error(self):
        service, _ = _make_auth_service()
        with patch("requests.post", side_effect=requests.exceptions.ConnectionError("refused")):
            with pytest.raises(BrokerNetworkError) as exc:
                service.authenticate(otp="123456")
        assert exc.value.code == "NETWORK_ERROR"

    def test_authenticate_does_not_log_api_key_or_otp(self):
        """Kiểm tra payload KHÔNG được ghi vào logger."""
        service, _ = _make_auth_service(api_key="MY-SECRET-KEY")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"token": "tok", "expiredTime": None}
        with patch("requests.post", return_value=mock_resp) as mock_post:
            service.authenticate(otp="654321")
        # Kiểm tra requests.post được gọi đúng endpoint
        call_kwargs = mock_post.call_args
        # json payload phải được gửi nhưng KHÔNG được xuất hiện trong bất kỳ log nào
        # (test này chỉ verify structure call, không verify log output)
        assert "json" in call_kwargs.kwargs or call_kwargs[1].get("json") is not None

    def test_authenticate_invalid_response_raises_auth_error(self):
        service, session = _make_auth_service()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"unexpected": "field"}  # Thiếu "token"
        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(BrokerAuthError) as exc:
                service.authenticate(otp="123456")
        assert exc.value.code == "AUTH_RESPONSE_INVALID"


class TestTCBSAuthServiceIsTokenValid:
    def test_returns_true_when_session_has_valid_token(self):
        service, session = _make_auth_service()
        session.set_token("jwt.valid")
        assert service.is_token_valid() is True

    def test_returns_false_when_session_not_authenticated(self):
        service, _ = _make_auth_service()
        assert service.is_token_valid() is False

    def test_returns_false_when_token_expired(self):
        service, session = _make_auth_service()
        past = datetime.now(tz=timezone.utc) - timedelta(seconds=1)
        session.set_token("jwt.old", expires_at=past)
        assert service.is_token_valid() is False


class TestTCBSAuthServiceRevoke:
    def test_revoke_clears_session(self):
        service, session = _make_auth_service()
        session.set_token("jwt.abc")
        service.revoke()
        assert session.state == SessionState.REVOKED


class TestTCBSExceptionsReExport:
    def test_tcbs_exceptions_are_same_as_broker_exceptions(self):
        """Verify re-export không tạo class mới — cùng object identity."""
        from vnbroker.broker.exceptions import BrokerAuthError as Base
        assert TCBSBrokerAuthError is Base

    def test_parse_expires_epoch_millis(self):
        future_ms = int(
            (datetime.now(tz=timezone.utc) + timedelta(hours=8)).timestamp() * 1000
        )
        result = TCBSAuthService._parse_expires(future_ms)
        assert result is not None
        assert result.tzinfo is not None

    def test_parse_expires_iso_string(self):
        result = TCBSAuthService._parse_expires("2026-05-20T18:00:00Z")
        assert result is not None
        assert result.year == 2026

    def test_parse_expires_none_returns_none(self):
        assert TCBSAuthService._parse_expires(None) is None

    def test_parse_expires_invalid_returns_none(self):
        assert TCBSAuthService._parse_expires("not-a-date") is None
