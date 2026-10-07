"""
vnbroker.brokerage.guards — hàng rào ghi cho lớp `brokerage/` (Private Brokerage).

VÌ SAO CẦN FILE RIÊNG (không dùng `vnbroker.broker.security.guards.write_gate`):

    `write_gate` của broker lane yêu cầu caller có `self._session` là một
    `BrokerSession` (đọc `session.is_write_enabled`, raise khi chưa enable).
    `BrokerageBase` **không có** session — nó là lớp độc lập, khác hẳn broker lane
    (xem docstring `brokerage/base.py`: "No PAT, No Gateway, No vninvest dependency").

    Ép `@write_gate` lên lớp này sẽ làm mọi write ném `BrokerPermissionError`
    vĩnh viễn (vì `self._session` luôn None) — biến hàng rào thành lỗi cứng.
    Vì vậy dựng cổng quyền riêng, tương thích với cấu trúc của lớp này.

MÔ HÌNH AN TOÀN (giống tinh thần `write_gate`, khác cơ chế):

    1. `dry_run=True` (MẶC ĐỊNH) → KHÔNG gọi HTTP. Trả `DryRunResult` mô tả lệnh
       đã được redact, không side-effect.
    2. `dry_run=False` nhưng chưa `enable_write()` → raise `BrokerPermissionError`.
    3. `dry_run=False` và đã `enable_write()` → gọi thật.

    Thứ tự trong `guarded_write` là **validate → guard → network**: guard chạy
    TRƯỚC mọi lời gọi HTTP nhưng SAU khi tham số đã được dựng. Nếu đặt guard
    trước validate, dry-run sẽ trả "OK" cho một lệnh mà lúc gửi thật chắc chắn
    raise — dry-run nói dối.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, ParamSpec, TypeVar

from vnbroker.broker.exceptions import BrokerPermissionError

P = ParamSpec("P")
R = TypeVar("R")

# Khóa bị loại khỏi bản mô tả dry-run (có thể chứa bí mật).
_REDACT_KEYS = frozenset(
    {
        "secret",
        "api_key",
        "apikey",
        "token",
        "access_token",
        "refresh_token",
        "password",
        "otp",
        "pin",
        "private_key",
        "signature",
    }
)


@dataclass
class DryRunResult:
    """Kết quả của một write bị chặn ở chế độ dry-run.

    Không phải `OrderResponse` — cố ý, để code gọi không thể vô tình xử lý nó
    như một lệnh đã đặt thành công.
    """

    dry_run: bool = True
    operation: str = ""
    message: str = ""
    kwargs: Dict[str, Any] = field(default_factory=dict)
    blocked: bool = True

    def __getitem__(self, key: str) -> Any:
        """Cho phép truy cập kiểu dict: result['operation']."""
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "operation": self.operation,
            "message": self.message,
            "kwargs": self.kwargs,
            "blocked": self.blocked,
        }


def _redact(value: Any) -> Any:
    """Loại bỏ giá trị của khóa nhạy cảm ở mọi độ sâu."""
    if isinstance(value, dict):
        return {
            k: "<redacted>" if k.lower() in _REDACT_KEYS else _redact(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(v) for v in value]
    return value


class WriteGateMixin:
    """Cổng quyền ghi cho lớp `brokerage/`.

    Lớp con kế thừa mixin này và bọc mọi write method bằng `@guarded_write`:

        class TCBSClient(WriteGateMixin, BrokerageBase):
            @guarded_write
            def place_order(self, request, *, dry_run: bool = True):
                ...  # chỉ chạy khi dry_run=False và đã enable_write()

    Trạng thái cổng nằm ở `self._write_enabled`, khởi tạo `False`.
    """

    _write_enabled: bool = False

    # ---------------------------------------------------------------- cổng
    @property
    def is_write_enabled(self) -> bool:
        """True khi đã gọi `enable_write()`."""
        return bool(getattr(self, "_write_enabled", False))

    def enable_write(self) -> None:
        """Mở cổng ghi sau khi người dùng đồng ý tường minh.

        Phải gọi SAU khi đã xác thực. Không có đường nào khác để mở cổng —
        không có tham số, biến môi trường, hay thuộc tính nào bypass được.
        """
        self._write_enabled = True

    def disable_write(self) -> None:
        """Đóng lại cổng ghi (dùng khi kết thúc phiên hoặc thu hồi quyền)."""
        self._write_enabled = False

    def _write_guard(self, operation: str, kwargs: Dict[str, Any]) -> DryRunResult:
        """Quyết định chặn hay cho qua. Tách riêng để test được không cần HTTP."""
        dry_run = kwargs.get("dry_run", True)
        if dry_run:
            return DryRunResult(
                operation=operation,
                message=(
                    f"[DRY_RUN] {operation} — lệnh KHÔNG được gửi. "
                    "Đặt dry_run=False và gọi enable_write() để thực thi."
                ),
                kwargs=_redact(kwargs),
            )
        if not self.is_write_enabled:
            raise BrokerPermissionError(
                message=(
                    "Write chưa được phép. Gọi enable_write() sau khi xác thực "
                    "trước khi đặt dry_run=False."
                ),
                code="WRITE_NOT_ENABLED",
                http_status=403,
            )
        return DryRunResult(dry_run=False, operation=operation, blocked=False)


def guarded_write(fn: Callable[P, R]) -> Callable[P, R]:
    """Decorator bắt buộc trên MỌI write method của `brokerage/`.

    Signature của hàm được bọc PHẢI khai `dry_run: bool = True`. Kiểm tra ở
    **thời điểm gắn decorator** (tức lúc import module), không phải mỗi lần gọi:
    lỗi lập trình phải nổ ngay khi import, không đợi tới lúc người dùng đặt lệnh.

    Lưu ý: `dry_run` là keyword-only (sau dấu `*`) nên nằm ở `__kwdefaults__`,
    không phải `__defaults__` — kiểm nhầm chỗ sẽ chặn oan mọi lời gọi.
    """
    import inspect

    sig = inspect.signature(fn)
    if "dry_run" not in sig.parameters:
        raise TypeError(
            f"{fn.__name__}: @guarded_write yêu cầu tham số 'dry_run: bool = True'. "
            "Thiếu nó thì không có chế độ dry-run — hàng rào vô nghĩa."
        )
    param = sig.parameters["dry_run"]
    if param.default is inspect.Parameter.empty:
        raise TypeError(
            f"{fn.__name__}: tham số 'dry_run' phải có giá trị MẶC ĐỊNH (True) — "
            "nếu không, mọi lời gọi buộc phải truyền tay và mặc định an toàn biến mất."
        )
    if param.default is not True:
        raise TypeError(
            f"{fn.__name__}: mặc định của 'dry_run' phải là True (đang là "
            f"{param.default!r}) — mặc định phải nghiêng về an toàn."
        )

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
        if not args or not isinstance(args[0], WriteGateMixin):
            raise TypeError(
                f"{fn.__name__}: @guarded_write chỉ dùng được trong lớp kế thừa "
                "WriteGateMixin."
            )
        self_obj = args[0]
        # dry_run là keyword-only (đã kiểm ở trên) nên chỉ cần đọc kwargs.
        # Cổng chạy TRƯỚC mọi HTTP call; quyết định dry-run/chặn/cho qua nằm
        # trong _write_guard để test được mà không cần network.
        decision = self_obj._write_guard(fn.__name__, dict(kwargs))
        if decision.dry_run:
            return decision
        return fn(*args, **kwargs)

    return wrapper


def guarded_writes(*names: str) -> Callable[[type], type]:
    """Class decorator: bọc nhiều method theo tên.

    Dùng khi lớp con không tiện gắn decorator lên từng method (ví dụ method
    kế thừa từ lớp khác). Kiểm tra tên tồn tại — sai tên là lỗi lập trình,
    phải nổ ngay chứ không được im lặng bỏ qua (bỏ qua = write không có cổng).
    """

    def decorator(cls: type) -> type:
        for name in names:
            original = getattr(cls, name, None)
            if original is None:
                raise TypeError(
                    f"guarded_writes: lớp {cls.__name__} không có method {name!r} "
                    "— kiểm lại tên, đừng để write không có cổng."
                )
            setattr(cls, name, guarded_write(original))
        return cls

    return decorator


__all__ = [
    "DryRunResult",
    "WriteGateMixin",
    "guarded_write",
    "guarded_writes",
]
