"""
Main entry point and orchestrator for vnbroker library.

This module provides the vnbroker class which acts as the primary interface
for accessing stock, forex, crypto, index, and fund data from various sources.

Architecture: PAT-Only with Hybrid Gateway + Emergency Fallback
- All requests route through vninvest SaaS Gateway with PAT authentication
- Emergency fallback to local explorers when Gateway is unavailable (10 calls/day)
"""

import logging
import os
from typing import Optional, Any, Dict

from vnbroker.core.utils.logger import get_logger
from vnbroker.core.utils.gateway_client import GatewayHttpClient, DEFAULT_PAT
from vnbroker.core.exceptions import (
    AuthenticationError,
    InvalidPATFormatError,
    GatewayUnavailableError,
    EmergencyQuotaExceededError,
)
from vnbroker.explorer.tcbs.auth import request_openapi_token
from vnbroker.common.data import (
    StockComponents,
    Fund,
    _load_msn_const,
    _CURRENCY_ID_MAP,
    _GLOBAL_INDICES,
    _CRYPTO_ID_MAP,
)

logger = get_logger(__name__)


class Vnbroker:
    """
    Main entry point for the vnbroker library (PAT-Only Architecture).
    
    Provides unified access to stock data, forex quotes, crypto prices,
    world indices, and fund information via vninvest SaaS Gateway.
    
    Authentication: Personal Access Token (PAT) required.
    - Format: vninvest_pat_<token>
    - Sources: Explicit parameter > VNBROKER_PAT_KEY env > Default PAT (free tier)
    - Default PAT provides limited quota (100 req/day) for testing
    
    Architecture:
    - Primary: Gateway API (caching, quota management, rate limiting)
    - Fallback: Direct provider calls (VCI/KBS/TCBS/MSN) - max 10 calls/day
    
    Attributes:
        SUPPORTED_SOURCES (list): List of supported data sources.
        msn_symbol_map (dict): Mapping of MSN symbols.
    
    Example:
        >>> # With explicit PAT (recommended)
        >>> vn = Vnbroker(pat_key="vninvest_pat_your_token_here")
        >>> acb = vn.stock('ACB')
        >>> history = acb.quote.history('2024-01-01', '2024-12-31')
        
        >>> # With environment variable (VNBROKER_PAT_KEY)
        >>> vn = Vnbroker()
        >>> acb = vn.stock('ACB')
        
        >>> # Default PAT (free tier, limited quota)
        >>> vn = Vnbroker()  # Uses DEFAULT_PAT automatically
    """
    
    SUPPORTED_SOURCES = ["GATEWAY", "AUTO"]
    DEFAULT_SOURCE = "GATEWAY"

    def __init__(
        self, 
        symbol: Optional[str] = None, 
        source: str = "GATEWAY",
        pat_key: Optional[str] = None,
        gateway_url: Optional[str] = None,
        show_log: bool = True
    ):
        """
        Initialize vnbroker client with PAT authentication.
        
        Args:
            symbol (str, optional): Default symbol for stock queries.
                Defaults to None.
            source (str): Default data source. 
                - "GATEWAY": Route through vninvest SaaS Gateway (default, requires PAT)
                - "AUTO": Automatic source selection via Gateway
                Defaults to "GATEWAY".
            pat_key (str, optional): Personal Access Token.
                Format: vninvest_pat_<token>
                Priority: explicit > VNBROKER_PAT_KEY env > DEFAULT_PAT (free tier)
            gateway_url (str, optional): Gateway base URL.
                Priority: explicit > VNBROKER_GATEWAY_URL env > https://api.vnstocks.com
            show_log (bool): Whether to display log messages.
                Defaults to True.
        
        Raises:
            InvalidPATFormatError: If PAT format is invalid
            ValueError: If source is not in SUPPORTED_SOURCES
        """
        self.symbol = symbol
        self.source = source.upper()
        self.show_log = show_log
        self._gateway_client: Optional[GatewayHttpClient] = None
        self._use_gateway = True
        
        if self.source not in self.SUPPORTED_SOURCES:
            raise ValueError(
                f"Supported sources: {', '.join(self.SUPPORTED_SOURCES)}. "
                f"Got: {source}"
            )
        
        if not show_log:
            logger.setLevel(logging.CRITICAL)
        
        # Initialize Gateway client
        self._init_gateway_client(pat_key, gateway_url)
    
    def _init_gateway_client(self, pat_key: Optional[str], gateway_url: Optional[str]) -> None:
        """Initialize Gateway HTTP client with PAT authentication."""
        try:
            self._gateway_client = GatewayHttpClient(
                pat_key=pat_key,
                base_url=gateway_url,
                show_log=self.show_log,
            )
            if self.show_log:
                logger.info("Gateway client initialized successfully")
                logger.debug(f"PAT: {self._gateway_client.pat_key[:20]}...")
        except InvalidPATFormatError as e:
            if self.show_log:
                logger.error(f"Invalid PAT format: {e}")
            raise
        except Exception as e:
            if self.show_log:
                logger.error(f"Failed to initialize Gateway client: {e}")
            raise

    @property
    def gateway_client(self) -> GatewayHttpClient:
        """Get or create Gateway HTTP client."""
        if self._gateway_client is None:
            self._init_gateway_client(None, None)
        return self._gateway_client

    @property
    def msn_symbol_map(self):
        """Lazy load MSN symbol map to avoid circular import."""
        _load_msn_const()
        return {
            **_CURRENCY_ID_MAP,
            **_GLOBAL_INDICES,
            **_CRYPTO_ID_MAP,
        }

    def _gateway_request(
        self,
        endpoint: str,
        method: str = "POST",
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute request via Gateway with emergency fallback.
        
        This is the core method that implements the Hybrid Model:
        1. Try Gateway first
        2. On connection failure, activate emergency fallback
        3. Track emergency quota (10 calls/day)
        """
        if not self._use_gateway:
            raise RuntimeError("Gateway request called but client not in GATEWAY mode")
        
        try:
            return self.gateway_client.request(endpoint, method, json_data, params)
        except GatewayUnavailableError:
            # Gateway down - try emergency fallback
            if self.show_log:
                logger.warning("Gateway unavailable, attempting emergency fallback...")
            try:
                return self.gateway_client._emergency_fallback(endpoint, json_data, params)
            except EmergencyQuotaExceededError:
                # Emergency quota exhausted
                if self.show_log:
                    logger.error("Emergency fallback quota exceeded (10 calls/day)")
                raise
        except (AuthenticationError, EmergencyQuotaExceededError):
            # Re-raise auth and emergency quota errors
            raise
        except Exception as e:
            # Other errors - try fallback as last resort
            if self.show_log:
                logger.warning(f"Gateway error: {e}. Attempting emergency fallback...")
            try:
                return self.gateway_client._emergency_fallback(endpoint, json_data, params)
            except EmergencyQuotaExceededError:
                raise

    def stock(self, symbol: Optional[str] = None,
              source: Optional[str] = None) -> StockComponents:
        """
        Get stock data components for a symbol.
        
        All data requests route through the vninvest SaaS Gateway with PAT authentication.
        
        Args:
            symbol (str, optional): Stock symbol (e.g., 'ACB', 'VNM').
                Defaults to 'VN30F1M' if not specified.
            source (str, optional): Data source override.
                Only "GATEWAY" or "AUTO" are supported.
                Defaults to instance source if not specified.
        
        Returns:
            StockComponents: Object with quote, company, finance, etc.
        
        Example:
            >>> vn = Vnbroker(pat_key="vninvest_pat_your_token")
            >>> acb = vn.stock('ACB')
            >>> history = acb.quote.history('2024-01-01', '2024-12-31')
            >>> profile = acb.company.profile()
        """
        if symbol is None:
            symbol = 'VN30F1M'
            if self.show_log:
                logger.info("Symbol not specified, using default: VN30F1M")
        else:
            self.symbol = symbol

        # Determine effective source (only GATEWAY or AUTO allowed)
        effective_source = source or self.source
        
        if effective_source.upper() not in self.SUPPORTED_SOURCES:
            raise ValueError(
                f"Source '{effective_source}' is not supported. "
                f"Only GATEWAY and AUTO are allowed."
            )
        
        # Always use Gateway
        return StockComponents(
            self.symbol,
            effective_source.upper(),
            show_log=self.show_log,
            gateway_client=self.gateway_client,
            gateway_request_func=self._gateway_request,
        )

    def fx(self, symbol: Optional[str] = 'EURUSD',
            source: Optional[str] = "GATEWAY"):
        """
        Get forex (currency) data via Gateway.
        
        Args:
            symbol (str): Currency pair (e.g., 'EURUSD', 'GBPUSD').
                Defaults to 'EURUSD'.
            source (str): Data source. Only GATEWAY or AUTO supported.
                Defaults to "GATEWAY".
        
        Returns:
            Object with quote and listing components.
        
        Example:
            >>> eurusd = stock.fx('EURUSD')
            >>> history = eurusd.quote.history('2023-01-01', '2023-12-31')
        """
        if source.upper() not in self.SUPPORTED_SOURCES:
            raise ValueError(
                f"Source '{source}' is not supported. "
                f"Only GATEWAY and AUTO are allowed."
            )
        
        if symbol:
            mapped_symbol = self.msn_symbol_map.get(symbol, symbol)
            logger.debug(f"Mapped {symbol} -> {mapped_symbol}")
        else:
            mapped_symbol = symbol

        # Return a simple object with quote and listing for forex
        from vnbroker.common.data import Quote, Listing
        return type('FXComponents', (), {
            'quote': Quote(mapped_symbol, source, gateway_client=self.gateway_client, gateway_request_func=self._gateway_request),
            'listing': Listing(source, gateway_client=self.gateway_client, gateway_request_func=self._gateway_request),
            'symbol': mapped_symbol,
            'source': source,
        })()

    def crypto(self, symbol: Optional[str] = 'BTC',
               source: Optional[str] = "GATEWAY"):
        """
        Get cryptocurrency data via Gateway.
        
        Args:
            symbol (str): Crypto symbol (e.g., 'BTC', 'ETH').
                Defaults to 'BTC'.
            source (str): Data source. Only GATEWAY or AUTO supported.
                Defaults to "GATEWAY".
        
        Returns:
            Object with quote and listing components.
        
        Example:
            >>> btc = stock.crypto('BTC')
            >>> history = btc.quote.history('2023-01-01', '2023-12-31')
        """
        if source.upper() not in self.SUPPORTED_SOURCES:
            raise ValueError(
                f"Source '{source}' is not supported. "
                f"Only GATEWAY and AUTO are allowed."
            )
        
        if symbol:
            mapped_symbol = self.msn_symbol_map.get(symbol, symbol)
            logger.debug(f"Mapped {symbol} -> {mapped_symbol}")
        else:
            mapped_symbol = symbol

        # Return a simple object with quote and listing for crypto
        from vnbroker.common.data import Quote, Listing
        return type('CryptoComponents', (), {
            'quote': Quote(mapped_symbol, source, gateway_client=self.gateway_client, gateway_request_func=self._gateway_request),
            'listing': Listing(source, gateway_client=self.gateway_client, gateway_request_func=self._gateway_request),
            'symbol': mapped_symbol,
            'source': source,
        })()

    def world_index(self, symbol: Optional[str] = 'DJI',
                    source: Optional[str] = "GATEWAY"):
        """
        Get world market index data via Gateway.
        
        Args:
            symbol (str): Index symbol (e.g., 'DJI', 'IXIC').
                Defaults to 'DJI' (Dow Jones).
            source (str): Data source. Only GATEWAY or AUTO supported.
                Defaults to "GATEWAY".
        
        Returns:
            Object with quote and listing components.
        
        Example:
            >>> djia = stock.world_index('DJI')
            >>> history = djia.quote.history('2023-01-01', '2023-12-31')
        """
        if source.upper() not in self.SUPPORTED_SOURCES:
            raise ValueError(
                f"Source '{source}' is not supported. "
                f"Only GATEWAY and AUTO are allowed."
            )
        
        if symbol:
            mapped_symbol = self.msn_symbol_map.get(symbol, symbol)
            logger.debug(f"Mapped {symbol} -> {mapped_symbol}")
        else:
            mapped_symbol = symbol

        # Return a simple object with quote and listing for world indices
        from vnbroker.common.data import Quote, Listing
        return type('IndexComponents', (), {
            'quote': Quote(mapped_symbol, source, gateway_client=self.gateway_client, gateway_request_func=self._gateway_request),
            'listing': Listing(source, gateway_client=self.gateway_client, gateway_request_func=self._gateway_request),
            'symbol': mapped_symbol,
            'source': source,
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

    def broker(
        self,
        provider: str = "tcbs",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """
        Trả về broker client để thực hiện giao dịch qua broker API.

        Client trả về chưa authenticated — cần gọi .authenticate(otp=...) trước
        khi dùng bất kỳ read/write method nào.

        Args:
            provider: Tên broker provider. Hiện tại chỉ hỗ trợ "tcbs".
            api_key: API key (tùy chọn — đọc từ env VNBROKER_BROKER_TCBS_API_KEY nếu không truyền).
            base_url: Override base URL (tùy chọn).

        Returns:
            BaseBrokerClient subclass tương ứng với provider.

        Example:
            >>> vn = Vnbroker()
            >>> client = vn.broker(provider='tcbs', api_key='your-key')
            >>> client.authenticate(otp='123456')
            >>> balance = client.get_balance(account_no='0123456789')
        """
        from vnbroker.api.broker import get_broker  # noqa: PLC0415
        return get_broker(provider=provider, api_key=api_key, base_url=base_url)
