import json

from typing import Any, Dict, Optional

import requests

import pandas as pd
from pandas import json_normalize

from vnbroker.config import Config
from vnbroker.connector.dnse.client import DNSEClient


from vnbroker.connector.dnse.client import DNSEClient

from vnbroker.connector.dnse.openapi_passthrough import (
    OpenApiPassthroughMixin,
)
from vnbroker.connector.dnse.trade_conditional import (
    ConditionalOrderMixin,
)
from vnbroker.connector.dnse.trade_derivatives import DerivativeMixin

from vnbroker.core.utils.logger import get_logger

logger = get_logger(__name__)


class Trade(OpenApiPassthroughMixin, ConditionalOrderMixin, DerivativeMixin):
    """API private cũ của DNSE (JWT + OTP). Xem `openapi_passthrough.py`
    cho phần chỉ đọc/ghi qua OpenAPI.
    """

    BASE_URL = "https://api.dnse.com.vn"
    TIMEOUT = Config.REQUEST_TIMEOUT

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_url: str = "https://openapi.dnse.com.vn",
        api_base_url: Optional[str] = None,
    ) -> None:
        self.token: Optional[str] = None
        self.trading_token: Optional[str] = None
        self._openapi_client: Optional[DNSEClient] = None
        self._api_key = api_key
        # Legacy DNSE API family (auth-service / order-service / deal-service /
        # conditional-order-api). Distinct from `base_url`, which is the newer
        # OpenAPI host the provider's own SDK documents. Settable per instance so
        # a sandbox or a test can intercept it; defaults to the class constant.
        self._api_base_url = api_base_url or self.BASE_URL
        self._api_secret = api_secret
        self._openapi_base_url = base_url
        # P0-2: đường GHI phải có hàng rào. Trước đây place_order /
        # cancel_order / deposit_derivative_margin / withdraw_derivative_margin
        # gửi thật ngay lập tức, không cần dry_run cũng không cần bật quyền.
        self._write_enabled = False

    def enable_write(self, enabled: bool = True) -> None:
        """Bật/tắt quyền thực thi lệnh thật.

        Mặc định là TẮT. Đặt lệnh hay rút tiền phải là hành động có chủ đích —
        không phải chuyện xảy ra do gọi nhầm.

        Example:
            >>> trade.enable_write()          # cho phép gửi thật
            >>> trade.place_order(..., dry_run=False)
        """
        self._write_enabled = enabled

    def _require_write(self, operation: str, dry_run: bool) -> Optional[Dict[str, Any]]:
        """Trả về envelope dry-run, hoặc ``None`` nếu được phép gửi thật.

        Raises:
            BrokerPermissionError: khi ``dry_run=False`` nhưng chưa ``enable_write()``.
        """
        if dry_run:
            return {
                "dry_run": True,
                "operation": operation,
                "message": (
                    f"[DRY_RUN] {operation} — lệnh KHÔNG được gửi. "
                    f"Gọi trade.enable_write() và truyền dry_run=False để thực thi."
                ),
            }
        if not self._write_enabled:
            from vnbroker.broker.exceptions import BrokerPermissionError

            raise BrokerPermissionError(
                message=(
                    f"{operation} chưa được phép. Gọi trade.enable_write() "
                    f"trước khi gửi lệnh thật."
                ),
                code="WRITE_NOT_ENABLED",
            )
        return None

    def _get_openapi_client(self) -> DNSEClient:
        if self._openapi_client is None:
            if not self._api_key or not self._api_secret:
                raise ValueError(
                    "api_key and api_secret are required for DNSE OpenAPI methods"
                )
            self._openapi_client = DNSEClient(
                api_key=self._api_key,
                api_secret=self._api_secret,
                base_url=self._openapi_base_url,
                write_enabled=self._write_enabled,
            )
        return self._openapi_client

    def as_openapi_client(self, api_key: str, api_secret: str) -> DNSEClient:
        """Create a DNSE OpenAPI client for authenticated market and order calls.

        The returned client carries this `Trade`'s write permission. Before
        PM-01 it carried none, so this public method was a one-line way past
        the gate: the client had no `_write_enabled` and every one of its money
        methods defaulted to `dry_run=False`.
        """
        return DNSEClient(
            api_key=api_key,
            api_secret=api_secret,
            base_url=self._openapi_base_url,
            write_enabled=self._write_enabled,
        )

    def login(self, user_name: str, password: str) -> Optional[str]:
        """
        Authenticate the user and obtain a JWT token for API requests.

        Args:
            user_name (str): DNSE username (custody code, email, or phone).
            password (str): Your DNSE password.

        Returns:
            Optional[str]: JWT token if successful, None otherwise.
        """
        url = f"{self._api_base_url}/auth-service/login"
        payload = json.dumps({'username': user_name, 'password': password})
        headers = {'Content-Type': 'application/json'}
        response = requests.post(url, headers=headers, data=payload, timeout=self.TIMEOUT)
        if response.status_code == 200:
            logger.info("Đăng nhập DNSE thành công")
            self.token = response.json().get('token')
            return self.token
        else:
            logger.error("Đăng nhập DNSE thất bại: %s", response.text)
            return None

    def account(self) -> Optional[pd.DataFrame]:
        """
        Get the full user profile from DNSE.

        Returns:
            Optional[pd.DataFrame]: DataFrame with user profile if successful,
                None otherwise.
        """
        url = f"{self._api_base_url}/user-service/api/me"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.token}'
        }
        response = requests.get(url, headers=headers, timeout=self.TIMEOUT)
        if response.status_code == 200:
            logger.info("Lấy hồ sơ tài khoản thành công")
            return pd.DataFrame(response.json(), index=[0])
        else:
            logger.error("Lấy hồ sơ tài khoản thất bại: %s", response.text)
            return None

    def sub_accounts(self) -> Optional[pd.DataFrame]:
        """
        Get sub-accounts information.

        Returns:
            Optional[pd.DataFrame]: DataFrame with sub-accounts info if
                successful, None otherwise.
        """
        url = f"{self._api_base_url}/order-service/accounts"
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url, headers=headers, timeout=self.TIMEOUT)
        if response.status_code == 200:
            result = response.json()
            return json_normalize(result.get('accounts', []))
        else:
            logger.error("Lấy sub-accounts thất bại: %s", response.text)
            return None

    def account_balance(self, sub_account: str) -> Optional[pd.DataFrame]:
        """
        Get account balance for a specific sub-account.

        Args:
            sub_account (str): DNSE sub account number.

        Returns:
            Optional[pd.DataFrame]: DataFrame with account balance if
                successful, None otherwise.
        """
        url = f"{self._api_base_url}/order-service/account-balances/{sub_account}"
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url, headers=headers, timeout=self.TIMEOUT)
        if response.status_code == 200:
            result = response.json()
            return json_normalize(result)
        else:
            logger.error("Lấy account balance thất bại: %s", response.text)
            return None

    def email_otp(self) -> None:
        """
        Trigger an email OTP request to DNSE.

        The OTP will be sent to the email address associated with
        the DNSE account.
        """
        url = f"{self._api_base_url}/auth-service/api/email-otp"
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url, headers=headers, timeout=self.TIMEOUT)
        if response.status_code == 200:
            logger.info("OTP đã được gửi tới email")
        else:
            logger.error("Gửi OTP thất bại: %s", response.text)

    def get_trading_token(
        self,
        otp: str,
        smart_otp: bool = True
    ) -> Optional[str]:
        """
        Authenticate using OTP and get the trading token.

        Args:
            otp (str): OTP code for authentication. Input as a string.
            smart_otp (bool): Indicates if smart OTP is used. Default True.

        Returns:
            Optional[str]: Trading token if successful, None otherwise.
        """
        url = f"{self._api_base_url}/order-service/trading-token"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "smart-otp" if smart_otp else "otp": otp
        }
        response = requests.post(url, headers=headers, timeout=self.TIMEOUT)
        if response.status_code == 200:
            trading_token = response.json().get("tradingToken")
            logger.info("Đã xác thực và nhận trading token")
            self.trading_token = trading_token
            return trading_token
        else:
            logger.error("Xác thực trading token thất bại: %s", response.text)
            return None

    def login_and_get_trading_session(
        self,
        username: str,
        password: str,
        otp: str,
        smart_otp: bool = True,
    ) -> dict:
        """Login, then exchange OTP for trading token in a single helper."""
        token = self.login(username, password)
        if not token:
            return {"token": None, "trading_token": None, "success": False}

        trading_token = self.get_trading_token(otp=otp, smart_otp=smart_otp)
        return {
            "token": token,
            "trading_token": trading_token,
            "success": trading_token is not None,
        }

    def loan_packages(
        self,
        sub_account: str,
        asset_type: str = 'stock'
    ) -> Optional[pd.DataFrame]:
        """
        Get the list of loan packages for a specific sub account.

        Args:
            sub_account (str): DNSE sub account number.
            asset_type (str): 'stock' or 'derivative'. Default is 'stock'.

        Returns:
            Optional[pd.DataFrame]: DataFrame with loan packages if successful,
                None otherwise.
        """
        if asset_type == 'stock':
            url = f"{self._api_base_url}/order-service/v2/accounts/"
            url += f"{sub_account}/loan-packages"
        else:
            url = f"{self._api_base_url}/order-service/accounts/"
            url += f"{sub_account}/derivative-loan-packages"
        
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url, headers=headers, timeout=self.TIMEOUT)
        if response.status_code == 200:
            result = response.json()
            return json_normalize(result.get('loanPackages', []))
        else:
            logger.error("Lấy loan packages thất bại: %s", response.text)
            return None

    def trade_capacities(
        self,
        symbol: str,
        price: float,
        sub_account: str,
        asset_type: str = 'stock',
        loan_package_id: Optional[int] = None
    ) -> Optional[pd.DataFrame]:
        """
        Get trade capacities (buying/selling power) for a sub account.

        Args:
            symbol (str): Symbol of the asset.
            price (float): Price of the asset, unit is VND.
            sub_account (str): DNSE sub account number.
            asset_type (str): 'stock' or 'derivative'. Default is 'stock'.
            loan_package_id (Optional[int]): Loan package ID (if applicable).

        Returns:
            Optional[pd.DataFrame]: DataFrame with trade capacities if
                successful, None otherwise.
        """
        if asset_type == 'stock':
            url = f"{self._api_base_url}/order-service/accounts/"
            url += f"{sub_account}/ppse"
            query_params = {
                "symbol": symbol,
                "price": price,
                "loanPackageId": loan_package_id
            }
            query_params = {
                k: v for k, v in query_params.items() if v is not None
            }
            if query_params:
                params_str = "&".join(
                    [f"{key}={value}" for key, value in query_params.items()]
                )
                url += f"?{params_str}"
        else:
            url = f"{self._api_base_url}/order-service/accounts/"
            url += f"{sub_account}/derivative-ppse"
            query_params = {
                "symbol": symbol,
                "price": price,
                "loanPackageId": loan_package_id
            }
            query_params = {
                k: v for k, v in query_params.items() if v is not None
            }
            if query_params:
                params_str = "&".join(
                    [f"{key}={value}" for key, value in query_params.items()]
                )
                url += f"?{params_str}"

        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url, headers=headers, timeout=self.TIMEOUT)
        if response.status_code == 200:
            return json_normalize(response.json())
        else:
            logger.error("Lấy trade capacities thất bại: %s", response.text)
            return None

    def place_order(
        self,
        sub_account: str,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        order_type: str,
        loan_package_id: Optional[int] = None,
        asset_type: str = 'stock'
    , dry_run: bool = True,) -> Optional[pd.DataFrame]:
        """
        Place an order for stocks or derivatives.

        Args:
            sub_account (str): Sub account number.
            symbol (str): Symbol of the asset.
            side (str): 'buy' or 'sell'.
            quantity (int): Order quantity.
            price (float): Order price.
            order_type (str): Order type.
            loan_package_id (Optional[int]): Loan package ID if applicable.
            asset_type (str): 'stock' or 'derivative'. Default is 'stock'.

        Returns:
            Optional[pd.DataFrame]: DataFrame with order info if successful,
                None otherwise.
        """
        # Validate TRƯỚC, rồi mới chặn. Thứ tự này quan trọng: dry-run phải mô
        # phỏng trung thực đường gửi thật — cùng input thì cùng lỗi. Nếu guard
        # chạy trước, dry_run sẽ trả envelope "OK" cho một lệnh mà lúc gửi
        # thật chắc chắn raise, tức là dry-run nói dối (xem P0-1/P0-2: nguyên tắc
        # chung — không bao giờ trả tín hiệu sai cho người dùng).
        normalized_side = str(side).strip().lower()
        if normalized_side in ("buy", "nb", "b", "mua"):
            side_code = "NB"
        elif normalized_side in ("sell", "ns", "s", "ban", "bán"):
            side_code = "NS"
        else:
            raise ValueError(
                f"Giá trị side '{side}' không hợp lệ. Vui lòng sử dụng 'buy' hoặc 'sell'."
            )

        # P0-2: hàng rào đường GHI — dry_run=True (mặc định) thì KHÔNG gửi.
        _dry = self._require_write("place_order", dry_run)
        if _dry is not None:
            return _dry

        if asset_type == 'stock':
            url = f"{self._api_base_url}/order-service/v2/orders"
        else:
            url = f"{self._api_base_url}/order-service/derivative/orders"
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Trading-Token": self.trading_token
        }
        payload = {
            "accountNo": sub_account,
            "symbol": symbol,
            "side": side_code,
            "quantity": quantity,
            "price": price,
            'orderType': order_type,
            "loanPackageId": loan_package_id
        }
        response = requests.post(url, headers=headers, json=payload, timeout=self.TIMEOUT)
        if response.status_code == 200:
            return json_normalize(response.json())
        else:
            logger.error("Đặt lệnh thất bại: %s", response.text)
            return None

    def order_list(
        self,
        sub_account: str,
        asset_type: str = 'stock'
    ) -> Optional[pd.DataFrame]:
        """
        Get the list of orders for a specific account.

        Args:
            sub_account (str): DNSE sub account number.
            asset_type (str): 'stock' or 'derivative'. Default is 'stock'.

        Returns:
            Optional[pd.DataFrame]: DataFrame with list of orders if
                successful, None otherwise.
        """
        if asset_type == 'stock':
            url = f"{self._api_base_url}/order-service/v2/orders"
            url += f"?accountNo={sub_account}"
        else:
            url = f"{self._api_base_url}/order-service/derivative/orders"
            url += f"?accountNo={sub_account}"
        
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url, headers=headers, timeout=self.TIMEOUT)
        if response.status_code == 200:
            logger.info("Lấy danh sách lệnh thành công")
            return json_normalize(response.json().get('orders', []))
        else:
            logger.error("Lấy danh sách lệnh thất bại: %s", response.text)
            return None

    def order_detail(
        self,
        order_id: str,
        sub_account: str,
        asset_type: str = 'stock'
    ) -> Optional[pd.DataFrame]:
        """
        Get the details of a specific order for a sub account.

        Args:
            order_id (str): Order ID.
            sub_account (str): DNSE sub account number.
            asset_type (str): 'stock' or 'derivative'. Default is 'stock'.

        Returns:
            Optional[pd.DataFrame]: DataFrame with order details if
                successful, None otherwise.
        """
        if asset_type == 'stock':
            url = f"{self._api_base_url}/order-service/v2/orders/{order_id}"
            url += f"?accountNo={sub_account}"
        else:
            url = f"{self._api_base_url}/order-service/derivative/orders/"
            url += f"{order_id}?accountNo={sub_account}"
        
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url, headers=headers, timeout=self.TIMEOUT)
        if response.status_code == 200:
            return json_normalize(response.json())
        else:
            logger.error("Lấy chi tiết lệnh thất bại: %s", response.text)
            return None

    def cancel_order(
        self,
        order_id: str,
        sub_account: str,
        asset_type: str = 'stock'
    , dry_run: bool = True,) -> Optional[pd.DataFrame]:
        """
        Cancel an order.

        Args:
            order_id (str): Order ID.
            sub_account (str): DNSE sub account number.
            asset_type (str): 'stock' or 'derivative'. Default is 'stock'.

        Returns:
            Optional[pd.DataFrame]: DataFrame with cancellation result if
                successful, None otherwise.
        """
        # P0-2: hàng rào đường GHI — hủy lệnh cũng là thao tác thật.
        _dry = self._require_write("cancel_order", dry_run)
        if _dry is not None:
            return _dry
        if asset_type == 'stock':
            url = f"{self._api_base_url}/order-service/v2/orders/{order_id}"
            url += f"?accountNo={sub_account}"
        else:
            url = f"{self._api_base_url}/order-service/derivative/orders/"
            url += f"{order_id}?accountNo={sub_account}"
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Trading-Token": self.trading_token
        }
        response = requests.delete(url, headers=headers, timeout=self.TIMEOUT)
        if response.status_code == 200:
            logger.info("Huỷ lệnh thành công")
            return json_normalize(response.json())
        else:
            logger.error("Huỷ lệnh thất bại: %s", response.text)
            return None

    def deals_list(
        self,
        sub_account: str,
        asset_type: str = 'stock'
    ) -> Optional[pd.DataFrame]:
        """
        Get the list of deals for a specific sub account.

        Args:
            sub_account (str): DNSE sub account number.
            asset_type (str): 'stock' or 'derivative'. Default is 'stock'.

        Returns:
            Optional[pd.DataFrame]: DataFrame with list of deals if
                successful, None otherwise.
        """
        if asset_type == 'stock':
            url = f'{self._api_base_url}/deal-service/deals'
            url += f'?accountNo={sub_account}'
        else:
            url = f'{self._api_base_url}/derivative-core/deals'
            url += f'?accountNo={sub_account}'
        
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url, headers=headers, timeout=self.TIMEOUT)
        if response.status_code == 200:
            logger.info("Lấy danh sách deal thành công")
            return json_normalize(response.json().get('data', []))
        else:
            logger.error("Lấy danh sách deal thất bại: %s", response.text)
            return None

    def set_deal_pnl_config(
        self,
        deal_id: int,
        config: dict,
        dry_run: bool = False,
    ) -> Optional[pd.DataFrame]:
        """
        Set take profit/stop loss config for a specific deal.

        Args:
            deal_id (int): Deal ID.
            config (dict): PnL configuration with keys like:
                - takeProfitEnabled (bool)
                - stopLossEnabled (bool)
                - takeProfitStrategy (str): 'PNL_RATE' or 'DELTA_PRICE'
                - stopLossStrategy (str): 'PNL_RATE' or 'DELTA_PRICE'
                - takeProfitOrderType (str): 'FASTEST' or 'DELTA_PRICE'
                - stopLossOrderType (str): 'FASTEST' or 'DELTA_PRICE'
                - takeProfitRate (float): > 0
                - stopLossRate (float): -1 <= x < 0
                - takeProfitDeltaPrice (float): > 0
                - stopLossDeltaPrice (float): > 0
                - takeProfitOrderDeltaPrice (float)
                - stopLossOrderDeltaPrice (float)

        Returns:
            Optional[pd.DataFrame]: DataFrame with config result if
                successful, None otherwise.
        """
        _dry = self._require_write("set_deal_pnl_config", dry_run)
        if _dry is not None:
            return _dry

        url = f"{self._api_base_url}/derivative-deal-risk/pnl-configs/{deal_id}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Trading-Token": self.trading_token
        }
        response = requests.post(url, headers=headers, json=config, timeout=self.TIMEOUT)
        if response.status_code == 200:
            logger.info("Thiết lập PnL config cho deal thành công")
            return json_normalize(response.json())
        else:
            logger.error("Thiết lập PnL config cho deal thất bại: %s", response.text)
            return None

    def set_account_pnl_config(
        self,
        account_no: str,
        config: dict,
        dry_run: bool = False,
    ) -> Optional[pd.DataFrame]:
        """
        Set take profit/stop loss config for an account.

        Args:
            account_no (str): Sub account number.
            config (dict): PnL configuration with keys like:
                - status (str): Must be 'ACTIVE'
                - takeProfitEnabled (bool)
                - stopLossEnabled (bool)
                - takeProfitStrategy (str): 'PNL_RATE' or 'DELTA_PRICE'
                - stopLossStrategy (str): 'PNL_RATE' or 'DELTA_PRICE'
                - takeProfitRate (float): > 0
                - stopLossRate (float): -1 <= x < 0
                - takeProfitDeltaPrice (float): > 0
                - stopLossDeltaPrice (float): > 0

        Returns:
            Optional[pd.DataFrame]: DataFrame with config result if
                successful, None otherwise.
        """
        _dry = self._require_write("set_account_pnl_config", dry_run)
        if _dry is not None:
            return _dry

        url = f"{self._api_base_url}/derivative-deal-risk/"
        url += f"account-pnl-configs/{account_no}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Trading-Token": self.trading_token
        }
        response = requests.patch(url, headers=headers, json=config, timeout=self.TIMEOUT)
        if response.status_code == 200:
            logger.info("Thiết lập PnL config cho tài khoản thành công")
            return json_normalize(response.json())
        else:
            logger.error("Thiết lập PnL config cho tài khoản thất bại: %s", response.text)
            return None

    def close_deal(self, deal_id: int, dry_run: bool = False) -> Optional[pd.DataFrame]:
        """
        Close a derivative deal.

        Args:
            deal_id (int): Deal ID to close.

        Returns:
            Optional[pd.DataFrame]: DataFrame with result if successful,
                None otherwise.
        """
        _dry = self._require_write("close_deal", dry_run)
        if _dry is not None:
            return _dry

        url = f"{self._api_base_url}/derivative-core/deals/{deal_id}/close"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Trading-Token": self.trading_token
        }
        response = requests.post(url, headers=headers, timeout=self.TIMEOUT)
        if response.status_code == 200:
            logger.info("Đóng deal thành công")
            return json_normalize(response.json())
        else:
            logger.error("Đóng deal thất bại: %s", response.text)
            return None
