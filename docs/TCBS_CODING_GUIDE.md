# TCBS Coding Guide

**Version:** 1.0  
**Cập nhật:** 2026-05-19  
**Đọc trước:** `TCBS_API_CONTRACT.md` → `TCBS_MODULE_STRUCTURE.md` → `TCBS_BROKER_SPEC.md` → *tài liệu này*

---

## 1. Setup môi trường phát triển

```powershell
# Kích hoạt virtual env
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& "c:\Mujoco Projects\brokerplatform\.venv\Scripts\Activate.ps1"

# Set env vars cho phiên làm việc (KHÔNG commit vào .env hay code)
$env:VNBROKER_BROKER_TCBS_API_KEY = "your_api_key_here"

# Kiểm tra đã set chưa
echo $env:VNBROKER_BROKER_TCBS_API_KEY

# Chạy test
python -m pytest tests/unit/broker/tcbs/ -v
```

> **Lưu ý bắt buộc:** Luôn dùng `python -m pytest`, KHÔNG dùng `pytest` bare (PATH issue đã xác nhận trong repo).

---

## 2. Thứ tự implement (bám sát slice S0–S11)

```
S0: Tạo cây thư mục + __init__.py rỗng
S1: exceptions.py
S2: security/credentials.py + security/redaction.py
S3: security/audit.py + security/idempotency.py + security/guards.py
S4: broker/session.py (state machine)
S5: broker/tcbs/auth.py (TCBSAuthService)
S6: broker/tcbs/account.py + broker/tcbs/money.py (read-only)
S7: broker/tcbs/equity.py (read-only)
S8: broker/tcbs/derivatives.py (read-only)
S9: broker/tcbs/equity.py write path (dry_run=True only)
S10: broker/tcbs/portfolio.py (PortfolioEngine)
S11: api/broker.py + common/client.py .broker() entrypoint
```

---

## 3. Bước-bước implement từng thành phần

### Bước 1 — Tạo cấu trúc thư mục (S0)

```powershell
# Chạy từ root repo
New-Item -ItemType Directory -Force -Path "vnbroker/broker/security"
New-Item -ItemType Directory -Force -Path "vnbroker/broker/tcbs"
New-Item -ItemType Directory -Force -Path "tests/unit/broker/tcbs"

# Tạo __init__.py rỗng
@("vnbroker/broker/__init__.py",
  "vnbroker/broker/security/__init__.py",
  "vnbroker/broker/tcbs/__init__.py",
  "tests/unit/broker/__init__.py",
  "tests/unit/broker/tcbs/__init__.py") | ForEach-Object {
    if (-not (Test-Path $_)) { New-Item -ItemType File -Force -Path $_ }
}
```

---

### Bước 2 — Exceptions (S1)

```python
# vnbroker/broker/tcbs/exceptions.py
class BrokerError(Exception):
    def __init__(self, message: str, code: str = "",
                 http_status: int = 0, request_id: str = ""):
        self.message = message
        self.code = code
        self.http_status = http_status
        self.request_id = request_id
        super().__init__(message)

class BrokerAuthError(BrokerError): pass
class BrokerSessionExpiredError(BrokerError): pass
class BrokerPermissionError(BrokerError): pass
class BrokerValidationError(BrokerError): pass
class BrokerRateLimitError(BrokerError): pass
class BrokerOrderError(BrokerError): pass
class BrokerNetworkError(BrokerError): pass
```

**Validation nhanh:**
```python
from vnbroker.broker.tcbs.exceptions import BrokerAuthError
try:
    raise BrokerAuthError("test", code="TEST_401", http_status=401)
except BrokerAuthError as e:
    assert e.code == "TEST_401"
    print("OK")
```

---

### Bước 3 — Credentials + Redaction (S2)

```python
# vnbroker/broker/security/credentials.py
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class TCBSCredentialConfig:
    api_key: str
    base_url: str = "https://openapi.tcbs.com.vn"
    timeout_seconds: float = 30.0
    auth_token: Optional[str] = None

def resolve_tcbs_credentials(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    auth_token: Optional[str] = None,
) -> TCBSCredentialConfig:
    resolved_key = (
        api_key
        or os.getenv("VNBROKER_BROKER_TCBS_API_KEY")
        or os.getenv("vnbroker_TCBS_OPENAPI_API_KEY")
        or os.getenv("TCBS_OPENAPI_API_KEY")
        or os.getenv("TCBS_API_KEY")
    )
    if not resolved_key:
        raise ValueError(
            "TCBS API key không tìm thấy. "
            "Set env var VNBROKER_BROKER_TCBS_API_KEY hoặc truyền api_key."
        )
    resolved_base = (
        base_url
        or os.getenv("VNBROKER_BROKER_TCBS_BASE_URL")
        or os.getenv("TCBS_OPENAPI_BASE_URL")
        or "https://openapi.tcbs.com.vn"
    ).rstrip("/")
    resolved_token = (
        auth_token
        or os.getenv("VNBROKER_BROKER_TCBS_AUTH_TOKEN")
        or os.getenv("TCBS_AUTH_TOKEN")
    )
    return TCBSCredentialConfig(
        api_key=resolved_key,
        base_url=resolved_base,
        auth_token=resolved_token,
    )
```

```python
# vnbroker/broker/security/redaction.py
from typing import Any

SENSITIVE_KEYS: frozenset = frozenset({
    "apikey", "api_key", "otp", "pincode", "pin_code",
    "authorization", "token", "password", "secret",
    "accountno", "account_no", "custodycode", "custody_code",
    "idno", "id_no", "phone", "email",
})

class Redactor:
    REDACTED = "***REDACTED***"

    @staticmethod
    def redact_dict(data: dict, keys: frozenset = SENSITIVE_KEYS) -> dict:
        result = {}
        for k, v in data.items():
            if k.lower().replace("-", "_") in keys:
                result[k] = Redactor.REDACTED
            elif isinstance(v, dict):
                result[k] = Redactor.redact_dict(v, keys)
            else:
                result[k] = v
        return result

    @staticmethod
    def redact_headers(headers: dict) -> dict:
        return {
            k: (Redactor.REDACTED if k.lower() == "authorization" else v)
            for k, v in headers.items()
        }
```

---

### Bước 4 — BrokerSession state machine (S4)

```python
# vnbroker/broker/session.py
from enum import Enum, auto
from datetime import datetime, timezone
from typing import Optional
from vnbroker.broker.tcbs.exceptions import BrokerSessionExpiredError, BrokerPermissionError

class SessionState(Enum):
    CREATED = auto()
    AUTHENTICATING = auto()
    AUTHENTICATED_READ = auto()
    AUTHENTICATED_WRITE_ENABLED = auto()
    EXPIRED = auto()
    LOCKED = auto()

class BrokerSession:
    def __init__(self):
        self.state = SessionState.CREATED
        self._token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    @property
    def token(self) -> Optional[str]:
        if self.state in (SessionState.EXPIRED, SessionState.LOCKED):
            raise BrokerSessionExpiredError(
                "Session đã hết hạn hoặc bị khoá.",
                code="SESSION_EXPIRED"
            )
        if self._token_expires_at and datetime.now(timezone.utc) > self._token_expires_at:
            self.revoke()
            raise BrokerSessionExpiredError(
                "Token hết hạn. Gọi .authenticate() lại.",
                code="TOKEN_EXPIRED"
            )
        return self._token

    @property
    def is_write_enabled(self) -> bool:
        return self.state == SessionState.AUTHENTICATED_WRITE_ENABLED

    def set_token(self, token: str, expires_at: Optional[datetime] = None) -> None:
        self._token = token
        self._token_expires_at = expires_at
        self.state = SessionState.AUTHENTICATED_READ

    def enable_write(self) -> None:
        if self.state != SessionState.AUTHENTICATED_READ:
            raise BrokerPermissionError(
                "Phải authenticate thành công trước khi enable write.",
                code="WRITE_NOT_PERMITTED"
            )
        self.state = SessionState.AUTHENTICATED_WRITE_ENABLED

    def revoke(self) -> None:
        self._token = None
        self._token_expires_at = None
        self.state = SessionState.EXPIRED

    def lock(self, reason: str) -> None:
        self._token = None
        self.state = SessionState.LOCKED
```

---

### Bước 5 — TCBSAuthService (S5)

```python
# vnbroker/broker/tcbs/auth.py
import requests
from typing import Optional
from datetime import datetime, timezone, timedelta
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.security.credentials import TCBSCredentialConfig
from vnbroker.broker.tcbs.exceptions import BrokerAuthError, BrokerNetworkError
from vnbroker.core.utils.logger import get_logger

logger = get_logger(__name__)

class TCBSAuthService:
    def __init__(self, config: TCBSCredentialConfig, session: BrokerSession):
        self._config = config
        self._session = session

    def authenticate(self, otp: str) -> None:
        if not otp or not otp.strip():
            raise ValueError("OTP không được rỗng.")
        
        url = f"{self._config.base_url}/gaia/v1/oauth2/openapi/token"
        # KHÔNG log apiKey hoặc otp
        logger.debug("[TCBS Auth] POST token exchange initiated.")
        
        try:
            resp = requests.post(
                url,
                json={"apiKey": self._config.api_key, "otp": otp},
                headers={"Content-Type": "application/json"},
                timeout=self._config.timeout_seconds,
            )
        except requests.RequestException as e:
            raise BrokerNetworkError(f"Lỗi kết nối TCBS: {e}", code="NETWORK_ERROR") from e

        data = resp.json()
        
        if resp.status_code != 200 or not data.get("token"):
            raise BrokerAuthError(
                data.get("message", "Token exchange thất bại."),
                code=data.get("code", "AUTH_FAILED"),
                http_status=resp.status_code,
            )
        
        # Parse expiry (~**24 giờ** (đo được 2026-10-10 từ JWT thật: `exp - iat = 86400s`) mặc định nếu không có)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=8)
        self._session.set_token(data["token"], expires_at=expires_at)
        logger.debug("[TCBS Auth] Token acquired. Session → AUTHENTICATED_READ.")

    def is_token_valid(self) -> bool:
        try:
            return bool(self._session.token)
        except Exception:
            return False

    def revoke(self) -> None:
        self._session.revoke()
```

---

### Bước 6 — Pattern chuẩn cho Read Service (S6–S8)

Dùng mẫu sau cho tất cả các service read-only:

```python
# Ví dụ: vnbroker/broker/tcbs/account.py
import requests
import pandas as pd
from typing import Union
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.security.credentials import TCBSCredentialConfig
from vnbroker.broker.tcbs.exceptions import (
    BrokerAuthError, BrokerNetworkError, BrokerValidationError
)
from vnbroker.core.utils.logger import get_logger

logger = get_logger(__name__)

class TCBSAccountService:
    def __init__(self, config: TCBSCredentialConfig, session: BrokerSession):
        self._config = config
        self._session = session

    def _headers(self) -> dict:
        """Xây header với JWT. Raise nếu session chưa authenticated."""
        token = self._session.token  # Sẽ raise BrokerSessionExpiredError nếu hết hạn
        if not token:
            raise BrokerAuthError("Session chưa được authenticate.", code="NOT_AUTHENTICATED")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: dict = None) -> dict:
        """Wrapper HTTP GET với error mapping."""
        url = f"{self._config.base_url}{path}"
        logger.debug(f"[TCBS] GET {path}")
        try:
            resp = requests.get(url, headers=self._headers(), params=params,
                                timeout=self._config.timeout_seconds)
        except requests.RequestException as e:
            raise BrokerNetworkError(f"Lỗi kết nối: {e}", code="NETWORK_ERROR") from e
        
        self._raise_for_status(resp)
        return resp.json()

    def _raise_for_status(self, resp) -> None:
        """Map HTTP status codes sang BrokerError hierarchy."""
        from vnbroker.broker.tcbs.exceptions import (
            BrokerSessionExpiredError, BrokerPermissionError,
            BrokerRateLimitError, BrokerOrderError
        )
        if resp.status_code == 200:
            return
        data = {}
        try:
            data = resp.json()
        except Exception:
            pass
        code = data.get("code", "")
        msg = data.get("message", resp.reason or "Lỗi không xác định")
        if resp.status_code == 401:
            if code == "SESSION_EXPIRED":
                raise BrokerSessionExpiredError(msg, code=code, http_status=401)
            raise BrokerAuthError(msg, code=code, http_status=401)
        if resp.status_code == 403:
            raise BrokerPermissionError(msg, code=code, http_status=403)
        if resp.status_code == 400:
            raise BrokerValidationError(msg, code=code, http_status=400)
        if resp.status_code == 429:
            raise BrokerRateLimitError(msg, code=code, http_status=429)
        if resp.status_code == 422:
            raise BrokerOrderError(msg, code=code, http_status=422)
        raise BrokerNetworkError(msg, code=code, http_status=resp.status_code)

    def get_balance(self, account_no: str, raw: bool = False) -> Union[pd.DataFrame, dict]:
        data = self._get(f"/gaia/v1/openapi/account/{account_no}/balance")
        if raw:
            return data
        df = pd.json_normalize(data if isinstance(data, list) else [data])
        # Rename camelCase → snake_case
        df.columns = [self._to_snake(c) for c in df.columns]
        return df

    @staticmethod
    def _to_snake(name: str) -> str:
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
```

---

### Bước 7 — Pattern chuẩn cho Write Service (S9)

```python
# Trong TCBSEquityService.place_order()
import uuid
from vnbroker.broker.security.redaction import Redactor
from vnbroker.broker.security.audit import AuditSink, AuditRecord
from vnbroker.broker.security.idempotency import IdempotencyStore

def place_order(self, account_no: str, symbol: str, side: str,
                order_type: str, quantity: int, price: float,
                pin_code: str, request_id: str,
                dry_run: bool = True) -> dict:
    # 1. Validate inputs
    if quantity <= 0:
        raise BrokerValidationError("quantity phải > 0", code="INVALID_QUANTITY")
    if price < 0:
        raise BrokerValidationError("price không được âm", code="INVALID_PRICE")
    if not request_id:
        request_id = str(uuid.uuid4())

    # 2. Idempotency check
    if not self._idempotency.check_and_store(request_id):
        raise BrokerValidationError(
            f"Duplicate request_id: {request_id}", code="DUPLICATE_REQUEST"
        )

    # 3. Write gate check
    if not self._session.is_write_enabled:
        raise BrokerPermissionError(
            "Write chưa được enable. Gọi client.enable_write() trước.",
            code="WRITE_NOT_ENABLED"
        )

    url = f"{self._config.base_url}/gaia/v1/openapi/account/{account_no}/orders"
    payload = {
        "symbol": symbol, "side": side, "orderType": order_type,
        "quantity": quantity, "price": price,
        "pinCode": pin_code, "requestId": request_id,
    }

    # 4. dry_run — trả về debug object KHÔNG gọi HTTP
    if dry_run:
        return {
            "dry_run": True,
            "method": "POST",
            "url": url,
            "headers": Redactor.redact_headers(self._headers()),
            "payload": Redactor.redact_dict(payload),
        }

    # 5. Thực hiện gọi HTTP (chỉ khi dry_run=False)
    try:
        resp = requests.post(url, json=payload, headers=self._headers(),
                             timeout=self._config.timeout_seconds)
    except requests.RequestException as e:
        raise BrokerNetworkError(f"Lỗi kết nối: {e}", code="NETWORK_ERROR") from e
    finally:
        # 6. Audit log — luôn ghi kể cả khi lỗi (KHÔNG log pin_code)
        self._audit.record(AuditRecord(
            timestamp=datetime.now(timezone.utc),
            operation="place_order",
            account_no=account_no[-4:],  # mask
            request_id=request_id,
            dry_run=dry_run,
            success=(resp.status_code == 201 if 'resp' in dir() else False),
        ))

    self._raise_for_status(resp)
    return resp.json()
```

---

## 4. Checklist trước khi commit

Chạy toàn bộ checklist này trước mỗi commit liên quan đến broker lane:

```powershell
# 1. Kiểm tra không có print() trong broker lane
Select-String -Path "vnbroker/broker/**/*.py" -Pattern "^\s*print\(" -Recurse
# Kỳ vọng: không có kết quả

# 2. Kiểm tra không log apiKey/otp/pin_code trực tiếp
Select-String -Path "vnbroker/broker/**/*.py" -Pattern "logger\.(info|debug|warning|error).*?(apiKey|otp|pin_code|pinCode|password)" -Recurse
# Kỳ vọng: không có kết quả

# 3. Chạy unit tests
python -m pytest tests/unit/broker/tcbs/ -v --tb=short
# Kỳ vọng: tất cả PASS

# 4. Kiểm tra trailing whitespace
git diff --check
# Kỳ vọng: không có output

# 5. Import smoke test
python -c "from vnbroker.broker.tcbs.client import TCBSBrokerClient; print('Import OK')"
```

---

## 5. Pitfalls thường gặp

### ❌ Pitfall 1: Dùng core/utils/client.py cho write path

```python
# SAI — show_log=True mặc định log payload thô
from vnbroker.core.utils import client
client.send_request(url=url, payload=payload, show_log=True)  # BUG: log pin_code!
```

```python
# ĐÚNG — dùng requests trực tiếp với redaction
import requests
resp = requests.post(url, json=payload, headers=headers)
# Chỉ log sau khi đã redact
```

---

### ❌ Pitfall 2: Import explorer auth vào broker

```python
# SAI
from vnbroker.explorer.tcbs.auth import request_openapi_token  # Sai layer!
```

```python
# ĐÚNG
from vnbroker.broker.tcbs.auth import TCBSAuthService
```

---

### ❌ Pitfall 3: Gọi write mà không set dry_run=False rõ ràng

```python
# Có thể gây confusion — đọc như dry_run=False nhưng thực ra là False ngầm định
client.place_order(account_no=..., ..., dry_run=False)  # OK nếu cố ý
```

Quy ước repo: **Khi chưa có sign-off production, giữ default `dry_run=True` trong tất cả code test và example.**

---

### ❌ Pitfall 4: Không kiểm tra IdempotencyStore trước write

```python
# SAI — gửi lệnh trùng lặp
resp = requests.post(url, json=payload)  # Không check idempotency

# ĐÚNG
if not self._idempotency.check_and_store(request_id):
    raise BrokerValidationError("Duplicate request_id", code="DUPLICATE_REQUEST")
resp = requests.post(url, json=payload)
```

---

### ❌ Pitfall 5: Không handle BrokerSessionExpiredError trong integration

```python
# SAI — sẽ crash khi token hết hạn sau **24 giờ** (đo được 2026-10-10 từ JWT thật: `exp - iat = 86400s`)
balance = client.get_balance(account_no)

# ĐÚNG
try:
    balance = client.get_balance(account_no)
except BrokerSessionExpiredError:
    client.authenticate(otp=input("Nhập OTP: "))
    balance = client.get_balance(account_no)
```

---

## 6. Ví dụ sử dụng hoàn chỉnh

```python
from vnbroker.broker.tcbs.client import TCBSBrokerClient
from vnbroker.broker.tcbs.exceptions import BrokerAuthError, BrokerSessionExpiredError

# 1. Khởi tạo (api_key đọc từ env VNBROKER_BROKER_TCBS_API_KEY)
client = TCBSBrokerClient()

# 2. Authenticate (can OTP - chi hoi nguoi dung 1 lan / 24 gio)
try:
    client.authenticate(otp="123456")
except BrokerAuthError as e:
    print(f"Auth thất bại: {e.message} [{e.code}]")
    raise

# 3. Đọc danh sách tài khoản
accounts = client.list_accounts()
print(accounts)

account_no = accounts["account_no"].iloc[0]

# 4. Đọc số dư
balance = client.get_balance(account_no=account_no)
print(balance)

# 5. Đặt lệnh (dry_run=True — kiểm tra payload trước khi thật)
import uuid
debug = client.place_order(
    account_no=account_no,
    symbol="VNM",
    side="BUY",
    order_type="LIMIT",
    quantity=100,
    price=80000,
    pin_code="123456",
    request_id=str(uuid.uuid4()),
    dry_run=True,   # Bắt buộc True cho đến khi có production sign-off
)
print(debug)  # Hiển thị payload đã redact — không có pin_code thật

# 6. Revoke session khi xong
client.revoke()
```
