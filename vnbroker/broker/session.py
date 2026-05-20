"""
vnbroker.broker.session — BrokerSession state machine.

Transitions (theo TCBS_BROKER_SPEC.md §3):
  CREATED → AUTHENTICATING           (set_token() gọi trong authenticate flow)
  AUTHENTICATING → AUTHENTICATED_READ (set_token() nhận token thành công)
  AUTHENTICATED_READ → AUTHENTICATED_WRITE_ENABLED (enable_write())
  AUTHENTICATED_READ/WRITE → EXPIRED  (revoke() hoặc token hết hạn)
  * → LOCKED                          (lock() khi security violation)

RULE: Token KHÔNG được log ở bất kỳ đâu.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum, auto
from typing import Optional

from vnbroker.broker.exceptions import (
    BrokerPermissionError,
    BrokerSessionExpiredError,
)


class SessionState(Enum):
    CREATED = auto()
    AUTHENTICATING = auto()
    AUTHENTICATED_READ = auto()
    AUTHENTICATED_WRITE_ENABLED = auto()
    EXPIRED = auto()
    LOCKED = auto()


class BrokerSession:
    """
    State machine cho vòng đời session broker.

    Sau khi LOCKED không thể unlock — tạo session mới.
    Token không bao giờ được xuất hiện trong repr, log, hay error message.
    """

    def __init__(self) -> None:
        self.state: SessionState = SessionState.CREATED
        self._token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._account_no: Optional[str] = None
        self._lock_reason: Optional[str] = None

    # ── Public properties ────────────────────────────────────────────────────

    @property
    def token(self) -> Optional[str]:
        """
        Trả về token nếu session hợp lệ.

        Raises:
            BrokerSessionExpiredError: Nếu state là EXPIRED hoặc LOCKED.
            BrokerSessionExpiredError: Nếu token đã quá expires_at.
        """
        if self.state in (SessionState.EXPIRED, SessionState.LOCKED):
            raise BrokerSessionExpiredError(
                message="Session đã hết hạn hoặc bị khoá. Vui lòng authenticate lại.",
                code="SESSION_EXPIRED",
                http_status=401,
            )
        if self._token_expires_at is not None:
            now = datetime.now(tz=timezone.utc)
            # Normalize timezone nếu expires_at không có tz
            expires = (
                self._token_expires_at
                if self._token_expires_at.tzinfo is not None
                else self._token_expires_at.replace(tzinfo=timezone.utc)
            )
            if now >= expires:
                self.state = SessionState.EXPIRED
                self._token = None
                raise BrokerSessionExpiredError(
                    message="Token đã hết hạn. Vui lòng authenticate lại.",
                    code="SESSION_EXPIRED",
                    http_status=401,
                )
        return self._token

    @property
    def is_write_enabled(self) -> bool:
        """True chỉ khi state = AUTHENTICATED_WRITE_ENABLED."""
        return self.state == SessionState.AUTHENTICATED_WRITE_ENABLED

    @property
    def is_authenticated(self) -> bool:
        """True khi state là READ hoặc WRITE_ENABLED."""
        return self.state in (
            SessionState.AUTHENTICATED_READ,
            SessionState.AUTHENTICATED_WRITE_ENABLED,
        )

    # ── State transitions ────────────────────────────────────────────────────

    def begin_authenticating(self) -> None:
        """
        Chuyển state CREATED → AUTHENTICATING.
        Gọi ngay trước khi gửi HTTP request authenticate.
        """
        if self.state == SessionState.LOCKED:
            raise BrokerPermissionError(
                message=f"Session đã bị khoá: {self._lock_reason}",
                code="SESSION_LOCKED",
                http_status=403,
            )
        self.state = SessionState.AUTHENTICATING

    def set_token(
        self,
        token: str,
        expires_at: Optional[datetime] = None,
    ) -> None:
        """
        Lưu token và chuyển state → AUTHENTICATED_READ.

        Args:
            token: JWT từ TCBS. KHÔNG log.
            expires_at: Thời điểm hết hạn (datetime). None = không tự expire.
        """
        self._token = token
        self._token_expires_at = expires_at
        self.state = SessionState.AUTHENTICATED_READ

    def enable_write(self) -> None:
        """
        Chuyển state → AUTHENTICATED_WRITE_ENABLED.

        Raises:
            BrokerPermissionError: Nếu state chưa phải AUTHENTICATED_READ.
        """
        if self.state != SessionState.AUTHENTICATED_READ:
            raise BrokerPermissionError(
                message=(
                    "Không thể enable write: session phải ở trạng thái "
                    f"AUTHENTICATED_READ, hiện là {self.state.name}."
                ),
                code="WRITE_ENABLE_REJECTED",
                http_status=403,
            )
        self.state = SessionState.AUTHENTICATED_WRITE_ENABLED

    def revoke(self) -> None:
        """Xoá token và chuyển state → EXPIRED."""
        self._token = None
        self._token_expires_at = None
        self.state = SessionState.EXPIRED

    def lock(self, reason: str) -> None:
        """
        Khoá session vĩnh viễn. Không thể unlock — tạo session mới.

        Args:
            reason: Lý do khoá (dùng cho logging/audit — KHÔNG chứa token/secret).
        """
        self._token = None
        self._lock_reason = reason
        self.state = SessionState.LOCKED

    # ── Repr ────────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        """Không expose token."""
        has_token = self._token is not None
        return (
            f"BrokerSession("
            f"state={self.state.name}, "
            f"has_token={has_token}, "
            f"expires_at={self._token_expires_at!r})"
        )
