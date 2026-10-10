"""
vnbroker.broker.tcbs.derivatives — TCBSDerivativesService: read-only derivatives.

READ endpoints (TCBS iFlash Open API v1.0.0 — /khronos service):
  GET /khronos/v1/account/portfolio/status?accountId=&subAccountId=   → get_positions()
  GET /khronos/v1/order/in-day?accountId=&symbol=&pageNo=&pageSize=   → get_orders()
  GET /khronos/v1/account/status?accountId=&subAccountId=&getType=    → get_cash()

CRITICAL: Phái sinh dùng accountId (custody code 105C format) không phải accountNo.
          Ví dụ: accountId = '105C334455'

RULE: Chỉ read methods. Write paths sẽ bổ sung sau khi có spec đầy đủ từ TCBS.
"""
from __future__ import annotations

import logging
from typing import Optional, Union

import pandas as pd
import requests

from vnbroker.broker.exceptions import (
    BrokerAuthError,
    BrokerNetworkError,
    BrokerPermissionError,
    BrokerRateLimitError,
    BrokerSessionExpiredError,
    BrokerValidationError,
)
from vnbroker.broker.security.credentials import TCBSCredentialConfig
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.tcbs.derivative_orders import DerivativeWriteMixin
from vnbroker.broker.tcbs.equity import _ensure_columns

_logger = logging.getLogger("vnbroker.broker.tcbs.derivatives")

_PATHS = {
    "positions": "/khronos/v1/account/portfolio/status",
    "orders": "/khronos/v1/order/in-day",
    "cash": "/khronos/v1/account/status",
    # Phase 4 additional endpoints
    "closed_positions": "/khronos/v1/account/portfolio/position/close",
    "condition_orders": "/khronos/v1/order/condition/detail",
    "place_order": "/khronos/v1/order/place",
    "place_condition_order": "/khronos/v1/order/condition/place",
    "change_order": "/khronos/v1/order/change",
    "change_condition_order": "/khronos/v2/order/condition/change",
    "cancel_order": "/khronos/v1/order/cancel",
}

# /khronos/v1/account/portfolio/status response fields
_POSITION_COLUMNS = {
    "symbol": "symbol",
    "side": "side",             # LONG / SHORT
    "openQtty": "open_quantity",
    "openPrice": "open_price",
    "marketPrice": "market_price",
    "unrealizedPnl": "unrealized_pnl",
    "margin": "margin",
    "tradingValue": "trading_value",
    "accountId": "account_id",
    "subAccountId": "sub_account_id",
}

# /khronos/v1/order/in-day response fields
_DERIV_ORDER_COLUMNS = {
    "orderId": "order_id",
    "symbol": "symbol",
    "side": "side",             # BUY / SELL
    "orderType": "order_type",
    "orderQtty": "quantity",
    "orderPrice": "price",
    "matchedQtty": "filled_quantity",
    "status": "status",
    "orderDate": "order_date",
    "orderTime": "order_time",
    "accountId": "account_id",
}

# /khronos/v1/account/status response fields
_CASH_COLUMNS = {
    "accountId": "account_id",
    "subAccountId": "sub_account_id",
    "balance": "balance",
    "availableBalance": "available_balance",
    "margin": "margin",
    "floatingPnl": "floating_pnl",
    "nav": "nav",
}


class TCBSDerivativesService(DerivativeWriteMixin):
    # Mixin doc path write tu day (tranh import vong).
    _ORDER_PATHS = _PATHS
    """Read-only derivatives service: vị thế phái sinh, lệnh phái sinh."""

    def __init__(
        self,
        config: TCBSCredentialConfig,
        session: BrokerSession,
    ) -> None:
        self._config = config
        self._session = session

    def get_positions(
        self,
        account_id: str,
        sub_account_id: str = "",
        raw: bool = False,
    ) -> Union[pd.DataFrame, list]:
        """
        GET /khronos/v1/account/portfolio/status?accountId=&subAccountId=

        Args:
            account_id: Custody code (105C format), ví dụ '105C334455'.
            sub_account_id: Tiểu khoản phái sinh (tùy chọn).

        DataFrame columns (raw=False):
            account_id, sub_account_id, symbol (str), side (category: LONG/SHORT),
            open_quantity (Int64), open_price (float64),
            market_price (float64), unrealized_pnl (float64),
            margin (float64), trading_value (float64)
        """
        if not account_id or not account_id.strip():
            raise BrokerValidationError(
                message="account_id (custody code) không được để trống.",
                code="INVALID_ACCOUNT_ID",
            )
        params: dict = {"accountId": account_id}
        if sub_account_id:
            params["subAccountId"] = sub_account_id

        data = self._get(_PATHS["positions"], params=params)

        if raw:
            return data

        records = data if isinstance(data, list) else ([data] if data else [])
        if not records:
            return pd.DataFrame(columns=list(_POSITION_COLUMNS.values()))

        df = pd.DataFrame(records)
        df = df.rename(columns=_POSITION_COLUMNS)
        df = _ensure_columns(df, _POSITION_COLUMNS.values())
        if "side" in df.columns:
            df["side"] = df["side"].astype("category")
        for col in ("open_price", "market_price", "unrealized_pnl", "margin", "trading_value"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        if "open_quantity" in df.columns:
            df["open_quantity"] = pd.to_numeric(df["open_quantity"], errors="coerce").astype("Int64")
        return df

    def get_orders(
        self,
        account_id: str,
        symbol: Optional[str] = None,
        page_no: int = 0,
        page_size: int = 50,
        size: Optional[int] = None,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /khronos/v1/order/in-day?accountId=&symbol=&pageNo=&pageSize=

        Args:
            account_id: Custody code (105C format).
            symbol: Lọc theo mã cụ thể (tùy chọn).
            size: Alias cho page_size (để tương thích với test).

        DataFrame columns (raw=False): account_id, order_id, symbol, side (category),
            order_type (category), quantity (Int64), price (float64),
            filled_quantity (Int64), status (category),
            order_date (str), order_time (str)
        """
        if not account_id or not account_id.strip():
            raise BrokerValidationError(
                message="account_id (custody code) không được để trống.",
                code="INVALID_ACCOUNT_ID",
            )
        # Support both page_size and size params
        effective_page_size = size if size is not None else page_size
        params: dict = {"accountId": account_id, "pageNo": page_no, "pageSize": effective_page_size}
        if symbol:
            params["symbol"] = symbol.upper()

        data = self._get(_PATHS["orders"], params=params)

        if raw:
            return data

        records = data.get("data", []) if isinstance(data, dict) else data
        if not records:
            return pd.DataFrame(columns=list(_DERIV_ORDER_COLUMNS.values()))

        df = pd.DataFrame(records)
        df = df.rename(columns=_DERIV_ORDER_COLUMNS)
        df = _ensure_columns(df, _DERIV_ORDER_COLUMNS.values())
        for col in ("side", "order_type", "status"):
            if col in df.columns:
                df[col] = df[col].astype("category")
        for col in ("price",):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        for col in ("quantity", "filled_quantity"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        return df

    def get_cash(
        self,
        account_id: str,
        sub_account_id: str = "",
        get_type: str = "",
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /khronos/v1/account/status?accountId=&subAccountId=&getType=

        Trả về thông tin tiền mặt phái sinh: số dư, tiền khả dụng, nặp/rút ký quỹ.

        Args:
            account_id: Custody code (105C format).
            sub_account_id: Tiểu khoản phái sinh (tùy chọn).
            get_type: Loại truy vấn (tùy thuộc API TCBS, có thể để rỗng).

        DataFrame columns (raw=False):
            account_id, sub_account_id, balance (float64),
            available_balance (float64), margin (float64),
            floating_pnl (float64), nav (float64)
        """
        if not account_id or not account_id.strip():
            raise BrokerValidationError(
                message="account_id (custody code) không được để trống.",
                code="INVALID_ACCOUNT_ID",
            )
        params: dict = {"accountId": account_id}
        if sub_account_id:
            params["subAccountId"] = sub_account_id
        if get_type:
            params["getType"] = get_type

        data = self._get(_PATHS["cash"], params=params)

        if raw:
            return data

        record = data if isinstance(data, dict) else (data[0] if data else {})
        if not record:
            return pd.DataFrame(columns=list(_CASH_COLUMNS.values()))

        df = pd.DataFrame([record])
        df = df.rename(columns=_CASH_COLUMNS)
        df = _ensure_columns(df, _CASH_COLUMNS.values())
        for col in ("balance", "available_balance", "margin", "floating_pnl", "nav"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        return df

    def get_closed_positions(
        self,
        account_id: str,
        sub_account_id: str,
        symbol: str = "",
        page_no: int = 1,
        page_size: int = 20,
        raw: bool = False,
    ) -> Union[pd.DataFrame, list]:
        """
        GET /khronos/v1/account/portfolio/position/close

        Args:
            account_id: Custody code (105C format).
            sub_account_id: Tiểu khoản phái sinh.
            symbol: Lọc theo mã (tùy chọn).
            page_no: Trang (1-based).
            page_size: Số lượng mỗi trang.
            raw: True → trả về list nguyên gốc.

        Returns:
            DataFrame columns (raw=False):
                symbol, side (category), close_quantity (Int64),
                close_price (float64), open_price (float64),
                realized_pnl (float64), close_date (str)
        """
        if not account_id or not account_id.strip():
            raise BrokerValidationError(
                message="account_id (custody code) không được để trống.",
                code="INVALID_ACCOUNT_ID",
            )
        params: dict = {
            "accountId": account_id,
            "subAccountId": sub_account_id,
            "pageNo": page_no,
            "pageSize": page_size,
        }
        if symbol:
            params["symbol"] = symbol.upper()

        data = self._get(_PATHS["closed_positions"], params=params)

        if raw:
            return data

        records = data.get("data", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        if not records:
            return pd.DataFrame(columns=[
                "symbol", "side", "close_quantity", "close_price",
                "open_price", "realized_pnl", "close_date"
            ])

        df = pd.DataFrame(records)
        if "close_quantity" in df.columns:
            df["close_quantity"] = pd.to_numeric(df["close_quantity"], errors="coerce").astype("Int64")
        for col in ("close_price", "open_price", "realized_pnl"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        if "side" in df.columns:
            df["side"] = df["side"].astype("category")
        return df

    def get_condition_orders(
        self,
        account_id: str,
        sub_account_id: str,
        order_status: str = "0",
        order_type: str = "ALL,ALL",
        symbol: str = "",
        page_no: int = 1,
        page_size: int = 25,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /khronos/v1/order/condition/detail

        Args:
            account_id: Custody code (105C format).
            sub_account_id: Tiểu khoản phái sinh.
            order_status: Trạng thái lệnh (0=All).
            order_type: Loại lệnh (ALL,ALL).
            symbol: Lọc theo mã (tùy chọn).
            page_no: Trang (1-based).
            page_size: Số lượng mỗi trang.
            raw: True → trả về dict nguyên gốc.

        Returns:
            DataFrame columns (raw=False):
                order_id, symbol, side (category), order_type (category),
                quantity (Int64), price (float64), trigger_price (float64),
                status (category), order_date (str), order_time (str)
        """
        if not account_id or not account_id.strip():
            raise BrokerValidationError(
                message="account_id (custody code) không được để trống.",
                code="INVALID_ACCOUNT_ID",
            )
        params: dict = {
            "pageNo": str(page_no),
            "PageSize": str(page_size),
            "accountId": account_id,
            "subAccountID": sub_account_id,
            "orderStatus": order_status,
            "orderType": order_type,
            "Symbol": symbol.upper() if symbol else "",
        }

        data = self._get(_PATHS["condition_orders"], params=params)

        if raw:
            return data

        records = data.get("data", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        if not records:
            return pd.DataFrame(columns=[
                "order_id", "symbol", "side", "order_type",
                "quantity", "price", "trigger_price", "status", "order_date", "order_time"
            ])

        df = pd.DataFrame(records)
        if "quantity" in df.columns:
            df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").astype("Int64")
        for col in ("price", "trigger_price"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        for col in ("side", "order_type", "status"):
            if col in df.columns:
                df[col] = df[col].astype("category")
        return df

    # ── Write HTTP methods ───────────────────────────────────────────────────

    # ── Internal HTTP ────────────────────────────────────────────────────────

    def _get(self, path: str, params: Optional[dict] = None) -> dict | list:
        try:
            token = self._session.token
        except BrokerSessionExpiredError:
            raise

        if not token:
            raise BrokerPermissionError(
                message="Session chưa được xác thực.",
                code="NOT_AUTHENTICATED",
                http_status=403,
            )

        url = self._config.base_url.rstrip("/") + path
        headers = {"Authorization": f"Bearer {token}"}

        try:
            resp = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=self._config.timeout_seconds,
            )
        except requests.exceptions.Timeout as exc:
            raise BrokerNetworkError(
                message=f"Timeout khi gọi {path}.",
                code="NETWORK_TIMEOUT",
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise BrokerNetworkError(
                message=f"Lỗi mạng: {type(exc).__name__}",
                code="NETWORK_ERROR",
            ) from exc

        if resp.status_code == 401:
            self._session.revoke()
            raise BrokerAuthError(
                message="Token hết hạn hoặc không hợp lệ.",
                code="TOKEN_EXPIRED",
                http_status=401,
            )
        if resp.status_code == 403:
            raise BrokerPermissionError(
                message="Không đủ quyền truy cập.",
                code="FORBIDDEN",
                http_status=403,
            )
        if resp.status_code == 429:
            raise BrokerRateLimitError(
                message="Vượt rate limit TCBS.",
                code="RATE_LIMIT",
                http_status=429,
            )
        if resp.status_code == 400:
            raise BrokerValidationError(
                message=f"Request không hợp lệ: {resp.text[:200]}",
                code="BAD_REQUEST",
                http_status=400,
            )
        if resp.status_code >= 500:
            raise BrokerNetworkError(
                message=f"TCBS server error {resp.status_code}.",
                code="SERVER_ERROR",
                http_status=resp.status_code,
            )

        return resp.json()
