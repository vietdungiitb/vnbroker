# Phản Biện & Xác Minh Tài Liệu DERIVATIVES_CRITIQUE_REPORT.md

**Ngày:** 2026-06-21
**Phương pháp:** Đối chiếu từng luận điểm trong tài liệu với mã nguồn thực tế của `vnbroker`.

---

## Kết Luận Tổng Quan

Tài liệu này **chính xác về các phát hiện chính** nhưng có **3 điểm sai lệch, 2 thiếu sót nghiêm trọng, và 1 khuyến nghị code chưa kiểm chứng**. Chi tiết dưới đây.

---

## 1. Xác Minh Các Phát Hiện

### ✅ 1.1. Claim 2.1 — `convert_derivative_symbol()` crash với KRX format

**Kết luận: ĐÚNG, có bằng chứng mã nguồn.**

- `convert_derivative_symbol()` tại `parser.py:1112-1180`: chỉ check prefix `VN30`, `VN100`, `GB05`, `GB10` (dòng 1136-1140). KHÔNG có check KRX format ở đầu hàm.
- `krx_derivative_pattern` regex tồn tại ở `parser.py:66` và `parser.py:229` nhưng **chỉ dùng trong `get_asset_type()`**, không dùng trong `convert_derivative_symbol()`.
- `KBSQuote.__init__()` (`kbs/quote.py:72-81`) dùng `try/except` để catch lỗi từ `convert_derivative_symbol()` — đúng là anti-pattern như tài liệu nói.

**Bổ sung:** Pattern regex đã có sẵn trong codebase, chỉ cần copy vào đầu hàm `convert_derivative_symbol()` là đủ. Không cần viết lại.

### ✅ 1.2. Claim 2.2 — Return type không đồng nhất (Series vs DataFrame)

**Kết luận: ĐÚNG, nhưng còn nghiêm trọng hơn tài liệu mô tả.**

Xác minh từ mã nguồn:

| Provider | `symbols_by_group()` return | `all_future_indices()` return |
|----------|---------------------------|------------------------------|
| TCBS | `pd.Series` (dòng 196) | `pd.Series` (dòng 251) |
| VCI | `pd.Series` (dòng 261, 301) | `pd.Series` (dòng 304) |
| KBS | `pd.Series` (dòng 260) | `pd.Series` (dòng 401) |
| DNSE | `pd.DataFrame` (dòng 162) | `pd.DataFrame` nhưng **gọi sai `self.indices()`** (dòng 229-231) |

**Vấn đề tài liệu bỏ sót:** `DNSEListing.all_future_indices()` không chỉ trả kiểu khác — nó trả về **dữ liệu sai hoàn toàn** (chỉ số INDEX thay vì hợp đồng tương lai FUTURES). Đây là P0 thực sự chứ không chỉ là chuyện chuẩn hóa schema.

### ✅ 1.3. Claim 2.3 — KRX prefix 41 vs 42 (Options)

**Kết luận: ĐÚNG về mặt kỹ thuật, nhưng premature.**

- Regex `^4[12]...` tại `parser.py:66` và `229` đã support cả 41 và 42.
- `convert_derivative_symbol()` tại dòng 1178 luôn hardcode `f"41{underlying_code}..."`.
- **Thực tế:** Thị trường Việt Nam hiện chưa có Options giao dịch sàn. Đề cập 42 là đúng về mặt thiết kế nhưng chưa cần action ngay.
- **Nên ghi nhận là "technical debt cho tương lai"**, không phải bug hiện tại.

### ✅ 1.4. Claim 2.4 — DNSE resolution cho derivatives

**Kết luận: ĐÚNG, cần smoke test.**

- `DNSEQuote.history()` hardcode `"type": "STOCK"` tại dòng 302 — nếu gọi với mã phái sinh, sẽ gửi `type=STOCK` + `symbol=VN30F2606`, khả năng cao DNSE upstream trả về empty.
- Resolution mapping đã đầy đủ trong `_INTERVAL_TO_RESOLUTION`.
- Cần smoke test để xác nhận DNSE support `1m`, `5m` cho DERIVATIVE.

### ✅ 1.5. Claim về `@cached_listing`

**Kết luận: ĐÚNG, decorator đã có sẵn.**

- `@cached_listing()` defined tại `cache.py:173`.
- Đã dùng trong `VCIListing` (dòng 49, 131) và `KBSListing` (dòng 66, 121).
- **Chưa dùng** trong `DNSEListing` và `TCBSListing` — và chưa dùng cho bất kỳ method `all_future_indices()` nào.
- Cần import `cached_listing` vào DNSE và TCBS listing files trước khi dùng.

---

## 2. Phát Hiện Tài Liệu Bỏ Sót (Omissions)

### ❌ 2.1. Thiếu sót nghiêm trọng: Không phát hiện `DNSEListing.all_future_indices()` trả về SAI DỮ LIỆU

Tài liệu tập trung vào "inconsistent return types" nhưng bỏ qua lỗi nghiêm trọng hơn:

```python
# dnse/listing.py:229-231
def all_future_indices(self, show_log=None) -> pd.DataFrame:
    """Compatibility fallback to indices()."""
    return self.indices(show_log=show_log)  # <-- SAI: trả về index, không phải futures
```

`self.indices()` (dòng 177-215) gọi `get_instruments(index_name="all")` — endpoint dành cho chỉ số chứng khoán (VN-Index, HNX-Index...), hoàn toàn khác với hợp đồng tương lai phái sinh.

**Mức độ ảnh hưởng:** Nếu user gọi `Listing(source="dnse").all_future_indices()`, họ nhận được danh sách chỉ số (VNINDEX, HNXINDEX...) thay vì danh sách futures (VN30F2606...). Dữ liệu hoàn toàn vô dụng.

### ❌ 2.2. Thiếu sót: Không kiểm tra TCBS có auto-convert KRX hay không

Tài liệu Claim 2.1 bàn về KBS pattern nhưng không kiểm tra TCBS:

- `TCBSQuote.__init__()` tại `tcbs/quote.py:97`: `self.asset_type = get_asset_type(symbol)` — gọi đúng.
- Nhưng KHÔNG có `convert_derivative_symbol()` như KBS.
- `TCBSQuote.history()` tại `tcbs/quote.py:366`: dùng `asset_type` parameter để gọi API.
- **Rủi ro:** Nếu TCBS upstream chỉ nhận KRX format, TCBS sẽ fail âm thầm.

### ❌ 2.3. Thiếu sót: `BaseAdapter` không normalize dữ liệu

Tài liệu đề xuất (mục 3, bước 4) sửa `BaseAdapter` để normalize output. Xác minh:

```python
# base.py:29-38
def wrapper(self, *args, **kwargs):
    if hasattr(self, '_call_dynamic_method'):
        return self._call_dynamic_method(method_name, *args, **kwargs)
    if not hasattr(self._provider, method_name):
        raise NotImplementedError(...)
    provider_method = getattr(self._provider, method_name)
    sig = inspect.signature(provider_method)
    filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
    return provider_method(*args, **filtered)  # <-- raw return, ko normalize
```

Đúng — `BaseAdapter._call_dynamic_method()` trả về raw từ provider, không có normalization layer. Đề xuất sửa là hợp lý.

---

## 3. Phản Biện Khuyến Nghị Code (Section 4)

### ⚠️ 3.1. Code fix `convert_derivative_symbol()` — chưa tối ưu

Tài liệu đề xuất thêm pattern guard:
```python
krx_derivative_pattern = re.compile(r'^4[12][A-Z0-9]{2}[0-9A-HJ-NP-TV-W][1-9A-C]\d{3}$')
if krx_derivative_pattern.match(symbol):
    return symbol
```

**Phản biện:** Pattern này đã có sẵn tại `parser.py:66` như global variable? Không — nó được compile inline trong `get_asset_type()`. Nếu copy vào `convert_derivative_symbol()` sẽ có **2 bản copy của cùng pattern** — vi phạm DRY.

**Fix đúng:** Đưa pattern ra global constant ở đầu file, dùng chung cho cả `get_asset_type()` và `convert_derivative_symbol()`.

```python
# parser.py đầu file
_KRX_DERIVATIVE_PATTERN = re.compile(r'^4[12][A-Z0-9]{2}[0-9A-HJ-NP-TV-W][1-9A-C]\d{3}$')
```

### ⚠️ 3.2. Code fix `DNSEListing.all_future_indices()` — chưa kiểm chứng endpoint

Tài liệu đề xuất:
```python
df = self._fetch_instruments(security_group_id="DER")
```

**Phản biện:** Cần kiểm tra:
1. Method `_fetch_instruments()` có chấp nhận tham số `security_group_id` không?
2. DNSE upstream có hiểu `security_group_id=DER` không? (Có thể là `securityGroup=DER` với camelCase)
3. Có fallback nếu DNSE thay đổi API không?

**Khuyến nghị:** Thêm try/except ngay từ đầu, fallback về filter client-side nếu API không support:
```python
try:
    df = self._fetch_instruments(security_group_id="DER")
except Exception:
    df = self._fetch_instruments()
    df = df[df.get("type", "").str.upper() == "DERIVATIVE"]
```

### ⚠️ 3.3. Code fix `DNSEQuote.history()` — OK nhưng thiếu import guard

Tài liệu đề xuất thêm `get_asset_type()` vào `DNSEQuote.history()`. Xác minh:
- `DNSEQuote` hiện tại **không import** `get_asset_type` từ parser.
- `VCIQuote` có import `get_asset_type` (line 25).
- `KBSQuote` có import `get_asset_type` (line 13).
- `TCBSQuote` có import `get_asset_type` (line 19).

**Cần thêm:** Import `from vnbroker.core.utils.parser import get_asset_type` vào `dnse/quote.py`.

---

## 4. Bổ Sung: Các Phát Hiện Mới Khi Đối Chiếu Codebase

### 🔍 4.1. `DNSEListing._fetch_instruments()` có thực sự support filter?

```python
# dnse/listing.py:44-78
def _fetch_instruments(self, security_group_id: Optional[str] = None, ...):
```

Có — method này đã có parameter `security_group_id`. Vậy đề xuất của tài liệu là khả thi.

### 🔍 4.2. `TCBSQuote` dùng endpoint futures-insight — có cần KRX convert?

TCBS quote dùng `GET /futures-insight/v2/stock/bars` với parameter `type=derivative`.
**Chưa rõ** TCBS backend có nhận KRX format không. Cần smoke test.

### 🔍 4.3. `KBSListing.all_future_indices()` có dùng cache?

KBS dùng `@agg_execution` (decorator custom) — không dùng `@cached_listing`.
`all_future_indices()` gọi `symbols_by_group()` → `_get_symbols_by_group_internal()` không cache.
**Đề xuất của tài liệu là đúng** (nên thêm `@cached_listing`).

---

## 5. Tổng Hợp: Verdict Cho Từng Phần

| Mục trong report | Verdict | Chi tiết |
|-----------------|---------|----------|
| **2.1** KRX crash | ✅ Đúng | Có evidence rõ ràng |
| **2.2** Series vs DataFrame | ✅ Đúng + thiếu | Bỏ sót lỗi DNSE trả về sai data |
| **2.3** Options 42 | ✅ Đúng lý thuyết | Nhưng premature, chưa có Options trên sàn VN |
| **2.4** DNSE resolution | ✅ Đúng | Cần smoke test để confirm |
| **3** Bảng Action Plan | ⚠️ Thiếu | Không đề cập P0: DNSE trả về sai data |
| **4.1** KRX pattern guard | ⚠️ Chưa DRY | Nên dùng global constant thay vì recompile |
| **4.2** DNSE all_future_indices | ⚠️ Thiếu fallback | Cần try/except + filter client-side |
| **4.3** DNSE history | ✅ OK | Cần thêm import get_asset_type |
| **5. Kết luận** | ⚠️ Thiếu action | Chưa phân loại rõ urgency của từng lỗi |

---

## 6. Ma Trận Mức Độ Nghiêm Trọng Thực Tế (Sau Khi Xác Minh)

| Issue | Mức độ | File/Location | Loại |
|-------|--------|--------------|------|
| `DNSEListing.all_future_indices()` trả về indices thay vì futures | **CRITICAL** | `dnse/listing.py:229-231` | Wrong data |
| `DNSEQuote.history()` hardcode `type: "STOCK"` | **CRITICAL** | `dnse/quote.py:301-306` | Wrong data |
| `convert_derivative_symbol()` không check KRX format | **HIGH** | `parser.py:1112-1180` | Anti-pattern |
| Return type inconsistency (Series vs DataFrame) | **HIGH** | `*/listing.py` (4 files) | UX inconsistency |
| `@cached_listing` chưa dùng cho derivatives | **MEDIUM** | `*listing.py` | Performance |
| TCBS quote chưa có KRX convert | **MEDIUM** | `tcbs/quote.py:97` | Future-proof |
| Không normalize schema ở BaseAdapter | **MEDIUM** | `base.py:29-38` | Architecture |
| Options prefix 42 chưa support | **LOW** | `parser.py:1178` | Future |

---

## 7. Kết Luận

Tài liệu `DERIVATIVES_CRITIQUE_REPORT.md` có chất lượng tốt — các phát hiện chính (KRX crash, inconsistent return types, DNSE hardcode type) đều **confirmed** từ mã nguồn.

**Cần bổ sung:**
1. 🔴 `DNSEListing.all_future_indices()` trả về indices → đây là lỗi **nghiêm trọng nhất** mà tài liệu bỏ sót.
2. 🟡 Đề xuất code fix cho `convert_derivative_symbol()` vi phạm DRY (pattern bị duplicate).
3. 🟡 Code fix cho `DNSEListing.all_future_indices()` thiếu fallback filter client-side.
4. 🟢 Cần thêm import guard cho `get_asset_type` vào `DNSEQuote`.

**Tổng thể:** Tài liệu đáng tin cậy ~80%. Các phát hiện đúng hướng, nhưng bỏ sót 1 lỗi P0 và có vài khuyến nghị code chưa hoàn chỉnh.
