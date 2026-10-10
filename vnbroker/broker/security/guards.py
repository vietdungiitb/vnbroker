"""
vnbroker.broker.security.guards — write_gate decorator.

RULE: Mọi write method trong broker lane PHẢI được decorate với @write_gate.
      Không có exception; không được bypass bằng cách truyền dry_run=False
      khi session chưa is_write_enabled.
"""

from __future__ import annotations

import functools
from typing import Any, Callable, Dict, ParamSpec, TypeVar

from vnbroker.broker.exceptions import BrokerPermissionError

P = ParamSpec("P")
R = TypeVar("R")

# Tên tham số nhạy cảm — không đưa vào envelope dry-run. So khớp substring với
# chữ thường để bắt cả `pin`, `pin_code`, `pinCode`, `otp`, `api_key`.
_SENSITIVE_KWARG_NAMES = frozenset(
    {"pin", "pincode", "otp", "api_key", "apikey", "password", "secret", "token"}
)


def _is_sensitive_kwarg(name: str) -> bool:
    normalized = name.replace("-", "_").replace(" ", "").lower()
    return any(bad in normalized for bad in _SENSITIVE_KWARG_NAMES)


def write_gate(fn: Callable[P, R]) -> Callable[P, R]:
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
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        dry_run = kwargs.get("dry_run", True)
        if dry_run:
            result: Dict[str, Any] = {
                "dry_run": True,
                "operation": fn.__name__,
                "message": (
                    f"[DRY_RUN] {fn.__name__} — lệnh không được gửi. "
                    "Đặt dry_run=False và gọi session.enable_write() để thực thi."
                ),
                "args_count": len(args),
                # Chỉ TÊN tham số an toàn. Danh sách tên đầy đủ có thể chứa
                # `pin` / `otp` / `api_key` / `pin_code` — tên field nhạy cảm lọt
                # vào log nếu caller in envelope (audit round 2, F-9).
                "kwargs_keys": [
                    k for k in kwargs if not _is_sensitive_kwarg(k)
                ],
            }
            return result  # type: ignore[return-value]  # dry-run envelope, R ở nhánh thực
        self_obj = args[0] if args else None
        session = getattr(self_obj, "_session", None)
        if session is None or not session.is_write_enabled:
            raise BrokerPermissionError(
                message=(
                    "Write chưa được phép. "
                    "Gọi session.enable_write() sau khi authenticate() trước."
                ),
                code="WRITE_NOT_ENABLED",
                http_status=403,
            )

        return fn(*args, **kwargs)

    return wrapper
