# DNSE Sprint Task Board

> Mục tiêu: bảng theo dõi công việc slice-by-slice cho đội code.
>
> Trạng thái: Sẵn sàng triển khai
>
> Ngày: 2026-05-08
>
> Nguồn gốc: tổng hợp từ `DNSE_INTEGRATION_PLAN_20260507.md` + `DNSE_EXPLORER_SPEC.md` + `DNSE_CODING_GUIDE.md`

---

## 1. Tổng quan Sprint

| Hạng mục | Giá trị |
|---|---|
| Sprint goal | DNSE được dùng như source ngang hàng VCI/KBS/TCBS trong vnbroker |
| Độ dài sprint | 1-2 ngày working |
| Branch | `dev` |
| Định nghĩa done (toàn sprint) | Tất cả ô trạng thái = ✅ DONE, `git diff --check` sạch, CI pass |

---

## 2. Scope rõ ràng

### Trong scope — không được bỏ

| Scope | Hạng mục |
|---|---|
| A — Market Data Provider | Tích hợp DNSE vào ProviderRegistry như source chuẩn |
| B — Trade/Account Bridge | Refactor Trade cũ, thêm bridge method sang OpenAPI |
| C — Tests & Tooling | Unit test explorer, integration test, env example |

### Ngoài scope — không được thêm

- WebSocket / streaming real-time DNSE
- DNSE vào `source='AUTO'` (cần auth, không thể là open candidate)
- Company / Financial / Screener cho DNSE
- Thay đổi tên method public của `Trade` cũ (backward compat)
- Thay đổi DNSE core/services đã hoàn chỉnh từ sprint 2026-04-13

---

## 3. Task Board — Slice S1–S11

### Cột mô tả

- **Slice**: ký hiệu ngắn
- **File tác động**: file cụ thể cần sửa/tạo
- **Mục tiêu slice**: output đo được
- **Phụ thuộc**: slice nào phải xong trước
- **Ước tính**: thời gian kỳ vọng
- **Người làm**: điền trước khi bắt đầu
- **Trạng thái**: `🔲 TODO` / `🔄 IN PROGRESS` / `✅ DONE` / `⏭ SKIP`
- **Bằng chứng**: lệnh validation hoặc link output

---

### S1 — Mở rộng `_to_dataframe` trong connector

| Trường | Giá trị |
|---|---|
| **File tác động** | `vnbroker/connector/dnse/client.py` |
| **Mục tiêu slice** | `_to_dataframe` nhận đủ keys: `bars`, `candles`, `ohlc`, `trades`, `instruments`, `securities` |
| **Phụ thuộc** | Không có |
| **Ước tính** | 10 phút |
| **Người làm** | _____ |
| **Trạng thái** | 🔲 TODO |
| **Bằng chứng** | `python -c "from vnbroker.connector.dnse.client import DNSEClient; import inspect; src = inspect.getsource(DNSEClient._to_dataframe); assert 'bars' in src; print('S1 PASS')"` |

**Checklist S1:**
- [ ] Keys `bars`, `candles`, `ohlc` được nhận
- [ ] Keys `trades`, `instruments`, `securities` được nhận
- [ ] Không thay đổi behavior cho keys cũ (`data`, `items`, `orders`, `accounts`, ...)
- [ ] Bằng chứng assertion pass

---

### S2 — Tạo `explorer/dnse/quote.py`

| Trường | Giá trị |
|---|---|
| **File tác động** | `vnbroker/explorer/dnse/quote.py` (NEW) |
| **Mục tiêu slice** | `DNSEQuote.history()` trả DataFrame đúng schema với mock client |
| **Phụ thuộc** | S1 |
| **Ước tính** | 30 phút |
| **Người làm** | _____ |
| **Trạng thái** | 🔲 TODO |
| **Bằng chứng** | `pytest tests/unit/explorer/dnse/test_quote.py -q` → 0 failed |

**Checklist S2:**
- [ ] File `vnbroker/explorer/dnse/quote.py` tồn tại
- [ ] Class `DNSEQuote` có `__init__(symbol, api_key, api_secret, show_log, **kwargs)`
- [ ] `ValueError` raise khi thiếu api_key hoặc api_secret
- [ ] `ValueError` message có URL đăng ký DNSE
- [ ] Method `history(symbol, start, end, interval, **kwargs)` trả DataFrame
- [ ] Cột output đúng: `time, open, high, low, close, volume`
- [ ] `time` dtype = `datetime64[ns]`, không có tz
- [ ] `volume` dtype = `Int64` (nullable)
- [ ] `open/high/low/close` dtype = `float64`
- [ ] Sort tăng dần theo `time`
- [ ] Trả empty DataFrame khi `get_ohlc` lỗi (không raise)
- [ ] Method `intraday(symbol, page_size, **kwargs)` trả DataFrame
- [ ] `intraday` trả empty DataFrame khi `get_trades` 404 (không raise)
- [ ] Method `price_depth(symbol, **kwargs)` trả DataFrame
- [ ] `price_depth` chấp nhận body dạng `list[dict]`
- [ ] Helpers `_normalize_interval`, `_to_unix_seconds`, `_extract_ohlc_list`, `_parse_ohlc`, `_parse_trades` tồn tại
- [ ] Không có `print()` trong file

---

### S3 — Tạo `explorer/dnse/listing.py`

| Trường | Giá trị |
|---|---|
| **File tác động** | `vnbroker/explorer/dnse/listing.py` (NEW) |
| **Mục tiêu slice** | `DNSEListing.all_symbols()` trả DataFrame có cột `symbol`, `exchange` |
| **Phụ thuộc** | S1 |
| **Ước tính** | 20 phút |
| **Người làm** | _____ |
| **Trạng thái** | 🔲 TODO |
| **Bằng chứng** | `pytest tests/unit/explorer/dnse/test_listing.py -q` → 0 failed |

**Checklist S3:**
- [ ] File `vnbroker/explorer/dnse/listing.py` tồn tại
- [ ] Class `DNSEListing` có `__init__(api_key, api_secret, show_log, **kwargs)`
- [ ] `ValueError` raise khi thiếu credential
- [ ] Method `all_symbols()` trả DataFrame
- [ ] Method `symbols_by_exchange(exchange)` trả DataFrame
- [ ] Method `symbols_by_group(group)` trả DataFrame
- [ ] Method `indices()` trả DataFrame
- [ ] Column rename: `marketId→exchange`, `name→organ_name`, `securityGroupId→security_group`, `boardId→board_id`
- [ ] Default limit = `1000` (không vượt limit live DNSE)
- [ ] Không có `print()` trong file

---

### S4 — Tạo `explorer/dnse/__init__.py`

| Trường | Giá trị |
|---|---|
| **File tác động** | `vnbroker/explorer/dnse/__init__.py` (NEW) |
| **Mục tiêu slice** | `ProviderRegistry.is_registered("quote", "dnse")` → `True` |
| **Phụ thuộc** | S2, S3 |
| **Ước tính** | 5 phút |
| **Người làm** | _____ |
| **Trạng thái** | 🔲 TODO |
| **Bằng chứng** | `python -c "from vnbroker.explorer.dnse import DNSEQuote, DNSEListing; print('S4 PASS')"` |

**Checklist S4:**
- [ ] File `vnbroker/explorer/dnse/__init__.py` tồn tại
- [ ] `ProviderRegistry.register("quote", "dnse", DNSEQuote)` được gọi
- [ ] `ProviderRegistry.register("listing", "dnse", DNSEListing)` được gọi
- [ ] Import `DNSEQuote`, `DNSEListing` từ `__init__` hoạt động

---

### S5 — Sửa `vnbroker/__init__.py` (lazy load dnse)

| Trường | Giá trị |
|---|---|
| **File tác động** | `vnbroker/__init__.py` |
| **Mục tiêu slice** | `_ensure_explorer_modules_loaded()` load `dnse` module |
| **Phụ thuộc** | S4 |
| **Ước tính** | 5 phút |
| **Người làm** | _____ |
| **Trạng thái** | 🔲 TODO |
| **Bằng chứng** | `python -c "from vnbroker import vnbroker; print('S5 PASS')"` |

**Checklist S5:**
- [ ] `from .explorer import dnse` được thêm vào `_ensure_explorer_modules_loaded()`
- [ ] `import vnbroker` không gây lỗi ImportError
- [ ] Không tạo circular import

---

### S6 — Sửa `vnbroker/common/client.py` và `common/data.py`

| Trường | Giá trị |
|---|---|
| **File tác động** | `vnbroker/common/client.py`, `vnbroker/common/data.py` |
| **Mục tiêu slice** | `vnbroker().stock('VNM', source='DNSE', api_key=..., api_secret=...)` khởi tạo được |
| **Phụ thuộc** | S5 |
| **Ước tính** | 20 phút |
| **Người làm** | _____ |
| **Trạng thái** | 🔲 TODO |
| **Bằng chứng** | `python -c "from vnbroker import vnbroker; s = vnbroker().stock('VNM','DNSE',api_key='k',api_secret='s'); print('S6 PASS')"` |

**Checklist S6:**
- [ ] `"DNSE"` có trong `SUPPORTED_SOURCES` của `vnbroker`
- [ ] `stock()` nhận `api_key` và `api_secret` kwargs
- [ ] `api_key`/`api_secret` được truyền vào `StockComponents`
- [ ] `StockComponents` với `source='DNSE'` khởi tạo `self.quote` và `self.listing`
- [ ] `StockComponents` với `source='DNSE'` set `self.trading = None`
- [ ] `StockComponents` với `source='DNSE'` set `self.company = None`
- [ ] `Quote(source='dnse')` nhận credential
- [ ] `Listing(source='dnse')` nhận credential
- [ ] VCI/TCBS/KBS source vẫn hoạt động bình thường

---

### S7 — Refactor `connector/dnse/trade.py` (print → logger)

| Trường | Giá trị |
|---|---|
| **File tác động** | `vnbroker/connector/dnse/trade.py` |
| **Mục tiêu slice** | Không còn `print()` trong file `trade.py` |
| **Phụ thuộc** | Không (độc lập) |
| **Ước tính** | 20 phút |
| **Người làm** | _____ |
| **Trạng thái** | 🔲 TODO |
| **Bằng chứng** | `Select-String -Path "vnbroker\connector\dnse\trade.py" -Pattern "print\("` → không có output |

**Checklist S7:**
- [ ] Không có `print(` trong `trade.py`
- [ ] `from vnbroker.core.utils.logger import get_logger` được import
- [ ] `logger = get_logger(__name__)` tồn tại
- [ ] Tất cả `print(...)` đã thay bằng `logger.info(...)` hoặc `logger.error(...)`
- [ ] Public method names giữ nguyên (backward compat)
- [ ] Tham số công khai không thay đổi
- [ ] `pytest tests/unit/connector/dnse/ -q` → không tăng số fail

---

### S8 — Thêm bridge methods vào `trade.py`

| Trường | Giá trị |
|---|---|
| **File tác động** | `vnbroker/connector/dnse/trade.py` |
| **Mục tiêu slice** | `Trade().as_openapi_client(api_key, api_secret)` trả `DNSEClient` instance |
| **Phụ thuộc** | S7 |
| **Ước tính** | 20 phút |
| **Người làm** | _____ |
| **Trạng thái** | 🔲 TODO |
| **Bằng chứng** | `pytest tests/unit/connector/dnse/test_trade_bridge.py -q` → 0 failed |

**Checklist S8:**
- [ ] Method `as_openapi_client(self, api_key, api_secret) -> DNSEClient` tồn tại
- [ ] Method `login_and_get_trading_session(self, username, password, otp_type, api_key, api_secret) -> dict` tồn tại
- [ ] `as_openapi_client` có docstring giải thích
- [ ] `login_and_get_trading_session` có docstring giải thích
- [ ] Không break tests cũ của `trade.py`

---

### S9 — Unit tests cho explorer/dnse

| Trường | Giá trị |
|---|---|
| **File tác động** | `tests/unit/explorer/dnse/test_quote.py`, `test_listing.py`, `test_adapters.py` |
| **Mục tiêu slice** | `pytest tests/unit/explorer/dnse/ -q` → 0 failed, coverage ≥ 80% |
| **Phụ thuộc** | S2, S3, S6 |
| **Ước tính** | 30 phút |
| **Người làm** | _____ |
| **Trạng thái** | 🔲 TODO |
| **Bằng chứng** | Output `pytest tests/unit/explorer/dnse/ -v --tb=short` |

**Checklist S9:**
- [ ] `test_quote.py`: test `history()` chuẩn hóa cột, dtype, sort
- [ ] `test_quote.py`: test `intraday()` trả empty khi mock 404
- [ ] `test_quote.py`: test `price_depth()` với body dict và list
- [ ] `test_quote.py`: test `ValueError` khi thiếu api_key
- [ ] `test_listing.py`: test `all_symbols()` với mock instruments
- [ ] `test_listing.py`: test `symbols_by_exchange()` filter
- [ ] `test_listing.py`: test `indices()` fallback
- [ ] `test_adapters.py`: test `Quote(source='dnse')` nhận credential
- [ ] `test_adapters.py`: test `Listing(source='dnse')` nhận credential
- [ ] 0 failed
- [ ] Coverage DNSE explorer ≥ 80%

---

### S10 — Integration test cho explorer

| Trường | Giá trị |
|---|---|
| **File tác động** | `tests/integration/test_dnse_explorer.py` |
| **Mục tiêu slice** | Test skip sạch khi thiếu env; pass khi có credential |
| **Phụ thuộc** | S9 |
| **Ước tính** | 20 phút |
| **Người làm** | _____ |
| **Trạng thái** | 🔲 TODO |
| **Bằng chứng** | `pytest tests/integration/test_dnse_explorer.py -v` output với `skip` hoặc `pass` |

**Checklist S10:**
- [ ] Test skip sạch khi `DNSE_API_KEY` không set
- [ ] Khi có credential: `history('VNM', start=...)` trả DataFrame không rỗng
- [ ] Validate schema: `time` là datetime, `close` là float
- [ ] `all_symbols()` trả ít nhất 10 rows
- [ ] Không leak credential vào output

---

### S11 — Cập nhật `.env.dnse.example`

| Trường | Giá trị |
|---|---|
| **File tác động** | `.env.dnse.example` |
| **Mục tiêu slice** | File example đủ hướng dẫn cả hai luồng HMAC và JWT |
| **Phụ thuộc** | S8 |
| **Ước tính** | 5 phút |
| **Người làm** | _____ |
| **Trạng thái** | 🔲 TODO |
| **Bằng chứng** | `Test-Path .env.dnse.example` → True; review nội dung |

**Checklist S11:**
- [ ] File tồn tại
- [ ] Có hướng dẫn cho luồng HMAC (`DNSE_API_KEY`, `DNSE_API_SECRET`)
- [ ] Có hướng dẫn cho luồng JWT (`DNSE_USERNAME`, `DNSE_PASSWORD`, `DNSE_ACCOUNT_NO`)
- [ ] Không chứa credential thật
- [ ] Có link đến tài liệu DNSE

---

## 4. Bảng tổng quan theo dõi

| Slice | Mô tả | Độ ưu tiên | Phụ thuộc | Người làm | Trạng thái | Commit |
|---|---|---|---|---|---|---|
| S1 | client.py `_to_dataframe` mở rộng | P0 | — | | 🔲 TODO | |
| S2 | explorer/dnse/quote.py | P0 | S1 | | 🔲 TODO | |
| S3 | explorer/dnse/listing.py | P0 | S1 | | 🔲 TODO | |
| S4 | explorer/dnse/__init__.py | P0 | S2, S3 | | 🔲 TODO | |
| S5 | vnbroker/__init__.py lazy load | P0 | S4 | | 🔲 TODO | |
| S6 | common/client.py + data.py | P0 | S5 | | 🔲 TODO | |
| S7 | trade.py print → logger | P1 | — | | 🔲 TODO | |
| S8 | trade.py bridge methods | P1 | S7 | | 🔲 TODO | |
| S9 | unit tests explorer/dnse | P1 | S2, S3, S6 | | 🔲 TODO | |
| S10 | integration test explorer | P2 | S9 | | 🔲 TODO | |
| S11 | .env.dnse.example cập nhật | P2 | S8 | | 🔲 TODO | |

---

## 5. Nguyên tắc làm việc không hỏi lại

1. Nếu có xung đột giữa tài liệu: ưu tiên `DNSE_API_CONTRACT.md` cho contract, `DNSE_EXPLORER_SPEC.md` cho class/method, `DNSE_CODING_GUIDE.md` cho implementation detail.
2. Nếu một method chưa có trong contract nhưng explorer cần: trả `pd.DataFrame()` rỗng, không raise.
3. Nếu live API trả format khác mock: cập nhật parser, ghi vào audit, không tự thêm endpoint mới.
4. Nếu test fail do môi trường (thiếu env): SKIP với lý do rõ ràng, không để FAIL.
5. Sau khi mỗi slice pass: commit riêng, push ngay, append audit.

---

## 6. Definition of Done — Toàn Sprint

Sprint chỉ được coi là xong khi tất cả điều kiện sau đồng thời thỏa:

- [ ] Tất cả S1–S9 ở trạng thái ✅ DONE (S10, S11 có thể SKIP với lý do env)
- [ ] `pytest tests/unit/explorer/dnse/ tests/unit/connector/dnse/ -q` → 0 failed
- [ ] `python -c "from vnbroker import vnbroker; s = vnbroker().stock('VNM','DNSE',api_key='k',api_secret='s'); print('OK')"` → `OK`
- [ ] `git diff --check` → không có output
- [ ] `Select-String -Path "vnbroker\explorer\dnse\*.py","vnbroker\connector\dnse\trade.py" -Pattern "print\("` → không có output
- [ ] `CENTRAL_MODIFIED_FILES_AUDIT.md` đã được append
- [ ] `module_tree_full.md` và `DNSE_INDEX.md` đã được cập nhật
- [ ] Tất cả commit đã push lên nhánh `dev`
