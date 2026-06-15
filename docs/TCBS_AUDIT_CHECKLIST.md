# TCBS Audit Checklist

**Version:** 1.0  
**Cập nhật:** 2026-05-19  
**Phạm vi:** Audit toàn bộ broker lane TCBS trước khi merge vào nhánh `main`.

---

## Hướng dẫn sử dụng

1. Chạy từng lệnh kiểm tra trong terminal PowerShell từ root repo.
2. Điền kết quả thực tế vào cột **Kết quả thực tế**.
3. Đính kèm screenshot/output vào cột **Bằng chứng**.
4. Mỗi hạng mục phải có trạng thái: ✅ PASS | ❌ FAIL | ⏭ SKIP (ghi lý do).
5. Không được merge khi còn bất kỳ ❌ FAIL nào.

---

## Phần A — Cấu trúc file (File Structure)

**Mục tiêu:** Xác nhận tất cả file được tạo đúng theo `TCBS_MODULE_STRUCTURE.md`.

```powershell
# Kiểm tra toàn bộ cây thư mục broker
Get-ChildItem -Recurse -Path "vnbroker/broker" | Select-Object FullName
Get-ChildItem -Recurse -Path "tests/unit/broker/tcbs" | Select-Object FullName
```

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| A1 | `vnbroker/broker/__init__.py` tồn tại | `Test-Path "vnbroker/broker/__init__.py"` | `True` | | |
| A2 | `vnbroker/broker/base.py` tồn tại | `Test-Path "vnbroker/broker/base.py"` | `True` | | |
| A3 | `vnbroker/broker/registry.py` tồn tại | `Test-Path "vnbroker/broker/registry.py"` | `True` | | |
| A4 | `vnbroker/broker/session.py` tồn tại | `Test-Path "vnbroker/broker/session.py"` | `True` | | |
| A5 | `vnbroker/broker/security/` đủ 5 file | `Get-ChildItem "vnbroker/broker/security/*.py" \| Measure-Object` | Count = 6 (incl. __init__) | | |
| A6 | `vnbroker/broker/tcbs/` đủ 8 file | `Get-ChildItem "vnbroker/broker/tcbs/*.py" \| Measure-Object` | Count = 8 | | |
| A7 | `vnbroker/api/broker.py` tồn tại | `Test-Path "vnbroker/api/broker.py"` | `True` | | |
| A8 | `tests/unit/broker/tcbs/` đủ 8 file test | `Get-ChildItem "tests/unit/broker/tcbs/*.py" \| Measure-Object` | Count = 9 (incl. __init__) | | |

---

## Phần B — Import và Registry

**Mục tiêu:** Xác nhận import chain không bị lỗi và không có circular import.

```powershell
python -c "from vnbroker.broker.tcbs.client import TCBSBrokerClient; print('OK')"
python -c "from vnbroker.broker.security.redaction import Redactor; print('OK')"
python -c "from vnbroker.broker.security.credentials import resolve_tcbs_credentials; print('OK')"
python -c "from vnbroker.broker.session import BrokerSession, SessionState; print('OK')"
python -c "from vnbroker.broker.tcbs.exceptions import BrokerAuthError; print('OK')"
python -c "from vnbroker.api.broker import get_broker; print('OK')"
```

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| B1 | Import TCBSBrokerClient thành công | `python -c "from vnbroker.broker.tcbs.client import TCBSBrokerClient; print('OK')"` | `OK` | | |
| B2 | Import Redactor thành công | `python -c "from vnbroker.broker.security.redaction import Redactor; print('OK')"` | `OK` | | |
| B3 | Import BrokerSession thành công | `python -c "from vnbroker.broker.session import BrokerSession; print('OK')"` | `OK` | | |
| B4 | Import exception hierarchy thành công | `python -c "from vnbroker.broker.tcbs.exceptions import BrokerAuthError, BrokerOrderError; print('OK')"` | `OK` | | |
| B5 | Không có circular import | `python -c "import vnbroker.broker; print('no circular')"` | `no circular` | | |
| B6 | Broker layer không import từ explorer auth | `Select-String -Path "vnbroker/broker/**/*.py" -Pattern "from vnbroker.explorer.tcbs.auth" -Recurse` | Không có kết quả | | |

---

## Phần C — Credentials và Env Vars

**Mục tiêu:** Xác nhận credential resolution đúng thứ tự ưu tiên và không rò rỉ key.

```powershell
# Test primary env var
$env:VNBROKER_BROKER_TCBS_API_KEY = "test_primary"
python -c "
from vnbroker.broker.security.credentials import resolve_tcbs_credentials
cfg = resolve_tcbs_credentials()
print('OK' if cfg.api_key == 'test_primary' else 'FAIL: ' + cfg.api_key)
"

# Test ValueError khi không có key
Remove-Item Env:VNBROKER_BROKER_TCBS_API_KEY -ErrorAction SilentlyContinue
python -c "
from vnbroker.broker.security.credentials import resolve_tcbs_credentials
try:
    resolve_tcbs_credentials()
    print('FAIL: Should raise ValueError')
except ValueError:
    print('OK: ValueError raised')
"
```

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| C1 | Primary env var `VNBROKER_BROKER_TCBS_API_KEY` được đọc | Xem trên | `OK` | | |
| C2 | ValueError khi không có env var nào | Xem trên | `OK: ValueError raised` | | |
| C3 | Legacy `TCBS_OPENAPI_API_KEY` được fallback | Test tương tự với legacy key | `OK` | | |
| C4 | Tham số trực tiếp `api_key` override env var | `resolve_tcbs_credentials(api_key="direct")` | `cfg.api_key == "direct"` | | |
| C5 | `auth_token` env var `VNBROKER_BROKER_TCBS_AUTH_TOKEN` được đọc | Test với env var | Token inject đúng | | |

---

## Phần D — Session State Machine

**Mục tiêu:** Xác nhận tất cả state transitions đúng spec.

```powershell
python -c "
from vnbroker.broker.session import BrokerSession, SessionState
s = BrokerSession()
assert s.state == SessionState.CREATED, f'Expected CREATED, got {s.state}'
s.set_token('fake')
assert s.state == SessionState.AUTHENTICATED_READ, f'Expected READ, got {s.state}'
s.enable_write()
assert s.state == SessionState.AUTHENTICATED_WRITE_ENABLED, f'Expected WRITE, got {s.state}'
s.revoke()
assert s.state == SessionState.EXPIRED, f'Expected EXPIRED, got {s.state}'
print('All state transitions OK')
"
```

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| D1 | State machine: CREATED → READ | Xem trên | `All state transitions OK` | | |
| D2 | State machine: READ → WRITE_ENABLED | Xem trên | Included | | |
| D3 | State machine: * → EXPIRED (revoke) | Xem trên | Included | | |
| D4 | `token` property raise khi EXPIRED | `s.revoke(); _ = s.token` | `BrokerSessionExpiredError` | | |
| D5 | `enable_write()` raise khi chưa authenticated | `BrokerSession().enable_write()` | `BrokerPermissionError` | | |
| D6 | `lock()` chuyển state → LOCKED | `s.lock("test"); s.state == LOCKED` | `True` | | |

---

## Phần E — Redaction và Security

**Mục tiêu:** Xác nhận không có secret nào lọt qua trong log hoặc dry_run output.

```powershell
# Test Redactor
python -c "
from vnbroker.broker.security.redaction import Redactor
data = {'apiKey': 'SECRET', 'otp': '123456', 'pinCode': 'SECRET_PIN', 'symbol': 'VNM'}
result = Redactor.redact_dict(data)
secrets = [v for v in result.values() if v in ('SECRET', '123456', 'SECRET_PIN')]
print('FAIL: secret not redacted' if secrets else 'Redaction OK')
"

# Kiểm tra không có print() trong broker lane
Select-String -Path "vnbroker/broker" -Pattern "^\s*print\(" -Recurse
```

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| E1 | Redactor xoá `apiKey` | Xem trên | `Redaction OK` | | |
| E2 | Redactor xoá `otp` | Xem trên | Included | | |
| E3 | Redactor xoá `pinCode` variants | Xem trên | Included | | |
| E4 | Redactor xoá `Authorization` header | `Redactor.redact_headers({"Authorization": "Bearer jwt"})` | `***REDACTED***` | | |
| E5 | Không có `print()` trong broker lane | `Select-String` trên | Không có kết quả | | |
| E6 | Không có hardcode secret trong broker code | `Select-String -Path "vnbroker/broker/**/*.py" -Pattern "(apiKey|otp|password)\s*=\s*['\"][^'\"]{4}"` | Không có kết quả | | |
| E7 | dry_run output không chứa real pin_code | Xem test_order_write_flow.py | `REAL_SECRET` không có trong output | | |
| E8 | AuditSink ghi operation mà không log secret | Code review + chạy test | AuditRecord không có trường secret | | |

---

## Phần F — Account và Money (Read-side)

**Mục tiêu:** Xác nhận read services trả đúng dtype và xử lý lỗi đúng.

```powershell
python -m pytest tests/unit/broker/tcbs/test_account_money.py -v --tb=short
```

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| F1 | `get_balance()` trả DataFrame | test_returns_dataframe_by_default | PASS | | |
| F2 | `get_balance(raw=True)` trả dict | test_raw_true_returns_dict | PASS | | |
| F3 | Columns là snake_case | test_column_names_snake_case | PASS | | |
| F4 | Raise khi session chưa auth | test_raises_when_session_unauthenticated | PASS | | |
| F5 | `get_cash()` trả DataFrame hợp lệ | Unit test tương tự | PASS | | |

---

## Phần G — Equity Orders (Read-side)

```powershell
python -m pytest tests/unit/broker/tcbs/test_orders_positions.py -v --tb=short
```

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| G1 | `get_orders()` trả DataFrame | Unit test | PASS | | |
| G2 | `get_orders(raw=True)` trả dict | Unit test | PASS | | |
| G3 | `get_executions()` column dtypes đúng spec | Kiểm tra dtype `executed_at` | `datetime64[ns, ...]` | | |
| G4 | `get_order_history()` hỗ trợ `symbol` filter | Unit test với symbol param | Lọc đúng | | |
| G5 | Derivative positions trả DataFrame | Unit test TCBSDerivativesService | PASS | | |

---

## Phần H — Write Flow (dry_run + Idempotency + Audit)

```powershell
python -m pytest tests/unit/broker/tcbs/test_order_write_flow.py -v --tb=short
```

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| H1 | `place_order(dry_run=True)` không gọi HTTP | test_dry_run_returns_debug_dict_without_http_call | PASS (mock_post.assert_not_called) | | |
| H2 | dry_run output redact pin_code | test_dry_run_redacts_pin_code | PASS | | |
| H3 | dry_run output redact Authorization | test_dry_run_redacts_authorization_header | PASS | | |
| H4 | quantity âm raise BrokerValidationError | test_raises_on_negative_quantity | PASS | | |
| H5 | Write khi chưa enable_write raise BrokerPermissionError | test_raises_when_write_not_enabled | PASS | | |
| H6 | Duplicate request_id raise BrokerValidationError | test_duplicate_request_id_raises | PASS | | |
| H7 | Idempotency TTL expiry cho phép reuse | TestIdempotencyStore.test_expired_key_allows_reuse | PASS | | |
| H8 | AuditSink được gọi sau mỗi write attempt | Verify audit.record() được call | PASS | | |

---

## Phần I — Portfolio Engine

```powershell
python -m pytest tests/unit/broker/tcbs/test_portfolio.py -v --tb=short
```

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| I1 | BUY tạo holding | test_single_buy_creates_holding | PASS | | |
| I2 | BUY + partial SELL giảm quantity đúng | test_buy_then_sell_reduces_quantity | PASS | | |
| I3 | Full SELL xoá holding | test_full_sell_removes_holding | PASS | | |
| I4 | Unrealized PnL > 0 khi giá lên | test_unrealized_pnl_calculation | PASS | | |
| I5 | Reconcile khớp khi ledger và broker nhất quán | test_reconcile_matches_when_consistent | PASS | | |
| I6 | Reconcile phát hiện discrepancy | test_reconcile_detects_discrepancy | PASS | | |

---

## Phần J — TCBS Provider Parity (Public Explorer Lane)

**Mục tiêu:** Xác nhận public provider (Quote, Finance, Trading) không bị ảnh hưởng bởi broker lane.

```powershell
python -c "
from vnbroker import Vnbroker
v = Vnbroker(source='TCBS')
print('Vnbroker TCBS provider init OK')
"

# Kiểm tra listing fallback vẫn hoạt động
python -c "
from vnbroker.common.data import StockComponents
sc = StockComponents(source='TCBS')
print('StockComponents TCBS OK, listing source:', type(sc.listing).__name__)
"
```

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| J1 | `Vnbroker(source='TCBS')` init thành công | Xem trên | `OK` | | |
| J2 | Quote.history vẫn hoạt động | `Vnbroker(source='TCBS').stock('VNM').quote.history(...)` | DataFrame | | |
| J3 | Finance.balance_sheet vẫn hoạt động | `Vnbroker(source='TCBS').stock('VNM').finance.balance_sheet()` | DataFrame | | |
| J4 | Trading.price_board vẫn hoạt động | `Vnbroker(source='TCBS').stock('VNM').trading.price_board(...)` | DataFrame | | |
| J5 | Listing fallback vẫn là KBS | Xem trên — StockComponents | source = KBS | | |

---

## Phần K — Backward Compatibility

**Mục tiêu:** Xác nhận code cũ dùng explorer auth không bị vỡ.

```powershell
# Explorer auth vẫn import được
python -c "
from vnbroker.explorer.tcbs.auth import request_openapi_token, get_tcbs_headers
print('Legacy import OK')
"

# Vnbroker.stock() vẫn hoạt động như trước (không dùng otp)
python -c "
from vnbroker import Vnbroker
v = Vnbroker()
print('Vnbroker() default init OK')
"
```

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| K1 | `vnbroker.explorer.tcbs.auth` vẫn import được | Xem trên | `Legacy import OK` | | |
| K2 | `Vnbroker()` default init không lỗi | Xem trên | `OK` | | |
| K3 | DeprecationWarning xuất hiện khi dùng explorer auth cho broker flow | Kiểm tra S10 | `DeprecationWarning` emitted | | |
| K4 | `Vnbroker.broker()` trả về TCBSBrokerClient | `type(Vnbroker().broker()) == TCBSBrokerClient` | `True` | | |

---

## Phần L — Unit Tests Coverage

```powershell
python -m pytest tests/unit/broker/tcbs/ -v --tb=short
python -m pytest tests/unit/broker/tcbs/ --cov=vnbroker/broker --cov-report=term-missing
```

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| L1 | Tất cả unit tests PASS | `python -m pytest tests/unit/broker/tcbs/ -v` | 0 FAIL | | |
| L2 | `exceptions.py` coverage ≥ 100% | `--cov-report=term-missing` | ≥ 100% | | |
| L3 | `session.py` coverage ≥ 95% | Xem trên | ≥ 95% | | |
| L4 | `security/credentials.py` coverage ≥ 90% | Xem trên | ≥ 90% | | |
| L5 | `security/redaction.py` coverage ≥ 95% | Xem trên | ≥ 95% | | |
| L6 | `broker/tcbs/auth.py` coverage ≥ 85% | Xem trên | ≥ 85% | | |
| L7 | Không có test import lỗi | `python -m pytest tests/unit/broker/tcbs/ --collect-only` | No import errors | | |

---

## Phần M — No Print / No Hardcode / No Secret

```powershell
# Không có print() trong broker lane
Select-String -Path "vnbroker/broker" -Pattern "^\s*print\(" -Recurse

# Không có hardcode URL production override
Select-String -Path "vnbroker/broker/**/*.py" -Pattern "openapi\.tcbs\.com\.vn" -Recurse | Where-Object { $_.Line -notmatch "default\s*=" }

# Không có test credentials trong code
Select-String -Path "tests/unit/broker/tcbs/**/*.py" -Pattern "(real|prod|live).*api_?key" -Recurse -CaseSensitive:$false
```

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| M1 | Không có `print()` trong `vnbroker/broker/` | Xem trên | Không có kết quả | | |
| M2 | Không có API key thật trong test code | Xem trên | Không có kết quả | | |
| M3 | Không có hardcode production URL ngoài default | Xem trên | Không có kết quả | | |
| M4 | Không có `show_log=True` với secret payload trong broker | `Select-String -Path "vnbroker/broker/**/*.py" -Pattern "show_log\s*=\s*True"` | Không có kết quả | | |

---

## Phần N — Git Hygiene và Docs Sync

```powershell
# Trailing whitespace
git diff --check

# Kiểm tra CENTRAL_MODIFIED_FILES_AUDIT.md đã được cập nhật
Select-String -Path "docs/CENTRAL_MODIFIED_FILES_AUDIT.md" -Pattern "vnbroker/broker"

# module_tree_full.md đã include broker/
Select-String -Path "module_tree_full.md" -Pattern "vnbroker/broker"

# TCBS_INDEX.md đã có 6 tài liệu kỹ thuật mới
Select-String -Path "docs/TCBS_INDEX.md" -Pattern "TCBS_API_CONTRACT|TCBS_BROKER_SPEC|TCBS_TEST_SPEC"
```

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| N1 | `git diff --check` pass | `git diff --check` | Exit code 0, no output | | |
| N2 | `CENTRAL_MODIFIED_FILES_AUDIT.md` cập nhật | Xem trên | Có entry `vnbroker/broker` | | |
| N3 | `module_tree_full.md` cập nhật | Xem trên | Có `vnbroker/broker` | | |
| N4 | `TCBS_INDEX.md` có 6 tài liệu mới | Xem trên | 3 pattern đều match | | |
| N5 | Commit message rõ ràng theo slice format | `git log --oneline -5` | `[TCBS-S*] ...` format | | |

---

## Tổng kết và Sign-off

| Mục | Số hạng mục | PASS | FAIL | SKIP |
|---|---|---|---|---|
| A — Cấu trúc file | 8 | | | |
| B — Import | 6 | | | |
| C — Credentials | 5 | | | |
| D — Session | 6 | | | |
| E — Redaction | 8 | | | |
| F — Account/Money | 5 | | | |
| G — Equity Read | 5 | | | |
| H — Write Flow | 8 | | | |
| I — Portfolio | 6 | | | |
| J — Provider Parity | 5 | | | |
| K — Backward Compat | 4 | | | |
| L — Coverage | 7 | | | |
| M — No Print/Secret | 4 | | | |
| N — Git Hygiene | 5 | | | |
| **Tổng** | **82** | | | |

---

### Kết quả audit

> Điền sau khi chạy đầy đủ:

- Tổng PASS: ___/82
- Tổng FAIL: ___
- Tổng SKIP: ___ (ghi lý do dưới đây)

**Lý do SKIP (nếu có):**
> _

**Các FAIL cần xử lý trước merge:**
> _

---

### Sign-off (3 vai trò bắt buộc)

| Vai trò | Họ tên | Ngày | Chữ ký / xác nhận |
|---|---|---|---|
| Developer (người implement) | | | |
| QA (người review test) | | | |
| Tech Lead (người chốt merge) | | | |

> **Không được merge vào `main` khi chưa có đủ 3 sign-off và tổng FAIL = 0.**
