"""
vnbroker.broker.ssi.fco — SSIFCOService: 7 lệnh điều kiện + query vòng đời (ký RSA).

  POST   /api/v3/trading/fco/order → place_fco_{gtd,stop,stop_limit,
                                        trailing_stop,trailing_stop_limit,
                                        oco,bull_bear}
  DELETE /api/v3/trading/fco/order → cancel_fco
  GET    /api/v3/trading/fco/list  → get_fco_by_{account_no,symbol,status,date,id}
  GET    /api/v3/trading/fco/orderbook → get_fco_order_book

Wire rules (đối chiếu models/fco.py):
  - STOP thuần ép price="MTL", priceSlip=0; GTD giá Enum → slip=0.
  - OCO có field cứng price="MP", priceSlip=0, stopPrice/activePrice/
    trailingAmount=0, operator/code="".
  - Date place "YYYY/MM/DD HH:MM:SS"; query from/to "YYYY/MM/DD".
  - Mọi write @write_gate + dry_run=True mặc định.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from vnbroker.broker.exceptions import BrokerValidationError
from vnbroker.broker.security.credentials import SSICredentialConfig
from vnbroker.broker.security.guards import write_gate
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.ssi import _paths
from vnbroker.broker.ssi._enums import (
    FCOOperator,
    FCOStatus,
    FCOType,
    OrderSide,
    OrderStatus,
    OrderType,
    parse_side,
    safe_parse,
)
from vnbroker.broker.ssi._transport import SSIHttpClient
from vnbroker.broker.ssi._utils import (
    require_non_empty,
    require_positive,
    to_float,
    to_int,
    validate_ssi_date,
    validate_ssi_datetime,
)

_logger = logging.getLogger("vnbroker.broker.ssi.fco")

_FCO_LIST_COLUMNS = [
    "fco_id",
    "account_no",
    "symbol",
    "type",
    "side",
    "quantity",
    "price",
    "price_slip",
    "from_date",
    "to_date",
    "matched_quantity",
    "status",
    "is_place_order",
]

_FCO_BOOK_COLUMNS = [
    "fco_id",
    "order_id",
    "account_no",
    "symbol",
    "side",
    "order_type",
    "quantity",
    "matched_quantity",
    "os_quantity",
    "avg_price",
    "price",
    "status",
    "is_main_order",
    "is_attached_order",
    "created_time",
    "updated_time",
]


class SSIFCOService:
    """Lệnh điều kiện FCO cho SSI broker."""

    def __init__(
        self,
        config: SSICredentialConfig,
        session: BrokerSession,
        transport: SSIHttpClient,
    ) -> None:
        self._config = config
        self._session = session
        self._transport = transport

    # ── Place (7 loại) ───────────────────────────────────────────────────

    def place_fco_gtd(
        self,
        account_no: str,
        symbol: str,
        side: str,
        quantity: int,
        price: Union[int, float, str],
        price_slip: Union[int, float] = 0,
        from_date: str = "",
        to_date: str = "",
        *,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Lệnh GTD. price số → slip giữ; price Enum-string (MTL/MP/…) → slip=0."""
        account_no, symbol, parsed_side = _common_place_args(
            account_no, symbol, side, quantity
        )
        from_date = validate_ssi_datetime(from_date, "from_date")
        to_date = validate_ssi_datetime(to_date, "to_date")
        price_str: str
        slip: Any
        if isinstance(price, (int, float)) and not isinstance(price, bool):
            require_positive(price, "price")
            price_str, slip = f"{price}", price_slip
        else:
            price_str, slip = _order_type_str(price, "price"), 0
        payload = {
            "accountNo": account_no,
            "type": FCOType.GTD.value,
            "symbol": symbol,
            "side": parsed_side.value,
            "price": price_str,
            "priceSlip": slip,
            "quantity": quantity,
            "from": from_date,
            "to": to_date,
            "deviceId": self._config.device_id,
            "userAgent": _user_agent(),
        }
        return self._gated_fco_post(payload, dry_run=dry_run)

    def place_fco_stop(
        self,
        account_no: str,
        symbol: str,
        side: str,
        quantity: int,
        stop_price: Union[int, float],
        operator: str,
        from_date: str = "",
        to_date: str = "",
        *,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Lệnh Stop (ép price=MTL, slip=0)."""
        payload = self._stop_payload(
            account_no,
            symbol,
            side,
            quantity,
            stop_price,
            operator,
            None,
            None,
            FCOType.STOP,
            from_date,
            to_date,
        )
        return self._gated_fco_post(payload, dry_run=dry_run)

    def place_fco_stop_limit(
        self,
        account_no: str,
        symbol: str,
        side: str,
        quantity: int,
        price: Union[int, float],
        price_slip: Union[int, float],
        stop_price: Union[int, float],
        operator: str,
        from_date: str = "",
        to_date: str = "",
        *,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Lệnh Stop-Limit."""
        payload = self._stop_payload(
            account_no,
            symbol,
            side,
            quantity,
            stop_price,
            operator,
            price,
            price_slip,
            FCOType.STOP_LIMIT,
            from_date,
            to_date,
        )
        return self._gated_fco_post(payload, dry_run=dry_run)

    def place_fco_trailing_stop(
        self,
        account_no: str,
        symbol: str,
        side: str,
        quantity: int,
        active_price: Union[int, float],
        trailing_amount: Union[int, float],
        from_date: str = "",
        to_date: str = "",
        *,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Trailing Stop (ép price=MTL, slip=0)."""
        payload = self._trailing_payload(
            account_no,
            symbol,
            side,
            quantity,
            active_price,
            trailing_amount,
            None,
            FCOType.TRAILING_STOP,
            from_date,
            to_date,
        )
        return self._gated_fco_post(payload, dry_run=dry_run)

    def place_fco_trailing_stop_limit(
        self,
        account_no: str,
        symbol: str,
        side: str,
        quantity: int,
        active_price: Union[int, float],
        trailing_amount: Union[int, float],
        price_slip: Union[int, float],
        from_date: str = "",
        to_date: str = "",
        *,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Trailing Stop-Limit."""
        payload = self._trailing_payload(
            account_no,
            symbol,
            side,
            quantity,
            active_price,
            trailing_amount,
            price_slip,
            FCOType.TRAILING_STOP_LIMIT,
            from_date,
            to_date,
        )
        return self._gated_fco_post(payload, dry_run=dry_run)

    def place_fco_oco(
        self,
        account_no: str,
        symbol: str,
        side: str,
        quantity: int,
        tp_active_price: Union[int, float],
        sl_active_price: Union[int, float],
        tp_price: Union[int, float, str] = "MP",
        sl_price: Union[int, float, str] = "MP",
        tp_slip: Union[int, float] = 0,
        sl_slip: Union[int, float] = 0,
        from_date: str = "",
        to_date: str = "",
        *,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Lệnh OCO (kèm field cứng theo wire-spec)."""
        account_no, symbol, parsed_side = _common_place_args(
            account_no, symbol, side, quantity
        )
        from_date = validate_ssi_datetime(from_date, "from_date")
        to_date = validate_ssi_datetime(to_date, "to_date")
        payload = {
            "accountNo": account_no,
            "type": FCOType.OCO.value,
            "symbol": symbol,
            "side": parsed_side.value,
            "quantity": quantity,
            "from": from_date,
            "to": to_date,
            "tpActivePrice": _positive_number(tp_active_price, "tp_active_price"),
            "slActivePrice": _positive_number(sl_active_price, "sl_active_price"),
            "tpPrice": _price_str(tp_price),
            "slPrice": _price_str(sl_price),
            "tpSlip": tp_slip,
            "slSlip": sl_slip,
            "userAgent": _user_agent(),
            "deviceId": self._config.device_id,
            "price": "MP",
            "priceSlip": 0,
            "stopPrice": 0,
            "activePrice": 0,
            "trailingAmount": 0,
            "operator": "",
            "code": "",
        }
        return self._gated_fco_post(payload, dry_run=dry_run)

    def place_fco_bull_bear(
        self,
        account_no: str,
        symbol: str,
        side: str,
        quantity: int,
        price: Union[int, float, str],
        price_slip: Union[int, float],
        tp_active_price: Union[int, float],
        sl_active_price: Union[int, float],
        tp_price: Union[int, float, str],
        sl_price: Union[int, float, str],
        tp_slip: Union[int, float],
        sl_slip: Union[int, float],
        from_date: str = "",
        to_date: str = "",
        *,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Lệnh Bull-Bear."""
        account_no, symbol, parsed_side = _common_place_args(
            account_no, symbol, side, quantity
        )
        from_date = validate_ssi_datetime(from_date, "from_date")
        to_date = validate_ssi_datetime(to_date, "to_date")
        if isinstance(price, (int, float)) and not isinstance(price, bool):
            price_str, slip = f"{price}", price_slip
        else:
            price_str, slip = _order_type_str(price, "price"), 0
        tp_str, tp_sl = _slip_price(tp_price, tp_slip)
        sl_str, sl_sl = _slip_price(sl_price, sl_slip)
        payload = {
            "accountNo": account_no,
            "type": FCOType.BULL_BEAR.value,
            "symbol": symbol,
            "side": parsed_side.value,
            "quantity": quantity,
            "price": price_str,
            "priceSlip": slip,
            "from": from_date,
            "to": to_date,
            "tpActivePrice": _positive_number(tp_active_price, "tp_active_price"),
            "slActivePrice": _positive_number(sl_active_price, "sl_active_price"),
            "tpPrice": tp_str,
            "slPrice": sl_str,
            "tpSlip": tp_sl,
            "slSlip": sl_sl,
            "userAgent": _user_agent(),
            "deviceId": self._config.device_id,
        }
        return self._gated_fco_post(payload, dry_run=dry_run)

    @write_gate
    def _gated_fco_post(
        self, payload: Dict[str, Any], *, dry_run: bool = True
    ) -> Dict[str, Any]:
        body = json.dumps(payload)
        data = self._transport.request_signed(
            "POST", _paths.EP_TRADING_FCO_ORDER, body, self._config.private_key
        )
        rec = data if isinstance(data, dict) else {}
        return {"fco_id": str(rec.get("fcoId", ""))}

    # ── Cancel ───────────────────────────────────────────────────────────

    def cancel_fco(self, fco_id: str, *, dry_run: bool = True) -> Dict[str, Any]:
        """Hủy FCO theo fco_id. dry_run=True mặc định."""
        fco_id = require_non_empty(fco_id, "fcoId")
        return self._gated_fco_cancel(fco_id, dry_run=dry_run)

    @write_gate
    def _gated_fco_cancel(self, fco_id: str, *, dry_run: bool = True) -> Dict[str, Any]:
        body = json.dumps({"fcoId": fco_id})
        data = self._transport.request_signed(
            "DELETE", _paths.EP_TRADING_FCO_ORDER, body, self._config.private_key
        )
        rec = data if isinstance(data, dict) else {}
        return {"fco_id": str(rec.get("fcoId", fco_id))}

    # ── Query ────────────────────────────────────────────────────────────

    def get_fco_by_account_no(
        self,
        account_no: str,
        page_index: int = 1,
        page_size: int = 10,
        raw: bool = False,
    ) -> Union[pd.DataFrame, List[Any]]:
        """Toàn bộ FCO của tài khoản (phân trang)."""
        return self._query_list(
            {"accountNo": require_non_empty(account_no, "accountNo")},
            page_index,
            page_size,
            raw,
        )

    def get_fco_by_symbol(
        self,
        account_no: str,
        symbol: str,
        page_index: int = 1,
        page_size: int = 10,
        raw: bool = False,
    ) -> Union[pd.DataFrame, List[Any]]:
        """FCO theo mã."""
        return self._query_list(
            {
                "accountNo": require_non_empty(account_no, "accountNo"),
                "symbol": require_non_empty(symbol, "symbol").upper(),
            },
            page_index,
            page_size,
            raw,
        )

    def get_fco_by_status(
        self,
        account_no: str,
        process_status: str,
        page_index: int = 1,
        page_size: int = 10,
        raw: bool = False,
    ) -> Union[pd.DataFrame, List[Any]]:
        """FCO theo trạng thái (INIT/WAIT/TRI/TRIT/TER/FIS/WC/EXP/ERR)."""
        status = safe_parse(FCOStatus, (process_status or "").strip().upper())
        if status is None:
            raise BrokerValidationError(
                message=f"process_status không hỗ trợ: {process_status!r}.",
                code="INVALID_FCO_STATUS",
                http_status=400,
            )
        return self._query_list(
            {
                "accountNo": require_non_empty(account_no, "accountNo"),
                "processStatus": status.value,
            },
            page_index,
            page_size,
            raw,
        )

    def get_fco_by_date(
        self,
        account_no: str,
        from_date: str,
        to_date: str,
        page_index: int = 1,
        page_size: int = 10,
        raw: bool = False,
    ) -> Union[pd.DataFrame, List[Any]]:
        """FCO theo khoảng ngày YYYY/MM/DD."""
        return self._query_list(
            {
                "accountNo": require_non_empty(account_no, "accountNo"),
                "from": validate_ssi_date(from_date, "from_date"),
                "to": validate_ssi_date(to_date, "to_date"),
            },
            page_index,
            page_size,
            raw,
        )

    def get_fco_by_id(self, account_no: str, fco_id: str) -> Optional[Dict[str, Any]]:
        """1 FCO theo ID (dict snake_case) hoặc None."""
        rows = self._query_list(
            {
                "accountNo": require_non_empty(account_no, "accountNo"),
                "fcoId": require_non_empty(fco_id, "fcoId"),
            },
            1,
            10,
            raw=True,
        )
        assert isinstance(rows, list)
        if not rows:
            return None
        rec = rows[0]
        return _fco_row(rec) if isinstance(rec, dict) else None

    def get_fco_order_book(
        self,
        fco_id: str,
        page_index: int = 1,
        page_size: int = 10,
        raw: bool = False,
    ) -> Union[pd.DataFrame, List[Any]]:
        """Nhật ký khớp của 1 FCO."""
        _ = self._session.token
        data = self._transport.request(
            "GET",
            _paths.EP_TRADING_FCO_ORDER_BOOK,
            params={
                "fcoId": require_non_empty(fco_id, "fcoId"),
                "pageIndex": _page(page_index),
                "pageSize": _page_size(page_size),
            },
        )
        records = _extract_list(data)
        if raw:
            return records
        if not records:
            return pd.DataFrame(columns=_FCO_BOOK_COLUMNS)
        df = pd.DataFrame([_book_row(r) for r in records], columns=_FCO_BOOK_COLUMNS)
        for col in ("quantity", "matched_quantity", "os_quantity", "avg_price"):
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        for col in ("side", "order_type", "status"):
            df[col] = df[col].astype("category")
        return df

    def _query_list(
        self, base: Dict[str, Any], page_index: int, page_size: int, raw: bool
    ) -> Union[pd.DataFrame, List[Any]]:
        _ = self._session.token
        params = dict(base)
        params["pageIndex"] = _page(page_index)
        params["pageSize"] = _page_size(page_size)
        data = self._transport.request("GET", _paths.EP_TRADING_FCO_LIST, params=params)
        records = _extract_list(data)
        if raw:
            return records
        if not records:
            return pd.DataFrame(columns=_FCO_LIST_COLUMNS)
        df = pd.DataFrame([_fco_row(r) for r in records], columns=_FCO_LIST_COLUMNS)
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").astype("Int64")
        df["matched_quantity"] = pd.to_numeric(
            df["matched_quantity"], errors="coerce"
        ).astype("Int64")
        for col in ("type", "side", "status"):
            df[col] = df[col].astype("category")
        return df

    # ── Builders ─────────────────────────────────────────────────────────

    def _stop_payload(
        self,
        account_no: str,
        symbol: str,
        side: str,
        quantity: int,
        stop_price: Union[int, float],
        operator: str,
        price: Optional[Union[int, float]],
        price_slip: Optional[Union[int, float]],
        fco_type: FCOType,
        from_date: str,
        to_date: str,
    ) -> Dict[str, Any]:
        account_no, symbol, parsed_side = _common_place_args(
            account_no, symbol, side, quantity
        )
        from_date = validate_ssi_datetime(from_date, "from_date")
        to_date = validate_ssi_datetime(to_date, "to_date")
        op = safe_parse(FCOOperator, (operator or "").strip().lower())
        if op is None:
            raise BrokerValidationError(
                message=f"operator không hỗ trợ: {operator!r}.",
                code="INVALID_FCO_OPERATOR",
                http_status=400,
            )
        price_str = OrderType.MTL.value
        slip: Any = 0
        if fco_type != FCOType.STOP:
            assert price is not None and price_slip is not None
            price_str = f"{_positive_number(price, 'price')}"
            slip = price_slip
        return {
            "accountNo": account_no,
            "type": fco_type.value,
            "symbol": symbol,
            "side": parsed_side.value,
            "price": price_str,
            "priceSlip": slip,
            "quantity": quantity,
            "from": from_date,
            "to": to_date,
            "stopPrice": _positive_number(stop_price, "stop_price"),
            "operator": op.value,
            "deviceId": self._config.device_id,
            "userAgent": _user_agent(),
        }

    def _trailing_payload(
        self,
        account_no: str,
        symbol: str,
        side: str,
        quantity: int,
        active_price: Union[int, float],
        trailing_amount: Union[int, float],
        price_slip: Optional[Union[int, float]],
        fco_type: FCOType,
        from_date: str,
        to_date: str,
    ) -> Dict[str, Any]:
        account_no, symbol, parsed_side = _common_place_args(
            account_no, symbol, side, quantity
        )
        from_date = validate_ssi_datetime(from_date, "from_date")
        to_date = validate_ssi_datetime(to_date, "to_date")
        payload: Dict[str, Any] = {
            "accountNo": account_no,
            "type": fco_type.value,
            "symbol": symbol,
            "side": parsed_side.value,
            "quantity": quantity,
            "from": from_date,
            "to": to_date,
            "activePrice": _positive_number(active_price, "active_price"),
            "trailingAmount": _positive_number(trailing_amount, "trailing_amount"),
            "userAgent": _user_agent(),
            "deviceId": self._config.device_id,
        }
        if fco_type == FCOType.TRAILING_STOP:
            payload["price"] = OrderType.MTL.value
            payload["priceSlip"] = 0
        else:
            assert price_slip is not None
            payload["priceSlip"] = price_slip
        return payload


# ── Helpers ──────────────────────────────────────────────────────────────


def _user_agent() -> str:
    try:
        from importlib.metadata import version

        return f"vnbroker/{version('vnbroker')}"
    except Exception:
        return "vnbroker/unknown"


def _common_place_args(
    account_no: str, symbol: str, side: str, quantity: int
) -> tuple[str, str, OrderSide]:
    account_no = require_non_empty(account_no, "accountNo")
    symbol = require_non_empty(symbol, "symbol").upper()
    parsed_side = parse_side(side)
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        raise BrokerValidationError(
            message=f"quantity phải là int > 0. Nhận: {quantity!r}",
            code="INVALID_QUANTITY",
            http_status=400,
        )
    return account_no, symbol, parsed_side


def _order_type_str(value: Union[int, float, str], name: str) -> str:
    if isinstance(value, str):
        parsed = safe_parse(OrderType, value.strip().upper())
        if parsed is None:
            raise BrokerValidationError(
                message=f"{name} Enum-string không hỗ trợ: {value!r}.",
                code="INVALID_ORDER_TYPE",
                http_status=400,
            )
        return parsed.value
    raise BrokerValidationError(
        message=f"{name} phải là số hoặc Enum-string. Nhận: {value!r}",
        code="INVALID_PRICE",
        http_status=400,
    )


def _positive_number(value: Union[int, float], name: str) -> Union[int, float]:
    require_positive(value, name)
    return value


def _price_str(value: Union[int, float, str]) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value}"
    return _order_type_str(value, "price")


def _slip_price(
    value: Union[int, float, str], slip: Union[int, float]
) -> tuple[str, Any]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value}", slip
    return _order_type_str(value, "price"), 0


def _page(value: int) -> int:
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value >= 1
        else 1
    )


def _page_size(value: int) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 100:
        return value
    return 10


def _extract_list(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        for key in ("data", "fcoList", "fco_list", "orderBook", "order_book"):
            records = data.get(key)
            if isinstance(records, list):
                return [r for r in records if isinstance(r, dict)]
    return []


def _fco_row(record: Dict[str, Any]) -> Dict[str, Any]:
    fco_type = safe_parse(FCOType, record.get("type"))
    status = safe_parse(FCOStatus, record.get("status"))
    try:
        side = parse_side(str(record.get("side", ""))).name
    except BrokerValidationError:
        side = str(record.get("side", ""))
    return {
        "fco_id": str(record.get("fcoId", "")),
        "account_no": str(record.get("accountNo", "")),
        "symbol": str(record.get("symbol", "")),
        "type": fco_type.name if fco_type else str(record.get("type", "")),
        "side": side,
        "quantity": to_int(record.get("quantity")),
        "price": str(record.get("price", "")),
        "price_slip": str(record.get("priceSlip", "")),
        "from_date": str(record.get("from", "")),
        "to_date": str(record.get("to", "")),
        "matched_quantity": to_int(record.get("matchedQuantity")),
        "status": status.name if status else str(record.get("status", "")),
        "is_place_order": bool(record.get("isPlaceOrder", False)),
    }


def _book_row(record: Dict[str, Any]) -> Dict[str, Any]:
    try:
        side = parse_side(str(record.get("side", ""))).name
    except BrokerValidationError:
        side = str(record.get("side", ""))
    order_type = safe_parse(OrderType, record.get("orderType"))
    status = safe_parse(OrderStatus, record.get("status"))
    return {
        "fco_id": str(record.get("fcoId", "")),
        "order_id": str(record.get("orderId", "")),
        "account_no": str(record.get("accountNo", "")),
        "symbol": str(record.get("symbol", "")),
        "side": side,
        "order_type": order_type.name
        if order_type
        else str(record.get("orderType", "")),
        "quantity": to_float(record.get("quantity")),
        "matched_quantity": to_float(record.get("matchedQuantity")),
        "os_quantity": to_float(record.get("osQuantity")),
        "avg_price": to_float(record.get("avgPrice")),
        "price": str(record.get("price", "")),
        "status": status.name if status else str(record.get("status", "")),
        "is_main_order": bool(record.get("isMainOrder", False)),
        "is_attached_order": bool(record.get("isAttachedOrder", False)),
        "created_time": str(record.get("createdTime", "")),
        "updated_time": str(record.get("updatedTime", "")),
    }
