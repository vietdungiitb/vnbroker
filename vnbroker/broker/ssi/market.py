"""
vnbroker.broker.ssi.market — SSI Market Data Service.

Handles market data operations for SSI FastConnect API.
"""

from __future__ import annotations

import logging
from typing import Optional, Union, List

import pandas as pd
import requests

from vnbroker.broker.security.credentials import SSICredentialConfig
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.exceptions import BrokerAuthError, BrokerAPIError

_logger = logging.getLogger("vnbroker.broker.ssi.market")


class SSIMarketService:
    """
    SSI FastConnect Market Data Service.
    
    Provides methods for market data: ticker info, snapshots, intraday, etc.
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

    def get_ticker_info(
        self,
        tickers: Optional[Union[str, List[str]]] = None,
        raw: bool = False,
    ) -> Union[dict, pd.DataFrame]:
        """
        Get basic ticker information.
        
        Args:
            tickers: Single ticker or list of tickers (optional, gets all if None)
            raw: Return raw dict instead of DataFrame
            
        Returns:
            Ticker information as DataFrame or dict
        """
        params = {}
        if tickers:
            if isinstance(tickers, list):
                params["tickers"] = ",".join(tickers)
            else:
                params["tickers"] = tickers
        
        data = self._request("GET", "/api/v1/market/ticker-info", params=params)
        
        if raw:
            return data
        
        if "data" in data and isinstance(data["data"], list):
            return pd.DataFrame(data["data"])
        
        return pd.DataFrame([data])

    def get_market_snapshot(
        self,
        raw: bool = False,
    ) -> Union[dict, pd.DataFrame]:
        """
        Get market snapshot (all tickers current prices).
        
        Args:
            raw: Return raw dict instead of DataFrame
            
        Returns:
            Market snapshot as DataFrame or dict
        """
        data = self._request("GET", "/api/v1/market/snapshot")
        
        if raw:
            return data
        
        if "data" in data and isinstance(data["data"], list):
            return pd.DataFrame(data["data"])
        
        return pd.DataFrame([data])

    def get_intraday(
        self,
        symbol: str,
        page: int = 0,
        size: int = 100,
        raw: bool = False,
    ) -> Union[dict, pd.DataFrame]:
        """
        Get intraday trading data for a symbol.
        
        Args:
            symbol: Stock symbol
            page: Page number
            size: Page size
            raw: Return raw dict instead of DataFrame
            
        Returns:
            Intraday data as DataFrame or dict
        """
        params = {
            "page": page,
            "size": size,
        }
        
        data = self._request("GET", f"/api/v1/market/intraday/{symbol}", params=params)
        
        if raw:
            return data
        
        if "data" in data and isinstance(data["data"], list):
            return pd.DataFrame(data["data"])
        
        return pd.DataFrame([data])

    def get_price_board(
        self,
        symbols: List[str],
        raw: bool = False,
    ) -> Union[dict, pd.DataFrame]:
        """
        Get price board for multiple symbols.
        
        Args:
            symbols: List of stock symbols
            raw: Return raw dict instead of DataFrame
            
        Returns:
            Price board as DataFrame or dict
        """
        payload = {"symbols": symbols}
        
        data = self._request("POST", "/api/v1/market/price-board", json=payload)
        
        if raw:
            return data
        
        if "data" in data and isinstance(data["data"], list):
            return pd.DataFrame(data["data"])
        
        return pd.DataFrame([data])

    def get_indices(
        self,
        raw: bool = False,
    ) -> Union[dict, pd.DataFrame]:
        """
        Get market indices.
        
        Args:
            raw: Return raw dict instead of DataFrame
            
        Returns:
            Indices data as DataFrame or dict
        """
        data = self._request("GET", "/api/v1/market/indices")
        
        if raw:
            return data
        
        if "data" in data and isinstance(data["data"], list):
            return pd.DataFrame(data["data"])
        
        return pd.DataFrame([data])