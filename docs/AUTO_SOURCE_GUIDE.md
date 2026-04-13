# AUTO Source — Hướng dẫn sử dụng nguồn tự động

> Tài liệu mô tả cơ chế `source='AUTO'` trong vnstock: cách chọn nguồn, thứ tự ưu tiên, failover, và cách sử dụng tối ưu.

---

## Mục lục

1. [Tổng quan](#1-tổng-quan)
2. [Thứ tự ưu tiên nguồn dữ liệu](#2-thứ-tự-ưu-tiên-nguồn-dữ-liệu)
3. [Hướng dẫn sử dụng theo nhóm dữ liệu](#3-hướng-dẫn-sử-dụng-theo-nhóm-dữ-liệu)
4. [Cơ chế routing và failover](#4-cơ-chế-routing-và-failover)
5. [Performance Profiles](#5-performance-profiles)
6. [Benchmark](#6-benchmark)
7. [Kiến trúc nội bộ](#7-kiến-trúc-nội-bộ)

---

## 1. Tổng quan

`source='AUTO'` cho phép vnstock **tự động chọn nguồn dữ liệu tốt nhất** mà không cần chỉ định thủ công. Hệ thống sẽ:

- Ưu tiên nguồn chính theo từng nhóm dữ liệu: `quote/company/financial` dùng **VCI-first**, còn `trading.price_board` dùng **KBS-first**.
- Tự động **failover sang nguồn kế tiếp** nếu nguồn chính bị rate-limit, timeout, hoặc trả về lỗi.
- Đặt nguồn lỗi vào **cooldown** (tối thiểu 5 giây, tối đa 90 giây theo exponential backoff) rồi thử lại sau.

```python
from vnstock import Vnstock

stock = Vnstock(source='AUTO', symbol='ACB')

# Lịch sử giá — tự động chọn VCI, failover sang KBS nếu cần
df = stock.quote.history(start='2025-01-01', end='2025-12-31')

# Thông tin doanh nghiệp
info = stock.company.overview()

# Báo cáo tài chính
bs = stock.finance.balance_sheet(period='quarter', lang='vi')
```

---

## 2. Thứ tự ưu tiên nguồn dữ liệu

### Nguồn hỗ trợ AUTO

| Nhóm | Nguồn hỗ trợ |
|---|---|
| `quote` | VCI → KBS → MSN |
| `company` | VCI → KBS |
| `financial` | VCI → KBS |
| `trading` | KBS → VCI |
| `listing` | KBS → VCI → MSN |

### Khuyến nghị sử dụng (theo thứ tự ưu tiên)

| Thứ tự | `source=` | Khi nào dùng |
|:---:|---|---|
| **1** | `'AUTO'` | **Mặc định cho mọi trường hợp.** Tự tiết kiệm chi phí xử lý lỗi. |
| **2** | `'VCI'` | Khi cần throughput tối đa và VCI đang hoạt động bình thường. |
| **3** | `'KBS'` | Khi VCI bị chặn hoặc cần nguồn dự phòng tĩnh. |
| **4** | `'MSN'` | Chỉ dùng cho listing symbols; không hỗ trợ đầy đủ quote. |
| **5** | `'TCBS'` | Nguồn có xác thực; dùng khi cần dữ liệu độc quyền TCBS. |

> **Ghi chú**: `AUTO` không còn là một policy duy nhất cho mọi nhóm dữ liệu. Hiện tại `quote/company/financial` vẫn là VCI-first, nhưng `trading.price_board` đã chuyển sang KBS-first do benchmark online cho thấy KBS ổn định hơn rõ rệt dưới tải duy trì.

---

## 3. Hướng dẫn sử dụng theo nhóm dữ liệu

### 3.1 Lịch sử giá (Quote)

```python
from vnstock import Vnstock

# ✅ Khuyến nghị: AUTO — VCI-first, failover sang KBS tự động
stock = Vnstock(source='AUTO', symbol='VNM')
df = stock.quote.history(start='2025-01-01', end='2025-12-31', interval='1D')

# Kiểm tra nguồn thực tế đã dùng
print(df.attrs.get('source_used'))  # → 'VCI' hoặc 'KBS'
```

```python
# Nhiều mã đồng thời — vẫn dùng AUTO
symbols = ['ACB', 'VNM', 'HPG', 'MSN']
results = {}
for sym in symbols:
    stock = Vnstock(source='AUTO', symbol=sym)
    results[sym] = stock.quote.history(start='2025-01-01', end='2025-12-31')
```

### 3.2 Thông tin doanh nghiệp (Company)

```python
from vnstock import Vnstock

stock = Vnstock(source='AUTO', symbol='VNM')

overview    = stock.company.overview()
subsidiaries = stock.company.subsidiaries()
officers    = stock.company.officers()
shareholders = stock.company.shareholders()
events      = stock.company.events()
```

### 3.3 Tài chính (Finance)

```python
from vnstock import Vnstock

stock = Vnstock(source='AUTO', symbol='VNM')

balance_sheet    = stock.finance.balance_sheet(period='quarter', lang='vi')
income_statement = stock.finance.income_statement(period='year',    lang='vi')
cash_flow        = stock.finance.cash_flow(period='quarter',        lang='vi')
ratio            = stock.finance.ratio(period='year',               lang='vi')
```

### 3.4 Giao dịch (Trading)

```python
from vnstock import Vnstock

stock = Vnstock(source='AUTO', symbol='ACB')

price_board = stock.trading.price_board(symbols_list=['ACB', 'VNM', 'HPG'])
```

### 3.5 Danh sách mã (Listing)

```python
from vnstock.common.data import Listing

listing = Listing(source='AUTO')

# Tất cả mã niêm yết (ưu tiên KBS → VCI → MSN)
all_symbols = listing.all_symbols()
hose        = listing.symbols_by_exchange()
```

### 3.6 Chỉ số thị trường (Index)

```python
from vnstock.common.indices import Indices

indices = Indices(source='VCI')   # Chỉ VCI hỗ trợ đủ
vni = indices.history(symbol='VNINDEX', start='2025-01-01', end='2025-12-31')
```

---

## 4. Cơ chế routing và failover

### Luồng xử lý một request

```
Vnstock(source='AUTO', symbol='ACB').quote.history(...)
         │
         ▼
  build_source_order('quote', symbol='ACB')
  ┌────────────────────────────────────────┐
  │  1. Lấy PRIMARY_POOL['quote'] = ['vci']│
  │  2. Lọc bỏ nguồn đang cooldown        │
  │  3. hash(module:SYMBOL) % pool_size → 0│
  │  4. primary_order = ['vci']            │
  │  5. extras = ['kbs', 'msn']            │
  │  6. return ['vci', 'kbs', 'msn']       │
  └────────────────────────────────────────┘
         │
         ▼
  Thử VCI → Thành công → record_success('quote', 'vci')
                       → annotate_result(df, source='VCI')
                       → return df

         │ (nếu VCI lỗi)
         ▼
  should_failover(exc) == True ?
  ├─ Yes → record_failure('quote', 'vci')   ← cooldown = 5s × 2^(fail-1)
  │         Thử KBS → Thành công → return df
  └─ No  → raise exception trực tiếp
```

### Cooldown exponential backoff

| Lần lỗi | Cooldown |
|:---:|---|
| 1 | 5 giây |
| 2 | 10 giây |
| 3 | 20 giây |
| 4 | 40 giây |
| 5+ | 90 giây (tối đa) |

### Các lỗi kích hoạt failover

- `ConnectionError`, `TimeoutError`, `NotImplementedError`
- HTTP 429 (Too Many Requests), 403 (Forbidden)
- Message chứa: `rate limit`, `timeout`, `connection`, `service unavailable`, `failed to fetch`, `not implemented`

### Reset trạng thái router

```python
from vnstock.core.source_router import reset_router_state

# Xóa toàn bộ cooldown state (dùng trong test hoặc khi muốn bắt đầu lại)
reset_router_state()
```

---

## 5. Performance Profiles

Kết hợp với AUTO để kiểm soát concurrency và retry:

```python
from vnstock.core.performance_profiles import apply_profile, apply_profile_for_current_time

# Cho benchmark / batch offline
apply_profile('benchmark_max_speed')

# Tự động theo giờ thị trường
apply_profile_for_current_time(
    peak_profile='market_hours',      # 09:00–11:30, 13:00–15:30
    offpeak_profile='benchmark_max_speed'
)
```

| Profile | Dùng khi | Concurrency | Retry |
|---|---|---|---|
| `benchmark_max_speed` | Batch offline, benchmark | Cao | Tắt |
| `production_stable` | Server production 24/7 | Trung bình | Đầy đủ |
| `market_hours` | Live trong giờ giao dịch | Thận trọng | Đầy đủ |

Xem thêm: [PERFORMANCE_PROFILES.md](PERFORMANCE_PROFILES.md)

---

## 6. Benchmark

### Kết quả đo thực tế (2026-04-04)

**Thiết lập:** 60 symbols, 30 ngày dữ liệu (2026-03-03 → 2026-04-03), profile `benchmark_max_speed`

| Provider | Concurrency | Symbols | Success | RPS | p50 | p95 | Provider split |
|---|:---:|:---:|:---:|:---:|:---:|:---:|---|
| **AUTO** | 8 | 60 | **100%** | **37.21** | 0.11s | 0.63s | VCI:60 |
| **AUTO** | 16 | 60 | **100%** | **38.09** | 0.12s | 0.95s | VCI:60 |
| VCI (thuần) | 8 | 60 | 100% | 46.52 | 0.09s | 0.61s | VCI:60 |
| VCI (thuần) | 16 | 60 | 100% | 43.45 | 0.13s | 1.02s | VCI:60 |
| KBS (thuần) | 8 | 60 | 86.67% | 11.12 | 0.04s | 4.08s | KBS:52 |
| KBS (thuần) | 16 | 60 | 86.67% | 11.63 | 0.08s | 4.14s | KBS:52 |

**Stress test:** 90 symbols, concurrency 12 và 24

| Provider | Concurrency | Symbols | Success | RPS | p50 | p95 | Provider split |
|---|:---:|:---:|:---:|:---:|:---:|:---:|---|
| AUTO | 12 | 90 | **100%** | **41.30** | 0.11s | 1.03s | KBS:5 / VCI:85 |
| AUTO | 24 | 90 | 95.56% | 13.97 | 0.18s | 3.88s | KBS:21 / VCI:65 |

**Nhận xét:**
- `AUTO` ở c=8,16 đạt 100% success và ~37–38 rps, sát ngang `VCI` thuần (~46 rps).
- `KBS` thuần chỉ 86.67% success và 11 rps — AUTO cải thiện cả hai chỉ số so với KBS.
- Ở c=12 (90 symbols), AUTO đạt 41 rps 100% nhờ VCI xử lý 85/90 request, KBS nhận 5 failover.
- Ở c=24 bắt đầu rate-limit; KBS failover hấp thụ 21/90 nhưng vẫn mất 4 request.
- **Concurrency tối ưu: 8–16** cho độ ổn định tốt nhất.

### Chạy benchmark thủ công

```bash
# So sánh AUTO vs VCI vs KBS, 60 symbols
python -m tests.examples.auto_source_benchmark \
  --profile benchmark_max_speed \
  --symbol-count 60 \
  --providers AUTO,VCI,KBS \
  --concurrency 8,16 \
  --runs 1 \
  --start 2025-01-01 --end 2025-03-31 \
  --output-csv tmp/bench/my_benchmark.csv \
  --output-json tmp/bench/my_benchmark.json
```

```bash
# Stress test AUTO 90 symbols
python -m tests.examples.auto_source_benchmark \
  --profile benchmark_max_speed \
  --symbol-count 90 \
  --providers AUTO \
  --concurrency 12,24 \
  --output-csv tmp/bench/stress.csv
```

Xem thêm tùy chọn CLI:

```bash
python -m tests.examples.auto_source_benchmark --help
```

---

## 7. Kiến trúc nội bộ

### Sơ đồ module

```
Vnstock(source='AUTO')
    └── vnstock/common/client.py
            └── vnstock/common/data.py          ← Facade layer
                    ├── StockComponents
                    ├── Quote._load_data_source()
                    ├── Listing._load_data_source()
                    ├── Trading._load_data_source()
                    ├── Company._load_data_source()
                    └── Finance._load_data_source()
                            │  (khi source in PUBLIC_VN_SOURCES)
                            ▼
                    vnstock/api/{quote,listing,...}.py  ← Adapter layer
                            │
                            ▼
                    vnstock/base.py (BaseAdapter)
                            │
                            ├── vnstock/core/source_router.py  ← Routing engine
                            │       ├── build_source_order()
                            │       ├── record_success/failure()
                            │       ├── should_failover()
                            │       └── annotate_result_source()
                            │
                            └── vnstock/core/registry.py       ← Provider registry
                                    └── ProviderRegistry.get(module, source)
```

### File liên quan

| File | Vai trò |
|---|---|
| `vnstock/core/source_router.py` | Engine routing AUTO: sharding, cooldown, failover |
| `vnstock/core/types.py` | `DataSource` enum (bao gồm `AUTO = "auto"`) |
| `vnstock/base.py` | `BaseAdapter` — vòng lặp thử nguồn |
| `vnstock/common/data.py` | Facade routing `source in PUBLIC_VN_SOURCES` → adapter |
| `vnstock/common/client.py` | `Vnstock` main class |
| `vnstock/api/quote.py` | Quote adapter |
| `vnstock/api/listing.py` | Listing adapter |
| `vnstock/api/company.py` | Company adapter |
| `vnstock/api/financial.py` | Finance adapter |
| `vnstock/api/trading.py` | Trading adapter |
| `tests/unit/api/test_auto_source_router.py` | Unit tests routing |
| `tests/examples/auto_source_benchmark.py` | Benchmark CLI tool |

### `DataSource` enum

```python
from vnstock.core.types import DataSource

DataSource.AUTO    # "auto"  ← Mới thêm
DataSource.VCI     # "vci"
DataSource.KBS     # "kbs"
DataSource.MSN     # "msn"
DataSource.TCBS    # "tcbs"
```

---

## Xem thêm

- [PERFORMANCE_PROFILES.md](PERFORMANCE_PROFILES.md) — Profiles và auto-tuning concurrency
- [PROXY_GUIDE.md](PROXY_GUIDE.md) — Sử dụng proxy với VCI
- [VNSTOCK_COMPARISON.md](VNSTOCK_COMPARISON.md) — So sánh nguồn dữ liệu
- [PORTFOLIO_ROBOADVISOR_GUIDE.md](PORTFOLIO_ROBOADVISOR_GUIDE.md) — Tích hợp robo-advisor
