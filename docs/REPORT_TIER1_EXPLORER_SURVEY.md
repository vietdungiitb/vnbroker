# BÁO CÁO KHẢO SÁT CUỐI CÙNG — Tier-1 Explorer (public market data)

**Ngày:** 2026-10-10 · **Phạm vi:** `vnbroker/explorer/` + `vnbroker/core/` + `vnbroker/api/`
**SHA:** `b6a3cc0` · **Chế độ:** khảo sát read-only, 3 agent chạy song song lát cắt rời nhau,
mọi phát hiện nghiêm trọng **PM tự kiểm chứng lại bằng script**
**Baseline gate:** **8/8 PASS** · pytest **1923 passed / 26 skipped** · ruff 0 · mypy 1266→1138

> **Kết luận 1 đoạn:** Kiến trúc định tuyến **tốt hơn nhiều so với mức kỳ vọng thông
> thường** — failover thật, circuit breaker thật, sức khoẻ sống sót qua restart thật.
> Nhưng **3 trong 4 yêu cầu của bạn chưa đạt**, và lý do không nằm ở chỗ khó nhất:
> `scopes`/`rate-limit` chưa có thì thêm cũng được, còn **"người dùng không phải
> quan tâm provider" thì đang HỎNG ở tầng đăng ký**, và **"thông tin luôn đúng bất kể
> provider nào" thì SAI ở 2 nơi, sai âm thầm**.

---

## 1. CHẤM ĐIỂM TỪNG YÊU CẦU — đo, không suy đoán

| # | Yêu cầu của bạn | Trạng thái | Bằng chứng đo được |
|:--|:--|:--|:--|
| 1 | Người dùng **không cần quan tâm provider** | ❌ **CHƯA ĐẠT** | `get_auto_candidates("quote")` = `['vci','kbs']` — **TCBS và DNSE không bao giờ xuất hiện**, kể cả khi DNSE **có key hợp lệ** trong `.env` |
| 2 | Thông tin **chuẩn hoá, đúng bất kể provider** | ❌ **CHƯA ĐẠT** | `intraday()`: TCBS/KBS trả cột `match_type`, **DNSE trả `side`** (`dnse/quote.py:233`). `market_cap` nhân **×1000** mặc định (`snapshot.py:358`) trong khi cả 3 provider khai giá thô là **VND** |
| 3 | Tốc độ cao nhờ **cơ chế bulk** | ⚠ **CÓ NHƯNG HỎNG** | Bulk **không chuẩn hoá** (`bulk.py:114-115` chỉ `pd.concat`) ⇒ `pd.concat` 2 nguồn khác tz rơi về `dtype object`. Không giới hạn kích thước lô |
| 4 | Xoay vòng theo **rate-limit** + **sức khoẻ provider** | ⚠ **MỘT NỬA** | Sức khoẻ: **thật** (cooldown luỹ thừa 5→90s, half-open, SQLite). **Rate-limit: KHÔNG TỒN TẠI** — `x-ratelimit` đọc **0** lần trong `vnbroker/`; `retry-after` đọc **1** lần (SSI, chỉ để nhét vào message) |
| 5 | **Tự chuyển provider thay thế** khi provider không có thông tin | ⚠ **CHỈ 1 TRONG 6 MODULE** | Chỉ `Quote` có failover thật (`data.py:608-718`). `Company/Finance/News/Listing/Trading` khai `AUTO` bị đổi ngay thành provider cứng (`data.py:247-251`) ⇒ **không bao giờ failover** |

---

## 2. PHÁT HIỆN QUAN TRỌNG NHẤT — ba danh sách provider mâu thuẫn nhau

Đo trực tiếp với `.env` thật nạp vào (`.env` của repo **có** `DNSE_API_KEY` + `DNSE_API_SECRET` hợp lệ):

| Nguồn sự thật | Provider cho `quote` | Có lọc credential? |
|:--|:--|:--|
| `ProviderRegistry.list_available()` | `['dnse','kbs','ssi','tcbs','vci']` | ❌ **không** |
| `ProviderPool.get_available_providers()` | `['vci','kbs','dnse']` | ✅ có |
| `source_router.get_auto_candidates()` | **`['vci','kbs']`** | — |

### 2.1 Vì sao TCBS không bao giờ tự lên danh sách

`provider_pool.py:29-33` yêu cầu **cặp** `TCBS_API_KEY` + `TCBS_API_SECRET`.

Đo trong `.env` thật:
```
TCBS_API_KEY       co = False
TCBS_API_SECRET    co = False     <-- biến này production CHƯA TỪNG đọc ở đâu khác
TCBS_AUTH_TOKEN    co = True      <-- biến thật đang có
TCBS_JWT_TOKEN     co = True
```

Kiểm chứng bằng đếm: `TCBS_API_SECRET` xuất hiện **1 lần** trong `vnbroker/` (chính dòng đọc đó) và **7 lần** trong `tests/`. Tức **test tự chích biến giả vào môi trường rồi khẳng định hợp đồng sai của chính nó.**

⇒ Kịch bản Owner mô tả ("TCBS và DNSE có sẵn api key trong env nên có thể tự động đưa vào provider list") **đúng ở DNSE, sai ở TCBS.**

### 2.2 Nhưng ngay cả DNSE cũng không vào `AUTO`

`get_auto_candidates("quote")` = `['vci','kbs']` — **DNSE không có mặt** dù key hợp lệ.
`OPEN_SOURCE_CANDIDATES` (`source_router.py:28-35`) là **danh sách viết cứng**, chỉ SSI
được thêm động (`source_router.py:191-200`).

⇒ **Cơ chế "auto-detect theo .env" có thật, nhưng chỉ nằm trong `ProviderPool`, mà `ProviderPool`
chỉ được dùng ở `api/bulk.py`.** Đường người dùng chính (`api/quote.py` → `common.data.Quote`)
dùng `source_router`, **hoàn toàn không thấy** cơ chế phát hiện env.

### 2.3 Ba module `AUTO` trả về danh sách rỗng

```
get_auto_candidates("screener") -> []
get_auto_candidates("indices")  -> []
get_auto_candidates("live")     -> []
```
Dù registry **có** `screener: ['kbs','ssi','vci']`, `indices: ['ssi']`. Người dùng gọi
`source="AUTO"` cho 3 module này sẽ nhận `ValueError`.

---

## 3. NHỮNG GÌ ĐÃ LÀM TỐT — nói rõ để không bị đánh giá thấp

Đây không phải một codebase yếu. Những thứ sau **có thật, đã chạy, có test**:

| Cơ chế | Bằng chứng |
|:--|:--|
| **Failover thật** | `data.py:686-718` — vòng lặp thử provider, phân biệt lỗi vận hành với lỗi lập trình |
| **Circuit breaker + cooldown luỹ thừa** | `source_router.py:311` — `min(90, 5·2^(n-1))`: 5s→10s→20s→40s→80s→90s |
| **Half-open probe** | `source_router.py:221-230` |
| **Sức khoẻ sống sót qua restart** | `health_store.py:88-135` — SQLite `~/.vnbroker/router_health.sqlite3` |
| **Phân biệt "provider chết âm thầm"** | `data.py:442-481` — frame rỗng có schema ⇒ coi là ngày nghỉ, **không** coi là provider chết. Có test khoá |
| **Bulk chia tải + song song** | `bulk_router.py:139-157` — round-robin symbol + `ThreadPoolExecutor` |
| **Thích nghi số worker theo p95** | `adaptive_controller.py:156-184` — p95 thật `statistics.quantiles(...,n=100)[94]` |
| **Cache có nhận biết provider** | `cache.py:372-386` — khoá theo `module.qualname`, nên `kbs.Listing` không đụng `vci.Listing`. Có test |
| **Không trộn lẫn lỗi lập trình với lỗi provider** | `should_failover` **không** failover với `TypeError`/`ValueError` — chủ ý thiết kế |

**Và một quyết định thiết kế rất đúng** mà nhiều thư viện hay làm sai: frame 0 dòng
**có đủ schema** được coi là *thành công* (ngày nghỉ giao dịch), còn frame thiếu cột mới là
*provider chết* (`data.py:458-461`). Naive thường coi cả hai là lỗi.

---

## 4. LỖI SAI SỐ DỮ LIỆU — im lặng, khó phát hiện nhất

### 4.1 🔴 `market_cap` sai **1000 lần** khi không truyền `price_unit`

```python
# api/snapshot.py:358
multiplier = 1_000 if (price_unit is None or price_unit.upper() != "VND") else 1
```
Mặc định `price_unit=None` ⇒ **nhân 1000**. Nhưng cả **3** provider đều khai giá thô là VND:

```
kbs/trading.py:227    source_unit='VND'
tcbs/trading.py:112   source_unit='VND'
vci/trading.py:136    source_unit='VND'
```

**Không có test nào bắt được**: `tests/unit/api/test_snapshot.py` patch
`@patch.object(MarketSnapshot, "_build_snapshot_df")` — hàm chứa công thức bị thay thế
hoàn toàn, **không bao giờ chạy**.

> **Lưu ý công bằng:** đây là **mâu thuẫn nội bộ đã chứng minh**, chưa chứng minh
> hướng nào đúng ở production. Cần probe API thật để kết luận.

### 4.2 🔴 Cùng khái niệm, **tên cột khác nhau** giữa provider

| Provider | `intraday()` trả cột |
|:--|:--|
| VCI / KBS / TCBS | `time, price, volume, **match_type**, id` |
| **DNSE** | `time, price, volume, **side**` (`dnse/quote.py:233`) |
| SSI | `raise NotImplementedError` |

Người dùng viết `df[df.match_type == "Buy"]` sẽ **hỏng âm thầm** khi AUTO chọn DNSE.

**Vì sao test không bắt**: `tests/contract/test_match_type_contract.py:34-43` **tự dựng
frame đã có sẵn cột `match_type`** rồi đưa vào hàm — nó kiểm *hàm*, không kiểm *provider có
thật sự sinh cột đó không*. DNSE không bao giờ sinh `match_type`, test vẫn xanh.

### 4.3 🔴 Bulk **không** chuẩn hoá — đúng kịch bản test mô tả

`api/bulk.py:114-115` chỉ `pd.concat` + `sort_values`. Frame từ provider khác nhau giữ
nguyên timezone khác nhau ⇒ `pd.concat` rơi về **`dtype object`**.

`tests/contract/test_failover_integration.py:113` có test tên `test_bulk_normalization`
nhưng gọi thẳng `Normalizer.normalize_history` (`:119`) — **không đi qua `BulkRouter`**.
Tên test gợi hình, nội dung thì không kiểm bulk thật.

### 4.4 🟠 `source_unit='VND'` hard-code cho **mọi** provider

`core/utils/transform.py:129` — hàm không nhận tham số provider, dán thẳng `VND`.
Provider nào thật sự trả **nghìn VND** sẽ bị dán nhãn sai và **không** quy đổi.

### 4.5 🟠 Hai bản chuẩn hoá **giống hệt nhau** — vi phạm SSOT

`core/utils/normalizer.py:55-78` và `common/data.py:838-881` thân hàm **giống nhau từng dòng**.
`CLAUDE.md:34-36` gọi `_normalize_quote_result` là *"the single enforcement point"* — **sai**,
có hai điểm. Sửa một bên ⇒ phân kỳ hành vi im lặng.

---

## 5. RATE-LIMIT — yêu cầu của bạn chưa được hiện thực

Đếm trên `vnbroker/` (không tính `docs/`):

| Mục | Số lần | Ý nghĩa |
|:--|--:|:--|
| Đọc header `X-RateLimit-*` | **0** | Không provider nào công bố giới hạn |
| Đọc `Retry-After` | **1** | Chỉ SSI, và **chỉ nhét vào message** — không ngủ, không nạp cooldown |
| `configure_rate_limiter(...)` được gọi | **0** | Token-bucket đường sync = **code chết** (có 15 test bảo vệ thứ không ai dùng) |
| Bộ đếm quota còn lại theo provider | **0** | `health_store` chỉ lưu `failures` + `cooldown_until` |

**Điều đang chạy thật** là *"xoay vòng theo số lần thất bại liên tiếp + cooldown"*, **không phải**
*"theo giới hạn rate-limit"* như bạn mô tả. Hai thứ khác nhau về bản chất.

**Hệ quả cụ thể** (`client.py:328-333`): mọi status ≠200 của VCI/KBS bị đổi thành
`ConnectionError("...429 - Too Many Requests")`, mà `ConnectionError` nằm trong
`per_provider_retry` với `stop_after_attempt(3)` + `wait_exponential(2,10)` ⇒ **gặp 429 mất
~6 giây retry chính provider đó rồi mới chuyển**. Retry một request đã bị throttle làm
nặng thêm tình trạng.

---

## 6. PHẠM VI FAILOVER CHỈ 1 TRONG 6 MODULE

```python
data.py:489   SUPPORTED_SOURCES = (..., "AUTO")   # Quote
data.py:351                                         # StockComponents
```
`Company/Finance/News/Listing/Trading` khai `AUTO` thì bị `_resolve_auto_source`
(`data.py:269-281`) đổi ngay thành provider cứng `candidates[0]` — đọc health store **một
lần lúc khởi tạo rồi không bao giờ xoay vòng nữa**.

Thêm nữa, đường `base.py:156-168` (dùng bởi `api/quote.py`, `api/company.py`, …) gọi
`record_success` **vô điều kiện** (`:161`), thiếu nhánh kiểm frame-rỗng mà `data.py:700-712`
có. ⇒ provider chết-im-lặng được tính là **thành công**, cooldown không kích hoạt.

---

## 7. PHÁI SỬA — theo thứ tự ưu tiên

### Ưu tiên 1 — Bỏ rào cản "người dùng phải biết provider"
| Việc | File:line | Ghi chú |
|:--|:--|:--|
| Cho `AUTO` nhận provider có credential từ `.env` | `source_router.py:28-35,191-200` | hiện là list cứng |
| Sửa cặp biến TCBS cho khớp `.env` thật | `provider_pool.py:30-31` | dùng `TCBS_AUTH_TOKEN`/`TCBS_OPENAPI_API_KEY` thay vì `TCBS_API_SECRET` |
| Để `screener`/`indices`/`live` có `AUTO` | `source_router.py:28-35` | hiện trả `[]` |
| Gộp 3 danh sách về **một** nguồn | `registry` / `provider_pool` / `source_router` | 3 nơi đang mâu thuẫn |

### Ưu tiên 2 — Đúng số (ưu tiên ngang với 1, vì hỏng dữ liệu người dùng)
| Việc | File:line |
|:--|:--|
| Quyết định đơn vị giá thật bằng probe API, sửa `multiplier` | `snapshot.py:358` |
| Thêm test cho `_compute_market_cap` (đang không có) | `tests/unit/api/test_snapshot.py` |
| Ép `match_type` ở tầng chung, kể cả DNSE | `core/utils/transform.py:516` |
| Chuẩn hoá trong `BulkRouter` | `api/bulk.py:114` |

### Ưu tiên 3 — Hiện thực rate-limit thật
| Việc | File:line |
|:--|:--|
| Đọc `X-RateLimit-*` và `Retry-After`, nạp vào `cooldown_until` | `source_router.py`, `health_store.py:26-36` |
| **Không retry** khi gặp 429 — chuyển provider ngay | `common/data.py:666-675` |
| Bật token-bucket hoặc xoá 15 test đang bảo vệ code chết | `core/utils/client.py:30-40` |

### Ưu tiên 4 — Vệ sinh
- `common/data.py` **1876 dòng** = **2,35×** trần 800 (`CLAUDE.md:27`). Cả repo có **12** file vượt (sinh bằng script, lệnh ở §8).
- Gộp 2 bản chuẩn hoá trùng lặp (`normalizer.py:55` ↔ `data.py:838`).
- `core/settings.py` là **cấu hình chết** — không nơi nào import (grep = 0 kết quả).

---

## 8. LỆNH TÁI TẠO — mọi con số trong báo cáo này

```powershell
# Baseline gate (8/8 PASS, 1923 passed)
pwsh -NoProfile -File scripts/check_all.ps1

# Ba danh sach provider — do la noi that nhat cua ba file nay
.venv\Scripts\python.exe -c "import sys;sys.path.insert(0,'.');from vnbroker.core.registry import ProviderRegistry as R;from vnbroker.core.source_router import get_auto_candidates as A;import vnbroker.core.registry as m;m._ensure_providers_loaded();print(R.list_available('quote'));print(A('quote'))"

# TCBS_API_SECRET chi doc o 1 cho production, 7 cho tests
Get-ChildItem -Recurse -Include *.py | Select-String -Pattern 'TCBS_API_SECRET' | Group-Object { $_.Path -match '\\tests\\' } | Select-Object Name,Count

# File vuot 800 dong (ReadAllLines, KHONG dung Measure-Object -Line)
Get-ChildItem -Path "$PWD\*" -Recurse -File -Include *.py |
  Where-Object { $_.FullName -notmatch '\\(\.git|\.venv|site-packages|__pycache__)\\' } |
  ForEach-Object { [pscustomobject]@{ L=([System.IO.File]::ReadAllLines($_.FullName)).Count; P=$_.Name } } |
  Where-Object { $_.L -gt 800 } | Sort-Object L -Descending

# Khong doc gi header rate-limit
Get-ChildItem -Path "$PWD\vnbroker\*" -Recurse -Include *.py | Select-String -Pattern 'x-ratelimit' | Measure-Object | Select-Object -ExpandProperty Count
```

> ⚠ `Get-ChildItem -Path $root -Recurse -Include *.py` **không có ký tự đại diện** sẽ trả
> **0 file** — phải dùng `"$PWD\*"`. Và `Measure-Object -Line` **bỏ dòng trống**, cho
> `data.py` = 1583 thay vì 1876. Hai cái bẫy này đã làm sai số trong lúc khảo sát.

---

## 9. CHƯA XÁC MINH ĐƯỢC

| Việc | Vì sao chưa |
|:--|:--|
| **Đơn vị giá thật của từng provider** | Mọi test đều mock **cùng một con số** cho cả 3 provider ⇒ không suy ra được wire format thật. Mâu thuẫn 4.1 **đã chứng minh**, nhưng **hướng nào đúng thì chưa** |
| Khối lượng là **lô hay cổ phiếu** | `lot_size` được sinh (`dnse/listing.py:33`) nhưng **không nơi nào trong `explorer/*/quote.py` tiêu thụ**. `docs/` không có dòng nào nói rõ |
| Provider nào thật sự gửi header rate-limit | **Chưa phát request HTTP nào** trong đợt khảo sát này |
| `market_cap` ở production | `_compute_market_cap` không có test nào chạy tới |
| Thư viện có tự nạp `.env` không | `python-dotenv` **chưa cài**; `tests/conftest.py` bọc trong `except ImportError` ⇒ im lặng bỏ qua. Người dùng phải nạp `.env` bằng tay |
| `connector/` có provider nào khác không | Ngoài phạm vi lát cắt |

---

## 10. KHUYẾN NGHỊ CỦA PM

1. **Ưu tiên 1 và 2 nên đi song song, cùng đợt** — chúng độc lập file.
2. **Đừng làm ưu tiên 3 trước.** Rate-limit chỉ hữu ích khi đã biết provider nào còn quota.
   Hiện ưu tiên 1 còn chưa xong thì router vẫn chỉ thấy 2 provider.
3. **Ưu tiên 4 (vượt 800L) nên gộp vào ưu tiên 2** vì cùng sửa ở `common/data.py`.
4. Tôi **không đề xuất** xoá `core/exceptions.py` hay `adaptive_controller` dù có phần
   code chết — chúng là **tài liệu ý định thiết kế**, giữ lại rẻ hơn là viết lại.
5. **Cổng chặn hồi quy** (như `check_tcbs_bodies.py` ở Round 4) là cách đúng để bảo vệ
   chuẩn hoá: nó chặn ở mức **payload**, nên test không thể "tự dựng frame rồi khẳng định
   đúng" như `test_match_type_contract.py` đang làm.