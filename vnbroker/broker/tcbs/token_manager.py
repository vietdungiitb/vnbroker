"""
vnbroker.broker.tcbs.token_manager — TokenManager: quản lý vòng đời JWT của TCBS.

KHÔNG gọi mạng. Spec TCBS v1.0.0 KHÔNG có endpoint refresh token (đếm chuỗi
"refresh" trong toàn spec = 0 lần) ⇒ TokenManager tự đọc `exp`/`iat` từ JWT và
để người gọi cấp token mới qua seam `token_provider`.

Nguyên tắc: KHÔNG đoán. Token không decode được ⇒ `expires_at=None` và
`is_expired()` trả `None` (chưa biết) thay vì giả định một hạn dùng.

SECURITY RULES (bắt buộc, không được vi phạm):
  - KHÔNG log token ở bất kỳ level nào (kể cả DEBUG).
  - KHÔNG log nội dung `token_provider` trả về.
"""
from __future__ import annotations

import base64
import binascii
import json
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional, cast

from vnbroker.broker.exceptions import BrokerSessionExpiredError
from vnbroker.broker.session import BrokerSession

__all__ = ["TokenManager"]

# Hướng dẫn cho người dùng khi token hết hạn — nêu đúng cách thoát ra.
_EXPIRED_GUIDANCE = (
    "Token TCBS đã hết hạn và không có nguồn thay thế. Spec TCBS 1.0.0 không có "
    "endpoint refresh token — cần Smart OTP (iOTP) mới từ ứng dụng TCInvest rồi "
    "gọi lại TCBSAuthService.authenticate()."
)
_PROVIDER_INVALID_GUIDANCE = (
    "token_provider trả về giá trị rỗng hoặc không phải chuỗi. Cần Smart OTP (iOTP) "
    "mới từ ứng dụng TCInvest."
)


class TokenManager:
    """
    Quản lý vòng đời JWT của TCBS bằng cách đọc claim cục bộ, không gọi mạng.

    Không phải "refresh tự động": TCBS không có endpoint refresh (spec v1.0.0).
    Đây là lớp giữ token + đọc hạn + seam `token_provider` cho người gọi.

    Attributes:
        token_provider: Callable trả JWT mới. `None` ⇒ hết hạn thì raise,
            không tự tìm nguồn thay thế.
        on_expiring: Callback bắn **một lần** mỗi token khi lần đầu bước vào
            ngưỡng buffer, nhận `expires_at` (None nếu không xác định được).
    """

    def __init__(
        self,
        token: Optional[str] = None,
        *,
        token_provider: Optional[Callable[[], str]] = None,
        on_expiring: Optional[Callable[[Optional[datetime]], None]] = None,
    ) -> None:
        """
        Khởi tạo TokenManager.

        Args:
            token: JWT ban đầu. Không bắt buộc decode được — token vẫn dùng được.
            token_provider: Callable trả JWT mới khi token sắp/cđã hết hạn.
            on_expiring: Callback báo "sắp hết hạn", bắn đúng 1 lần mỗi token.
        """
        self._lock = threading.RLock()
        self._token: Optional[str] = None
        self._expires_at: Optional[datetime] = None
        self._issued_at: Optional[datetime] = None
        self._expiring_notified = False
        self._token_provider = token_provider
        self._on_expiring = on_expiring
        # Buffer đọc từ BrokerSession — KHÔNG tự đặt hằng ở đây, nếu không sẽ
        # thành 2 nguồn sự thật cho cùng một khái niệm (session.py:51).
        self._refresh_buffer = timedelta(
            seconds=BrokerSession().TOKEN_REFRESH_BUFFER_SECONDS
        )
        if token is not None:
            self.set_token(token)

    # ── Thuộc tính ────────────────────────────────────────────────────────────

    @property
    def token(self) -> Optional[str]:
        """Token hiện tại (None nếu chưa có). Dùng token: `get_token()`."""
        with self._lock:
            return self._token

    @property
    def expires_at(self) -> Optional[datetime]:
        """Mốc hết hạn theo claim `exp`; None nếu token không decode được."""
        with self._lock:
            return self._expires_at

    @property
    def issued_at(self) -> Optional[datetime]:
        """Mốc phát hành theo claim `iat`; None nếu token không decode được."""
        with self._lock:
            return self._issued_at

    @property
    def has_token(self) -> bool:
        """True nếu đang giữ token."""
        with self._lock:
            return self._token is not None

    @property
    def refresh_buffer_seconds(self) -> int:
        """Buffer hết hạn (giây), lấy từ `BrokerSession.TOKEN_REFRESH_BUFFER_SECONDS`."""
        return int(self._refresh_buffer.total_seconds())

    def __repr__(self) -> str:
        return (
            f"TokenManager(has_token={self.has_token}, "
            f"expires_at={self.expires_at!r}, "
            f"refresh_buffer_seconds={self.refresh_buffer_seconds}, "
            f"token='REDACTED' if {self.has_token} else None, "
            f"has_provider={self._token_provider is not None})"
        )

    # ── API chính ─────────────────────────────────────────────────────────────

    def set_token(self, token: Optional[str]) -> None:
        """
        Gán token mới và đọc lại claim `exp`/`iat`.

        Args:
            token: JWT mới. `None` nghĩa là xoá token (xem `clear()`).
        """
        with self._lock:
            self._token = token
            self._expires_at = self.decode_expiry(token) if token is not None else None
            self._issued_at = self.decode_issued_at(token) if token is not None else None
            self._expiring_notified = False

    def clear(self) -> None:
        """Xoá token và mọi claim đã decode."""
        with self._lock:
            self._token = None
            self._expires_at = None
            self._issued_at = None
            self._expiring_notified = False

    def is_expired(self) -> Optional[bool]:
        """
        Kiểm token đã bước qua ngưỡng buffer hay chưa.

        Returns:
            True nếu đã bước qua ngưỡng buffer; False nếu còn hạn; **None** nếu
            không xác định được (chưa có token, hoặc token không phải JWT) —
            trường hợp này để caller tự quyết, không giả định.
        """
        with self._lock:
            if self._token is None or self._expires_at is None:
                return None
            return self._is_expired_locked()

    def get_token(self) -> str:
        """
        Lấy token, tự gọi `token_provider` đúng một lần nếu đã hết hạn.

        Raises:
            BrokerSessionExpiredError: Token đã hết hạn mà không có provider,
                hoặc provider trả về token rỗng / vẫn chết.

        Returns:
            Token còn dùng được. Token không phải JWT vẫn được trả về — không biết
            hạn thì không đoán.
        """
        with self._lock:
            if self._token is None:
                self._refresh_locked()
            if self._is_expired_locked():
                self._notify_expiring_locked()
                self._refresh_locked()
            if self._is_expired_locked():
                raise BrokerSessionExpiredError(
                    message=_EXPIRED_GUIDANCE,
                    code="SESSION_EXPIRED",
                    http_status=401,
                )
            return cast(str, self._token)

    # ── Decode JWT cục bộ (không verify chữ ký — chỉ đọc claim) ─────────────

    @staticmethod
    def decode_claims(token: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Giải mã payload JWT bằng stdlib (`base64` + `json`).

        Chữ ký KHÔNG được verify — mục đích chỉ là đọc `exp`/`iat`, và token do
        TCBS phát. Mọi lỗi (không đủ 3 phần, base64 hỏng, JSON hỏng) trả None.

        Args:
            token: JWT hoặc chuỗi bất kỳ.

        Returns:
            Dict claim, hoặc None nếu không giải mã được.
        """
        if not token:
            return None
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1]
        if not payload:
            return None
        # base64url trong JWT bỏ padding '=' — phải bù lại trước khi decode.
        padded = payload + "=" * (-len(payload) % 4)
        try:
            raw = base64.urlsafe_b64decode(padded.encode("ascii"))
            claims: object = json.loads(raw.decode("utf-8"))
        except (binascii.Error, UnicodeDecodeError, ValueError):
            return None
        if not isinstance(claims, dict):
            return None
        return cast(Dict[str, Any], claims)

    @classmethod
    def decode_expiry(cls, token: Optional[str]) -> Optional[datetime]:
        """
        Đọc claim `exp` thành datetime có timezone (UTC).

        Args:
            token: JWT hoặc chuỗi bất kỳ.

        Returns:
            datetime có tz, hoặc None nếu không đọc được.
        """
        return cls._claim_to_datetime((cls.decode_claims(token) or {}).get("exp"))

    @classmethod
    def decode_issued_at(cls, token: Optional[str]) -> Optional[datetime]:
        """
        Đọc claim `iat` thành datetime có timezone (UTC).

        Args:
            token: JWT hoặc chuỗi bất kỳ.

        Returns:
            datetime có tz, hoặc None nếu không đọc được.
        """
        return cls._claim_to_datetime((cls.decode_claims(token) or {}).get("iat"))

    # ── Private ───────────────────────────────────────────────────────────────

    @staticmethod
    def _claim_to_datetime(value: object) -> Optional[datetime]:
        """Chuyển claim số (epoch giây) sang datetime UTC; None nếu không hợp lệ."""
        # bool là subclass của int — loại trước, nếu không True sẽ thành epoch 1.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None

    def _is_expired_locked(self) -> bool:
        """True nếu đã bước qua ngưỡng buffer. Không xác định hạn ⇒ False (không đoán)."""
        if self._token is None or self._expires_at is None:
            return False
        return datetime.now(timezone.utc) >= (self._expires_at - self._refresh_buffer)

    def _notify_expiring_locked(self) -> None:
        """Bắn `on_expiring` đúng một lần mỗi token."""
        if self._expiring_notified or self._on_expiring is None:
            return
        self._expiring_notified = True
        self._on_expiring(self._expires_at)

    def _refresh_locked(self) -> None:
        """
        Gọi `token_provider` để lấy token mới.

        Raises:
            BrokerSessionExpiredError: Không có provider, provider trả rỗng,
                hoặc token mới vẫn đã hết hạn.
        """
        if self._token_provider is None:
            raise BrokerSessionExpiredError(
                message=_EXPIRED_GUIDANCE,
                code="SESSION_EXPIRED",
                http_status=401,
            )
        new_token = self._token_provider()
        if not new_token or not isinstance(new_token, str):
            raise BrokerSessionExpiredError(
                message=_PROVIDER_INVALID_GUIDANCE,
                code="TOKEN_REFRESH_FAILED",
                http_status=0,
            )
        self.set_token(new_token)
        if self._is_expired_locked():
            # Provider trả về token đã chết — raise thay vì lặp vô hạn.
            raise BrokerSessionExpiredError(
                message=_EXPIRED_GUIDANCE,
                code="SESSION_EXPIRED",
                http_status=401,
            )