"""
vnbroker.broker.tcbs.equity — TCBSEquityService: read-only equity data.

READ endpoints:
  GET /gaia/v1/openapi/account/{accountNo}/orders
  GET /gaia/v1/openapi/account/{accountNo}/orders/{orderId}
  GET /gaia/v1/openapi/account/{accountNo}/orders/history
  GET /gaia/v1/openapi/account/{accountNo}/executions
  GET /gaia/v1/openapi/account/{accountNo}/portfolio/holdings

WRITE endpoints (S8 — not here):
  POST   /gaia/v1/openapi/account/{accountNo}/orders   → place_order()
  PUT    /gaia/v1/openapi/account/{accountNo}/orders/{orderId} → modify_order()
  DELETE /gaia/v1/openapi/account/{accountNo}/orders/{orderId} → cancel_order()

RULE: Chỉ read methods trong slice này. Write methods thêm ở S8.
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
from vnbroker.broker.tcbs.account import _validate_account_no

_logger = logging.getLogger("vnbroker.broker.tcbs.equity")

_PATHS = {
    "orders": "/gaia/v1/openapi/account/{accountNo}/orders",
    "order_detail": "/gaia/v1/openapi/account/{accountNo}/orders/{orderId}",
    "order_history": "/gaia/v1/openapi/account/{accountNo}/orders/history",
    "executions": "/gaia/v1/openapi/account/{accountNo}/executions",
    "holdings": "/gaia/v1/openapi/account/{accountNo}/portfolio/holdings",
}

_ORDER_COLUMNS = {
    "orderId": "order_id",
    "symbol": "symbol",
    "side": "side",
    "orderType": "order_type",
    "quantity": "quantity",
    "price": "price",
    "filledQuantity": "filled_quantity",
    "status": "status",
    "createdAt": "created_at",
}

_EXECUTION_COLUMNS = {
    "executionId": "execution_id",
    "orderId": "order_id",
    "symbol": "symbol",
    "side": "side",
    "executedQuantity": "executed_quantity",
    "executedPrice": "executed_price",
    "executedAt": "executed_at",
    "fee": "fee",
    "tax": "tax",
}

_HOLDING_COLUMNS = {
    "symbol": "symbol",
    "quantity": "quantity",
    "availableQuantity": "available_quantity",
    "averageCost": "average_cost",
    "currentPrice": "current_price",
    "marketValue": "market_value",
    "unrealizedPnl": "unrealized_pnl",
    "unrealizedPnlPercent": "unrealized_pnl_pct",
}


class TCBSEquityService:
    """Read-only equity service: danh sách lệnh, lịch sử khớp, holdings."""

    def __init__(
        self,
        config: TCBSCredentialConfig,
        session: BrokerSession,
    ) -> None:
        self._config = config
        self._session = session

    # ── Orders ────────────────────────────────────────────────────────────────

    def get_orders(
        self,
        account_no: str,
        page: int = 0,
        size: int = 50,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /gaia/v1/openapi/account/{accountNo}/orders

        DataFrame columns (raw=False): order_id, symbol, side (category),
            order_type (category), quantity (int64), price (float64),
            filled_quantity (int64), status (category), created_at (str)
        """
        _validate_account_no(account_no)
        if size > 100:
            raise BrokerValidationError(
                message="size tối đa 100.",
                code="INVALID_SIZE",
            )
        path = _PATHS["orders"].format(accountNo=account_no)
        data = self._get(path, params={"page": page, "size": size})

        if raw:
            return data

        records = data.get("data", []) if isinstance(data, dict) else data
        df = _build_order_df(records)
        return df

    def get_order_detail(
        self,
        account_no: str,
        order_id: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /gaia/v1/openapi/account/{accountNo}/orders/{orderId}
        """
        _validate_account_no(account_no)
        if not order_id or not order_id.strip():
            raise BrokerValidationError(
                message="order_id không được để trống.",
                code="INVALID_ORDER_ID",
            )
        path = _PATHS["order_detail"].format(accountNo=account_no, orderId=order_id)
        data = self._get(path)

        if raw:
            return data

        df = _build_order_df([data] if isinstance(data, dict) else data)
        return df

    def get_order_history(
        self,
        account_no: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        symbol: Optional[str] = None,
        page: int = 0,
        size: int = 50,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /gaia/v1/openapi/account/{accountNo}/orders/history

        Params: fromDate/toDate YYYY-MM-DD, symbol (optional), page, size.
        """
        _validate_account_no(account_no)
        params: dict = {"page": page, "size": size}
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date
        if symbol:
            params["symbol"] = symbol

        path = _PATHS["order_history"].format(accountNo=account_no)
        data = self._get(path, params=params)

        if raw:
            return data

        records = data.get("data", []) if isinstance(data, dict) else data
        df = _build_order_df(records)
        return df

    # ── Executions ────────────────────────────────────────────────────────────

    def get_executions(
        self,
        account_no: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page: int = 0,
        size: int = 50,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /gaia/v1/openapi/account/{accountNo}/executions

        DataFrame columns (raw=False): execution_id, order_id, symbol, side,
            executed_quantity (int64), executed_price (float64),
            executed_at (str), fee (float64), tax (float64)
        """
        _validate_account_no(account_no)
        params: dict = {"page": page, "size": size}
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date

        path = _PATHS["executions"].format(accountNo=account_no)
        data = self._get(path, params=params)

        if raw:
            return data

        records = data.get("data", []) if isinstance(data, dict) else data
        if not records:
            return pd.DataFrame(columns=list(_EXECUTION_COLUMNS.values()))

        df = pd.DataFrame(records)
        df = df.rename(columns=_EXECUTION_COLUMNS)
        df = _ensure_columns(df, _EXECUTION_COLUMNS.values())
        for col in ("side",):
            if col in df.columns:
                df[col] = df[col].astype("category")
        for col in ("executed_price", "fee", "tax"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        for col in ("executed_quantity",):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        return df

    # ── Holdings ──────────────────────────────────────────────────────────────

    def get_holdings(
        self,
        account_no: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, list]:
        """
        GET /gaia/v1/openapi/account/{accountNo}/portfolio/holdings

        DataFrame columns (raw=False): symbol, quantity (int64),
            available_quantity (int64), average_cost (float64),
            current_price (float64), market_value (float64),
            unrealized_pnl (float64), unrealized_pnl_pct (float64)
        """
        _validate_account_no(account_no)
        path = _PATHS["holdings"].format(accountNo=account_no)
        data = self._get(path)

        if raw:
            return data

        records = data if isinstance(data, list) else [data]
        if not records:
            return pd.DataFrame(columns=list(_HOLDING_COLUMNS.values()))

        df = pd.DataFrame(records)
        df = df.rename(columns=_HOLDING_COLUMNS)
        df = _ensure_columns(df, _HOLDING_COLUMNS.values())
        for col in ("average_cost", "current_price", "market_value", "unrealized_pnl", "unrealized_pnl_pct"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        for col in ("quantity", "available_quantity"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        return df

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


# ── Helpers ──────────────────────────────────────────────────────────────────

def _build_order_df(records: list) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=list(_ORDER_COLUMNS.values()))
    df = pd.DataFrame(records)
    df = df.rename(columns=_ORDER_COLUMNS)
    df = _ensure_columns(df, _ORDER_COLUMNS.values())
    for col in ("side", "order_type", "status"):
        if col in df.columns:
            df[col] = df[col].astype("category")
    for col in ("price", "filled_quantity"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ("quantity",):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    return df


def _ensure_columns(df: pd.DataFrame, columns) -> pd.DataFrame:
    """Đảm bảo DataFrame có đủ các columns, thêm NaN nếu thiếu."""
    for col in columns:
        if col not in df.columns:
            df[col] = pd.NA
    return df
