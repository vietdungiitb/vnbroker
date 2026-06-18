"""
Main entry point and orchestrator for vnbroker library.

This module provides the vnbroker class which acts as the primary interface
for accessing stock, forex, crypto, index, and fund data from various providers.

Architecture: Direct Provider Access Only
- VCI, KBS, TCBS, DNSE: Direct provider access with own credentials
- No PAT/Gateway required (v3.0+)
"""

import logging
from typing import Optional

from vnbroker.core.utils.logger import get_logger
from vnbroker.common.data import (
    StockComponents,
    Fund,
)

logger = get_logger(__name__)


class Vnbroker:
    """
    Main entry point for the vnbroker library (Direct Provider Architecture).
    
    Provides unified access to stock data, forex quotes, crypto prices,
    world indices, and fund information via direct provider access.
    
    Supported Sources:
    - "KBS": Korea Investment (KIS) - default
    - "VCI", "TCBS", "DNSE": Direct provider access
    
    Example:
        >>> # Direct provider mode (no PAT needed)
        >>> vn = Vnbroker()
        >>> acb = vn.stock('ACB')  # Uses default KBS
        >>> acb = vn.stock('ACB', source='VCI')  # Direct VCI access
        >>> acb = vn.stock('ACB', source='DNSE')  # Direct DNSE access (requires DNSE_API_KEY + DNSE_API_SECRET)
    """
    
    SUPPORTED_SOURCES = ["KBS", "VCI", "TCBS", "DNSE"]
    DEFAULT_SOURCE = "KBS"

    def __init__(
        self, 
        symbol: Optional[str] = None, 
        source: str = "KBS",
        show_log: bool = True,
    ):
        """
        Initialize vnbroker client with direct provider support.
        
        Args:
            symbol (str, optional): Default symbol for stock queries.
                Defaults to None.
            source (str): Default data source. 
                - "KBS", "VCI", "TCBS": Direct provider access (no auth)
                - "DNSE": Direct provider access (requires DNSE_API_KEY + DNSE_API_SECRET env vars)
                Defaults to "KBS".
            show_log (bool): Whether to display log messages.
                Defaults to True.
        
        Raises:
            ValueError: If source is not in SUPPORTED_SOURCES
        """
        self.symbol = symbol
        self.source = source.upper()
        self.show_log = show_log
        
        if self.source not in self.SUPPORTED_SOURCES:
            raise ValueError(
                f"Supported sources: {', '.join(self.SUPPORTED_SOURCES)}. "
                f"Got: {source}"
            )
        
        if not show_log:
            logger.setLevel(logging.CRITICAL)
    
    def stock(self, symbol: Optional[str] = None,
              source: Optional[str] = None) -> StockComponents:
        """
        Get stock data components for a symbol.
        
        Args:
            symbol (str, optional): Stock symbol (e.g., 'ACB', 'VNM').
                Defaults to 'VN30F1M' if not specified.
            source (str, optional): Data source override.
                - "KBS", "VCI", "TCBS", "DNSE": Direct provider access
                Defaults to instance source if not specified.
        
        Returns:
            StockComponents: Object with quote, company, finance, etc.
        
        Example:
            >>> # Direct provider mode
            >>> vn = Vnbroker()
            >>> acb = vn.stock('ACB')  # Uses default KBS
            >>> acb = vn.stock('ACB', source='VCI')  # Direct VCI access
            >>> acb = vn.stock('ACB', source='DNSE')  # Direct DNSE access (requires DNSE_API_KEY + DNSE_API_SECRET)
        """
        if symbol is None:
            symbol = 'VN30F1M'
            if self.show_log:
                logger.info("Symbol not specified, using default: VN30F1M")
        else:
            self.symbol = symbol

        # Determine effective source
        effective_source = (source or self.source).upper()
        
        if effective_source not in self.SUPPORTED_SOURCES:
            raise ValueError(
                f"Source '{effective_source}' is not supported. "
                f"Supported: {', '.join(self.SUPPORTED_SOURCES)}"
            )
        
        return StockComponents(
            self.symbol,
            effective_source,
            show_log=self.show_log,
        )

    def fx(self, symbol: Optional[str] = 'EURUSD',
            source: Optional[str] = None):
        """
        Get forex (currency) data.
        
        Args:
            symbol (str): Currency pair (e.g., 'EURUSD', 'GBPUSD').
                Defaults to 'EURUSD'.
            source (str): Data source.
                - "KBS", "VCI", "TCBS", "DNSE": Direct provider access
                Defaults to instance source if not specified.
        
        Returns:
            Object with quote and listing components.
        
        Example:
            >>> vn = Vnbroker()
            >>> eurusd = vn.fx('EURUSD', source='KBS')
            >>> history = eurusd.quote.history('2023-01-01', '2023-12-31')
        """
        effective_source = (source or self.source).upper()
        if effective_source not in self.SUPPORTED_SOURCES:
            raise ValueError(
                f"Source '{source}' is not supported. "
                f"Supported: {', '.join(self.SUPPORTED_SOURCES)}"
            )

        from vnbroker.common.data import Quote, Listing
        return type('FXComponents', (), {
            'quote': Quote(symbol, effective_source),
            'listing': Listing(effective_source),
            'symbol': symbol,
            'source': effective_source,
        })()

    def crypto(self, symbol: Optional[str] = 'BTC',
               source: Optional[str] = None):
        """
        Get cryptocurrency data.
        
        Args:
            symbol (str): Crypto symbol (e.g., 'BTC', 'ETH').
                Defaults to 'BTC'.
            source (str): Data source.
                - "KBS", "VCI", "TCBS", "DNSE": Direct provider access
                Defaults to instance source if not specified.
        
        Returns:
            Object with quote and listing components.
        
        Example:
            >>> vn = Vnbroker()
            >>> btc = vn.crypto('BTC', source='KBS')
        """
        effective_source = (source or self.source).upper()
        if effective_source not in self.SUPPORTED_SOURCES:
            raise ValueError(
                f"Source '{source}' is not supported. "
                f"Supported: {', '.join(self.SUPPORTED_SOURCES)}"
            )

        from vnbroker.common.data import Quote, Listing
        return type('CryptoComponents', (), {
            'quote': Quote(symbol, effective_source),
            'listing': Listing(effective_source),
            'symbol': symbol,
            'source': effective_source,
        })()

    def world_index(self, symbol: Optional[str] = 'DJI',
                  source: Optional[str] = None):
        """
        Get world market index data.
        
        Args:
            symbol (str): Index symbol (e.g., 'DJI', 'IXIC').
                Defaults to 'DJI' (Dow Jones).
            source (str): Data source.
                - "KBS", "VCI", "TCBS", "DNSE": Direct provider access
                Defaults to instance source if not specified.
        
        Returns:
            Object with quote and listing components.
        
        Example:
            >>> vn = Vnbroker()
            >>> djia = vn.world_index('DJI', source='KBS')
        """
        effective_source = (source or self.source).upper()
        if effective_source not in self.SUPPORTED_SOURCES:
            raise ValueError(
                f"Source '{source}' is not supported. "
                f"Supported: {', '.join(self.SUPPORTED_SOURCES)}"
            )

        from vnbroker.common.data import Quote, Listing
        return type('IndexComponents', (), {
            'quote': Quote(symbol, effective_source),
            'listing': Listing(effective_source),
            'symbol': symbol,
            'source': effective_source,
        })()

    def fund(self, source: str = "FMARKET") -> Fund:
        """
        Get fund/mutual fund data.
        
        Args:
            source (str): Data source. Only FMARKET is currently supported.
                Defaults to "FMARKET".
        
        Returns:
            Fund: Object with fund data and methods.
        
        Example:
            >>> funds = stock.fund()
            >>> all_funds = funds.listing()
        """
        return Fund(source)
