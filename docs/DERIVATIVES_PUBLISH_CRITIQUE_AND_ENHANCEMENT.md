# Phản Biện & Bổ Sung Kế Hoạch Tích Hợp Dữ Liệu Phái Sinh Công Khai (Publish APIs) Trong vnbroker

**Ngày cập nhật:** 2026-06-21
**Cơ sở:** Phân tích từ 3 tài liệu: `DERIVATIVES_API_RESEARCH.md`, `DERIVATIVES_PUBLISH_RESEARCH_PLAN.md`, và mã nguồn thực tế.

---

## 1. Đánh Giá Tổng Quan

### Điểm mạnh của bộ tài liệu hiện tại
1. **Phân tách rõ ràng Publish vs Private APIs** — đúng kiến trúc `vnbroker`, tránh nhầm lẫn giữa dữ liệu công khai và giao dịch.
2. **Khảo sát đủ 4 providers** — TCBS, DNSE, VCI, KBS — phủ hết thị trường chứng khoán phái sinh Việt Nam.
3. **Phát hiện đúng các lỗi kỹ thuật cốt lõi:**
   - `DNSEListing.all_future_indices()` fallback sai về `indices()` (API research mục 2.1 và research plan mục 3.2 đều xác nhận).
   - `DNSEQuote.history()` hardcode `type: "STOCK"` (API research mục 3.1 và research plan mục 3.2).
   - Thiếu chuẩn hóa schema trả về giữa các providers.

### Điểm yếu & Thiếu sót

#### 1.1. Thiếu phân tích chiều sâu về KRX mapping
Cả 3 tài liệu đều đề cập đến chuyển đổi mã KRX nhưng **không phân tích chi tiết cấu trúc mã KRX**:
```
41 <I1=VN30|I2=VN100|G5=GB05|G10=GB10> <Năm> <Tháng> 000
Ví dụ: 41I1F7000 = VN30F tháng 7 2026
```
Mã nguồn trong `convert_derivative_symbol()` (parser.py) có logic parse phức tạp nhưng tài liệu không mô tả. Cần thêm bảng mapping rõ ràng để developers có thể debug khi KRX thay đổi format.

#### 1.2. Thiếu đánh giá độ tin cậy (Reliability) giữa các providers
API research (mục 4) so sánh tính năng nhưng **không có số liệu**:
- TCBS: Rate limit bao nhiêu req/s? Có cần API key không?
- DNSE: OpenAPI có giới hạn số lượng request miễn phí không?
- KBS: Crawl từ web page — có bị block IP không? Cần retry strategy gì?
- VCI: Endpoint `/price/symbols/getByGroup` có ổn định không?

**Đề xuất:** Bổ sung bảng đánh giá độ tin cậy dạng:
| Provider | Rate Limit | Uptime | Auth Required | Crawl Stability |
|----------|-----------|--------|---------------|-----------------|
| TCBS | ? | Cao | Public Token | Ổn định |
| DNSE | ? | Cao | Public Token | Ổn định |
| VCI | ? | TB | Không | Trung bình |
| KBS | ? | TB | Không | Thấp (crawl) |

#### 1.3. Thiếu kịch bản xử lý lỗi (Error Handling)
Research plan đề xuất `AdaptiveController` nhưng không chi tiết:
- Khi DNSE OpenAPI trả về 429 Too Many Requests → chờ bao lâu?
- Khi TCBS futures-insight service down → fallback sang provider khác?
- Khi VCI endpoint trả về empty list → retry hay báo lỗi?

#### 1.4. Mâu thuẫn về chiến lược KRX giữa các tài liệu
- **API research (mục 3.2):** Nói TCBS/VCI "cần kiểm tra" KRX compatibility.
- **Research plan (mục 3.4):** Đề xuất KBS pattern làm chuẩn — auto-convert trong `__init__`.
- **Critique cũ:** Mâu thuẫn giữa "giữ nguyên mã cũ" và "luôn convert".

**Đánh giá:** Cần **Feature flag cụ thể** hơn là đề xuất chung chung. Ví dụ:
```python
# config.py hoặc env
VNBROKER_KRX_MODE = "auto"     # auto-detect, force_krx, legacy_only
VNBROKER_KRX_FORCE = False     # nếu True, luôn convert sang KRX
```

---

## 2. Phản Biện Chi Tiết Từng Provider

### 2.1. DNSE — Cần Cải Tiến Nhiều Nhất (Đồng Ý với Research Plan)

**Listing (`all_future_indices()`):**
- **Vấn đề:** `all_future_indices()` hiện tại `return self.indices()` — sai hoàn toàn.
- **Root cause:** `DNSEListing` không override method này, fallback về `BaseListing` gọi `symbols_by_group()` → gọi sai endpoint.
- **Fix đề xuất:** Gọi `_fetch_instruments(security_group_id="DER")` như critique cũ đã chỉ ra.
- **Cảnh báo:** Endpoint `/market/instruments` trả về cả cổ phiếu và chứng chỉ quỹ nếu không filter. Cần filter thêm `type` nếu DNSE hỗ trợ.

**Quote (`history()`):**
- **Vấn đề:** `type: "STOCK"` hardcode tại dòng 215.
- **Root cause:** Không gọi `get_asset_type()` như các provider khác (VCI, KBS).
- **Fix đề xuất:** Sửa thành dynamic type dựa trên `get_asset_type(symbol)`.
- **Bổ sung:** DNSE cũng cần hỗ trợ `history()` với resolution mapping. Kiểm tra xem DNSE có hỗ trợ `1m`, `5m` cho phái sinh không (không phải resolution nào cũng available cho derivatives).

### 2.2. TCBS — Tốt Nhưng Thiếu Chuẩn Hóa

**Listing:**
- **OK:** `symbols_by_group(group="FU_INDEX")` hoạt động tốt, gọi đúng endpoint.
- **Thiếu:** Trả về `pd.Series` chỉ có symbol. Cần nâng cấp lên `pd.DataFrame` với `organ_name`, `exchange`.

**Quote:**
- **OK:** Đã gọi `get_asset_type()` trong `__init__`.
- **Vấn đề:** Endpoint `/futures-insight/v2/stock/bars` — TCBS có chấp nhận mã KRX mới không? Chưa được kiểm tra.
- **Đề xuất bổ sung:** TCBS có 2 hệ thống: `apiextaws.tcbs.com.vn` (cũ) và `openapi.tcbs.com.vn` (mới). Cần xác nhận futures-insight service thuộc hệ nào và hỗ trợ format mã nào.

### 2.3. VCI — Cần Kiểm Tra UPstream Trước

**Listing:**
- **OK:** Gọi đúng endpoint `/price/symbols/getByGroup?group=FU_INDEX`.
- **Thiếu:** Cùng vấn đề — trả về `pd.Series` thiếu thông tin.

**Quote:**
- **OK:** Đã có `get_asset_type()`.
- **Rủi ro:** Endpoint `/chart/OHLCChart/gap-chart` — không rõ VCI backend có tự detect derivative qua symbol không, hay cần thêm tham số.
- **Cần kiểm tra:** VCI có rate limit riêng không? Hiện tại VCI explorer dùng `@AdaptiveController` (delay 0.05-0.1s).

### 2.4. KBS — Hình Mẫu Tốt Nhất (Đồng Ý)

- **Listing:** `_get_full_stock_data()` + filter `type == DER` — robust, p hù hợp với kiến trúc crawler.
- **Quote:** `convert_derivative_symbol()` trong `__init__` — pattern đúng.
- **Điểm yếu:** Dựa vào crawl trang web KBS. Nếu KBS thay đổi cấu trúc HTML/JSON nội bộ, toàn bộ listing và quote sẽ hỏng.
- **Đề xuất:** Thêm caching layer cho `_get_full_stock_data()` (TTL 1 giờ) để giảm tải request và tránh bị block.

---

## 3. Bổ Sung Kiến Trúc

### 3.1. Schema Chuẩn Hóa (Research Plan mục 4.2)

Research plan đề xuất chuẩn hóa nhưng cần cụ thể hơn:

```python
# vnbroker/api/listing.py
from dataclasses import dataclass
import pandas as pd

@dataclass(frozen=True)
class FutureContract:
    symbol: str           # VN30F2606 hoặc 41I1F7000
    organ_name: str       # "VN30 Futures Jul 2026"
    exchange: str         # "HNX"
    expiry_date: str      # "2026-07-17" (ngày đáo hạn thực tế)
    underlying: str       # "VN30" | "VN100" | "GB05" | "GB10"
    krx_format: bool      # True nếu là mã KRX mới

def all_future_indices(self, **kwargs) -> pd.DataFrame:
    ...
```

### 3.2. OHLC Normalization

Research plan đề cập normalize timezone nhưng thiếu:
- DNSE trả về timestamp UTC → cần convert sang UTC+7.
- TCBS trả về timestamp theo VN timezone (UTC+7) → giữ nguyên.
- VCI và KBS format thế nào? Cần khảo sát thêm.
- **Đề xuất:** Thêm `_normalize_ohlc(df: pd.DataFrame, provider: str) -> pd.DataFrame` để đảm bảo output đồng nhất.

### 3.3. Unified KRX Strategy

**Phát hiện mâu thuẫn trong tài liệu:** Research plan khuyên "áp dụng KBS pattern", nhưng critique cũ lại đề xuất "Feature flag". Tôi đề xuất:

1. **Layer 1 — Auto-detect:** Khi khởi tạo `Quote(symbol)`, thử gọi API với cả 2 format (cũ và KRX). Format nào trả về dữ liệu hợp lệ thì dùng.
2. **Layer 2 — Feature flag:** Nếu auto-detect không khả thi (tốn request), dùng `VNBROKER_KRX_FORCE_SYMBOL=true/false`.
3. **Layer 3 — Hardcode mapping:** Cho từng provider, lưu kết quả detect vào constants:
   ```python
   PROVIDER_KRX_MAP = {
       "kbs": True,    # KBS chỉ nhận KRX format
       "tcbs": None,   # Chưa xác định
       "dnse": False,  # DNSE vẫn nhận mã cũ
       "vci": None,    # Chưa xác định
   }
   ```

### 3.4. Caching & Rate Limiting

Cả 3 tài liệu đều thiếu chiến lược caching cho dữ liệu phái sinh:
- **`all_future_indices()`:** Chỉ thay đổi 1 lần/tháng (ngày đáo hạn). Cache TTL = 1 ngày là đủ. Không cần gọi API mỗi lần user request.
- **`history()` (OHLC daily):** Dữ liệu quá khứ không thay đổi. Cache vô thời hạn (cache-aside với Redis).
- **`history()` (OHLC intraday):** Cache TTL = 1 phút.

---

## 4. Rủi Ro Bổ Sung (Ngoài Research Plan mục 4)

| Rủi ro | Mức độ | Ảnh hưởng | Giảm thiểu |
|--------|--------|-----------|-----------|
| **VN30 đáo hạn — thiếu dữ liệu ngày đáo hạn** | Cao | `all_future_indices()` không cập nhật kịp mã mới | Cache TTL ngắn (1h) trong 3 ngày quanh ngày đáo hạn |
| **TCBS thay đổi API futures-insight** | Trung bình | Mất nguồn dữ liệu OHLC tốt nhất | Fallback sang DNSE làm secondary source |
| **DNSE OpenAPI thu phí** | Thấp | Mất luồng đặt lệnh miễn phí | Cần kế hoạch dự phòng (chuyển sang TCBS read-only) |
| **KBS bị chặn crawl** | Cao | Mất 1 provider | Dùng cache dài hơn và cảnh báo sớm |
| **Xung đột format mã giữa các provider** | Trung bình | Symbol mapping sai dẫn đến data sai | Kiểm tra chéo dữ liệu giữa 2+ providers |

---

## 5. Phản Biện Kế Hoạch Triển Khai (Research Plan mục 5)

### Bước 1: Smoke Tests
- **Đồng ý** — cần thiết trước khi code.
- **Bổ sung:** Viết script smoke test tự động ghi lại kết quả (symbol format accepted, response time, error rate) vào file JSON để so sánh sau này.

### Bước 2: Sửa DNSE
- **Đồng ý** — ưu tiên P0.
- **Cảnh báo:** `_fetch_instruments(security_group_id="DER")` — cần kiểm tra DNSE có hỗ trợ filter này không. Nếu không, fallback về lọc client-side.
- **Sửa `history()`:** Không chỉ sửa `type` param. Còn cần kiểm tra `DNSEQuote._INTERVAL_TO_RESOLUTION` có hỗ trợ `1m`, `5m` cho DERIVATIVE không.

### Bước 3: TCBS & VCI KRX
- **Đồng ý** — P1.
- **Lưu ý:** Cần phân biệt giữa "TCBS chấp nhận KRX" và "TCBS **chỉ** chấp nhận KRX". Hai trường hợp này xử lý khác nhau.

### Bước 4: Chuẩn hóa Schema
- **Đồng ý** — P2.
- **Bổ sung:** Nên thêm `FutureContract` dataclass trước, sau đó mới normalize DataFrame.

### Bước 5: Benchmark
- **Đồng ý** — P3.
- **Bổ sung:** Tiêu chí benchmark cần cụ thể: latency (p50/p95/p99), error rate, data consistency (so sánh OHLC giữa các providers), số lượng symbols trả về.

---

## 6. Tóm Tắt Đề Xuất Sửa Đổi

### Critical (cần sửa ngay — trước khi release)
1. **DNSEListing.all_future_indices() — sai endpoint** → gọi `_fetch_instruments(security_group_id="DER")`.
2. **DNSEQuote.history() — hardcode type** → dynamic type dựa trên `get_asset_type()`.

### High Priority
3. **Check KRX compatibility** cho TCBS và VCI — smoke test ngay.
4. **Thêm FutureContract dataclass** — chuẩn hóa output.
5. **Thêm OHLC normalizer** — UTC+7 naive datetime, float rounding.

### Medium Priority
6. **Thêm caching** cho `all_future_indices()` (TTL 1 ngày).
7. **Thêm caching** cho `history()` daily data (cache-aside).
8. **Unified KRX strategy** với feature flag + auto-detect.

### Low Priority
9. **Benchmark** độ tin cậy 4 providers.
10. **Thêm error handling** cho rate limit, timeout, empty response.

---

## 7. Kết Luận

Bộ tài liệu hiện tại (research plan + API research) đã xác định đúng vấn đề và đề xuất hướng giải quyết phù hợp. Các điểm yếu chính cần bổ sung:

1. **Thiếu chi tiết kỹ thuật** — cần cụ thể hóa schema, error handling, caching strategy.
2. **Thiếu dữ liệu định lượng** — rate limit, latency, uptime của từng provider.
3. **Chiến lược KRX chưa thống nhất** — giữa "KBS pattern" và "feature flag".
4. **Thiếu kịch bản fallback** — khi provider A down, chuyển sang provider B thế nào.

Khuyến nghị: **Sửa DNSE (P0) trước**, song song chạy smoke test KRX cho TCBS/VCI, sau đó chuẩn hóa schema ở adapter layer.
