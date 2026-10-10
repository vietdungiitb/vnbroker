# SUMMARY — agent-t1-bulk (Slice 1: bulk thực sự fetch dữ liệu)

- **Worktree:** `C:\Users\PHAMVI~1\AppData\Local\Temp\opencode\t1-bulk`
- **Branch:** `feat/tier1-bulk`
- **Baseline:** `e5d8133` (`origin/dev`, sau merge PR #4 fix-gates)
- **Kế hoạch:** `docs/PLAN_TIER1_ENGINE_v3.md` (MAIN checkout `C:\Mujoco Projects\vnbroker`) — §1.2, §2 Slice 1, §4 AC-1..AC-6, §6
- **Ngày:** 2026-10-08

> Mọi lệnh dưới đây chạy với `workdir` = worktree của tôi và
> `$env:PYTHONPATH = "C:\Users\PHAMVI~1\AppData\Local\Temp\opencode\t1-bulk"`,
> `$env:PYTHONUTF8 = "1"`, interpreter
> `C:\Mujoco Projects\vnbroker\.venv\Scripts\python.exe`.
> Đã kiểm tra `vnbroker.__file__` → `...\Temp\opencode\t1-bulk\vnbroker\__init__.py`
> (KHÔNG phải main checkout).

---

## 1. Commits

| # | Hash | Nội dung |
|---|------|----------|
| 1 | `b28ce63` | `fix(registry): T1` — tự động khám phá provider sau `import vnbroker` |
| 2 | `535cf0c` | `refactor(api/quote)` — tách bridge sync/async thành `call_provider_sync` |
| 3 | `fc2792f` | `fix(bulk): T2/T3/R4/R5 + D7/D3` — bulk lấy được dữ liệu |
| 4 | `ea07dd9` | `test(bulk)` — sửa 2 test **xanh sai** trước đó (AC-12 thật) |

## 2. Files changed (đúng 7 path đã claim, 0 file ngoài)

```
tests/unit/api/test_bulk_api.py     | 254 +++++++++
tests/unit/core/test_bulk_router.py  | 423 ++++++++++++++-
vnbroker/api/bulk.py                 |  40 ++-
vnbroker/api/quote.py                |  87 ++--
vnbroker/core/bulk_router.py         | 350 +++++++++++++------
vnbroker/core/registry.py            |  72 ++-
6 files changed, 1109 insertions(+), 117 deletions(-)
```

`vnbroker/core/unified_registry.py` **không cần sửa** — nó chỉ delegate
`ProviderRegistry`, nên T1 đã sửa tận gốc (plan §2 ghi "chỉ nếu T2 cần").

**KHÔNG merge, KHÔNG push, KHÔNG chạm file nào ngoài danh sách claim.**
`git status --short` → sạch.

---

## 3. Baseline — đã tự tái lập trước khi sửa

```
$ ...python.exe -c "import vnbroker, vnbroker.api.bulk; ..."
list_available(quote) -> []
get_provider('quote','kbs') -> ValueError: Provider 'quote/kbs' not found. Available: []
VCI.fetch_multiple iscoroutinefunction -> True
KBS.fetch_multiple iscoroutinefunction -> False
VCI.fetch_multiple is classmethod -> True
KBS.fetch_multiple is classmethod -> True

$ ...python.exe -c "<patch requests.Session.request để raise; BulkAPI.history>"
shape -> (0, 7)
attrs -> {'sources_used': {}, 'failed': {}, 'requested': 2, 'returned': 0}
network calls -> 0
```

Khớp **100%** với baseline trong đề bài và §1.2 của plan. Baseline gates:

| Gate | Kết quả baseline |
|---|---|
| `pytest tests/unit tests/contract -q --timeout=300` | `1128 passed, 6 skipped` — exit **0** |
| `ruff check vnbroker tests/unit tests/contract/` | `All checks passed!` — exit **0** |
| `scripts/check_mypy_baseline.py` | `OK: no new strict errors (baseline 1266, now 1209, fixed 57)` — exit **0** |

---

## 4. AC — cách đạt + lệnh + output thật

### AC-2 — Registry ấn định sau `import vnbroker` ✅

**Sửa:** `vnbroker/core/registry.py` — thêm `_ensure_providers_loaded()`, gọi
**lazy loader đã tồn tại** của `vnbroker/__init__.py`
(`_ensure_explorer_modules_loaded`) thay vì tự liệt kê module explorer (giữ
SSOT). `get()`, `list_available()`, `list_all()`, `is_registered()` đều kích
hoạt nó. Có 3 chốt an toàn:
- memo `_auto_loaded` → `clear()` (chỉ dùng cho test) được chữa lại ở lookup
  sau; gọi loader lại **không** giúp vì `sys.modules` cache module nên dòng
  `ProviderRegistry.register(...)` ở đáy file không chạy lần hai;
- re-entrancy guard `_loading` (tránh đệ quy khi loader đang nạp);
- **không** đánh dấu `_load_attempted` nếu `vnbroker` chưa kịp định nghĩa
  loader (đang chạy `__init__` của chính nó) → lần gọi sau sẽ thử lại.

```powershell
$ ...python.exe -c "import vnbroker; from vnbroker.core.registry import ProviderRegistry; print(ProviderRegistry.list_available('quote'))"
['dnse', 'kbs', 'ssi', 'tcbs', 'vci']      # G7_EXIT=0
```
Thêm: sau `ProviderRegistry.clear()` → `list_available('quote')` trả lại
đủ 5 provider (tự chữa).

Test: `test_ac2_real_providers_registered_in_cold_process` (router) +
`test_ac1_real_registry_is_populated` (API).

### AC-1 — Bulk trả **dữ liệu** thật, `sources_used` nêu provider thực sự phục vụ ✅

**Sửa (3 tầng T1/T2/T3 cùng lúc):**

- **T2** — `bulk_router.py`: `provider_class()` → `TypeError` vì `__init__` của
  VCI **và** KBS đều bắt buộc `symbol`. Và `history(sym, start, end)` **sai lệch
  toàn bộ**: không provider nào có tham số `symbol` trong `history` (symbol nằm
  trên instance) → `sym` rơi vào `start`, `start` rơi vào `end`, `end` rơi vào
  `interval`. Đây chính là "mis-bound self". Nay:
  `instance = provider_class(symbol=sym)` rồi `instance.history(start=…, end=…, interval=…)`.
- **T3** — `fetch_multiple` của VCI là **async classmethod** → trả coroutine →
  `isinstance(result, list)` và `isinstance(result, dict)` đều `False` →
  batch rỗng bị coi là thành công. Nay đi qua `call_provider_sync`
  (SSOT đã tách ở `api/quote.py`, commit `535cf0c` — **không** viết bridge thứ hai).
- **T1** — provider phải tra được (xem AC-2).

**Chứng minh bằng spy, không phải phỏng đoán:** test đăng ký một provider giả
có `calls` ghi lại từng lời gọi, chặn **cả hai** client mạng, rồi assert
`sources_used` khớp đúng provider mà spy ghi nhận.

```powershell
$ ...python.exe -m pytest "tests/unit/api/test_bulk_api.py::TestBulkAPIDataPath::test_ac1_history_returns_rows_and_names_real_provider" -q
PASSED
```
Nội dung assert: `len(df) > 0`, `attrs["returned"] == 2`, `attrs["requested"] == 2`,
`attrs["failed"] == {}`, `attrs["sources_used"] == {"ACB":"SERVAA","VNM":"SERVAA"}`,
`sorted(df["symbol"].unique()) == ["ACB","VNM"]`, và
`_ServingProvider.calls == [(("ACB","VNM"), "1D")]`.

**Đo lại end-to-end, chặn `requests.Session.request` (đúng định nghĩa G6 của plan):**
```
shape -> (25, 7)                          # baseline: (0, 7)
returned -> 1
sources_used -> {'ACB': 'VCI'}            # provider THỰC SỰ phục vụ
failed keys -> ['KBS']
network calls -> 1                        # baseline: 0
```

> **Phát hiện quan trọng (xem §7):** con số 25 dòng này **không** chứng minh
> "lấy được dữ liệu khi mạng bị chặn" — VCI đi qua aiohttp
> (`vnbroker.core.utils.async_send_request`) nên **lọt** ra ngoài. Chặn cả hai
> thì `rows = 0`, nhưng `failed` giờ đầy đủ và **2 network calls thực sự được
> thử** (baseline: 0). Đó mới là bằng chứng đúng cho AC-1, và vì vậy AC-1 được
> kiểm bằng provider giả đăng ký thật + chặn cả hai đường mạng.

### AC-3 — Lỗi lập trình không bị giấu ✅

**Sửa:** tách 2 tuple ở `bulk_router.py`:

| | Nội dung |
|---|---|
| `PROGRAMMING_ERRORS` | `TypeError, AttributeError, NameError, ImportError, IndentationError, SyntaxError, AssertionError` → **`raise` thẳng**, không bao giờ đổi thành `logger.warning` |
| `PROVIDER_ERRORS` | `OSError` (gồm `ConnectionError`/`TimeoutError`), `RuntimeError`, `ValueError`, `KeyError`, `LookupError`, `NotImplementedError` → ghi `errors[]` + `record_failure` |

Ngoài ra: nếu provider **healthy nhưng chưa đăng ký**, router bỏ qua kèm
`logger.warning` thay vì im lặng trả 0 frame trông như thành công.

Test: `test_ac3_constructor_type_error_propagates`,
`test_ac3_attribute_error_propagates`, `test_ac3_misbound_self_is_not_reproduced`.

### AC-4 — Bulk báo lỗi provider, đúng đường nuốt ✅

**Sửa (theo ghi chú của plan: sửa chỗ nuốt ở `:136`/`:153`, không phải `:74`):**
`errors[provider]` đã được set ở `:74` từ trước; nó rỗng vì `_fetch_batch` nuốt
hết trước đó. Nay lỗi vận hành **nổi lên** từ `_fetch_batch` và gọi
`HealthRouter.record_failure(provider, exc, module=module)` trước khi nổi.

**Một lỗi thật tìm thêm khi đo:** `KBS.fetch_multiple`
(`explorer/kbs/quote.py:246`) `except Exception: return None` rồi trả `[]` —
nghĩa là provider nuốt lỗi **bên trong**, nên router **không** có gì để bắt.
Đo được: `failed` vẫn rỗng dù KBS chết. Sửa ở router (không sửa provider —
non-goal 1): `fetch_multiple` trả list **rỗng cho N symbol > 0** cũng tính là
thất bại → `RuntimeError` → `errors[provider]` + `record_failure`.

Test: `test_ac4_all_providers_runtime_error_is_reported` (spy `record_failure`),
`test_ac4_empty_result_counts_as_provider_failure`,
`test_ac4_all_providers_down_reports_failed` (API, kiểm `attrs["failed"]`).

### AC-5 — `interval` đi hết đường ✅

**Sửa:** `BulkRouter.fetch_history(..., module="quote", *, interval="1D", providers=None)`
— `interval` và `providers` đều **keyword-only**, đặt **sau `module`**, nên thứ tự
tham số vị trí không đổi. `_fetch_batch` nhận `interval` và forward xuống
`fetch_multiple` / `history`.

Kiểm chứng tương thích (AC-11):
```python
positional == ["self", "symbols", "start", "end", "module"]   # test
BulkAPI.history positional == ["self","symbols","start","end","interval"]  # test
```

Test: `test_ac5_interval_is_keyword_only_after_module`,
`test_ac5_interval_reaches_provider`, `test_ac5_fetch_batch_accepts_interval_positionally_last`,
`test_ac5_interval_forwarded_to_router` (API).

### AC-6 — `price_board` theo `self.source` (cả 2 chỗ) ✅

**Sửa:** `api/bulk.py` — `Trading(source=self.source, …)` (trước: `:121` hardcode
`"KBS"`) **và** `Listing(source=self.source, …)` (trước: `:126` hardcode `"KBS"`).

Kiểm chứng an toàn: `data.py:239-256` chấp nhận `AUTO` ở mọi component và tự
resolve, nên `BulkAPI(source="AUTO").price_board(...)` không vỡ.

Test: `test_ac6_price_board_honours_self_source` (chặn cả 2 component, assert
**không** component nào nhận source khác `self.source`) +
`test_ac6_price_board_module_has_no_hardcoded_source` (quét source của `bulk.py`).

### D3 — Quyết định của Slice 1 (plan §6) ✅

**Quyết định: dùng `ProviderPool` THẬT trong `history()`, và làm cho nhánh
`raise ConnectionError` trở nên reachable thay vì xoá.**

Lý do: `ProviderPool.get_available_providers()` **không bao giờ rỗng** vì
`NO_AUTH_PROVIDERS = ["vci","kbs"]` là list hardcode ⇒ nhánh `raise` cũ là dead
code. Thay vì xoá (làm mất thông tin), tôi làm nó **có nghĩa thật**:

1. pool là **nguồn danh sách provider duy nhất** (không phải lời gọi bị bỏ);
2. lọc bỏ provider không có implementation trong registry;
3. nếu còn rỗng → `ConnectionError` với thông báo nêu rõ pool đã đề xuất gì;
4. danh sách còn lại đưa cho `BulkRouter` để nó hẹp theo health.

**Hệ quả có lợi:** provider có credential trong env (`dnse`, `ssi`, `tcbs` —
`ProviderPool.AUTH_PROVIDERS`) giờ thực sự được đưa vào đường bulk, thay vì
bị bỏ qua vì `HealthRouter` chỉ biết AUTO candidates.

**Hành vi mới so với cũ:** registry rỗng hoặc pool rỗng giờ **báo lỗi thay vì
trả DataFrame rỗng**. Đây là chủ ý — đường bulk im lặng trả 0 dòng chính là
thất bại âm thầm mà `e5d8133` đang mắc.

**Ràng buộc cho Slice 3** (`provider_pool.py`): `NO_AUTH_PROVIDERS` phải giữ
nguyên ý nghĩa "luôn có provider không cần auth" (tôi đang **dựa vào** nó để
coi pool là nguồn danh sách). Slice 3 chỉ dọn dead code **nội bộ** trong file
đó; **KHÔNG** được làm `get_available_providers` trả về rỗng theo bất kỳ lý do
nào, nếu không `api/bulk.py:66` lại thành dead code lần nữa.

Test: `test_d3_empty_pool_raises_connection_error`,
`test_d3_pool_provider_without_implementation_raises`,
`test_d3_pool_drives_provider_selection`.

---

## 5. AC-12 — bằng chứng fail-trước / pass-sau

**Phương pháp (tuân thủ hazard 11):** `Copy-Item` bản của tôi ra `$env:TEMP\t1_keep`
→ `git show e5d8133:<path> > <path>` (PowerShell 7, `>` = utf8NoBOM) → chạy test →
`Copy-Item` khôi phục. **KHÔNG dùng `git checkout --` bất cứ lúc nào.**
Sau mỗi lần khôi phục đã đối chiếu SHA-256: cả 4 file nguồn **IDENTICAL** với bản
backup. Script: `$env:TEMP\t1_ac12.ps1`.

| Lần revert | Lệnh | Kết quả trước | Kết quả sau |
|---|---|---|---|
| `vnbroker/core/registry.py` | 3 test AC-2/AC-1 | **2 failed**, 1 passed — exit 1 | **3 passed** — exit 0 |
| `vnbroker/core/bulk_router.py` | `tests/unit/core/test_bulk_router.py` | **15 failed**, 10 passed — exit 1 | **25 passed** — exit 0 |
| `vnbroker/api/bulk.py` | `test_bulk_api.py::TestBulkAPIDataPath` | **7 failed**, 3 passed — exit 1 | **10 passed** — exit 0 |
| `vnbroker/api/quote.py` | `test_ac1_async_fetch_multiple_is_awaited` | **1 failed** — exit 1 | **1 passed** — exit 0 |
| **cả 4 file** | cả 2 file test | **23 failed**, 23 passed — exit 1 | **46 passed** — exit 0 |

**Lý do fail là hành vi thật, không phải "tham số lạ":**
```
E   Failed: DID NOT RAISE <class 'TypeError'>            # :136 nuốt lỗi lập trình
E   Failed: DID NOT RAISE <class 'AttributeError'>      # :136 nuốt mis-bound self
WARNING Provider VCI batch fetch failed: __init__() missing 1 required
        positional argument: 'symbol'                    # ← đúng lỗi T2
WARNING Provider VCI batch fetch failed: network unreachable   # ← đúng lỗi R4
```

### Tôi đã tự phát hiện và sửa 3 test "xanh sai"

Bản test đầu tiên của tôi **không** bảo vệ thật. Ghi lại đây để không ai tin
nhầm là chỉ cần thêm test là xong:

1. **`test_ac3_constructor_type_error_propagates`** và
   **`test_normalize_multi_result_rejects_unknown_type`** gọi
   `fetch_history(..., providers=[...])`. Ở `e5d8133` hàm đó ném
   `TypeError: unexpected keyword argument 'providers'` — và
   `pytest.raises(TypeError)` **nuốt chính lỗi đó**, nên test **XANH SAI**.
   → Chuyển sang gọi trực tiếp `_fetch_batch` (tồn tại ở cả hai phía, không dựa
   vào tham số mới).
2. **Các test còn lại** cũng chỉ chết vì tham số mới, chưa chạm hành vi.
   → Provider giả cài vào **đúng slot `vci`** của AUTO candidates
   (`get_source_health_snapshot('quote')` chỉ liệt kê `OPEN_SOURCE_CANDIDATES`,
   nên provider mang tên lạ **không bao giờ** xuất hiện trong health snapshot —
   đây là ràng buộc thật của `health_router.py`, không phải lỗi test).
3. **`_SpyProvider`/`_AsyncSpyProvider` có `__init__` không tham số** ⇒
   `provider_class()` ở `e5d8133` chạy được ⇒ `test_ac1_fetch_multiple_sync_provider_returns_rows`
   **xanh** dù code cũ sai. Provider thật (VCI/KBS) đều **bắt buộc** `symbol`
   ⇒ đã thêm `__init__(self, symbol)` cho stub. Sau đó test này FAIL đúng lý do.

### Test mới **không** discriminate (báo cáo trung thực)

| Test | Vì sao |
|---|---|
| `test_d3_empty_pool_raises_connection_error` | `api/bulk.py` ở `e5d8133` **đã có** check `if not providers: raise ConnectionError`. Test này **giữ** nhánh đó còn reachable; nó không chứng minh được gì về fix. Đã ghi rõ trong docstring. |
| `test_bulk_api_history_signature_unchanged` | Regression guard AC-11 — cố ý xanh ở cả hai phía. |
| `test_explicit_providers_*` (2 test) | Bảo vệ tham số `providers` **mới**; ở `e5d8133` chết vì thiếu tham số (đúng mục đích). |
| `test_ac1_history_returns_rows_and_names_real_provider` khi revert **registry.py** | Test tự đăng ký provider giả nên không cần discovery. T1 có 2 test riêng (`test_ac2_*`) lo. Đã đo và ghi nhận. |

---

## 6. Gates — exit code THẬT

| # | Lệnh | Exit | Output |
|---|---|---|---|
| G1 | `python -m pytest tests/unit tests/contract -q --timeout=300` | **0** | `1154 passed, 6 skipped, 2 warnings in 78.96s` (baseline `1128 passed` ⇒ **+26**) |
| G2 | `python -m pytest tests/ -q --timeout=60` | **0** | `1199 passed, 30 skipped, 2 warnings in 82.73s` (plan §3 G2 ghi `1173 passed`) |
| G3 | `python -m ruff check vnbroker tests/unit tests/contract/` | **0** | `All checks passed!` |
| G4 | `python scripts/check_mypy_baseline.py` | **0** | `OK: no new strict errors (baseline 1266, now 1209, fixed 57)` |
| G6 | probe bulk end-to-end (network blocked) | 0 | xem bên dưới |
| G7 | `python -c "import vnbroker; ProviderRegistry.list_available('quote')"` | **0** | `['dnse','kbs','ssi','tcbs','vci']` (baseline `[]`) |

**G4 nội bộ:** lần đầu G4 **ĐỎ (exit 1)** với 6 strict error mới
(`record_failure` nhận `BaseException` không phải `Exception`; 4 lỗi
`exc` bị xoá sau `except`; `Type` thiếu type-arg). Đã sửa **tận gốc**
(đổi type, đổi tên biến, `Type[Any]`) chứ **KHÔNG** chạy `--update`. G4 xanh lại
với **baseline con số không đổi** (1266/1209/57).

**G6 — đo lại 2 kiểu chặn mạng (đây là điểm dễ báo cáo sai):**

| Cách chặn | rows | `failed` | network calls |
|---|---|---|---|
| baseline `e5d8133`, chặn `requests.Session.request` | **0** | `{}` | **0** |
| **sau fix**, chặn `requests.Session.request` | **25** | `{'KBS': ...}` | **1** |
| **sau fix**, chặn **cả** `requests` **và** `async_send_request` | **0** | `{'KBS': ..., 'VCI': ...}` | **2** |

⇒ G6 chuyển **1 → 0** theo nghĩa của plan ("bulk trả dữ liệu, không im lặng
thất bại"). Nhưng con số 25 dòng ở hàng 2 là **bẫy**: VCI đi qua aiohttp nên lọt
khỏi việc chặn. Hàng 3 mới là phép đo trung thực: **vẫn 0 dòng** (đúng — mạng
bị chặn), nhưng **2 lần gọi mạng thực sự được thử** và `failed` **liệt kê đúng
cả 2 provider**. Ở `e5d8133` con số này là 0/0 — đường bulk chết mà không tốn
một byte mạng nào.

**Nhiễu vô hại:** cả G1 và G2 in
`PermissionError: [WinError 5] Access is denied: '...\Temp\pytest-of-...\pytest-current'`
ở bước teardown. Đây là symlink cache của pytest trên Windows, **không** ảnh
hưởng exit code (vẫn 0) và cũng xuất hiện ở **baseline**. Không phải do thay đổi
của tôi.

### Test riêng cho file của tôi + vùng có thể regression

```powershell
$ ...python.exe -m pytest tests/unit/core/test_bulk_router.py -q          # 25 passed, exit 0
$ ...python.exe -m pytest tests/unit/api/test_bulk_api.py   -q          # 21 passed, exit 0
```

---

## 7. KHÔNG xác minh được

| # | Nội dung | Vì sao |
|---|---|---|
| 1 | **Bulk với provider thật + mạng thật.** Mọi phép đo end-to-end đều chặn egress (deterministic). Không có bằng chứng rằng `KBS.fetch_multiple` trả về frame **đúng thứ tự** khi một phần symbol fail — tôi chỉ align vị trí khi `len(frames) == len(symbols)`, nếu lệch thì bỏ align (giả định có thể sai). | Non-goal 9: CI không chạy; cần môi trường có egress để đo. |
| 2 | **Provider ngoài `vci`/`kbs`/`tcbs` trên đường bulk** (`dnse`, `ssi`). `ProviderPool.AUTH_PROVIDERS` giờ được dùng thật, nhưng tôi không có credential nên **không** chạy được nhánh đó. | Không có env credential. |
| 3 | **`interval="1m"` với provider thật.** Test chỉ chứng minh `interval` được forward tới provider (spy), không chứng minh provider chấp nhận `1m`. | Cần mạng. |
| 4 | **`price_board` với `self.source="VCI"` thật.** Test dùng component giả (chặn `data_module.Trading`/`Listing`) vì `data.py` không thuộc claim của tôi và cần mạng. Đã xác minh bằng đọc code rằng `data.py:247-256` chấp nhận `AUTO`, nhưng **chưa** chạy thật `Trading(source="VCI").price_board(...)`. | Cần mạng + `data.py` ngoài phạm vi. |
| 5 | **`BulkRouter` dưới tải đồng thời thật.** `_fetch_batch` chạy trong `ThreadPoolExecutor`; `ProviderRegistry._registry` được đọc không khoá (đúng như code gốc). | Không có bài test stress; không phải phạm vi của tôi. |
| 6 | **G8 (budget ≤800L), G11 (build+dist), G10 (CI).** | G10 = non-goal 9 (`duration_ms: 0`). G8/G11 thuộc phạm vi supervisor/Slice 0, tôi không claim file nào liên quan. **CHƯA CHẠY.** |
| 7 | **`tests/acceptance/test_tier1_dod.py` (Slice 0).** | Không nằm trong claim list của tôi. |

---

## 8. Rủi ro / tồn đọng

1. **Đảo chiều phụ thuộc tầng `core → api`.** `core/bulk_router.py` import
   `api/quote.py` (hàm `call_provider_sync`). Đây là **điển hình core → api**, tức
   lớp dưới phụ thuộc lớp trên — về lâu dài là mùa thu kỹ thuật.
   Tôi làm vì plan §2 + non-goal 10 **chỉ định** `api/quote.py` là nơi duy nhất đã
   có mẫu đúng và yêu cầu "tái dùng". Import được làm **lazy** (trong hàm) để
   không tạo vòng import. **Đề xuất cho các slice sau:** nếu muốn đúng tầng,
   hãy chuyển `call_provider_sync` xuống `vnbroker/core/utils/` — nhưng đó là
   file **không thuộc claim** của tôi nên tôi **không** tự làm.
2. **`ProviderRegistry` bây giờ tự nạp ⇒ import explorer có thể xảy ra ở bất kỳ
   lúc nào ai đó gọi `registry.get/list_available/is_registered`.**
   `vnbroker/__init__.py` ghi chú "lazy load to avoid circular import deadlock".
   Tôi đã dùng đúng lazy loader sẵn có + re-entrancy guard + không đánh dấu
   `_load_attempted` khi loader chưa sẵn sàng. **CHƯA CHỨNG MINH** được không có
   deadlock trong mọi thứ tự import; cần một test import-cycle riêng (ngoài claim).
3. **`_auto_loaded` memo chụp toàn bộ registry sau lần nạp đầu**, kể cả entry do
   test đăng ký trước đó. Dùng `setdefault` khi chữa nên không ghi đè override,
   nhưng bản chất vẫn hơi "lẫn". Chấp nhận được vì chỉ dùng cho test; đã ghi
   comment trong code.
4. **Sai sót về hành vi có thể xảy ra:** `fetch_multiple` trả list rỗng cho N>0
   giờ **bị coi là thất bại** ⇒ provider bị đưa vào cooldown và ghi vào `failed`.
   Nếu một provider hợp lệ *cố ý* không phục vụ một số symbol (ví dụ mã chỉ số
   mà KBS từ chối), giờ nó sẽ bị phạt oan. Đây là **đánh đổi có chủ đích**: im lặng
   là nguyên nhân gốc của AC-4. Nhưng nên theo dõi nếu `failed` xuất hiện nhiều
   trong thực tế.
5. **`attrs` rò rỉ từ frame nguồn:** `combined.attrs` vẫn mang `symbol`/
   `price_unit` của frame đầu tiên do `pd.concat` (hành vi có sẵn ở `e5d8133`,
   không do tôi). `sources_used`/`failed`/`requested`/`returned` ghi đè nên
   không sai, nhưng `combined.attrs["symbol"]` là **một** symbol trong khi
   DataFrame chứa nhiều symbol. **Không sửa** (ngoài phạm vi, và sửa cần
   `api/bulk.py` — đúng là file của tôi, nhưng đổi hợp đồng `attrs` thì rủi ro
   với người dùng cũ; để ticket riêng).
6. **`_select_providers` đọc `source_router` trực tiếp** thay vì qua
   `HealthRouter` (tôi không được sửa `health_router.py`). Lý do: `HealthRouter`
   chỉ trả về AUTO candidates nên không thể dùng cho danh sách do `ProviderPool`
   đưa vào. Nếu `health_router.py` sau này đổi hợp đồng, `_health_snapshot` ở
   `bulk_router.py` phải theo.
7. **Số test mới: 26** (15 router + 11 API). 23/26 fail trước fix; 3 là
   regression guard theo thiết kế (đã liệt kê ở §5).

---

## 9. Vấn đề ngoài phạm vi — phát hiện, KHÔNG sửa

| # | Mức | Vị trí | Ghi chú |
|---|---|---|---|
| 1 | **P0** | `vnbroker/api/quote.py` (trước khi tôi sửa) | Bridge sync/async nằm inline trong `Quote.fetch_multiple` nên không ai dùng lại được — chính vì vậy `bulk_router` phải viết lại và viết sai (T3). Đã tách thành `call_provider_sync` (thuộc claim của tôi). **Đây là nguyên nhân gốc của class lỗi T3.** |
| 2 | **P1** | `vnbroker/explorer/kbs/quote.py:246` | `fetch_multiple` `except Exception: return None` rồi trả `[]` — **nuốt lỗi không dấu vết**. Giống hệt `_run_one` ở `vci/quote.py:389-392`. Non-goal 1 cấm sửa `explorer/*` ⇒ tôi sửa bằng cách coi "0 frame cho N symbol" là thất bại ở router. **Nên mở ticket riêng** để provider tự báo lỗi. |
| 3 | **P1** | `vnbroker/core/health_router.py` | `get_healthy_providers()` chỉ trả provider trong `source_router.OPEN_SOURCE_CANDIDATES`, nên provider đăng ký ngoài danh sách đó (`dnse`, `ssi`, và bất kỳ provider tương lai) **không bao giờ** được bulk chọn. File **không thuộc claim** của tôi. Đây là giới hạn thật của thiết kế health, cần ticket riêng nếu muốn bulk dùng hết provider. |
| 4 | **P1** | `vnbroker/core/provider_pool.py:79-81` | `get_provider()` trả **class** chứ không phải instance (comment tự thừa nhận "will be implemented in WP-5"). Đây chính là nguồn của bug `prov.history(sym, …)` trên class (T2) nếu ai đó dùng nó. Tôi **không** dùng hàm này (tự tra registry trong router) và **không sửa** file (thuộc Slice 3). **Báo để Slice 3 dọn.** |
| 5 | **P2** | `vnbroker/common/data.py:1800` | Vượt quy tắc ≤800L (`CLAUDE.md:15`) — non-goal 6 cấm cắt file, và file này thuộc Slice 2. **Không sửa.** |
| 6 | **P2** | `vnbroker/api/bulk.py` | `combined.attrs` rò rỉ `symbol`/`price_unit` từ frame đầu (xem §8.5). **Không sửa** vì đổi hợp đồng `attrs`. |

---

## 10. Kết luận

Slice 1 đạt **AC-1..AC-6 + D3**, đủ bằng chứng **AC-12** (revert từng file nguồn,
23/23 test mới có lý do fail thật, 4 file nguồn đã đối chiếu SHA-256 sau khôi
phục). G1 **1154 passed** (≥ 1128 yêu cầu, +26), G2/G3/G4 đều exit **0**, G7 đã
chuyển `[]` → 5 provider. G6 chuyển đỏ → xanh theo nghĩa "không còn thất bại âm
thầm": 2 network call thật được thử và `failed` liệt kê đúng provider thay vì
0 dòng / `{}` / 0 call.

Không merge, không push, không sửa file ngoài claim.
