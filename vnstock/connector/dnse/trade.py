import requests
import json
import pandas as pd
import warnings
from pandas import json_normalize
from typing import Optional

from vnstock.connector.dnse.client import DNSEClient

class Trade:
    BASE_URL = "https://api.dnse.com.vn"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_url: str = "https://openapi.dnse.com.vn",
    ):
        self.token: Optional[str] = None
        self.trading_token: Optional[str] = None
        self._openapi_client: Optional[DNSEClient] = None
        self._api_key = api_key
        self._api_secret = api_secret
        self._openapi_base_url = base_url

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
            )
        return self._openapi_client

    def login(self, user_name: str, password: str) -> Optional[str]:
        """
        Authenticate the user and obtain a JWT token for API requests.

        Args:
            user_name (str): DNSE username (custody code, email, or phone).
            password (str): Your DNSE password.

        Returns:
            Optional[str]: JWT token if successful, None otherwise.
        """
        url = f"{self.BASE_URL}/auth-service/login"
        payload = json.dumps({'username': user_name, 'password': password})
        headers = {'Content-Type': 'application/json'}
        response = requests.post(url, headers=headers, data=payload)
        if response.status_code == 200:
            print('Login successfully')
            self.token = response.json().get('token')
            return self.token
        else:
            print(f'Login failed: {response.text}')
            return None

    def account(self) -> Optional[pd.DataFrame]:
        """
        Get the full user profile from DNSE.

        Returns:
            Optional[pd.DataFrame]: DataFrame with user profile if successful,
                None otherwise.
        """
        url = f"{self.BASE_URL}/user-service/api/me"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.token}'
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            print('Get profile successfully')
            return pd.DataFrame(response.json(), index=[0])
        else:
            print(f'Get profile failed: {response.text}')
            return None

    def sub_accounts(self) -> Optional[pd.DataFrame]:
        """
        Get sub-accounts information.

        Returns:
            Optional[pd.DataFrame]: DataFrame with sub-accounts info if
                successful, None otherwise.
        """
        url = f"{self.BASE_URL}/order-service/accounts"
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            result = response.json()
            return json_normalize(result.get('accounts', []))
        else:
            print(f"Error: {response.text}")
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
        url = f"{self.BASE_URL}/order-service/account-balances/{sub_account}"
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            result = response.json()
            return json_normalize(result)
        else:
            print(f"Error: {response.text}")
            return None

    def email_otp(self) -> None:
        """
        Trigger an email OTP request to DNSE.

        The OTP will be sent to the email address associated with
        the DNSE account.
        """
        url = f"{self.BASE_URL}/auth-service/api/email-otp"
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            print("OTP sent to email")
        else:
            print(f"Error: {response.text}")

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
        url = f"{self.BASE_URL}/order-service/trading-token"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "smart-otp" if smart_otp else "otp": otp
        }
        response = requests.post(url, headers=headers)
        if response.status_code == 200:
            trading_token = response.json().get("tradingToken")
            print("Authenticated! Trading token returned.")
            self.trading_token = trading_token
            return trading_token
        else:
            print(f"Error authenticating: {response.text}")
            return None

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
            url = f"{self.BASE_URL}/order-service/v2/accounts/"
            url += f"{sub_account}/loan-packages"
        else:
            url = f"{self.BASE_URL}/order-service/accounts/"
            url += f"{sub_account}/derivative-loan-packages"
        
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            result = response.json()
            return json_normalize(result.get('loanPackages', []))
        else:
            print(f"Error: {response.text}")
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
            url = f"{self.BASE_URL}/order-service/accounts/"
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
            url = f"{self.BASE_URL}/order-service/accounts/"
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
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return json_normalize(response.json())
        else:
            print(f"Error: {response.text}")
            return None

    def place_order(
        self,
        sub_account: str,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        order_type: str,
        loan_package_id: Optional[int],
        asset_type: str = 'stock'
    ) -> Optional[pd.DataFrame]:
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
        side_code = 'NB' if side == 'buy' else 'NS'

        if asset_type == 'stock':
            url = f"{self.BASE_URL}/order-service/v2/orders"
        else:
            url = f"{self.BASE_URL}/order-service/derivative/orders"
        
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
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            return json_normalize(response.json())
        else:
            print(f"Error: {response.text}")
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
            url = f"{self.BASE_URL}/order-service/v2/orders"
            url += f"?accountNo={sub_account}"
        else:
            url = f"{self.BASE_URL}/order-service/derivative/orders"
            url += f"?accountNo={sub_account}"
        
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            print('Order list retrieved')
            return json_normalize(response.json().get('orders', []))
        else:
            print(f"Error: {response.text}")
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
            url = f"{self.BASE_URL}/order-service/v2/orders/{order_id}"
            url += f"?accountNo={sub_account}"
        else:
            url = f"{self.BASE_URL}/order-service/derivative/orders/"
            url += f"{order_id}?accountNo={sub_account}"
        
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return json_normalize(response.json())
        else:
            print(f"Error: {response.text}")
            return None

    def cancel_order(
        self,
        order_id: str,
        sub_account: str,
        asset_type: str = 'stock'
    ) -> Optional[pd.DataFrame]:
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
        if asset_type == 'stock':
            url = f"{self.BASE_URL}/order-service/v2/orders/{order_id}"
            url += f"?accountNo={sub_account}"
        else:
            url = f"{self.BASE_URL}/order-service/derivative/orders/"
            url += f"{order_id}?accountNo={sub_account}"
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Trading-Token": self.trading_token
        }
        response = requests.delete(url, headers=headers)
        if response.status_code == 200:
            print("Order cancelled")
            return json_normalize(response.json())
        else:
            print(f"Error: {response.text}")
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
            url = f'{self.BASE_URL}/deal-service/deals'
            url += f'?accountNo={sub_account}'
        else:
            url = f'{self.BASE_URL}/derivative-core/deals'
            url += f'?accountNo={sub_account}'
        
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            print('Deals list retrieved')
            return json_normalize(response.json().get('data', []))
        else:
            print(f"Error: {response.text}")
            return None

    def set_deal_pnl_config(
        self,
        deal_id: int,
        config: dict
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
        url = f"{self.BASE_URL}/derivative-deal-risk/pnl-configs/{deal_id}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Trading-Token": self.trading_token
        }
        response = requests.post(url, headers=headers, json=config)
        if response.status_code == 200:
            print("Deal PnL config set successfully")
            return json_normalize(response.json())
        else:
            print(f"Error: {response.text}")
            return None

    def set_account_pnl_config(
        self,
        account_no: str,
        config: dict
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
        url = f"{self.BASE_URL}/derivative-deal-risk/"
        url += f"account-pnl-configs/{account_no}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Trading-Token": self.trading_token
        }
        response = requests.patch(url, headers=headers, json=config)
        if response.status_code == 200:
            print("Account PnL config set successfully")
            return json_normalize(response.json())
        else:
            print(f"Error: {response.text}")
            return None

    def close_deal(self, deal_id: int) -> Optional[pd.DataFrame]:
        """
        Close a derivative deal.

        Args:
            deal_id (int): Deal ID to close.

        Returns:
            Optional[pd.DataFrame]: DataFrame with result if successful,
                None otherwise.
        """
        url = f"{self.BASE_URL}/derivative-core/deals/{deal_id}/close"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Trading-Token": self.trading_token
        }
        response = requests.post(url, headers=headers)
        if response.status_code == 200:
            print("Deal closed successfully")
            return json_normalize(response.json())
        else:
            print(f"Error: {response.text}")
            return None

    def deposit_derivative_margin(
        self,
        account_no: str,
        source_account_no: str,
        loan_package_id: int,
        amount: int,
        via: str,
        otp: str
    ) -> Optional[pd.DataFrame]:
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
        url = f"{self.BASE_URL}/derivative-asset-service/deposit"
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
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            print("Margin deposited successfully")
            return json_normalize(response.json())
        else:
            print(f"Error: {response.text}")
            return None

    def withdraw_derivative_margin(
        self,
        account_no: str,
        source_account_no: str,
        loan_package_id: int,
        amount: int,
        via: str,
        otp: str
    ) -> Optional[pd.DataFrame]:
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
        url = f"{self.BASE_URL}/derivative-asset-service/withdraw"
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
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            print("Margin withdrawn successfully")
            return json_normalize(response.json())
        else:
            print(f"Error: {response.text}")
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
        url = f"{self.BASE_URL}/derivative-core/cash-accounts"
        url += f"?accountNo={account_no}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "accept": "application/json, text/plain,/"
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return json_normalize(response.json())
        else:
            print(f"Error: {response.text}")
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
        url = f"{self.BASE_URL}/derivative-core/ppse"
        url += f"?loanPackageId={loan_package_id}&accountNo={account_no}"
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return json_normalize(response.json())
        else:
            print(f"Error: {response.text}")
            return None

    def place_conditional_order(
        self,
        account_no: str,
        symbol: str,
        condition: str,
        target_order: dict,
        props: dict,
        time_in_force: dict,
        category: str = "STOP"
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
        url = f"{self.BASE_URL}/conditional-order-api/v1/orders"
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
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            print("Conditional order placed successfully")
            return json_normalize(response.json())
        else:
            print(f"Error: {response.text}")
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
        status: Optional[list] = None,
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
        url = f"{self.BASE_URL}/conditional-order-api/v1/orders"
        headers = {"Authorization": f"Bearer {self.token}"}
        params = {
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

        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            result = response.json()
            return json_normalize(result.get('content', []))
        else:
            print(f"Error: {response.text}")
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
        url = f"{self.BASE_URL}/conditional-order-api/v1/orders/{order_id}"
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return json_normalize(response.json())
        else:
            print(f"Error: {response.text}")
            return None

    def cancel_conditional_order(
        self,
        order_id: str
    ) -> Optional[pd.DataFrame]:
        """
        Cancel a conditional order.

        Args:
            order_id (str): Conditional order ID to cancel.

        Returns:
            Optional[pd.DataFrame]: DataFrame with result if successful,
                None otherwise.
        """
        url = f"{self.BASE_URL}/conditional-order-api/v1/orders/"
        url += f"{order_id}/cancel"
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.patch(url, headers=headers)
        if response.status_code == 200:
            print("Conditional order cancelled successfully")
            return json_normalize(response.json())
        else:
            print(f"Error: {response.text}")
            return None

    # OpenAPI compatibility bridge
    def get_accounts(self, dry_run: bool = False, raw: bool = False):
        warnings.warn(
            "Trade OpenAPI bridge is active. Prefer using vnstock.connector.dnse.DNSEClient directly.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._get_openapi_client().get_accounts(dry_run=dry_run, raw=raw)

    def get_balances(self, account_no: str, dry_run: bool = False, raw: bool = False):
        return self._get_openapi_client().get_balances(
            account_no=account_no,
            dry_run=dry_run,
            raw=raw,
        )

    def get_loan_packages(
        self,
        account_no: str,
        market_type: str,
        symbol: Optional[str] = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._get_openapi_client().get_loan_packages(
            account_no=account_no,
            market_type=market_type,
            symbol=symbol,
            dry_run=dry_run,
            raw=raw,
        )

    def get_ppse(
        self,
        account_no: str,
        market_type: str,
        symbol: str,
        price: float,
        loan_package_id: int,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._get_openapi_client().get_ppse(
            account_no=account_no,
            market_type=market_type,
            symbol=symbol,
            price=price,
            loan_package_id=loan_package_id,
            dry_run=dry_run,
            raw=raw,
        )

    def get_orders(
        self,
        account_no: str,
        market_type: str,
        order_category: Optional[str] = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._get_openapi_client().get_orders(
            account_no=account_no,
            market_type=market_type,
            order_category=order_category,
            dry_run=dry_run,
            raw=raw,
        )

    def get_order_detail(
        self,
        account_no: str,
        order_id: str,
        market_type: str,
        order_category: Optional[str] = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._get_openapi_client().get_order_detail(
            account_no=account_no,
            order_id=order_id,
            market_type=market_type,
            order_category=order_category,
            dry_run=dry_run,
            raw=raw,
        )

    def get_execution_detail(
        self,
        account_no: str,
        order_id: str,
        market_type: str,
        order_category: str = "NORMAL",
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._get_openapi_client().get_execution_detail(
            account_no=account_no,
            order_id=order_id,
            market_type=market_type,
            order_category=order_category,
            dry_run=dry_run,
            raw=raw,
        )

    def get_order_history(
        self,
        account_no: str,
        market_type: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page_size: Optional[int] = None,
        page_index: Optional[int] = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._get_openapi_client().get_order_history(
            account_no=account_no,
            market_type=market_type,
            from_date=from_date,
            to_date=to_date,
            page_size=page_size,
            page_index=page_index,
            dry_run=dry_run,
            raw=raw,
        )

    def post_order(
        self,
        market_type: str,
        payload: dict,
        trading_token: str,
        order_category: str = "NORMAL",
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._get_openapi_client().post_order(
            market_type=market_type,
            payload=payload,
            trading_token=trading_token,
            order_category=order_category,
            dry_run=dry_run,
            raw=raw,
        )

    def put_order(
        self,
        account_no: str,
        order_id: str,
        market_type: str,
        payload: dict,
        trading_token: str,
        order_category: Optional[str] = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._get_openapi_client().put_order(
            account_no=account_no,
            order_id=order_id,
            market_type=market_type,
            payload=payload,
            trading_token=trading_token,
            order_category=order_category,
            dry_run=dry_run,
            raw=raw,
        )

    def cancel_order_openapi(
        self,
        account_no: str,
        order_id: str,
        market_type: str,
        trading_token: str,
        order_category: Optional[str] = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._get_openapi_client().cancel_order(
            account_no=account_no,
            order_id=order_id,
            market_type=market_type,
            trading_token=trading_token,
            order_category=order_category,
            dry_run=dry_run,
            raw=raw,
        )

    def send_email_otp(self, dry_run: bool = False, raw: bool = False):
        return self._get_openapi_client().send_email_otp(dry_run=dry_run, raw=raw)

    def create_trading_token(
        self,
        otp_type: str,
        passcode: str,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._get_openapi_client().create_trading_token(
            otp_type=otp_type,
            passcode=passcode,
            dry_run=dry_run,
            raw=raw,
        )

    def get_positions(
        self,
        account_no: str,
        market_type: str,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._get_openapi_client().get_positions(
            account_no=account_no,
            market_type=market_type,
            dry_run=dry_run,
            raw=raw,
        )

    def get_position_by_id(
        self,
        market_type: str,
        position_id: str,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._get_openapi_client().get_position_by_id(
            market_type=market_type,
            position_id=position_id,
            dry_run=dry_run,
            raw=raw,
        )

    def close_position(
        self,
        position_id: str,
        market_type: str,
        trading_token: str,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._get_openapi_client().close_position(
            position_id=position_id,
            market_type=market_type,
            trading_token=trading_token,
            dry_run=dry_run,
            raw=raw,
        )

    def get_security_definition(
        self,
        symbol: str,
        board_id: Optional[str] = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._get_openapi_client().get_security_definition(
            symbol=symbol,
            board_id=board_id,
            dry_run=dry_run,
            raw=raw,
        )

    def get_ohlc(
        self,
        bar_type: str,
        query: Optional[dict] = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._get_openapi_client().get_ohlc(
            bar_type=bar_type,
            query=query,
            dry_run=dry_run,
            raw=raw,
        )

    def get_trades(
        self,
        symbol: str,
        board_id: Optional[str] = None,
        from_date: Optional[int] = None,
        to_date: Optional[int] = None,
        limit: Optional[int] = None,
        order: Optional[str] = None,
        next_page_token: Optional[str] = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._get_openapi_client().get_trades(
            symbol=symbol,
            board_id=board_id,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            order=order,
            next_page_token=next_page_token,
            dry_run=dry_run,
            raw=raw,
        )

    def get_instruments(
        self,
        symbol: Optional[str] = None,
        market_id: Optional[str] = None,
        security_group_id: Optional[str] = None,
        index_name: Optional[str] = None,
        limit: Optional[int] = None,
        page: Optional[int] = None,
        dry_run: bool = False,
        raw: bool = False,
    ):
        return self._get_openapi_client().get_instruments(
            symbol=symbol,
            market_id=market_id,
            security_group_id=security_group_id,
            index_name=index_name,
            limit=limit,
            page=page,
            dry_run=dry_run,
            raw=raw,
        )
