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
from typing import Any, Dict, Optional

import requests

from vnbroker.broker.exceptions import (
    BrokerAuthError,
    BrokerError,
    BrokerNetworkError,
    BrokerSessionExpiredError,
)
from vnbroker.broker.security.credentials import TCBSCredentialConfig
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.tcbs.token_manager import TokenManager

_logger = logging.getLogger("vnbroker.broker.tcbs.auth")

_AUTH_PATH = "/gaia/v1/oauth2/openapi/token"
_APIKEY_INFO_PATH = "/gaia/v1/oauth2/openapi/apikey/info"
_APIKEY_EXTEND_PATH = "/gaia/v1/oauth2/openapi/apikey/extend"


class TCBSAuthService:
    """
    Xử lý luồng xác thực với TCBS OpenAPI.

    Flow:
        1. authenticate(otp) → POST /gaia/v1/oauth2/openapi/token
        2. Nhận token → session.set_token(), hạn lấy từ JWT claim `exp`
        3. Session chuyển AUTHENTICATED_READ

    KHÔNG có endpoint refresh token trong spec 1.0.0 ⇒ token mới chỉ lấy được
    bằng Smart OTP (iOTP) mới từ app TCInvest qua `authenticate()`.

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

        # KHÔNG log payload — chứa api_key và otp
        payload = {
            "apiKey": self._config.api_key,
            "otp": otp.strip(),
        }

        try:
            data = self._post_gaia(_AUTH_PATH, payload)
        except BrokerError:
            self._session.revoke()
            raise

        raw_token = data.get("token")
        if not isinstance(raw_token, str) or not raw_token:
            self._session.revoke()
            raise BrokerAuthError(
                message="TCBS trả về response auth không hợp lệ.",
                code="AUTH_RESPONSE_INVALID",
                http_status=200,
            )
        token = raw_token

        # AC T7: server KHÔNG gửi `expiredTime` (spec 1.0.0 đếm 0 lần) ⇒ hạn
        # phải lấy từ claim `exp` của JWT. Không có gì thì KHÔNG bịa hạn.
        expires_at = self._resolve_expires_at(data.get("expiredTime"), token)

        # Lưu token vào session — KHÔNG log token
        self._store_token(token, expires_at)
        _logger.info("TCBS authentication successful. expires_at=%s", expires_at)

    def get_api_key_expiration(self) -> Optional[datetime]:
        """
        Tra hạn hiệu lực của API key.

        POST /gaia/v1/oauth2/openapi/apikey/info — body `{"apiKey": ...}`,
        response 200 trả `expireDate` (ISO 8601, múi giờ Việt Nam +07:00).

        Returns:
            datetime có tz, hoặc None nếu TCBS không trả `expireDate`.

        Raises:
            BrokerNetworkError: Timeout hoặc lỗi mạng.
            BrokerAuthError: HTTP khác 200 hoặc response không đọc được.
        """
        data = self._post_gaia(_APIKEY_INFO_PATH, {"apiKey": self._config.api_key})
        return self._parse_expires(data.get("expireDate"))

    def extend_api_key(self, otp: str) -> Optional[datetime]:
        """
        Gia hạn API key.

        POST /gaia/v1/oauth2/openapi/apikey/extend — body `{"apiKey", "otp"}`,
        response 200 trả `expireDate`.

        Gia hạn **API key**, KHÔNG phải JWT: vẫn cần Smart OTP (iOTP) mới từ
        app TCInvest, và KHÔNG phải endpoint refresh token. Phiên hiện tại
        không bị đụng tới.

        Args:
            otp: Smart OTP (iOTP) từ ứng dụng TCBS. KHÔNG log.

        Returns:
            Hạn mới của API key, hoặc None nếu TCBS không trả `expireDate`.

        Raises:
            ValueError: Nếu otp rỗng hoặc whitespace.
            BrokerNetworkError: Timeout hoặc lỗi mạng.
            BrokerAuthError: HTTP khác 200 hoặc response không đọc được.
        """
        if not otp or not otp.strip():
            raise ValueError("OTP không được để trống.")

        # KHÔNG log payload — chứa api_key và otp
        payload = {
            "apiKey": self._config.api_key,
            "otp": otp.strip(),
        }
        data = self._post_gaia(_APIKEY_EXTEND_PATH, payload)
        return self._parse_expires(data.get("expireDate"))

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

    def _post_gaia(self, path: str, payload: Dict[str, str]) -> Dict[str, Any]:
        """
        POST tới endpoint `gaia` và ánh xạ lỗi HTTP/network sang broker exception.

        Args:
            path: Đường dẫn sau base_url, ví dụ `/gaia/v1/oauth2/openapi/token`.
            payload: Body JSON. KHÔNG log — có thể chứa api_key/otp.

        Returns:
            Response 200 đã parse thành dict.

        Raises:
            BrokerNetworkError: Timeout hoặc lỗi mạng.
            BrokerAuthError: HTTP khác 200, hoặc body không phải JSON object.
        """
        url = self._config.base_url.rstrip("/") + path

        try:
            resp = requests.post(
                url,
                json=payload,
                timeout=self._config.timeout_seconds,
            )
        except requests.exceptions.Timeout as exc:
            raise BrokerNetworkError(
                message=f"Timeout khi kết nối TCBS ({self._config.timeout_seconds}s).",
                code="NETWORK_TIMEOUT",
                http_status=0,
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise BrokerNetworkError(
                message=f"Lỗi kết nối mạng: {type(exc).__name__}",
                code="NETWORK_ERROR",
                http_status=0,
            ) from exc

        if resp.status_code != 200:
            _logger.warning("TCBS request failed. path=%s status=%d", path, resp.status_code)
            code = "AUTH_FAILED"
            msg = f"HTTP {resp.status_code}"
            try:
                body: object = resp.json()
                if isinstance(body, dict):
                    code = str(body.get("code", code))
                    msg = str(body.get("message", msg))
            except ValueError:
                pass
            raise BrokerAuthError(
                message=msg,
                code=code,
                http_status=resp.status_code,
            )

        try:
            data: object = resp.json()
        except ValueError as exc:
            raise BrokerAuthError(
                message="TCBS trả về response không hợp lệ.",
                code="AUTH_RESPONSE_INVALID",
                http_status=resp.status_code,
            ) from exc
        if not isinstance(data, dict):
            raise BrokerAuthError(
                message="TCBS trả về response không hợp lệ.",
                code="AUTH_RESPONSE_INVALID",
                http_status=resp.status_code,
            )
        return data

    @staticmethod
    def _resolve_expires_at(expired_time: object, token: str) -> Optional[datetime]:
        """
        Chọn nguồn hạn token theo thứ tự ưu tiên (AC T7).

        (a) `expiredTime` — nhánh tương thích ngược. Spec TCBS 1.0.0 KHÔNG có
            field này (đếm 0 lần trong toàn spec) ⇒ **không reachable** từ
            server thật, giữ lại chỉ để không vỡ tương thích.
        (b) claim `exp` của JWT — nguồn thật duy nhất theo spec hiện tại.
        (c) không có gì ⇒ None. KHÔNG tự chế hạn, để caller quyết.

        Args:
            expired_time: Giá trị `expiredTime` thô từ response (thường là None).
            token: JWT vừa nhận, dùng để đọc claim `exp`.

        Returns:
            datetime có tz, hoặc None nếu không xác định được.
        """
        expires_at = TCBSAuthService._parse_expires(expired_time)
        if expires_at is not None:
            return expires_at
        return TokenManager.decode_expiry(token)

    def _store_token(self, token: str, expires_at: Optional[datetime]) -> None:
        """
        Lưu token vào session mà KHÔNG tự chế hạn.

        `BrokerSession.set_token()` có `expires_in_seconds=28800` và chỉ bỏ qua
        khi `expires_at` khác None ⇒ gọi thẳng với `expires_at=None` sẽ khiến
        session tự chế **8 giờ bịa đặt** (bug F-2). Xoá lại ở đây cho khớp
        AC T7(c). Không sửa `session.py` — nằm ngoài phạm vi lát T.

        Việc xoá phải nằm **trong `_lock`** của session: `token` property đọc
        `token_expires_at` dưới cùng lock đó (session.py:116), nên ghi ngoài lock là
        race — thread đang đọc có thể thấy `expires_at=None` (chưa xoá) rồi đổi
        sang `(now + 8h)` (đã set_token), tức lại quay về bug F-2 một cách im lặng.
        """
        with self._session._lock:
            self._session.set_token(token, expires_at=expires_at)
            if expires_at is None:
                self._session.token_expires_at = None

    @staticmethod
    def _parse_expires(expired_time: object) -> Optional[datetime]:
        """
        Parse thời điểm hết hạn từ response TCBS.

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
