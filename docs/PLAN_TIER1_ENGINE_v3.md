# PLAN v3 — TIER 1 DATA ENGINE: sửa để ĐẠT ĐƯỢC DoD của chính nó

- **Task ID:** `TIER1-ENGINE-v3`
- **Planner:** Team Code Leader (supervisor)
- **Ngày:** 2026-10-08
- **Baseline:** `e5d8133` (`origin/dev`, sau merge PR #4 fix-gates)
- **Supersedes:** `docs/PLAN_TIER1_ENGINE.md` (v1, `DRAFT`) · `docs/PLAN_TIER1_ENGINE_v2.md` (v2, verdict `NEED_REVISION`)
- **Bản chất:** v1 đã **code xong** (`b51b2a8` + `16db774`, 5 agent claim `done`). Đây là kế hoạch **sửa sai lệch** giữa DoD §9 của v1 và hành vi thật.

> **v2 → v3:** Stage 2 audit trả `NEED_REVISION`, **8 vấn đề chặn**. Tất cả đã được **tự tái lập bằng thực thi** ở `e5d8133` (xem §1.3). Không vấn đề nào của auditor được chấp nhận mù quáng; cũng không vấn đề nào bị bác bằng lý do suông.

---

## 1. Vì sao có kế hoạch này

### 1.1 Chẩn đoán gốc: bulk **không hoạt động chút nào**

Không phải "gán sai nhãn provider" như v2 mô tả. Đo end-to-end, network bị chặn:

```
BulkAPI.history(["ACB","VNM"]) -> shape (0, 7)
attrs: {'sources_used': {}, 'failed': {}, 'requested': 2, 'returned': 0}
network calls attempted: 0
```

⇒ Mục tiêu v1 §1.6 *"API `Market(auto=True).bulk.history(...)` hoạt động được"* là **sai**. Nó không hoạt động, và nó **không tốn một lần gọi mạng nào** — tức thất bại rất âm thầm.

### 1.2 Ba tầng hỏng độc lập trên đường bulk

Tự tái lập (không đọc code, chạy thật):

```powershell
$env:PYTHONUTF8=1
.\.venv\Scripts\python.exe -c "import vnbroker, vnbroker.api.bulk; from vnbroker.core.registry import ProviderRegistry; print(ProviderRegistry.list_available('quote'))"
# -> []            <-- TAY 1
.\.venv\Scripts\python.exe -c "from vnbroker.core.unified_registry import get_provider; get_provider('quote','kbs')"
# -> ValueError: Provider 'quote/kbs' not found. Available: []     <-- TAY 2
.\.venv\Scripts\python.exe -c "import inspect; from vnbroker.explorer.vci.quote import Quote as V; print(inspect.iscoroutinefunction(V.fetch_multiple))"
# -> True          <-- TAY 3
```

| Tầng | Vị trí @ `e5d8133` | Cơ chế |
|:--|:--|:--|
| **T1** | `vnbroker/core/bulk_router.py:105` | `ProviderRegistry` **rỗng** sau `import vnbroker` — đăng ký chỉ xảy ra khi import `explorer/*` (`explorer/kbs/quote.py:734`). `ProviderRegistry.get` ném `ValueError` ⇒ bắt ở `:106` ⇒ `provider_class = None` ⇒ **`:113` không bao giờ chạy**. |
| **T2** | `vnbroker/core/bulk_router.py:148` | Fallback gọi `unified_registry.get_provider(...)` — registry vẫn rỗng ⇒ `ValueError` ⇒ bị `:153` nuốt. Ngoài ra nếu có class, `:150` gọi `prov.history(sym, …)` trên **class** ⇒ `self` bị bind vào chuỗi symbol. |
| **T3** | `vnbroker/explorer/vci/quote.py:348` | `VCI.fetch_multiple` là **`async classmethod`**. Cách sửa "dùng `fetch_multiple`" mà v2 đề xuất trả **coroutine** ⇒ `isinstance(result, list)` và `dict` đều False ⇒ `return frames` **rỗng** ở `:123`. KBS thì đã là classmethod (`explorer/kbs/quote.py:161`) nên chạy được. |

### 1.3 Bảng tiền đề đã tái lập (Stage 2 audit, tôi tự chạy lại)

| ID | v2 nói | Thực tế | Bằng chứng |
|---|---|---|---|
| R1 | **3** hàm lồng retry | **SAI — 2 hàm** | `git grep @retry e5d8133 -- vnbroker/common/data.py` ⇒ `:669`(intraday), `:696`(price_depth). `:653` là **docstring** của `history`, không phải decorator. `history` không lồng. |
| R1 citations | `:654-659`, `:681-686` | **SAI, lệch 15 dòng** | Hai dòng đó là docstring. |
| R2 | FAIL | **XÁC NHẬN** | `should_failover(exc)` nhận `Exception` (`core/source_router.py:357`); không tầng nào xử lý frame rỗng. `data.py:642-643` `record_success` + `return` ngay cả khi rỗng. |
| R3 | `:113` chết | **ĐÚNG NHƯNG NÔNG** — thêm T1/T2/T3 | §1.2 |
| R4 | `errors[provider]` không set | **KẾT LUẬN ĐÚNG, CƠ CHẾ SAI** | `errors[provider]` **có** được set ở `bulk_router.py:74` khi future ném. Nó rỗng vì `_fetch_batch` nuốt hết trước đó tại `:136`/`:153`. Sửa: bắt lỗi **tại `:136`/`:153`**, không phải ở `:74`. |
| R5 | `interval` không truyền | **XÁC NHẬN** | `BulkRouter.fetch_history` không có tham số `interval`. |
| D7 | `Trading` hardcode KBS | **THIẾU 1 CHỖ** | `api/bulk.py:126` `Listing(source="KBS", …)` **cũng** hardcode. |
| VN-2 | key va chạm | **NẶNG HƠN** | Không chỉ `date`: `["ACB","VNM"] ≡ ["VNM","ACB"]` (không phân biệt thứ tự) và `{"a":1} ≡ {"a":2}`. |
| VN-3 | `acquire` treo | **HƯỚNG SAI** | `acquire(1.0)` trả `False` sau **0,01 ms** — không treo. Chỗ treo thật là `wait()`. AC-10 của v2 nhắm sai hàm. |
| **N2** | session dùng chung nguy hiểm, cookie không khoá | **BỊ BÁC BỎ** | `requests` 2.33.1: `RequestsCookieJar.__init__` đặt `self._cookies_lock = RLock()`; `extract_cookies()` khoá quanh thao tác. A/B 3 vòng: shared **1600/1600, 0 lỗi**. ⇒ **Không được đòi sửa thứ không hỏng.** |
| N2 phần `code chết` | `_thread_local` chết | **XÁC NHẬN** | `git grep _thread_local` ⇒ đúng 1 hit `core/utils/client.py:91`, không nơi nào đọc/ghi. |
| BUDGET | 12 file >800L | **XÁC NHẬN** | đếm `vnbroker/**/*.py`; luật ở `CLAUDE.md:15`. |

### 1.4 Ba lỗi của chính tôi ở v2 (đã ghi, không giấu)

| Lỗi | Xử lý |
|---|---|
| Probe `probe_tier1_dod.py` **không nằm trong repo** ⇒ `3/13` và `T6` không tái lập được, `<probe>` chỉ là placeholder | **v3: probe được commit vào `tests/`** và chạy như một gate thật. |
| R3b probe trả `PASS` nhưng vô nghĩa (frames đến từ fallback, không phải nhánh đang kiểm) | Bỏ hẳn khỏi danh sách. |
| R4 probe lần 1 `NameError` | Đã viết lại, kết quả FAIL giữ nguyên. |

### 1.5 `check-baseline-gates.cjs` trả PASS nhưng vô hiệu

Nó **textual**, so *tên* gate. Chạy lên plan v2: `PASS` kèm `gates named: 0 (none)`. ⇒ **xanh giả**. Vì vậy §4 ghi **exit code thật** của từng gate, không ghi tên. Đây là hazard 9 (script tồn tại ≠ script chạy).

---

## 2. In-scope — 3 slice, file set rời nhau tuyệt đối

### Slice 1 — Bulk thực sự chạy (P0)

| Path | Sửa |
|---|---|
| `vnbroker/core/registry.py` | **T1**: registry phải có provider sau `import vnbroker` (đăng ký lazy nhưng chắc chắn, hoặc `get()` tự nạp). Không dựa vào việc ai đó import `explorer/*` trước. |
| `vnbroker/core/bulk_router.py` | **T2**: dựng provider đúng (truyền `symbol`; gọi `history` trên **instance**). **T3**: `fetch_multiple` async ⇒ chạy qua bridge sync/async. **R4**: bắt lỗi tại `:136`/`:153`, set `errors[provider]`, gọi `health.record_failure`. **R5**: nhận + truyền `interval`. Không nuốt `TypeError`/`AttributeError` (lỗi lập trình phải nổi). |
| `vnbroker/api/quote.py` | Tái dùng bridge sync/async **đã có sẵn** tại `:243-323` cho `fetch_multiple`. *(v1 §3 cấm file này; v3 **gỡ cấm** và ghi lý do — nó là nơi duy nhất đã có mẫu đúng.)* |
| `vnbroker/api/bulk.py` | R5; D7 cho **cả** `Trading` (`:121`) **và** `Listing` (`:126`); D3 (thống nhất với R7, xem §6). |
| `vnbroker/core/unified_registry.py` | Chỉ nếu T2 cần; giữ nhỏ nhất có thể. |
| `tests/unit/core/test_bulk_router.py`, `tests/unit/api/test_bulk_api.py` | +test cho T1/T2/T3/R4/R5/D7 |

### Slice 2 — Failover đúng nghĩa (P0)

| Path | Sửa |
|---|---|
| `vnbroker/common/data.py` | **R1**: gỡ `@retry` ở `:669` (intraday) và `:696` (price_depth) — giữ đúng như `history` đang làm (retry **cho từng provider** trong `_run_with_failover`). **R2**: kết quả rỗng ⇒ coi là provider không phục vụ được ⇒ **không** `record_success`, chuyển provider tiếp. |
| `tests/contract/test_failover_integration.py` | +test: provider trả rỗng ⇒ chuyển provider; **đếm số lần gọi provider** để chứng minh retry không lồng |
| `tests/contract/test_failover_tier1.py` | **Claim bắt buộc** (v2 thiếu — S-1 của audit). File này đang khẳng định `kbs.calls == 3`, `vci.calls == DEFAULT_RETRIES`; sửa R1 sẽ làm đổi nó. |
| `tests/unit/common/test_bulk_normalizer.py` | regression cho `history` |

### Slice 3 — Cache + rate limiter + code chết (P1)

| Path | Sửa |
|---|---|
| `vnbroker/core/utils/cache.py` | VN-2: `_make_key` không bỏ tham số; phân biệt `date` khác nhau, list khác thứ tự, dict khác value. |
| `vnbroker/core/utils/rate_limiter.py` | VN-3: `capacity >= 1.0`; `wait()` nhận `max_wait` và **ném `TimeoutError`** thay vì lặp vô hạn. |
| `vnbroker/core/utils/client.py` | Xoá `_thread_local` **chết** (`:91`). **KHÔNG** sửa session dùng chung — N2 đã bị bác bỏ. Nếu muốn tài liệu hoá, ghi rõ phần đã đo (cookie jar có `RLock`). |
| `vnbroker/core/provider_pool.py` | D3: pool dùng thật **hoặc** bỏ dead code — **một** quyết định, ghi vào commit message. |
| `tests/unit/core/test_cache_key.py`, `test_rate_limiter.py`, `test_connection_pool.py`, `test_provider_pool.py` | +test |

### Slice 0 — Probe trở thành gate thật (supervisor làm, trước Stage 4)

`tests/acceptance/test_tier1_dod.py` — commit vào repo, chạy bằng `pytest`, **không** phải script tạm. Đây là fix cho chính sự cố làm T6 không xác minh được.

---

## 3. Baseline gate — exit code THẬT tại `e5d8133`

| # | Gate | Lệnh | Baseline |
|---|---|---|---|
| G1 | unit+contract | `pytest tests/unit tests/contract -q --timeout=300` | 🟢 0 — `1128 passed, 6 skipped` |
| G2 | full suite | `pytest tests/ --cov=vnbroker --cov-report=xml --cov-report=term-missing --timeout=60 -x` | 🟢 0 — `1173 passed, 30 skipped` |
| G3 | ruff | `ruff check vnbroker tests/unit tests/contract/` | 🟢 0 — `All checks passed!` |
| G4 | mypy baseline | `python scripts/check_mypy_baseline.py` | 🟢 0 — `OK: no new strict errors (baseline 1266, now 1209, fixed 57)` |
| G5 | version sync | `python scripts/check_version_sync.py` | 🟢 0 — `version-sync OK: 3.5.0` |
| G6 | **bulk end-to-end** | probe end-to-end (network blocked) | 🔴 1 — `rows=0, network calls=0` |
| G7 | registry ấn định | `python -c "import vnbroker; ProviderRegistry.list_available('quote')"` | 🔴 1 — `[]` |
| G8 | budget ≤800L | đếm dòng | 🔴 1 — 12 file, max `data.py`=1800 |
| G9 | DoD probe | `pytest tests/acceptance/test_tier1_dod.py` | ⚫ **CHƯA TỒN TẠI** — sẽ tạo ở Slice 0 |
| G10 | CI | `gh pr checks` | ⚫ **`duration_ms: 0`, `steps: []`** — Actions không chạy (billing). 10/10 run gần nhất trên `dev` đều `failure`. **KHÔNG dùng làm tiêu chí nghiệm thu.** |
| G11 | build+dist | `python -m build`; `PYTHONUTF8=1 python scripts/check_dist_contents.py dist/`; `twine check dist/*` | 🟢 0 cả 3 |

> G6/G7/G8 **đỏ trước khi sửa** — đó là lý do chúng tồn tại. Đọc "gate đỏ" mà bỏ qua dòng này là hazard 6.
> G6/G7/G9 thay thế con số `3/13` của v2 **vì con số đó không có script trong repo nên không ai tái lập được.**

---

## 4. Acceptance criteria

### AC-1 — Bulk trả **dữ liệu**, không chỉ "không TypeError"

> Hazard 8: AC-1 của v2 là **proxy** — nó có thể xanh trong khi bulk vẫn trả 0 dòng, đúng trạng thái `e5d8133`. AC này đo **số dòng thật**.

- **Given** `BulkAPI(source="AUTO")`, `requests.Session.request` bị patch để **ném** (chặn mọi lần thoát ra mạng), registry đã đầy
- **When** `api.history(["ACB","VNM"], start=..., end=...)`
- **Then** `len(df) > 0`; `attrs["returned"] == 2`; **`attrs["sources_used"]` ghi provider THỰC SỰ phục vụ** (so với provider mà frame đến từ nó, đo bằng spy)

### AC-2 — Registry ấn định sau `import vnbroker`

- **Given** tiến trình lạnh, chỉ `import vnbroker`
- **When** `ProviderRegistry.list_available("quote")`
- **Then** khác rỗng; và `vnbroker/core/registry.py:83` **không** ném `ValueError` cho provider thật

### AC-3 — Lỗi lập trình không bị giấu

- **Given** provider **class** ném `TypeError` khi dựng, hoặc `history` bind sai `self`
- **When** `_fetch_batch` chạy
- **Then** `TypeError`/`AttributeError` **nổi lên**; không đổi thành `logger.warning`

### AC-4 — Bulk báo lỗi provider (đúng đường nuốt)

- **Given** mọi provider đều ném `RuntimeError` (lỗi mạng)
- **When** `api.history([...])`
- **Then** `attrs["failed"]` **không rỗng**; `HealthRouter.record_failure` được gọi ≥ 1 lần; và lỗi **không** bị nuốt ở `bulk_router.py:136`/`:153`

### AC-5 — `interval` đi hết đường

- **Given** `BulkAPI.history(..., interval="1m")`
- **When** spy `BulkRouter.fetch_history`
- **Then** `interval="1m"` xuất hiện trong lời gọi
- **Ràng buộc tương thích (giải quyết mâu thuẫn audit C-12/AC-12 của v2)**: `BulkRouter.fetch_history` nhận `interval` **keyword-only sau `module`** (`..., module="quote", *, interval="1D"`) để **không** đổi thứ tự tham số vị trí.

### AC-6 — `price_board` theo `self.source` (cả 2 chỗ)

- **Given** `BulkAPI(source="VCI")`
- **When** gọi `price_board(["ACB"])` và đường `symbols=None`
- **Then** `Trading` **và** `Listing` đều dùng `self.source`; **không** có `source="KBS"` hardcode trong `bulk.py`

### AC-7 — Failover kích hoạt khi provider trả rỗng

- **Given** provider #1 trả `DataFrame()` **không ném lỗi**, #2 trả dữ liệu thật
- **When** `Quote("ACB","AUTO").history(...)`
- **Then** #2 **được gọi**; `record_success` **không** được gọi cho #1; frame trả về có dữ liệu

### AC-8 — Retry không lồng, đo bằng **đếm lời gọi**

> Không dùng `inspect.getsource()` — đã chứng minh báo giả: docstring `data.py:653` chứa chuỗi `@retry` dù không có decorator.

- **Given** `Config.DEFAULT_RETRIES=3`, provider đầu luôn ném lỗi mạng, pool 2 provider
- **When** đếm lần gọi provider cho `intraday()` **và** `price_depth()`
- **Then** mỗi hàm **≤ `3 × 2 = 6`**; baseline `e5d8133` là **18**. `history` phải giữ **6**.

### AC-9 — Cache key không va chạm

- **Given** các cặp: `date(2024,1,1)` vs `date(2026,10,8)` · `["ACB","VNM"]` vs `["VNM","ACB"]` · `{"a":1}` vs `{"a":2}`
- **When** so `_make_key`
- **Then** **mọi cặp đều khác nhau**

### AC-10 — Rate limiter: nhắm đúng `wait()`

> `acquire(1.0)` **không** treo (0,01 ms). Chỗ treo thật là `wait()`. AC-10 của v2 nhắm sai hàm.

- **Given** `TokenBucketRateLimiter(rate=0.5)`
- **When** `wait(1.0)`
- **Then** **kết thúc trong < 2s** hoặc **ném `TimeoutError`**; tuyệt đối không treo. Và `acquire(1.0)` trả `True`.

### AC-11 — Không phá hợp đồng công khai

- **Given** bản sửa cả 3 slice
- **When** so `__all__` + chữ ký `vnbroker/api/*`, `vnbroker/core/*` với `e5d8133`
- **Then** không symbol nào bị xoá; tham số mới **đều có default hoặc keyword-only**; thứ tự tham số vị trí không đổi

### AC-12 — Gate bảo vệ thật sự bảo vệ (hazard 9/10)

- **Given** test mới của **mỗi** lỗi
- **When** hoàn nguyên đúng file nguồn về `e5d8133` bằng `git show e5d8133:<file>` (**KHÔNG** `git checkout --` — hazard 11)
- **Then** test **đỏ**; khôi phục thì **xanh**. Ghi kết quả vào `docs/SUMMARY_<agent>.md`.

### AC-13 — Không lệch khỏi baseline đang xanh

- **Given** G1..G5, G11 ở `e5d8133` đều 0
- **When** chạy lại sau khi merge cả 3 slice
- **Then** **vẫn 0**; `pytest tests/unit tests/contract` **≥ 1128 passed**; G6/G7 chuyển từ 1 → 0; G8 **vẫn 1** (có chủ ý, §5 non-goal 6)

---

## 5. Non-goals

| # | Không làm | Vì sao |
|---|---|---|
| 1 | Không sửa provider implementation trong `vnbroker/explorer/*` | T1/T2/T3 sửa **cách gọi + registry**, không sửa provider. |
| 2 | Không sửa `vnbroker/broker/**`, `vnbroker/brokerage/**` | Tier 2, non-goal của v1. Bug P0 ở §7. |
| 3 | Không sửa `vnbroker/core/source_router.py` | Đã có; chỉ nối vào. **Ghi rõ**: quyết định "rỗng = thất bại" đặt ở `data.py` (`_run_with_failover`), **không** ở `should_failover`. |
| 4 | Không sửa `core/utils/transform.py` | `match_type`/ATO-ATC là P1 khác — ticket riêng. |
| 5 | Không đổi dependency/version | v1 §3. |
| 6 | **Không cắt file > 800L** | `data.py`=1800L vi phạm `CLAUDE.md:15`, nhưng cắt 12 file là refactor lớn. **Chấp nhận `data.py` dài thêm.** |
| 7 | **Không "sửa" N2** | Đã bị bác bỏ bằng A/B 1600/1600 + `RLock` trong requests 2.33.1. Sửa thứ không hỏng là tự tạo rủi ro mới. Chỉ xoá `_thread_local` chết. |
| 8 | Không chạy `check_mypy_baseline.py --update` | Xoá gate, không phải sửa gate. |
| 9 | Không dùng GitHub Actions làm nghiệm thu | G10. |
| 10 | ~~Không sửa `vnbroker/api/quote.py`~~ | **v3 GỠ cấm** — file đã có bridge sync/async đúng (`:243-323`), là nơi duy nhất không phải viết lại. Ghi ở đây để không coi là nới phạm vi ngầm. |

---

## 6. D3 / R7 — một lỗi, một chỗ

v2 vừa *sửa* D3 (in-scope) vừa *cấm sửa* R7 (non-goal), **cùng một dòng** `api/bulk.py:66`. Worker sẽ chống lại nhau. v3 gộp:

> `NO_AUTH_PROVIDERS` không bao giờ rỗng ⇒ `raise ConnectionError` ở `api/bulk.py:66` là **unreachable**. Slice 1 **dùng `ProviderPool` thật** trong `history()` và xoá nhánh dead. Slice 3 **không** đụng `provider_pool.py` ngoài việc dọn dead code nội bộ. **Một quyết định, một chủ sở hữu: Slice 1.**

---

## 7. Ngoài phạm vi — phát hiện, KHÔNG sửa

| ID | Mức | Vị trí @ `e5d8133` | Ghi chú đã chỉnh (audit đã bác bỏ phần ngạo nói) |
|---|---|---|---|
| **T1** | **P0** | `vnbroker/connector/dnse/trade.py` | `_require_write` chỉ gọi ở **4** chỗ (`:381`, `:494`, `:677`, `:725`). 9 method ghi (`:548`, `:628`, `:813`, `:950`, `:1101`, `:1119`, `:1141`, `:1164`, `:1206`) nhận `dry_run: bool = False` **mặc định**, forward thẳng, **không gate**. Nhưng `connector/dnse/trade.py` **không** nằm trong non-goal glob `broker/*` của v1 ⇒ việc đẩy sang §7 là quyết định **thuận tiện**. Sửa ~9 dòng, **không slice nào claim file** ⇒ không va chạm. **Khuyến nghị: mở slice 4 riêng.** |
| T4 | P1 | `connector/dnse/core/http_client.py:53-55` | Dry-run envelope chỉ mask `"trading-token"`, header thật là `"Trading-Token"`. **KHÔNG XÁC MINH** ở v3 (audit chỉ kiểm chứng T1, S1). |
| S1 | P1 | `broker/security/redaction.py:54-55`, `:148-159` | `x-api-key`/`x-apikey` chuẩn hoá thành `x_api_key`/`x_apikey` — không entry nào trong set ⇒ cả 2 chết. `redact_headers` chỉ mask `authorization`. **KHÔNG XÁC MINH** ở v3. |
| R6 | P1 | `core/utils/transform.py:200-223`, `:268-274`, `:278` | **KHÔNG XÁC MINH** ở v3. |
| — | P2 | `core/utils/client.py:91` | `_thread_local` chết → đã đưa vào Slice 3 (code chết, không phải race). |

---

## 8. Rollback

Từng slice revert riêng (merge commit, không squash):

```powershell
git revert -m 1 <merge-commit-cua-slice>
```

Hazard 11 — **KHÔNG** dùng `git checkout -- <file>`:

```powershell
Copy-Item vnbroker\core\bulk_router.py $env:TEMP\keep.py
git show e5d8133:vnbroker/core/bulk_router.py > vnbroker\core\bulk_router.py
# ... đo ...
Copy-Item $env:TEMP\keep.py vnbroker\core\bulk_router.py
```

---

## 9. Claim dự kiến (kiểm rời nhau bằng `check-claims.cjs`)

| Slice | Agent | Branch | Files |
|:--|:--|:--|:--|
| 1 | `agent-t1-bulk` | `feat/tier1-bulk` | `vnbroker/core/registry.py`, `vnbroker/core/bulk_router.py`, `vnbroker/core/unified_registry.py`, `vnbroker/api/quote.py`, `vnbroker/api/bulk.py`, `tests/unit/core/test_bulk_router.py`, `tests/unit/api/test_bulk_api.py` |
| 2 | `agent-t1-failover` | `feat/tier1-failover` | `vnbroker/common/data.py`, `tests/contract/test_failover_integration.py`, `tests/contract/test_failover_tier1.py`, `tests/unit/common/test_bulk_normalizer.py` |
| 3 | `agent-t1-netpool` | `feat/tier1-netpool` | `vnbroker/core/utils/cache.py`, `vnbroker/core/utils/rate_limiter.py`, `vnbroker/core/utils/client.py`, `vnbroker/core/provider_pool.py`, `tests/unit/core/test_cache_key.py`, `tests/unit/core/test_rate_limiter.py`, `tests/unit/core/test_connection_pool.py`, `tests/unit/core/test_provider_pool.py` |

7 + 4 + 8 = **19 path, 0 giao nhau**. Slice 3 **không** claim `connection_pool.py` (không còn việc gì sau khi N2 bị bác bỏ) — nhưng được phép sửa **nếu** AC-12 buộc, **phải** báo coordinator trước (hazard 1).

**Hướng phụ thuộc**: Slice 1 và Slice 3 cùng liên quan D3 → **Slice 1 quyết định, Slice 3 làm theo** (§6). Các slice khác độc lập.

---

## 10. Điều kiện Done

- [ ] G1..G5, G11 vẫn 0; **G6, G7: 1 → 0**; G8 vẫn 1 (có chủ ý); G10 `CHƯA CHẠY`
- [ ] `tests/acceptance/test_tier1_dod.py` **có trong repo** và chạy được
- [ ] `pytest tests/unit tests/contract` **≥ 1128 passed**
- [ ] `AUDIT_TIER1_ENGINE_v3.md`: **0 blocker, 0 major, `confidence: high`**
- [ ] AC-1..AC-13 đạt; AC-12 có bằng chứng fail-trước/pass-sau cho **từng** test mới
- [ ] Không file nào ngoài §2 bị sửa
- [ ] Claim 3 slice không giao nhau
- [ ] Merge merge-commit, không squash
- [ ] **Ledger ghi vào `CHANGELOG.md` của repo này** (skill §0), **không** ghi vào ledger của `vninvest`