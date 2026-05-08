# Kế hoạch tích hợp DNSE LightSpeed API vào vnbroker
**Ngày:** 2026-05-07  
**Trạng thái:** CHỜ PHÊ DUYỆT  
**Tác giả:** GitHub Copilot  

---

## 1. Bối cảnh & Vấn đề hiện tại

### 1.1 Tình trạng hiện có (đã có sẵn)

Dự án đã có skeleton DNSE từ sprint 2026-04-13:

| File | Trạng thái | Ghi chú |
|---|---|---|
| `vnbroker/connector/dnse/core/*` | ✅ Xong | Config, signature, http_client, errors, models |
| `vnbroker/connector/dnse/services/*` | ✅ Xong | AccountService, MarketService, OrderService, PositionService, TokenService |
| `vnbroker/connector/dnse/client.py` | ✅ Xong | Facade DNSEClient với dry_run/raw mode |
| `vnbroker/connector/dnse/trade.py` | ✅ Có | Class Trade cũ (JWT-based, api.dnse.com.vn) — còn dùng `print()` thô |
| `vnbroker/connector/dnse/__init__.py` | ✅ Xong | Export DNSEClient, Trade |
| `tests/unit/connector/dnse/*` | ✅ Xong | Unit tests cho core/services |

### 1.2 Vấn đề còn tồn tại

1. **Không có explorer/dnse** — DNSE chưa thể dùng qua `vnbroker().stock('VNM', source='DNSE')` hay `Quote(source='dnse', ...)` như VCI/KBS/TCBS.
2. **vnbroker.SUPPORTED_SOURCES chưa có 'DNSE'** — sẽ raise ValueError.
3. **Trade cũ (JWT-based) và DNSEClient (HMAC-based) chưa được bridge** — hai luồng auth chạy song song, user phải biết dùng cái nào.
4. **`_to_dataframe` trong client.py thiếu key** `bars`, `candles`, `trades`, `instruments` — OHLC/market data bị trả về dict thô thay vì DataFrame.
5. **Không có `.env.dnse.example`** đầy đủ cho người mới vào.
6. **Không có test cho explorer/dnse** (vì chưa tạo).

---

## 2. Mục tiêu tích hợp

Sau khi hoàn tất, người dùng có thể:

```python
# Cách 1: Giao diện thống nhất vnbroker (Market Data, cần API key DNSE)
from vnbroker import vnbroker
stock = vnbroker()
vnm = stock.stock('VNM', source='DNSE',
                  api_key='your_key', api_secret='your_secret')
df = vnm.quote.history(start='2024-01-01', end='2024-12-31')
listing = vnm.listing.all_symbols()

# Cách 2: Trực tiếp qua DNSEClient (low-level, đầy đủ nhất)
from vnbroker.connector.dnse import DNSEClient
client = DNSEClient(api_key='...', api_secret='...')
client.get_ohlc(bar_type='D', query={'symbol': 'VNM', 'from': ..., 'to': ...})
client.get_accounts()
client.post_order(...)

# Cách 3: Tài khoản cá nhân — login bằng JWT rồi đặt lệnh
from vnbroker.connector.dnse import Trade
t = Trade()
t.login('username', 'password')
t.email_otp()
t.get_trading_token(otp='123456')
t.place_order(sub_account='...', symbol='VNM', side='buy', ...)
```

---

## 3. Phạm vi công việc (Scope)

### Scope A — Market Data Provider (tích hợp vào chuẩn vnbroker)

Mục tiêu: DNSE xuất hiện như một `source` bình đẳng với VCI, KBS, TCBS.

| # | Hạng mục | File tác động | Ghi chú |
|---|---|---|---|
| A1 | Tạo `vnbroker/explorer/dnse/quote.py` | Mới | Class `DNSEQuote` implement `history()`, `intraday()`, `price_depth()` |
| A2 | Tạo `vnbroker/explorer/dnse/listing.py` | Mới | Class `DNSEListing` implement `all_symbols()`, `symbols_by_exchange()`, `indices()` |
| A3 | Tạo `vnbroker/explorer/dnse/__init__.py` | Mới | Đăng ký vào `ProviderRegistry` với `source='dnse'` |
| A4 | Sửa `vnbroker/__init__.py` | Có sẵn | Thêm `from .explorer import dnse` vào `_ensure_explorer_modules_loaded()` |
| A5 | Sửa `vnbroker/common/client.py` | Có sẵn | Thêm `'DNSE'` vào `SUPPORTED_SOURCES`; xử lý kwargs `api_key`/`api_secret` cho DNSE trong `stock()` |
| A6 | Sửa `vnbroker/connector/dnse/client.py` | Có sẵn | Mở rộng `_to_dataframe` để nhận key `bars`, `candles`, `trades`, `instruments` |

### Scope B — Trading & Account API (tài khoản cá nhân)

Mục tiêu: Giữ `Trade` cũ (JWT) hoạt động, cải tiến chất lượng, thêm bridge sang OpenAPI.

| # | Hạng mục | File tác động | Ghi chú |
|---|---|---|---|
| B1 | Refactor `Trade` cũ: thay `print()` → `logger`, thêm proper error handling | `trade.py` | Không thay đổi public API |
| B2 | Thêm bridge method `as_openapi_client()` trong `Trade` | `trade.py` | Tái dùng `DNSEClient` sau khi có api_key/api_secret |
| B3 | Thêm `login_and_get_client()` helper | `trade.py` | Kết hợp JWT login + openapi client trong 1 bước |

### Scope C — Tests & Tooling

| # | Hạng mục | File tác động | Ghi chú |
|---|---|---|---|
| C1 | Unit test cho `DNSEQuote` | `tests/unit/explorer/dnse/test_quote.py` | Mock DNSEClient, test parse/transform |
| C2 | Unit test cho `DNSEListing` | `tests/unit/explorer/dnse/test_listing.py` | Mock DNSEClient |
| C3 | Integration test bổ sung cho explorer | `tests/integration/test_dnse_explorer.py` | Skip nếu thiếu env |
| C4 | Cập nhật `.env.dnse.example` | Root | Thêm hướng dẫn đủ 2 luồng |

---

## 4. Thiết kế chi tiết từng hạng mục

### A1 – `vnbroker/explorer/dnse/quote.py`

**Class:** `DNSEQuote(symbol, api_key, api_secret, show_log)`

**Init:** Nhận `api_key`/`api_secret` từ tham số hoặc env `DNSE_API_KEY`/`DNSE_API_SECRET`, khởi tạo `DNSEClient` nội bộ.

**Methods:**

| Method | Tham số | Output | Ánh xạ DNSE API |
|---|---|---|---|
| `history(symbol, start, end, interval)` | interval: `'1D','1W','1M','1H','1m','5m','15m','30m'` | `pd.DataFrame` cột `time,open,high,low,close,volume` | `/price/ohlc?type={bar}&symbol={sym}&from={ts}&to={ts}` |
| `intraday(symbol, page_size)` | page_size: số lệnh tối đa | `pd.DataFrame` cột `time,price,volume,side` | `/price/trades?symbol={sym}&limit={n}` |
| `price_depth(symbol)` | — | `pd.DataFrame` security definition | `/price/{sym}/secdef` |

**Interval mapping:**

```
'1m'→'1', '5m'→'5', '15m'→'15', '30m'→'30'
'1H'→'60', '1D'→'D', '1W'→'W', '1M'→'M'
```

**Chuẩn hóa output:**
- Timestamp Unix → `datetime64[ns]` naive (no tz)  
- Giá: `float64`  
- Volume: `Int64` (nullable)  
- Sắp xếp tăng dần theo `time`  

---

### A2 – `vnbroker/explorer/dnse/listing.py`

**Class:** `DNSEListing(api_key, api_secret, show_log)`

**Methods:**

| Method | Tham số | Output | Ánh xạ DNSE API |
|---|---|---|---|
| `all_symbols(show_log)` | — | DataFrame cột `symbol, organ_name, exchange, ...` | `/instruments?limit=2000` |
| `symbols_by_exchange(exchange)` | `'HOSE','HNX','UPCOM','ALL'` | DataFrame | `/instruments?marketId={exchange}&limit=2000` |
| `symbols_by_group(group)` | mã nhóm DNSE | DataFrame | `/instruments?securityGroupId={group}` |
| `indices(show_log)` | — | DataFrame danh sách chỉ số | `/instruments?indexName=all` (fallback: lọc type=INDEX) |

**Normalize columns:** `marketId→exchange`, `name→organ_name`, `securityGroupId→security_group`, `boardId→board_id`

---

### A3 – `vnbroker/explorer/dnse/__init__.py`

```python
from vnbroker.core.registry import ProviderRegistry
from .quote import DNSEQuote
from .listing import DNSEListing

ProviderRegistry.register("quote", "dnse", DNSEQuote)
ProviderRegistry.register("listing", "dnse", DNSEListing)
```

---

### A4 – Sửa `vnbroker/__init__.py`

Thêm `from .explorer import dnse` vào block `_ensure_explorer_modules_loaded()`.

```python
# Trước
from .explorer import vci, tcbs, msn, kbs, rss_cafef, rss_vneconomy

# Sau
from .explorer import vci, tcbs, msn, kbs, rss_cafef, rss_vneconomy, dnse
```

---

### A5 – Sửa `vnbroker/common/client.py`

**Thay đổi 1:** Thêm `'DNSE'` vào `SUPPORTED_SOURCES`.

```python
SUPPORTED_SOURCES = ["AUTO", "KBS", "VCI", "TCBS", "MSN", "DNSE"]
```

**Thay đổi 2:** `stock()` nhận thêm `api_key`/`api_secret` cho DNSE và truyền vào `StockComponents`.

```python
def stock(self, symbol=None, source=None,
          auth_token=None, api_key=None, api_secret=None,
          otp=None, openapi_base_url=None) -> StockComponents:
```

**Thay đổi 3:** Truyền `api_key`/`api_secret` vào `StockComponents` để nó có thể khởi tạo `DNSEQuote` / `DNSEListing`.

---

### A6 – Sửa `vnbroker/connector/dnse/client.py`

Mở rộng `_to_dataframe` nhận thêm các key market data:

```python
for key in (
    "data", "items", "orders", "accounts", "loanPackages",
    "positions", "reports",
    # Market data
    "bars", "candles", "ohlc", "trades", "instruments", "securities",
):
```

---

### B1 – Refactor `Trade` cũ

- Thay toàn bộ `print(...)` → `logger.info(...)` / `logger.error(...)`  
- Bọc HTTP call trong try/except, raise `DNSETransportError` thay vì trả `None` im lặng  
- Không thay đổi tên method, không thay đổi tham số công khai  

---

### B2/B3 – Bridge method trong `Trade`

```python
def as_openapi_client(self, api_key: str, api_secret: str) -> DNSEClient:
    """Trả về DNSEClient (HMAC signed) để dùng Market Data và Order API chuẩn."""
    ...

def login_and_get_trading_session(
    self, username, password, otp_type='email', api_key=None, api_secret=None
) -> dict:
    """Đăng nhập JWT, lấy trading token, tuỳ chọn trả kèm DNSEClient."""
    ...
```

---

### C1–C4 – Tests

**`tests/unit/explorer/dnse/test_quote.py`:**
- Mock `DNSEClient._market.get_ohlc` trả về fixture OHLC bars list
- Test `history()` chuẩn hóa cột, dtype, sort
- Mock `get_trades` → test `intraday()`
- Test `price_depth()` với body dict và list
- Test raise `ValueError` khi thiếu api_key

**`tests/unit/explorer/dnse/test_listing.py`:**
- Mock `get_instruments` → test `all_symbols()`, `symbols_by_exchange()`, `indices()`

**`tests/integration/test_dnse_explorer.py`:**
- Skip khi thiếu `DNSE_API_KEY`
- Chạy `history()` với symbol `VNM` 30 ngày gần nhất
- Validate schema DataFrame output

---

## 5. Thứ tự thực hiện (Slices)

| Slice | Hạng mục | Độ ưu tiên | Ước tính |
|---|---|---|---|
| S1 | A6 (client.py `_to_dataframe`) | P0 – prerequisite | 10 phút |
| S2 | A1 (explorer/dnse/quote.py) | P0 | 30 phút |
| S3 | A2 (explorer/dnse/listing.py) | P0 | 20 phút |
| S4 | A3 (explorer/dnse/__init__.py) | P0 | 5 phút |
| S5 | A4 (vnbroker/__init__.py) | P0 | 5 phút |
| S6 | A5 (common/client.py SUPPORTED_SOURCES + kwargs) | P0 | 15 phút |
| S7 | B1 (Trade refactor print→logger) | P1 | 20 phút |
| S8 | B2/B3 (Trade bridge methods) | P1 | 20 phút |
| S9 | C1–C2 (unit tests explorer) | P1 | 30 phút |
| S10 | C3 (integration test explorer) | P2 | 20 phút |
| S11 | C4 (.env.dnse.example cập nhật) | P2 | 5 phút |

**Tổng ước tính:** ~3 giờ code + test

---

## 6. Những gì KHÔNG làm trong scope này

- Không triển khai WebSocket / streaming real-time (thuộc DNSE SSE/WebSocket — scope tương lai)
- Không tích hợp DNSE vào `source='AUTO'` — DNSE cần auth nên không thể là open candidate
- Không thay đổi DNSE core/services/client đã hoàn thiện
- Không đổi tên method public của `Trade` cũ (backward compat)
- Không tạo Company/Financial/Screener cho DNSE (API DNSE không cung cấp data này)

---

## 7. Điều kiện dừng (Done criteria)

- [ ] `Quote(source='dnse', symbol='VNM', api_key=..., api_secret=...).history(start='2024-01-01')` trả DataFrame đúng schema
- [ ] `vnbroker().stock('VNM', source='DNSE', api_key=..., api_secret=...).quote.history(...)` hoạt động
- [ ] `DNSEClient(...).get_ohlc(...)` trả DataFrame (không trả dict)
- [ ] `Trade().login(...)` dùng logger thay print
- [ ] Unit tests Scope C pass 100%
- [ ] Integration test skip sạch khi thiếu env

---

## 8. Rủi ro & Kiểm soát

| Rủi ro | Xác suất | Tác động | Kiểm soát |
|---|---|---|---|
| DNSE API trả key khác với mock (`bars` vs `data`) | Cao | Trung bình | `_extract_ohlc_list` thử nhiều key; kiểm bằng dry_run trước |
| `StockComponents` không nhận `api_key`/`api_secret` | Trung bình | Cao | Đọc `common/data.py` trước khi sửa A5 |
| DNSE auth HMAC không khớp (signature 401) | Thấp | Cao | Đã có unit test signature; dùng dry_run verify header |
| Break compat với TCBS/VCI khi sửa `stock()` | Thấp | Cao | Chỉ thêm optional kwargs, không xoá tham số cũ |

---

## 9. Checklist trước khi merge

- [ ] Không hardcode api_key/secret trong bất kỳ file nào
- [ ] Không có `print()` mới trong business logic
- [ ] Unit tests pass: `pytest tests/unit/connector/dnse tests/unit/explorer/dnse -v`
- [ ] Import không gây circular: `python -c "from vnbroker import vnbroker"`
- [ ] `.env.dnse.example` có đủ hướng dẫn 2 luồng (HMAC OpenAPI + JWT Trading)
