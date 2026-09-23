"""
Brokerage Base Module

Abstract base classes for direct broker API access (Private Brokerage).
These classes bypass Gateway/PAT entirely and connect directly to broker APIs.

Security: Credentials (API Key, Secret, OTP, PIN) never leave this module.
No GatewayHttpClient, no PAT, no vninvest SaaS dependency.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    LO = "LO"      # Limit Order
    MP = "MP"      # Market Price
    MOK = "MOK"    # Market on Open/Close (provider specific)
    ATO = "ATO"    # At the Open
    ATC = "ATC"    # At the Close


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    PARTIAL_FILLED = "PARTIAL_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class TimeInForce(str, Enum):
    DAY = "DAY"
    IOC = "IOC"    # Immediate or Cancel
    FOK = "FOK"    # Fill or Kill
    GTD = "GTD"    # Good Till Date


@dataclass
class OrderRequest:
    symbol: str
    side: OrderSide
    quantity: int
    price: Optional[float] = None
    order_type: OrderType = OrderType.LO
    time_in_force: TimeInForce = TimeInForce.DAY
    expiry_date: Optional[datetime] = None  # For GTD
    account_no: Optional[str] = None  # Override default account


@dataclass
class OrderResponse:
    order_id: str
    symbol: str
    side: OrderSide
    quantity: int
    filled_quantity: int
    price: float
    order_type: OrderType
    status: OrderStatus
    created_at: datetime
    updated_at: datetime
    account_no: str
    raw_response: Dict[str, Any]


@dataclass
class Balance:
    cash_available: float
    cash_blocked: float
    total_cash: float
    margin_available: float
    margin_used: float
    total_equity: float
    currency: str = "VND"
    raw_response: Dict[str, Any] = None


@dataclass
class Position:
    symbol: str
    quantity: int
    avg_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float = 0.0
    side: str = "LONG"  # LONG/SHORT
    raw_response: Dict[str, Any] = None


@dataclass
class MarginInfo:
    margin_ratio: float
    maintenance_margin: float
    initial_margin: float
    margin_call_level: float
    liquidation_level: float
    raw_response: Dict[str, Any] = None


@dataclass
class TickData:
    symbol: str
    price: float
    volume: int
    timestamp: datetime
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    bid_volume: Optional[int] = None
    ask_volume: Optional[int] = None
    side: Optional[str] = None  # BUY/SELL for trade ticks
    raw_response: Dict[str, Any] = None


class BrokerageBase(ABC):
    """
    Abstract base class for direct broker API access.
    
    No PAT, No Gateway, No vninvest dependency.
    Each subclass implements broker-specific authentication and endpoints.
    """
    
    def __init__(
        self,
        api_key: str,
        secret: str,
        account_no: str,
        base_url: Optional[str] = None,
        sandbox: bool = False,
        timeout: float = 30.0,
    ):
        """
        Initialize brokerage client.
        
        Args:
            api_key: Broker API Key (public identifier)
            secret: Broker API Secret (private key for signing)
            account_no: Trading account number
            base_url: Override base URL (for sandbox/custom endpoints)
            sandbox: Use sandbox/test environment
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.secret = secret
        self.account_no = account_no
        self.sandbox = sandbox
        self.timeout = timeout
        
        # Base URL resolution
        self.base_url = base_url or self._get_base_url(sandbox)
        
        # HTTP client (sync)
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers=self._get_default_headers(),
        )
        
        # Async HTTP client (lazy init)
        self._async_client: Optional[httpx.AsyncClient] = None
        
        # WebSocket manager (lazy init)
        self._ws_manager = None
    
    @abstractmethod
    def _get_base_url(self, sandbox: bool) -> str:
        """Return base URL for the broker (production or sandbox)."""
        pass
    
    @abstractmethod
    def _get_default_headers(self) -> Dict[str, str]:
        """Return default headers for all requests."""
        pass
    
    @abstractmethod
    def _sign_request(self, method: str, path: str, payload: Dict[str, Any]) -> Dict[str, str]:
        """
        Sign request and return authentication headers.
        Implement broker-specific signing (HMAC, JWT, etc.)
        """
        pass
    
    @abstractmethod
    def _handle_otp_challenge(self, response: httpx.Response) -> httpx.Response:
        """
        Handle OTP/2FA challenge from broker.
        Return response after OTP resolution.
        """
        pass
    
    # ==================== HTTP Helpers ====================
    
    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """Make signed HTTP request with OTP handling."""
        headers = self._sign_request(method, path, payload or {})
        response = self._client.request(method, path, json=payload, params=params, headers=headers)
        
        # Handle OTP challenge if needed
        if response.status_code == 401 and self._is_otp_challenge(response):
            response = self._handle_otp_challenge(response)
        
        response.raise_for_status()
        return response
    
    async def _async_request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """Make signed async HTTP request with OTP handling."""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self._get_default_headers(),
            )
        
        headers = self._sign_request(method, path, payload or {})
        response = await self._async_client.request(method, path, json=payload, params=params, headers=headers)
        
        if response.status_code == 401 and self._is_otp_challenge(response):
            response = await self._async_handle_otp_challenge(response)
        
        response.raise_for_status()
        return response
    
    def _is_otp_challenge(self, response: httpx.Response) -> bool:
        """Check if response is an OTP challenge. Override in subclass."""
        return False
    
    async def _async_handle_otp_challenge(self, response: httpx.Response) -> httpx.Response:
        """Async OTP handler. Override in subclass."""
        return self._handle_otp_challenge(response)
    
    # ==================== Account Operations ====================
    
    @abstractmethod
    def get_balance(self) -> Balance:
        """Get cash balance, margin info, total equity."""
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Position]:
        """Get current holdings/positions."""
        pass
    
    @abstractmethod
    def get_orders(self, status: Optional[OrderStatus] = None) -> List[OrderResponse]:
        """Get order history, optionally filtered by status."""
        pass
    
    @abstractmethod
    def get_margin_info(self) -> MarginInfo:
        """Get margin ratio, maintenance/initial margin levels."""
        pass
    
    # ==================== Order Execution ====================
    
    @abstractmethod
    def place_order(self, request: OrderRequest) -> OrderResponse:
        """Place a new order."""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> OrderResponse:
        """Cancel an existing order."""
        pass
    
    @abstractmethod
    def modify_order(self, order_id: str, **kwargs) -> OrderResponse:
        """Modify an existing order (price, quantity, etc.)."""
        pass
    
    # ==================== Market Data (Broker-specific) ====================
    
    def get_intraday(self, symbol: str, interval: str = "1m") -> List[Dict[str, Any]]:
        """
        Get intraday OHLCV data (if broker provides).
        Override in subclass if supported.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support intraday")
    
    async def intratick_stream(self, symbols: List[str]) -> AsyncGenerator[TickData, None]:
        """
        Stream real-time tick data via WebSocket (if broker provides).
        Override in subclass if supported.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support intratick streaming")
    
    # ==================== Lifecycle ====================
    
    def close(self):
        """Close HTTP connections."""
        self._client.close()
        if self._async_client:
            import asyncio
            asyncio.run(self._async_client.aclose())
        if self._ws_manager:
            self._ws_manager.close()
    
    async def aclose(self):
        """Async close HTTP connections."""
        self._client.close()
        if self._async_client:
            await self._async_client.aclose()
        if self._ws_manager:
            await self._ws_manager.aclose()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()