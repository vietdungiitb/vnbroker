from typing import TYPE_CHECKING, Any, Dict, List, Optional

from vnbroker.core.utils.logger import get_logger

# `get_logger` chua co type annotation (dong bo tai `core/utils/logger.py`),
# nen mypy strict bao loi o MOI module goi no. Loi nay da nam trong baseline
# cho cac file khac; file moi se lai khac duong dan nen bi tinh la `new`.
# Giu loi bang `ignore` co chu dich hon la phinh baseline cho file moi.
logger = get_logger(__name__)  # type: ignore[no-untyped-call]

import requests

import pandas as pd
from pandas import json_normalize


class ConditionalOrderMixin:
    """Lệnh điều kiện. Cần `Trade` cung cấp `_require_write`.
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



    def place_conditional_order(
        self,
        account_no: str,
        symbol: str,
        condition: str,
        target_order: Dict[str, Any],
        props: Dict[str, Any],
        time_in_force: Dict[str, Any],
        category: str = "STOP",
        dry_run: bool = False,
    ) -> Optional[pd.DataFrame]:
        """
        Place a conditional order.

        Args:
            account_no (str): Sub account number.
            symbol (str): Stock symbol.
            condition (str): Condition string, e.g. 'price <= 26650'.
            target_order (dict): Target order config with keys:
                - quantity (int): Order quantity
                - side (str): 'NB' (buy) or 'NS' (sell)
                - price (float): Order price
                - loanPackageId (int): Loan package ID
                - orderType (str): 'LO' or 'MP/MTL'
            props (dict): Properties with keys:
                - stopPrice (float): Trigger price
                - marketId (str): 'UNDERLYING' or 'DERIVATIVES'
            time_in_force (dict): Time config with keys:
                - expireTime (str): Expiration time ISO format
                - kind (str): 'GTD'
            category (str): Order category. Default is 'STOP'.

        Returns:
            Optional[pd.DataFrame]: DataFrame with order ID if successful,
                None otherwise.
        """
        _dry = self._require_write("place_conditional_order", dry_run)
        if _dry is not None:
            return _dry

        url = f"{self._api_base_url}/conditional-order-api/v1/orders"
        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {
            "condition": condition,
            "targetOrder": target_order,
            "symbol": symbol,
            "props": props,
            "accountNo": account_no,
            "category": category,
            "timeInForce": time_in_force
        }
        response = requests.post(url, headers=headers, json=payload, timeout=self.TIMEOUT)
        if response.status_code == 200:
            logger.info("Đặt conditional order thành công")
            return json_normalize(response.json())
        else:
            logger.error("Đặt conditional order thất bại: %s", response.text)
            return None

    def conditional_order_list(
        self,
        account_no: str,
        market_id: str,
        daily: bool = False,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page: int = 1,
        size: int = 10000,
        status: Optional[List[Any]] = None,
        symbol: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """
        Get list of conditional orders.

        Args:
            account_no (str): Sub account number.
            market_id (str): 'UNDERLYING' (stock) or 'DERIVATIVES'.
            daily (bool): Get today's orders only. Default False.
            from_date (Optional[str]): Start date 'yyyy-MM-dd'.
            to_date (Optional[str]): End date 'yyyy-MM-dd'.
            page (int): Page number. Default 1.
            size (int): Items per page. Default 10000.
            status (Optional[list]): Order statuses list:
                NEW/ACTIVATED/REJECTED/CANCELLED/EXPIRED/FAILED/
                CANCELLED_BY_RIGHTS_EVENT
            symbol (Optional[str]): Stock symbol filter.

        Returns:
            Optional[pd.DataFrame]: DataFrame with order list if successful,
                None otherwise.
        """
        url = f"{self._api_base_url}/conditional-order-api/v1/orders"
        headers = {"Authorization": f"Bearer {self.token}"}
        # Annotate rõ kiểu: không có thì mypy suy ra dict[str, object], không
        # khớp chữ ký `params` của requests (SupportsItems[str, ...]).
        params: Dict[str, Any] = {
            "accountNo": account_no,
            "marketId": market_id,
            "daily": daily,
            "page": page,
            "size": size
        }
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if status:
            params["status"] = status
        if symbol:
            params["symbol"] = symbol

        response = requests.get(url, headers=headers, params=params, timeout=self.TIMEOUT)
        if response.status_code == 200:
            result = response.json()
            return json_normalize(result.get('content', []))
        else:
            logger.error("Lấy danh sách conditional orders thất bại: %s", response.text)
            return None

    def conditional_order_detail(
        self,
        order_id: str
    ) -> Optional[pd.DataFrame]:
        """
        Get details of a specific conditional order.

        Args:
            order_id (str): Conditional order ID.

        Returns:
            Optional[pd.DataFrame]: DataFrame with order details if
                successful, None otherwise.
        """
        url = f"{self._api_base_url}/conditional-order-api/v1/orders/{order_id}"
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url, headers=headers, timeout=self.TIMEOUT)
        if response.status_code == 200:
            return json_normalize(response.json())
        else:
            logger.error("Lấy chi tiết conditional order thất bại: %s", response.text)
            return None

    def cancel_conditional_order(
        self,
        order_id: str,
        dry_run: bool = False,
    ) -> Optional[pd.DataFrame]:
        """
        Cancel a conditional order.

        Args:
            order_id (str): Conditional order ID to cancel.

        Returns:
            Optional[pd.DataFrame]: DataFrame with result if successful,
                None otherwise.
        """
        _dry = self._require_write("cancel_conditional_order", dry_run)
        if _dry is not None:
            return _dry

        url = f"{self._api_base_url}/conditional-order-api/v1/orders/"
        url += f"{order_id}/cancel"
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.patch(url, headers=headers, timeout=self.TIMEOUT)
        if response.status_code == 200:
            logger.info("Huỷ conditional order thành công")
            return json_normalize(response.json())
        else:
            logger.error("Huỷ conditional order thất bại: %s", response.text)
            return None
