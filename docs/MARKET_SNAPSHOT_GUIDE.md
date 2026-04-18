# MarketSnapshot — Hướng dẫn sử dụng

> **Phiên bản:** vnstock ≥ 3.4.0  
> **Module:** `vnstock.api.snapshot`  
> **Tác giả:** vnstock team  
> **Cập nhật:** 2026-04-18

---

## Mục lục

1. [Giới thiệu](#1-giới-thiệu)
2. [Cài đặt / Import](#2-cài-đặt--import)
3. [Schema dữ liệu đầu ra](#3-schema-dữ-liệu-đầu-ra)
4. [Hướng dẫn nhanh](#4-hướng-dẫn-nhanh)
5. [API Reference](#5-api-reference)
6. [Giải thích đơn vị](#6-giải-thích-đơn-vị)
7. [Cache & hiệu năng](#7-cache--hiệu-năng)
8. [Tích hợp với Frontend (React / ECharts)](#8-tích-hợp-với-frontend-react--echarts)
9. [Xử lý lỗi thường gặp](#9-xử-lý-lỗi-thường-gặp)
10. [Danh sách nhóm chỉ số được hỗ trợ](#10-danh-sách-nhóm-chỉ-số-được-hỗ-trợ)

---

## 1. Giới thiệu

`MarketSnapshot` gộp **ba nguồn dữ liệu** thành một JSON list chuẩn hoá, phục vụ trực tiếp cho:

| Use-case | Method |
|---|---|
| Heatmap thị trường (treemap ECharts) | `heatmap_data()` / `heatmap_data_by_group()` |
| Bảng danh mục holdings | `heatmap_df()` |
| API endpoint JSON cho Django/FastAPI | `heatmap_data()` |

Vấn đề **"NHÓM NGÀNH: undefined"** đã được giải quyết: field `industry` luôn có giá trị tiếng Việt đầy đủ (fallback `"Khác"` nếu KBS không trả về ngành).

### Luồng dữ liệu

```
MarketSnapshot.heatmap_data(symbols)
        │
        ├─[1]─ KBS Trading.price_board(get_all=True)
        │       → symbol, close_price, reference_price, percent_change,
        │         volume_accumulated, listed_shares
        │
        ├─[2]─ KBS Listing.symbols_by_industries()  ← cache 5 phút
        │       → symbol → industry_name (tiếng Việt)
        │
        ├─[3]─ KBS Listing.all_symbols()            ← cache 5 phút
        │       → symbol → organ_name (tên công ty)
        │
        ├─[4]─ Tính market_cap = close_price × listed_shares
        │
        └─[5]─ Merge & select → JSON list 8 fields
```

---

## 2. Cài đặt / Import

```python
# Cách 1 — import trực tiếp từ vnstock
from vnstock import MarketSnapshot

# Cách 2 — import từ module cụ thể
from vnstock.api.snapshot import MarketSnapshot
```

Khởi tạo:

```python
snap = MarketSnapshot()                          # Mặc định: source="kbs"
snap = MarketSnapshot(show_log=True)             # Bật log debug
snap = MarketSnapshot(random_agent=True)         # Dùng random user-agent
```

---

## 3. Schema dữ liệu đầu ra

Mỗi phần tử trong list / mỗi hàng trong DataFrame:

| Field | Kiểu | Đơn vị | Mô tả |
|---|---|---|---|
| `symbol` | `str` | — | Mã chứng khoán (VD: `"VCB"`) |
| `current_price` | `float` | nghìn VND* | Giá khớp hiện tại |
| `prev_price` | `float` | nghìn VND* | Giá tham chiếu (đóng cửa hôm qua) |
| `change_pct` | `float` | % | % thay đổi so với tham chiếu (VD: `-1.5`) |
| `volume` | `int` | cổ phiếu | Khối lượng giao dịch lũy kế |
| `market_cap` | `float` | tỷ VND | Vốn hoá thị trường |
| `industry` | `str` | — | Nhóm ngành tiếng Việt (VD: `"Ngân hàng"`) |
| `company_name` | `str` | — | Tên công ty đầy đủ |

> *Nếu truyền `price_unit="VND"` thì `current_price` và `prev_price` ở VND nguyên. `market_cap` luôn ở tỷ VND.

---

## 4. Hướng dẫn nhanh

### 4.1 Lấy dữ liệu cho danh sách mã

```python
from vnstock import MarketSnapshot

snap = MarketSnapshot()

# Trả về list[dict] — dùng trực tiếp làm JSON response
data = snap.heatmap_data(["VCB", "TCB", "BID", "CTG", "VNM", "HPG"])

print(data[0])
# {
#   "symbol": "VCB",
#   "current_price": 88.5,
#   "prev_price": 89.0,
#   "change_pct": -0.56,
#   "volume": 1234567,
#   "market_cap": 315432.1,
#   "industry": "Ngân hàng",
#   "company_name": "Ngân hàng TMCP Ngoại Thương Việt Nam"
# }
```

### 4.2 Lấy dữ liệu cho nhóm chỉ số

```python
snap = MarketSnapshot()

# VN30 — 30 cổ phiếu vốn hoá lớn nhất HOSE
vn30_data = snap.heatmap_data_by_group("VN30")

# Toàn bộ HOSE
hose_data = snap.heatmap_data_by_group("HOSE")

# VN100
vn100_data = snap.heatmap_data_by_group("VN100")
```

### 4.3 Lấy dạng DataFrame

```python
snap = MarketSnapshot()
df = snap.heatmap_df(["VCB", "VNM", "HPG", "FPT"])

print(df.columns.tolist())
# ['symbol', 'current_price', 'prev_price', 'change_pct',
#  'volume', 'market_cap', 'industry', 'company_name']

print(df.attrs)
# {'price_unit': 'nghìn VND', 'market_cap_unit': 'tỷ VND', 'source': 'KBS'}

# Lọc theo ngành
banks = df[df["industry"] == "Ngân hàng"]
print(banks[["symbol", "current_price", "market_cap"]])
```

### 4.4 Dùng với giá VND nguyên

```python
snap = MarketSnapshot()
data = snap.heatmap_data(["VCB", "VNM"], price_unit="VND")
# current_price và prev_price ở VND (×1000 so với mặc định)
# market_cap vẫn tính về tỷ VND
```

### 4.5 Xuất JSON cho Django/FastAPI

```python
import json
from vnstock import MarketSnapshot

snap = MarketSnapshot()
data = snap.heatmap_data_by_group("VN30")

# Trả về HTTP response trực tiếp
json_str = json.dumps(data, ensure_ascii=False, indent=2)
print(json_str[:500])
```

**Django view mẫu:**

```python
# views.py
from django.http import JsonResponse
from vnstock import MarketSnapshot

_snap = MarketSnapshot()  # Singleton — khởi tạo 1 lần

def market_heatmap(request):
    group = request.GET.get("group", "VN30")
    try:
        data = _snap.heatmap_data_by_group(group)
        return JsonResponse({"status": "ok", "data": data})
    except ValueError as exc:
        return JsonResponse({"status": "error", "message": str(exc)}, status=400)
```

---

## 5. API Reference

### `MarketSnapshot(source, random_agent, show_log)`

| Tham số | Kiểu | Mặc định | Mô tả |
|---|---|---|---|
| `source` | `str` | `"kbs"` | Nguồn dữ liệu. Hiện hỗ trợ `"kbs"`. |
| `random_agent` | `bool` | `False` | Dùng random user-agent HTTP. |
| `show_log` | `bool` | `False` | In log debug ra console. |

---

### `heatmap_data(symbols_list, price_unit, refresh_cache) → list[dict]`

| Tham số | Kiểu | Mặc định | Mô tả |
|---|---|---|---|
| `symbols_list` | `list[str]` | *(bắt buộc)* | Danh sách mã CK. |
| `price_unit` | `str \| None` | `None` | Đơn vị giá: `None` = nghìn VND, `"VND"` = đồng. |
| `refresh_cache` | `bool` | `False` | Bắt buộc reload industry/company cache. |

**Trả về:** `list[dict]` — danh sách 8-field, rỗng nếu không lấy được dữ liệu giá.  
**Raises:** `ValueError` nếu `symbols_list` rỗng.

---

### `heatmap_data_by_group(group, price_unit, refresh_cache) → list[dict]`

| Tham số | Kiểu | Mặc định | Mô tả |
|---|---|---|---|
| `group` | `str` | `"VN30"` | Tên nhóm chỉ số (xem mục 10). |
| `price_unit` | `str \| None` | `None` | Xem `heatmap_data`. |
| `refresh_cache` | `bool` | `False` | Xem `heatmap_data`. |

---

### `heatmap_df(symbols_list, price_unit, refresh_cache) → pd.DataFrame`

Tương tự `heatmap_data()` nhưng trả về DataFrame.  
`df.attrs` chứa `price_unit`, `market_cap_unit`, `source`.

---

### `refresh_caches() → None`

Xóa toàn bộ cache industry và company_name, buộc fetch lại lần gọi tiếp theo.

```python
snap.refresh_caches()
```

---

## 6. Giải thích đơn vị

### Giá (current_price, prev_price)

HOSE / KBS trả về giá theo **nghìn VND** (đây là chuẩn hiển thị của sàn HoSE):

```
Giá hiển thị trên bảng điện tử: 88.5 (nghìn đồng) = 88,500 VND thực
```

Nếu frontend cần VND nguyên, truyền `price_unit="VND"`:

```python
data = snap.heatmap_data(symbols, price_unit="VND")
# current_price = 88500.0  (VND)
```

### market_cap (tỷ VND)

```
market_cap = (close_price_nghìnVND × 1000 × listed_shares) / 1_000_000_000
           = close_price_nghìnVND × listed_shares / 1_000_000
```

Ví dụ VCB:
```
close_price = 88.5 nghìn VND
listed_shares ≈ 3,564,600,000 cổ phiếu
market_cap = 88.5 × 1000 × 3,564,600,000 / 1e9 ≈ 315,467 tỷ VND
```

> **Lưu ý:** `market_cap` sẽ là `None` nếu KBS không trả về `listed_shares` cho mã đó.

---

## 7. Cache & hiệu năng

`MarketSnapshot` sử dụng **instance-level TTL cache** (5 phút) cho:
- `symbols_by_industries()` — chậm do gọi API riêng cho từng ngành
- `all_symbols()` — tên công ty ít thay đổi

**Bảng giá (price_board)** **không được cache** — luôn fetch realtime mỗi lần gọi.

### Tối ưu khi dùng trong server:

```python
# Khởi tạo 1 lần, dùng lại cho nhiều request
# (cache industry/company được giữ giữa các lần gọi)
_market_snap = MarketSnapshot()

def get_heatmap():
    return _market_snap.heatmap_data_by_group("VN30")

# Nếu muốn refresh cache thủ công (VD: sau corporate action)
_market_snap.refresh_caches()
```

### Thời gian ước tính (lần đầu, cache rỗng):

| Số mã | Thời gian ước tính |
|---|---|
| 30 (VN30) | ~2–4 giây |
| 100 (VN100) | ~3–6 giây |
| 700+ (HOSE) | ~8–15 giây |

Từ lần 2 trở đi (industry/company cache còn hạn): nhanh hơn ~50%.

---

## 8. Tích hợp với Frontend (React / ECharts)

### Cấu trúc JSON cho ECharts Treemap

ECharts treemap yêu cầu field `name`, `value`, và `children`. Dưới đây là cách transform:

```javascript
// frontend: transformToTreemap.js
export function transformToTreemap(snapshotData) {
  // Gom nhóm theo industry
  const groups = {};
  for (const item of snapshotData) {
    const industry = item.industry || "Khác";
    if (!groups[industry]) groups[industry] = [];
    groups[industry].push(item);
  }

  // Build ECharts treemap data
  return Object.entries(groups).map(([industry, stocks]) => ({
    name: industry,
    children: stocks.map(s => ({
      name: s.symbol,
      value: s.market_cap || 0,
      current_price: s.current_price,
      change_pct: s.change_pct,
      volume: s.volume,
      company_name: s.company_name,
      // itemStyle dùng change_pct để tô màu
      itemStyle: {
        color: s.change_pct > 0 ? "#00c853" : s.change_pct < 0 ? "#d32f2f" : "#757575"
      }
    }))
  }));
}
```

### Mapping field vnstock → frontend

| vnstock field | Frontend field (quotesBySymbol) | Ghi chú |
|---|---|---|
| `symbol` | `symbol` | Key định danh |
| `current_price` | `current_price` | Giá khớp (WS override nếu có) |
| `prev_price` | `prev_price` | Dùng cho sparkline fallback |
| `change_pct` | `change_pct` | % thay đổi |
| `volume` | `volume` | KL lũy kế |
| `market_cap` | `market_cap` | Vốn hoá (tỷ VND) |
| `industry` | `industry` | **Bắt buộc** cho treemap groupBy |
| `company_name` | `company_name` | Hiển thị trong tooltip |

---

## 9. Xử lý lỗi thường gặp

### `market_cap` là `None`

**Nguyên nhân:** KBS không trả về `listed_shares` cho mã đó trong `price_board`.  
**Xử lý:** Frontend guard bằng `item.market_cap ?? 0` hoặc loại bỏ khỏi treemap.

### `industry` là `"Khác"`

**Nguyên nhân:** Mã không có trong danh sách ngành của KBS (thường gặp với ETF, CW, trái phiếu).  
**Xử lý:** Filter trước khi truyền vào `heatmap_data`, hoặc group "Khác" vào một tile riêng trong treemap.

### Lỗi khi gọi `symbols_by_industries`

```python
# Nếu API ngành bị lỗi, MarketSnapshot vẫn trả dữ liệu giá
# với industry = "Khác" cho tất cả mã
snap = MarketSnapshot(show_log=True)  # Bật log để xem chi tiết lỗi
```

### `heatmap_data` trả về list rỗng

**Nguyên nhân:** `price_board` không lấy được dữ liệu (mất kết nối, ngoài giờ giao dịch, v.v.).  
**Xử lý:**

```python
data = snap.heatmap_data(symbols)
if not data:
    # Fallback: dùng dữ liệu cache hoặc hiển thị thông báo
    print("Không lấy được dữ liệu thị trường.")
```

---

## 10. Danh sách nhóm chỉ số được hỗ trợ

Dùng với `heatmap_data_by_group(group=...)`:

| `group` | Mô tả |
|---|---|
| `"VN30"` | 30 cổ phiếu vốn hoá lớn nhất & thanh khoản tốt nhất HOSE |
| `"VN100"` | 100 cổ phiếu vốn hoá lớn nhất HOSE |
| `"VNMidCap"` | Mid-Cap — cổ phiếu vốn hoá trung bình |
| `"VNSmallCap"` | Small-Cap — cổ phiếu vốn hoá nhỏ |
| `"VNSI"` | Vietnam Small-Cap Index |
| `"VNX50"` | VNX50 |
| `"VNXALL"` | VNX All |
| `"VNALL"` | Tất cả cổ phiếu HOSE + HNX |
| `"HOSE"` | Toàn bộ sàn HOSE |
| `"HNX"` | Toàn bộ sàn HNX |
| `"UPCOM"` | Toàn bộ sàn UPCOM |
| `"HNX30"` | HNX30 |
| `"ETF"` | Quỹ ETF |

---

## Changelog

| Ngày | Phiên bản | Thay đổi |
|---|---|---|
| 2026-04-18 | 3.4.0+ | Tạo mới `MarketSnapshot` với `heatmap_data`, `heatmap_data_by_group`, `heatmap_df`, `refresh_caches` |
