"""
vnbroker.broker.ssi.equity — SSI Equity Trading Service.

Handles equity order operations for SSI FastConnect API.
"""

from __future__ import annotations

import logging
from typing import Optional, Union, List

import pandas as pd
import requests

from vnbroker.broker.security.credentials import SSICredentialConfig
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.exceptions import BrokerAuthError, BrokerAPIError, BrokerPermissionError
from vnbroker.broker.security.guards import require_write

_logger = logging.getLogger("vnbroker.broker.ssi.equity")


class SSIEquityService:
    """
    SSI FastConnect Equity Trading Service.
    
    Provides methods for placing, modifying, canceling orders and querying executions/holdings.
    """

    def __init__(self, config: SSICredentialConfig, session: BrokerSession) -> None:
        self._config = config
        self._session = session
        self._base_url = config.base_url

    def _get_headers(self) -> dict:
        """Get headers with authorization token."""
        if not self._session.is_token_valid():
            raise BrokerAuthError("SSI token expired or not authenticated. Call authenticate() first.")
        
        return {
            "Authorization": f"Bearer {self._session.access_token}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make authenticated request to SSI API."""
        url = f"{self._base_url}{endpoint}"
        headers = self._get_headers()
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                timeout=self._config.timeout_seconds,
                **kwargs,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise BrokerAuthError("SSI token expired or invalid") from e
            elif e.response.status_code == 403:
                raise BrokerPermissionError("SSI permission denied - check write access") from e
            _logger.error(f"SSI API error: {e.response.status_code} - {e.response.text}")
            raise BrokerAPIError(f"SSI API error: {e.response.status_code}") from e
        except requests.RequestException as e:
            _logger.error(f"SSI request failed: {e}")
            raise BrokerAPIError(f"SSI request failed: {e}") from e

    # ── Order Operations ──────────────────────────────────────────────────────

    @require_write
    def place_order(
        self,
        account_no: str,
        symbol: str,
        side: str,  # "BUY" or "SELL"
        order_type: str,  # "LO" (Limit), "MP" (Market), "ATO", "ATC"
        quantity: int,
        price: Optional[float] = None,
        validity: str = "DAY",  # "DAY", "IOC", "FOK"
        raw: bool = False,
    ) -> Union[dict, pd.DataFrame]:
        """
        Place a new equity order.
        
        Args:
            account_no: Account number
            symbol: Stock symbol
            side: "BUY" or "SELL"
            order_type: "LO" (Limit), "MP" (Market), "ATO", "ATC"
            quantity: Order quantity
            price: Limit price (required for LO orders)
            validity: Order validity ("DAY", "IOC", "FOK")
            raw: Return raw dict instead of DataFrame
            
        Returns:
            Order confirmation as DataFrame or dict
        """
        if order_type == "LO" and price is None:
            raise ValueError("Price is required for Limit orders (LO)")
        
        payload = {
            "accountNo": account_no,
            "symbol": symbol,
            "side": side.upper(),
            "orderType": order_type.upper(),
            "quantity": quantity,
            "validity": validity.upper(),
        }
        
        if price is not None:
            payload["price"] = price
        
        data = self._request("POST", "/api/v1/order", json=payload)
        
        if raw:
            return data
        
        return pd.DataFrame([data])

    @require_write
    def modify_order(
        self,
        account_no: str,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        raw: bool = False,
    ) -> Union[dict, pd.DataFrame]:
        """
        Modify an existing order.
        
        Args:
            account_no: Account number
            order_id: Order ID to modify
            quantity: New quantity (optional)
            price: New price (optional)
            raw: Return raw dict instead of DataFrame
            
        Returns:
            Modified order confirmation as DataFrame or dict
        """
        payload = {}
        if quantity is not None:
            payload["quantity"] = quantity
        if price is not None:
            payload["price"] = price
        
        if not payload:
            raise ValueError("At least one of quantity or price must be provided")
        
        data = self._request("PUT", f"/api/v1/order/{order_id}", json=payload)
        
        if raw:
            return data
        
        return pd.DataFrame([data])

    @require_write
    def cancel_order(
        self,
        account_no: str,
        order_id: str,
        raw: bool = False,
    ) -> Union[dict, pd.DataFrame]:
        """
        Cancel an existing order.
        
        Args:
            account_no: Account number
            order_id: Order ID to cancel
            raw: Return raw dict instead of DataFrame
            
        Returns:
            Cancellation confirmation as DataFrame or dict
        """
        data = self._request("DELETE", f"/api/v1/order/{order_id}")
        
        if raw:
            return data
        
        return pd.DataFrame([data])

    # ── Query Operations ──────────────────────────────────────────────────────

    def get_orders(
        self,
        account_no: str,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page: int = 0,
        size: int = 50,
        raw: bool = False,
    ) -> Union[dict, pd.DataFrame]:
        """
        Get order history.
        
        Args:
            account_no: Account number
            symbol: Filter by symbol (optional)
            status: Filter by status (optional)
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            page: Page number
            size: Page size
            raw: Return raw dict instead of DataFrame
            
        Returns:
            Order history as DataFrame or dict
        """
        params = {
            "page": page,
            "size": size,
        }
        
        if symbol:
            params["symbol"] = symbol
        if status:
            params["status"] = status
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date
        
        data = self._request("GET", f"/api/v1/account/{account_no}/orders", params=params)
        
        if raw:
            return data
        
        if "data" in data and isinstance(data["data"], list):
            return pd.DataFrame(data["data"])
        
        return pd.DataFrame([data])

    def get_executions(
        self,
        account_no: str,
        symbol: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page: int = 0,
        size: int = 50,
        raw: bool = False,
    ) -> Union[dict, pd.DataFrame]:
        """
        Get execution history (filled orders).
        
        Args:
            account_no: Account number
            symbol: Filter by symbol (optional)
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            page: Page number
            size: Page size
            raw: Return raw dict instead of DataFrame
            
        Returns:
            Execution history as DataFrame or dict
        """
        params = {
            "page": page,
            "size": size,
        }
        
        if symbol:
            params["symbol"] = symbol
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date
        
        data = self._request("GET", f"/api/v1/account/{account_no}/executions", params=params)
        
        if raw:
            return data
        
        if "data" in data and isinstance(data["data"], list):
            return pd.DataFrame(data["data"])
        
        return pd.DataFrame([data])

    def get_holdings(
        self,
        account_no: str,
        raw: bool = False,
    ) -> Union[dict, pd.DataFrame]:
        """
        Get current holdings (portfolio).
        
        Args:
            account_no: Account number
            raw: Return raw dict instead of DataFrame
            
        Returns:
            Holdings as DataFrame or dict
        """
        data = self._request("GET", f"/api/v1/account/{account_no}/holdings")
        
        if raw:
            return data
        
        if "data" in data and isinstance(data["data"], list):
            return pd.DataFrame(data["data"])
        
        return pd.DataFrame([data])