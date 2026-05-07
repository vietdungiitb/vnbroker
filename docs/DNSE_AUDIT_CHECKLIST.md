# DNSE Explorer — Audit Evidence Checklist
**Phiên bản:** 1.0  
**Ngày duyệt:** 2026-05-07  
**Người thực hiện audit:** _______________  
**Ngày thực hiện audit:** _______________  

> **Hướng dẫn:** Mỗi mục điền "✅ PASS", "❌ FAIL [mô tả lỗi]", hoặc "⏭ SKIP [lý do]". Không được để trống. Mọi ❌ FAIL phải tạo issue trước khi merge.

---

## Phần A — Kiểm tra cấu trúc file

| # | Hạng mục | Cách kiểm tra | Kết quả mong đợi | Kết quả thực tế |
|---|---|---|---|---|
| A1 | `vnstock/explorer/dnse/__init__.py` tồn tại | `Test-Path vnstock/explorer/dnse/__init__.py` | True | |
| A2 | `vnstock/explorer/dnse/quote.py` tồn tại | `Test-Path vnstock/explorer/dnse/quote.py` | True | |
| A3 | `vnstock/explorer/dnse/listing.py` tồn tại | `Test-Path vnstock/explorer/dnse/listing.py` | True | |
| A4 | `tests/unit/explorer/dnse/__init__.py` tồn tại | `Test-Path tests/unit/explorer/dnse/__init__.py` | True | |
| A5 | `tests/unit/explorer/dnse/test_quote.py` tồn tại | `Test-Path tests/unit/explorer/dnse/test_quote.py` | True | |
| A6 | `tests/unit/explorer/dnse/test_listing.py` tồn tại | `Test-Path tests/unit/explorer/dnse/test_listing.py` | True | |
| A7 | `tests/integration/test_dnse_explorer.py` tồn tại | `Test-Path tests/integration/test_dnse_explorer.py` | True | |

**Lệnh kiểm tra tổng hợp phần A:**
```powershell
@(
  "vnstock/explorer/dnse/__init__.py",
  "vnstock/explorer/dnse/quote.py",
  "vnstock/explorer/dnse/listing.py",
  "tests/unit/explorer/dnse/__init__.py",
  "tests/unit/explorer/dnse/test_quote.py",
  "tests/unit/explorer/dnse/test_listing.py",
  "tests/integration/test_dnse_explorer.py"
) | ForEach-Object { Write-Host "$_ : $(Test-Path $_)" }
```

---

## Phần B — Kiểm tra import & registry

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế |
|---|---|---|---|---|
| B1 | Import vnstock không lỗi | `python -c "from vnstock import Vnstock; print('OK')"` | `OK` | |
| B2 | DNSEQuote importable | `python -c "from vnstock.explorer.dnse.quote import DNSEQuote; print('OK')"` | `OK` | |
| B3 | DNSEListing importable | `python -c "from vnstock.explorer.dnse.listing import DNSEListing; print('OK')"` | `OK` | |
| B4 | ProviderRegistry có quote/dnse | Xem lệnh B4 | `True` | |
| B5 | ProviderRegistry có listing/dnse | Xem lệnh B5 | `True` | |
| B6 | Vnstock.SUPPORTED_SOURCES có DNSE | Xem lệnh B6 | `True` | |
| B7 | StockComponents.SUPPORTED_SOURCES có DNSE | Xem lệnh B7 | `True` | |

**Lệnh B4:**
```python
from vnstock import _ensure_explorer_modules_loaded; _ensure_explorer_modules_loaded()
from vnstock.core.registry import ProviderRegistry
print(ProviderRegistry.is_registered("quote", "dnse"))   # True
print(ProviderRegistry.is_registered("listing", "dnse")) # True
```

**Lệnh B6:**
```python
from vnstock.common.client import Vnstock
print("DNSE" in Vnstock.SUPPORTED_SOURCES)  # True
```

**Lệnh B7:**
```python
from vnstock.common.data import StockComponents, Quote, Listing
print("DNSE" in StockComponents.SUPPORTED_SOURCES)  # True
print("DNSE" in Quote.SUPPORTED_SOURCES)             # True
print("DNSE" in Listing.SUPPORTED_SOURCES)           # True
```

---

## Phần C — Kiểm tra credential validation

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế |
|---|---|---|---|---|
| C1 | Thiếu api_key → ValueError ngay trong `__init__` | Xem lệnh C1 | `ValueError raised` | |
| C2 | Thiếu api_secret → ValueError ngay trong `__init__` | Xem lệnh C2 | `ValueError raised` | |
| C3 | Env var DNSE_API_KEY được dùng nếu không truyền tham số | Xem lệnh C3 | Không lỗi | |
| C4 | Tham số trực tiếp ưu tiên hơn env var | Xem lệnh C4 | Key truyền vào được dùng | |
| C5 | DNSEListing cũng raise ValueError khi thiếu key | `python -c "from vnstock.explorer.dnse.listing import DNSEListing; DNSEListing()"` | `ValueError` | |

**Lệnh C1:**
```python
import os; os.environ.pop("DNSE_API_KEY", None); os.environ.pop("DNSE_API_SECRET", None)
from vnstock.explorer.dnse.quote import DNSEQuote
try:
    q = DNSEQuote("VNM")
    print("FAIL: không raise ValueError")
except ValueError as e:
    print("PASS:", str(e)[:80])
```

**Lệnh C3:**
```python
import os; os.environ["DNSE_API_KEY"] = "test_k"; os.environ["DNSE_API_SECRET"] = "test_s"
from unittest.mock import patch
with patch("vnstock.connector.dnse.client.DNSEClient"):
    from vnstock.explorer.dnse.quote import DNSEQuote
    q = DNSEQuote("VNM")  # Không lỗi
    print("PASS")
```

---

## Phần D — Kiểm tra schema output

| # | Hạng mục | Cách kiểm tra | Kết quả mong đợi | Kết quả thực tế |
|---|---|---|---|---|
| D1 | `history()` trả đúng 6 cột | Xem lệnh D1 | 6 cột đúng tên | |
| D2 | `time` có dtype `datetime64[ns]` (không có tz) | `df["time"].dtype == "datetime64[ns]"` | True | |
| D3 | `open/high/low/close` là float64 | `df["open"].dtype == float64` | True | |
| D4 | `volume` là Int64 (nullable) | `str(df["volume"].dtype) == "Int64"` | True | |
| D5 | Trả empty DataFrame (không raise) khi API lỗi | Xem lệnh D5 | Empty DF, không exception | |
| D6 | `intraday()` trả đúng 4 cột | `["time","price","volume","side"]` trong columns | True | |

**Lệnh D1:**
```python
from vnstock.explorer.dnse.quote import _parse_ohlc
from datetime import datetime
records = [
    {"t": 1704067200, "o": 67000.0, "h": 68500.0, "l": 66800.0, "c": 68000.0, "v": 1234567}
]
df = _parse_ohlc(records)
print(list(df.columns))   # ['time', 'open', 'high', 'low', 'close', 'volume']
print(df.dtypes)
```

**Lệnh D5:**
```python
from unittest.mock import MagicMock, patch
import os; os.environ["DNSE_API_KEY"] = "k"; os.environ["DNSE_API_SECRET"] = "s"
with patch("vnstock.connector.dnse.client.DNSEClient") as MC:
    mc = MagicMock()
    mc._market.get_ohlc.side_effect = Exception("timeout")
    MC.return_value = mc
    from vnstock.explorer.dnse.quote import DNSEQuote
    q = DNSEQuote("VNM")
    df = q.history(start="2024-01-01")
    print("Empty:", df.empty)   # True
    print("Columns:", list(df.columns))  # ['time', 'open', ...]
```

---

## Phần E — Kiểm tra không có print() và hardcode

| # | Hạng mục | Cách kiểm tra | Kết quả mong đợi | Kết quả thực tế |
|---|---|---|---|---|
| E1 | Không có `print(` trong `explorer/dnse/` | `grep -n "print(" vnstock/explorer/dnse/*.py` | Không có kết quả | |
| E2 | Không có `print(` trong `connector/dnse/trade.py` | `grep -n "print(" vnstock/connector/dnse/trade.py` | Không có kết quả | |
| E3 | Không có hardcode key trong source files | `grep -rn "api_key.*=.*['\"][A-Za-z0-9]" vnstock/` (exclude .env) | Không có kết quả | |

**Lệnh PowerShell E1:**
```powershell
Select-String -Path "vnstock\explorer\dnse\*.py" -Pattern "print\("
# Mong đợi: không có output
```

**Lệnh PowerShell E2:**
```powershell
Select-String -Path "vnstock\connector\dnse\trade.py" -Pattern "print\("
# Mong đợi: không có output
```

---

## Phần F — Unit tests pass

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế |
|---|---|---|---|---|
| F1 | Unit tests explorer/dnse pass 100% | `pytest tests/unit/explorer/dnse/ -v` | 0 failed | |
| F2 | Unit tests connector/dnse pass 100% | `pytest tests/unit/connector/dnse/ -v` | 0 failed | |
| F3 | Full vnstock import không phá tests hiện có | `pytest tests/ -v --ignore=tests/integration/` | Không tăng số fail | |

---

## Phần G — Backward compatibility

| # | Hạng mục | Cách kiểm tra | Kết quả mong đợi | Kết quả thực tế |
|---|---|---|---|---|
| G1 | VCI source vẫn hoạt động | `python -c "from vnstock import Vnstock; v=Vnstock(); s=v.stock('VNM','VCI'); print('VCI OK')"` | `VCI OK` | |
| G2 | TCBS source vẫn hoạt động | Tương tự với `'TCBS'` | `TCBS OK` | |
| G3 | AUTO source vẫn hoạt động | Tương tự với `'AUTO'` | `AUTO OK` | |
| G4 | Không có circular import | `python -c "import vnstock"` | Không lỗi ImportError | |
| G5 | `explorer/__init__.py` không bị sửa scope | Xem lệnh G5 | Các module khác vẫn load được | |

**Lệnh G5:**
```python
from vnstock.explorer import vci, tcbs, kbs
print("VCI, TCBS, KBS explorers OK")
```

---

## Phần H — Code review checklist

| # | Hạng mục | Review | Pass |
|---|---|---|---|
| H1 | Tất cả public method có `**kwargs` | Code review | |
| H2 | Import `DNSEClient` trong `__init__` của class (không ở module level) | Code review | |
| H3 | `ValueError` có message đủ hướng dẫn user (có URL đăng ký) | Code review | |
| H4 | Không có exception bị nuốt im trong `history()`/`intraday()` | Code review | |
| H5 | `trade.py` không còn `print()` | Code review + E2 | |
| H6 | `as_openapi_client` và `login_and_get_trading_session` có docstring | Code review | |
| H7 | DNSE không được thêm vào `OPEN_SOURCE_CANDIDATES` | Kiểm tra `source_router.py` | |
| H8 | Chỉ sửa file trong danh sách đã duyệt (Section 2 của DNSE_EXPLORER_SPEC.md) | `git diff --name-only` | |

**Lệnh H7:**
```python
with open("vnstock/core/source_router.py") as f:
    src = f.read()
assert "dnse" not in src.lower() or "OPEN_SOURCE_CANDIDATES" not in src, \
    "FAIL: DNSE không được trong OPEN_SOURCE_CANDIDATES"
print("H7 PASS")
```

**Lệnh H8 (sau khi code xong, trước merge):**
```powershell
git diff --name-only main
# Chỉ được thấy:
# vnstock/explorer/dnse/__init__.py
# vnstock/explorer/dnse/quote.py
# vnstock/explorer/dnse/listing.py
# vnstock/connector/dnse/client.py
# vnstock/connector/dnse/trade.py
# vnstock/common/data.py
# vnstock/common/client.py
# vnstock/__init__.py
# tests/unit/explorer/dnse/... (files test)
# tests/integration/test_dnse_explorer.py
# docs/... (documentation files)
```

---

## Phần I — Sign-off

| Người | Vai trò | Ngày | Chữ ký/Nhận xét |
|---|---|---|---|
| | Developer | | |
| | QA / Reviewer | | |
| | Tech Lead | | |

---

## Tóm tắt kết quả audit

```
Tổng số mục: 40+
PASS:    ___
FAIL:    ___
SKIP:    ___

Ghi chú:
_________________________________________________________________
_________________________________________________________________

Quyết định merge: □ APPROVED  □ BLOCKED (ghi lý do)
```
