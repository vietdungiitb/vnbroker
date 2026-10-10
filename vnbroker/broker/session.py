"""
Broker session state machine.

Manages authentication lifecycle and session state.
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import threading


class SessionState(Enum):
    """Session state machine states."""
    CREATED = "created"
    AUTHENTICATING = "authenticating"
    AUTHENTICATED_READ = "authenticated_read"
    AUTHENTICATED_WRITE_ENABLED = "authenticated_write_enabled"
    EXPIRED = "expired"
    LOCKED = "locked"
    REVOKED = "revoked"


from vnbroker.broker.exceptions import BrokerSessionExpiredError  # noqa: E402


@dataclass
class BrokerSession:
    """
    Broker session with state machine for auth lifecycle.

    State transitions:
    CREATED -> AUTHENTICATING -> AUTHENTICATED_READ -> AUTHENTICATED_WRITE_ENABLED
    Any state -> EXPIRED (on token expiry)
    Any state -> LOCKED (on security violation)
    Any state -> REVOKED (on explicit logout)
    """

    provider: str = "TCBS"
    api_key: str = ""
    base_url: str = "https://openapi.tcbs.com.vn"
    state: SessionState = SessionState.CREATED
    _token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    last_activity: datetime = field(default_factory=datetime.now)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    _lock_reason: str = ""

    # Configuration
    TOKEN_REFRESH_BUFFER_SECONDS: int = 300  # Refresh 5 min before expiry
    # ⚠ KHÔNG nhầm với hạn token. Đây là **timeout nhàn rỗi** của session.
    # Hạn token thật đến từ claim `exp` của JWT (`auth.py::_store_token`).
    # Con số 28800 từng bị hiểu là "JWT sống 8 giờ" — **SAI**, đo được 24 giờ.
    SESSION_TIMEOUT_SECONDS: int = 28800  # 8 giờ nhàn rỗi (không phải hạn token)

    #: Hạn JWT TCBS **ĐO ĐƯỢC** 2026-10-10 từ token thật trong `.env`:
    #: `exp - iat = 86400s = 24.0 giờ`. Tài liệu cũ ghi "~8 giờ" — sai.
    #: CHỈ dùng làm **fallback** khi JWT không có claim `exp`; không bao giờ
    #: định nghĩa hạn token. Xem `docs/evidence/tcbs-probe-20261010.json`.
    TCBS_JWT_TTL_SECONDS: int = 86400  # 24 giờ (đo, không phải ước lượng)

    def __post_init__(self):
        if isinstance(self.state, str):
            self.state = SessionState(self.state)

    def update_activity(self) -> None:
        """Update last activity timestamp."""
        with self._lock:
            self.last_activity = datetime.now()

    def begin_authenticating(self) -> None:
        """Mark session as authenticating."""
        with self._lock:
            if self.state == SessionState.LOCKED:
                from vnbroker.broker.exceptions import BrokerPermissionError
                raise BrokerPermissionError(
                    message="Session is locked.",
                    code="SESSION_LOCKED",
                    http_status=403,
                )
            self.state = SessionState.AUTHENTICATING
            self.update_activity()

    def set_token(
        self,
        token: str,
        expires_at: Optional[datetime] = None,
        expires_in_seconds: int = 86400,
    ) -> None:
        """
        Set authenticated state with token.

        Args:
            token: JWT token
            expires_at: Explicit expiration datetime (takes precedence over expires_in_seconds)
            expires_in_seconds: Token validity in seconds. **Default 86400 (24h)** —
                đo được từ JWT TCBS thật (`exp - iat`, 2026-10-10). Trước đây là
                28800 (8h) do **ước lượng từ tài liệu**, thấp hơn thực tế một
                nửa: token còn hiệu lực vẫn bị coi là hết hạn sớm.

        ⚠ `expires_in_seconds` chỉ là **fallback**. Đường thật là `expires_at`
        lấy từ claim `exp` (xem `broker/tcbs/auth.py::_store_token`). Còn khi
        không có `exp` thì `is_token_expired()` coi token là **đã hết hạn**
        (fail-closed) — con số này không thay thế được việc đó.
        """
        with self._lock:
            self._token = token
            if expires_at is not None:
                self.token_expires_at = expires_at
            else:
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in_seconds)
            self.state = SessionState.AUTHENTICATED_READ
            self.update_activity()

    def enable_write(self) -> None:
        """Enable write mode after explicit user consent."""
        with self._lock:
            if self.state == SessionState.AUTHENTICATED_READ:
                self.state = SessionState.AUTHENTICATED_WRITE_ENABLED
            else:
                from vnbroker.broker.exceptions import BrokerPermissionError
                raise BrokerPermissionError(
                    message=f"Cannot enable write mode from state {self.state}. Must be in AUTHENTICATED_READ state.",
                    code="WRITE_ENABLE_REJECTED",
                    http_status=403,
                )

    def disable_write_mode(self) -> None:
        """Disable write mode, revert to read-only."""
        with self._lock:
            if self.state == SessionState.AUTHENTICATED_WRITE_ENABLED:
                self.state = SessionState.AUTHENTICATED_READ

    @property
    def token(self) -> str:
        """Get token if valid, otherwise raise BrokerSessionExpiredError."""
        with self._lock:
            if self.state in (SessionState.EXPIRED, SessionState.LOCKED, SessionState.REVOKED):
                raise BrokerSessionExpiredError("Session expired or revoked")
            if self.token_expires_at is not None:
                buffer = timedelta(seconds=self.TOKEN_REFRESH_BUFFER_SECONDS)
                now = datetime.now(self.token_expires_at.tzinfo) if self.token_expires_at.tzinfo is not None else datetime.now()
                if now >= (self.token_expires_at - buffer):
                    self.state = SessionState.EXPIRED
                    raise BrokerSessionExpiredError(
                        message="Token expired",
                        code="SESSION_EXPIRED",
                        http_status=401,
                    )
            if self._token is None:
                raise BrokerSessionExpiredError("No token set")
            return self._token

    @property
    def is_authenticated(self) -> bool:
        """Check if session is authenticated (read or write)."""
        with self._lock:
            return self.state in (
                SessionState.AUTHENTICATED_READ,
                SessionState.AUTHENTICATED_WRITE_ENABLED
            )

    @property
    def is_write_enabled(self) -> bool:
        """Check if write operations are allowed."""
        with self._lock:
            return self.state == SessionState.AUTHENTICATED_WRITE_ENABLED

    def is_token_expired(self) -> bool:
        """Check if token is expired or about to expire."""
        if self.token_expires_at is None:
            return True
        buffer = timedelta(seconds=self.TOKEN_REFRESH_BUFFER_SECONDS)
        now = datetime.now(self.token_expires_at.tzinfo) if self.token_expires_at.tzinfo is not None else datetime.now()
        return now >= (self.token_expires_at - buffer)

    def is_session_expired(self) -> bool:
        """Check if session has timed out due to inactivity."""
        timeout = timedelta(seconds=self.SESSION_TIMEOUT_SECONDS)
        return datetime.now() >= (self.last_activity + timeout)

    def check_and_update_state(self) -> SessionState:
        """
        Check session validity and update state if needed.

        Returns:
            Current session state
        """
        with self._lock:
            if self.state in (SessionState.EXPIRED, SessionState.LOCKED, SessionState.REVOKED):
                return self.state

            if self.is_session_expired() or self.is_token_expired():
                self.state = SessionState.EXPIRED
                return self.state

            return self.state

    def revoke(self) -> None:
        """Revoke session explicitly (logout)."""
        with self._lock:
            self.state = SessionState.REVOKED
            self._token = None
            self.token_expires_at = None

    def lock(self, reason: str = "Security violation") -> None:
        """Lock session due to security concern."""
        with self._lock:
            self.state = SessionState.LOCKED
            self._token = None
            self.token_expires_at = None
            self._lock_reason = reason

    def get_auth_header(self) -> Optional[str]:
        """Get Authorization header value if authenticated."""
        with self._lock:
            if self.state in (
                SessionState.AUTHENTICATED_READ,
                SessionState.AUTHENTICATED_WRITE_ENABLED
            ) and self._token:
                return f"Bearer {self._token}"
            return None

    def can_write(self) -> bool:
        """Check if write operations are allowed."""
        with self._lock:
            return self.state == SessionState.AUTHENTICATED_WRITE_ENABLED

    def __str__(self) -> str:
        return f"BrokerSession(provider={self.provider}, state={self.state.value})"

    def __repr__(self) -> str:
        has_token = self._token is not None
        return (
            f"BrokerSession(provider={self.provider!r}, "
            f"api_key={self.api_key!r}, "
            f"base_url={self.base_url!r}, "
            f"state={self.state.value!r}, "
            f"_token={'REDACTED' if self._token else None}, "
            f"token_expires_at={self.token_expires_at}, "
            f"has_token={has_token})"
        )