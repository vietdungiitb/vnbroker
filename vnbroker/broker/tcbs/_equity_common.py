"""Phần dùng chung giữa `equity.py` (đọc) và `equity_orders.py` (ghi).

Tách ra 2026-10-10 để tránh IMPORT VÒNG: cả hai cần cùng bảng `_PATHS` và
cùng hàm validate, nhưng `equity.py` phải import `EquityWriteMixin` từ
`equity_orders.py`. Gộp vào đây thì quan hệ import là một chiều.
"""

from __future__ import annotations

from vnbroker.broker.exceptions import BrokerValidationError

_PATHS = {
    "orders": "/aion/v1/accounts/{accountNo}/orders",
    "order_detail": "/aion/v1/accounts/{accountNo}/orders/{orderID}",
    "matching_details": "/aion/v1/accounts/{accountNo}/matching-details",
    "se": "/aion/v1/accounts/{accountNo}/se",
    "place_order": "/akhlys/v1/accounts/{accountNo}/orders",
    "modify_order": "/akhlys/v1/accounts/{accountNo}/orders/{orderId}",
    "cancel_orders": "/akhlys/v1/accounts/{accountNo}/cancel-orders",
    # market enrichment (dùng trong get_holdings)
    "ticker_commons": "/tartarus/v1/tickerCommons",
}

_VALID_PRICE_TYPES = frozenset({"LO", "ATO", "ATC", "PLO", "MP", "MTL", "MOK", "MAK"})


def _validate_order_input(
    symbol: str,
    side: str,
    order_type: str,
    quantity: int,
    price: float,
    request_id: str,
) -> None:
    """Validate đầu vào cho place_order theo TCBS iFlash spec."""
    if not symbol or not symbol.strip():
        raise BrokerValidationError(
            message="symbol không được để trống.",
            code="INVALID_SYMBOL",
        )
    if side.upper() not in ("BUY", "SELL"):
        raise BrokerValidationError(
            message="side phải là 'BUY' hoặc 'SELL'.",
            code="INVALID_SIDE",
        )
    if order_type.upper() not in _VALID_PRICE_TYPES:
        raise BrokerValidationError(
            message=f"order_type không hợp lệ. Hỗ trợ: {', '.join(sorted(_VALID_PRICE_TYPES))}.",
            code="INVALID_ORDER_TYPE",
        )
    if quantity <= 0:
        raise BrokerValidationError(
            message="quantity phải > 0.",
            code="INVALID_QUANTITY",
        )
    if price < 0:
        raise BrokerValidationError(
            message="price phải >= 0.",
            code="INVALID_PRICE",
        )
    if not request_id or not request_id.strip():
        raise BrokerValidationError(
            message="request_id là bắt buộc cho write methods (idempotency key).",
            code="MISSING_REQUEST_ID",
        )

