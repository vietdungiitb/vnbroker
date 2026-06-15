"""
vnbroker.broker.tcbs.account — TCBSAccountService: read-only account data.

Endpoints (TCBS iFlash Open API v1.0.0):
  GET /eros/v2/get-profile/by-username/{custodyCode}   → get_profile()
  GET /aion/v1/accounts/{accountNo}/cashInvestments    → get_balance()
  GET /aion/v1/accounts/{accountNo}/ppse               → get_purchasing_power()

RULE: Không có write method. Mọi request dùng requests trực tiếp + session.token.
      custodyCode, idNo, phone, email phải masked trong raw=False output.
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
from vnbroker.broker.security.redaction import Redactor
from vnbroker.broker.session import BrokerSession

_logger = logging.getLogger("vnbroker.broker.tcbs.account")

_PATHS = {
    "profile": "/eros/v2/get-profile/by-username/{custodyCode}",
    "balance": "/aion/v1/accounts/{accountNo}/cashInvestments",
    "purchasing_power": "/aion/v1/accounts/{accountNo}/ppse",
    "list_accounts": "/aion/v1/accounts",
}


class TCBSAccountService:
    """Read-only account data service cho TCBS broker."""

    def __init__(
        self,
        config: TCBSCredentialConfig,
        session: BrokerSession,
    ) -> None:
        self._config = config
        self._session = session

    # ── Public methods ───────────────────────────────────────────────────────

    def get_profile(
        self,
        custody_code: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /eros/v2/get-profile/by-username/{custodyCode}

        Args:
            custody_code: Số tài khoản 105C (ví dụ: "105C334455").
            raw: True → trả về dict nguyên gốc (AccountInformationResponse).
                 False → trả về DataFrame với PII masked.

        Returns:
            DataFrame columns (raw=False):
                account_no (str) — tcbsId, dùng cho các endpoint /aion/, /akhlys/
                custody_code (str, masked)
                status (category)
                full_name (str, nếu có trong personalInfo)
        """
        _validate_custody_code(custody_code)
        path = _PATHS["profile"].format(custodyCode=custody_code)
        data = self._get(path)

        if raw:
            return data

        basic = data.get("basicInfo", {}) if isinstance(data, dict) else {}
        personal = data.get("personalInfo", {}) if isinstance(data, dict) else {}

        row = {
            "account_no": basic.get("tcbsId", ""),
            "custody_code": Redactor.mask_account_no(basic.get("code105C", custody_code)),
            "status": basic.get("status", ""),
            "full_name": personal.get("fullName", ""),
        }
        df = pd.DataFrame([row])
        if "status" in df.columns:
            df["status"] = df["status"].astype("category")
        return df

    def list_accounts(
        self,
        raw: bool = False,
    ) -> Union[pd.DataFrame, list]:
        """
        GET /aion/v1/accounts

        Args:
            raw: True → trả về list nguyên gốc.
                 False → trả về DataFrame với PII masked.

        Returns:
            DataFrame columns (raw=False):
                account_no (str), custody_code (str, masked),
                full_name (str), account_type (category), status (category)
        """
        path = _PATHS["list_accounts"]
        data = self._get(path)

        if raw:
            return data

        # Response: list of account objects
        records = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
        if not records:
            return pd.DataFrame(
                columns=["account_no", "custody_code", "full_name", "account_type", "status"]
            )

        rows = []
        for item in records:
            row = {
                "account_no": item.get("accountNo", ""),
                "custody_code": Redactor.mask_account_no(item.get("custodyCode", "")),
                "full_name": item.get("fullName", ""),
                "account_type": item.get("accountType", ""),
                "status": item.get("status", ""),
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        if "account_type" in df.columns:
            df["account_type"] = df["account_type"].astype("category")
        if "status" in df.columns:
            df["status"] = df["status"].astype("category")
        return df

    def get_balance(
        self,
        account_no: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /aion/v1/accounts/{accountNo}/cashInvestments

        Args:
            account_no: Số tiểu khoản 10 chữ số (ví dụ: "0001170730").
            raw: True → trả về dict nguyên gốc (CashInvestmentResponse).
                 False → trả về DataFrame.

        Returns:
            DataFrame columns (raw=False):
                account_no, custody_id, full_name,
                cash_balance (float64), bod_balance (float64),
                balance (float64), buying_power_bf (float64), bank_available_bf (float64)
        """
        _validate_account_no(account_no)
        path = _PATHS["balance"].format(accountNo=account_no)
        data = self._get(path)

        if raw:
            return data

        # CashInvestmentResponse: {object, totalCount, pageSize, pageIndex, data: [CashInvestmentInfo]}
        # Also handle flat response format for backward compatibility
        if isinstance(data, dict) and "data" in data:
            records = data.get("data", [])
        else:
            # Flat response format (legacy test compatibility)
            records = [data] if isinstance(data, dict) else []
        
        if not records:
            return pd.DataFrame(
                columns=["account_no", "custody_id", "full_name", "cash_balance",
                         "bod_balance", "balance", "buying_power_bf", "bank_available_bf"]
            )
        item = records[0] if isinstance(records, list) else records

        row = {
            "account_no": item.get("accountNo", account_no),
            "custody_id": item.get("custodyID", ""),
            "full_name": item.get("fullName", ""),
            "cash_balance": float(item.get("cashBalance") or item.get("totalAsset") or 0),
            "bod_balance": float(item.get("bodBalance") or 0),
            "balance": float(item.get("balance") or item.get("cashBalance") or 0),
            "buying_power_bf": float(item.get("pp0forBF") or item.get("availableAdvanceAmount") or 0),
            "bank_available_bf": float(item.get("bankAvlBalanceBF") or 0),
        }
        return pd.DataFrame([row]).astype({
            "cash_balance": "float64",
            "bod_balance": "float64",
            "balance": "float64",
            "buying_power_bf": "float64",
            "bank_available_bf": "float64",
        })

    def get_purchasing_power(
        self,
        account_no: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /aion/v1/accounts/{accountNo}/ppse

        Args:
            account_no: Số tiểu khoản 10 chữ số.
            raw: True → trả về dict nguyên gốc.
                 False → trả về DataFrame.

        Returns:
            DataFrame columns (raw=False):
                account_no (str), custody_id (str),
                pp0 (float64) — sức mua T0,
                ppse (float64) — sức mua thực tế,
                purchasing_power (float64) — alias for ppse,
                margin_ratio (float64) — tỷ lệ ký quỹ
        """
        _validate_account_no(account_no)
        path = _PATHS["purchasing_power"].format(accountNo=account_no)
        data = self._get(path)

        if raw:
            return data

        # Response schema không có trong spec — map các field phổ biến
        pp0 = float(data.get("pp0") or 0)
        ppse = float(data.get("ppse") or 0)
        margin_limit = float(data.get("marginLimit") or 1)
        margin_used = float(data.get("marginUsed") or 0)
        margin_ratio = margin_used / margin_limit if margin_limit > 0 else 0.0

        row = {
            "account_no": data.get("accountNo", account_no),
            "custody_id": data.get("custodyID", ""),
            "pp0": pp0,
            "ppse": ppse,
            "purchasing_power": ppse,
            "margin_ratio": margin_ratio,
        }
        return pd.DataFrame([row]).astype({
            "pp0": "float64",
            "ppse": "float64",
            "purchasing_power": "float64",
            "margin_ratio": "float64",
        })

    # ── Internal HTTP ────────────────────────────────────────────────────────

    def _get(self, path: str, params: dict | None = None) -> dict | list:
        """
        Gửi GET request với Bearer token từ session.
        Không log Authorization header.
        """
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

def _validate_account_no(account_no: str) -> None:
    if not account_no or not account_no.strip():
        raise BrokerValidationError(
            message="account_no không được để trống.",
            code="INVALID_ACCOUNT_NO",
        )


def _validate_custody_code(custody_code: str) -> None:
    if not custody_code or not custody_code.strip():
        raise BrokerValidationError(
            message="custody_code không được để trống (ví dụ: '105C334455').",
            code="INVALID_CUSTODY_CODE",
        )
