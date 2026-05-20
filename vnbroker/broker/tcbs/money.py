"""
vnbroker.broker.tcbs.money — TCBSMoneyService: read-only cash & margin data.

Endpoints:
  GET /gaia/v1/openapi/account/{accountNo}/money/cash
  GET /gaia/v1/openapi/account/{accountNo}/money/margin

RULE: Không có write method. Reuse _get pattern từ account service.
"""
from __future__ import annotations

import logging
from typing import Union

import pandas as pd
import requests

from vnbroker.broker.exceptions import (
    BrokerAuthError,
    BrokerNetworkError,
    BrokerPermissionError,
    BrokerSessionExpiredError,
    BrokerValidationError,
)
from vnbroker.broker.security.credentials import TCBSCredentialConfig
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.tcbs.account import _validate_account_no

_logger = logging.getLogger("vnbroker.broker.tcbs.money")

_PATHS = {
    "cash": "/gaia/v1/openapi/account/{accountNo}/money/cash",
    "margin": "/gaia/v1/openapi/account/{accountNo}/money/margin",
}


class TCBSMoneyService:
    """Read-only cash và margin service cho TCBS broker."""

    def __init__(
        self,
        config: TCBSCredentialConfig,
        session: BrokerSession,
    ) -> None:
        self._config = config
        self._session = session

    def get_cash(
        self,
        account_no: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /gaia/v1/openapi/account/{accountNo}/money/cash

        DataFrame columns (raw=False):
            account_no (str), withdrawable_amount (float64),
            pending_settlement (float64), cash_balance (float64)
        """
        _validate_account_no(account_no)
        path = _PATHS["cash"].format(accountNo=account_no)
        data = self._get(path)

        if raw:
            return data

        row = {
            "account_no": data.get("accountNo", account_no),
            "withdrawable_amount": float(data.get("withdrawableAmount", 0)),
            "pending_settlement": float(data.get("pendingSettlement", 0)),
            "cash_balance": float(data.get("cashBalance", 0)),
        }
        return pd.DataFrame([row]).astype({
            "withdrawable_amount": "float64",
            "pending_settlement": "float64",
            "cash_balance": "float64",
        })

    def get_margin(
        self,
        account_no: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /gaia/v1/openapi/account/{accountNo}/money/margin

        DataFrame columns (raw=False):
            account_no (str), margin_limit (float64), margin_used (float64),
            margin_available (float64), maintenance_margin_rate (float64)
        """
        _validate_account_no(account_no)
        path = _PATHS["margin"].format(accountNo=account_no)
        data = self._get(path)

        if raw:
            return data

        row = {
            "account_no": data.get("accountNo", account_no),
            "margin_limit": float(data.get("marginLimit", 0)),
            "margin_used": float(data.get("marginUsed", 0)),
            "margin_available": float(data.get("marginAvailable", 0)),
            "maintenance_margin_rate": float(data.get("maintenanceMarginRate", 0.0)),
        }
        return pd.DataFrame([row]).astype({
            "margin_limit": "float64",
            "margin_used": "float64",
            "margin_available": "float64",
            "maintenance_margin_rate": "float64",
        })

    # ── Internal HTTP ────────────────────────────────────────────────────────

    def _get(self, path: str) -> dict:
        try:
            token = self._session.token
        except BrokerSessionExpiredError:
            raise

        if not token:
            raise BrokerPermissionError(
                message="Session chưa được xác thực. Gọi authenticate() trước.",
                code="NOT_AUTHENTICATED",
                http_status=403,
            )

        url = self._config.base_url.rstrip("/") + path
        headers = {"Authorization": f"Bearer {token}"}

        try:
            resp = requests.get(
                url,
                headers=headers,
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
        if resp.status_code >= 500:
            raise BrokerNetworkError(
                message=f"TCBS server error {resp.status_code}.",
                code="SERVER_ERROR",
                http_status=resp.status_code,
            )

        return resp.json()
