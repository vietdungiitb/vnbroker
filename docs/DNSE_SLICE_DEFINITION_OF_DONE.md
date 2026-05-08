# DNSE Slice Definition of Done

> Mục tiêu: quy định chính xác "xong" nghĩa là gì cho từng slice S1–S11.
>
> Trạng thái: Tài liệu thực thi — không tự sửa phạm vi
>
> Ngày: 2026-05-08
>
> Sử dụng cùng với: `DNSE_SPRINT_TASK_BOARD.md` và `DNSE_TEST_AND_AUDIT_EVIDENCE_PROTOCOL.md`

---

## Cách dùng tài liệu này

Sau khi hoàn tất code hoặc edit một slice, người thực hiện phải:

1. Chạy từng lệnh validation trong phần slice tương ứng.
2. Ghi output vào mẫu evidence bên dưới.
3. Điền trạng thái PASS/FAIL/SKIP.
4. Append vào `CENTRAL_MODIFIED_FILES_AUDIT.md`.
5. Commit và push.

Không được chuyển sang slice kế tiếp khi slice hiện tại chưa có evidence đầy đủ.

---

## S1 — `_to_dataframe` mở rộng

### Validation commands

```powershell
# V1: Kiểm tra key 'bars' có trong source
python -c "
from vnstock.connector.dnse.client import DNSEClient
import inspect
src = inspect.getsource(DNSEClient._to_dataframe)
missing = [k for k in ('bars','candles','ohlc','trades','instruments','securities') if k not in src]
if missing: print('FAIL missing keys:', missing)
else: print('S1 V1 PASS')
"

# V2: Kiểm tra format diff sạch
git diff --check

# V3: Import sạch
python -c "from vnstock.connector.dnse.client import DNSEClient; print('S1 V3 PASS')"
```

### Mẫu ghi evidence S1

```text
Branch: dev
Commit: <hash>
Slice: S1
Environment: local
V1 output: ___________
V2 output: (rỗng = OK)
V3 output: ___________
PASS/FAIL/SKIP: ___________
Ghi chú: ___________
```

---

## S2 — `explorer/dnse/quote.py`

### Validation commands

```powershell
# V1: File tồn tại
python -c "import pathlib; assert pathlib.Path('vnstock/explorer/dnse/quote.py').exists(); print('S2 V1 PASS')"

# V2: Import class
python -c "from vnstock.explorer.dnse.quote import DNSEQuote; print('S2 V2 PASS')"

# V3: ValueError khi thiếu credential
python -c "
import os; os.environ.pop('DNSE_API_KEY',None); os.environ.pop('DNSE_API_SECRET',None)
from vnstock.explorer.dnse.quote import DNSEQuote
try:
    DNSEQuote('VNM')
    print('S2 V3 FAIL - không raise ValueError')
except ValueError as e:
    print('S2 V3 PASS -', str(e)[:60])
"

# V4: Unit tests
pytest tests/unit/explorer/dnse/test_quote.py -q

# V5: Không có print()
Select-String -Path "vnstock\explorer\dnse\quote.py" -Pattern "print\("
```

### Schema contract bắt buộc

| Method | Output columns | dtype time | dtype volume | dtype close |
|---|---|---|---|---|
| `history()` | `time,open,high,low,close,volume` | `datetime64[ns]` no-tz | `Int64` | `float64` |
| `intraday()` | `time,price,volume,side` | `datetime64[ns]` no-tz | `Int64` | `float64` |
| `price_depth()` | DataFrame từ `json_normalize` | — | — | — |

### Mẫu ghi evidence S2

```text
Branch: dev
Commit: <hash>
Slice: S2
Environment: local
V1 output: ___________
V2 output: ___________
V3 output: ___________
V4 output: ___ passed, ___ failed
V5 output: (rỗng = OK)
PASS/FAIL/SKIP: ___________
Ghi chú: ___________
```

---

## S3 — `explorer/dnse/listing.py`

### Validation commands

```powershell
# V1: File tồn tại
python -c "import pathlib; assert pathlib.Path('vnstock/explorer/dnse/listing.py').exists(); print('S3 V1 PASS')"

# V2: Import class
python -c "from vnstock.explorer.dnse.listing import DNSEListing; print('S3 V2 PASS')"

# V3: Unit tests
pytest tests/unit/explorer/dnse/test_listing.py -q

# V4: Không có print()
Select-String -Path "vnstock\explorer\dnse\listing.py" -Pattern "print\("
```

### Column rename contract

| Raw API column | Output column |
|---|---|
| `marketId` | `exchange` |
| `name` | `organ_name` |
| `securityGroupId` | `security_group` |
| `boardId` | `board_id` |

### Mẫu ghi evidence S3

```text
Branch: dev
Commit: <hash>
Slice: S3
V1–V4 output: ___________
PASS/FAIL/SKIP: ___________
```

---

## S4 — `explorer/dnse/__init__.py`

### Validation commands

```powershell
# V1: File tồn tại
python -c "import pathlib; assert pathlib.Path('vnstock/explorer/dnse/__init__.py').exists(); print('S4 V1 PASS')"

# V2: Registry check
python -c "
import importlib; importlib.import_module('vnstock.explorer.dnse')
from vnstock.core.registry import ProviderRegistry
assert ProviderRegistry.is_registered('quote','dnse'), 'quote/dnse not registered'
assert ProviderRegistry.is_registered('listing','dnse'), 'listing/dnse not registered'
print('S4 V2 PASS - registry OK')
"
```

### Mẫu ghi evidence S4

```text
Branch: dev
Commit: <hash>
Slice: S4
V1 output: ___________
V2 output: ___________
PASS/FAIL/SKIP: ___________
```

---

## S5 — `vnstock/__init__.py` lazy load

### Validation commands

```powershell
# V1: Import chính không lỗi
python -c "from vnstock import Vnstock; print('S5 V1 PASS')"

# V2: DNSE đã được load qua lazy loader
python -c "
from vnstock import Vnstock, _ensure_explorer_modules_loaded
_ensure_explorer_modules_loaded()
from vnstock.core.registry import ProviderRegistry
assert ProviderRegistry.is_registered('quote','dnse')
print('S5 V2 PASS - dnse loaded via lazy loader')
"

# V3: Không có circular import
python -c "import vnstock; print('S5 V3 PASS - no circular')"
```

### Mẫu ghi evidence S5

```text
Branch: dev
Commit: <hash>
Slice: S5
V1–V3 output: ___________
PASS/FAIL/SKIP: ___________
```

---

## S6 — `common/client.py` và `common/data.py`

### Validation commands

```powershell
# V1: DNSE trong SUPPORTED_SOURCES
python -c "
from vnstock.common.client import Vnstock
assert 'DNSE' in Vnstock.SUPPORTED_SOURCES, 'FAIL: DNSE not in SUPPORTED_SOURCES'
print('S6 V1 PASS')
"

# V2: Khởi tạo StockComponents với DNSE
python -c "
from vnstock import Vnstock
s = Vnstock().stock('VNM', source='DNSE', api_key='fake_k', api_secret='fake_s')
assert s.quote is not None, 'FAIL: s.quote is None'
assert s.listing is not None, 'FAIL: s.listing is None'
assert s.company is None, 'FAIL: s.company phải None'
print('S6 V2 PASS')
"

# V3: VCI backward compat
python -c "from vnstock import Vnstock; s=Vnstock().stock('VNM','VCI'); print('S6 V3 VCI PASS')"

# V4: TCBS backward compat
python -c "from vnstock import Vnstock; s=Vnstock().stock('VNM','TCBS'); print('S6 V4 TCBS PASS')"

# V5: KBS backward compat
python -c "from vnstock import Vnstock; s=Vnstock().stock('VNM','KBS'); print('S6 V5 KBS PASS')"
```

### Mẫu ghi evidence S6

```text
Branch: dev
Commit: <hash>
Slice: S6
V1 output: ___________
V2 output: ___________
V3 output: ___________
V4 output: ___________
V5 output: ___________
PASS/FAIL/SKIP: ___________
Ghi chú backward compat: ___________
```

---

## S7 — `trade.py` print → logger

### Validation commands

```powershell
# V1: Không có print() còn sót
Select-String -Path "vnstock\connector\dnse\trade.py" -Pattern "print\("

# V2: Logger đã được import
python -c "
import inspect, importlib
m = importlib.import_module('vnstock.connector.dnse.trade')
src = inspect.getsource(m)
assert 'get_logger' in src, 'FAIL: get_logger not found'
assert 'logger' in src, 'FAIL: logger not found'
print('S7 V2 PASS')
"

# V3: Unit tests không tăng fail
pytest tests/unit/connector/dnse/ -q
```

### Mẫu ghi evidence S7

```text
Branch: dev
Commit: <hash>
Slice: S7
V1 output: (rỗng = OK)
V2 output: ___________
V3 output: ___ passed, ___ failed
PASS/FAIL/SKIP: ___________
```

---

## S8 — `trade.py` bridge methods

### Validation commands

```powershell
# V1: Methods tồn tại
python -c "
from vnstock.connector.dnse.trade import Trade
assert hasattr(Trade,'as_openapi_client'), 'FAIL: as_openapi_client missing'
assert hasattr(Trade,'login_and_get_trading_session'), 'FAIL: login_and_get_trading_session missing'
print('S8 V1 PASS')
"

# V2: Methods có docstring
python -c "
from vnstock.connector.dnse.trade import Trade
assert Trade.as_openapi_client.__doc__, 'FAIL: as_openapi_client no docstring'
assert Trade.login_and_get_trading_session.__doc__, 'FAIL: login_and_get_trading_session no docstring'
print('S8 V2 PASS')
"

# V3: Bridge test
pytest tests/unit/connector/dnse/test_trade_bridge.py -q
```

### Mẫu ghi evidence S8

```text
Branch: dev
Commit: <hash>
Slice: S8
V1–V3 output: ___________
PASS/FAIL/SKIP: ___________
```

---

## S9 — Unit tests explorer/dnse

### Validation commands

```powershell
# V1: Chạy toàn bộ unit tests
pytest tests/unit/explorer/dnse/ tests/unit/connector/dnse/ -v --tb=short

# V2: Coverage (nếu có coverage plugin)
pytest tests/unit/explorer/dnse/ --cov=vnstock/explorer/dnse --cov-report=term-missing -q
```

### KPI bắt buộc

| Chỉ số | Ngưỡng |
|---|---|
| Unit test pass rate | 100% |
| Coverage `vnstock/explorer/dnse/` | ≥ 80% |
| Thời gian chạy unit suite DNSE | ≤ 30 giây |

### Mẫu ghi evidence S9

```text
Branch: dev
Commit: <hash>
Slice: S9
V1 output: ___ passed, ___ failed, ___ warnings
V2 coverage: ___% explorer/dnse
Elapsed: ___s
PASS/FAIL/SKIP: ___________
```

---

## S10 — Integration test explorer

### Validation commands

```powershell
# V1: Test skip sạch khi thiếu env
$env:DNSE_API_KEY=""; $env:DNSE_API_SECRET=""
pytest tests/integration/test_dnse_explorer.py -v

# V2: Test pass khi có credential (chỉ chạy khi có key thật)
# $env:DNSE_API_KEY="<real>"; $env:DNSE_API_SECRET="<real>"
# pytest tests/integration/test_dnse_explorer.py -v
```

### Mẫu ghi evidence S10

```text
Branch: dev
Commit: <hash>
Slice: S10
V1 output: ___ skipped
V2 output: (N/A nếu không có credential) hoặc ___ passed
PASS/FAIL/SKIP: SKIP (thiếu env) hoặc PASS
Lý do skip: DNSE_API_KEY không có trong môi trường
```

---

## S11 — `.env.dnse.example`

### Validation commands

```powershell
# V1: File tồn tại
Test-Path .env.dnse.example

# V2: Nội dung đủ hai luồng
Select-String -Path ".env.dnse.example" -Pattern "DNSE_API_KEY"
Select-String -Path ".env.dnse.example" -Pattern "DNSE_USERNAME"
```

### Mẫu ghi evidence S11

```text
Branch: dev
Commit: <hash>
Slice: S11
V1 output: True
V2 output: DNSE_API_KEY và DNSE_USERNAME tìm thấy
PASS/FAIL/SKIP: ___________
```

---

## Mẫu tổng hợp evidence cho toàn Sprint

Dùng bảng này để bàn giao cuối sprint:

| Slice | Trạng thái | Commit | Validation summary | Ghi chú |
|---|---|---|---|---|
| S1 | | | | |
| S2 | | | | |
| S3 | | | | |
| S4 | | | | |
| S5 | | | | |
| S6 | | | | |
| S7 | | | | |
| S8 | | | | |
| S9 | | | | |
| S10 | | | | |
| S11 | | | | |

**Sprint DONE khi:** tất cả S1–S9 là PASS hoặc PASS với caveat; S10, S11 có thể là SKIP với lý do.
