# DNSE Audit Checklist V2 — Triển khai đầy đủ

> Mục tiêu: bộ checklist audit đầy đủ để sign-off trước khi merge nhánh `dev`.
>
> Phiên bản: 2.0 — nâng cấp từ V1, bổ sung phần I–L và mục bằng chứng thực tế.
>
> Ngày: 2026-05-08
>
> Người thực hiện: _______________
>
> Ngày audit: _______________
>
> Commit hash được audit: _______________
>
> **Hướng dẫn:** Mỗi mục điền "✅ PASS", "❌ FAIL [mô tả lỗi]", hoặc "⏭ SKIP [lý do]".
> Không để trống. Mọi ❌ FAIL phải tạo issue trước khi merge.

---

## Phần A — Cấu trúc file

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| A1 | `vnstock/explorer/dnse/__init__.py` tồn tại | `Test-Path vnstock/explorer/dnse/__init__.py` | True | | |
| A2 | `vnstock/explorer/dnse/quote.py` tồn tại | `Test-Path vnstock/explorer/dnse/quote.py` | True | | |
| A3 | `vnstock/explorer/dnse/listing.py` tồn tại | `Test-Path vnstock/explorer/dnse/listing.py` | True | | |
| A4 | `tests/unit/explorer/dnse/__init__.py` tồn tại | `Test-Path tests/unit/explorer/dnse/__init__.py` | True | | |
| A5 | `tests/unit/explorer/dnse/test_quote.py` tồn tại | `Test-Path ...` | True | | |
| A6 | `tests/unit/explorer/dnse/test_listing.py` tồn tại | `Test-Path ...` | True | | |
| A7 | `tests/unit/explorer/dnse/test_adapters.py` tồn tại | `Test-Path ...` | True | | |
| A8 | `tests/unit/connector/dnse/test_trade_bridge.py` tồn tại | `Test-Path ...` | True | | |
| A9 | `.env.dnse.example` tồn tại | `Test-Path .env.dnse.example` | True | | |
| A10 | `tests/integration/test_dnse_integration.py` tồn tại | `Test-Path ...` | True | | |

**Lệnh kiểm tra tổng hợp A:**
```powershell
@(
  "vnstock/explorer/dnse/__init__.py",
  "vnstock/explorer/dnse/quote.py",
  "vnstock/explorer/dnse/listing.py",
  "tests/unit/explorer/dnse/__init__.py",
  "tests/unit/explorer/dnse/test_quote.py",
  "tests/unit/explorer/dnse/test_listing.py",
  "tests/unit/explorer/dnse/test_adapters.py",
  "tests/unit/connector/dnse/test_trade_bridge.py",
  ".env.dnse.example"
) | ForEach-Object { "$_ : $(Test-Path $_)" }
```

---

## Phần B — Import và ProviderRegistry

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| B1 | `from vnstock import Vnstock` không lỗi | `python -c "from vnstock import Vnstock; print('OK')"` | `OK` | | |
| B2 | `DNSEQuote` importable | `python -c "from vnstock.explorer.dnse.quote import DNSEQuote; print('OK')"` | `OK` | | |
| B3 | `DNSEListing` importable | `python -c "from vnstock.explorer.dnse.listing import DNSEListing; print('OK')"` | `OK` | | |
| B4 | Registry quote/dnse đã đăng ký | Xem lệnh B4 | `True` | | |
| B5 | Registry listing/dnse đã đăng ký | Xem lệnh B4 | `True` | | |
| B6 | `Vnstock.SUPPORTED_SOURCES` có DNSE | Xem lệnh B6 | `True` | | |
| B7 | `StockComponents.SUPPORTED_SOURCES` có DNSE | Xem lệnh B7 | `True` | | |
| B8 | Không có circular import | `python -c "import vnstock"` | Không lỗi | | |

**Lệnh B4:**
```python
from vnstock import _ensure_explorer_modules_loaded; _ensure_explorer_modules_loaded()
from vnstock.core.registry import ProviderRegistry
print(ProviderRegistry.is_registered("quote", "dnse"))    # True
print(ProviderRegistry.is_registered("listing", "dnse"))  # True
```

**Lệnh B6:**
```python
from vnstock.common.client import Vnstock
print("DNSE" in Vnstock.SUPPORTED_SOURCES)
```

**Lệnh B7:**
```python
from vnstock.common.data import StockComponents, Quote, Listing
print("DNSE" in StockComponents.SUPPORTED_SOURCES)
print("DNSE" in Quote.SUPPORTED_SOURCES)
print("DNSE" in Listing.SUPPORTED_SOURCES)
```

---

## Phần C — Credential validation

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| C1 | Thiếu api_key → ValueError ngay | Xem lệnh C1 | `ValueError raised` | | |
| C2 | Thiếu api_secret → ValueError ngay | Xem lệnh C2 | `ValueError raised` | | |
| C3 | Env var DNSE_API_KEY được dùng nếu không truyền | Xem lệnh C3 | Không lỗi | | |
| C4 | Tham số trực tiếp ưu tiên hơn env var | Xem lệnh C4 | Key truyền vào được dùng | | |
| C5 | `DNSEListing` cũng raise ValueError khi thiếu key | Test tương tự C1 cho DNSEListing | ValueError | | |
| C6 | ValueError message có URL đăng ký DNSE | `assert 'developers.dnse.com.vn' in str(exc)` | True | | |

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
    q = DNSEQuote("VNM")
    print("PASS - env vars used")
```

---

## Phần D — Schema output và dtype

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| D1 | `history()` trả đúng 6 cột | Xem lệnh D1 | `['time','open','high','low','close','volume']` | | |
| D2 | `time` dtype `datetime64[ns]` không có tz | `df["time"].dt.tz is None` | True | | |
| D3 | `open/high/low/close` là float64 | `df["open"].dtype == "float64"` | True | | |
| D4 | `volume` là Int64 | `str(df["volume"].dtype) == "Int64"` | True | | |
| D5 | Trả empty DataFrame khi API lỗi, không raise | Xem lệnh D5 | Empty DF, không exception | | |
| D6 | `intraday()` trả đúng 4 cột | `["time","price","volume","side"]` | True | | |
| D7 | `intraday()` trả empty DF khi get_trades 404 | Mock 404, call intraday | Empty DF | | |
| D8 | `price_depth()` nhận body dạng list[dict] | Xem lệnh D8 | DataFrame không rỗng | | |

**Lệnh D1:**
```python
from vnstock.explorer.dnse.quote import _parse_ohlc
records = [{"t": 1704067200, "o": 67000.0, "h": 68500.0, "l": 66800.0, "c": 68000.0, "v": 1234567}]
df = _parse_ohlc(records)
print(list(df.columns))
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
    print("empty:", df.empty, "cols:", list(df.columns))
```

**Lệnh D8:**
```python
import pandas as pd
from vnstock.explorer.dnse.quote import _parse_ohlc
from unittest.mock import MagicMock, patch
import os; os.environ["DNSE_API_KEY"] = "k"; os.environ["DNSE_API_SECRET"] = "s"
# Giả lập list[dict] như live DNSE trả về
secdef_list = [{"symbol": "VNM", "boardId": "HOSE", "lotSize": 100}]
with patch("vnstock.connector.dnse.client.DNSEClient") as MC:
    mc = MagicMock()
    mc._market.get_security_definition.return_value = (None, secdef_list)
    MC.return_value = mc
    from vnstock.explorer.dnse.quote import DNSEQuote
    q = DNSEQuote("VNM")
    df = q.price_depth()
    print("rows:", len(df), "cols:", list(df.columns))
```

---

## Phần E — Không có print() và hardcode

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| E1 | Không có `print(` trong `explorer/dnse/` | PowerShell command | Không có output | | |
| E2 | Không có `print(` trong `trade.py` | PowerShell command | Không có output | | |
| E3 | Không có hardcode API key trong source | Grep pattern | Không có output | | |
| E4 | Không có secret trong test fixtures | Review thủ công | Không có credential thật | | |

**Lệnh E1:**
```powershell
Select-String -Path "vnstock\explorer\dnse\*.py" -Pattern "print\("
```

**Lệnh E2:**
```powershell
Select-String -Path "vnstock\connector\dnse\trade.py" -Pattern "print\("
```

**Lệnh E3:**
```powershell
Select-String -Path "vnstock\" -Recurse -Pattern "api_key\s*=\s*['\"][A-Za-z0-9]{10}" -Include "*.py" |
  Where-Object { $_.Line -notmatch "#" -and $_.Line -notmatch "environ" }
```

---

## Phần F — Unit tests

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| F1 | Unit tests explorer/dnse pass 100% | `pytest tests/unit/explorer/dnse/ -v` | 0 failed | | |
| F2 | Unit tests connector/dnse pass 100% | `pytest tests/unit/connector/dnse/ -v` | 0 failed | | |
| F3 | Coverage explorer/dnse ≥ 80% | `pytest --cov=vnstock/explorer/dnse -q` | ≥ 80% | | |
| F4 | Full unit không tăng số fail so với baseline | `pytest tests/ -v --ignore=tests/integration/` | Không nhiều hơn baseline | | |
| F5 | Thời gian chạy unit suite ≤ 30s | Elapsed từ pytest output | ≤ 30 giây | | |

---

## Phần G — Backward compatibility

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| G1 | VCI source vẫn hoạt động | `Vnstock().stock('VNM','VCI')` | Không lỗi | | |
| G2 | TCBS source vẫn hoạt động | `Vnstock().stock('VNM','TCBS')` | Không lỗi | | |
| G3 | KBS source vẫn hoạt động | `Vnstock().stock('VNM','KBS')` | Không lỗi | | |
| G4 | AUTO source vẫn hoạt động | `Vnstock().stock('VNM','AUTO')` | Không lỗi | | |
| G5 | `Trade()` public methods không bị đổi tên | `hasattr(Trade, 'login')`, v.v. | True | | |
| G6 | Không có circular import | `import vnstock` | Không lỗi ImportError | | |
| G7 | `explorer/__init__.py` không bị sửa scope | VCI/TCBS/KBS explorers load được | Không lỗi | | |

**Lệnh G7:**
```python
from vnstock.explorer import vci, tcbs, kbs
print("VCI, TCBS, KBS explorers OK")
```

---

## Phần H — Trade bridge methods

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| H1 | `as_openapi_client` tồn tại | `hasattr(Trade, 'as_openapi_client')` | True | | |
| H2 | `login_and_get_trading_session` tồn tại | `hasattr(Trade, 'login_and_get_trading_session')` | True | | |
| H3 | Cả hai method có docstring | `Trade.as_openapi_client.__doc__` | Không rỗng | | |
| H4 | `test_trade_bridge.py` pass 100% | `pytest tests/unit/connector/dnse/test_trade_bridge.py -v` | 0 failed | | |

---

## Phần I — Listing provider behavior

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| I1 | `all_symbols()` có cột `symbol` và `exchange` | Unit test hoặc lệnh trực tiếp | True | | |
| I2 | `symbols_by_exchange('HOSE')` không lỗi với mock | Unit test | Không raise | | |
| I3 | `indices()` không lỗi dù DNSE không có indexName endpoint | Fallback test | Empty DF hoặc filtered DF | | |
| I4 | Default limit = 1000 (không vượt limit live) | `inspect.getsource(DNSEListing._fetch_instruments)` | `limit=1000` | | |
| I5 | Column rename đúng: `marketId→exchange` | Unit test normalize | exchange in columns | | |

---

## Phần J — Connector và client contract

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| J1 | `DNSEClient._to_dataframe` nhận key `bars` | `'bars' in inspect.getsource(...)` | True | | |
| J2 | `DNSEClient._to_dataframe` nhận key `trades` | `'trades' in inspect.getsource(...)` | True | | |
| J3 | `DNSEClient._to_dataframe` nhận key `instruments` | `'instruments' in inspect.getsource(...)` | True | | |
| J4 | `get_ohlc` nhận `bar_type='STOCK'` | Contract review | Method tồn tại | | |
| J5 | `get_security_definition` trả được list | Unit test hoặc dry_run | DataFrame có rows | | |

---

## Phần K — Security và logging

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| K1 | Không log api_secret trong bất kỳ module nào | `Select-String -Recurse -Pattern "api_secret"` trong log paths | Không có output | | |
| K2 | Không log trading_token đầy đủ | Code review | Không thấy full token | | |
| K3 | `.env.dnse.example` không chứa credential thật | Review file | Chỉ có placeholder | | |
| K4 | Không có `api_key` hardcode trong tests | `Select-String -Path "tests/" -Recurse -Pattern '"[A-Z0-9]{20,}"'` | Không có key thật | | |
| K5 | Error messages không leak thông tin nhạy cảm | Code review | Chỉ message thân thiện | | |

---

## Phần L — Git hygiene và docs đồng bộ

| # | Hạng mục | Lệnh kiểm tra | Kết quả mong đợi | Kết quả thực tế | Bằng chứng |
|---|---|---|---|---|---|
| L1 | `git diff --check` sạch | `git diff --check` | Không có output | | |
| L2 | Chỉ sửa file trong phạm vi đã duyệt | `git diff --name-only dev~11 dev` | Chỉ DNSE files | | |
| L3 | `CENTRAL_MODIFIED_FILES_AUDIT.md` đã append | Review file | Có entry 2026-05-08 | | |
| L4 | `module_tree_full.md` đã cập nhật | Review file | Có listing DNSE explorer files | | |
| L5 | `DNSE_INDEX.md` đã cập nhật | Review file | Luồng đọc phản ánh đúng trạng thái | | |
| L6 | DNSE không có trong `OPEN_SOURCE_CANDIDATES` | `grep -i "dnse" vnstock/core/source_router.py` | Không có hoặc không trong candidates | | |
| L7 | Tất cả commit đã push lên `dev` | `git status` | Không có branch diverge | | |

**Lệnh L2:**
```powershell
git diff --name-only "$(git log --oneline | Select-String 'explorer.*dnse\|dnse.*explorer' | Select-Object -First 1 -ExpandProperty LineNumber)~1" HEAD
# hoặc review thủ công git log --oneline --stat
```

**Lệnh L6:**
```python
import pathlib
src = pathlib.Path("vnstock/core/source_router.py").read_text(errors="replace") if pathlib.Path("vnstock/core/source_router.py").exists() else ""
assert "dnse" not in src.lower().split("OPEN_SOURCE_CANDIDATES")[1].split("]")[0].lower() if "OPEN_SOURCE_CANDIDATES" in src else True
print("L6 PASS - DNSE not in open candidates")
```

---

## Tóm tắt kết quả audit

```
Tổng số mục:  ___
✅ PASS:      ___
❌ FAIL:      ___
⏭ SKIP:      ___

Phần có FAIL:
__________________________________________________

Mô tả FAIL và issue đã tạo:
__________________________________________________

Phần có SKIP:
__________________________________________________

Lý do SKIP:
__________________________________________________
```

---

## Form Sign-off

| Người | Vai trò | Ngày | Kết quả | Nhận xét |
|---|---|---|---|---|
| | Developer | | □ APPROVED □ BLOCKED | |
| | QA / Reviewer | | □ APPROVED □ BLOCKED | |
| | Tech Lead | | □ APPROVED □ BLOCKED | |

```
Quyết định cuối:  □ APPROVED — cho phép merge vào dev
                  □ BLOCKED  — lý do: ________________________
```
