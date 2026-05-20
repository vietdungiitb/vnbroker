"""
vnbroker.broker.tcbs.auth — TCBSAuthService: xác thực OTP và quản lý token lifecycle.

SECURITY RULES (bắt buộc, không được vi phạm):
  - KHÔNG log api_key, otp, token ở bất kỳ level nào (kể cả DEBUG).
  - Payload request PHẢI được redact trước khi đưa vào bất kỳ log/audit nào.
  - Dùng requests trực tiếp — KHÔNG dùng vnbroker.core.utils.client (log raw payload).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import requests

from vnbroker.broker.exceptions import (
    BrokerAuthError,
    BrokerNetworkError,
    BrokerSessionExpiredError,
)
from vnbroker.broker.security.credentials import TCBSCredentialConfig
from vnbroker.broker.session import BrokerSession

_logger = logging.getLogger("vnbroker.broker.tcbs.auth")

_AUTH_PATH = "/gaia/v1/oauth2/openapi/token"


class TCBSAuthService:
    """
    Xử lý luồng xác thực với TCBS OpenAPI.

    Flow:
        1. authenticate(otp) → POST /gaia/v1/oauth2/openapi/token
        2. Nhận token + expiredTime → session.set_token()
        3. Session chuyển AUTHENTICATED_READ

    Không xử lý write enable — caller dùng session.enable_write() khi cần.
    """

    def __init__(
        self,
        config: TCBSCredentialConfig,
        session: BrokerSession,
    ) -> None:
        self._config = config
        self._session = session

    def authenticate(self, otp: str) -> None:
        """
        Xác thực với TCBS bằng apiKey + OTP.

        Args:
            otp: 6 chữ số OTP từ ứng dụng TCBS. KHÔNG log.

        Raises:
            ValueError: Nếu otp rỗng hoặc whitespace.
            BrokerAuthError: Nếu TCBS trả lỗi auth (OTP sai, hết hạn, ...).
            BrokerNetworkError: Nếu network timeout hoặc 5xx.
        """
        if not otp or not otp.strip():
            raise ValueError("OTP không được để trống.")

        self._session.begin_authenticating()

        url = self._config.base_url.rstrip("/") + _AUTH_PATH

        # KHÔNG log payload — chứa api_key và otp
        payload = {
            "apiKey": self._config.api_key,
            "otp": otp.strip(),
        }

        try:
            resp = requests.post(
                url,
                json=payload,
                timeout=self._config.timeout_seconds,
            )
        except requests.exceptions.Timeout as exc:
            self._session.revoke()
            raise BrokerNetworkError(
                message=f"Timeout khi kết nối TCBS auth ({self._config.timeout_seconds}s).",
                code="NETWORK_TIMEOUT",
                http_status=0,
            ) from exc
        except requests.exceptions.RequestException as exc:
            self._session.revoke()
            raise BrokerNetworkError(
                message=f"Lỗi kết nối mạng: {type(exc).__name__}",
                code="NETWORK_ERROR",
                http_status=0,
            ) from exc

        if resp.status_code != 200:
            self._session.revoke()
            _logger.warning(
                "TCBS auth failed. status=%d",
                resp.status_code,
            )
            try:
                body = resp.json()
                code = body.get("code", "AUTH_FAILED")
                msg = body.get("message", "Xác thực thất bại.")
            except Exception:
                code = "AUTH_FAILED"
                msg = f"HTTP {resp.status_code}"
            raise BrokerAuthError(
                message=msg,
                code=code,
                http_status=resp.status_code,
            )

        try:
            data = resp.json()
            token: str = data["token"]
            expires_at: Optional[datetime] = self._parse_expires(data.get("expiredTime"))
        except (KeyError, ValueError) as exc:
            self._session.revoke()
            raise BrokerAuthError(
                message="TCBS trả về response auth không hợp lệ.",
                code="AUTH_RESPONSE_INVALID",
                http_status=resp.status_code,
            ) from exc

        # Lưu token vào session — KHÔNG log token
        self._session.set_token(token, expires_at=expires_at)
        _logger.info("TCBS authentication successful. expires_at=%s", expires_at)

    def is_token_valid(self) -> bool:
        """
        Trả về True nếu session có token hợp lệ và chưa hết hạn.
        Không raise — dùng để check trước khi authenticate.
        """
        try:
            return self._session.token is not None
        except BrokerSessionExpiredError:
            return False

    def revoke(self) -> None:
        """Huỷ session hiện tại — xoá token, state → EXPIRED."""
        self._session.revoke()

    # ── Private ──────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_expires(expired_time: object) -> Optional[datetime]:
        """
        Parse expiredTime từ TCBS response.

        Hỗ trợ:
          - ISO8601 string: "2026-05-20T18:00:00Z"
          - Epoch milliseconds: 1747742400000
          - None / không có → trả về None (không tự expire)
        """
        if expired_time is None:
            return None
        if isinstance(expired_time, (int, float)):
            # Epoch millis
            try:
                return datetime.fromtimestamp(expired_time / 1000, tz=timezone.utc)
            except (OSError, OverflowError, ValueError):
                return None
        if isinstance(expired_time, str):
            for fmt in (
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%S%z",
            ):
                try:
                    dt = datetime.strptime(expired_time, fmt)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except ValueError:
                    continue
        return None
