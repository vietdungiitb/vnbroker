"""
vnbroker.broker.ssi.auth — SSIAuthService: OTP/Smart-OTP/refresh, token lifecycle.

Endpoints:
  POST /api/v3/auth/token      → authenticate() (+ market-only khi không OTP)
  POST /api/v3/auth/requestOtp → request_otp()
  POST /api/v3/auth/refresh    → refresh()

Smart OTP push-approval pending = HTTP 202 + body {"code": 401114}:
được raise dạng _SmartOTPPending (subclass BrokerAuthError) để poll loop phân biệt.

SECURITY: KHÔNG log apiKey/apiSecret/otp/transactionId/token ở mọi level.
Body log phải qua Redactor.redact_dict. Dùng SSIHttpClient — KHÔNG core/utils/client.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from vnbroker.broker.exceptions import (
    BrokerAuthError,
    BrokerError,
    BrokerSessionExpiredError,
    BrokerValidationError,
)
from vnbroker.broker.security.credentials import SSICredentialConfig
from vnbroker.broker.security.redaction import Redactor
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.ssi import _paths
from vnbroker.broker.ssi._transport import SSIHttpClient

_logger = logging.getLogger("vnbroker.broker.ssi.auth")


class _SmartOTPPending(BrokerAuthError):
    """Internal: Smart OTP push chưa approve — chỉ poll loop bắt riêng."""


class SSIAuthService:
    """
    Xác thực SSI FastConnect v3 + quản lý token/refresh.

    Khác TCBS ở chỗ services nhận thêm `transport` dùng chung
    (1 Bearer header + 1 rate-limiter cho cả lane — xem client.py S7).
    """

    def __init__(
        self,
        config: SSICredentialConfig,
        session: BrokerSession,
        transport: SSIHttpClient,
    ) -> None:
        self._config = config
        self._session = session
        self._transport = transport
        self._refresh_token = ""

    # ── Public ───────────────────────────────────────────────────────────

    def authenticate(
        self,
        otp: Optional[str] = None,
        transaction_id: Optional[str] = None,
    ) -> str:
        """
        Xác thực lấy access token.

        - Không otp/transaction_id → market-data-only auth (không OTP).
        - otp → OTP thường / mã Smart OTP đọc tay trên app.
        - transaction_id → Smart OTP push (đã approve); chưa approve → _SmartOTPPending.

        Returns:
            access token string.

        Raises:
            BrokerValidationError: otp+transaction_id cùng lúc, hoặc chuỗi rỗng.
            BrokerAuthError: server từ chối / payload thiếu accessToken.
            BrokerNetworkError: lỗi mạng.
        """
        otp = _strict_opt(otp, "otp")
        transaction_id = _strict_opt(transaction_id, "transaction_id")
        if otp is not None and transaction_id is not None:
            raise BrokerValidationError(
                message="Chỉ truyền otp hoặc transaction_id, không cả hai.",
                code="MUTUALLY_EXCLUSIVE",
                http_status=400,
            )
        self._require_credentials()
        self._session.begin_authenticating()

        body: Dict[str, Any] = {
            "apiKey": self._config.api_key,
            "apiSecret": self._config.api_secret,
        }
        if otp is not None:
            body["otp"] = otp
        if transaction_id is not None:
            body["transactionId"] = transaction_id
        _logger.debug("SSI authenticate body=%s", Redactor.redact_dict(body))

        try:
            data = self._transport.request(
                "POST", _paths.EP_ACCESS_TOKEN, json_body=body
            )
            return self._store_token(data)
        except _SmartOTPPending:
            raise
        except BrokerError:
            self._session.revoke()
            self._transport.clear_token()
            raise

    def request_otp(self) -> Dict[str, Any]:
        """
        Yêu cầu gửi OTP (SMS/email) hoặc push Smart OTP. Server tự chọn kênh.

        Returns:
            dict gốc (chứa transactionId cho Smart OTP).
        """
        self._require_credentials()
        body = {
            "apiKey": self._config.api_key,
            "apiSecret": self._config.api_secret,
        }
        _logger.debug("SSI request_otp body=%s", Redactor.redact_dict(body))
        data = self._transport.request("POST", _paths.EP_REQUEST_OTP, json_body=body)
        return data if isinstance(data, dict) else {}

    def refresh(self) -> str:
        """
        Lấy access token mới bằng refresh token đang giữ.

        Raises:
            BrokerAuthError: chưa có refresh token, hoặc server từ chối.
        """
        if not self._refresh_token:
            raise BrokerAuthError(
                message="Không có refresh token — authenticate() trước.",
                code="NO_REFRESH_TOKEN",
                http_status=401,
            )
        self._require_credentials()
        self._session.begin_authenticating()
        body = {"refreshToken": self._refresh_token}
        try:
            data = self._transport.request(
                "POST", _paths.EP_REFRESH_TOKEN, json_body=body
            )
            return self._store_token(data)
        except _SmartOTPPending:  # pragma: no cover — refresh không pending
            raise
        except BrokerError:
            self._session.revoke()
            self._transport.clear_token()
            raise

    def ensure_authenticated(
        self,
        otp: Optional[str] = None,
        transaction_id: Optional[str] = None,
        poll_interval: float = _paths.SMART_OTP_POLL_INTERVAL,
        poll_max_retries: int = _paths.SMART_OTP_POLL_MAX_RETRIES,
    ) -> str:
        """
        Đảm bảo có token hợp lệ: còn hạn → dùng; có refresh → refresh;
        otp → authenticate 1 lần; transaction_id → poll tới khi approve.

        Raises:
            BrokerValidationError: poll params sai.
            BrokerAuthError: hết lượt poll / không có cách auth nào.
        """
        if poll_interval < 0 or poll_max_retries < 1:
            raise BrokerValidationError(
                message="poll_interval >= 0 và poll_max_retries >= 1.",
                code="INVALID_POLL",
                http_status=400,
            )
        if self.is_token_valid():
            token = self._session.token
            assert token is not None
            return token
        if self._refresh_token:
            return self.refresh()
        if otp is not None:
            return self.authenticate(otp=otp)
        if transaction_id is not None:
            last_error: Optional[BrokerError] = None
            for attempt in range(1, poll_max_retries + 1):
                try:
                    return self.authenticate(transaction_id=transaction_id)
                except _SmartOTPPending as exc:
                    last_error = exc
                    if attempt >= poll_max_retries:
                        break
                    _logger.info(
                        "SSI Smart OTP pending (%d/%d).",
                        attempt,
                        poll_max_retries,
                    )
                    if poll_interval > 0:
                        time.sleep(poll_interval)
            raise BrokerAuthError(
                message=(
                    f"Smart OTP chưa approve sau {poll_max_retries} lần — "
                    "bấm approve trên thiết bị rồi thử lại."
                ),
                code="SMART_OTP_TIMEOUT",
                http_status=401,
            ) from last_error
        raise BrokerAuthError(
            message="Cần otp hoặc transaction_id (không có refresh token).",
            code="NO_CREDENTIALS",
            http_status=401,
        )

    def set_token_manual(
        self,
        access_token: str,
        expires_at: Optional[datetime] = None,
        refresh_token: str = "",
    ) -> str:
        """Gán token thủ công (advanced). Không gọi mạng."""
        token = access_token.strip() if access_token else ""
        if not token:
            raise BrokerValidationError(
                message="access_token rỗng.",
                code="EMPTY_FIELD",
                http_status=400,
            )
        self._refresh_token = refresh_token
        self._transport.set_token(token)
        self._session.set_token(token, expires_at=expires_at)
        return token

    def is_token_valid(self) -> bool:
        """True nếu session còn token hợp lệ. Không raise."""
        try:
            return self._session.token is not None
        except BrokerSessionExpiredError:
            return False

    def revoke(self) -> None:
        """Hủy session + xóa bearer + quên refresh token."""
        self._refresh_token = ""
        self._transport.clear_token()
        self._session.revoke()

    # ── Private ──────────────────────────────────────────────────────────

    def _require_credentials(self) -> None:
        if not self._config.api_key.strip() or not self._config.api_secret.strip():
            raise BrokerAuthError(
                message="Thiếu api_key/api_secret SSI.",
                code="MISSING_CREDENTIALS",
                http_status=401,
            )

    def _store_token(self, data: Any) -> str:
        """Parse payload (hỗ trợ bọc {"data": {...}}), lưu token. Raise khi lỗi."""
        payload = data.get("data", data) if isinstance(data, dict) else None
        if not isinstance(payload, dict):
            raise BrokerAuthError(
                message="SSI trả response token không hợp lệ.",
                code="BAD_PAYLOAD",
                http_status=502,
            )
        access = str(payload.get("accessToken") or "")
        if not access:
            code = payload.get("code")
            if code == _paths.SMART_OTP_PENDING_CODE or str(code) == str(
                _paths.SMART_OTP_PENDING_CODE
            ):
                raise _SmartOTPPending(
                    message="Smart OTP push đang chờ approve trên thiết bị.",
                    code="SMART_OTP_PENDING",
                    http_status=_paths.SMART_OTP_PENDING_STATUS,
                )
            raise BrokerAuthError(
                message="SSI không trả accessToken.",
                code="TOKEN_MISSING",
                http_status=502,
            )
        expires_at = _epoch_to_datetime(payload.get("expiresAt"))
        self._refresh_token = str(payload.get("refreshToken") or "")
        self._transport.set_token(access)
        self._session.set_token(access, expires_at=expires_at)
        _logger.info("SSI authentication successful.")
        return access


def _strict_opt(value: Optional[str], name: str) -> Optional[str]:
    """
    None → None (không truyền). Chuỗi rỗng/whitespace → lỗi
    (tránh nhầm market-only auth khi user lỡ tay).
    """
    if value is None:
        return None
    text = value.strip()
    if not text:
        raise BrokerValidationError(
            message=f"{name} rỗng — bỏ trống hoàn toàn để auth market-only.",
            code="EMPTY_FIELD",
            http_status=400,
        )
    return text


def _epoch_to_datetime(value: Any) -> Optional[datetime]:
    """expiresAt epoch giây → datetime UTC. 0/None/invalid → None (session default)."""
    try:
        epoch = int(value)
    except (TypeError, ValueError):
        return None
    if epoch <= 0:
        return None
    try:
        return datetime.fromtimestamp(epoch, tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        return None
