"""
vnbroker.broker.tcbs.account — TCBSAccountService: read-only account data.

Endpoints (TCBS iFlash Open API v1.0.0):
  GET /eros/v2/get-profile/by-username/{custodyCode}   → get_profile()
  GET /aion/v1/accounts/{accountNo}/cashInvestments    → get_balance()
  GET /aion/v1/accounts/{accountNo}/ppse               → get_purchasing_power()

RULE: Không có write method. Mọi request dùng requests trực tiếp + session.token.
      custodyCode, idNo, phone, email phải masked trong raw=False output.

GỠ 13 PATH LEGACY (`/erebos/v1/*`, `/erebos/v2/accounts/*`) — 2026-10-09
---------------------------------------------------------------------
13 path này KHÔNG có trong CẢ HAI tài liệu chính thức:
`openapi-v1.0.0.json` và `tcbs-openapi-v1.0.0.postman_collection.json`
(cả hai đều có 48 REST endpoint, khớp nhau 48/48).

⇒ Xoá theo quyết định của Owner dựa trên 2 tài liệu chính thức, CHƯA probe
  server. Lý do không probe được: TCBS trả 401 TRƯỚC khi routing nên không
  phân biệt được route tồn tại hay không.
⇒ KHÔNG phải kết luận "path không tồn tại trên server" — chỉ là
  "không có trong tài liệu chính thức".
⇒ Method công khai tương ứng VẪN CÒN nhưng NÉM NotImplementedError
  (xem `_raise_removed()`), không im lặng trả về rỗng.

NGOẠI LỆ: `/aion/v1/accounts` (không param) được GIỮ LẠI vì
`BaseBrokerClient.get_account_list()` là @abstractmethod
(`vnbroker/broker/base.py:55-58`). Path thay thế trong spec
`/aion/v1/customers/{custodyId}/accounts` cần custodyId — tức là cần chính
thông tin mà `get_account_list()` sinh ra, nên không thay thế được.
"""
from __future__ import annotations

import logging
from typing import NoReturn, Union

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
    # NGOẠI LỆ — xem docstring module. Giữ vì get_account_list() là @abstractmethod.
    "list_accounts": "/aion/v1/accounts",
}

# 13 path đã gỡ — xoá theo quyết định Owner dựa trên 2 tài liệu chính thức,
# CHƯA probe server. Key = tên method công khai, value = path đã gỡ.
_REMOVED_PATHS: dict[str, str] = {
    "get_erebos_v1_asset": "/erebos/v1/account/asset",
    "get_erebos_v1_available_balance": "/erebos/v1/account/available-balance",
    "get_erebos_v1_portfolio_asset": "/erebos/v1/portfolio-asset",
    "get_erebos_v1_portfolio_asset_token": "/erebos/v1/portfolio-asset/token",
    "get_erebos_v1_portfolio_stock_statistic": "/erebos/v1/portfolio/stock/{accountNo}/statistic",
    "get_erebos_v2_asset": "/erebos/v2/accounts/{accountNo}/asset",
    "get_erebos_v2_available_balance": "/erebos/v2/accounts/{accountNo}/available-balance",
    "get_erebos_v2_stock_statistic": "/erebos/v2/accounts/{accountNo}/stock-statistic",
    "get_erebos_v2_orders_history": "/erebos/v2/accounts/{accountNo}/orders/history",
    "get_erebos_v2_orders_matching": "/erebos/v2/accounts/{accountNo}/orders/matching",
    "get_erebos_v2_withdraw_history": "/erebos/v2/accounts/{accountNo}/withdraw",
    "get_erebos_v2_deposit_history": "/erebos/v2/accounts/{accountNo}/deposit",
    "get_erebos_v2_dividend_history": "/erebos/v2/accounts/{accountNo}/dividend",
}


def _raise_removed(method_name: str) -> NoReturn:
    """
    Ném lỗi rõ ràng cho method đã gỡ — KHÔNG trả về rỗng im lặng.

    Path bị gỡ không có trong openapi-v1.0.0.json và
    tcbs-openapi-v1.0.0.postman_collection.json. Đây là quyết định của Owner
    dựa trên 2 tài liệu chính thức; CHƯA probe server (401 chạy trước
    routing nên không phân biệt được route có hay không).
    """
    path = _REMOVED_PATHS[method_name]
    raise NotImplementedError(
        f"{method_name}() đã bị gỡ bỏ: path {path} không có trong "
        f"openapi-v1.0.0.json và tcbs-openapi-v1.0.0.postman_collection.json. "
        f"Xoá theo quyết định Owner dựa trên 2 tài liệu chính thức, chưa probe server. "
        f"Dùng endpoint trong spec thay thế (ví dụ /aion/v1/accounts/{{accountNo}}/se, "
        f"/aion/v1/accounts/{{accountNo}}/cashInvestments)."
    )


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

# ── Path đã gỡ (13 path) ─────────────────────────────────────────────────
    # Xoá theo quyết định Owner dựa trên 2 tài liệu chính thức, chưa probe server.
    # Mỗi method ném NotImplementedError — KHÔNG im lặng trả về rỗng.

    def get_erebos_v1_asset(self, account_no: str, raw: bool = False) -> Union[pd.DataFrame, dict]:
        """ĐÃ GỠ — /erebos/v1/account/asset. Xem docstring module + `_REMOVED_PATHS`."""
        _raise_removed("get_erebos_v1_asset")

    def get_erebos_v1_available_balance(self, account_no: str, raw: bool = False) -> Union[pd.DataFrame, dict]:
        """ĐÃ GỠ — /erebos/v1/account/available-balance."""
        _raise_removed("get_erebos_v1_available_balance")

    def get_erebos_v1_portfolio_asset(self, account_no: str, raw: bool = False) -> Union[pd.DataFrame, list]:
        """ĐÃ GỠ — /erebos/v1/portfolio-asset."""
        _raise_removed("get_erebos_v1_portfolio_asset")

    def get_erebos_v1_portfolio_asset_token(self, account_no: str, raw: bool = False) -> Union[pd.DataFrame, list]:
        """ĐÃ GỠ — /erebos/v1/portfolio-asset/token."""
        _raise_removed("get_erebos_v1_portfolio_asset_token")

    def get_erebos_v1_portfolio_stock_statistic(self, account_no: str, raw: bool = False) -> Union[pd.DataFrame, dict]:
        """ĐÃ GỠ — /erebos/v1/portfolio/stock/{accountNo}/statistic."""
        _raise_removed("get_erebos_v1_portfolio_stock_statistic")

    def get_erebos_v2_asset(self, account_no: str, raw: bool = False) -> Union[pd.DataFrame, dict]:
        """ĐÃ GỠ — /erebos/v2/accounts/{accountNo}/asset."""
        _raise_removed("get_erebos_v2_asset")

    def get_erebos_v2_available_balance(self, account_no: str, raw: bool = False) -> Union[pd.DataFrame, dict]:
        """ĐÃ GỠ — /erebos/v2/accounts/{accountNo}/available-balance."""
        _raise_removed("get_erebos_v2_available_balance")

    def get_erebos_v2_stock_statistic(self, account_no: str, raw: bool = False) -> Union[pd.DataFrame, dict]:
        """ĐÃ GỠ — /erebos/v2/accounts/{accountNo}/stock-statistic."""
        _raise_removed("get_erebos_v2_stock_statistic")

    def get_erebos_v2_orders_history(
        self,
        account_no: str,
        from_date: str = "",
        to_date: str = "",
        page: int = 0,
        size: int = 50,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """ĐÃ GỠ — /erebos/v2/accounts/{accountNo}/orders/history."""
        _raise_removed("get_erebos_v2_orders_history")

    def get_erebos_v2_orders_matching(
        self,
        account_no: str,
        from_date: str = "",
        to_date: str = "",
        page: int = 0,
        size: int = 50,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """ĐÃ GỠ — /erebos/v2/accounts/{accountNo}/orders/matching."""
        _raise_removed("get_erebos_v2_orders_matching")

    def get_erebos_v2_withdraw_history(
        self,
        account_no: str,
        from_date: str = "",
        to_date: str = "",
        page: int = 0,
        size: int = 50,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """ĐÃ GỠ — /erebos/v2/accounts/{accountNo}/withdraw."""
        _raise_removed("get_erebos_v2_withdraw_history")

    def get_erebos_v2_deposit_history(
        self,
        account_no: str,
        from_date: str = "",
        to_date: str = "",
        page: int = 0,
        size: int = 50,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """ĐÃ GỠ — /erebos/v2/accounts/{accountNo}/deposit."""
        _raise_removed("get_erebos_v2_deposit_history")

    def get_erebos_v2_dividend_history(
        self,
        account_no: str,
        from_date: str = "",
        to_date: str = "",
        page: int = 0,
        size: int = 50,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """ĐÃ GỠ — /erebos/v2/accounts/{accountNo}/dividend."""
        _raise_removed("get_erebos_v2_dividend_history")

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
