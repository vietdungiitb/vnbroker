"""
vnbroker.broker.tcbs.money — TCBSMoneyService: read-only cash & margin data.

Endpoints (TCBS iFlash Open API v1.0.0):
  GET /aion/v1/accounts/{accountNo}/cashInvestments    → get_cash()
  GET /erebos/v2/digital/margin-info?acctno=&fromdate=&toDate=&page=&size=&custodycd=
                                                       → get_margin()

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
)
from vnbroker.broker.security.credentials import TCBSCredentialConfig
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.tcbs.account import _validate_account_no

_logger = logging.getLogger("vnbroker.broker.tcbs.money")

_PATHS = {
    "cash": "/aion/v1/accounts/{accountNo}/cashInvestments",
    "margin": "/erebos/v2/digital/margin-info",
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
        GET /aion/v1/accounts/{accountNo}/cashInvestments

        CashInvestmentResponse (paginated). Lấy data[0] nếu có.

        DataFrame columns (raw=False):
            account_no, custody_id, full_name,
            cash_balance (float64), bod_balance (float64), balance (float64),
            buying_power_bf (float64), bank_available_bf (float64),
            withdrawable_amount (float64), pending_settlement (float64)
        """
        _validate_account_no(account_no)
        path = _PATHS["cash"].format(accountNo=account_no)
        data = self._get(path)

        if raw:
            return data

        # Paginated: {data: [CashInvestmentItem], ...}
        # Also handle flat response format for backward compatibility
        if isinstance(data, dict) and "data" in data:
            records = data.get("data", [])
        else:
            records = [data] if isinstance(data, dict) else data
        record = records[0] if records else {}
        row = {
            "account_no": record.get("accountNo", account_no),
            "custody_id": record.get("custodyId", ""),
            "full_name": record.get("fullName", ""),
            "cash_balance": float(record.get("cashBalance") or record.get("totalAsset") or 0),
            "bod_balance": float(record.get("bodBalance") or 0),
            "balance": float(record.get("balance") or record.get("cashBalance") or 0),
            "buying_power_bf": float(record.get("buyingPowerBf") or record.get("availableAdvanceAmount") or 0),
            "bank_available_bf": float(record.get("bankAvailableBf") or 0),
            "withdrawable_amount": float(record.get("withdrawableAmount") or record.get("availableAdvanceAmount") or 0),
            "pending_settlement": float(record.get("pendingSettlement") or 0),
        }
        return pd.DataFrame([row]).astype({
            "cash_balance": "float64",
            "bod_balance": "float64",
            "balance": "float64",
            "buying_power_bf": "float64",
            "bank_available_bf": "float64",
            "withdrawable_amount": "float64",
            "pending_settlement": "float64",
        })

    def get_margin(
        self,
        account_no: str,
        custody_code: str = "",
        from_date: str = "",
        to_date: str = "",
        page: int = 0,
        size: int = 20,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /erebos/v2/digital/margin-info

        Query params: acctno, fromdate, toDate, page, size, custodycd.

        DataFrame columns (raw=False):
            account_no (str), custody_code (str),
            margin_limit (float64), margin_used (float64),
            margin_available (float64), call_margin (float64),
            maintenance_margin_rate (float64),
            from_date (str), to_date (str)
        """
        _validate_account_no(account_no)
        params: dict = {"acctno": account_no, "page": page, "size": size}
        if custody_code:
            params["custodycd"] = custody_code
        if from_date:
            params["fromdate"] = from_date
        if to_date:
            params["toDate"] = to_date

        data = self._get(_PATHS["margin"], params=params)

        if raw:
            return data

        records = data.get("data", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        if not records:
            record = {}
        else:
            record = records[0]
        
        margin_limit = float(record.get("marginLimit") or 0)
        margin_used = float(record.get("marginUsed") or 0)
        maintenance_margin_rate = margin_used / margin_limit if margin_limit > 0 else 0.0
        
        row = {
            "account_no": record.get("acctno", account_no),
            "custody_code": record.get("custodycd", custody_code),
            "margin_limit": margin_limit,
            "margin_used": margin_used,
            "margin_available": float(record.get("marginAvailable") or 0),
            "call_margin": float(record.get("callMargin") or 0),
            "maintenance_margin_rate": maintenance_margin_rate,
            "from_date": record.get("fromdate", from_date),
            "to_date": record.get("toDate", to_date),
        }
        return pd.DataFrame([row]).astype({
            "margin_limit": "float64",
            "margin_used": "float64",
            "margin_available": "float64",
            "call_margin": "float64",
            "maintenance_margin_rate": "float64",
        })

    # ── Internal HTTP ────────────────────────────────────────────────────────

    def _get(self, path: str, params: dict | None = None) -> dict:
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
        if resp.status_code >= 500:
            raise BrokerNetworkError(
                message=f"TCBS server error {resp.status_code}.",
                code="SERVER_ERROR",
                http_status=resp.status_code,
            )

        return resp.json()
