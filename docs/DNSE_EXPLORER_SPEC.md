# DNSE Explorer Layer — Đặc tả kỹ thuật chi tiết
**Phiên bản:** 1.0  
**Ngày duyệt:** 2026-05-07  
**Trạng thái:** ĐÃ DUYỆT — Đội code thực hiện theo tài liệu này, không được tự sửa phạm vi.

---

## 1. Mục đích

Tài liệu này định nghĩa **chính xác từng file, từng class, từng method, từng tham số, từng kiểu dữ liệu** của lớp explorer DNSE. Đội code đọc tài liệu này để viết code — không cần suy đoán thêm.

---

## 2. Cây file cần tạo/sửa

```
vnstock/
├── explorer/
│   └── dnse/                          ← MỚI HOÀN TOÀN
│       ├── __init__.py                ← Đăng ký ProviderRegistry
│       ├── quote.py                   ← DNSEQuote class
│       └── listing.py                 ← DNSEListing class
├── connector/
│   └── dnse/
│       ├── client.py                  ← SỬA: mở rộng _to_dataframe
│       └── trade.py                   ← SỬA: print→logger, thêm 2 method
├── common/
│   └── client.py                      ← SỬA: SUPPORTED_SOURCES, StockComponents
│       data.py                        ← SỬA: StockComponents + Quote + Listing
└── __init__.py                        ← SỬA: lazy load dnse explorer
```

---

## 3. File `vnstock/explorer/dnse/quote.py`

### 3.1 Import dependencies

```python
from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import Optional
import pandas as pd
from vnstock.core.utils.logger import get_logger

logger = get_logger(__name__)
```

### 3.2 Hằng số & mapping — KHÔNG được thay đổi giá trị

```python
_INTERVAL_TO_BAR_TYPE: dict[str, str] = {
    "1m":  "1",
    "5m":  "5",
    "15m": "15",
    "30m": "30",
    "1H":  "60",
    "1D":  "D",
    "1W":  "W",
    "1M":  "M",
}

_INTERVAL_ALIASES: dict[str, str] = {
    "d": "1D", "day": "1D", "daily": "1D",
    "w": "1W", "week": "1W", "weekly": "1W",
    "m": "1M", "month": "1M", "monthly": "1M",
    "h": "1H", "hour": "1H", "1h": "1H",
}

# Keys để tìm list OHLC trong response body — thử lần lượt
_OHLC_RESPONSE_KEYS = ("bars", "data", "items", "candles", "ohlc")

_OHLC_COLUMN_MAP: dict[str, str] = {
    "t": "time",   "time": "time",   "timestamp": "time",
    "o": "open",   "open": "open",
    "h": "high",   "high": "high",
    "l": "low",    "low": "low",
    "c": "close",  "close": "close",
    "v": "volume", "volume": "volume", "vol": "volume",
}

_TRADES_COLUMN_MAP: dict[str, str] = {
    "t": "time",   "time": "time",
    "p": "price",  "price": "price",
    "v": "volume", "volume": "volume", "q": "volume", "qty": "volume",
    "s": "side",   "side": "side",     "bs": "side",
}
```

### 3.3 Helper functions (module-level, không export)

#### `_normalize_interval(interval: str) -> str`
- Input: chuỗi bất kỳ.
- Lowercase + tra `_INTERVAL_ALIASES`. Nếu không tìm thấy, trả nguyên input.
- Ví dụ: `"daily"` → `"1D"`, `"1H"` → `"1H"`.

#### `_to_unix_seconds(date_str: str) -> int`
- Parse `"YYYY-MM-DD"` → Unix timestamp UTC (giây).
- Dùng `datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)`.
- Raise `ValueError` (từ strptime) nếu format sai — **không bắt exception**.

#### `_extract_ohlc_list(body: dict | list | None) -> list`
- Nếu `None` → trả `[]`.
- Nếu `list` → trả thẳng.
- Nếu `dict` → thử từng key trong `_OHLC_RESPONSE_KEYS`, trả list đầu tiên tìm thấy.
- Nếu không có → trả `[]`.

#### `_parse_ohlc(records: list) -> pd.DataFrame`
- `records = []` → trả `pd.DataFrame(columns=["time","open","high","low","close","volume"])`.
- `pd.json_normalize(records)`.
- Rename theo `_OHLC_COLUMN_MAP` (chỉ rename key có trong df.columns).
- Convert cột `time`:
  - Nếu numeric → `pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_localize(None)`.
  - Nếu string → `pd.to_datetime(df["time"], errors="coerce")`.
- Cast `open/high/low/close` → `float64` via `pd.to_numeric(..., errors="coerce")`.
- Cast `volume` → `Int64` (nullable) via `pd.to_numeric(..., errors="coerce").astype("Int64")`.
- Sort tăng dần theo `time`.
- Chỉ giữ cột trong `("time","open","high","low","close","volume")` nếu tồn tại.

#### `_parse_trades(records: list) -> pd.DataFrame`
- Tương tự `_parse_ohlc` nhưng dùng `_TRADES_COLUMN_MAP`.
- Output columns: `("time","price","volume","side")`.
- `price` → `float64`, `volume` → `Int64`, `side` → không cast.

---

### 3.4 Class `DNSEQuote`

#### 3.4.1 `__init__`

```python
def __init__(
    self,
    symbol: str,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    show_log: bool = False,
    **kwargs,          # bỏ qua kwargs thừa từ registry
):
```

**Logic:**
1. `self.symbol = symbol.upper()`
2. `self.show_log = show_log`
3. `resolved_key = api_key or os.environ.get("DNSE_API_KEY", "")`
4. `resolved_secret = api_secret or os.environ.get("DNSE_API_SECRET", "")`
5. Nếu `not resolved_key or not resolved_secret`:  
   Raise `ValueError` với message:  
   ```
   "DNSE cần api_key và api_secret. "
   "Cung cấp trực tiếp hoặc đặt biến môi trường DNSE_API_KEY và DNSE_API_SECRET. "
   "Đăng ký tại: https://developers.dnse.com.vn/"
   ```
6. Import lazy (tránh circular):  
   ```python
   from vnstock.connector.dnse.client import DNSEClient
   ```
7. `self._client = DNSEClient(api_key=resolved_key, api_secret=resolved_secret, show_log=show_log)`
8. `self._market = self._client._market`

#### 3.4.2 `history`

```python
def history(
    self,
    symbol: Optional[str] = None,
    start: str = "2024-01-01",
    end: Optional[str] = None,
    interval: str = "1D",
    **kwargs,
) -> pd.DataFrame:
```

**Logic:**
1. `sym = (symbol or self.symbol).upper()`
2. `end = end or datetime.now().strftime("%Y-%m-%d")`
3. `norm_interval = _normalize_interval(interval)`
4. `bar_type = "STOCK"`  # live DNSE history contract for equities
5. `from_ts = _to_unix_seconds(start)`
6. `to_ts = _to_unix_seconds(end) + 86399`  ← đến cuối ngày end
7. `query = {"symbol": sym, "from": from_ts, "to": to_ts}`
8. Gọi `_, body = self._market.get_ohlc(bar_type=bar_type, query=query)` trong try/except:
   - Nếu lỗi: `logger.warning("DNSE get_ohlc lỗi: %s", exc)`, trả `pd.DataFrame(columns=[...])`
9. `records = _extract_ohlc_list(body)`
10. `df = _parse_ohlc(records)`
11. Nếu `self.show_log`: `logger.info("DNSE history: %d rows, %s, %s→%s", len(df), sym, start, end)`
12. Trả `df`

> Ghi chú contract live: `_extract_ohlc_list` phải chấp nhận cả body là list lẫn body là một dict top-level có `t/o/h/l/c/v` rồi wrap thành một record.

**Schema output bắt buộc:**

| Cột | Dtype | Ghi chú |
|---|---|---|
| time | datetime64[ns] | UTC naive (không có tz) |
| open | float64 | Đơn vị: đồng VNĐ (không nhân/chia) |
| high | float64 | |
| low | float64 | |
| close | float64 | |
| volume | Int64 | Nullable integer |

#### 3.4.3 `intraday`

```python
def intraday(
    self,
    symbol: Optional[str] = None,
    page_size: int = 100,
    **kwargs,
) -> pd.DataFrame:
```

**Logic:**
1. `sym = (symbol or self.symbol).upper()`
2. Gọi `_, body = self._market.get_trades(symbol=sym, limit=page_size)` trong try/except.
3. Nếu `body is None`: trả empty DataFrame.
4. Tìm list trades trong body: thử keys `("trades","data","items")`, fallback = body nếu là list.
5. `df = _parse_trades(records)`
6. Trả `df`

> Ghi chú contract live: smoke hiện tại trả 404 page not found cho `get_trades`, nên `intraday()` được xem là best-effort và phải log warning rồi trả empty DataFrame khi endpoint chưa ổn định.

**Schema output:**

| Cột | Dtype | Ghi chú |
|---|---|---|
| time | datetime64[ns] | UTC naive |
| price | float64 | |
| volume | Int64 | |
| side | object | "B"/"S" hoặc "BUY"/"SELL" — không chuẩn hoá thêm |

#### 3.4.4 `price_depth`

```python
def price_depth(
    self,
    symbol: Optional[str] = None,
    **kwargs,
) -> pd.DataFrame:
```

**Logic:**
1. `sym = (symbol or self.symbol).upper()`
2. Gọi `_, body = self._market.get_security_definition(symbol=sym)` trong try/except.
3. Nếu `body is None` → trả `pd.DataFrame()`.
4. Nếu `dict` → `pd.json_normalize(body)`.
5. Nếu `list` → `pd.json_normalize(body)`.
6. Trả `df`.

> **Lưu ý:** `price_depth` trong context DNSE trả security definition (thông tin chứng khoán), không phải order book. Live smoke quan sát được body dạng list[dict], nên DataFrame thường có nhiều dòng sau normalization. Đây là hành vi dự kiến — không cần thêm logic khác.

---

## 4. File `vnstock/explorer/dnse/listing.py`

### 4.1 Import dependencies

Giống quote.py, thêm `from vnstock.connector.dnse.client import DNSEClient` (lazy trong `__init__`).

### 4.2 Hằng số

```python
_INSTRUMENT_COLUMN_MAP: dict[str, str] = {
    "symbol":          "symbol",
    "marketId":        "exchange",
    "market_id":       "exchange",
    "securityGroupId": "security_group",
    "security_group_id": "security_group",
    "name":            "organ_name",
    "shortName":       "short_name",
    "short_name":      "short_name",
    "boardId":         "board_id",
    "board_id":        "board_id",
    "type":            "type",
    "status":          "status",
    "lot":             "lot_size",
    "lotSize":         "lot_size",
}
```

### 4.3 Class `DNSEListing`

#### 4.3.1 `__init__`

```python
def __init__(
    self,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    show_log: bool = False,
    **kwargs,
):
```

**Logic:** Tương tự `DNSEQuote.__init__` — resolve credentials, raise `ValueError` nếu thiếu, tạo `DNSEClient`, lưu `self._market = self._client._market`.

> **Khác biệt:** Không nhận `symbol` (listing không cần symbol).

#### 4.3.2 Private helper `_fetch_instruments`

```python
def _fetch_instruments(
    self,
    market_id: Optional[str] = None,
    security_group_id: Optional[str] = None,
    limit: int = 2000,
) -> pd.DataFrame:
```

**Logic:**
1. Gọi `_, body = self._market.get_instruments(market_id=market_id, security_group_id=security_group_id, limit=limit)` trong try/except.
2. Tìm list trong body: thử keys `("instruments","data","items","securities")`.
3. Fallback: nếu body là `dict` không chứa list → `records = [body]`.
4. `pd.json_normalize(records)`.
5. Rename theo `_INSTRUMENT_COLUMN_MAP`.
6. Trả `df` (có thể empty).

#### 4.3.3 Public methods

| Method | Tham số | Logic | DNSE API call |
|---|---|---|---|
| `all_symbols(show_log)` | — | Gọi `_fetch_instruments()` | `/instruments?limit=1000` |
| `symbols_by_exchange(exchange, show_log)` | `'HOSE'/'HNX'/'UPCOM'/'ALL'` | `market_id=None` nếu `ALL`, ngược lại `market_id=exchange.upper()` | `/instruments?marketId={exchange}&limit=1000` |
| `symbols_by_group(group, show_log)` | mã nhóm DNSE | `_fetch_instruments(security_group_id=group)` | `/instruments?securityGroupId={group}&limit=1000` |
| `indices(show_log)` | — | Gọi `get_instruments(index_name="all")`, fallback lọc `type==INDEX` từ all_symbols | `/instruments?indexName=all&limit=1000` |

**Tất cả public methods đều:**
- Gọi `reset_index(drop=True)` trước khi return.
- Log nếu `show_log or self.show_log`.

---

## 5. File `vnstock/explorer/dnse/__init__.py`

```python
"""
vnstock/explorer/dnse/__init__.py
Đăng ký DNSE explorer providers vào ProviderRegistry của vnstock.
"""
from vnstock.core.registry import ProviderRegistry
from .quote import DNSEQuote
from .listing import DNSEListing

ProviderRegistry.register("quote",   "dnse", DNSEQuote)
ProviderRegistry.register("listing", "dnse", DNSEListing)

__all__ = ["DNSEQuote", "DNSEListing"]
```

> **QUAN TRỌNG:** Không import thêm gì khác. Không tạo instance.  
> Registry.register() dùng key `(provider_type, source_name_lower)` — đảm bảo `"dnse"` viết thường.

---

## 6. Sửa `vnstock/connector/dnse/client.py`

### Chỉ thay đổi duy nhất: method `_to_dataframe`

**Thay đổi:** Thêm 5 key market-data vào tuple tìm list.

```python
# TRƯỚC
for key in ("data", "items", "orders", "accounts", "loanPackages", "positions", "reports"):

# SAU
for key in (
    "data", "items", "orders", "accounts", "loanPackages",
    "positions", "reports",
    "bars", "candles", "ohlc", "trades", "instruments", "securities",
):
```

Không sửa gì khác trong file này.

---

## 7. Sửa `vnstock/__init__.py`

### Chỉ thay đổi duy nhất: thêm `dnse` vào lazy load

```python
# TRƯỚC (trong _ensure_explorer_modules_loaded)
from .explorer import vci, tcbs, msn, kbs, rss_cafef, rss_vneconomy  # noqa: F401

# SAU
from .explorer import vci, tcbs, msn, kbs, rss_cafef, rss_vneconomy  # noqa: F401
from .explorer import dnse  # noqa: F401  – DNSE provider registration
```

Không sửa gì khác trong file này.

---

## 8. Sửa `vnstock/common/data.py`

### 8.1 Thêm DNSE vào `StockComponents.SUPPORTED_SOURCES`

```python
# TRƯỚC
class StockComponents(BaseComponent):
    SUPPORTED_SOURCES = ["AUTO", "KBS", "VCI", "TCBS", "MSN", "FMP"]

# SAU
class StockComponents(BaseComponent):
    SUPPORTED_SOURCES = ["AUTO", "KBS", "VCI", "TCBS", "MSN", "FMP", "DNSE"]
```

### 8.2 Thêm tham số `api_key`/`api_secret` vào `StockComponents.__init__`

```python
# TRƯỚC
def __init__(self, symbol: str, source: str = Config.DEFAULT_SOURCE,
             show_log: bool = True,
             auth_token: Optional[str] = None):
    self.auth_token = auth_token
    super().__init__(symbol, source)

# SAU
def __init__(self, symbol: str, source: str = Config.DEFAULT_SOURCE,
             show_log: bool = True,
             auth_token: Optional[str] = None,
             api_key: Optional[str] = None,
             api_secret: Optional[str] = None):
    self.auth_token = auth_token
    self.api_key = api_key
    self.api_secret = api_secret
    super().__init__(symbol, source)
```

### 8.3 Thêm branch DNSE vào `_initialize_components`

Thêm vào cuối block `elif` trong `_initialize_components`:

```python
elif self.source == 'DNSE':
    from vnstock.api.quote import Quote as QuoteAdapter
    from vnstock.api.listing import Listing as ListingAdapter
    self.quote = QuoteAdapter(
        source='dnse',
        symbol=self.symbol,
        show_log=False,
        api_key=self.api_key,
        api_secret=self.api_secret,
    )
    self.listing = ListingAdapter(
        source='dnse',
        show_log=False,
        api_key=self.api_key,
        api_secret=self.api_secret,
    )
    self.trading = None
    self.screener = None
    self.company = None
    self.finance = None
    self.news = None
```

### 8.4 Thêm DNSE vào `Quote.SUPPORTED_SOURCES` và `Listing.SUPPORTED_SOURCES`

```python
# Quote class
class Quote(BaseComponent):
    SUPPORTED_SOURCES = ["AUTO", "KBS", "VCI", "TCBS", "MSN", "FMP", "DNSE"]

# Listing class
class Listing(BaseComponent):
    SUPPORTED_SOURCES = ["AUTO", "KBS", "VCI", "MSN", "FMP", "DNSE"]
```

### 8.5 Thêm DNSE vào `Quote._load_data_source`

Thêm branch trước `module = importlib.import_module(...)`:

```python
if self.source == "DNSE":
    from vnstock.explorer.dnse.quote import DNSEQuote
    return DNSEQuote(
        symbol=self.symbol,
        api_key=getattr(self, "api_key", None),
        api_secret=getattr(self, "api_secret", None),
        show_log=False,
    )
```

Và trong `__init__` của `Quote` class, lưu `api_key`/`api_secret`:

```python
def __init__(self, symbol: str, source: str = Config.DEFAULT_SOURCE,
             auth_token: Optional[str] = None,
             api_key: Optional[str] = None,
             api_secret: Optional[str] = None):
    self.auth_token = auth_token
    self.api_key = api_key
    self.api_secret = api_secret
    super().__init__(symbol, source)
```

### 8.6 Thêm DNSE vào `Listing._load_data_source`

Thêm branch trước `module = importlib.import_module(...)`:

```python
if self.source == "DNSE":
    from vnstock.explorer.dnse.listing import DNSEListing
    return DNSEListing(
        api_key=getattr(self, "api_key", None),
        api_secret=getattr(self, "api_secret", None),
        show_log=False,
    )
```

Và trong `__init__` của `Listing` class:

```python
def __init__(self, source: str = Config.DEFAULT_SOURCE,
             api_key: Optional[str] = None,
             api_secret: Optional[str] = None,
             show_log: bool = False):
    self.api_key = api_key
    self.api_secret = api_secret
    super().__init__(symbol=None, source=source)
```

---

## 9. Sửa `vnstock/common/client.py`

### 9.1 Thêm DNSE vào `Vnstock.SUPPORTED_SOURCES`

```python
# TRƯỚC
SUPPORTED_SOURCES = ["AUTO", "KBS", "VCI", "TCBS", "MSN"]

# SAU
SUPPORTED_SOURCES = ["AUTO", "KBS", "VCI", "TCBS", "MSN", "DNSE"]
```

### 9.2 Thêm `api_key`/`api_secret` vào `Vnstock.stock()`

```python
# TRƯỚC
def stock(self, symbol=None, source=None, auth_token=None,
          api_key=None, otp=None, openapi_base_url=None) -> StockComponents:

# SAU
def stock(self, symbol=None, source=None, auth_token=None,
          api_key=None, api_secret=None,     # ← thêm api_secret
          otp=None, openapi_base_url=None) -> StockComponents:
```

### 9.3 Truyền `api_secret` vào `StockComponents`

```python
# TRƯỚC
return StockComponents(self.symbol, source, show_log=self.show_log, auth_token=auth_token)

# SAU
return StockComponents(
    self.symbol, source,
    show_log=self.show_log,
    auth_token=auth_token,
    api_key=api_key,
    api_secret=api_secret,
)
```

---

## 10. Sửa `vnstock/connector/dnse/trade.py`

### 10.1 Thay `print()` → `logger`

Thêm import ở đầu file:
```python
from vnstock.core.utils.logger import get_logger
logger = get_logger(__name__)
```

Thay thế:
- `print('Login successfully')` → `logger.info("Đăng nhập DNSE thành công")`
- `print(f'Login failed: {response.text}')` → `logger.error("Đăng nhập DNSE thất bại: %s", response.text)`
- `print('Get profile successfully')` → `logger.info("Lấy thông tin tài khoản thành công")`
- `print(f'...')` trong tất cả methods → `logger.info(...)` hoặc `logger.error(...)` tương ứng
- `print("OTP sent to email")` → `logger.info("OTP đã được gửi tới email")`
- `print("Authenticated! Trading token returned.")` → `logger.info("Đã xác thực, nhận trading token")`

Quy tắc: success → `logger.info`, failure → `logger.error`, không dùng `logger.warning` trừ khi logic là "có thể bỏ qua".

### 10.2 Thêm method `as_openapi_client`

```python
def as_openapi_client(
    self,
    api_key: str,
    api_secret: str,
) -> "DNSEClient":
    """
    Tạo và trả về DNSEClient (HMAC-signed) để dùng Market Data và Order API chuẩn.

    Tham số:
        api_key (str): DNSE OpenAPI key.
        api_secret (str): DNSE OpenAPI secret.

    Trả về:
        DNSEClient: Client đã được khởi tạo.

    Ví dụ:
        t = Trade()
        t.login('username', 'password')
        client = t.as_openapi_client(api_key='...', api_secret='...')
        client.get_accounts()
    """
    return DNSEClient(api_key=api_key, api_secret=api_secret)
```

### 10.3 Thêm method `login_and_get_trading_session`

```python
def login_and_get_trading_session(
    self,
    username: str,
    password: str,
    otp: str,
    smart_otp: bool = True,
) -> dict:
    """
    Đăng nhập JWT và lấy trading token trong một bước.

    Tham số:
        username (str): Tên đăng nhập DNSE (mã lưu ký, email, hoặc số điện thoại).
        password (str): Mật khẩu DNSE.
        otp (str): OTP từ email (gọi email_otp() trước để nhận OTP).
        smart_otp (bool): True nếu dùng Smart OTP. Mặc định True.

    Trả về:
        dict với keys:
            - "token" (str): JWT bearer token.
            - "trading_token" (str | None): Trading token (None nếu OTP sai).
            - "success" (bool): True nếu cả hai bước đều thành công.

    Ví dụ:
        t = Trade()
        # Bước 0: gọi email_otp() trước để nhận OTP
        session = t.login_and_get_trading_session(
            username='0001XXXXX',
            password='mypassword',
            otp='123456',
        )
        if session['success']:
            # Tiến hành giao dịch
            t.place_order(...)
    """
    token = self.login(username, password)
    if not token:
        return {"token": None, "trading_token": None, "success": False}

    trading_token = self.get_trading_token(otp=otp, smart_otp=smart_otp)
    return {
        "token": token,
        "trading_token": trading_token,
        "success": trading_token is not None,
    }
```

---

## 11. Quy tắc chung khi code

1. **Không hardcode** `api_key`, `api_secret`, `username`, `password` trong bất kỳ file source nào.
2. **Không `print()`** trong business logic — chỉ dùng `logger`.
3. **Không raise exception** trong `history()` / `intraday()` / `price_depth()` khi lỗi API — log warning và trả empty DataFrame.
4. **Raise `ValueError`** sớm trong `__init__` khi thiếu credentials.
5. **Import lazy** tất cả DNSE dependencies trong `__init__` của class (không ở module level) để tránh circular import.
6. **`**kwargs`** trong mọi `__init__` để registry có thể truyền tham số dư mà không báo lỗi.
7. **Không sửa** file ngoài danh sách Section 2 — đặc biệt không sửa core/, api/, hay explorer/vci/ v.v.

---

## 12. Xác nhận Done Criteria

Sau khi code xong, chạy lệnh sau — tất cả phải pass:

```python
# Kiểm tra 1: Import không lỗi
python -c "from vnstock import Vnstock; print('OK')"

# Kiểm tra 2: DNSE có trong registry
python -c "
from vnstock import _ensure_explorer_modules_loaded
_ensure_explorer_modules_loaded()
from vnstock.core.registry import ProviderRegistry
print(ProviderRegistry.list_all())
# Phải thấy 'dnse' trong quote và listing
"

# Kiểm tra 3: Quote DNSE khởi tạo đúng (thiếu key phải raise ValueError)
python -c "
import os; os.environ.pop('DNSE_API_KEY', None); os.environ.pop('DNSE_API_SECRET', None)
from vnstock.explorer.dnse.quote import DNSEQuote
try:
    q = DNSEQuote('VNM')
    print('FAIL: phải raise ValueError')
except ValueError as e:
    print('PASS:', str(e)[:60])
"

# Kiểm tra 4: Vnstock nhận DNSE
python -c "
from vnstock.common.client import Vnstock
v = Vnstock()
print('SUPPORTED_SOURCES:', v.SUPPORTED_SOURCES)
assert 'DNSE' in v.SUPPORTED_SOURCES, 'DNSE phải có trong SUPPORTED_SOURCES'
print('PASS')
"
```
