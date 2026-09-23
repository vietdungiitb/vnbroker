"""
TCBS Explorer Compatibility Layer for iFlash OpenAPI

This module provides backward compatibility for the TCBS explorer while using
the new iFlash OpenAPI endpoints on https://openapi.tcbs.com.vn.

Key changes:
1. Derivatives listing uses /tartarus/v1/derivatives (new)
2. Intraday data uses /nyx/v1/intraday/{ticker}/his/paging (new)
3. OHLC history computed from intraday tick data (new)
4. Listing endpoints updated to use new base URL
5. Company data endpoints updated to use new base URL
"""

import pandas as pd
from typing import List, Optional

from vnbroker.core.utils import client
from vnbroker.core.utils.logger import get_logger

from .auth import get_tcbs_headers
from .const import _BASE_URL, TARTARUS_PATH, NYX_PATH, LIGO_PATH, _ANALYSIS_URL

logger = get_logger(__name__)

# New endpoint URLs
_DERIVATIVES_URL = f"{_BASE_URL}{TARTARUS_PATH}/derivatives"
_INTRADAY_URL_TEMPLATE = f"{_BASE_URL}{NYX_PATH}/intraday/{{ticker}}/his/paging"
_TICKER_COMMONS_URL = f"{_BASE_URL}{TARTARUS_PATH}/tickerCommons"
_LIGO_WATCHLIST_URL = f"{_BASE_URL}{LIGO_PATH}/watchlist/preview"
_TCANALYSIS_URL_TEMPLATE = f"{_BASE_URL}{_ANALYSIS_URL}/v1"

# OHLC column mapping for intraday data
_OHLC_COLUMNS = {
    'time': 'time',
    'p': 'open',
    'v': 'volume',
}

# Intraday column mapping
_INTRADAY_COLUMNS = {
    't': 'time',
    'p': 'price',
    'v': 'volume',
    'a': 'match_type',
}

class TCBSCompatibility:
    """
    Compatibility layer for TCBS explorer with iFlash OpenAPI.
    
    This class provides backward-compatible methods for the TCBS explorer
    while using the new iFlash OpenAPI endpoints.
    """
    
    def __init__(
        self,
        symbol: Optional[str] = None,
        random_agent: bool = False,
        show_log: bool = True,
        auth_token: Optional[str] = None,
    ):
        self.data_source = 'TCBS'
        self.symbol = symbol
        self.headers = get_tcbs_headers(
            random_agent=random_agent,
            auth_token=auth_token,
        )
        self.show_log = show_log
        if not show_log:
            logger.setLevel('CRITICAL')
    
    def get_derivatives_list(self, show_log: bool = False) -> pd.Series:
        """
        Get derivatives list using the new /tartarus/v1/derivatives endpoint.
        
        Args:
            show_log: Whether to show log messages.
            
        Returns:
            Series of derivative symbols.
        """
        try:
            response = client.send_request(
                url=_DERIVATIVES_URL,
                headers=self.headers,
                method="GET",
                show_log=show_log,
            )
        except Exception as exc:
            if show_log:
                logger.error(f"TCBS derivatives fetch failed: {exc}")
            return pd.Series([], name="symbol", dtype="object")

        records = response if isinstance(response, list) else response.get("data", [])
        if not records:
            return pd.Series([], name="symbol", dtype="object")

        symbols = [r.get("symbol") or r.get("t") for r in records if r.get("symbol") or r.get("t")]
        s = pd.Series(sorted(set(symbols)), name="symbol")
        s.attrs["source"] = self.data_source
        if show_log:
            logger.info(f"TCBS derivatives: {len(s)} symbols.")
        return s
    
    def get_intraday_data(
        self,
        ticker: str,
        page: int = 0,
        size: int = 100,
        show_log: bool = False,
    ) -> pd.DataFrame:
        """
        Get intraday data using the new /nyx/v1/intraday/{ticker}/his/paging endpoint.
        
        Args:
            ticker: Stock symbol.
            page: Page number for pagination.
            size: Number of records per page.
            show_log: Whether to show log messages.
            
        Returns:
            DataFrame with intraday data.
        """
        try:
            url = _INTRADAY_URL_TEMPLATE.format(ticker=ticker.upper())
            params = {
                'page': page,
                'size': size,
                'headIndex': -1
            }
            
            response = client.send_request(
                url=url,
                headers=self.headers,
                method="GET",
                params=params,
                show_log=show_log,
            )
        except Exception as exc:
            if show_log:
                logger.error(f"TCBS intraday fetch failed: {exc}")
            return pd.DataFrame()

        records = response.get("data", []) if isinstance(response, dict) else response
        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df = df.rename(columns=_INTRADAY_COLUMNS)
        
        # Convert data types
        for col in ("price", "volume"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        if "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"], errors="coerce")
        
        return df
    
    def compute_ohlc_from_intraday(
        self,
        ticker: str,
        interval: str = "1D",
        start: Optional[str] = None,
        end: Optional[str] = None,
        show_log: bool = False,
    ) -> pd.DataFrame:
        """
        Compute OHLC data from intraday tick data.
        
        Since the new iFlash OpenAPI doesn't provide OHLC bars directly,
        this method computes them from the intraday tick data.
        
        Args:
            ticker: Stock symbol.
            interval: Time interval (currently only 1D is supported).
            start: Start date (YYYY-MM-DD format).
            end: End date (YYYY-MM-DD format).
            show_log: Whether to show log messages.
            
        Returns:
            DataFrame with OHLC data.
        """
        if interval != "1D":
            if show_log:
                logger.warning(f"OHLC computation for interval {interval} not implemented, using 1D")
        
        # Get intraday data
        df = self.get_intraday_data(ticker, show_log=show_log)
        if df.empty:
            return pd.DataFrame()
        
        # Filter by date range if specified
        if start and end:
            df = df[(df["time"].dt.strftime("%Y-%m-%d") >= start) & 
                   (df["time"].dt.strftime("%Y-%m-%d") <= end)]
        
        # Compute OHLC by date
        if "time" in df.columns and "price" in df.columns:
            # Group by date and compute OHLC
            df["date"] = df["time"].dt.date
            
            ohlc_df = df.groupby("date").agg({
                "price": ["min", "max", "mean", "count"],
                "volume": "sum"
            }).reset_index()
            
            # Flatten multi-level columns
            ohlc_df.columns = [
                "time", "open", "high", "close", "volume"
            ]
            
            # Fill missing values
            ohlc_df["open"] = ohlc_df["open"].fillna(method="ffill")
            ohlc_df["high"] = ohlc_df["high"].fillna(method="ffill")
            ohlc_df["low"] = ohlc_df["low"].fillna(method="ffill")
            ohlc_df["close"] = ohlc_df["close"].fillna(method="ffill")
            
            # Convert to proper format
            ohlc_df["time"] = ohlc_df["time"].apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S") if pd.notnull(x) else None)
            
            return ohlc_df
        
        return pd.DataFrame()
    
    def get_ticker_info(self, tickers: Optional[str] = None, show_log: bool = False) -> pd.DataFrame:
        """
        Get ticker information using the new /tartarus/v1/tickerCommons endpoint.
        
        Args:
            tickers: Comma-separated list of tickers or None for all.
            show_log: Whether to show log messages.
            
        Returns:
            DataFrame with ticker information.
        """
        params = {}
        if tickers:
            params["tickers"] = tickers.upper()
        
        try:
            response = client.send_request(
                url=_TICKER_COMMONS_URL,
                headers=self.headers,
                method="GET",
                params=params if params else None,
                show_log=show_log,
            )
        except Exception as exc:
            if show_log:
                logger.error(f"TCBS ticker info fetch failed: {exc}")
            return pd.DataFrame()

        records = response if isinstance(response, list) else response.get("data", [])
        if not records:
            return pd.DataFrame()
        
        df = pd.DataFrame(records)
        return df
    
    def get_company_data(self, symbol: str, endpoint: str, show_log: bool = False) -> pd.DataFrame:
        """
        Get company data using the new tcanalysis endpoint.
        
        Args:
            symbol: Stock symbol.
            endpoint: Company data endpoint (e.g., "overview", "large-share-holders").
            show_log: Whether to show log messages.
            
        Returns:
            DataFrame with company data.
        """
        try:
            url = f"{_TCANALYSIS_URL_TEMPLATE}/{endpoint}/{symbol}"
            
            response = client.send_request(
                url=url,
                headers=self.headers,
                method="GET",
                show_log=show_log,
            )
        except Exception as exc:
            if show_log:
                logger.error(f"TCBS company data fetch failed: {exc}")
            return pd.DataFrame()

        if isinstance(response, dict):
            return pd.DataFrame([response])
        elif isinstance(response, list):
            return pd.DataFrame(response)
        else:
            return pd.DataFrame()
    
    def get_watchlist(self, filters: List[dict], size: int = 1000, show_log: bool = False) -> List[dict]:
        """
        Get watchlist data using the new ligo endpoint.
        
        Args:
            filters: List of filter conditions.
            size: Maximum number of results.
            show_log: Whether to show log messages.
            
        Returns:
            List of watchlist items.
        """
        payload = {"tcbsID": None, "filters": filters, "size": size}
        
        try:
            response = client.send_request(
                url=_LIGO_WATCHLIST_URL,
                headers=self.headers,
                method="POST",
                payload=payload,
                show_log=show_log,
            )
        except Exception as exc:
            if show_log:
                logger.error(f"TCBS watchlist fetch failed: {exc}")
            return []

        if not response:
            return []
        
        search_data = response.get("searchData", {})
        if not search_data:
            return []
        
        return search_data.get("pageContent") or []