"""
vnbroker.broker.exceptions — Exception hierarchy cho toàn bộ broker lane.

Đặt tại broker level (không phải tcbs level) để security/guards.py có thể import
mà không tạo circular dependency với vnbroker.broker.tcbs.

vnbroker/broker/tcbs/exceptions.py (S5) sẽ re-export từ đây + thêm TCBS-specific nếu cần.
"""
from __future__ import annotations


class BrokerError(Exception):
    """Base exception cho mọi lỗi từ broker lane."""

    def __init__(
        self,
        message: str,
        code: str = "",
        http_status: int = 0,
        request_id: str = "",
    ) -> None:
        self.message = message
        self.code = code
        self.http_status = http_status
        self.request_id = request_id
        super().__init__(message)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"code={self.code!r}, "
            f"http_status={self.http_status}, "
            f"request_id={self.request_id!r})"
        )


class BrokerAuthError(BrokerError):
    """401 — OTP sai, token hết hạn."""


class BrokerSessionExpiredError(BrokerError):
    """401 code=SESSION_EXPIRED — phiên đã hết hạn."""


class BrokerPermissionError(BrokerError):
    """403 — không đủ quyền (ví dụ: write khi chưa enable_write())."""


class BrokerValidationError(BrokerError):
    """400 — input sai."""


class BrokerRateLimitError(BrokerError):
    """429 — rate limit."""


class BrokerOrderError(BrokerError):
    """422 — lỗi nghiệp vụ lệnh."""


class BrokerNetworkError(BrokerError):
    """Timeout hoặc 5xx từ TCBS."""
