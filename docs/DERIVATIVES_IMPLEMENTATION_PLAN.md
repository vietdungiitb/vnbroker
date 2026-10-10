# Kế Hoạch Thực Hiện Tích Hợp Dữ Liệu Phái Sinh (Futures) — vnbroker

<!-- TRẠNG THÁI ĐỐI CHIẾU — WP-PLAN-CLEANUP-01, 2026-10-07 -->

> ## ⚠️ Trạng thái đối chiếu (2026-10-07) — KHÔNG đọc các ô `[ ]` bên dưới như việc còn dở
>
> File ghi trạng thái gốc *"CHỜ AUDIT — chưa thực hiện code"* (2026-06-21). Thực tế
> phần phái sinh **đã được triển khai** ở lane broker:
>
> **Đã xác minh bằng lệnh — XONG:**
> `vnbroker/broker/tcbs/derivatives.py` tồn tại · phái sinh SSI trong
> `vnbroker/broker/ssi/` · `pytest tests/unit/broker/tcbs tests/unit/connector/dnse
> tests/unit/explorer/dnse` → **318 passed**.
>
> **CHƯA LÀM:** phần phái sinh DNSE theo phạm vi kế hoạch này.
>
> Cách kiểm lại: `ls vnbroker/broker/tcbs/derivatives.py vnbroker/broker/ssi/`.


**Phiên bản:** 1.0  
**Ngày:** 2026-06-21  
**Cơ sở:** Đã xác minh qua 4 tài liệu + codebase thực tế  
**Trạng thái:** CHỜ AUDIT — chưa thực hiện code

---

## Mục Lục

1. [Tổng Quan Công Việc](#1-tổng-quan-công-việc)
2. [Ma Trận Ưu Tiên](#2-ma-trận-ưu-tiên)
3. [P0 — Critical (Sửa Ngay)](#3-p0--critical-sửa-ngay)
4. [P1 — High Priority](#4-p1--high-priority)
5. [P2 — Medium Priority](#5-p2--medium-priority)
6. [P3 — Low Priority](#6-p3--low-priority)
7. [Kế Hoạch Kiểm Thử (Testing Strategy)](#7-kế-hoạch-kiểm-thử-testing-strategy)
8. [Rủi Ro & Rollback](#8-rủi-ro--rollback)
9. [Danh Sách File Cần Sửa](#9-danh-sách-file-cần-sửa)

---

## 1. Tổng Quan Công Việc

Dựa trên 4 tài liệu nghiên cứu/phản biện và đối chiếu mã nguồn thực tế, có **7 vấn đề** cần sửa, chia làm 4 mức ưu tiên. Mỗi issue được gắn ID để trace.

| ID | Mô tả | File chính | Mức độ |
|----|-------|-----------|--------|
| FIX-001 | `DNSEListing.all_future_indices()` gọi sai `self.indices()` | `dnse/listing.py:229-231` | P0 ❌ |
| FIX-002 | `DNSEQuote.history()` hardcode `type: "STOCK"` | `dnse/quote.py:301-306` | P0 ❌ |
| FIX-003 | `convert_derivative_symbol()` thiếu KRX guard + vi phạm DRY | `parser.py:1112-1180` | P1 ⚠️ |
| FIX-004 | Chuẩn hóa `all_future_indices()` return type → DataFrame | `*/listing.py` (4 files) + `base.py` | P1 ⚠️ |
| FIX-005 | Smoke test KRX compatibility cho TCBS và VCI | TCBS/VCI upstream | P1 ⚠️ |
| FIX-006 | Thêm `@cached_listing` cho derivative methods | `*listing.py` | P2 🔶 |
| FIX-007 | Benchmark độ tin cậy 4 providers cho dữ liệu phái sinh | Test suite | P3 🔷 |

---

## 2. Ma Trận Ưu Tiên

```
P0 [CRITICAL]                  P1 [HIGH]
  FIX-001 DNSE wrong data        FIX-003 DRY KRX pattern
  FIX-002 DNSE hardcode type     FIX-004 Schema normalization
                                  FIX-005 Smoke test TCBS/VCI

P2 [MEDIUM]                    P3 [LOW]
  FIX-006 Caching                 FIX-007 Benchmark
```

**Nguyên tắc:** Làm P0 → P1 → P2 → P3. Không chuyển bước nếu bước trước chưa pass review.

---

## 3. P0 — Critical (Sửa Ngay)

### 3.1. FIX-001: `DNSEListing.all_future_indices()` — Sai endpoint

**Vấn đề:** Dòng 229-231 gọi `self.indices()` trả về chỉ số (VNINDEX, HNXINDEX...) thay vì hợp đồng tương lai.

**Root cause:** `DNSEListing` không override method này. Fallback về `BaseListing` → không có `all_future_indices` → gọi `symbols_by_group` → cũng không có → lộn xuống `indices()`.

**File:** `vnbroker/explorer/dnse/listing.py`

**Spec code:**
```python
# Xóa hoặc comment dòng 229-231 cũ, thay bằng:

def all_future_indices(self, show_log: Optional[bool] = None) -> pd.DataFrame:
    """Lấy danh sách hợp đồng tương lai phái sinh từ DNSE OpenAPI."""
    # Bước 1: Thử lấy trực tiếp từ API với filter security_group_id="DER"
    df = self._fetch_instruments(security_group_id="DER")
    
    # Bước 2: Nếu API không support filter hoặc trả về rỗng → fallback client-side
    if df.empty or "symbol" not in df.columns:
        df_full = self._fetch_instruments()
        if not df_full.empty and "type" in df_full.columns:
            df = df_full[df_full["type"].str.upper() == "DERIVATIVE"].reset_index(drop=True)
        else:
            df = pd.DataFrame()
    
    if show_log or self.show_log:
        logger.info("DNSE all_future_indices: %d hợp đồng", len(df))
    return df
```

**Cơ chế fallback** (theo phản biện của user):
- `_fetch_instruments()` đã tự bọc `try/except` và trả về `pd.DataFrame()` empty khi lỗi (dòng 89-91).
- Do đó không cần `try/except` ở caller.
- Dùng `df.empty` check để phát hiện API trả về rỗng.
- Dùng `df.empty or "symbol" not in df.columns` để phát hiện cả trường hợp API trả về data nhưng không đúng format.

**Kiểm tra:**
- Unit test: gọi `DNSEListing().all_future_indices()` → kiểm tra cột `symbol` có chứa `VN30F` hoặc `41I` prefix.
- Regression: `DNSEListing().all_symbols()` vẫn hoạt động bình thường.

---

### 3.2. FIX-002: `DNSEQuote.history()` — Hardcode `type: "STOCK"`

**Vấn đề:** Dòng 301-306 luôn gửi `"type": "STOCK"` — với mã phái sinh, DNSE upstream trả về empty hoặc lỗi.

**Root cause:** `DNSEQuote` không gọi `get_asset_type()` như các provider khác (VCI, KBS, TCBS đều gọi).

**File:** `vnbroker/explorer/dnse/quote.py`

**Thay đổi 1 — Thêm import (đầu file, sau dòng 16):**
```python
from vnbroker.core.utils.parser import get_asset_type
```

**Thay đổi 2 — Sửa history() method (dòng 301-306 cũ → mới):**
```python
        # Xác định asset type động dựa trên symbol
        asset_type = get_asset_type(sym)
        type_param = "STOCK"
        if asset_type == "derivative":
            type_param = "DERIVATIVE"
        elif asset_type == "index":
            type_param = "INDEX"

        query = {
            "type": type_param,
            "resolution": resolution,
            "from": from_ts,
            "to": to_ts,
        }
```

**Kiểm tra:**
- Gọi `DNSEQuote("VN30F2606").history(interval="1D")` với DNSE_API_KEY thật → kiểm tra không empty.
- Gọi `DNSEQuote("VNM").history(interval="1D")` → regression, vẫn trả về data cổ phiếu.

---

## 4. P1 — High Priority

### 4.1. FIX-003: `convert_derivative_symbol()` — Thiếu KRX guard + DRY

**Vấn đề:**
- Hàm `convert_derivative_symbol()` (parser.py:1112) không check đầu vào đã là KRX format chưa → throw ValueError.
- Pattern `krx_derivative_pattern` compile inline ở 2 nơi (parser.py:66, 229) → vi phạm DRY.

**File:** `vnbroker/core/utils/parser.py`

**Thay đổi 1 — Thêm global constant (sau dòng 3 `import re`, trước class/functions):**
```python
_KRX_DERIVATIVE_PATTERN = re.compile(
    r'^4[12][A-Z0-9]{2}[0-9A-HJ-NP-TV-W][1-9A-C]\d{3}$'
)
```

**Thay đổi 2 — Sửa `get_asset_type()` tại 2 vị trí (dòng 66 và 229):**
```python
# Thay: krx_derivative_pattern = re.compile(...)
# Bằng: (đã là global constant, xóa dòng compile)
if _KRX_DERIVATIVE_PATTERN.match(symbol):
    return 'derivative'
```

**Thay đổi 3 — Sửa `convert_derivative_symbol()` (thêm guard ở đầu hàm, sau dòng 1121):**
```python
    symbol = symbol.upper()

    # Nếu đã là mã KRX chuẩn → return luôn, không cần convert
    if _KRX_DERIVATIVE_PATTERN.match(symbol):
        return symbol

    # Logic cũ bên dưới...
```

**Kiểm tra:**
- `convert_derivative_symbol("41I1F7000")` → `"41I1F7000"` (idempotent).
- `convert_derivative_symbol("VN30F2606")` → `"41I1F7000"` (hoặc tương đương).
- `get_asset_type("41I1F7000")` → `"derivative"` (regression).

---

### 4.2. FIX-004: Chuẩn hóa `all_future_indices()` return type → DataFrame

**Vấn đề:**
- TCBS, VCI, KBS trả về `pd.Series` (chỉ symbol).
- DNSE trả về `pd.DataFrame` (nhưng sai data — đã fix ở FIX-001).
- User nhận output không đồng nhất.

**File:** `vnbroker/base.py`

**Thay đổi — Thêm normalization layer trong `BaseAdapter._call_dynamic_method()`:**

```python
def _call_dynamic_method(self, method_name, *args, **kwargs):
    """Gọi provider method + normalize output."""
    provider_method = getattr(self._provider, method_name)
    sig = inspect.signature(provider_method)
    filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
    result = provider_method(*args, **filtered)
    
    # Normalize: nếu method là all_future_indices và result là Series → DataFrame
    if method_name == "all_future_indices" and isinstance(result, pd.Series):
        result = result.to_frame("symbol")
        result["exchange"] = "HNX"
        result["organ_name"] = result["symbol"].apply(_build_future_name)
    
    return result
```

**Hàm helper (thêm trong base.py hoặc parser.py):**
```python
def _build_future_name(symbol: str) -> str:
    """Xây dựng tên hợp đồng từ symbol.
    Ví dụ: 'VN30F2606' → 'VN30 Futures Jun 2026'
           '41I1F7000' → 'VN30 Futures Jul 2026'
    """
    # Parse từ symbol cũ hoặc KRX
    from vnbroker.core.utils.parser import get_derivative_maturity_date
    # ...logic mapping...
```

**Kiểm tra:**
- Gọi `Listing(source="tcbs").all_future_indices()` → DataFrame với 3 cột: symbol, exchange, organ_name.
- Gọi `Listing(source="kbs").all_future_indices()` → same format.
- Gọi `Listing(source="dnse").all_future_indices()` → same format (sau FIX-001).

---

### 4.3. FIX-005: Smoke Test KRX Compatibility — TCBS & VCI

**Vấn đề:** Chưa rõ TCBS và VCI upstream chấp nhận mã cũ (VN30F2606) hay mã KRX mới (41I1F7000).

**File:** Không sửa code — chạy smoke test thủ công.

**Kế hoạch test:**

```
Test Case 1: TCBS history() với mã cũ
  Input: TCBSQuote("VN30F2606").history(interval="1D")
  Expected: DataFrame có data
  Actual: ? (cần test)

Test Case 2: TCBS history() với mã KRX
  Input: TCBSQuote("41I1F7000").history(interval="1D")
  Expected: DataFrame có data nếu TCBS support KRX
  Actual: ? (cần test)

Test Case 3: VCI history() với mã cũ
  Input: VCIQuote("VN30F2606").history(interval="1D")
  Expected: DataFrame có data
  Actual: ? (cần test)

Test Case 4: VCI history() với mã KRX
  Input: VCIQuote("41I1F7000").history(interval="1D")
  Expected: DataFrame có data nếu VCI support KRX
  Actual: ? (cần test)
```

**Kết quả mong đợi và hành động:**

| Kết quả smoke test | Hành động |
|-------------------|-----------|
| Cả TCBS và VCI đều chấp nhận mã cũ | Giữ nguyên, theo dõi |
| TCBS chỉ nhận KRX, VCI nhận cả hai | Thêm `convert_derivative_symbol()` vào `TCBSQuote.__init__()` |
| Cả hai đều chỉ nhận KRX | Thêm convert cho cả TCBS và VCI Quote |
| Cả hai đều chấp nhận cả hai format | Giữ nguyên, thêm feature flag để sau này force KRX |

---

## 5. P2 — Medium Priority

### 5.1. FIX-006: Thêm `@cached_listing` cho derivative methods

**Vấn đề:** `all_future_indices()` gọi API mỗi lần, trong khi danh sách futures chỉ thay đổi 1 lần/tháng (ngày đáo hạn).

**File:** `vnbroker/explorer/dnse/listing.py` và `vnbroker/explorer/tcbs/listing.py`

**Thay đổi** — Thêm decorator:

```python
# dnse/listing.py — thêm import (đầu file)
from vnbroker.core.utils.cache import cached_listing

# Trên method all_future_indices():
@cached_listing(ttl_seconds=86400)  # 1 ngày
def all_future_indices(self, show_log: Optional[bool] = None) -> pd.DataFrame:
    ...

# tcbs/listing.py — tương tự
from vnbroker.core.utils.cache import cached_listing

@optimize_execution("TCBS")
@cached_listing(ttl_seconds=86400)
def all_future_indices(self, show_log: Optional[bool] = False) -> pd.Series:
    ...
```

**Lưu ý:** VCI và KBS đã import `cached_listing`, chỉ cần thêm decorator.

**Kiểm tra:**
- Gọi 2 lần liên tiếp `all_future_indices()`, lần 2 không gọi API thật (kiểm tra log hoặc mock).

---

## 6. P3 — Low Priority

### 6.1. FIX-007: Benchmark độ tin cậy 4 providers

**File:** `tests/test_derivatives_benchmark.py` (tạo mới)

**Spec test:**
```python
"""
Benchmark các provider cho dữ liệu phái sinh.
"""
BENCHMARK_CASES = [
    {"provider": "tcbs", "symbol": "VN30F2606", "interval": "1D"},
    {"provider": "dnse", "symbol": "VN30F2606", "interval": "1D"},
    {"provider": "vci",  "symbol": "VN30F2606", "interval": "1D"},
    {"provider": "kbs",  "symbol": "41I1F7000", "interval": "1D"},
]

METRICS = ["latency_p50", "latency_p95", "error_rate", "row_count"]
```

**Tiêu chí đánh giá:**
- Latency p50 < 2s, p95 < 5s.
- Error rate < 5%.
- Data consistency: OHLC giữa các providers có tương đồng không (> 90% match)?
- Số lượng futures symbols trả về từ `all_future_indices()`: 4 mã (F1M, F2M, F1Q, F2Q).

---

## 7. Kế Hoạch Kiểm Thử (Testing Strategy)

### 7.1. Unit Tests (cho từng FIX)

| FIX | Test case | Expected |
|-----|-----------|----------|
| FIX-001 | `DNSEListing().all_future_indices()` returns DataFrame | Cột `symbol` chứa futures symbols |
| FIX-001 | Fallback khi API trả về empty | DataFrame rỗng, không crash |
| FIX-002 | `DNSEQuote("VN30F2606").history(interval="1D")` | DataFrame 6 cột, không empty |
| FIX-002 | `DNSEQuote("VNM").history(interval="1D")` regression | Vẫn hoạt động như cũ |
| FIX-003 | `convert_derivative_symbol("41I1F7000")` | `"41I1F7000"` (idempotent) |
| FIX-003 | `convert_derivative_symbol("VN30F2606")` | KRX format |
| FIX-003 | `get_asset_type("41I1F7000")` | `"derivative"` |
| FIX-004 | `Listing(source="tcbs").all_future_indices()` | DataFrame 3+ cột |
| FIX-004 | `Listing(source="vci").all_future_indices()` | DataFrame 3+ cột |
| FIX-004 | `Listing(source="kbs").all_future_indices()` | DataFrame 3+ cột |
| FIX-006 | Gọi cached method 2 lần | Lần 2 dùng cache (mock verify) |

### 7.2. Integration Tests

```python
# tests/test_integration_derivatives.py
"""
Test tích hợp: cần API key thật.
Bỏ qua (skip) nếu không có biến môi trường.
"""
@pytest.mark.skipif(not os.getenv("DNSE_API_KEY"), reason="Cần DNSE_API_KEY")
def test_dnse_futures_integration():
    lst = DNSEListing()
    df = lst.all_future_indices()
    assert not df.empty
    assert "symbol" in df.columns
```

### 7.3. QA Gates (trước khi merge)

- [ ] P0 tests pass.
- [ ] P1 tests pass.
- [ ] Regression: `pytest tests/` không có test nào fail ngoài expected.
- [ ] Lint: `ruff vnbroker/explorer/dnse/` không lỗi.
- [ ] Type check: `mypy vnbroker/explorer/dnse/` không lỗi mới.

---

## 8. Rủi Ro & Rollback

### Rủi ro đã biết

| Rủi ro | FIX liên quan | Xác suất | Giảm thiểu |
|--------|--------------|---------|-----------|
| DNSE OpenAPI không support `security_group_id=DER` | FIX-001 | Trung bình | Fallback client-side đã được thiết kế |
| DNSE upstream reject `type=DERIVATIVE` với 1m/5m | FIX-002 | Thấp | Dùng interval "1D" cho derivatives nếu intraday không support |
| TCBS/VCI thay đổi API sau smoke test | FIX-005 | Thấp | Feature flag + cập nhật mapping |
| Cache trả về data cũ sau ngày đáo hạn | FIX-006 | Cao (3 ngày/tháng) | TTL ngắn hơn (1h) trong tuần đáo hạn |

### Rollback plan

Mỗi FIX là một commit riêng biệt:

```
git checkout -b feat/derivatives-p0-dnse
# sửa FIX-001, FIX-002
git commit -m "fix(p0): sửa DNSE listing và quote cho derivatives"

git checkout -b feat/derivatives-p1-krx
# sửa FIX-003
git commit -m "fix(p1): DRY KRX pattern + guard cho convert_derivative_symbol"

git checkout -b feat/derivatives-p1-schema
# sửa FIX-004
git commit -m "fix(p1): chuẩn hóa all_future_indices() return type"

git checkout -b feat/derivatives-p2-cache
# sửa FIX-006
git commit -m "feat(p2): thêm cached_listing cho derivative methods"
```

Nếu cần rollback: `git revert <commit_hash>` từng FIX, không ảnh hưởng chéo.

---

## 9. Danh Sách File Cần Sửa

| File | Thay đổi |
|------|---------|
| `vnbroker/core/utils/parser.py` | Thêm `_KRX_DERIVATIVE_PATTERN` global, sửa `get_asset_type()` (2 chỗ), sửa `convert_derivative_symbol()` |
| `vnbroker/explorer/dnse/listing.py` | Sửa `all_future_indices()`, thêm import `cached_listing` |
| `vnbroker/explorer/dnse/quote.py` | Thêm import `get_asset_type`, sửa `history()` dynamic type |
| `vnbroker/base.py` | Thêm normalization trong `_call_dynamic_method` |
| `vnbroker/explorer/tcbs/listing.py` | Thêm `@cached_listing` |
| `vnbroker/explorer/vci/listing.py` | Thêm `@cached_listing` |
| `vnbroker/explorer/kbs/listing.py` | Thêm `@cached_listing` |
| (mới) `tests/test_derivatives_benchmark.py` | Benchmark 4 providers |

---

## Phụ Lục: Sơ Đồ Thực Hiện

```
Tuần 1: P0                            Tuần 2: P1
┌─────────────────────┐              ┌──────────────────────┐
│ FIX-001 DNSE Listing│──────┐      │ FIX-003 DRY KRX     │
│ FIX-002 DNSE Quote  │      │      │ FIX-005 Smoke test   │
└─────────────────────┘      │      └──────────────────────┘
                             │              │
                             ▼              ▼
                      ┌──────────────────────────┐
                      │ Review + Integration Test │
                      └──────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                    ▼
          ┌─────────────────┐                  ┌─────────────────┐
          │ FIX-004 Schema  │                  │ FIX-006 Cache   │
          │ (P1 - Tuần 2)   │                  │ (P2 - Tuần 3)   │
          └─────────────────┘                  └─────────────────┘
                    │                                    │
                    └──────────────┬─────────────────────┘
                                   ▼
                        ┌─────────────────────┐
                        │ FIX-007 Benchmark   │
                        │ (P3 - Tuần 4)       │
                        └─────────────────────┘
```

---

*Kế hoạch đã được xây dựng dựa trên phân tích mã nguồn thực tế và phản biện kỹ thuật từ 4 tài liệu trong thư mục `docs/`. Chờ phê duyệt trước khi thực hiện code.*
