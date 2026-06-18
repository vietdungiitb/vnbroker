"""
vnbroker.broker.ssi.account — SSI Account Service.

Handles account-related operations for SSI FastConnect API.
"""

from __future__ import annotations

import logging
from typing import Optional, Union

import pandas as pd
import requests

from vnbroker.broker.security.credentials import SSICredentialConfig
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.exceptions import BrokerAuthError, BrokerAPIError

_logger = logging.getLogger("vnbroker.broker.ssi.account")


class SSIAccountService:
    """
    SSI FastConnect Account Service.
    
    Provides methods for account information, balance, and portfolio.
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
            _logger.error(f"SSI API error: {e.response.status_code} - {e.response.text}")
            raise BrokerAPIError(f"SSI API error: {e.response.status_code}") from e
        except requests.RequestException as e:
            _logger.error(f"SSI request failed: {e}")
            raise BrokerAPIError(f"SSI request failed: {e}") from e

    def get_account_info(self, account_no: str, raw: bool = False) -> Union[dict, pd.DataFrame]:
        """
        Get account information.
        
        Args:
            account_no: Account number
            raw: Return raw dict instead of DataFrame
            
        Returns:
            Account information as DataFrame or dict
        """
        data = self._request("GET", f"/api/v1/account/{account_no}")
        
        if raw:
            return data
        
        return pd.DataFrame([data])

    def get_balance(self, account_no: str, raw: bool = False) -> Union[dict, pd.DataFrame]:
        """
        Get account balance (cash, margin, etc.).
        
        Args:
            account_no: Account number
            raw: Return raw dict instead of DataFrame
            
        Returns:
            Balance information as DataFrame or dict
        """
        data = self._request("GET", f"/api/v1/account/{account_no}/balance")
        
        if raw:
            return data
        
        return pd.DataFrame([data])

    def get_portfolio(self, account_no: str, raw: bool = False) -> Union[dict, pd.DataFrame]:
        """
        Get account portfolio (holdings).
        
        Args:
            account_no: Account number
            raw: Return raw dict instead of DataFrame
            
        Returns:
            Portfolio holdings as DataFrame or dict
        """
        data = self._request("GET", f"/api/v1/account/{account_no}/portfolio")
        
        if raw:
            return data
        
        # Normalize portfolio data
        if "data" in data and isinstance(data["data"], list):
            return pd.DataFrame(data["data"])
        
        return pd.DataFrame([data])

    def get_purchasing_power(self, account_no: str, raw: bool = False) -> Union[dict, pd.DataFrame]:
        """
        Get account purchasing power.
        
        Args:
            account_no: Account number
            raw: Return raw dict instead of DataFrame
            
        Returns:
            Purchasing power information as DataFrame or dict
        """
        data = self._request("GET", f"/api/v1/account/{account_no}/purchasing-power")
        
        if raw:
            return data
        
        return pd.DataFrame([data])