"""
vnbroker.broker.ssi.equity — SSIEquityService: đặt/sửa/hủy lệnh cơ sở (ký RSA).

  POST   /api/v3/trading/order → place_order (+alias limit/market/ato/atc)
  PUT    /api/v3/trading/order → modify_order (giá HOẶC lượng, cấm đồng thời)
  DELETE /api/v3/trading/order → cancel_order

SECURITY (mirror TCBS equity.py):
  - dry_run=True mặc định + @write_gate bắt buộc (chưa enable_write → 403).
  - Validation chạy TRƯỚC gate (public validate → delegate internal gated).
  - price gửi wire dạng string; request_id (nanoid) bắt buộc (tự sinh nếu thiếu).
  - KHÁC TCBS: không có pin_code — SSI ký RSA bằng private_key của config.
  - private_key/body/signature KHÔNG log.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Union

from vnbroker.broker.exceptions import BrokerValidationError
from vnbroker.broker.security.credentials import SSICredentialConfig
from vnbroker.broker.security.guards import write_gate
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.ssi import _paths
from vnbroker.broker.ssi._enums import (
    OrderSide,
    OrderType,
    parse_side as _parse_side,
    safe_parse,
)
from vnbroker.broker.ssi._signing import generate_request_id
from vnbroker.broker.ssi._transport import SSIHttpClient
from vnbroker.broker.ssi._utils import (
    require_empty,
    require_non_empty,
    require_non_negative,
    require_positive,
)

_logger = logging.getLogger("vnbroker.broker.ssi.equity")


def _user_agent() -> str:
    try:
        from importlib.metadata import version

        return f"vnbroker/{version('vnbroker')}"
    except Exception:
        return "vnbroker/unknown"


_USER_AGENT = _user_agent()


class SSIEquityService:
    """Write (+alias) equity orders cho SSI broker."""

    def __init__(
        self,
        config: SSICredentialConfig,
        session: BrokerSession,
        transport: SSIHttpClient,
    ) -> None:
        self._config = config
        self._session = session
        self._transport = transport

    # ── Place ────────────────────────────────────────────────────────────

    def place_order(
        self,
        account_no: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: int,
        price: Union[int, float] = 0,
        request_id: Optional[str] = None,
        *,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """
        Đặt lệnh. dry_run=True mặc định (không gửi).

        Args:
            side: "BUY"/"SELL" (map sang "B"/"S").
            order_type: LO/MTL/MP/ATO/ATC/MOK/MAK/PLO.
            price: VND; 0 cho lệnh không giá (MTL/ATO/ATC); LO bắt buộc > 0.
            request_id: idempotency key; None → tự sinh nanoid 20 ký tự.
        """
        account_no = require_non_empty(account_no, "accountNo")
        symbol = require_non_empty(symbol, "symbol").upper()
        parsed_side = _parse_side(side)
        parsed_type = _parse_order_type(order_type)
        quantity = _validate_quantity(quantity)
        price = _validate_price(price, parsed_type)
        request_id = request_id.strip() if request_id else ""
        if not request_id:
            request_id = generate_request_id()
            _logger.debug("SSI place_order: sinh request_id mới.")
        return self._gated_place_order(
            account_no,
            symbol,
            parsed_side,
            parsed_type,
            quantity,
            price,
            request_id,
            dry_run=dry_run,
        )

    @write_gate
    def _gated_place_order(
        self,
        account_no: str,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: int,
        price: Union[int, float],
        request_id: str,
        *,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        payload = {
            "accountNo": account_no,
            "symbol": symbol,
            "side": side.value,
            "quantity": quantity,
            "price": f"{price}",
            "orderType": order_type.value,
            "clientRequestId": request_id,
            "deviceId": self._config.device_id,
            "userAgent": _USER_AGENT,
        }
        body = json.dumps(payload)
        data = self._transport.request_signed(
            "POST", _paths.EP_TRADING_ORDER, body, self._config.private_key
        )
        rec = data if isinstance(data, dict) else {}
        return {
            "order_id": str(rec.get("orderId", "")),
            "client_request_id": str(rec.get("clientRequestId", request_id)),
            "status": str(rec.get("orderStatus", "")),
        }

    def place_limit_order(
        self,
        account_no: str,
        symbol: str,
        side: str,
        quantity: int,
        price: Union[int, float],
        request_id: Optional[str] = None,
        *,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Lệnh LO (giá bắt buộc > 0)."""
        require_positive(price, "price")
        return self.place_order(
            account_no,
            symbol,
            side,
            "LO",
            quantity,
            price,
            request_id,
            dry_run=dry_run,
        )

    def place_market_order(
        self,
        account_no: str,
        symbol: str,
        side: str,
        quantity: int,
        request_id: Optional[str] = None,
        *,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Lệnh MTL (price=0)."""
        return self.place_order(
            account_no,
            symbol,
            side,
            "MTL",
            quantity,
            0,
            request_id,
            dry_run=dry_run,
        )

    def place_ato_order(
        self,
        account_no: str,
        symbol: str,
        side: str,
        quantity: int,
        request_id: Optional[str] = None,
        *,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Lệnh ATO (price=0)."""
        return self.place_order(
            account_no,
            symbol,
            side,
            "ATO",
            quantity,
            0,
            request_id,
            dry_run=dry_run,
        )

    def place_atc_order(
        self,
        account_no: str,
        symbol: str,
        side: str,
        quantity: int,
        request_id: Optional[str] = None,
        *,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Lệnh ATC (price=0)."""
        return self.place_order(
            account_no,
            symbol,
            side,
            "ATC",
            quantity,
            0,
            request_id,
            dry_run=dry_run,
        )

    # ── Modify ───────────────────────────────────────────────────────────

    def modify_order(
        self,
        account_no: str,
        quantity: Optional[int] = None,
        price: Optional[Union[int, float]] = None,
        order_id: str = "",
        client_request_id: str = "",
        *,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """
        Sửa lệnh: đúng 1 trong {price, quantity}; ít nhất 1 identifier.

        Args:
            order_id: server order ID (ưu tiên nếu cả hai cùng truyền).
            client_request_id: caller request ID.
        """
        account_no = require_non_empty(account_no, "accountNo")
        order_id = (order_id or "").strip()
        client_request_id = (client_request_id or "").strip()
        if not order_id and not client_request_id:
            raise BrokerValidationError(
                message="Cần order_id hoặc client_request_id.",
                code="MISSING_IDENTIFIER",
                http_status=400,
            )
        if price is not None and quantity is not None:
            raise BrokerValidationError(
                message="Chỉ sửa giá HOẶC lượng trong 1 lần gọi.",
                code="MUTUALLY_EXCLUSIVE",
                http_status=400,
            )
        if price is None and quantity is None:
            raise BrokerValidationError(
                message="Cần giá mới hoặc lượng mới.",
                code="EMPTY_FIELD",
                http_status=400,
            )
        if price is not None:
            require_non_negative(price, "price")
        if quantity is not None:
            require_positive(quantity, "quantity")
        return self._gated_modify_order(
            account_no,
            order_id,
            client_request_id,
            quantity,
            price,
            dry_run=dry_run,
        )

    @write_gate
    def _gated_modify_order(
        self,
        account_no: str,
        order_id: str,
        client_request_id: str,
        quantity: Optional[int],
        price: Optional[Union[int, float]],
        *,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "accountNo": account_no,
            "clientModifyId": generate_request_id(),
            "deviceId": self._config.device_id,
            "userAgent": _USER_AGENT,
        }
        if order_id:
            payload["orderId"] = order_id
        else:
            payload["clientRequestId"] = client_request_id
        if quantity is not None:
            payload["quantity"] = quantity
            require_empty(price, "price")
        if price is not None:
            payload["price"] = f"{price}"
            require_empty(quantity, "quantity")
        body = json.dumps(payload)
        data = self._transport.request_signed(
            "PUT", _paths.EP_TRADING_ORDER, body, self._config.private_key
        )
        rec = data if isinstance(data, dict) else {}
        return {
            "client_modify_id": str(rec.get("clientModifyId", "")),
            "order_id": str(rec.get("orderId", order_id)),
            "client_request_id": str(rec.get("clientRequestId", client_request_id)),
            "status": str(rec.get("orderStatus", "")),
        }

    # ── Cancel ───────────────────────────────────────────────────────────

    def cancel_order(
        self,
        account_no: str,
        order_id: str = "",
        client_request_id: str = "",
        *,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Hủy lệnh theo order_id hoặc client_request_id. dry_run=True mặc định."""
        account_no = require_non_empty(account_no, "accountNo")
        order_id = (order_id or "").strip()
        client_request_id = (client_request_id or "").strip()
        if not order_id and not client_request_id:
            raise BrokerValidationError(
                message="Cần order_id hoặc client_request_id.",
                code="MISSING_IDENTIFIER",
                http_status=400,
            )
        return self._gated_cancel_order(
            account_no, order_id, client_request_id, dry_run=dry_run
        )

    @write_gate
    def _gated_cancel_order(
        self,
        account_no: str,
        order_id: str,
        client_request_id: str,
        *,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "accountNo": account_no,
            "clientCancelId": generate_request_id(),
            "deviceId": self._config.device_id,
            "userAgent": _USER_AGENT,
        }
        if order_id:
            payload["orderId"] = order_id
        else:
            payload["clientRequestId"] = client_request_id
        body = json.dumps(payload)
        data = self._transport.request_signed(
            "DELETE", _paths.EP_TRADING_ORDER, body, self._config.private_key
        )
        rec = data if isinstance(data, dict) else {}
        return {
            "client_cancel_id": str(rec.get("clientCancelId", "")),
            "order_id": str(rec.get("orderId", order_id)),
            "client_request_id": str(rec.get("clientRequestId", client_request_id)),
            "status": str(rec.get("orderStatus", "")),
        }


# ── Validators ──────────────────────────────────────────────────────────


def _parse_order_type(order_type: str) -> OrderType:
    text = (order_type or "").strip().upper()
    parsed = safe_parse(OrderType, text)
    if parsed is None:
        raise BrokerValidationError(
            message=f"order_type không hỗ trợ: {order_type!r}. "
            "Dùng LO/MTL/MP/ATO/ATC/MOK/MAK/PLO.",
            code="INVALID_ORDER_TYPE",
            http_status=400,
        )
    return parsed


def _validate_quantity(quantity: Any) -> int:
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        raise BrokerValidationError(
            message=f"quantity phải là int > 0. Nhận: {quantity!r}",
            code="INVALID_QUANTITY",
            http_status=400,
        )
    return quantity


def _validate_price(
    price: Union[int, float], order_type: OrderType
) -> Union[int, float]:
    require_non_negative(price, "price")
    if order_type == OrderType.LO and price <= 0:
        raise BrokerValidationError(
            message="Lệnh LO yêu cầu price > 0.",
            code="INVALID_PRICE",
            http_status=400,
        )
    return price
