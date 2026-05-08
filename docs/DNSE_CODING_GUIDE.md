# DNSE Explorer — Hướng dẫn coding & Ví dụ mẫu
**Phiên bản:** 1.0  
**Ngày duyệt:** 2026-05-07  
**Áp dụng cho:** Đội dev khi viết code Scope A–B trong `DNSE_INTEGRATION_PLAN_20260507.md`

---

## 1. Thứ tự thực hiện bắt buộc

Thực hiện **đúng thứ tự sau**. Bước sau phụ thuộc bước trước.

```
S1: Sửa connector/dnse/client.py (_to_dataframe)          [5 phút]
S2: Tạo explorer/dnse/quote.py                             [30 phút]
S3: Tạo explorer/dnse/listing.py                           [20 phút]
S4: Tạo explorer/dnse/__init__.py                          [5 phút]
S5: Sửa vnstock/__init__.py (lazy load dnse)               [5 phút]
S6: Sửa common/data.py (StockComponents + Quote + Listing) [20 phút]
S7: Sửa common/client.py (SUPPORTED_SOURCES + api_secret)  [10 phút]
S8: Sửa connector/dnse/trade.py (logger + bridge methods)  [20 phút]
```

Sau mỗi bước chạy quick smoke:
```powershell
python -c "from vnstock import Vnstock; print('import OK')"
```

---

## 2. Mẫu code chuẩn — quote.py

### 2.1 Đoạn `__init__` mẫu

```python
class DNSEQuote:
    def __init__(
        self,
        symbol: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        show_log: bool = False,
        **kwargs,                          # ← BẮT BUỘC để registry không lỗi
    ):
        from vnstock.connector.dnse.client import DNSEClient   # ← lazy import
        
        self.symbol = symbol.upper()
        self.show_log = show_log
        resolved_key    = api_key    or os.environ.get("DNSE_API_KEY", "")
        resolved_secret = api_secret or os.environ.get("DNSE_API_SECRET", "")
        
        if not resolved_key or not resolved_secret:
            raise ValueError(
                "DNSE cần api_key và api_secret. "
                "Cung cấp trực tiếp hoặc đặt biến môi trường "
                "DNSE_API_KEY và DNSE_API_SECRET. "
                "Đăng ký tại: https://developers.dnse.com.vn/"
            )
        
        self._client  = DNSEClient(
            api_key=resolved_key, api_secret=resolved_secret, show_log=show_log
        )
        self._market  = self._client._market
```

### 2.2 Đoạn `history` mẫu

```python
    def history(
        self,
        symbol: Optional[str] = None,
        start: str = "2024-01-01",
        end: Optional[str] = None,
        interval: str = "1D",
        **kwargs,
    ) -> pd.DataFrame:
        sym      = (symbol or self.symbol).upper()
        end      = end or datetime.now().strftime("%Y-%m-%d")
        bar_type = "STOCK"  # live DNSE history contract for equities
        from_ts  = _to_unix_seconds(start)
        to_ts    = _to_unix_seconds(end) + 86399
        
        try:
            _, body = self._market.get_ohlc(
                bar_type=bar_type,
                query={"symbol": sym, "from": from_ts, "to": to_ts},
            )
        except Exception as exc:
            logger.warning("DNSE get_ohlc lỗi: %s", exc)
            return pd.DataFrame(
                columns=["time", "open", "high", "low", "close", "volume"]
            )
        
        df = _parse_ohlc(_extract_ohlc_list(body))
        if self.show_log:
            logger.info("DNSE history: %d rows, %s %s→%s", len(df), sym, start, end)
        return df
```

---

## 3. Mẫu code chuẩn — `_parse_ohlc` helper

```python
def _parse_ohlc(records: list) -> pd.DataFrame:
    _EMPTY = pd.DataFrame(
        columns=["time", "open", "high", "low", "close", "volume"]
    )
    if not records:
        return _EMPTY
    
    df = pd.json_normalize(records)
    
    # Rename — chỉ rename cột tồn tại
    rename_map = {k: v for k, v in _OHLC_COLUMN_MAP.items() if k in df.columns}
    df.rename(columns=rename_map, inplace=True)
    
    # Convert time
    if "time" in df.columns:
        if pd.api.types.is_numeric_dtype(df["time"]):
            df["time"] = (
                pd.to_datetime(df["time"], unit="s", utc=True)
                .dt.tz_localize(None)
            )
        else:
            df["time"] = pd.to_datetime(df["time"], errors="coerce")
    
    # Numeric casts
    for col in ("open", "high", "low", "close"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "volume" in df.columns:
        df["volume"] = (
            pd.to_numeric(df["volume"], errors="coerce").astype("Int64")
        )
    
    # Sort & giữ cột chuẩn
    if "time" in df.columns:
        df = df.sort_values("time").reset_index(drop=True)
    keep = [c for c in ("time","open","high","low","close","volume") if c in df.columns]
    return df[keep]
```

---

## 4. Mẫu code chuẩn — common/data.py (DNSE branch)

### 4.1 Thêm vào `StockComponents._initialize_components`

Tìm đoạn `elif self.source == 'FMP':` → thêm **sau** nó:

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
            self.trading  = None
            self.screener = None
            self.company  = None
            self.finance  = None
            self.news     = None
```

### 4.2 Thêm vào `Quote._load_data_source`

Tìm `module = importlib.import_module(self.source_module)` → thêm **trước** nó:

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

### 4.3 Thêm vào `Listing._load_data_source`

```python
        if self.source == "DNSE":
            from vnstock.explorer.dnse.listing import DNSEListing
            return DNSEListing(
                api_key=getattr(self, "api_key", None),
                api_secret=getattr(self, "api_secret", None),
                show_log=False,
            )
```

---

## 5. Mẫu code chuẩn — trade.py (logger replacement)

### 5.1 Thêm ở đầu file (sau existing imports)

```python
from vnstock.core.utils.logger import get_logger
logger = get_logger(__name__)
```

### 5.2 Bảng thay thế print → logger

| Print cũ | Logger mới |
|---|---|
| `print('Login successfully')` | `logger.info("Đăng nhập DNSE thành công")` |
| `print(f'Login failed: {response.text}')` | `logger.error("Đăng nhập DNSE thất bại: %s", response.text)` |
| `print('Get profile successfully')` | `logger.info("Lấy thông tin tài khoản thành công")` |
| `print(f'Get profile failed: {response.text}')` | `logger.error("Lấy thông tin tài khoản thất bại: %s", response.text)` |
| `print(f"Error: {response.text}")` | `logger.error("DNSE API lỗi: %s", response.text)` |
| `print("OTP sent to email")` | `logger.info("OTP đã được gửi tới email")` |
| `print("Authenticated! Trading token returned.")` | `logger.info("Đã xác thực, nhận trading token")` |
| `print(f"Error authenticating: {response.text}")` | `logger.error("Xác thực thất bại: %s", response.text)` |
| `print('Order list retrieved')` | `logger.info("Lấy danh sách lệnh thành công")` |
| `print("Order cancelled")` | `logger.info("Huỷ lệnh thành công")` |
| `print('Deals list retrieved')` | `logger.info("Lấy danh sách khớp lệnh thành công")` |
| `print('Get profile successfully')` | `logger.info("Lấy hồ sơ thành công")` |

---

## 6. Cách kiểm tra từng bước (smoke test inline)

### Sau S1 (client.py _to_dataframe)

```python
from vnstock.connector.dnse.client import DNSEClient
import inspect
src = inspect.getsource(DNSEClient._to_dataframe)
assert "bars" in src, "FAIL: thiếu key 'bars'"
print("S1 PASS")
```

### Sau S4 (__init__.py)

```python
from vnstock.explorer.dnse import DNSEQuote, DNSEListing
from vnstock.core.registry import ProviderRegistry
assert ProviderRegistry.is_registered("quote", "dnse"), "FAIL: quote/dnse chưa register"
assert ProviderRegistry.is_registered("listing", "dnse"), "FAIL: listing/dnse chưa register"
print("S4 PASS")
```

### Sau S5 (vnstock/__init__.py)

```python
from vnstock import _ensure_explorer_modules_loaded
_ensure_explorer_modules_loaded()
from vnstock.core.registry import ProviderRegistry
all_prov = ProviderRegistry.list_all()
assert "dnse" in all_prov.get("quote", []), "FAIL: dnse chưa load"
print("S5 PASS")
```

### Sau S7 (common/client.py)

```python
from vnstock.common.client import Vnstock
assert "DNSE" in Vnstock.SUPPORTED_SOURCES, "FAIL"
from vnstock.common.data import StockComponents, Quote, Listing
assert "DNSE" in StockComponents.SUPPORTED_SOURCES, "FAIL"
assert "DNSE" in Quote.SUPPORTED_SOURCES, "FAIL"
assert "DNSE" in Listing.SUPPORTED_SOURCES, "FAIL"
print("S7 PASS")
```

### Smoke cuối (toàn bộ flow — thiếu API key)

```python
import os
# Xoá env để test ValueError
os.environ.pop("DNSE_API_KEY", None)
os.environ.pop("DNSE_API_SECRET", None)

from vnstock.common.client import Vnstock
try:
    v = Vnstock()
    s = v.stock("VNM", source="DNSE")       # StockComponents khởi tạo OK
    df = s.quote.history(start="2024-01-01") # Chỉ tại đây mới gọi DNSEQuote.__init__
    print("FAIL: phải raise ValueError do thiếu key")
except ValueError as e:
    print("PASS — ValueError đúng lúc:", str(e)[:80])
```

---

## 7. Các lỗi thường gặp & cách xử lý

| Lỗi | Nguyên nhân | Cách sửa |
|---|---|---|
| `circular import` khi load `vnstock` | Import DNSE ở module level | Chuyển tất cả import DNSEClient/registry vào trong `__init__` của class |
| `ValueError: Provider 'quote/dnse' not found` | `ProviderRegistry.register` chưa chạy | Kiểm tra `vnstock/__init__.py` đã có `from .explorer import dnse` chưa |
| `DNSE get_trades lỗi: 404 page not found` | Live trades endpoint chưa ổn định trong smoke | `intraday()` trả empty DataFrame và chỉ log warning; không fail cứng |
| `KeyError: 'bars'` trong DataFrame | `_to_dataframe` cũ chưa có key `bars` | Kiểm tra S1 đã thực hiện chưa |
| `TypeError: __init__() got unexpected keyword argument 'api_key'` | Class chưa có `**kwargs` | Thêm `**kwargs` vào `__init__` signature |
| DNSE trả 401 | API key/secret sai hoặc chữ ký HMAC lỗi | Dùng `dry_run=True` để xem headers; kiểm tra `DNSEConfig` |
| `pd.DataFrame` thiếu cột `volume` | Response DNSE không trả `v` hoặc `volume` | Kiểm tra raw body bằng `raw=True`; mapping `_OHLC_COLUMN_MAP` |

---

## 8. Không làm — danh sách cấm

- ❌ Không sửa `core/`, `api/`, `explorer/vci/`, `explorer/tcbs/`, `explorer/kbs/`
- ❌ Không thêm DNSE vào `OPEN_SOURCE_CANDIDATES` trong `source_router.py` (DNSE cần auth)
- ❌ Không sửa `ProviderRegistry` class
- ❌ Không tạo `Company`, `Finance`, `Screener` cho DNSE trong scope này
- ❌ Không thay đổi tên hay signature bất kỳ method public nào của `Trade` cũ
- ❌ Không raise exception trong `history()`/`intraday()` khi lỗi mạng — chỉ log + trả empty

---

## 9. Checklist trước khi commit mỗi slice

```
□ python -c "from vnstock import Vnstock" không lỗi
□ pytest tests/unit/connector/dnse/ -v pass 100%  
□ Không có print() mới trong source code  
□ Không có hardcode api_key/secret  
□ Mọi public method có **kwargs  
□ Import DNSEClient trong __init__ của class (không ở module level)
```
