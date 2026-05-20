"""
vnbroker.broker.tcbs.derivatives — TCBSDerivativesService: read-only derivatives.

READ endpoints:
  GET /gaia/v1/openapi/account/{accountNo}/derivatives/positions
  GET /gaia/v1/openapi/account/{accountNo}/derivatives/orders

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
from vnbroker.broker.tcbs.account import _validate_account_no
from vnbroker.broker.tcbs.equity import _ensure_columns

_logger = logging.getLogger("vnbroker.broker.tcbs.derivatives")

_PATHS = {
    "positions": "/gaia/v1/openapi/account/{accountNo}/derivatives/positions",
    "orders": "/gaia/v1/openapi/account/{accountNo}/derivatives/orders",
}

_POSITION_COLUMNS = {
    "symbol": "symbol",
    "side": "side",
    "openQuantity": "open_quantity",
    "openPrice": "open_price",
    "currentPrice": "current_price",
    "unrealizedPnl": "unrealized_pnl",
    "margin": "margin",
}

_DERIV_ORDER_COLUMNS = {
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


class TCBSDerivativesService:
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
        account_no: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, list]:
        """
        GET /gaia/v1/openapi/account/{accountNo}/derivatives/positions

        DataFrame columns (raw=False):
            symbol (str), side (category: LONG/SHORT),
            open_quantity (Int64), open_price (float64),
            current_price (float64), unrealized_pnl (float64), margin (float64)
        """
        _validate_account_no(account_no)
        path = _PATHS["positions"].format(accountNo=account_no)
        data = self._get(path)

        if raw:
            return data

        records = data if isinstance(data, list) else ([data] if data else [])
        if not records:
            return pd.DataFrame(columns=list(_POSITION_COLUMNS.values()))

        df = pd.DataFrame(records)
        df = df.rename(columns=_POSITION_COLUMNS)
        df = _ensure_columns(df, _POSITION_COLUMNS.values())
        df["side"] = df["side"].astype("category")
        for col in ("open_price", "current_price", "unrealized_pnl", "margin"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        if "open_quantity" in df.columns:
            df["open_quantity"] = pd.to_numeric(df["open_quantity"], errors="coerce").astype("Int64")
        return df

    def get_orders(
        self,
        account_no: str,
        page: int = 0,
        size: int = 50,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /gaia/v1/openapi/account/{accountNo}/derivatives/orders

        DataFrame columns (raw=False): order_id, symbol, side (category),
            order_type (category), quantity (Int64), price (float64),
            filled_quantity (float64), status (category), created_at (str)
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
        if not records:
            return pd.DataFrame(columns=list(_DERIV_ORDER_COLUMNS.values()))

        df = pd.DataFrame(records)
        df = df.rename(columns=_DERIV_ORDER_COLUMNS)
        df = _ensure_columns(df, _DERIV_ORDER_COLUMNS.values())
        for col in ("side", "order_type", "status"):
            if col in df.columns:
                df[col] = df[col].astype("category")
        for col in ("price", "filled_quantity"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        if "quantity" in df.columns:
            df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").astype("Int64")
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
