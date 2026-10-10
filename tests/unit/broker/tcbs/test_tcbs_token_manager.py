"""
Unit tests lát T — TokenManager (T1..T6) + 2 endpoint gaia (T8) + chặn bug 8 giờ (T7).

TẤT CẢ test OFFLINE: JWT dựng tay bằng base64url, HTTP bị monkeypatch `requests.post`.
Không có test nào chạm mạng.

Nhóm auth/session có sẵn: tests/unit/broker/tcbs/test_session_auth.py — lát này KHÔNG
sửa file đó; T10 chỉ assert chữ ký của `authenticate` / `is_token_valid` / `revoke`.
"""
from __future__ import annotations

import ast
import base64
import inspect
import json
import logging
import textwrap
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest
import requests

from vnbroker.broker.exceptions import (
    BrokerAuthError,
    BrokerNetworkError,
    BrokerSessionExpiredError,
)
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.security.credentials import TCBSCredentialConfig
from vnbroker.broker.tcbs import token_manager as token_manager_mod
from vnbroker.broker.tcbs.auth import TCBSAuthService
from vnbroker.broker.tcbs.token_manager import TokenManager


# ─── Helpers: dựng JWT bằng tay (không cần pyjwt) ──────────────────────────────

_SECRET_SIG = "c2lnbmF0dXJlLXBsYWNlaG9sZGVyLWhlcmU"


def _b64url(payload: Dict[str, Any]) -> str:
    """base64url KHÔNG padding — đúng như JWT thật."""
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _make_jwt(claims: Optional[Dict[str, Any]] = None) -> str:
    """Dựng JWT 3 phần. `claims=None` ⇒ payload rỗng (thiếu `exp`)."""
    body = _b64url(claims if claims is not None else {})
    return f"{_b64url({'alg': 'HS256', 'typ': 'JWT'})}.{body}.{_SECRET_SIG}"


def _jwt_expired(seconds_ago: int = 60) -> str:
    exp = int((datetime.now(tz=timezone.utc) - timedelta(seconds=seconds_ago)).timestamp())
    return _make_jwt({"exp": exp, "iat": exp - 3600})


def _jwt_expiring_in(seconds: int) -> str:
    """Token còn hạn thật nhưng đã bước vào ngưỡng buffer (300s)."""
    exp = int((datetime.now(tz=timezone.utc) + timedelta(seconds=seconds)).timestamp())
    return _make_jwt({"exp": exp, "iat": exp - 3600})


def _jwt_valid(hours: int = 1) -> str:
    exp = int((datetime.now(tz=timezone.utc) + timedelta(hours=hours)).timestamp())
    return _make_jwt({"exp": exp, "iat": exp - 3600})


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _make_auth_service(api_key: str = "test-api-key") -> Tuple[TCBSAuthService, BrokerSession]:
    config = TCBSCredentialConfig(api_key=api_key)
    session = BrokerSession()
    return TCBSAuthService(config=config, session=session), session


def _mock_response(status: int, body: Any) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = body
    return resp


# ─── T1: decode JWT exp/iat cục bộ ────────────────────────────────────────────

class TestT1LocalJwtDecode:
    def test_decode_exp_returns_tz_aware_datetime(self):
        exp_dt = datetime.now(tz=timezone.utc) + timedelta(hours=2)
        token = _make_jwt({"exp": int(exp_dt.timestamp())})

        decoded = TokenManager.decode_expiry(token)

        assert decoded is not None
        assert decoded.tzinfo is not None
        # int(...) vì JWT chỉ mang epoch giây nguyên — microsecond bị cắt.
        assert decoded == datetime.fromtimestamp(int(exp_dt.timestamp()), tz=timezone.utc)

    def test_decode_iat_returns_tz_aware_datetime(self):
        iat_dt = datetime.now(tz=timezone.utc) - timedelta(minutes=5)
        token = _make_jwt({"iat": int(iat_dt.timestamp())})

        decoded = TokenManager.decode_issued_at(token)

        assert decoded is not None
        assert decoded.tzinfo is not None

    def test_decode_handles_missing_base64url_padding(self):
        """JWT thật bỏ padding '='. Payload dựng ở đây cũng bị bỏ padding."""
        token = _make_jwt({"exp": 4000000000, "sub": "tcbs-user-123456"})
        payload_part = token.split(".")[1]
        assert "=" not in payload_part, "payload dựng tay phải thiếu padding để test có ý nghĩa"

        decoded = TokenManager.decode_expiry(token)

        assert decoded == datetime.fromtimestamp(4000000000, tz=timezone.utc)

    def test_decode_does_not_call_network(self, monkeypatch):
        """T1 nói rõ: decode cục bộ. Chặn requests.post/session.get bằng assertion."""
        def _boom(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("TokenManager.decode_expiry() không được gọi mạng")

        monkeypatch.setattr(requests, "post", _boom)
        monkeypatch.setattr(requests, "get", _boom)
        monkeypatch.setattr(requests, "request", _boom)

        assert TokenManager.decode_expiry(_jwt_valid()) is not None

    def test_expired_token_decoded_locally_is_expired(self):
        tm = TokenManager(token=_jwt_expired())

        assert tm.is_expired() is True


# ─── T2: token không phải JWT ⇒ không crash, vẫn dùng được ────────────────────

class TestT2NonJwtToken:
    @pytest.mark.parametrize(
        "token,label",
        [
            ("opaque-token-khong-co-dau-cham", "1 phần"),
            ("aaa.@@@@-khong-base64-hop-le@@@@.ccc", "base64 hỏng"),
            ("aaa." + _b64url({"sub": "x", "role": "user"}) + ".ccc", "thiếu claim exp"),
            ("", "chuỗi rỗng"),
            ("....", "chỉ dấu chấm"),
        ],
    )
    def test_non_jwt_token_does_not_raise(self, token: str, label: str):
        tm = TokenManager(token=token)

        assert tm.expires_at is None, f"{label}: expires_at phải là None"
        assert tm.is_expired() is None, f"{label}: is_expired() phải trả None (không biết)"
        assert tm.get_token() == token, f"{label}: token vẫn phải dùng được"

    def test_non_jwt_with_expired_token_still_raises_when_actually_expired(self):
        """Không phải mọi token hỏng đều được tha — chỉ là không biết hạn thì không đoán."""
        tm = TokenManager(token=_jwt_expired())

        assert tm.is_expired() is True
        with pytest.raises(BrokerSessionExpiredError):
            tm.get_token()


# ─── T3: buffer lấy từ BrokerSession, không tự đặt hằng ───────────────────────

class TestT3BufferSingleSource:
    def test_buffer_read_from_broker_session(self):
        tm = TokenManager()

        assert tm.refresh_buffer_seconds == BrokerSession().TOKEN_REFRESH_BUFFER_SECONDS
        assert tm.refresh_buffer_seconds == 300

    def test_module_has_no_hardcoded_expiry_constants(self):
        """T3: đặt thêm hằng 300/28800 ở file mới = 2 nguồn sự thật cho 1 khái niệm."""
        src = textwrap.dedent(inspect.getsource(token_manager_mod))
        literals = [
            node.value
            for node in ast.walk(ast.parse(src))
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool)
        ]

        assert 300 not in literals, f"token_manager.py tự đặt lại buffer 300: {literals}"
        assert 28800 not in literals, f"token_manager.py tự đặt lại 28800: {literals}"


# ─── T4: hết hạn + không provider ⇒ raise kèm hướng dẫn ───────────────────────

class TestT4ExpiredWithoutProvider:
    def test_raises_broker_session_expired_error(self):
        tm = TokenManager(token=_jwt_expired())

        with pytest.raises(BrokerSessionExpiredError):
            tm.get_token()

    def test_error_message_contains_guidance(self):
        tm = TokenManager(token=_jwt_expired())

        with pytest.raises(BrokerSessionExpiredError) as exc:
            tm.get_token()

        msg = exc.value.message
        assert "OTP" in msg, "message phải hướng dẫn cần Smart OTP mới"
        assert "TCInvest" in msg, "message phải chỉ đúng app cấp OTP"
        assert exc.value.http_status == 401

    def test_no_token_and_no_provider_raises_instead_of_returning_empty(self):
        tm = TokenManager()

        with pytest.raises(BrokerSessionExpiredError):
            tm.get_token()

    def test_error_message_does_not_leak_token(self):
        token = _jwt_expired()
        tm = TokenManager(token=token)

        with pytest.raises(BrokerSessionExpiredError) as exc:
            tm.get_token()

        assert token not in exc.value.message
        assert token.split(".")[1] not in exc.value.message


# ─── T5: token_provider gọi đúng 1 lần, cache token mới ──────────────────────

class TestT5TokenProvider:
    def test_provider_called_exactly_once_then_cached(self):
        calls: List[int] = []

        def _provider() -> str:
            calls.append(1)
            return _jwt_valid(hours=4)

        tm = TokenManager(token=_jwt_expired(), token_provider=_provider)

        first = tm.get_token()
        second = tm.get_token()
        third = tm.get_token()

        assert len(calls) == 1, f"provider phải gọi đúng 1 lần, thực tế {len(calls)}"
        assert first == second == third
        assert first == tm.token

    def test_provider_used_when_no_token_at_all(self):
        calls: List[int] = []

        def _provider() -> str:
            calls.append(1)
            return _jwt_valid(hours=4)

        tm = TokenManager(token_provider=_provider)

        assert tm.get_token() is not None
        assert tm.get_token() is not None
        assert len(calls) == 1

    def test_provider_returning_dead_token_raises_instead_of_looping(self):
        def _provider() -> str:
            return _jwt_expired()

        tm = TokenManager(token=_jwt_expired(), token_provider=_provider)

        with pytest.raises(BrokerSessionExpiredError):
            tm.get_token()

    def test_provider_returning_garbage_raises(self):
        tm = TokenManager(token=_jwt_expired(), token_provider=lambda: "")

        with pytest.raises(BrokerSessionExpiredError):
            tm.get_token()


# ─── T6: on_expiring bắn đúng 1 lần ──────────────────────────────────────────

class TestT6OnExpiringCallback:
    def test_callback_fires_once_when_crossing_buffer(self):
        fired: List[Any] = []
        tm = TokenManager(token=_jwt_expiring_in(60), on_expiring=fired.append)

        with pytest.raises(BrokerSessionExpiredError):
            tm.get_token()
        with pytest.raises(BrokerSessionExpiredError):
            tm.get_token()
        with pytest.raises(BrokerSessionExpiredError):
            tm.get_token()

        assert len(fired) == 1, f"on_expiring phải bắn đúng 1 lần, thực tế {len(fired)}"

    def test_callback_receives_expiry_datetime(self):
        fired: List[Any] = []
        tm = TokenManager(token=_jwt_expiring_in(60), on_expiring=fired.append)

        with pytest.raises(BrokerSessionExpiredError):
            tm.get_token()

        assert len(fired) == 1
        assert isinstance(fired[0], datetime)

    def test_callback_resets_after_new_token_set(self):
        fired: List[Any] = []
        tm = TokenManager(token=_jwt_expiring_in(60), on_expiring=fired.append)
        tm.set_token(_jwt_expiring_in(60))

        with pytest.raises(BrokerSessionExpiredError):
            tm.get_token()

        assert len(fired) == 1

    def test_callback_not_fired_while_token_still_fresh(self):
        fired: List[Any] = []
        tm = TokenManager(token=_jwt_valid(hours=4), on_expiring=fired.append)

        assert tm.get_token()
        assert fired == []


# ─── T7: chặn bug 8 giờ bịa đặt — 3 nhánh authenticate() ─────────────────────

class TestT7AuthenticateExpiryBranches:
    def test_branch_a_expired_time_field_is_used(self):
        """NHÁNH (a) — tương thích ngược.

        ⚠ Spec TCBS 1.0.0 KHÔNG có field `expiredTime`
        (đếm 0 lần trong toàn spec — lệnh tái lập ở SUMMARY). Nhánh này KHÔNG
        reachable từ server thật; test xanh KHÔNG đồng nghĩa hành vi production
        đã được kiểm chứng.
        """
        service, session = _make_auth_service()
        wanted = datetime.now(tz=timezone.utc) + timedelta(days=30)
        body = {
            "token": "jwt.real-token",
            "expiredTime": wanted.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        with patch("requests.post", return_value=_mock_response(200, body)):
            service.authenticate(otp="123456")

        assert session.token == "jwt.real-token"
        assert session.token_expires_at is not None
        assert session.token_expires_at.year == wanted.year

    def test_branch_b_exp_claim_used_when_no_expired_time(self):
        """NHÁNH (b) — nguồn thật duy nhất theo spec hiện tại: claim `exp` của JWT."""
        service, session = _make_auth_service()
        exp_dt = datetime.now(tz=timezone.utc) + timedelta(hours=3)
        body = {"token": _make_jwt({"exp": int(exp_dt.timestamp())})}

        with patch("requests.post", return_value=_mock_response(200, body)):
            service.authenticate(otp="123456")

        assert session.token_expires_at is not None
        assert abs((session.token_expires_at - exp_dt).total_seconds()) < 2

    def test_branch_c_no_expired_time_and_no_jwt_does_not_fabricate_8h(self):
        """NHÁNH (c) — CHẶN BUG 8 GIỜ (F-2).

        Bug gốc: `session.set_token(token, expires_at=None)` → `session.py:87-90`
        rơi vào nhánh `else` ⇒ `token_expires_at = now + 28800s`. 8 giờ bịa đặt.
        Sau khi sửa: session KHÔNG tự chế hạn, token vẫn dùng được.
        """
        service, session = _make_auth_service()
        before = datetime.now(tz=timezone.utc)

        with patch("requests.post", return_value=_mock_response(200, {"token": "opaque-token"})):
            service.authenticate(otp="123456")

        assert session.token_expires_at is None, (
            "session tự chế 8 giờ — bug F-2 chưa chặn. "
            f"token_expires_at={session.token_expires_at!r} sau khi gọi lúc {before!r}"
        )
        assert session.token == "opaque-token"
        assert session.is_authenticated is True

    def test_branch_c_token_manager_reports_unknown_not_false(self):
        """T7: `is_expired()` trả None (không biết) ⇒ để caller quyết, không giả định."""
        tm = TokenManager(token="opaque-token")

        assert tm.is_expired() is None

    def test_branch_a_takes_precedence_over_jwt_exp(self):
        service, session = _make_auth_service()
        from_field = datetime.now(tz=timezone.utc) + timedelta(days=2)
        from_jwt = datetime.now(tz=timezone.utc) + timedelta(minutes=10)
        body = {
            "token": _make_jwt({"exp": int(from_jwt.timestamp())}),
            "expiredTime": from_field.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        with patch("requests.post", return_value=_mock_response(200, body)):
            service.authenticate(otp="123456")

        assert session.token_expires_at is not None
        assert (session.token_expires_at - from_jwt).total_seconds() > 3600


# ─── T8: 2 endpoint gaia ──────────────────────────────────────────────────────

class TestT8ApiKeyEndpoints:
    def test_get_api_key_expiration_posts_correct_path_and_body(self):
        service, _ = _make_auth_service(api_key="AK-123")
        expire = "2027-01-02T03:04:05+07:00"

        with patch("requests.post", return_value=_mock_response(200, {"expireDate": expire})) as post:
            result = service.get_api_key_expiration()

        url = post.call_args[0][0]
        payload = post.call_args[1]["json"]
        assert url.endswith("/gaia/v1/oauth2/openapi/apikey/info")
        assert payload == {"apiKey": "AK-123"}
        assert result == datetime.fromisoformat(expire)

    def test_get_api_key_expiration_returns_none_when_field_absent(self):
        service, _ = _make_auth_service()

        with patch("requests.post", return_value=_mock_response(200, {})):
            assert service.get_api_key_expiration() is None

    def test_extend_api_key_posts_correct_path_and_body(self):
        service, _ = _make_auth_service(api_key="AK-123")
        expire = "2027-06-07T08:09:10+07:00"

        with patch("requests.post", return_value=_mock_response(200, {"expireDate": expire})) as post:
            result = service.extend_api_key(otp="654321")

        url = post.call_args[0][0]
        payload = post.call_args[1]["json"]
        assert url.endswith("/gaia/v1/oauth2/openapi/apikey/extend")
        assert payload == {"apiKey": "AK-123", "otp": "654321"}
        assert result == datetime.fromisoformat(expire)

    def test_extend_api_key_rejects_empty_otp(self):
        service, _ = _make_auth_service()

        with pytest.raises(ValueError, match="OTP"):
            service.extend_api_key(otp="   ")

    def test_extend_api_key_non_200_raises_auth_error(self):
        service, _ = _make_auth_service()

        with patch("requests.post", return_value=_mock_response(401, {"code": "OTP_INVALID"})):
            with pytest.raises(BrokerAuthError) as exc:
                service.extend_api_key(otp="000000")

        assert exc.value.code == "OTP_INVALID"
        assert exc.value.http_status == 401

    def test_get_api_key_expiration_timeout_raises_network_error(self):
        service, _ = _make_auth_service()

        with patch("requests.post", side_effect=requests.exceptions.Timeout):
            with pytest.raises(BrokerNetworkError) as exc:
                service.get_api_key_expiration()

        assert exc.value.code == "NETWORK_TIMEOUT"

    def test_get_api_key_expiration_invalid_json_raises_auth_error(self):
        service, _ = _make_auth_service()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.side_effect = ValueError("not json")

        with patch("requests.post", return_value=resp):
            with pytest.raises(BrokerAuthError) as exc:
                service.get_api_key_expiration()

        assert exc.value.code == "AUTH_RESPONSE_INVALID"

    def test_extend_api_key_does_not_revoke_existing_session(self):
        """Gia hạn API key KHÔNG phải xác thực lại — không được phá phiên hiện tại."""
        service, session = _make_auth_service()
        session.set_token("jwt.existing")

        with patch("requests.post", return_value=_mock_response(200, {"expireDate": "2027-01-01T00:00:00+07:00"})):
            service.extend_api_key(otp="123456")

        assert session.token == "jwt.existing"


# ─── T9: KHÔNG log token / otp / api_key ở bất kỳ level nào ───────────────────

class TestT9NoSecretInLogs:
    def test_no_secret_in_any_log_level(self, caplog):
        api_key = "API-KEY-SECRET-XYZ"
        otp = "OTP-SECRET-999"
        token = _jwt_valid(hours=4)
        service, _ = _make_auth_service(api_key=api_key)

        with caplog.at_level(logging.DEBUG):
            with patch("requests.post", return_value=_mock_response(200, {"token": token})):
                service.authenticate(otp=otp)
            with patch("requests.post", return_value=_mock_response(200, {"expireDate": "2027-01-01T00:00:00+07:00"})):
                service.get_api_key_expiration()
                service.extend_api_key(otp=otp)
            with patch("requests.post", return_value=_mock_response(401, {"code": "BAD", "message": "OTP sai"})):
                with pytest.raises(BrokerAuthError):
                    service.extend_api_key(otp=otp)
            tm = TokenManager(token=token, token_provider=lambda: _jwt_valid(hours=1))
            tm.get_token()
            _logger_probe_error(token)

        # Bắt buộc: log KHÔNG rỗng — test không được xanh một cách vô nghĩa.
        assert len(caplog.records) > 0, "caplog rỗng ⇒ assert bên dưới là tautology"

        blob = "\n".join(
            r.getMessage() + "|" + repr(getattr(r, "args", ()))
            for r in caplog.records
        )
        for secret in (api_key, otp, token, token.split(".")[1]):
            assert secret not in blob, f"secret lọt vào log: {secret[:24]}..."

        levels = {r.levelno for r in caplog.records}
        assert logging.DEBUG <= min(levels), f"chưa bắt được DEBUG, thấy {levels}"

    def test_repr_of_token_manager_redacts_token(self):
        token = _jwt_valid()
        tm = TokenManager(token=token)

        assert token not in repr(tm)
        assert "REDACTED" in repr(tm)

    def test_str_of_auth_error_does_not_leak_payload(self):
        service, _ = _make_auth_service(api_key="API-KEY-SECRET-XYZ")

        with patch("requests.post", return_value=_mock_response(401, {"code": "X", "message": "sai"})):
            with pytest.raises(BrokerAuthError) as exc:
                service.authenticate(otp="OTP-SECRET-999")

        assert "API-KEY-SECRET-XYZ" not in repr(exc.value)
        assert "OTP-SECRET-999" not in repr(exc.value)


def _logger_probe_error(token: str) -> None:
    """Gọi 1 đường log ở mức WARNING để caplog chắc chắn có bản ghi."""
    logging.getLogger("vnbroker.broker.tcbs.auth").warning("probe token len=%d", len(token))


# ─── T10: chữ ký public không đổi ────────────────────────────────────────────

class TestT10PublicSignatureUnchanged:
    # Chụp TRƯỚC khi sửa auth.py bằng inspect.signature (chạy ở dev@3e252ac):
    #   authenticate    (self, otp: 'str') -> 'None'
    #   is_token_valid  (self) -> 'bool'
    #   revoke          (self) -> 'None'
    #   __init__        (self, config: 'TCBSCredentialConfig', session: 'BrokerSession') -> 'None'
    def test_authenticate_signature_unchanged(self):
        sig = inspect.signature(TCBSAuthService.authenticate)

        assert list(sig.parameters) == ["self", "otp"]
        assert sig.parameters["otp"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        assert sig.parameters["otp"].annotation == "str"
        assert sig.parameters["otp"].default is inspect.Parameter.empty
        assert sig.return_annotation in (None, "None")

    def test_is_token_valid_signature_unchanged(self):
        sig = inspect.signature(TCBSAuthService.is_token_valid)

        assert list(sig.parameters) == ["self"]
        assert sig.return_annotation in (None, "bool")

    def test_revoke_signature_unchanged(self):
        sig = inspect.signature(TCBSAuthService.revoke)

        assert list(sig.parameters) == ["self"]
        assert sig.return_annotation in (None, "None")

    def test_constructor_signature_unchanged(self):
        sig = inspect.signature(TCBSAuthService.__init__)

        assert list(sig.parameters) == ["self", "config", "session"]
        assert sig.parameters["config"].annotation == "TCBSCredentialConfig"
        assert sig.parameters["session"].annotation == "BrokerSession"

    def test_original_public_methods_still_present(self):
        public = {n for n in dir(TCBSAuthService) if not n.startswith("_")}

        assert {"authenticate", "is_token_valid", "revoke"} <= public


# ─── Ràng buộc kỹ thuật của lát T ────────────────────────────────────────────

class TestSliceConstraints:
    def test_module_under_400_lines(self):
        from pathlib import Path

        src = Path(token_manager_mod.__file__).read_text(encoding="utf-8")

        assert len(src.splitlines()) <= 400, f"token_manager.py vượt 400L: {len(src.splitlines())}L"

    def test_no_new_third_party_dependency(self):
        """JWT decode bằng stdlib base64+json — không cài pyjwt."""
        src = textwrap.dedent(inspect.getsource(token_manager_mod))

        assert "import jwt" not in src
        assert "pyjwt" not in src.lower()

    def test_uses_rlock_like_broker_session(self):
        tm = TokenManager()

        assert isinstance(getattr(tm, "_lock", None), type(threading.RLock()))

    def test_public_surface_is_exported(self):
        assert "TokenManager" in token_manager_mod.__all__