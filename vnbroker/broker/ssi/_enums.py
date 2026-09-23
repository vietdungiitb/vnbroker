"""
vnbroker.broker.ssi._enums — Enums wire-protocol SSI (giá trị cố định theo server).

Facade nhận "BUY"/"SELL" (chuẩn brokerage/base) rồi map sang OrderSide ở service.
Unknown value từ server → giữ string gốc ở DataFrame, không raise (xem safe_parse).
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, TypeVar

T = TypeVar("T", bound=Enum)


class OrderSide(str, Enum):
    BUY = "B"
    SELL = "S"


class OrderType(str, Enum):
    ATO = "ATO"
    ATC = "ATC"
    LO = "LO"
    MTL = "MTL"
    MP = "MP"
    MOK = "MOK"
    MAK = "MAK"
    PLO = "PLO"


class OrderStatus(str, Enum):
    PENDING = "PD"
    PENDING_APPROVAL = "WA"
    READY = "RS"
    SENT = "SD"
    QUEUED = "QU"
    FILLED = "FF"
    PARTIAL_FILLED = "PF"
    PARTIAL_CANCELLED = "FFPC"
    PENDING_MODIFY = "WM"
    PENDING_CANCEL = "WC"
    CANCELLED = "CL"
    REJECTED = "RJ"
    EXPIRED = "EX"
    PRE_SESSION = "IAV"


class Board(str, Enum):
    HOSE = "HOSE"
    HNX = "HNX"
    UPCOM = "UPCOM"
    DERIVATIVES = "DERIVATIVES"


class Timeframe(str, Enum):
    MINUTE_1 = "1m"
    MINUTE_3 = "3m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    DAY_1 = "1d"
    WEEK_1 = "1w"
    MONTH_1 = "1M"


class AccountType(str, Enum):
    EQUITY = "Cash"
    EQUITY_MARGIN = "Margin"
    DERIVATIVE = "Derivative"


class FCOType(str, Enum):
    GTD = "gtd"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    TRAILING_STOP_LIMIT = "trailing_stop_limit"
    OCO = "oco"
    BULL_BEAR = "bullbear"


class FCOOperator(str, Enum):
    GREATER = "greater"
    GREATER_OR_EQUAL = "greater_or_equal"
    LESSER = "lesser"
    LESSER_OR_EQUAL = "lesser_or_equal"
    EQUAL = "equal"


class FCOStatus(str, Enum):
    INIT = "INIT"
    WAIT = "WAIT"
    TRI = "TRI"
    TRIT = "TRIT"
    TER = "TER"
    FIS = "FIS"
    WC = "WC"
    EXP = "EXP"
    ERR = "ERR"


def safe_parse(enum_cls: type[T], value: object) -> Optional[T]:
    """Parse giá trị wire → Enum, trả None nếu không khớp (không raise)."""
    if isinstance(value, enum_cls):
        return value
    try:
        return enum_cls(value)
    except ValueError:
        return None


def parse_side(value: str) -> OrderSide:
    """Parse side facade ("BUY"/"SELL"/"B"/"S", case-insensitive) → OrderSide."""
    text = (value or "").strip().upper()
    if text in ("BUY", "B"):
        return OrderSide.BUY
    if text in ("SELL", "S"):
        return OrderSide.SELL
    from vnbroker.broker.exceptions import BrokerValidationError

    raise BrokerValidationError(
        message=f"side phải là BUY/SELL. Nhận: {value!r}",
        code="INVALID_SIDE",
        http_status=400,
    )
