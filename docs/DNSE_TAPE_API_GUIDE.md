# DNSE Tape / Intraday API — Hướng dẫn lập trình viên

> **Cập nhật:** 2026-05-19 — Fix endpoint path, column mapping, page_size limit sau integration test thực tế

---

## Tổng quan

`DNSEQuote.intraday()` gọi endpoint `GET /price/{symbol}/trades` của DNSE LightSpeed OpenAPI.  
Hàm hỗ trợ cả **tape phiên hiện tại** lẫn **tape lịch sử nhiều ngày** với cursor pagination tự động.

> **Lưu ý:** Endpoint yêu cầu tham số `from` (Unix timestamp). Khi không truyền `date`/`start`, hàm tự động dùng boundary của ngày hôm nay (giờ VN).

---

## Chữ ký hàm

```python
def intraday(
    self,
    symbol: str | None = None,
    date: str | None = None,        # 'YYYY-MM-DD' — tape 1 ngày
    start: str | None = None,       # 'YYYY-MM-DD' — từ ngày
    end: str | None = None,         # 'YYYY-MM-DD' — đến ngày (mặc định: hôm nay)
    page_size: int | None = None,   # mặc định 1000 khi có date/start, 100 cho live; hard cap 1000
    get_all: bool = False,          # True → tự phân trang qua nextPageToken
    order: str = "asc",             # 'asc' hoặc 'desc'
    show_log: bool | None = None,
    **kwargs,
) -> pd.DataFrame
```

### Tham số chi tiết

| Tham số | Kiểu | Mô tả |
|---|---|---|
| `symbol` | `str` | Mã CK (ví dụ: `"ACB"`). Mặc định dùng symbol khởi tạo. |
| `date` | `str` | Ngày cụ thể `YYYY-MM-DD`. Lấy tape từ `00:00` đến `23:59` giờ VN (UTC+7). |
| `start` | `str` | Ngày bắt đầu của khoảng nhiều ngày. |
| `end` | `str` | Ngày kết thúc. Bỏ qua → mặc định là hôm nay. |
| `page_size` | `int` | Số lệnh tối đa mỗi request. Tự động `1000` khi có `date`/`start`; `100` khi live. **Giới hạn tối đa của DNSE: 1000.** |
| `get_all` | `bool` | `True` → tự động follow `nextPageToken` để lấy toàn bộ dữ liệu. |
| `order` | `str` | `"asc"` (cũ→mới) hoặc `"desc"` (mới→cũ). |
| `show_log` | `bool` | Ghi log số record. Mặc định kế thừa từ `__init__`. |

### Giá trị trả về

`pd.DataFrame` với các cột: `time`, `price`, `volume`, `side`

---

## Ví dụ sử dụng

### Truy cập qua `DNSEQuote` (explorer layer)

```python
from vnbroker.explorer.dnse.quote import DNSEQuote

q = DNSEQuote("ACB", api_key="your_key", api_secret="your_secret")

# 1. Tape phiên hiện tại — 100 lệnh gần nhất (backward compat)
df = q.intraday()

# 2. Toàn bộ tape ngày 2026-05-15
df = q.intraday(date="2026-05-15", get_all=True)

# 3. Tape ngày 2026-05-15, chỉ lấy 200 lệnh đầu (không phân trang)
df = q.intraday(date="2026-05-15", page_size=200)

# 4. Tape từ 2026-05-12 đến 2026-05-16 (toàn bộ)
df = q.intraday(start="2026-05-12", end="2026-05-16", get_all=True)

# 5. Tape từ 2026-05-01 đến hôm nay
df = q.intraday(start="2026-05-01", get_all=True)

# 6. Sắp xếp mới → cũ (desc)
df = q.intraday(date="2026-05-15", get_all=True, order="desc")

print(df.head())
print(df.dtypes)
```

### Truy cập qua `Quote` (public API layer)

```python
from vnbroker.api.quote import Quote

# Mọi tham số của intraday() đều được forward qua **kwargs
q = Quote("ACB", source="dnse", api_key="your_key", api_secret="your_secret")

df = q.intraday(date="2026-05-15", get_all=True)
df = q.intraday(start="2026-05-12", end="2026-05-16", get_all=True)
```

### Truy cập qua `Vnbroker` (client thống nhất)

```python
from vnbroker import Vnbroker

broker = Vnbroker(source="dnse", api_key="your_key", api_secret="your_secret")
acb = broker.stock("ACB")

df = acb.quote.intraday(date="2026-05-15", get_all=True)
```

---

## Luồng xử lý nội bộ

```
intraday(date="2026-05-15", get_all=True)
  │
  ├─ _to_vn_day_bounds("2026-05-15")
  │    └─ Trả về (from_ts, to_ts) Unix seconds theo UTC+7
  │         → from_ts = 1778778000  (2026-05-15 00:00:00+07:00)
  │         → to_ts   = 1778864399  (2026-05-15 23:59:59+07:00)
  │
  ├─ page_size = 1000 (auto, hard cap)
  │
  └─ Cursor pagination loop:
       while True:
           GET /price/ACB/trades?from=1778778000&to=1778864399&limit=1000&order=asc
           → append records
           → nếu get_all=True và response có nextPageToken → tiếp tục
           → nếu không có nextPageToken → dừng
       # ACB ngày 2026-05-15: ~8 864 lệnh, ~9 requests
```

### Helper `_to_vn_day_bounds`

```python
from vnbroker.explorer.dnse.quote import _to_vn_day_bounds

f, t = _to_vn_day_bounds("2026-05-15")
# f = 1778778000  (2026-05-15 00:00:00+07:00)
# t = 1778864399  (2026-05-15 23:59:59+07:00)
```

Hàm này có thể import trực tiếp để debug timestamp.

## Response shape thực tế (từ DNSE API)

DNSE trả về JSON:
```json
{
  "trades": [
    {
      "marketId": "STO",
      "boardId": "G1",
      "symbol": "ACB",
      "matchPrice": 22.8,
      "matchQtty": 10,
      "side": "SELL",
      "time": "2026-05-15 07:45:01",
      "avgPrice": 23.18,
      "totalVolumeTraded": 2159190,
      "highestPrice": 23.35,
      "lowestPrice": 22.8,
      "openPrice": 22.8
    }
  ],
  "nextPageToken": "MjQ2NzYyMzlfMjAyNi0wNS0xNVQwNzo0NTowMS43M1o="
}
```

Sau parse, DataFrame có cột:

| Cột | Kiểu | Nguồn API | Ghi chú |
|---|---|---|---|
| `time` | `datetime64` | `time` | Parse từ string `YYYY-MM-DD HH:MM:SS` |
| `price` | `float64` | `matchPrice` | Giá khớp (nghìn VND) |
| `volume` | `Int64` | `matchQtty` | KL khớp (cổ phiếu) |
| `side` | `object` | `side` | `"BUY"` hoặc `"SELL"` |

---



| Điểm | Chi tiết |
|---|---|
| **Endpoint** | `GET /price/{symbol}/trades` — symbol là **path param**, không phải query param. |
| **`from` bắt buộc** | API luôn yêu cầu `from` (Unix seconds). Nếu không truyền `date`/`start`, hàm tự dùng `00:00` hôm nay (VN). |
| **Múi giờ** | Tất cả boundary timestamp tính theo **UTC+7** (giờ Việt Nam). |
| **`page_size` max 1000** | DNSE giới hạn cứng 1–1000 mỗi request. Vượt quá sẽ báo lỗi 400. |
| **`get_all=False` (mặc định)** | Chỉ lấy 1 page (tối đa 1000 lệnh). Dùng khi cần nhanh hoặc test. |
| **`get_all=True`** | Phân trang tự động qua `nextPageToken`. ACB 1 ngày ≈ 8 000–10 000 lệnh, mất ~5 giây. |
| **Tape live (hôm nay)** | Trong giờ giao dịch, `intraday()` trả về lệnh đã khớp từ `09:00` đến hiện tại. Ngoài giờ trả về rỗng. |
| **`nextPageToken` format** | Base64 encoding. Hàm tự xử lý, không cần thao tác thủ công. |

---

## Test trước khi dùng

### Smoke test (không cần creds)

```python
import inspect
from vnbroker.explorer.dnse.quote import DNSEQuote, _to_vn_day_bounds

# Kiểm tra signature
print(list(inspect.signature(DNSEQuote.intraday).parameters.keys()))
# → ['self', 'symbol', 'date', 'start', 'end', 'page_size', 'get_all', 'order', 'show_log', 'kwargs']

# Kiểm tra helper timezone
f, t = _to_vn_day_bounds("2026-05-15")
from datetime import datetime, timezone, timedelta
VN = timezone(timedelta(hours=7))
print(datetime.fromtimestamp(f, tz=VN).isoformat())  # 2026-05-15T00:00:00+07:00
print(datetime.fromtimestamp(t, tz=VN).isoformat())  # 2026-05-15T23:59:59+07:00
```

### Integration test (cần DNSE creds)

```python
import os
from vnbroker.explorer.dnse.quote import DNSEQuote

q = DNSEQuote(
    "ACB",
    api_key=os.environ["DNSE_API_KEY"],
    api_secret=os.environ["DNSE_API_SECRET"],
    show_log=True,
)

# Test tape 1 ngày lịch sử
df = q.intraday(date="2026-05-15", get_all=True)
assert not df.empty, "Tape rỗng — kiểm tra ngày giao dịch"
assert set(["time", "price", "volume", "side"]).issubset(df.columns)
print(f"Tape 2026-05-15: {len(df)} records")  # kỳ vọng ~8 864 cho ACB
print(df.head(3))
# Output mẫu:
#                   time  price  volume  side
# 0  2026-05-15 02:15:00   22.8       1  SELL
# 1  2026-05-15 02:15:00   22.8       4  SELL
# 2  2026-05-15 02:15:00   22.8       1  SELL

# Test tape khoảng ngày
df2 = q.intraday(start="2026-05-13", end="2026-05-15", get_all=True)
print(f"Tape 3 ngày: {len(df2)} records")
```

---

## Files liên quan

| File | Mục đích |
|---|---|
| `vnbroker/explorer/dnse/quote.py` | Explorer layer — `DNSEQuote.intraday()`, `_to_vn_day_bounds()` |
| `vnbroker/connector/dnse/services/market_service.py` | Service layer — `get_trades()` gọi DNSE REST |
| `vnbroker/connector/dnse/client.py` | Client wrapper — `DNSEClient.get_trades()` |
| `vnbroker/api/quote.py` | Public API — `Quote.intraday()` forward `**kwargs` |
| `docs/DNSE_API_CONTRACT.md` | Hợp đồng API DNSE đầy đủ |
| `docs/DNSE_INDEX.md` | Index tài liệu DNSE |
