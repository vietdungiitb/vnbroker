"""
vnbroker.broker.tcbs.derivative_orders - `DerivativeWriteMixin`: 10 method WRITE phai sinh.

Tach khoi `derivatives.py` de file do xuong duoi ngan sach 800L (`CLAUDE.md:15`).
`derivatives.py` truoc tach **852L** - vuot ngan sach san.

KHONG doi hanh vi:
- `TCBSDerivativesService` van **giu nguyen** moi public method va chu ky. Day la
  mixin, khong phai class moi, nen `client._derivatives.place_derivative_order(...)`
  goi y het nhu cu.
- `self._ORDER_PATHS` la class attribute; `derivatives.py` gan `_ORDER_PATHS = _PATHS`.
  Nho vay mixin khong `import` nguoc ve module cha (import vong la thu da gap - L-P03).
- `_post` / `_write_request` (74 dong) bi bo: moi write di qua `_write_http.post_json`,
  dung chung voi `money.py` va `condition_orders.py`. Truoc do moi service mot bang,
  va bang cua derivatives day du nhat - nho giu lai.
"""

from __future__ import annotations

from typing import Any, Dict

from vnbroker.broker.exceptions import BrokerValidationError
from vnbroker.broker.security.guards import write_gate
from vnbroker.broker.tcbs._write_http import post_json


class DerivativeWriteMixin:
    """10 method write phai sinh. Ke thua boi `TCBSDerivativesService`."""

    # Gan boi class con trong `derivatives.py`.
    _ORDER_PATHS: Dict[str, str] = {}

    _config: Any
    _session: Any

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST JSON - cung mot duong voi `money.py` va `condition_orders.py`."""
        return post_json(self._session, self._config, path, payload)

    def place_derivative_order(
        self,
        account_id: str,
        sub_account_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: int,
        price: float,
        request_id: str,
        *,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """
        POST /khronos/v1/order/place

        Args:
            account_id: Custody code (105C format).
            sub_account_id: Tiểu khoản phái sinh.
            symbol: Mã hợp đồng phái sinh.
            side: 'BUY' hoặc 'SELL'.
            order_type: 'LO', 'MP', 'ATO', 'ATC'.
            quantity: Khối lượng.
            price: Giá đặt lệnh.
            request_id: ID idempotency key (bắt buộc).
            dry_run: True (default) → không gửi HTTP.
        """
        if not account_id or not account_id.strip():
            raise BrokerValidationError(
                message="account_id không được để trống.",
                code="INVALID_ACCOUNT_ID",
            )
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
                message="request_id là bắt buộc cho write methods.",
                code="MISSING_REQUEST_ID",
            )
        return self._gated_place_derivative_order(
            account_id, sub_account_id, symbol, side, order_type, quantity, price, request_id,
            dry_run=dry_run,
        )

    @write_gate
    def _gated_place_derivative_order(
        self,
        account_id: str,
        sub_account_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: int,
        price: float,
        request_id: str,
        *,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        payload = {
            "accountId": account_id,
            "subAccountId": sub_account_id,
            "symbol": symbol.upper(),
            "side": side.upper(),
            "orderType": order_type.upper(),
            # Spec goi tinh "Quantity" la `volume`, KHONG phai `quantity`.
            "volume": quantity,
            "price": int(price),
            # Spec dinh nghia `refId`, KHONG co `requestId` trong toan spec.
            # Spec mo ta: "Unique random id identifying the order channel (H.<sequence>)".
            "refId": request_id,
        }
        return self._post(self._ORDER_PATHS["place_order"], payload)

    def place_derivative_condition_order(
        self,
        account_id: str,
        sub_account_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: int,
        price: float,
        trigger_price: float,
        request_id: str,
        *,
        callback_point: float | None = None,
        activation_price: float | None = None,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """
        POST /khronos/v1/order/condition/place

        Args:
            account_id: Custody code (105C format).
            sub_account_id: Tiểu khoản phái sinh.
            symbol: Mã hợp đồng phái sinh.
            side: 'BUY' hoặc 'SELL'.
            order_type: 'LO', 'MP'.
            quantity: Khối lượng (gửi lên là `volume`).
            price: Giá đặt lệnh.
            trigger_price: Giá kích hoạt (gửi lên là `soPrice`).
            request_id: ID idempotency key (gửi lên là `refId`).
            callback_point: Bước dồn trailing — **bắt buộc khi `order_type='TSO'`**.
            activation_price: Giá kích hoạt trailing — **bắt buộc khi `order_type='TSO'`**.
            dry_run: True (default) → không gửi HTTP.
        """
        if not account_id or not account_id.strip():
            raise BrokerValidationError(
                message="account_id không được để trống.",
                code="INVALID_ACCOUNT_ID",
            )
        if trigger_price < 0:
            raise BrokerValidationError(
                message="trigger_price phải >= 0.",
                code="INVALID_TRIGGER_PRICE",
            )
        return self._gated_place_derivative_condition_order(
            account_id, sub_account_id, symbol, side, order_type, quantity, price, trigger_price, request_id,
            dry_run=dry_run,
        )

    @write_gate
    def _gated_place_derivative_condition_order(
        self,
        account_id: str,
        sub_account_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: int,
        price: float,
        trigger_price: float,
        request_id: str,
        *,
        callback_point: float | None = None,
        activation_price: float | None = None,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        payload = {
            "accountId": account_id,
            "subAccountId": sub_account_id,
            "symbol": symbol.upper(),
            "side": side.upper(),
            "orderType": order_type.upper(),
            "volume": quantity,
            "price": int(price),
            "soPrice": int(trigger_price),
            "refId": request_id,
        }
        # `callbackPoint` va `activationPrice` DANH DUNG cho orderType = "TSO"
        # (trailing stop). Schema spec them chung vao `required`, nhung mo ta
        # lai ghi "only for orderType = TSO" — hai noi cua spec mau thuan nhau.
        # Ta chon theo mo ta: chi gui khi TSO. Gui gia tri 0 cho lenh SOL/SOU
        # co the lam TCBS tu choi ca don; bo qua thi an toanh hon.
        # Xem `docs/REPORT_TCBS_ROUND4.md` §Mau-thuan-noi-bo-cua-spec.
        if order_type.upper() == "TSO":
            if callback_point is None or activation_price is None:
                raise BrokerValidationError(
                    message=(
                        "order_type='TSO' (trailing stop) bat buoc can "
                        "callback_point va activation_price."
                    ),
                    code="MISSING_TRAILING_PARAMS",
                )
            payload["callbackPoint"] = callback_point
            payload["activationPrice"] = activation_price
        return self._post(self._ORDER_PATHS["place_condition_order"], payload)

    def change_derivative_order(
        self,
        account_id: str,
        sub_account_id: str,
        order_id: str,
        quantity: int,
        price: float,
        request_id: str,
        *,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """
        POST /khronos/v1/order/change

        Args:
            account_id: Custody code — **bắt buộc theo spec** (trước đây thiếu).
            sub_account_id: Tiểu khoản phái sinh — **bắt buộc theo spec**.
            order_id: `orderNo` lấy từ API đặt lệnh (gửi lên là `orderNo`).
            quantity: Khối lượng mới (gửi lên là `nvol`).
            price: Giá mới (gửi lên là `nprice`).
            request_id: ID idempotency key (gửi lên là `refId`).
            dry_run: True (default) → không gửi HTTP.
        """
        if not account_id or not account_id.strip():
            raise BrokerValidationError(
                message="account_id không được để trống.",
                code="INVALID_ACCOUNT_ID",
            )
        if not order_id or not order_id.strip():
            raise BrokerValidationError(
                message="order_id không được để trống.",
                code="INVALID_ORDER_ID",
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
                message="request_id là bắt buộc cho write methods.",
                code="MISSING_REQUEST_ID",
            )
        return self._gated_change_derivative_order(
            account_id, sub_account_id, order_id, quantity, price, request_id, dry_run=dry_run
        )

    @write_gate
    def _gated_change_derivative_order(
        self,
        account_id: str,
        sub_account_id: str,
        order_id: str,
        quantity: int,
        price: float,
        request_id: str,
        *,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        # Spec /khronos/v1/order/change co DUNG 6 field required. Ban cu gui 4
        # field, thieu `accountId` + `subAccountId` va sai ten 3 field con lai.
        payload = {
            "accountId": account_id,
            "subAccountId": sub_account_id,
            "orderNo": order_id,
            "nvol": quantity,
            "nprice": int(price),
            "refId": request_id,
        }
        return self._post(self._ORDER_PATHS["change_order"], payload)

    def change_derivative_condition_order(
        self,
        account_id: str,
        order_id: str,
        trigger_price: float,
        request_id: str,
        *,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """
        POST /khronos/v2/order/condition/change

        ⚠ **ĐỔI CHỮ KÝ (2026-10-10)** — bỏ 2 tham số `quantity` và `price`.
        Spec `/khronos/v2/order/condition/change` **không định nghĩa** 2 field đó:
        lệnh điều kiện chỉ sửa được **giá kích hoạt** (`soPrice`), không sửa được
        khối lượng hay giá. Bản cũ gửi 3 field thừa khiến TCBS có thể từ chối
        cả yêu cầu. Gọi bằng chữ ký cũ sẽ ném `TypeError` — cố ý, để lỗi nổi
        thay vì âm thầm gửi payload sai.

        Args:
            account_id: Custody code — **bắt buộc theo spec** (trước đây thiếu).
            order_id: `pk_orderNo` từ API tra sách lệnh (gửi lên là `pkOrderNo`).
            trigger_price: Giá kích hoạt mới (gửi lên là `soPrice`).
            request_id: ID idempotency key (gửi lên là `refId`).
            dry_run: True (default) → không gửi HTTP.
        """
        if not account_id or not account_id.strip():
            raise BrokerValidationError(
                message="account_id không được để trống.",
                code="INVALID_ACCOUNT_ID",
            )
        if not order_id or not order_id.strip():
            raise BrokerValidationError(
                message="order_id không được để trống.",
                code="INVALID_ORDER_ID",
            )
        if trigger_price < 0:
            raise BrokerValidationError(
                message="trigger_price phải >= 0.",
                code="INVALID_TRIGGER_PRICE",
            )
        return self._gated_change_derivative_condition_order(
            account_id, order_id, trigger_price, request_id, dry_run=dry_run
        )

    @write_gate
    def _gated_change_derivative_condition_order(
        self,
        account_id: str,
        order_id: str,
        trigger_price: float,
        request_id: str,
        *,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        # Spec chi co 4 field required: accountId, pkOrderNo, refId, soPrice.
        payload = {
            "accountId": account_id,
            "pkOrderNo": order_id,
            "soPrice": int(trigger_price),
            "refId": request_id,
        }
        return self._post(self._ORDER_PATHS["change_condition_order"], payload)

    def cancel_derivative_order(
        self,
        account_id: str,
        order_id: str,
        request_id: str,
        *,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """
        POST /khronos/v1/order/cancel

        Args:
            account_id: Custody code — **bắt buộc theo spec** (trước đây thiếu).
            order_id: `orderNo` từ API tra sách lệnh (gửi lên là `orderNo`).
            request_id: ID idempotency key (gửi lên là `refId`).
            dry_run: True (default) → không gửi HTTP.
        """
        if not account_id or not account_id.strip():
            raise BrokerValidationError(
                message="account_id không được để trống.",
                code="INVALID_ACCOUNT_ID",
            )
        if not order_id or not order_id.strip():
            raise BrokerValidationError(
                message="order_id không được để trống.",
                code="INVALID_ORDER_ID",
            )
        if not request_id or not request_id.strip():
            raise BrokerValidationError(
                message="request_id là bắt buộc cho write methods.",
                code="MISSING_REQUEST_ID",
            )
        return self._gated_cancel_derivative_order(account_id, order_id, request_id, dry_run=dry_run)

    @write_gate
    def _gated_cancel_derivative_order(
        self,
        account_id: str,
        order_id: str,
        request_id: str,
        *,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        # Spec /khronos/v1/order/cancel: required = accountId, orderNo.
        # `pin` (mô tả "Order channel (F)") KHÔNG phải mã PIN giao dịch và
        # cũng không có trong bản cũ — không gửi.
        payload = {
            "accountId": account_id,
            "orderNo": order_id,
            "refId": request_id,
        }
        return self._post(self._ORDER_PATHS["cancel_order"], payload)

