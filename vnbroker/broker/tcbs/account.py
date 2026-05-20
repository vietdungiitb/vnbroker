"""
vnbroker.broker.tcbs.account — TCBSAccountService: read-only account data.

Endpoints:
  GET /gaia/v1/openapi/account/list
  GET /gaia/v1/openapi/account/{accountNo}/profile
  GET /gaia/v1/openapi/account/{accountNo}/balance
  GET /gaia/v1/openapi/account/{accountNo}/portfolio/purchasing-power

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
    "list": "/gaia/v1/openapi/account/list",
    "profile": "/gaia/v1/openapi/account/{accountNo}/profile",
    "balance": "/gaia/v1/openapi/account/{accountNo}/balance",
    "purchasing_power": "/gaia/v1/openapi/account/{accountNo}/portfolio/purchasing-power",
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

    def list_accounts(self, raw: bool = False) -> Union[pd.DataFrame, list]:
        """
        GET /gaia/v1/openapi/account/list

        Args:
            raw: True → trả về list[dict] nguyên gốc.
                 False → trả về DataFrame (custodyCode masked).

        Returns:
            DataFrame hoặc list tùy `raw`.
            DataFrame columns: account_no, custody_code, full_name,
                               account_type (category), status (category)
        """
        data = self._get(_PATHS["list"])
        if not isinstance(data, list):
            data = [data]

        if raw:
            return data

        df = pd.DataFrame(data)
        if df.empty:
            return df

        df = df.rename(columns={
            "accountNo": "account_no",
            "custodyCode": "custody_code",
            "fullName": "full_name",
            "accountType": "account_type",
            "status": "status",
        })
        # Mask custody_code trong raw=False
        if "custody_code" in df.columns:
            df["custody_code"] = df["custody_code"].apply(
                lambda v: Redactor.mask_account_no(str(v)) if pd.notna(v) else v
            )
        for col in ("account_type", "status"):
            if col in df.columns:
                df[col] = df[col].astype("category")
        return df

    def get_profile(
        self,
        account_no: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /gaia/v1/openapi/account/{accountNo}/profile

        PII fields (idNo, phone, email, custodyCode) đều bị redact trong raw=False.
        """
        _validate_account_no(account_no)
        path = _PATHS["profile"].format(accountNo=account_no)
        data = self._get(path)

        if raw:
            return data

        # Redact PII trong output
        safe = Redactor.redact_dict(
            data,
            keys=frozenset({"idno", "id_no", "phone", "email", "custodycode", "custody_code"}),
        )
        df = pd.DataFrame([safe])
        df = df.rename(columns={
            "accountNo": "account_no",
            "custodyCode": "custody_code",
            "fullName": "full_name",
            "idNo": "id_no",
        })
        return df

    def get_balance(
        self,
        account_no: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /gaia/v1/openapi/account/{accountNo}/balance

        DataFrame columns (raw=False):
            account_no (str), total_asset (float64), cash_balance (float64),
            stock_value (float64), debt_balance (float64),
            available_advance_amount (float64)
        """
        _validate_account_no(account_no)
        path = _PATHS["balance"].format(accountNo=account_no)
        data = self._get(path)

        if raw:
            return data

        row = {
            "account_no": data.get("accountNo", account_no),
            "total_asset": float(data.get("totalAsset", 0)),
            "cash_balance": float(data.get("cashBalance", 0)),
            "stock_value": float(data.get("stockValue", 0)),
            "debt_balance": float(data.get("debtBalance", 0)),
            "available_advance_amount": float(data.get("availableAdvanceAmount", 0)),
        }
        return pd.DataFrame([row]).astype({
            "total_asset": "float64",
            "cash_balance": "float64",
            "stock_value": "float64",
            "debt_balance": "float64",
            "available_advance_amount": "float64",
        })

    def get_purchasing_power(
        self,
        account_no: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /gaia/v1/openapi/account/{accountNo}/portfolio/purchasing-power

        DataFrame columns (raw=False):
            account_no (str), purchasing_power (float64),
            margin_purchasing_power (float64), margin_ratio (float64)
        """
        _validate_account_no(account_no)
        path = _PATHS["purchasing_power"].format(accountNo=account_no)
        data = self._get(path)

        if raw:
            return data

        row = {
            "account_no": data.get("accountNo", account_no),
            "purchasing_power": float(data.get("purchasingPower", 0)),
            "margin_purchasing_power": float(data.get("marginPurchasingPower", 0)),
            "margin_ratio": float(data.get("marginRatio", 0.0)),
        }
        return pd.DataFrame([row]).astype({
            "purchasing_power": "float64",
            "margin_purchasing_power": "float64",
            "margin_ratio": "float64",
        })

    # ── Internal HTTP ────────────────────────────────────────────────────────

    def _get(self, path: str) -> dict | list:
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
