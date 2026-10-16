from typing import TYPE_CHECKING, Any, Dict
from typing import TYPE_CHECKING, Any, Dict, Optional

import requests

import pandas as pd
from pandas import json_normalize

from vnbroker.core.utils.logger import get_logger

# `get_logger` chua co type annotation (dong bo tai `core/utils/logger.py`),
# nen mypy strict bao loi o MOI module goi no. Loi nay da nam trong baseline
# cho cac file khac; file moi se lai khac duong dan nen bi tinh la `new`.
# Giu loi bang `ignore` co chu dich hon la phinh baseline cho file moi.
logger = get_logger(__name__)  # type: ignore[no-untyped-call]


"""Margin phái sinh — nạp, rút, cash account, công suất mua.

Tách khỏi `trade.py` ngày 2026-10-16 (file đó 1352 dòng, vượt trần 800L).
Cùng cách làm với `MultiMarketMixin` cho `DNSEClient` và `EquityWriteMixin`
cho `broker/tcbs/`.

⚠ **Đây là money lane.** `deposit_derivative_margin` và
`withdraw_derivative_margin` chuyển tiền thật. Cả hai đều gọi
`self._require_write`, hàm đó **không** nằm ở file này mà ở `Trade` — tức
lát tách này **không được** làm yếu hàng rào đó đi một bước.
"""

class DerivativeMixin:
    """Margin phái sinh. Cần `Trade` cung cấp `_require_write`.
    """
    # `TIMEOUT` va `_api_base_url` thuoc `Trade` (xem `trade.py`).
    # Khai bao duoi `TYPE_CHECKING` de mypp biet ma khong gan gia tri That —
    # gan gia tri o cap class se che mat `_require_write` cua `Trade`.
    if TYPE_CHECKING:
        TIMEOUT: int
        token: Optional[str]
        _api_base_url: str

        def _require_write(
            self, operation: str, dry_run: bool
        ) -> Optional[Dict[str, Any]]: ...



    def deposit_derivative_margin(
        self,
        account_no: str,
        source_account_no: str,
        loan_package_id: int,
        amount: int,
        via: str,
        otp: str
    , dry_run: bool = True,) -> Optional[pd.DataFrame]:
        """
        Deposit margin for derivative trading.

        Args:
            account_no (str): Sub account number.
            source_account_no (str): Source sub account number.
            loan_package_id (int): Loan package ID.
            amount (int): Deposit amount.
            via (str): Transaction channel.
            otp (str): Smart OTP from Entrade X app.

        Returns:
            Optional[pd.DataFrame]: DataFrame with result if successful,
                None otherwise.
        """
        # P0-2: nạp ký quỹ = tiền thật vào tài khoản phái sinh.
        _dry = self._require_write("deposit_derivative_margin", dry_run)
        if _dry is not None:
            return _dry
        url = f"{self._api_base_url}/derivative-asset-service/deposit"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "smart-otp": otp
        }
        payload = {
            "accountNo": account_no,
            "sourceAccountNo": source_account_no,
            "loanPackageId": loan_package_id,
            "amount": amount,
            "via": via
        }
        response = requests.post(url, headers=headers, json=payload, timeout=self.TIMEOUT)
        if response.status_code == 200:
            logger.info("Nạp margin thành công")
            return json_normalize(response.json())
        else:
            logger.error("Nạp margin thất bại: %s", response.text)
            return None

    def withdraw_derivative_margin(
        self,
        account_no: str,
        source_account_no: str,
        loan_package_id: int,
        amount: int,
        via: str,
        otp: str
    , dry_run: bool = True,) -> Optional[pd.DataFrame]:
        """
        Withdraw margin from derivative trading.

        Args:
            account_no (str): Sub account number.
            source_account_no (str): Source sub account number.
            loan_package_id (int): Loan package ID.
            amount (int): Withdrawal amount.
            via (str): Transaction channel.
            otp (str): Smart OTP from Entrade X app.

        Returns:
            Optional[pd.DataFrame]: DataFrame with result if successful,
                None otherwise.
        """
        # P0-2: rút ký quỹ = tiền thật ra khỏi tài khoản.
        _dry = self._require_write("withdraw_derivative_margin", dry_run)
        if _dry is not None:
            return _dry
        url = f"{self._api_base_url}/derivative-asset-service/withdraw"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "smart-otp": otp
        }
        payload = {
            "accountNo": account_no,
            "sourceAccountNo": source_account_no,
            "loanPackageId": loan_package_id,
            "amount": amount,
            "via": via
        }
        response = requests.post(url, headers=headers, json=payload, timeout=self.TIMEOUT)
        if response.status_code == 200:
            logger.info("Rút margin thành công")
            return json_normalize(response.json())
        else:
            logger.error("Rút margin thất bại: %s", response.text)
            return None

    def get_derivative_cash_account(
        self,
        account_no: str
    ) -> Optional[pd.DataFrame]:
        """
        Get derivative cash account information.

        This endpoint provides cash account details including:
        - vsdSecure, DNSESecure
        - holdCollateralFee, holdDailyRealizedTradingTaxAndFee
        - totalLoanDebt
        - dailyRealizedProfit, dailyRealizedTradingFee
        - dailyRealizedTradingTax, positionFee, maturityFee
        - profitVmReceiving

        Args:
            account_no (str): Sub account number.

        Returns:
            Optional[pd.DataFrame]: DataFrame with cash account info if
                successful, None otherwise.
        """
        url = f"{self._api_base_url}/derivative-core/cash-accounts"
        url += f"?accountNo={account_no}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "accept": "application/json, text/plain,/"
        }
        response = requests.get(url, headers=headers, timeout=self.TIMEOUT)
        if response.status_code == 200:
            return json_normalize(response.json())
        else:
            logger.error("Lấy derivative cash account thất bại: %s", response.text)
            return None

    def get_derivative_ppse(
        self,
        account_no: str,
        loan_package_id: int
    ) -> Optional[pd.DataFrame]:
        """
        Get derivative buying power (PP0) information.

        This endpoint provides:
        - PP0 (remaining margin)
        - awaitingDepositCash

        Args:
            account_no (str): Sub account number.
            loan_package_id (int): Loan package ID.

        Returns:
            Optional[pd.DataFrame]: DataFrame with PP0 info if successful,
                None otherwise.
        """
        url = f"{self._api_base_url}/derivative-core/ppse"
        url += f"?loanPackageId={loan_package_id}&accountNo={account_no}"
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url, headers=headers, timeout=self.TIMEOUT)
        if response.status_code == 200:
            return json_normalize(response.json())
        else:
            logger.error("Lấy derivative ppse thất bại: %s", response.text)
            return None
