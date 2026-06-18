"""
vnbroker.broker.ssi.money — SSI Money Service.

Handles cash and margin operations for SSI FastConnect API.
"""

from __future__ import annotations

import logging
from typing import Optional, Union

import pandas as pd
import requests

from vnbroker.broker.security.credentials import SSICredentialConfig
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.exceptions import BrokerAuthError, BrokerAPIError

_logger = logging.getLogger("vnbroker.broker.ssi.money")


class SSIMoneyService:
    """
    SSI FastConnect Money Service.
    
    Provides methods for cash balance and margin information.
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

    def get_cash(
        self,
        account_no: str,
        raw: bool = False,
    ) -> Union[dict, pd.DataFrame]:
        """
        Get cash balance for account.
        
        Args:
            account_no: Account number
            raw: Return raw dict instead of DataFrame
            
        Returns:
            Cash balance as DataFrame or dict
        """
        data = self._request("GET", f"/api/v1/account/{account_no}/cash")
        
        if raw:
            return data
        
        if "data" in data and isinstance(data["data"], list):
            return pd.DataFrame(data["data"])
        
        return pd.DataFrame([data])

    def get_margin(
        self,
        account_no: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page: int = 0,
        size: int = 20,
        raw: bool = False,
    ) -> Union[dict, pd.DataFrame]:
        """
        Get margin information for account.
        
        Args:
            account_no: Account number
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            page: Page number
            size: Page size
            raw: Return raw dict instead of DataFrame
            
        Returns:
            Margin information as DataFrame or dict
        """
        params = {
            "page": page,
            "size": size,
        }
        
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date
        
        data = self._request("GET", f"/api/v1/account/{account_no}/margin", params=params)
        
        if raw:
            return data
        
        if "data" in data and isinstance(data["data"], list):
            return pd.DataFrame(data["data"])
        
        return pd.DataFrame([data])