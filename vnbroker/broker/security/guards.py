"""
vnbroker.broker.security.guards — write_gate decorator.

RULE: Mọi write method trong broker lane PHẢI được decorate với @write_gate.
      Không có exception; không được bypass bằng cách truyền dry_run=False
      khi session chưa is_write_enabled.
"""
from __future__ import annotations

import functools
from typing import Any, Callable

from vnbroker.broker.exceptions import BrokerPermissionError


def write_gate(fn: Callable) -> Callable:
    """
    Decorator bắt buộc trên mọi write method của broker service.

    Behaviour:
      1. Nếu dry_run=True (default) → KHÔNG gọi HTTP.
         Trả về dict mô tả lệnh đã được redact, không side-effect.
      2. Nếu dry_run=False nhưng session.is_write_enabled = False
         → raise BrokerPermissionError.
      3. Nếu dry_run=False và session.is_write_enabled = True → gọi fn() bình thường.

    Caller phải có thuộc tính `self._session` là BrokerSession instance.

    Args:
        fn: Method cần wrap. Signature phải có `dry_run: bool = True` param.

    Example:
        class TCBSEquityService:
            @write_gate
            def place_order(self, ..., dry_run: bool = True) -> dict:
                # Chỉ chạy khi dry_run=False và session.is_write_enabled
                ...
    """

    @functools.wraps(fn)
    def wrapper(self: Any, *args: Any, dry_run: bool = True, **kwargs: Any) -> Any:
        if dry_run:
            return {
                "dry_run": True,
                "operation": fn.__name__,
                "message": (
                    f"[DRY_RUN] {fn.__name__} — lệnh không được gửi. "
                    "Đặt dry_run=False và gọi session.enable_write() để thực thi."
                ),
                "args_count": len(args),
                "kwargs_keys": list(kwargs.keys()),
            }

        # Kiểm tra session write permission
        session = getattr(self, "_session", None)
        if session is None or not session.is_write_enabled:
            raise BrokerPermissionError(
                message=(
                    "Write chưa được phép. "
                    "Gọi session.enable_write() sau khi authenticate() trước."
                ),
                code="WRITE_NOT_ENABLED",
                http_status=403,
            )

        return fn(self, *args, dry_run=dry_run, **kwargs)

    return wrapper
