"""
vnbroker.broker.tcbs.money — TCBSMoneyService: cash & margin (read + write).

READ endpoints (TCBS iFlash Open API v1.0.0):
  GET /aion/v1/accounts/{accountNo}/cashInvestments    → get_cash()
  GET /erebos/v2/digital/margin-info?acctno=&fromdate=&toDate=&page=&size=&custodycd=
                                                       → get_margin()
  GET /hydros/v1/account/{accountNo}/pricing-policy?productId=
                                                       → get_pricing_policy()

WRITE endpoints (dry_run=True mặc định, @write_gate bắt buộc):
  POST /khronos/v1/cash/deposit/update                → deposit_margin()
  POST /khronos/v1/cash/withdraw/update               → withdraw_margin()
  POST /physis/v1/stock/transfer                      → transfer_between_sub_accounts()

RULE:
  - Mọi write method PHẢI khai `dry_run` là keyword-only: write_gate đọc dry_run
    từ kwargs (security/guards.py:46), truyền theo vị trí sẽ không bao giờ qua gate.
  - Body theo đúng tên field trong spec. KHÔNG gửi `requestId` — chuỗi này
    không tồn tại trong openapi-v1.0.0.json (đếm 0 lần).
  - Reuse _get/_post pattern từ account service.
"""
from __future__ import annotations

import logging
from typing import Any, Union

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
from vnbroker.broker.security.guards import write_gate
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.tcbs.account import _validate_account_no

_logger = logging.getLogger("vnbroker.broker.tcbs.money")

_PATHS = {
    "cash": "/aion/v1/accounts/{accountNo}/cashInvestments",
    "margin": "/erebos/v2/digital/margin-info",
    # Phase 2 additional endpoints
    "ppse_symbol": "/aion/v1/accounts/{accountNo}/ppse/{symbol}",
    "ppse_symbol_price": "/aion/v1/accounts/{accountNo}/ppse/{symbol}/{price}",
    "customer_accounts": "/aion/v1/customers/{custodyId}/accounts",
    "hydros_risk": "/hydros/v1/account/{accountNo}/risk",
    "margin_subscription": "/campaign-management/v1/margin/subscription/{accountNo}/addons/detail",
    "loan_list": "/khaos/v1/loan/{accountNo}",
    "cash_statements": "/erebos/v2/digital/trans-hist-cashStatements",
    # Round 2 (spec v1.0.0): 1 read + 3 write
    "pricing_policy": "/hydros/v1/account/{accountNo}/pricing-policy",
    "cash_deposit": "/khronos/v1/cash/deposit/update",
    "cash_withdraw": "/khronos/v1/cash/withdraw/update",
    "stock_transfer": "/physis/v1/stock/transfer",
}


class TCBSMoneyService:
    """Cash và margin service cho TCBS broker (read + write)."""

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

    def get_purchasing_power_by_symbol(
        self,
        account_no: str,
        symbol: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /aion/v1/accounts/{accountNo}/ppse/{symbol}

        Args:
            account_no: Số tiểu khoản 10 chữ số.
            symbol: Mã chứng khoán (VNM, HPG...).
            raw: True → trả về dict nguyên gốc.

        Returns:
            DataFrame columns (raw=False):
                account_no, symbol, ppse (float64),
                max_quantity (Int64), margin_ratio (float64)
        """
        _validate_account_no(account_no)
        if not symbol or not symbol.strip():
            raise BrokerValidationError(
                message="symbol không được để trống.",
                code="INVALID_SYMBOL",
            )
        path = _PATHS["ppse_symbol"].format(accountNo=account_no, symbol=symbol.upper())
        data = self._get(path)

        if raw:
            return data

        row = {
            "account_no": data.get("accountNo", account_no),
            "symbol": symbol.upper(),
            "ppse": float(data.get("ppse") or 0),
            "max_quantity": int(data.get("maxQuantity") or 0),
            "margin_ratio": float(data.get("marginRatio") or 0),
        }
        return pd.DataFrame([row]).astype({
            "ppse": "float64",
            "max_quantity": "Int64",
            "margin_ratio": "float64",
        })

    def get_purchasing_power_by_symbol_price(
        self,
        account_no: str,
        symbol: str,
        price: float,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /aion/v1/accounts/{accountNo}/ppse/{symbol}/{price}

        Args:
            account_no: Số tiểu khoản 10 chữ số.
            symbol: Mã chứng khoán (VNM, HPG...).
            price: Giá đặt lệnh.
            raw: True → trả về dict nguyên gốc.

        Returns:
            DataFrame columns (raw=False):
                account_no, symbol, price (float64),
                max_quantity (Int64), ppse (float64)
        """
        _validate_account_no(account_no)
        if not symbol or not symbol.strip():
            raise BrokerValidationError(
                message="symbol không được để trống.",
                code="INVALID_SYMBOL",
            )
        price_str = str(int(price))
        path = _PATHS["ppse_symbol_price"].format(accountNo=account_no, symbol=symbol.upper(), price=price_str)
        data = self._get(path)

        if raw:
            return data

        row = {
            "account_no": data.get("accountNo", account_no),
            "symbol": symbol.upper(),
            "price": float(price),
            "max_quantity": int(data.get("maxQuantity") or 0),
            "ppse": float(data.get("ppse") or 0),
        }
        return pd.DataFrame([row]).astype({
            "price": "float64",
            "max_quantity": "Int64",
            "ppse": "float64",
        })

    def get_customer_accounts(
        self,
        custody_id: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, list]:
        """
        GET /aion/v1/customers/{custodyId}/accounts

        Hạn mức margin theo customer.

        Args:
            custody_id: Mã lưu ký (105C format).
            raw: True → trả về list nguyên gốc.

        Returns:
            DataFrame columns (raw=False):
                account_no, custody_id, margin_limit (float64),
                margin_used (float64), margin_available (float64),
                status (category)
        """
        if not custody_id or not custody_id.strip():
            raise BrokerValidationError(
                message="custody_id không được để trống.",
                code="INVALID_CUSTODY_ID",
            )
        path = _PATHS["customer_accounts"].format(custodyId=custody_id)
        data = self._get(path)

        if raw:
            return data

        records = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
        if not records:
            return pd.DataFrame(columns=[
                "account_no", "custody_id", "margin_limit", "margin_used",
                "margin_available", "status"
            ])

        df = pd.DataFrame(records)
        for col in ("margin_limit", "margin_used", "margin_available"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        if "status" in df.columns:
            df["status"] = df["status"].astype("category")
        return df

    def get_margin_risk(
        self,
        account_no: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /hydros/v1/account/{accountNo}/risk

        Tổng nợ gốc, Tổng nợ lãi, Rtt thực tế, Tỷ lệ ký quỹ ban đầu,
        Tỷ lệ duy trì, Tỷ lệ cảnh báo.

        Args:
            account_no: Số tiểu khoản 10 chữ số.
            raw: True → trả về dict nguyên gốc.

        Returns:
            DataFrame columns (raw=False):
                account_no, total_principal_debt (float64),
                total_interest_debt (float64), rtt_actual (float64),
                initial_margin_ratio (float64), maintenance_margin_ratio (float64),
                warning_margin_ratio (float64)
        """
        _validate_account_no(account_no)
        path = _PATHS["hydros_risk"].format(accountNo=account_no)
        data = self._get(path)

        if raw:
            return data

        records = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
        if not records:
            return pd.DataFrame(columns=[
                "account_no", "total_principal_debt", "total_interest_debt",
                "rtt_actual", "initial_margin_ratio", "maintenance_margin_ratio",
                "warning_margin_ratio"
            ])

        row = records[0] if isinstance(records, list) else records
        result = {
            "account_no": row.get("accountNo", account_no),
            "total_principal_debt": float(row.get("totalPrincipalDebt") or 0),
            "total_interest_debt": float(row.get("totalInterestDebt") or 0),
            "rtt_actual": float(row.get("rttActual") or 0),
            "initial_margin_ratio": float(row.get("initialMarginRatio") or 0),
            "maintenance_margin_ratio": float(row.get("maintenanceMarginRatio") or 0),
            "warning_margin_ratio": float(row.get("warningMarginRatio") or 0),
        }
        return pd.DataFrame([result]).astype({
            "total_principal_debt": "float64",
            "total_interest_debt": "float64",
            "rtt_actual": "float64",
            "initial_margin_ratio": "float64",
            "maintenance_margin_ratio": "float64",
            "warning_margin_ratio": "float64",
        })

    def get_margin_subscription_detail(
        self,
        account_no: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /campaign-management/v1/margin/subscription/{accountNo}/addons/detail

        Gói vay bổ trợ.

        Args:
            account_no: Số tiểu khoản 10 chữ số.
            raw: True → trả về dict nguyên gốc.

        Returns:
            DataFrame columns (raw=False):
                account_no, subscription_name (str),
                interest_rate (float64), max_amount (float64),
                status (category), start_date (str), end_date (str)
        """
        _validate_account_no(account_no)
        path = _PATHS["margin_subscription"].format(accountNo=account_no)
        data = self._get(path)

        if raw:
            return data

        row = {
            "account_no": data.get("accountNo", account_no),
            "subscription_name": data.get("subscriptionName", ""),
            "interest_rate": float(data.get("interestRate") or 0),
            "max_amount": float(data.get("maxAmount") or 0),
            "status": data.get("status", ""),
            "start_date": data.get("startDate", ""),
            "end_date": data.get("endDate", ""),
        }
        return pd.DataFrame([row]).astype({
            "interest_rate": "float64",
            "max_amount": "float64",
        })

    def get_loan_list(
        self,
        account_no: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, list]:
        """
        GET /khaos/v1/loan/{accountNo}

        Danh sách khoản vay.

        Args:
            account_no: Số tiểu khoản 10 chữ số.
            raw: True → trả về list nguyên gốc.

        Returns:
            DataFrame columns (raw=False):
                loan_id, account_no, amount (float64),
                interest_rate (float64), status (category),
                start_date (str), due_date (str), remaining_amount (float64)
        """
        _validate_account_no(account_no)
        path = _PATHS["loan_list"].format(accountNo=account_no)
        data = self._get(path)

        if raw:
            return data

        records = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
        if not records:
            return pd.DataFrame(columns=[
                "loan_id", "account_no", "amount", "interest_rate",
                "status", "start_date", "due_date", "remaining_amount"
            ])

        df = pd.DataFrame(records)
        for col in ("amount", "interest_rate", "remaining_amount"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        if "status" in df.columns:
            df["status"] = df["status"].astype("category")
        return df

    def get_cash_statements(
        self,
        account_no: str,
        from_date: str,
        to_date: str,
        page: int = 0,
        size: int = 25,
        transaction_code: str = "",
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /erebos/v2/digital/trans-hist-cashStatements

        Args:
            account_no: Số tiểu khoản 10 chữ số.
            from_date: Ngày bắt đầu (YYYY-MM-DD).
            to_date: Ngày kết thúc (YYYY-MM-DD).
            page: Trang (0-based).
            size: Số lượng mỗi trang.
            transaction_code: Mã giao dịch (tùy chọn).
            raw: True → trả về dict nguyên gốc.

        Returns:
            DataFrame columns (raw=False):
                transaction_id, account_no, amount (float64),
                transaction_code (str), description (str),
                tx_date (str), tx_time (str), balance_after (float64)
        """
        _validate_account_no(account_no)
        params: dict = {
            "accountNo": account_no,
            "fromDate": from_date,
            "toDate": to_date,
            "pageSize": size,
            "pageIndex": page,
        }
        if transaction_code:
            params["transactionCode"] = transaction_code

        data = self._get(_PATHS["cash_statements"], params=params)

        if raw:
            return data

        records = data.get("data", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        if not records:
            return pd.DataFrame(columns=[
                "transaction_id", "account_no", "amount", "transaction_code",
                "description", "tx_date", "tx_time", "balance_after"
            ])

        df = pd.DataFrame(records)
        for col in ("amount", "balance_after"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        return df

    def get_pricing_policy(
        self,
        account_no: str,
        product_id: int | None = None,
    ) -> dict[str, Any]:
        """
        GET /hydros/v1/account/{accountNo}/pricing-policy

        Args:
            account_no: Số tiểu khoản 10 chữ số.
            product_id: Product ID (query `productId`, tuỳ chọn theo spec).
                        None/rỗng → KHÔNG gửi, server tự suy ra từ tài khoản.

        Returns:
            Dict nguyên gốc. Spec KHÔNG mô tả schema response 200 (không có
            `content`) ⇒ không ép DataFrame, không bịa tên cột.
        """
        _validate_account_no(account_no)
        params: dict[str, Any] = {}
        if product_id is not None and str(product_id).strip():
            params["productId"] = product_id
        path = _PATHS["pricing_policy"].format(accountNo=account_no)
        return self._get(path, params=params)

    # ── Write methods (dry_run=True default) ────────────────────────────────
    # Pattern: validation chạy TRƯỚC write_gate check.
    # Public method validate → delegate sang @write_gate internal method.

    def deposit_margin(
        self,
        account_id: str,
        sub_account_id: str,
        amount: float,
        payment_content: str = "",
        *,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """
        POST /khronos/v1/cash/deposit/update

        Nạp tiền margin vào tài khoản phái sinh.

        Args:
            account_id: Số tài khoản lưu ký (bắt buộc theo spec).
            sub_account_id: Số tài khoản phái sinh (bắt buộc theo spec).
            amount: Số tiền nạp, phải > 0.
            payment_content: Mô tả giao dịch (tuỳ chọn — rỗng thì không gửi).
            dry_run: True (mặc định) → không gửi HTTP, trả envelope dry-run.
        """
        _require_text(account_id, "account_id", "INVALID_ACCOUNT_ID")
        _require_text(sub_account_id, "sub_account_id", "INVALID_SUB_ACCOUNT_ID")
        amount = _validate_amount(amount)
        return self._gated_deposit_margin(
            account_id, sub_account_id, amount, payment_content, dry_run=dry_run,
        )

    @write_gate
    def _gated_deposit_margin(
        self, account_id: str, sub_account_id: str, amount: float, payment_content: str,
        *, dry_run: bool = True,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "accountId": account_id, "subAccountId": sub_account_id, "amount": amount,
        }
        if payment_content:
            payload["paymentContent"] = payment_content
        return self._post(_PATHS["cash_deposit"], payload)

    def withdraw_margin(
        self,
        account_id: str,
        sub_account_id: str,
        amount: float,
        payment_content: str = "",
        *,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """
        POST /khronos/v1/cash/withdraw/update

        Rút tiền margin khỏi tài khoản phái sinh. Tham số giống deposit_margin().
        """
        _require_text(account_id, "account_id", "INVALID_ACCOUNT_ID")
        _require_text(sub_account_id, "sub_account_id", "INVALID_SUB_ACCOUNT_ID")
        amount = _validate_amount(amount)
        return self._gated_withdraw_margin(
            account_id, sub_account_id, amount, payment_content, dry_run=dry_run,
        )

    @write_gate
    def _gated_withdraw_margin(
        self, account_id: str, sub_account_id: str, amount: float, payment_content: str,
        *, dry_run: bool = True,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "accountId": account_id, "subAccountId": sub_account_id, "amount": amount,
        }
        if payment_content:
            payload["paymentContent"] = payment_content
        return self._post(_PATHS["cash_withdraw"], payload)

    def transfer_between_sub_accounts(
        self,
        source_account_number: str,
        destination_account_number: str,
        amount: float,
        description: str,
        *,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """
        POST /physis/v1/stock/transfer

        Chuyển tiền giữa các tài khoản con. Cả 4 field đều bắt buộc theo spec,
        amount phải > 0. dry_run=True (mặc định) → không gửi HTTP, trả envelope.
        """
        _require_text(source_account_number, "source_account_number", "INVALID_SOURCE_ACCOUNT")
        _require_text(destination_account_number, "destination_account_number", "INVALID_DESTINATION_ACCOUNT")
        _require_text(description, "description", "MISSING_DESCRIPTION")
        amount = _validate_amount(amount)
        return self._gated_transfer_between_sub_accounts(
            source_account_number, destination_account_number, amount, description,
            dry_run=dry_run,
        )

    @write_gate
    def _gated_transfer_between_sub_accounts(
        self, source_account_number: str, destination_account_number: str, amount: float,
        description: str, *, dry_run: bool = True,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "sourceAccountNumber": source_account_number,
            "destinationAccountNumber": destination_account_number,
            "amount": amount,
            "description": description,
        }
        return self._post(_PATHS["stock_transfer"], payload)

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

        self._check_status(resp)
        return resp.json()

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """
        POST JSON. Bản riêng của money.py — trùng lệnh với `_write_request` ở
        derivatives.py:714 và `_post` ở equity.py:651 (nợ nhân bản có sẵn, N8).
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
            resp = requests.post(
                url,
                json=payload,
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

        self._check_status(resp)
        data: dict[str, Any] = resp.json()
        return data

    def _check_status(self, resp: requests.Response) -> None:
        """Map status code → exception. Dùng chung cho _get và _post."""
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


# ── Helpers ──────────────────────────────────────────────────────────────────

def _validate_amount(amount: float) -> float:
    """amount bắt buộc theo spec và phải > 0. Trả về float đã chuẩn hoá."""
    try:
        value = float(amount)
    except (TypeError, ValueError) as exc:
        raise BrokerValidationError(
            message="amount phải là số.",
            code="INVALID_AMOUNT",
        ) from exc
    if value <= 0:
        raise BrokerValidationError(
            message="amount phải lớn hơn 0.",
            code="INVALID_AMOUNT",
        )
    return value


def _require_text(value: str, field: str, code: str) -> None:
    if not value or not value.strip():
        raise BrokerValidationError(
            message=f"{field} không được để trống.",
            code=code,
        )
