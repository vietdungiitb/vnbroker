# TCBS Module Structure

**Version:** 1.0  
**Cập nhật:** 2026-05-19  
**Phạm vi:** Layout file chính xác cho `vnbroker/broker/` và test tương ứng.

---

## 1. Mục đích

Tài liệu này định nghĩa **cấu trúc thư mục và file** bắt buộc cho broker lane TCBS. Đội code dùng tài liệu này làm bản vẽ — không được tạo file ngoài cấu trúc dưới đây mà không cập nhật tài liệu này trước.

---

## 2. Cây thư mục

```
vnbroker/
├── broker/
│   ├── __init__.py                  # Export TCBSBrokerClient, BrokerRegistry, BrokerSession
│   ├── base.py                      # BaseBrokerClient (ABC) — interface contract
│   ├── registry.py                  # BrokerRegistry singleton — lookup broker by name
│   ├── session.py                   # BrokerSession — state machine + token lifecycle
│   │
│   ├── security/
│   │   ├── __init__.py              # Export Redactor, AuditSink, IdempotencyStore, write_gate
│   │   ├── credentials.py           # TCBSCredentialConfig, resolve_tcbs_credentials()
│   │   ├── redaction.py             # Redactor class, redact_dict(), SENSITIVE_KEYS
│   │   ├── audit.py                 # AuditSink, AuditRecord dataclass
│   │   ├── idempotency.py           # IdempotencyStore (in-memory, TTL-based)
│   │   └── guards.py                # write_gate() decorator, dry_run_check()
│   │
│   └── tcbs/
│       ├── __init__.py              # Export TCBSBrokerClient
│       ├── client.py                # TCBSBrokerClient — điểm vào duy nhất của broker lane
│       ├── auth.py                  # TCBSAuthService — token exchange, refresh, revoke
│       ├── account.py               # TCBSAccountService — list, profile, balance, purchasing power
│       ├── money.py                 # TCBSMoneyService — cash, margin
│       ├── equity.py                # TCBSEquityService — orders, executions, history
│       ├── derivatives.py           # TCBSDerivativesService — positions, orders
│       ├── portfolio.py             # PortfolioEngine — holdings, cost basis, PnL, ledger
│       └── exceptions.py           # BrokerError hierarchy: Auth/Permission/Validation/Order/...
│
├── api/
│   ├── broker.py                    # Public Vnbroker.broker() entrypoint
│   └── ...                          # (các api/*.py hiện có không đổi)
│
└── common/
    └── client.py                    # Vnbroker — thêm .broker() method (S10)

tests/
└── unit/
    └── broker/
        └── tcbs/
            ├── __init__.py
            ├── fixtures.py               # SAMPLE_* dicts, make_mock_*() helpers
            ├── test_credentials.py       # Unit test TCBSCredentialConfig, resolve_tcbs_credentials
            ├── test_security.py          # Unit test Redactor, AuditSink, IdempotencyStore, guards
            ├── test_session_auth.py      # Unit test BrokerSession state machine + TCBSAuthService
            ├── test_account_money.py     # Unit test TCBSAccountService + TCBSMoneyService
            ├── test_orders_positions.py  # Unit test TCBSEquityService + TCBSDerivativesService (read)
            ├── test_order_write_flow.py  # Unit test write flow: dry_run gate, idempotency, audit sink
            └── test_portfolio.py         # Unit test PortfolioEngine
```

---

## 3. Quy tắc trách nhiệm

### 3.1 Phân chia layer

| Layer | Trách nhiệm | Cấm làm |
|---|---|---|
| `vnbroker/broker/security/` | Credential resolution, token redaction, audit logging, write gate | Gọi TCBS HTTP trực tiếp |
| `vnbroker/broker/tcbs/auth.py` | Token exchange OTP→JWT, token lifecycle | Đọc env var trực tiếp (dùng `credentials.py`) |
| `vnbroker/broker/tcbs/client.py` | Orchestrate services, public facade | Chứa business logic của từng domain |
| `vnbroker/broker/tcbs/*.py` (services) | Gọi TCBS HTTP, map response → DataFrame/dict | Import từ `vnbroker/core/utils/client.py` cho write path |
| `vnbroker/broker/base.py` | Interface contract chỉ | Implement bất kỳ logic nào |
| `vnbroker/api/broker.py` | Entrypoint public, trả về TCBSBrokerClient | Leak session/token ra ngoài |

### 3.2 HTTP Client dùng cho Broker Lane

Broker lane **KHÔNG** dùng `vnbroker/core/utils/client.py` trực tiếp cho các path nhạy cảm vì module này log payload thô. Thay vào đó:

```python
# Trong mọi service broker — dùng requests trực tiếp với header đã built sẵn
import requests
from vnbroker.broker.security.redaction import Redactor

response = requests.post(url, json=payload, headers=headers, timeout=30)
# Log chỉ qua AuditSink với payload đã redact
```

Exception: Các GET read-only (không chứa secret trong payload/params) có thể dùng `core/utils/client.py` với `show_log=False`.

---

## 4. Naming Conventions

| Loại | Quy ước | Ví dụ |
|---|---|---|
| Class | PascalCase | `TCBSBrokerClient`, `BrokerSession` |
| Method public | snake_case | `get_balance()`, `place_order()` |
| Method private | `_` prefix | `_build_headers()`, `_resolve_token()` |
| Constant | UPPER_SNAKE | `SENSITIVE_KEYS`, `SESSION_TIMEOUT_SECONDS` |
| Enum | PascalCase class, UPPER_SNAKE member | `SessionState.AUTHENTICATED_READ` |
| Test class | `Test` + CamelCase | `TestBrokerSessionTransition` |
| Test method | `test_` + snake_case | `test_authenticate_sets_token_on_success` |
| Fixtures file | `SAMPLE_` prefix cho dict, `make_` prefix cho factory | `SAMPLE_BALANCE`, `make_mock_client()` |

---

## 5. Output Modes

Mọi method trả về dữ liệu từ TCBS phải hỗ trợ `raw: bool = False`:

| `raw` | Kiểu trả về |
|---|---|
| `False` (default) | `pd.DataFrame` — đã normalize, đúng dtype |
| `True` | `dict` hoặc `list` — JSON response gốc từ TCBS |

Write methods (place/update/cancel) trả về `dict` bất kể `raw`.

---

## 6. Logging Rules

| Tình huống | Được làm |
|---|---|
| Log request URL + method | `logger.debug(f"[TCBS] {method} {url}")` |
| Log response status code | `logger.debug(f"[TCBS] Response: {status_code}")` |
| Log error message (KHÔNG chứa secret) | `logger.error(f"[TCBS] {error.code}: {error.message}")` |
| Log audit event | Qua `AuditSink.record()` — không qua `logger` |

| Tình huống | **TUYỆT ĐỐI CẤM** |
|---|---|
| Log apiKey, otp, pinCode, authorization token | Dù ở debug level |
| Log accountNo, custodyCode, idNo, phone, email | Trừ khi đã redact |
| Log payload gốc của write request | Luôn redact trước khi log |
| `print()` bất kỳ thứ gì trong broker lane | Không ngoại lệ |

---

## 7. Quan hệ với Explorer Layer

```
vnbroker/
├── explorer/tcbs/          ← Provider lane (Quote, Finance, Trading, Company, Listing)
│   └── auth.py             ← Legacy auth helper — GIỮ NGUYÊN, thêm DeprecationWarning từ S10
└── broker/tcbs/            ← Broker lane (Auth, Account, Money, Equity, Derivatives, Portfolio)
    └── auth.py             ← Broker auth — TÁCH HOÀN TOÀN, không import từ explorer
```

Hai layer này được phép dùng chung:
- `vnbroker/core/utils/logger.py` (nhưng broker KHÔNG log payload nhạy cảm qua nó)
- `vnbroker/core/utils/validation.py`
- `vnbroker/core/utils/transform.py`

Hai layer này **KHÔNG** được import lẫn nhau về auth/session/credential logic.
