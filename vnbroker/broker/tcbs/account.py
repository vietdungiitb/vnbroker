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
    # Erebos v1 account endpoints
    "erebos_v1_asset": "/erebos/v1/account/asset",
    "erebos_v1_available_balance": "/erebos/v1/account/available-balance",
    "erebos_v1_portfolio_asset": "/erebos/v1/portfolio-asset",
    "erebos_v1_portfolio_asset_token": "/erebos/v1/portfolio-asset/token",
    "erebos_v1_portfolio_stock_statistic": "/erebos/v1/portfolio/stock/{accountNo}/statistic",
    # Erebos v2 account endpoints
    "erebos_v2_asset": "/erebos/v2/accounts/{accountNo}/asset",
    "erebos_v2_available_balance": "/erebos/v2/accounts/{accountNo}/available-balance",
    "erebos_v2_stock_statistic": "/erebos/v2/accounts/{accountNo}/stock-statistic",
    "erebos_v2_orders_history": "/erebos/v2/accounts/{accountNo}/orders/history",
    "erebos_v2_orders_matching": "/erebos/v2/accounts/{accountNo}/orders/matching",
    "erebos_v2_withdraw": "/erebos/v2/accounts/{accountNo}/withdraw",
    "erebos_v2_deposit": "/erebos/v2/accounts/{accountNo}/deposit",
    "erebos_v2_dividend": "/erebos/v2/accounts/{accountNo}/dividend",
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

    # ── Erebos v1 Account Endpoints ───────────────────────────────────────────

    def get_erebos_v1_asset(
        self,
        account_no: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /erebos/v1/account/asset

        Args:
            account_no: Số tiểu khoản 10 chữ số.
            raw: True → trả về dict nguyên gốc.

        Returns:
            DataFrame columns (raw=False):
                account_no, total_asset (float64), cash_balance (float64),
                stock_value (float64), margin_balance (float64)
        """
        _validate_account_no(account_no)
        data = self._get(_PATHS["erebos_v1_asset"], params={"accountNo": account_no})

        if raw:
            return data

        row = {
            "account_no": data.get("accountNo", account_no),
            "total_asset": float(data.get("totalAsset") or 0),
            "cash_balance": float(data.get("cashBalance") or 0),
            "stock_value": float(data.get("stockValue") or 0),
            "margin_balance": float(data.get("marginBalance") or 0),
        }
        return pd.DataFrame([row]).astype({
            "total_asset": "float64",
            "cash_balance": "float64",
            "stock_value": "float64",
            "margin_balance": "float64",
        })

    def get_erebos_v1_available_balance(
        self,
        account_no: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /erebos/v1/account/available-balance

        Args:
            account_no: Số tiểu khoản 10 chữ số.
            raw: True → trả về dict nguyên gốc.

        Returns:
            DataFrame columns (raw=False):
                account_no, available_balance (float64),
                buying_power (float64), withdrawable_balance (float64)
        """
        _validate_account_no(account_no)
        data = self._get(_PATHS["erebos_v1_available_balance"], params={"accountNo": account_no})

        if raw:
            return data

        row = {
            "account_no": data.get("accountNo", account_no),
            "available_balance": float(data.get("availableBalance") or 0),
            "buying_power": float(data.get("buyingPower") or 0),
            "withdrawable_balance": float(data.get("withdrawableBalance") or 0),
        }
        return pd.DataFrame([row]).astype({
            "available_balance": "float64",
            "buying_power": "float64",
            "withdrawable_balance": "float64",
        })

    def get_erebos_v1_portfolio_asset(
        self,
        account_no: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, list]:
        """
        GET /erebos/v1/portfolio-asset

        Args:
            account_no: Số tiểu khoản 10 chữ số.
            raw: True → trả về list nguyên gốc.

        Returns:
            DataFrame columns (raw=False):
                symbol, sec_type, quantity (Int64), average_cost (float64),
                market_price (float64), market_value (float64),
                unrealized_pnl (float64), unrealized_pnl_pct (float64)
        """
        _validate_account_no(account_no)
        data = self._get(_PATHS["erebos_v1_portfolio_asset"], params={"accountNo": account_no})

        if raw:
            return data

        records = data if isinstance(data, list) else data.get("data", [])
        if not records:
            return pd.DataFrame(columns=[
                "symbol", "sec_type", "quantity", "average_cost",
                "market_price", "market_value", "unrealized_pnl", "unrealized_pnl_pct"
            ])

        df = pd.DataFrame(records)
        for col in ("quantity",):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        for col in ("average_cost", "market_price", "market_value", "unrealized_pnl", "unrealized_pnl_pct"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        return df

    def get_erebos_v1_portfolio_asset_token(
        self,
        account_no: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, list]:
        """
        GET /erebos/v1/portfolio-asset/token

        Danh mục phái sinh & chứng quyền.

        Args:
            account_no: Số tiểu khoản 10 chữ số.
            raw: True → trả về list nguyên gốc.

        Returns:
            DataFrame columns (raw=False):
                symbol, sec_type, quantity (Int64), average_cost (float64),
                market_price (float64), market_value (float64),
                unrealized_pnl (float64)
        """
        _validate_account_no(account_no)
        data = self._get(_PATHS["erebos_v1_portfolio_asset_token"], params={"accountNo": account_no})

        if raw:
            return data

        records = data if isinstance(data, list) else data.get("data", [])
        if not records:
            return pd.DataFrame(columns=[
                "symbol", "sec_type", "quantity", "average_cost",
                "market_price", "market_value", "unrealized_pnl"
            ])

        df = pd.DataFrame(records)
        for col in ("quantity",):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        for col in ("average_cost", "market_price", "market_value", "unrealized_pnl"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        return df

    def get_erebos_v1_portfolio_stock_statistic(
        self,
        account_no: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /erebos/v1/portfolio/stock/{accountNo}/statistic

        Args:
            account_no: Số tiểu khoản 10 chữ số.
            raw: True → trả về dict nguyên gốc.

        Returns:
            DataFrame columns (raw=False):
                account_no, total_stock_value (float64),
                total_unrealized_pnl (float64), total_unrealized_pnl_pct (float64),
                num_positions (Int64), top_gainer (str), top_loser (str)
        """
        _validate_account_no(account_no)
        path = _PATHS["erebos_v1_portfolio_stock_statistic"].format(accountNo=account_no)
        data = self._get(path)

        if raw:
            return data

        row = {
            "account_no": data.get("accountNo", account_no),
            "total_stock_value": float(data.get("totalStockValue") or 0),
            "total_unrealized_pnl": float(data.get("totalUnrealizedPnl") or 0),
            "total_unrealized_pnl_pct": float(data.get("totalUnrealizedPnlPct") or 0),
            "num_positions": int(data.get("numPositions") or 0),
            "top_gainer": data.get("topGainer", ""),
            "top_loser": data.get("topLoser", ""),
        }
        return pd.DataFrame([row]).astype({
            "total_stock_value": "float64",
            "total_unrealized_pnl": "float64",
            "total_unrealized_pnl_pct": "float64",
            "num_positions": "Int64",
        })

    # ── Erebos v2 Account Endpoints ───────────────────────────────────────────

    def get_erebos_v2_asset(
        self,
        account_no: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /erebos/v2/accounts/{accountNo}/asset

        Args:
            account_no: Số tiểu khoản 10 chữ số.
            raw: True → trả về dict nguyên gốc.

        Returns:
            DataFrame columns (raw=False):
                account_no, total_asset (float64), cash_balance (float64),
                stock_value (float64), derivative_balance (float64),
                margin_balance (float64)
        """
        _validate_account_no(account_no)
        path = _PATHS["erebos_v2_asset"].format(accountNo=account_no)
        data = self._get(path)

        if raw:
            return data

        row = {
            "account_no": data.get("accountNo", account_no),
            "total_asset": float(data.get("totalAsset") or 0),
            "cash_balance": float(data.get("cashBalance") or 0),
            "stock_value": float(data.get("stockValue") or 0),
            "derivative_balance": float(data.get("derivativeBalance") or 0),
            "margin_balance": float(data.get("marginBalance") or 0),
        }
        return pd.DataFrame([row]).astype({
            "total_asset": "float64",
            "cash_balance": "float64",
            "stock_value": "float64",
            "derivative_balance": "float64",
            "margin_balance": "float64",
        })

    def get_erebos_v2_available_balance(
        self,
        account_no: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /erebos/v2/accounts/{accountNo}/available-balance

        Args:
            account_no: Số tiểu khoản 10 chữ số.
            raw: True → trả về dict nguyên gốc.

        Returns:
            DataFrame columns (raw=False):
                account_no, available_balance (float64),
                buying_power (float64), withdrawable_balance (float64),
                margin_available (float64)
        """
        _validate_account_no(account_no)
        path = _PATHS["erebos_v2_available_balance"].format(accountNo=account_no)
        data = self._get(path)

        if raw:
            return data

        row = {
            "account_no": data.get("accountNo", account_no),
            "available_balance": float(data.get("availableBalance") or 0),
            "buying_power": float(data.get("buyingPower") or 0),
            "withdrawable_balance": float(data.get("withdrawableBalance") or 0),
            "margin_available": float(data.get("marginAvailable") or 0),
        }
        return pd.DataFrame([row]).astype({
            "available_balance": "float64",
            "buying_power": "float64",
            "withdrawable_balance": "float64",
            "margin_available": "float64",
        })

    def get_erebos_v2_stock_statistic(
        self,
        account_no: str,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /erebos/v2/accounts/{accountNo}/stock-statistic

        Args:
            account_no: Số tiểu khoản 10 chữ số.
            raw: True → trả về dict nguyên gốc.

        Returns:
            DataFrame columns (raw=False):
                account_no, total_stock_value (float64),
                total_unrealized_pnl (float64), total_unrealized_pnl_pct (float64),
                num_positions (Int64), top_gainer (str), top_loser (str)
        """
        _validate_account_no(account_no)
        path = _PATHS["erebos_v2_stock_statistic"].format(accountNo=account_no)
        data = self._get(path)

        if raw:
            return data

        row = {
            "account_no": data.get("accountNo", account_no),
            "total_stock_value": float(data.get("totalStockValue") or 0),
            "total_unrealized_pnl": float(data.get("totalUnrealizedPnl") or 0),
            "total_unrealized_pnl_pct": float(data.get("totalUnrealizedPnlPct") or 0),
            "num_positions": int(data.get("numPositions") or 0),
            "top_gainer": data.get("topGainer", ""),
            "top_loser": data.get("topLoser", ""),
        }
        return pd.DataFrame([row]).astype({
            "total_stock_value": "float64",
            "total_unrealized_pnl": "float64",
            "total_unrealized_pnl_pct": "float64",
            "num_positions": "Int64",
        })

    def get_erebos_v2_orders_history(
        self,
        account_no: str,
        from_date: str = "",
        to_date: str = "",
        page: int = 0,
        size: int = 50,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /erebos/v2/accounts/{accountNo}/orders/history

        Args:
            account_no: Số tiểu khoản 10 chữ số.
            from_date: Ngày bắt đầu (YYYY-MM-DD).
            to_date: Ngày kết thúc (YYYY-MM-DD).
            page: Trang (0-based).
            size: Số lượng mỗi trang.
            raw: True → trả về dict nguyên gốc.

        Returns:
            DataFrame columns (raw=False):
                order_id, symbol, side (category), order_type (category),
                quantity (Int64), filled_quantity (Int64), price (float64),
                status (category), tx_date (str), tx_time (str)
        """
        _validate_account_no(account_no)
        path = _PATHS["erebos_v2_orders_history"].format(accountNo=account_no)
        params: dict = {"page": page, "size": size}
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date

        data = self._get(path, params=params)

        if raw:
            return data

        records = data.get("data", []) if isinstance(data, dict) else data
        if not records:
            return pd.DataFrame(columns=[
                "order_id", "symbol", "side", "order_type",
                "quantity", "filled_quantity", "price", "status", "tx_date", "tx_time"
            ])

        df = pd.DataFrame(records)
        for col in ("quantity", "filled_quantity"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        if "price" in df.columns:
            df["price"] = pd.to_numeric(df["price"], errors="coerce").astype("float64")
        for col in ("side", "order_type", "status"):
            if col in df.columns:
                df[col] = df[col].astype("category")
        return df

    def get_erebos_v2_orders_matching(
        self,
        account_no: str,
        from_date: str = "",
        to_date: str = "",
        page: int = 0,
        size: int = 50,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /erebos/v2/accounts/{accountNo}/orders/matching

        Args:
            account_no: Số tiểu khoản 10 chữ số.
            from_date: Ngày bắt đầu (YYYY-MM-DD).
            to_date: Ngày kết thúc (YYYY-MM-DD).
            page: Trang (0-based).
            size: Số lượng mỗi trang.
            raw: True → trả về dict nguyên gốc.

        Returns:
            DataFrame columns (raw=False):
                order_id, trade_id, symbol, side (category),
                quantity (Int64), price (float64),
                fee (float64), tx_date (str), tx_time (str)
        """
        _validate_account_no(account_no)
        path = _PATHS["erebos_v2_orders_matching"].format(accountNo=account_no)
        params: dict = {"page": page, "size": size}
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date

        data = self._get(path, params=params)

        if raw:
            return data

        records = data.get("data", []) if isinstance(data, dict) else data
        if not records:
            return pd.DataFrame(columns=[
                "order_id", "trade_id", "symbol", "side",
                "quantity", "price", "fee", "tx_date", "tx_time"
            ])

        df = pd.DataFrame(records)
        if "quantity" in df.columns:
            df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").astype("Int64")
        for col in ("price", "fee"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        if "side" in df.columns:
            df["side"] = df["side"].astype("category")
        return df

    def get_erebos_v2_withdraw_history(
        self,
        account_no: str,
        from_date: str = "",
        to_date: str = "",
        page: int = 0,
        size: int = 50,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /erebos/v2/accounts/{accountNo}/withdraw

        Args:
            account_no: Số tiểu khoản 10 chữ số.
            from_date: Ngày bắt đầu (YYYY-MM-DD).
            to_date: Ngày kết thúc (YYYY-MM-DD).
            page: Trang (0-based).
            size: Số lượng mỗi trang.
            raw: True → trả về dict nguyên gốc.

        Returns:
            DataFrame columns (raw=False):
                withdraw_id, account_no, amount (float64),
                bank_account (str), status (category),
                tx_date (str), tx_time (str)
        """
        _validate_account_no(account_no)
        path = _PATHS["erebos_v2_withdraw"].format(accountNo=account_no)
        params: dict = {"page": page, "size": size}
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date

        data = self._get(path, params=params)

        if raw:
            return data

        records = data.get("data", []) if isinstance(data, dict) else data
        if not records:
            return pd.DataFrame(columns=[
                "withdraw_id", "account_no", "amount", "bank_account", "status", "tx_date", "tx_time"
            ])

        df = pd.DataFrame(records)
        if "amount" in df.columns:
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce").astype("float64")
        if "status" in df.columns:
            df["status"] = df["status"].astype("category")
        return df

    def get_erebos_v2_deposit_history(
        self,
        account_no: str,
        from_date: str = "",
        to_date: str = "",
        page: int = 0,
        size: int = 50,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /erebos/v2/accounts/{accountNo}/deposit

        Args:
            account_no: Số tiểu khoản 10 chữ số.
            from_date: Ngày bắt đầu (YYYY-MM-DD).
            to_date: Ngày kết thúc (YYYY-MM-DD).
            page: Trang (0-based).
            size: Số lượng mỗi trang.
            raw: True → trả về dict nguyên gốc.

        Returns:
            DataFrame columns (raw=False):
                deposit_id, account_no, amount (float64),
                bank_account (str), status (category),
                tx_date (str), tx_time (str)
        """
        _validate_account_no(account_no)
        path = _PATHS["erebos_v2_deposit"].format(accountNo=account_no)
        params: dict = {"page": page, "size": size}
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date

        data = self._get(path, params=params)

        if raw:
            return data

        records = data.get("data", []) if isinstance(data, dict) else data
        if not records:
            return pd.DataFrame(columns=[
                "deposit_id", "account_no", "amount", "bank_account", "status", "tx_date", "tx_time"
            ])

        df = pd.DataFrame(records)
        if "amount" in df.columns:
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce").astype("float64")
        if "status" in df.columns:
            df["status"] = df["status"].astype("category")
        return df

    def get_erebos_v2_dividend_history(
        self,
        account_no: str,
        from_date: str = "",
        to_date: str = "",
        page: int = 0,
        size: int = 50,
        raw: bool = False,
    ) -> Union[pd.DataFrame, dict]:
        """
        GET /erebos/v2/accounts/{accountNo}/dividend

        Args:
            account_no: Số tiểu khoản 10 chữ số.
            from_date: Ngày bắt đầu (YYYY-MM-DD).
            to_date: Ngày kết thúc (YYYY-MM-DD).
            page: Trang (0-based).
            size: Số lượng mỗi trang.
            raw: True → trả về dict nguyên gốc.

        Returns:
            DataFrame columns (raw=False):
                symbol, dividend_type (str), ratio (float64),
                amount (float64), ex_date (str), payment_date (str)
        """
        _validate_account_no(account_no)
        path = _PATHS["erebos_v2_dividend"].format(accountNo=account_no)
        params: dict = {"page": page, "size": size}
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date

        data = self._get(path, params=params)

        if raw:
            return data

        records = data.get("data", []) if isinstance(data, dict) else data
        if not records:
            return pd.DataFrame(columns=[
                "symbol", "dividend_type", "ratio", "amount", "ex_date", "payment_date"
            ])

        df = pd.DataFrame(records)
        for col in ("ratio", "amount"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        return df

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
