# DNSE Tape / Intraday API — Hướng dẫn lập trình viên

> **Cập nhật:** 2026-05-18 — Thêm hỗ trợ tape lịch sử (`date`, `start`, `end`, `get_all`, cursor pagination)

---

## Tổng quan

`DNSEQuote.intraday()` gọi endpoint `GET /price/trades` của DNSE LightSpeed OpenAPI.  
Từ phiên bản hiện tại, hàm hỗ trợ cả **tape phiên hiện tại** lẫn **tape lịch sử nhiều ngày** với cursor pagination tự động.

---

## Chữ ký hàm

```python
def intraday(
    self,
    symbol: str | None = None,
    date: str | None = None,        # 'YYYY-MM-DD' — tape 1 ngày
    start: str | None = None,       # 'YYYY-MM-DD' — từ ngày
    end: str | None = None,         # 'YYYY-MM-DD' — đến ngày (mặc định: hôm nay)
    page_size: int | None = None,   # mặc định 10 000 khi có date/start, 100 cho live
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
| `page_size` | `int` | Số lệnh tối đa mỗi request. Tự động `10 000` khi có `date`/`start`; `100` khi live. |
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
  │         → from_ts = 1747238400  (2026-05-15 00:00:00+07:00)
  │         → to_ts   = 1747324799  (2026-05-15 23:59:59+07:00)
  │
  ├─ page_size = 10_000 (auto vì có date)
  │
  └─ Cursor pagination loop:
       while True:
           GET /price/trades?symbol=ACB&from=...&to=...&limit=10000&order=asc
           → append records
           → nếu get_all=True và response có nextPageToken → tiếp tục
           → nếu không có nextPageToken → dừng
```

### Helper `_to_vn_day_bounds`

```python
from vnbroker.explorer.dnse.quote import _to_vn_day_bounds

f, t = _to_vn_day_bounds("2026-05-15")
# f = 1747238400  (00:00:00 VN)
# t = 1747324799  (23:59:59 VN)
```

Hàm này có thể import trực tiếp để debug timestamp.

---

## Lưu ý quan trọng

| Điểm | Chi tiết |
|---|---|
| **Múi giờ** | Tất cả boundary timestamp tính theo **UTC+7** (giờ Việt Nam). DNSE API nhận Unix seconds, không nhận chuỗi ngày. |
| **`get_all=False` (mặc định)** | Chỉ lấy 1 page. Dùng khi cần nhanh hoặc test. |
| **`get_all=True`** | Phân trang tự động đến hết. Có thể mất vài giây với ngày có khối lượng lớn. |
| **`page_size` giới hạn** | DNSE có thể giới hạn tối đa. Nếu gặp lỗi 400, thử giảm xuống `5_000`. |
| **Tape live** | Khi không truyền `date`/`start`, hàm lấy tape phiên hiện tại (`from_ts=None`). DNSE trả về các lệnh gần nhất theo `limit`. |
| **`nextPageToken` expire** | Token có thể hết hạn sau một thời gian. Nếu cần tape toàn ngày lớn, chạy ngay sau market close. |
| **Backward compat** | `intraday()` không tham số vẫn hoạt động như trước — trả về 100 lệnh gần nhất. |

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
assert set(["time", "price", "volume"]).issubset(df.columns)
print(f"Tape 2026-05-15: {len(df)} records")
print(df.head(3))

# Test tape khoảng ngày
df2 = q.intraday(start="2026-05-12", end="2026-05-14", get_all=True)
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
