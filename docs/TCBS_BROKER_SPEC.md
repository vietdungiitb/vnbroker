# TCBS Broker Spec

**Version:** 1.0  
**Cập nhật:** 2026-05-19  
**Phạm vi:** Class/method signatures contract cho `vnbroker/broker/tcbs/`. Đội code implement theo đây — không được thêm/bớt signature public mà không cập nhật tài liệu này trước.

---

## 1. Exceptions — `vnbroker/broker/tcbs/exceptions.py`

```python
class BrokerError(Exception):
    """Base exception cho mọi lỗi từ broker lane."""
    def __init__(self, message: str, code: str = "", http_status: int = 0, request_id: str = ""):
        self.message = message
        self.code = code
        self.http_status = http_status
        self.request_id = request_id
        super().__init__(message)

class BrokerAuthError(BrokerError): ...         # 401 — OTP sai, token hết hạn
class BrokerSessionExpiredError(BrokerError): ... # 401 code=SESSION_EXPIRED
class BrokerPermissionError(BrokerError): ...   # 403 — không đủ quyền
class BrokerValidationError(BrokerError): ...   # 400 — input sai
class BrokerRateLimitError(BrokerError): ...    # 429 — rate limit
class BrokerOrderError(BrokerError): ...        # 422 — lỗi nghiệp vụ lệnh
class BrokerNetworkError(BrokerError): ...      # timeout / 5xx
```

---

## 2. Security Layer — `vnbroker/broker/security/`

### 2.1 `credentials.py`

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class TCBSCredentialConfig:
    api_key: str                    # Bắt buộc — KHÔNG log
    base_url: str = "https://openapi.tcbs.com.vn"
    timeout_seconds: float = 30.0
    auth_token: Optional[str] = None  # Inject sẵn JWT nếu có

def resolve_tcbs_credentials(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    auth_token: Optional[str] = None,
) -> TCBSCredentialConfig:
    """
    Đọc credentials theo thứ tự ưu tiên:
    1. Tham số trực tiếp
    2. VNBROKER_BROKER_TCBS_API_KEY
    3. vnbroker_TCBS_OPENAPI_API_KEY
    4. TCBS_OPENAPI_API_KEY
    5. TCBS_API_KEY
    Raises ValueError nếu không tìm thấy api_key.
    """
    ...
```

---

### 2.2 `redaction.py`

```python
from typing import Any

SENSITIVE_KEYS: frozenset = frozenset({
    "apikey", "api_key", "otp", "pincode", "pin_code",
    "authorization", "token", "password", "secret",
    "accountno", "custodycode", "idno", "phone", "email",
    "authorization",
})

class Redactor:
    REDACTED = "***REDACTED***"

    @staticmethod
    def redact_dict(data: dict, keys: frozenset = SENSITIVE_KEYS) -> dict:
        """
        Trả về bản sao dict với các key nhạy cảm đã thay bằng REDACTED.
        So sánh key case-insensitive. Xử lý nested dict đệ quy.
        """
        ...

    @staticmethod
    def redact_headers(headers: dict) -> dict:
        """Redact Authorization header value. Giữ nguyên key khác."""
        ...
```

---

### 2.3 `audit.py`

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

@dataclass
class AuditRecord:
    timestamp: datetime
    operation: str              # "authenticate", "get_balance", "place_order", ...
    account_no: str             # Đã redact nếu cần, hoặc masked last 4
    request_id: str
    dry_run: bool
    success: bool
    error_code: Optional[str] = None
    metadata: dict = field(default_factory=dict)  # Không chứa secret

class AuditSink:
    """
    Ghi audit records ra structured log.
    Không phụ thuộc vào logger generic của vnbroker/core/utils.
    """
    def __init__(self, sink_name: str = "vnbroker.broker.audit"):
        self._logger = ...  # logger riêng, KHÔNG phải get_logger từ core

    def record(self, rec: AuditRecord) -> None:
        """Ghi record ra log theo dạng structured JSON."""
        ...
```

---

### 2.4 `idempotency.py`

```python
class IdempotencyStore:
    """
    In-memory store với TTL — kiểm tra idempotency key trước khi gửi write request.
    Không dùng Redis (dependency quá nặng cho alpha); có thể swap sau.
    """
    def __init__(self, ttl_seconds: int = 300):
        self._store: dict[str, float] = {}  # key → timestamp
        self._ttl = ttl_seconds

    def check_and_store(self, key: str) -> bool:
        """
        Trả về True nếu key chưa tồn tại (được phép tiến hành).
        Trả về False nếu key đã tồn tại và chưa TTL (duplicate — từ chối).
        Tự dọn dẹp expired keys khi check.
        """
        ...

    def mark_completed(self, key: str) -> None:
        """Đánh dấu key đã hoàn thành (có thể dùng để phân biệt in-flight vs completed)."""
        ...
```

---

### 2.5 `guards.py`

```python
import functools
from typing import Callable, Any

def write_gate(fn: Callable) -> Callable:
    """
    Decorator bắt buộc trên mọi write method.
    Nếu dry_run=True → không gọi HTTP, trả về debug dict đã redact.
    Nếu session chưa authenticated_write_enabled → raise BrokerPermissionError.
    """
    @functools.wraps(fn)
    def wrapper(self, *args, dry_run: bool = True, **kwargs) -> Any:
        ...
    return wrapper
```

---

## 3. Session — `vnbroker/broker/session.py`

```python
from enum import Enum, auto
from datetime import datetime
from typing import Optional

class SessionState(Enum):
    CREATED = auto()
    AUTHENTICATING = auto()
    AUTHENTICATED_READ = auto()
    AUTHENTICATED_WRITE_ENABLED = auto()
    EXPIRED = auto()
    LOCKED = auto()

class BrokerSession:
    """
    State machine cho vòng đời session broker.
    
    Transitions:
      CREATED → AUTHENTICATING (khi gọi authenticate())
      AUTHENTICATING → AUTHENTICATED_READ (khi nhận token thành công)
      AUTHENTICATED_READ → AUTHENTICATED_WRITE_ENABLED (khi enable_write() gọi)
      AUTHENTICATED_READ/WRITE → EXPIRED (khi token hết hạn hoặc gọi revoke())
      * → LOCKED (khi phát hiện security violation)
    """
    def __init__(self):
        self.state: SessionState = SessionState.CREATED
        self._token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._account_no: Optional[str] = None

    @property
    def token(self) -> Optional[str]:
        """Trả về token nếu session chưa expired. Raise BrokerSessionExpiredError nếu đã expired."""
        ...

    @property
    def is_write_enabled(self) -> bool:
        return self.state == SessionState.AUTHENTICATED_WRITE_ENABLED

    def set_token(self, token: str, expires_at: Optional[datetime] = None) -> None:
        """Lưu token và chuyển state → AUTHENTICATED_READ."""
        ...

    def enable_write(self) -> None:
        """Chuyển state → AUTHENTICATED_WRITE_ENABLED. Raise nếu chưa AUTHENTICATED_READ."""
        ...

    def revoke(self) -> None:
        """Xoá token, chuyển state → EXPIRED."""
        ...

    def lock(self, reason: str) -> None:
        """Khoá session, chuyển state → LOCKED. Không thể unlock."""
        ...
```

---

## 4. Auth Service — `vnbroker/broker/tcbs/auth.py`

```python
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.security.credentials import TCBSCredentialConfig

class TCBSAuthService:
    def __init__(self, config: TCBSCredentialConfig, session: BrokerSession):
        self._config = config
        self._session = session

    def authenticate(self, otp: str) -> None:
        """
        Gửi apiKey + otp đến POST /gaia/v1/oauth2/openapi/token.
        Lưu token vào session. KHÔNG log apiKey hoặc otp.
        Raise BrokerAuthError nếu TCBS trả lỗi.
        Raise ValueError nếu otp rỗng.
        """
        ...

    def is_token_valid(self) -> bool:
        """Trả về True nếu session có token và chưa hết hạn."""
        ...

    def revoke(self) -> None:
        """Huỷ session hiện tại."""
        ...
```

---

## 5. Account Service — `vnbroker/broker/tcbs/account.py`

```python
import pandas as pd
from typing import Union

class TCBSAccountService:
    def __init__(self, config: TCBSCredentialConfig, session: BrokerSession):
        ...

    def list_accounts(self, raw: bool = False) -> Union[pd.DataFrame, list]:
        """GET /gaia/v1/openapi/account/list"""
        ...

    def get_profile(self, account_no: str, raw: bool = False) -> Union[pd.DataFrame, dict]:
        """GET /gaia/v1/openapi/account/{accountNo}/profile"""
        ...

    def get_balance(self, account_no: str, raw: bool = False) -> Union[pd.DataFrame, dict]:
        """GET /gaia/v1/openapi/account/{accountNo}/balance"""
        ...

    def get_purchasing_power(self, account_no: str, raw: bool = False) -> Union[pd.DataFrame, dict]:
        """GET /gaia/v1/openapi/account/{accountNo}/portfolio/purchasing-power"""
        ...
```

---

## 6. Money Service — `vnbroker/broker/tcbs/money.py`

```python
class TCBSMoneyService:
    def __init__(self, config: TCBSCredentialConfig, session: BrokerSession):
        ...

    def get_cash(self, account_no: str, raw: bool = False) -> Union[pd.DataFrame, dict]:
        """GET /gaia/v1/openapi/account/{accountNo}/money/cash"""
        ...

    def get_margin(self, account_no: str, raw: bool = False) -> Union[pd.DataFrame, dict]:
        """GET /gaia/v1/openapi/account/{accountNo}/money/margin"""
        ...
```

---

## 7. Equity Service — `vnbroker/broker/tcbs/equity.py`

```python
from datetime import date
from typing import Optional, Union

class TCBSEquityService:
    def __init__(self, config: TCBSCredentialConfig, session: BrokerSession,
                 audit: AuditSink, idempotency: IdempotencyStore):
        ...

    # --- READ ---
    def get_orders(self, account_no: str, page: int = 0, size: int = 50,
                   raw: bool = False) -> Union[pd.DataFrame, dict]:
        """GET /gaia/v1/openapi/account/{accountNo}/orders"""
        ...

    def get_order(self, account_no: str, order_id: str,
                  raw: bool = False) -> Union[pd.DataFrame, dict]:
        """GET /gaia/v1/openapi/account/{accountNo}/orders/{orderId}"""
        ...

    def get_executions(self, account_no: str, from_date: date, to_date: date,
                       page: int = 0, size: int = 50,
                       raw: bool = False) -> Union[pd.DataFrame, dict]:
        """GET /gaia/v1/openapi/account/{accountNo}/executions"""
        ...

    def get_order_history(self, account_no: str, from_date: date, to_date: date,
                          symbol: Optional[str] = None,
                          page: int = 0, size: int = 50,
                          raw: bool = False) -> Union[pd.DataFrame, dict]:
        """GET /gaia/v1/openapi/account/{accountNo}/orders/history"""
        ...

    # --- WRITE (dry_run=True bắt buộc khi chưa có production sign-off) ---
    def place_order(
        self,
        account_no: str,
        symbol: str,
        side: str,           # "BUY" | "SELL"
        order_type: str,     # "LIMIT" | "MARKET" | "MP" | "ATO" | "ATC"
        quantity: int,
        price: float,
        pin_code: str,       # KHÔNG log
        request_id: str,     # UUID idempotency key
        dry_run: bool = True,
    ) -> dict:
        """POST /gaia/v1/openapi/account/{accountNo}/orders"""
        ...

    def update_order(
        self,
        account_no: str,
        order_id: str,
        quantity: int,
        price: float,
        request_id: str,
        dry_run: bool = True,
    ) -> dict:
        """PUT /gaia/v1/openapi/account/{accountNo}/orders/{orderId}"""
        ...

    def cancel_order(
        self,
        account_no: str,
        order_id: str,
        request_id: str,
        dry_run: bool = True,
    ) -> dict:
        """DELETE /gaia/v1/openapi/account/{accountNo}/orders/{orderId}"""
        ...
```

---

## 8. Derivatives Service — `vnbroker/broker/tcbs/derivatives.py`

```python
class TCBSDerivativesService:
    def __init__(self, config: TCBSCredentialConfig, session: BrokerSession):
        ...

    def get_positions(self, account_no: str, raw: bool = False) -> Union[pd.DataFrame, list]:
        """GET /gaia/v1/openapi/account/{accountNo}/derivatives/positions"""
        ...

    def get_orders(self, account_no: str, raw: bool = False) -> Union[pd.DataFrame, dict]:
        """GET /gaia/v1/openapi/account/{accountNo}/derivatives/orders"""
        ...
```

---

## 9. Portfolio Engine — `vnbroker/broker/tcbs/portfolio.py`

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class HoldingRecord:
    symbol: str
    quantity: int
    average_cost: float     # VND/cp, đã tính phí mua gốc
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    cost_basis: float       # = average_cost * quantity
    as_of: datetime

@dataclass
class PortfolioLedgerEntry:
    date: datetime
    symbol: str
    action: str             # "BUY" | "SELL" | "DIVIDEND" | "ADJUST"
    quantity: int
    price: float
    fee: float
    tax: float
    net_amount: float       # Dương = tiền vào, âm = tiền ra
    order_id: Optional[str] = None
    request_id: Optional[str] = None

class PortfolioEngine:
    """
    Tính toán holdings, cost basis, PnL, return metrics từ ledger.
    Không gọi TCBS API trực tiếp — nhận data từ TCBSEquityService.
    """
    def __init__(self):
        self._ledger: list[PortfolioLedgerEntry] = []

    def ingest_executions(self, executions_df: pd.DataFrame) -> None:
        """Đọc DataFrame executions từ TCBSEquityService và ghi vào ledger."""
        ...

    def get_holdings(self, current_prices: dict[str, float]) -> list[HoldingRecord]:
        """
        Tính holdings tại thời điểm hiện tại từ ledger + current_prices.
        Dùng FIFO cost basis.
        """
        ...

    def get_portfolio_summary(self, current_prices: dict[str, float]) -> dict:
        """
        Trả về:
          total_cost_basis, total_market_value, total_unrealized_pnl,
          total_unrealized_pnl_pct, holdings: list[HoldingRecord]
        """
        ...

    def get_realized_pnl(self, from_date: Optional[datetime] = None,
                         to_date: Optional[datetime] = None) -> pd.DataFrame:
        """Tính realized PnL từ SELL entries trong ledger. FIFO matching."""
        ...

    def reconcile(self, broker_holdings: pd.DataFrame) -> dict:
        """
        So sánh holdings tính từ ledger với holdings từ TCBS API.
        Trả về: {"matched": [...], "discrepancies": [...]}
        """
        ...
```

---

## 10. Main Client — `vnbroker/broker/tcbs/client.py`

```python
from typing import Optional
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.security.credentials import TCBSCredentialConfig, resolve_tcbs_credentials
from vnbroker.broker.security.redaction import Redactor
from vnbroker.broker.security.audit import AuditSink
from vnbroker.broker.security.idempotency import IdempotencyStore
from vnbroker.broker.tcbs.auth import TCBSAuthService
from vnbroker.broker.tcbs.account import TCBSAccountService
from vnbroker.broker.tcbs.money import TCBSMoneyService
from vnbroker.broker.tcbs.equity import TCBSEquityService
from vnbroker.broker.tcbs.derivatives import TCBSDerivativesService
from vnbroker.broker.tcbs.portfolio import PortfolioEngine

class TCBSBrokerClient:
    """
    Điểm vào duy nhất của TCBS broker lane.
    Mirrors DNSEClient pattern từ vnbroker/connector/dnse/client.py.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: float = 30.0,
        show_log: bool = False,
    ):
        self._config: TCBSCredentialConfig = resolve_tcbs_credentials(api_key, base_url)
        self._session: BrokerSession = BrokerSession()
        self._audit: AuditSink = AuditSink()
        self._idempotency: IdempotencyStore = IdempotencyStore()
        self._redactor: Redactor = Redactor()

        self._auth = TCBSAuthService(self._config, self._session)
        self._account = TCBSAccountService(self._config, self._session)
        self._money = TCBSMoneyService(self._config, self._session)
        self._equity = TCBSEquityService(
            self._config, self._session, self._audit, self._idempotency
        )
        self._derivatives = TCBSDerivativesService(self._config, self._session)
        self._portfolio = PortfolioEngine()

    # --- Auth ---
    def authenticate(self, otp: str) -> None: ...
    def enable_write(self) -> None: ...
    def revoke(self) -> None: ...

    # --- Account ---
    def list_accounts(self, raw: bool = False): ...
    def get_profile(self, account_no: str, raw: bool = False): ...
    def get_balance(self, account_no: str, raw: bool = False): ...
    def get_purchasing_power(self, account_no: str, raw: bool = False): ...

    # --- Money ---
    def get_cash(self, account_no: str, raw: bool = False): ...
    def get_margin(self, account_no: str, raw: bool = False): ...

    # --- Equity read ---
    def get_orders(self, account_no: str, page: int = 0, size: int = 50, raw: bool = False): ...
    def get_order(self, account_no: str, order_id: str, raw: bool = False): ...
    def get_executions(self, account_no: str, from_date, to_date, raw: bool = False): ...
    def get_order_history(self, account_no: str, from_date, to_date, symbol=None, raw: bool = False): ...

    # --- Equity write (dry_run=True default trong alpha) ---
    def place_order(self, account_no: str, symbol: str, side: str, order_type: str,
                    quantity: int, price: float, pin_code: str,
                    request_id: str, dry_run: bool = True) -> dict: ...
    def update_order(self, account_no: str, order_id: str, quantity: int, price: float,
                     request_id: str, dry_run: bool = True) -> dict: ...
    def cancel_order(self, account_no: str, order_id: str, request_id: str,
                     dry_run: bool = True) -> dict: ...

    # --- Derivatives ---
    def get_derivative_positions(self, account_no: str, raw: bool = False): ...
    def get_derivative_orders(self, account_no: str, raw: bool = False): ...

    # --- Portfolio ---
    def get_portfolio_summary(self, account_no: str, current_prices: dict) -> dict: ...
    def get_realized_pnl(self, account_no: str, from_date=None, to_date=None) -> "pd.DataFrame": ...
    def reconcile_portfolio(self, account_no: str) -> dict: ...
```

---

## 11. Public API Entrypoint — `vnbroker/api/broker.py`

```python
from typing import Optional
from vnbroker.broker.tcbs.client import TCBSBrokerClient

def get_broker(
    provider: str = "tcbs",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    show_log: bool = False,
) -> TCBSBrokerClient:
    """
    Factory function cho broker entrypoint.
    Gọi qua Vnbroker.broker() — xem vnbroker/common/client.py.
    
    Args:
        provider: "tcbs" (hiện tại chỉ hỗ trợ TCBS)
        api_key: API key (tùy chọn — đọc từ env nếu không truyền)
        base_url: Base URL override
        show_log: Không có tác dụng với broker lane (luôn False)
    
    Returns:
        TCBSBrokerClient — chưa authenticated, cần gọi .authenticate(otp=...)
    """
    ...
```

---

## 12. Output Schema Contracts

### 12.1 `list_accounts()` → DataFrame

| Cột | dtype | Ghi chú |
|---|---|---|
| `account_no` | `str` | |
| `custody_code` | `str` | Masked: hiển thị đủ trong raw=True, masked trong raw=False |
| `full_name` | `str` | |
| `account_type` | `category` | "EQUITY" \| "DERIVATIVES" |
| `status` | `category` | "ACTIVE" \| "INACTIVE" |

### 12.2 `get_balance()` → DataFrame

| Cột | dtype | Ghi chú |
|---|---|---|
| `account_no` | `str` | |
| `total_asset` | `float64` | VND |
| `cash_balance` | `float64` | VND |
| `stock_value` | `float64` | VND |
| `debt_balance` | `float64` | VND |
| `available_advance_amount` | `float64` | VND |

### 12.3 `get_orders()` → DataFrame

| Cột | dtype | Ghi chú |
|---|---|---|
| `order_id` | `str` | |
| `symbol` | `str` | |
| `side` | `category` | "BUY" \| "SELL" |
| `order_type` | `category` | "LIMIT" \| "MARKET" \| ... |
| `quantity` | `int64` | |
| `price` | `float64` | VND |
| `filled_quantity` | `int64` | |
| `status` | `category` | "PENDING" \| "FILLED" \| "CANCELLED" \| ... |
| `created_at` | `datetime64[ns, Asia/Ho_Chi_Minh]` | |

### 12.4 `get_derivative_positions()` → DataFrame

| Cột | dtype | Ghi chú |
|---|---|---|
| `symbol` | `str` | VN30F... |
| `side` | `category` | "LONG" \| "SHORT" |
| `open_quantity` | `int64` | |
| `open_price` | `float64` | Điểm |
| `current_price` | `float64` | Điểm |
| `unrealized_pnl` | `float64` | VND |
| `margin` | `float64` | VND |
