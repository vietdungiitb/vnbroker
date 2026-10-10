"""
TCBS Private API Client

Direct connection to TCBS brokerage APIs.
Authentication: HMAC-SHA256 + OTP/2FA
WebSocket: Real-time market data & order updates
"""

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional
import asyncio
import httpx
import websockets

from vnbroker.brokerage.base import (
    BrokerageBase,
    Balance,
    MarginInfo,
    OrderRequest,
    OrderResponse,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    TickData,
)
from vnbroker.brokerage.guards import WriteGateMixin, guarded_write


class TCBSClient(WriteGateMixin, BrokerageBase):
    """
    TCBS Direct Brokerage Client.

    Endpoints (production):
    - REST: https://apipubaws.tcbs.com.vn
    - WebSocket: wss://apipubaws.tcbs.com.vn/ws

    Sandbox:
    - REST: https://apipubaws-sandbox.tcbs.com.vn
    - WebSocket: wss://apipubaws-sandbox.tcbs.com.vn/ws

    Authentication: HMAC-SHA256 signature + API Key + Timestamp
    OTP: SMS/Email/Google Authenticator challenge on sensitive operations

    An toàn đường ghi: kế thừa `WriteGateMixin`. Mọi write method bọc
    `@guarded_write` với `dry_run=True` MẶC ĐỊNH — muốn gửi thật phải đặt
    `dry_run=False` VÀ gọi `enable_write()` trước.
    """
    
    PROD_BASE_URL = "https://apipubaws.tcbs.com.vn"
    SANDBOX_BASE_URL = "https://apipubaws-sandbox.tcbs.com.vn"
    
    PROD_WS_URL = "wss://apipubaws.tcbs.com.vn/ws"
    SANDBOX_WS_URL = "wss://apipubaws-sandbox.tcbs.com.vn/ws"
    
    def __init__(
        self,
        api_key: str,
        secret: str,
        account_no: str,
        base_url: Optional[str] = None,
        sandbox: bool = False,
        timeout: float = 30.0,
        otp_handler: Optional[callable] = None,
    ):
        """
        Initialize TCBS client.
        
        Args:
            api_key: TCBS API Key (from TCBS developer portal)
            secret: TCBS API Secret (base64 encoded)
            account_no: TCBS trading account number
            base_url: Override base URL
            sandbox: Use sandbox environment
            timeout: Request timeout
            otp_handler: Callable(otp_type: str) -> str for OTP resolution
                        otp_type: "sms", "email", "google_auth"
        """
        self.otp_handler = otp_handler
        self._ws_connection = None
        self._ws_subscriptions: Dict[str, asyncio.Queue] = {}
        super().__init__(api_key, secret, account_no, base_url, sandbox, timeout)
    
    def _get_base_url(self, sandbox: bool) -> str:
        return self.SANDBOX_BASE_URL if sandbox else self.PROD_BASE_URL
    
    def _get_ws_url(self) -> str:
        return self.SANDBOX_WS_URL if self.sandbox else self.PROD_WS_URL
    
    def _get_default_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-TCBS-APIKEY": self.api_key,
        }
    
    def _sign_request(self, method: str, path: str, payload: Dict[str, Any]) -> Dict[str, str]:
        """
        TCBS HMAC-SHA256 Signature:
        signature = base64(hmac_sha256(secret, timestamp + method + path + body))
        """
        timestamp = str(int(time.time() * 1000))
        body = json.dumps(payload, separators=(",", ":")) if payload else ""
        
        message = f"{timestamp}{method.upper()}{path}{body}"
        
        # Secret is base64 encoded
        secret_bytes = base64.b64decode(self.secret)
        signature = base64.b64encode(
            hmac.new(secret_bytes, message.encode(), hashlib.sha256).digest()
        ).decode()
        
        return {
            "X-TCBS-TIMESTAMP": timestamp,
            "X-TCBS-SIGNATURE": signature,
            "X-TCBS-APIKEY": self.api_key,
        }
    
    def _is_otp_challenge(self, response: httpx.Response) -> bool:
        """Check if response is OTP challenge."""
        if response.status_code != 401:
            return False
        try:
            data = response.json()
            return data.get("errorCode") == "OTP_REQUIRED" or "otp" in data.get("message", "").lower()
        except Exception:
            return False
    
    def _handle_otp_challenge(self, response: httpx.Response) -> httpx.Response:
        """Handle OTP challenge by requesting OTP from handler."""
        if not self.otp_handler:
            raise RuntimeError("OTP required but no otp_handler provided")
        
        data = response.json()
        otp_type = data.get("otpType", "sms").lower()  # sms, email, google_auth
        challenge_id = data.get("challengeId")
        
        otp_code = self.otp_handler(otp_type)
        
        # Retry original request with OTP
        original_request = response.request
        payload = json.loads(original_request.content) if original_request.content else {}
        payload["otpCode"] = otp_code
        payload["challengeId"] = challenge_id
        
        headers = self._sign_request(original_request.method, original_request.url.path, payload)
        headers["Content-Type"] = "application/json"
        
        retry_response = self._client.request(
            original_request.method,
            original_request.url.path,
            json=payload,
            headers=headers,
        )
        retry_response.raise_for_status()
        return retry_response
    
    # ==================== WebSocket Manager ====================
    
    class _WSManager:
        """Internal WebSocket connection manager."""
        
        def __init__(self, client: "TCBSClient"):
            self.client = client
            self.websocket = None
            self.running = False
            self._tasks: List[asyncio.Task] = []
        
        async def connect(self):
            url = self.client._get_ws_url()
            headers = {
                "X-TCBS-APIKEY": self.client.api_key,
                "Authorization": f"Bearer {self.client._get_ws_token()}",
            }
            
            self.websocket = await websockets.connect(url, extra_headers=headers)
            self.running = True
            
            # Start message handler
            self._tasks.append(asyncio.create_task(self._message_loop()))
        
        def _get_ws_token(self) -> str:
            """Get WebSocket auth token (short-lived)."""
            # TCBS typically uses a separate WS auth endpoint
            response = self.client._request("POST", "/api/v1/websocket/token")
            return response.json()["token"]
        
        async def _message_loop(self):
            try:
                async for message in self.websocket:
                    data = json.loads(message)
                    await self._route_message(data)
            except websockets.exceptions.ConnectionClosed:
                self.running = False
        
        async def _route_message(self, data: Dict[str, Any]):
            channel = data.get("channel")
            if channel in self.client._ws_subscriptions:
                await self.client._ws_subscriptions[channel].put(data)
        
        async def subscribe(self, channel: str) -> AsyncGenerator[Dict[str, Any], None]:
            import asyncio
            if not self.running:
                await self.connect()
            
            # Subscribe to channel
            await self.websocket.send(json.dumps({
                "action": "subscribe",
                "channel": channel,
                "account": self.client.account_no,
            }))
            
            queue = asyncio.Queue()
            self.client._ws_subscriptions[channel] = queue
            
            try:
                while True:
                    yield await queue.get()
            finally:
                del self.client._ws_subscriptions[channel]
                await self.websocket.send(json.dumps({
                    "action": "unsubscribe",
                    "channel": channel,
                }))
        
        async def close(self):
            self.running = False
            for task in self._tasks:
                task.cancel()
            if self.websocket:
                await self.websocket.close()
    
    def _get_ws_manager(self):
        if self._ws_manager is None:
            self._ws_manager = self._WSManager(self)
        return self._ws_manager
    
    # ==================== Account Endpoints ====================
    
    def get_balance(self) -> Balance:
        """Get account balance and cash info."""
        response = self._request("GET", f"/api/v1/accounts/{self.account_no}/balance")
        data = response.json()["data"]
        return Balance(
            cash_available=data["availableCash"],
            cash_blocked=data["blockedCash"],
            total_cash=data["totalCash"],
            margin_available=data.get("availableMargin", 0),
            margin_used=data.get("usedMargin", 0),
            total_equity=data["totalEquity"],
            currency="VND",
            raw_response=data,
        )
    
    def get_positions(self) -> List[Position]:
        """Get current stock positions."""
        response = self._request("GET", f"/api/v1/accounts/{self.account_no}/positions")
        data = response.json()["data"]
        positions = []
        for p in data:
            positions.append(Position(
                symbol=p["symbol"],
                quantity=p["quantity"],
                avg_price=p["avgPrice"],
                current_price=p["currentPrice"],
                market_value=p["marketValue"],
                unrealized_pnl=p["unrealizedPnL"],
                realized_pnl=p.get("realizedPnL", 0),
                side=p.get("side", "LONG"),
                raw_response=p,
            ))
        return positions
    
    def get_orders(self, status: Optional[OrderStatus] = None) -> List[OrderResponse]:
        """Get order history."""
        params = {"account": self.account_no}
        if status:
            params["status"] = status.value
        response = self._request("GET", "/api/v1/orders", params=params)
        data = response.json()["data"]
        orders = []
        for o in data:
            orders.append(OrderResponse(
                order_id=o["orderId"],
                symbol=o["symbol"],
                side=OrderSide(o["side"]),
                quantity=o["quantity"],
                filled_quantity=o["filledQuantity"],
                price=o["price"],
                order_type=OrderType(o["orderType"]),
                status=OrderStatus(o["status"]),
                created_at=datetime.fromisoformat(o["createdAt"]),
                updated_at=datetime.fromisoformat(o["updatedAt"]),
                account_no=o["accountNo"],
                raw_response=o,
            ))
        return orders
    
    def get_margin_info(self) -> MarginInfo:
        """Get margin ratio and levels."""
        response = self._request("GET", f"/api/v1/accounts/{self.account_no}/margin")
        data = response.json()["data"]
        return MarginInfo(
            margin_ratio=data["marginRatio"],
            maintenance_margin=data["maintenanceMargin"],
            initial_margin=data["initialMargin"],
            margin_call_level=data["marginCallLevel"],
            liquidation_level=data["liquidationLevel"],
            raw_response=data,
        )
    
    # ==================== Order Execution ====================
    
    @guarded_write
    def place_order(self, request: OrderRequest, *, dry_run: bool = True) -> OrderResponse:
        """Place a new order.

        `dry_run=True` (mặc định) → KHÔNG gửi lệnh, trả `DryRunResult`.
        Muốn gửi thật: `dry_run=False` và đã gọi `enable_write()`.
        """
        payload = {
            "accountNo": request.account_no or self.account_no,
            "symbol": request.symbol,
            "side": request.side.value,
            "orderType": request.order_type.value,
            "quantity": request.quantity,
            "timeInForce": request.time_in_force.value,
        }
        if request.price is not None:
            payload["price"] = request.price
        if request.expiry_date:
            payload["expiryDate"] = request.expiry_date.strftime("%Y-%m-%d")

        response = self._request("POST", "/api/v1/orders", payload=payload)
        data = response.json()["data"]
        return OrderResponse(
            order_id=data["orderId"],
            symbol=data["symbol"],
            side=OrderSide(data["side"]),
            quantity=data["quantity"],
            filled_quantity=data.get("filledQuantity", 0),
            price=data["price"],
            order_type=OrderType(data["orderType"]),
            status=OrderStatus(data["status"]),
            created_at=datetime.fromisoformat(data["createdAt"]),
            updated_at=datetime.fromisoformat(data["updatedAt"]),
            account_no=data["accountNo"],
            raw_response=data,
        )
    
    @guarded_write
    def cancel_order(self, order_id: str, *, dry_run: bool = True) -> OrderResponse:
        """Cancel an order.

        `dry_run=True` (mặc định) → KHÔNG gửi, trả `DryRunResult`.
        """
        response = self._request("DELETE", f"/api/v1/orders/{order_id}")
        data = response.json()["data"]
        return OrderResponse(
            order_id=data["orderId"],
            symbol=data["symbol"],
            side=OrderSide(data["side"]),
            quantity=data["quantity"],
            filled_quantity=data.get("filledQuantity", 0),
            price=data["price"],
            order_type=OrderType(data["orderType"]),
            status=OrderStatus(data["status"]),
            created_at=datetime.fromisoformat(data["createdAt"]),
            updated_at=datetime.fromisoformat(data["updatedAt"]),
            account_no=data["accountNo"],
            raw_response=data,
        )
    
    @guarded_write
    def modify_order(self, order_id: str, *, dry_run: bool = True, **kwargs) -> OrderResponse:
        """Modify an order (price, quantity).

        `dry_run=True` (mặc định) → KHÔNG gửi, trả `DryRunResult`.
        """
        payload = {}
        if "price" in kwargs:
            payload["price"] = kwargs["price"]
        if "quantity" in kwargs:
            payload["quantity"] = kwargs["quantity"]

        response = self._request("PATCH", f"/api/v1/orders/{order_id}", payload=payload)
        data = response.json()["data"]
        return OrderResponse(
            order_id=data["orderId"],
            symbol=data["symbol"],
            side=OrderSide(data["side"]),
            quantity=data["quantity"],
            filled_quantity=data.get("filledQuantity", 0),
            price=data["price"],
            order_type=OrderType(data["orderType"]),
            status=OrderStatus(data["status"]),
            created_at=datetime.fromisoformat(data["createdAt"]),
            updated_at=datetime.fromisoformat(data["updatedAt"]),
            account_no=data["accountNo"],
            raw_response=data,
        )
    
    # ==================== Market Data (TCBS Specific) ====================
    
    def get_intraday(self, symbol: str, interval: str = "1m") -> List[Dict[str, Any]]:
        """
        Get intraday OHLCV data from TCBS.
        Intervals: 1m, 5m, 15m, 30m, 1H
        """
        params = {"symbol": symbol, "interval": interval}
        response = self._request("GET", "/api/v1/market/intraday", params=params)
        return response.json()["data"]
    
    def get_derivatives_chain(self, underlying: str) -> List[Dict[str, Any]]:
        """Get derivatives/options chain for underlying (TCBS unique)."""
        response = self._request("GET", f"/api/v1/market/derivatives/{underlying}")
        return response.json()["data"]
    
    async def intratick_stream(self, symbols: List[str]) -> AsyncGenerator[TickData, None]:
        """
        Stream real-time tick data via TCBS WebSocket.
        Channel: "tick:{symbol}"
        """
        ws_manager = self._get_ws_manager()
        
        # Subscribe to tick channels for each symbol
        channels = [f"tick:{s}" for s in symbols]
        
        # For simplicity, subscribe to a combined channel if TCBS supports
        # Otherwise, create multiple subscriptions
        for channel in channels:
            async for msg in ws_manager.subscribe(channel):
                yield TickData(
                    symbol=msg["symbol"],
                    price=msg["price"],
                    volume=msg["volume"],
                    timestamp=datetime.fromisoformat(msg["timestamp"]),
                    bid_price=msg.get("bidPrice"),
                    ask_price=msg.get("askPrice"),
                    bid_volume=msg.get("bidVolume"),
                    ask_volume=msg.get("askVolume"),
                    side=msg.get("side"),
                    raw_response=msg,
                )
    
    async def order_updates_stream(self) -> AsyncGenerator[OrderResponse, None]:
        """Stream real-time order status updates."""
        ws_manager = self._get_ws_manager()
        async for msg in ws_manager.subscribe(f"orders:{self.account_no}"):
            yield OrderResponse(
                order_id=msg["orderId"],
                symbol=msg["symbol"],
                side=OrderSide(msg["side"]),
                quantity=msg["quantity"],
                filled_quantity=msg.get("filledQuantity", 0),
                price=msg["price"],
                order_type=OrderType(msg["orderType"]),
                status=OrderStatus(msg["status"]),
                created_at=datetime.fromisoformat(msg["createdAt"]),
                updated_at=datetime.fromisoformat(msg["updatedAt"]),
                account_no=msg["accountNo"],
                raw_response=msg,
            )
    
    # ==================== Lifecycle ====================
    
    def close(self):
        super().close()
        if self._ws_manager:
            import asyncio
            asyncio.run(self._ws_manager.close())
    
    async def aclose(self):
        await super().aclose()
        if self._ws_manager:
            await self._ws_manager.close()


# Convenience alias
TCBSBrokerage = TCBSClient