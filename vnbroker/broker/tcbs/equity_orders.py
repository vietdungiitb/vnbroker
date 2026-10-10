"""Tách write methods ra khỏi `equity.py` để giữ dưới ngân sách 800L (`CLAUDE.md:15`).

Lý do tách: sửa payload theo spec 2026-10-10 làm `equity.py` vượt 808 dòng và
`test_tcbs_legacy_removed.py::TestAc4FileSizeLimit` đỏ. Không nén bằng cách xoá
comment — cấu trúc sai thì mọi lần sửa sau lại vượt tiếp.

Cùng pattern với `derivative_orders.py`: mixin, không phải class mới, nên
`client._equity.place_order(...)` gọi y hệt trước.

LƯU Ý API (2026-10-10, chữ ký GIỮ NGUYÊN):
`place_order` vẫn nhận `pin_code` và `request_id` để không phá chữ ký cũ, nhưng
hai tham số đó **không còn được gửi lên TCBS** vì spec không định nghĩa chúng.
"""

from __future__ import annotations

from typing import Any

from vnbroker.broker.exceptions import BrokerValidationError
from vnbroker.broker.security.guards import write_gate
from vnbroker.broker.tcbs.account import _validate_account_no
from vnbroker.broker.tcbs._equity_common import _PATHS, _validate_order_input


class EquityWriteMixin:
    """3 write method cổa phiếu. Kế thừa bởi `TCBSEquityService`."""

    _config: Any
    _session: Any

    def _put(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError  # gán bởi `TCBSEquityService`

    def _post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError  # gán bởi `TCBSEquityService`
    # ── Write methods (dry_run=True default) ────────────────────────────────
    # Pattern: validation chạy TRƯỚC write_gate check.
    # Public method validate → delegate sang @write_gate internal method.

    def place_order(
        self,
        account_no: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: int,
        price: float,
        pin_code: str,
        request_id: str,
        *,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """
        POST /akhlys/v1/accounts/{accountNo}/orders

        Args:
            side: 'BUY' hoặc 'SELL' (được map sang 'NB'/'NS' theo spec).
            order_type: 'LO', 'ATO', 'ATC', 'MP', 'MTL', 'MOK', 'MAK', 'PLO'.
            price: Giá tính theo đơn vị đồng (float).
            pin_code: **KHÔNG CÒN ĐƯỢC GỬI** (deprecated 2026-10-10). Spec
                `/akhlys/v1/accounts/{accountNo}/orders` không định nghĩa
                `pinCode`. Vẫn nhận để không phá chữ ký cũ, nhưng giá trị bị bỏ
                qua hoàn toàn. Đừng truyền nữa.
            request_id: **KHÔNG CÒN ĐƯỢC GỬI** (deprecated 2026-10-10). Spec
                không định nghĩa `requestId` cho endpoint này. Vẫn được validate
                (idempotency key nội bộ) nhưng không gửi lên TCBS.
            dry_run: True (default) → không gửi HTTP, trả về dry_run dict.
                     False → gửi thực. Yêu cầu session.enable_write() trước.

        Returns:
            {'error': '0', 'message': '...', 'orderId': '...'} khi dry_run=False.
        """
        _validate_account_no(account_no)
        _validate_order_input(symbol, side, order_type, quantity, price, request_id)
        return self._gated_place_order(
            account_no, symbol, side, order_type, quantity, price, pin_code, request_id,
            dry_run=dry_run,
        )

    @write_gate
    def _gated_place_order(
        self,
        account_no: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: int,
        price: float,
        pin_code: str,
        request_id: str,
        *,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        exec_type = "NB" if side.upper() == "BUY" else "NS"
        # Spec /akhlys/v1/accounts/{accountNo}/orders co DUNG 5 field required,
        # khong co `pinCode` va khong co `requestId`. Hai field do da bi gui
        # o ban cu va bi ghi vao `docs/tcbs_body_baseline.json` (38 dong no).
        # Owner chot 2026-10-10: bo, vi khong co trong tai lieu chinh thuc.
        # Ghi them vao payload se lam TCBS tu choi ca don (error 422).
        payload = {
            "symbol": symbol.upper(),
            "execType": exec_type,
            "priceType": order_type.upper(),
            "quantity": quantity,
            "price": int(price),
        }
        url = self._config.base_url.rstrip("/") + _PATHS["place_order"].format(accountNo=account_no)
        return self._post(url, payload)

    def modify_order(
        self,
        account_no: str,
        order_id: str,
        quantity: int,
        price: float,
        request_id: str,
        *,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """
        PUT /akhlys/v1/accounts/{accountNo}/orders/{orderId}

        Args:
            price: Giá mới (float, đơn vị đồng).
            quantity: Khối lượng mới.
            request_id: ID idempotency key (bắt buộc theo TCBS spec).
        """
        _validate_account_no(account_no)
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
                message="request_id là bắt buộc cho write methods (idempotency key).",
                code="MISSING_REQUEST_ID",
            )
        return self._gated_modify_order(account_no, order_id, quantity, price, request_id, dry_run=dry_run)

    @write_gate
    def _gated_modify_order(
        self,
        account_no: str,
        order_id: str,
        quantity: int,
        price: float,
        request_id: str,
        *,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        # Spec chi dinh nghia 2 field: `price` va `quantity`.
        # `requestId` khong ton tai trong spec -> da go khoi payload.
        payload = {
            "quantity": quantity,
            "price": int(price),
        }
        url = self._config.base_url.rstrip("/") + _PATHS["modify_order"].format(
            accountNo=account_no, orderId=order_id
        )
        return self._put(url, payload)

    def cancel_order(
        self,
        account_no: str,
        order_id: str,
        request_id: str,
        *,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """
        PUT /akhlys/v1/accounts/{accountNo}/cancel-orders

        Body: {ordersList: [{orderID: order_id}], requestId: request_id}
        Hỗ trợ huỷ nhiều lệnh: truyền list order_id qua cancel_orders().
        """
        _validate_account_no(account_no)
        if not order_id or not order_id.strip():
            raise BrokerValidationError(
                message="order_id không được để trống.",
                code="INVALID_ORDER_ID",
            )
        if not request_id or not request_id.strip():
            raise BrokerValidationError(
                message="request_id là bắt buộc cho write methods (idempotency key).",
                code="MISSING_REQUEST_ID",
            )
        return self._gated_cancel_order(account_no, [order_id], request_id, dry_run=dry_run)

    def cancel_orders(
        self,
        account_no: str,
        order_ids: list[str],
        request_id: str,
        *,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """
        PUT /akhlys/v1/accounts/{accountNo}/cancel-orders

        Huỷ nhiều lệnh cùng lúc.
        """
        _validate_account_no(account_no)
        if not order_ids:
            raise BrokerValidationError(
                message="order_ids không được rỗng.",
                code="INVALID_ORDER_ID",
            )
        if not request_id or not request_id.strip():
            raise BrokerValidationError(
                message="request_id là bắt buộc cho write methods (idempotency key).",
                code="MISSING_REQUEST_ID",
            )
        return self._gated_cancel_order(account_no, order_ids, request_id, dry_run=dry_run)

    @write_gate
    def _gated_cancel_order(
        self,
        account_no: str,
        order_ids: list[str],
        request_id: str,
        *,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        # Spec chi dinh nghia 1 field: `ordersList`. `requestId` khong co
        # trong spec -> da go khoi payload.
        payload = {
            "ordersList": [{"orderID": oid} for oid in order_ids],
        }
        url = self._config.base_url.rstrip("/") + _PATHS["cancel_orders"].format(accountNo=account_no)
        return self._put(url, payload)

