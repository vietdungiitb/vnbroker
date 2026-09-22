"""
vnbroker.broker.ssi._utils — validators, coercion số, date helpers cho SSI lane.

Fail-sớm với BrokerValidationError thay vì để server trả 400 khó đọc.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Union

from vnbroker.broker.exceptions import BrokerValidationError

SSI_DATE_FMT = "%Y/%m/%d"
SSI_DATETIME_FMT = "%Y/%m/%d %H:%M:%S"


def require_non_empty(value: Any, name: str) -> str:
    """Validate string non-empty (strip). Trả về chuỗi đã strip."""
    text = str(value).strip() if value is not None else ""
    if not text:
        raise BrokerValidationError(
            message=f"{name} không được để trống.",
            code="EMPTY_FIELD",
            http_status=400,
        )
    return text


def require_positive(value: Union[int, float], name: str) -> Union[int, float]:
    """Validate số > 0."""
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise BrokerValidationError(
            message=f"{name} phải > 0. Nhận: {value!r}",
            code="INVALID_POSITIVE",
            http_status=400,
        )
    return value


def require_non_negative(value: Union[int, float], name: str) -> Union[int, float]:
    """Validate số >= 0."""
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise BrokerValidationError(
            message=f"{name} phải >= 0. Nhận: {value!r}",
            code="INVALID_NON_NEGATIVE",
            http_status=400,
        )
    return value


def require_empty(value: Any, name: str) -> None:
    """Validate field phải rỗng/None (dùng cho modify: giá HOẶC lượng)."""
    if value is not None:
        raise BrokerValidationError(
            message=f"{name} phải để trống khi field đối ứng đã set.",
            code="MUTUALLY_EXCLUSIVE",
            http_status=400,
        )


def validate_ssi_date(value: str, name: str) -> str:
    """Validate date "YYYY/MM/DD" strict. Trả về chuỗi đã strip."""
    text = require_non_empty(value, name)
    try:
        datetime.strptime(text, SSI_DATE_FMT)
    except ValueError as exc:
        raise BrokerValidationError(
            message=f"{name} phải định dạng YYYY/MM/DD. Nhận: {value!r}",
            code="INVALID_DATE",
            http_status=400,
        ) from exc
    return text


def validate_ssi_datetime(value: str, name: str) -> str:
    """Validate datetime "YYYY/MM/DD HH:MM:SS" strict (FCO place)."""
    text = require_non_empty(value, name)
    try:
        datetime.strptime(text, SSI_DATETIME_FMT)
    except ValueError as exc:
        raise BrokerValidationError(
            message=f"{name} phải định dạng YYYY/MM/DD HH:MM:SS. Nhận: {value!r}",
            code="INVALID_DATETIME",
            http_status=400,
        ) from exc
    return text


def today_date_str() -> str:
    """Ngày hôm nay "YYYY/MM/DD" (giờ local)."""
    return datetime.now().strftime(SSI_DATE_FMT)


def to_int(value: Any, default: int = 0) -> int:
    """Ép số nguyên, lỗi → default (không raise — dữ liệu server có thể bẩn)."""
    try:
        if value is None or value == "":
            return default
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return default


def to_float(value: Any, default: float = 0.0) -> float:
    """Ép số thực, lỗi → default."""
    try:
        if value is None or value == "":
            return default
        return float(str(value).strip())
    except (ValueError, TypeError):
        return default


def to_number(value: Any, default: Union[int, float] = 0) -> Union[int, float]:
    """Ép số: giữ int nếu nguyên, else float; lỗi → default."""
    result = to_float(value, float(default))
    if result.is_integer():
        return int(result)
    return result


def to_price(value: Any) -> Union[int, float]:
    """Ép giá (server có thể trả "66800.0" dạng chuỗi)."""
    return to_number(value, 0)


def opt_str(value: Any) -> Optional[str]:
    """None/empty → None, else str stripped."""
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None
