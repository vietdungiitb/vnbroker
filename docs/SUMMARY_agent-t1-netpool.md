# SUMMARY — agent-t1-netpool (Slice 3: cache key, rate limiter, dead code)

- **Agent:** `agent-t1-netpool` · **Branch:** `feat/tier1-netpool`
- **Worktree:** `C:\Users\PHAMVI~1\AppData\Local\Temp\opencode\t1-netpool`
- **Baseline:** `e5d8133` · **HEAD sau khi làm:** `b4f8414` · **7 commit**
- **Plan:** `docs/PLAN_TIER1_ENGINE_v3.md` §2 Slice 3 · §4 AC-9/AC-10/AC-11/AC-12 · §5 non-goal 6+7 · §6
- **Phạm vi:** 8 path đã claim, `git diff e5d8133 --stat` = **đúng 8 file**, không đụng file nào ngoài danh sách.

> **Môi trường đã kiểm tra TRƯỚC khi sửa gì:** `PYTHONPATH` trỏ worktree, `python -c "import vnbroker"`
> in ra `…\opencode\t1-netpool\vnbroker\__init__.py` (không phải main checkout).

---

## 1. Tóm tắt

Sửa 3 lỗi đã tái lập được bằng thực thi (VN-2 cache key, VN-3 rate limiter, code chết), **không**
sửa shared session (non-goal 7), và tìm thêm **1 lỗi nặng hơn VN-2** trong chính `cache.py` mà plan
không có: hai provider khác nhau dùng chung một ô cache trong **24 giờ**. Lỗi đó đã được sửa ở
commit riêng để revert độc lập nếu coordinator không đồng ý.

| Hạng mục | Kết quả |
|---|---|
| AC-9 cache key không va chạm | ✅ đạt (13 test mới) |
| AC-10 `wait()` không treo, `acquire(1.0)` trả `True` | ✅ đạt (9 test mới) |
| Dead code `_thread_local` | ✅ xoá, `git grep` = 0 hit |
| D3 `provider_pool.py` | ✅ một quyết định: **giữ class, xoá `get_provider` chết** |
| AC-11 hợp đồng công khai | ⚠️ 0 symbol thêm, 1 symbol xoá (`ProviderPool.get_provider`), 1 chữ ký đổi (`wait` +`max_wait` có default) |
| AC-12 fail-trước/pass-sau | ✅ 3/3 file nguồn có bằng chứng; `client.py` **không tái lập được** bằng test (xem §6) |
| G1/G2/G3/G4 | ✅ exit 0, `1160 passed` (baseline `1128`) |

---

## 2. Commit

| # | SHA | Nội dung |
|---|---|---|
| 1 | `c732499` | `fix(cache)` VN-2/AC-9 — `_make_key` giữ toàn bộ tham số |
| 2 | `6e01926` | `fix(cache)` namespace key theo module/qualname (lỗi **ngoài plan**) |
| 3 | `b2f43ff` | `fix(rate_limiter)` VN-3/AC-10 — `capacity >= 1 token`, `wait(max_wait=…)` |
| 4 | `1632450` | `chore(client)` xoá `_thread_local` chết, giữ nguyên shared session |
| 5 | `a381050` | `chore(provider_pool)` D3 — giữ class, xoá `get_provider` chết |
| 6 | `efc9a17` | `test(connection_pool)` guard chốt N2 (không sửa code) |
| 7 | `b4f8414` | `fix(cache)` thêm type argument cho generic để G4 xanh |

Mỗi commit một lỗi; commit 2 tách riêng để revert được nếu cần.

## 3. File đã đổi

```
tests/unit/core/test_cache_key.py       | 237 +++++-   +17 test
tests/unit/core/test_connection_pool.py |  75 +++      +3 test (guard, KHÔNG phải bằng chứng)
tests/unit/core/test_provider_pool.py   |  52 +++      +3 test
tests/unit/core/test_rate_limiter.py    | 111 +++      +9 test
vnbroker/core/provider_pool.py          |  10 --       xoá get_provider
vnbroker/core/utils/cache.py            |  73 ++-      _encode_value + _cache_namespace
vnbroker/core/utils/client.py           |  13 +-       xoá _thread_local + import threading
vnbroker/core/utils/rate_limiter.py     |  57 ++-      MIN_CAPACITY + wait(max_wait)
8 files changed, 603 insertions(+), 25 deletions(-)
```

---

## 4. Tái lập lỗi TRƯỚC khi sửa (probe ngoài repo)

Probe: `C:\Users\PHAMVI~1\AppData\Local\Temp\opencode\probe_t1_netpool.py` (**không** nằm trong repo).

**VN-2 — cache key va chạm.** Không so chuỗi key suông, mà **ghi thật rồi đọc thật**:

```
key(date(2024,1,1)) == key(date(2026,10,8)) == 'all_symbols'      -> True
key(['ACB','VNM'])  == key(['VNM','ACB'])    == 'all_symbols'      -> True
key({'a':1})        == key({'a':2})          == 'all_symbols'      -> True
ghi duoi key(2024-01-01), doc key(2026-10-08) -> {'payload': 'data as of 2024-01-01'}   CORRUPTED=True
ghi ['ACB','VNM'],           doc ['VNM','ACB'] -> 'ACB-then-VNM'                          CORRUPTED=True
ghi {'a':1},                 doc {'a':2}       -> 'value-for-a=1'                         CORRUPTED=True
```

**VN-3 — rate limiter.** Đo cả hai hàm vì plan v2 nhắm sai:

```
rate=0.5 -> capacity=0.5
acquire(1.0) -> False trong 0,0069 ms      <-- KHONG treo
wait(1.0) returned within 3s? False        <-- treo that, vo han
```

**Control (để chắc cache vẫn hit):** `_make_key('func','a',1,2.5,True,None)` ổn định, gọi 2 lần → hit.

**Sau khi sửa, cùng probe:**

```
date       key_equal=False  key='all_symbols|date:2024-01-01'
list-order key_equal=False  key='all_symbols|list:2:[ACB,VNM]'
dict-value key_equal=False  key='all_symbols|dict:1:{a=1}'
3 ca doc cross-key -> None, CORRUPTED=False
rate=0.5 -> capacity=1.0 ; acquire(1.0) -> True ; wait(1.0) within 3s? True
control: stable key True, second get -> 'hit'
```

---

## 5. AC theo AC

### AC-9 — cache key không va chạm ✅

Lệnh: `pytest tests/unit/core/test_cache_key.py -q --timeout=60` → **25 passed, exit 0**.

| Cặp AC-9 | Test | Trước | Sau |
|---|---|---|---|
| `date(2024,1,1)` vs `date(2026,10,8)` | `test_date_arguments_do_not_collide` | FAIL `'all_symbols' != 'all_symbols'` | PASS |
| `["ACB","VNM"]` vs `["VNM","ACB"]` | `test_list_order_is_part_of_the_key` | FAIL `'f' != 'f'` | PASS |
| `{"a":1}` vs `{"a":2}` | `test_dict_values_are_part_of_the_key` | FAIL `'f' != 'f'` | PASS |

Trường hợp dương (AC-9 yêu cầu "cache vẫn phải hit"):
- `test_same_arguments_still_produce_one_stable_key` — cùng tham số → cùng key
- `test_cache_still_hits_for_repeated_non_primitive_arguments` — 3 lần gọi khác tham số chỉ
  tính **3** lần vào thân hàm; trước fix chỉ **1** (`assert 1 == 3`) vì mọi tham số gộp làm một key.
- `test_cache_key_*` cũ (8 test có sẵn) vẫn xanh ⇒ không phá hợp đồng format `k=v`, không rò địa chỉ bộ nhớ.

### AC-10 — rate limiter nhắm đúng `wait()` ✅

Lệnh: `pytest tests/unit/core/test_rate_limiter.py -q --timeout=60` → **15 passed, exit 0**.

| Yêu cầu | Test | Kết quả |
|---|---|---|
| `wait(1.0)` kết thúc < 2 s | `test_wait_returns_within_two_seconds` | PASS |
| hoặc ném `TimeoutError`, không bao giờ treo | `test_wait_raises_timeout_instead_of_hanging` | PASS (`TimeoutError`) |
| `acquire(1.0)` trả `True` | `test_acquire_one_token_succeeds_on_a_slow_limiter` | PASS |
| `capacity >= 1.0` | `test_capacity_is_never_below_one_token` | PASS |
| `wait()` có `max_wait` hữu hạn | `test_wait_default_max_wait_is_a_finite_bound` | PASS (`30.0`) |
| `max_wait` được tôn trọng | `test_wait_honours_max_wait_on_a_drained_bucket`, `test_wait_succeeds_when_tokens_arrive_in_time` | PASS |

**Kỹ thuật quan trọng:** test "không được treo" chạy `wait()` trên **daemon thread + `join(deadline)`**
và assert thread đã kết thúc. Nhờ vậy AC-12 chạy được: lần "fail-trước" **không treo cả suite**
(6,82 s), thay vì treo vô hạn.

### Dead code — `_thread_local` ✅

```powershell
git grep -n _thread_local     # trước: vnbroker/core/utils/client.py:91 (1 hit, không đọc/ghi)
git grep -n _thread_local     # sau:  exit 1, không dòng nào
```

`import threading` (`client.py:16`) bị xoá theo vì dùng **duy nhất** ở dòng 91 (ruff F401 sẽ bắt).

### D3 — `provider_pool.py`: một quyết định ✅

**Quyết định: `ProviderPool` DÙNG THẬT → giữ nguyên class. Chỉ xoá dead code BÊN TRONG nó
(`get_provider`).**

Bằng chứng class dùng thật:
- `vnbroker/api/bulk.py:37` → `self._provider_pool = ProviderPool()`
- `vnbroker/api/bulk.py:64` → `self._provider_pool.get_available_providers("quote")`
- `tests/unit/api/test_bulk_api.py:89-93` assert `api._provider_pool is not None`
- đo: `pool.get_available_providers('quote') -> ['vci', 'kbs']`

Bằng chứng `get_provider` là code chết:
- **0 caller**: `git grep -n "\.get_provider(" -- vnbroker tests` chỉ ra `unified_registry.py:33`
  và `:187`, cả hai là `UnifiedRegistry.get_provider`. `bulk_router.py:148` cũng gọi
  `unified_registry.get_provider`, **không** phải method của pool.
- comment trong thân: *"This will be implemented in WP-5"* — placeholder.
- tham số `symbol` không dùng trong thân hàm.
- **trái docstring**: docstring nói *"Create a provider instance"* nhưng trả
  `ProviderRegistry.get(...)` — tức **class**. Đo tại `e5d8133`: registry rỗng
  (`list_available('quote') -> []`) nên `pool.get_provider('vci','quote') -> None` **100% số lần**.

Tôi **không** đụng `api/bulk.py` (decision D3 về file đó thuộc Slice 1, plan §6).

---

## 6. AC-12 — bằng chứng fail-trước / pass-sau

Quy trình: copy file nguồn ra `$env:TEMP` → `git show e5d8133:<path>` ghi đè (byte-exact bằng
`subprocess` + `write_bytes`, tránh PowerShell redirect mã hoá lại) → chạy test → khôi phục bản
đã sửa → `git diff --exit-code` xác nhận khôi phục đúng bằng HEAD → chạy lại.
**Không dùng `git checkout --` lần nào.**

### 6.1 `vnbroker/core/utils/cache.py` → `tests/unit/core/test_cache_key.py`

```
restored cache.py to e5d8133: 9203 bytes sha256=54d8a86ab095df5a
FAIL-BEFORE: 13 failed, 12 passed          exit 1
PASS-AFTER : 25 passed                      exit 0   (git diff --exit-code = 0, đúng HEAD)
```

13 test đỏ (chi tiết lỗi từng test):

| Test | Lỗi quan sát được |
|---|---|
| `test_date_arguments_do_not_collide` | `assert 'all_symbols' != 'all_symbols'` |
| `test_list_order_is_part_of_the_key` | `assert 'f' != 'f'` |
| `test_dict_values_are_part_of_the_key` | `assert 'f' != 'f'` |
| `test_list_and_tuple_are_distinguished` | `assert 'f' != 'f'` |
| `test_datetime_and_date_are_distinguished` | `assert 'f' != 'f'` |
| `test_nested_arguments_are_distinguished` | `assert 'f' != 'f'` |
| `test_kwarg_container_values_are_distinguished` | `assert 'f' != 'f'` |
| `test_unknown_object_types_are_distinguished_without_addresses` | `assert 'f' != 'f'` |
| `test_cache_still_hits_for_repeated_non_primitive_arguments` | `assert 1 == 3` |
| `test_cache_does_not_serve_another_dates_payload` | `assert 'payload-2024-01-01' is not None` |
| `test_cache_does_not_serve_another_list_order_payload` | `assert 'payload-acb-vnm' is not None` |
| `test_cache_does_not_serve_another_dict_payload` | `assert 'payload-a=1' is not None` |
| `test_cached_listing_does_not_cross_serve_same_named_provider_methods` | `assert 'FROM-KBS' == 'FROM-VCI'` |

4 test xanh ở cả hai vòng ⇒ **guard**, không phải bằng chứng:
`test_cache_key_*` cũ (8), `test_same_arguments_still_produce_one_stable_key`,
`test_cached_listing_does_not_cross_serve_across_cache_types`,
`test_cached_listing_still_caches_the_same_provider_method`,
`test_cached_listing_still_honours_arguments`.

### 6.2 `vnbroker/core/utils/rate_limiter.py` → `tests/unit/core/test_rate_limiter.py`

```
restored rate_limiter.py to e5d8133: 1219 bytes sha256=cbf4d0b7e107ac3d
FAIL-BEFORE: 9 failed, 6 passed, 6,82 s    exit 1     (khong treo suite)
PASS-AFTER : 15 passed                      exit 0     (git diff --exit-code = 0)
```

| Test | Lỗi quan sát được |
|---|---|
| `test_capacity_is_never_below_one_token` | `assert 0.5 >= 1.0` |
| `test_explicit_small_capacity_is_raised_to_one_token` | `assert 0.1 >= 1.0` |
| `test_acquire_one_token_succeeds_on_a_slow_limiter` | `assert False is True` |
| `test_wait_returns_within_two_seconds` | `wait(1.0) was still blocked after 2s` |
| `test_wait_raises_timeout_instead_of_hanging` | `wait(2.0) hung instead of raising` |
| `test_wait_honours_max_wait_on_a_drained_bucket` | `expected TimeoutError, got TypeError(... unexpected keyword 'max_wait')` |
| `test_wait_succeeds_when_tokens_arrive_in_time` | `expected …, got TypeError(... unexpected keyword 'max_wait')` |
| `test_wait_default_max_wait_is_a_finite_bound` | `KeyError: 'max_wait'` |
| `test_zero_max_wait_still_hands_out_available_tokens` | `TypeError(... unexpected keyword 'max_wait')` |

### 6.3 `vnbroker/core/provider_pool.py` → `tests/unit/core/test_provider_pool.py`

```
restored provider_pool.py to e5d8133: 2935 bytes sha256=c7baa29e396e54ef
FAIL-BEFORE: 1 failed, 8 passed           exit 1
PASS-AFTER : 9 passed                      exit 0     (git diff --exit-code = 0)
```

| Test | Lỗi | Ghi chú |
|---|---|---|
| `test_dead_get_provider_is_gone` | `assert True is not false` | **phân biệt được** |
| `test_pool_keeps_the_api_bulk_depends_on` | — | guard (xanh cả 2 vòng) |
| `test_pool_still_reports_auth_providers` | — | guard (xanh cả 2 vòng) |

### 6.4 `vnbroker/core/utils/client.py` — **không tái lập được bằng test**

Việc xoá một biến **module-level không dùng** không có observable phân biệt được bằng test: không
hàm nào đọc nó, nên không test nào có thể đỏ trước/xanh sau. Tôi **không viết test `hasattr` cho
một biến private chỉ để có bằng chứng đỏ** — đó là đệm số. Bằng chứng là `git grep` chạy trước và
sau (§5). Nói rõ thay vì giấu.

### 6.5 `vnbroker/core/utils/connection_pool.py` — **test KHÔNG phải bằng chứng**

Tôi **không sửa file này**: `git diff e5d8133 --stat -- vnbroker/core/utils/connection_pool.py` → rỗng.
3 test thêm vào `test_connection_pool.py` là **guard đặc tính hóa (characterization)**: chúng xanh
**trước và sau**, nên theo đúng yêu cầu tôi **không** trích dẫn chúng làm bằng chứng AC-12 hay
bằng chứng cho bất kỳ thay đổi nào. Mục đích duy nhất: ghim kết quả đo của N2 để agent sau không
"sửa" code concurrent đang đúng chỉ vì một tài liệu nói sai.

---

## 7. Gate — exit code thật

Baseline đo trước khi sửa, tại `e5d8133` trên chính worktree này:

| # | Gate | Baseline | Sau khi sửa | Exit |
|---|---|---|---|---|
| G1 | `pytest tests/unit tests/contract -q --timeout=300` | `1128 passed, 6 skipped` (101,32 s) | **`1160 passed, 6 skipped`** (70,59 s) | **0** ✅ ≥ 1128 |
| G2 | `pytest tests/ -q --timeout=60` | — | **`1205 passed, 30 skipped`** (76,41 s) | **0** ✅ |
| G3 | `ruff check vnbroker tests/unit tests/contract/` | `All checks passed!` | `All checks passed!` | **0** ✅ |
| G4 | `python scripts/check_mypy_baseline.py` | `OK: no new strict errors (baseline 1266, now 1209, fixed 57)` | `OK: no new strict errors (baseline 1266, now 1209, fixed 57)` | **0** ✅ |
| G5 | `python scripts/check_version_sync.py` *(chạy thêm, không yêu cầu)* | — | `version-sync OK: 3.5.0` | **0** ✅ |

`1160 − 1128 = 32` test mới = 17 (cache) + 9 (rate limiter) + 3 (connection pool) + 3 (provider pool). ✅ khớp.

**G4 từng FAIL một lần rồi mới xanh** — tôi ghi lại vì đây là bằng chứng gate thật sự bảo vệ:

```
FAIL: 2 NEW mypy --strict errors (baseline 1266, now 1211, fixed 57):
  + vnbroker/core/utils/cache.py :: Missing type arguments for generic type "Callable" [type-arg]
  + vnbroker/core/utils/cache.py :: Missing type arguments for generic type "tuple"   [type-arg]
exit 1  ->  commit b4f8414 sửa Callable[..., Any] / tuple[Any, ...]  ->  exit 0
```

Số `now` quay về đúng **1209** ⇒ không lỗi mới, không lỗi cũ nào bị che mất.

**G10 (CI) = CHƯA CHẠY**: Actions tắt ở đây (`duration_ms: 0`) — mọi gate trên đều chạy local.
Không gate nào ở trên là "PASS suông": đều lấy từ exit code thật.

### AC-11 — hợp đồng công khai (đo bằng AST, `e5d8133` vs HEAD)

```
### vnbroker/core/utils/cache.py
(khong co thay doi public API)

### vnbroker/core/utils/rate_limiter.py
  CHANGED  TokenBucketRateLimiter.wait: (self, tokens: float=1.0)  ->  (self, tokens: float=1.0, max_wait: float=DEFAULT_MAX_WAIT)

### vnbroker/core/utils/client.py
(khong co thay doi public API)

### vnbroker/core/provider_pool.py
  REMOVED  ProviderPool.get_provider(self, name: str, module: str, symbol: Optional[str]=None)

SUMMARY added=0 removed=1 changed=1
```

- `max_wait` **có default** và nối **sau** `tokens` ⇒ thứ tự tham số vị trí không đổi, không phá
  call site nào. Đúng ràng buộc AC-11.
- `cache.py`: hàm mới (`_encode_value`, `_cache_namespace`) đều có tiền tố `_` ⇒ public API không đổi.
- **Ngoại lệ duy nhất:** `ProviderPool.get_provider` bị xoá. Đây đúng là điểm giao giữa AC-11 với
  §2 Slice 3 + §6 (cho phép dọn dead code nội bộ `provider_pool.py`). Tôi **nêu rõ thay vì giấu**:
  nếu coordinator ưu tiên AC-11, `git revert a381050` là đủ.

---

## 8. Xác nhận: KHÔNG đổi hành vi shared session

**Tôi không thay đổi bất kỳ hành vi nào của shared HTTP session, và đây là quyết định có chủ đích.**

- `vnbroker/core/utils/connection_pool.py`: **không sửa** (`git diff e5d8133` rỗng).
- `_get_thread_session()` giữ nguyên thân hàm, vẫn trả **một** session dùng chung cho mọi thread.
  Tôi chỉ thêm docstring ghi lại phép đo và cảnh báo đừng "sửa" lại.
- `send_request` / `send_request_direct` không đổi dòng nào.

**Vì sao tôi không sửa, dù tài liệu trước bảo sửa:** non-goal 7 (§5) nói rõ và tôi tự đo lại:

```
requests 2.33.1
RequestsCookieJar._cookies_lock  ->  RLock        (dat trong __init__)
8 thread x 200 cookie khac nhau  ->  1600/1600 cookie, 0 that lac
```

`http.cookiejar.CookieJar.set_cookie` và `extract_cookies` đều khoá quanh thao tác ⇒ dùng chung
session là an toàn. Sửa code **đúng** vì một tài liệu nói nó sai là cách tạo regression: đổi lấy
một connection pool mới cho từng thread (chi phí thật) để tránh một race đã được bác bỏ.

3 guard test trong `test_connection_pool.py` chốt lại kết quả đo này, không dùng mạng.

---

## 9. Lỗi phát hiện NGOÀI phạm vi — phát hiện, KHÔNG sửa

### 9.1 P0 — `async_client.py` dùng async context manager trên object không có nó

```python
vnbroker/core/utils/async_client.py:360    async with RATE_LIMITER:
```

Đo trực tiếp:

```
TokenBucketRateLimiter.__mro__ = (TokenBucketRateLimiter, object)
hasattr(TokenBucketRateLimiter, '__aenter__') -> False
hasattr(TokenBucketRateLimiter, '__enter__')  -> False
```

⇒ mọi request đi qua `async_client` ném `AttributeError: __aenter__` ngay tại `:360`.
`RATE_LIMITER` được export ở `core/utils/__init__.py:60,138`.

**Vì sao tôi không sửa:** `async_client.py` **không** nằm trong danh sách claim của tôi và **không**
nằm trong non-goal của plan ⇒ không slice nào claim nó. Thêm `__aenter__`/`__aexit__` cũng là *tính
năng mới*, nằm ngoài VN-3, và tôi không có test nào chứng minh nhánh async chạy được. Thêm nó vào
đây là tự mở rộng phạm vi. **Đề xuất: mở slice riêng.**

### 9.2 P1 — cache key chung giữa các provider (lỗi **nặng hơn VN-2**, đã sửa ở commit 2)

VN-2 của plan chỉ liệt kê 3 cặp (`date`/`list`/`dict`). Tôi tìm thêm một va chạm **không cần tham số
đặc biệt nào cả** — chỉ cần gọi hàm không tham số:

```
vnbroker/explorer/kbs/listing.py:18   class Listing      (listing.py:66  @cached_listing() def all_symbols)
vnbroker/explorer/vci/listing.py:17   class Listing      (listing.py:49  @cached_listing() def all_symbols)

key(kbs.Listing.all_symbols) == key(vci.Listing.all_symbols) == 'all_symbols'  -> True
doc duoi key cua VCI -> [{'symbol': 'FROM-KBS'}]
```

Cả hai provider dùng **chung một** `_listing_cache` toàn cục, tên phương thức trùng nhau, `self` bị
`_make_key` bỏ qua, và key chỉ gồm `func.__name__`. Provider gọi trước sẽ trả DataFrame của mình cho
provider sau trong suốt `Config.LISTING_CACHE_TTL` = **86 400 s = 24 giờ** (không phải 1 giờ).

Đã sửa bằng `_cache_namespace(func, args)` tiền key bằng `module.qualname` (và `module.qualname` của
class `self` khi gọi dưới dạng method). `@wraps` truyền tiếp `__module__`/`__qualname__` qua
`agg_execution`/`optimize_execution` — đã kiểm chứng:

```
kbs -> vnbroker.explorer.kbs.listing.Listing.all_symbols
vci -> vnbroker.explorer.vci.listing.Listing.all_symbols
ssi -> vnbroker.explorer.ssi.listing.SSIListing.all_symbols      all distinct: True
```

**Sửa ngay trong `cache.py`**, **không** sửa `explorer/*` (non-goal 1). Tách commit riêng để revert
độc lập. Ghi chú: `kbs` và `vci` đều tên class là `Listing`, nên nếu chỉ dùng tên class thì vẫn
va chạm — phải dùng `__module__` mới tách được.

### 9.3 Mức độ "tiềm ẩn" của VN-2 — nói thẳng, không thổi phồng

VN-2 **như plan mô tả là tiềm ẩn ở `e5d8133`**: tôi đọc 13 vị trí decorate
`@cached_listing`/`@cached_industry` (`dnse/listing.py:230`, `kbs/listing.py:66,121,190,388`,
`vci/listing.py:49,63`, `tcbs/listing.py:253`, `ssi/indices.py:66,102`, `ssi/listing.py:83`,
`ssi/securities.py:97`, `ssi/trading.py:90`) và **tất cả tham số khai báo đều là primitive**
(`str`/`bool`/`Optional[str]`). Nhưng ba hàm có `**kwargs: Any`
(`ssi/listing.py:85`, `ssi/indices.py:67`, `ssi/securities.py:99`) nên caller truyền `date`/`list`
vẫn va chạm ngay. Còn lỗi §9.2 thì **không tiềm ẩn** — cần gọi `all_symbols()` là đã hỏng.

### 9.4 Ghi chú kỹ thuật nhỏ

- `client.py:180` gọi `_rate_limiter.wait()` khi limiter được bật opt-in. Sau VN-3, lệnh này **ném
  `TimeoutError` sau 30 s** thay vì treo vô hạn. Đây chính là điều VN-3 muốn, nhưng là **thay đổi
  hành vi thật** ở một call site, nên tôi ghi ra đây.
- `async_client.py:90` dựng limiter với `Config.RATE_LIMIT_RPM` (mặc định 300) ⇒ capacity giữ nguyên
  300, **không đổi**.
- Tôi **cố ý không** thêm validate `rate > 0`: `core/utils/__init__.py:60` import `RATE_LIMITER`
  lúc import package, nên raise ở constructor sẽ biến thành `ImportError` mới cho toàn bộ cây khi
  env var đặt sai. `wait()` đã có giới hạn ⇒ `rate <= 0` sẽ ra `TimeoutError` thay vì treo.

---

## 10. `CHƯA CHẠY`

| Hạng mục | Lý do |
|---|---|
| G6/G7/G8/G9/G11 (bulk end-to-end, registry, budget ≤800L, DoD probe, build+dist) | **CHƯA CHẠY** — ngoài 4 gate được giao cho Slice 3, phụ thuộc `explorer/*`/`api/*` thuộc Slice 1; G8 vốn đã đỏ có chủ ý (non-goal 6) |
| G10 (GitHub Actions) | **CHƯA CHẠY** — Actions tắt ở đây (`duration_ms: 0`) |
| Nhánh **async** của `async_client.py` sau khi thêm `__aenter__` | **CHƯA CHẠY** — tôi không sửa file đó (§9.1) |
| AC-12 cho `client.py` | **không tái lập được** bằng test — xem §6.4, bằng chứng là `git grep` |
| Hành vi thật của `cached_listing` với **network thật** | **CHƯA CHẠY** — mọi test cache chạy offline với stub; tôi không gọi provider thật |
| AC-1..AC-8, AC-13 | **Ngoài slice** — thuộc Slice 1/2 |

---

## 11. Rủi ro

1. **Đổi hành vi `wait()` → `TimeoutError`** ở `client.py:180`. Đây là chủ ý, nhưng nếu ai đó
   bật limiter với `rate` quá nhỏ, giờ nhận exception thay vì treo. Đã ghi trong commit `b2f43ff`.
2. **Commit `6e01926` (namespace) là thay đổi ngoài plan.** Nó sửa lỗi thật nhưng chạm hành vi cache
   dùng chung của 13 method trên 6 provider. Rủi ro còn lại: nếu một decorator nào đó **không** dùng
   `@wraps`, `__module__` sẽ trỏ nhầm và hai provider có thể va chạm lại (fail-open về hành vi cũ,
   không hỏng mới). Đã có test chốt; nếu coordinator muốn giữ Slice 3 gọn, revert riêng commit này.
3. **Xoá `ProviderPool.get_provider` là ngoại lệ AC-11.** Nếu Slice 1 định dùng lại hàm này để dựng
   provider từ pool, hàm đó phải được viết lại **trả instance** (bản cũ trả class). Không có code
   nào đang gọi nên không có gì hỏng lúc merge.
4. **Rủi ro môi trường khi chạy test:** `test_provider_pool.py` phụ thuộc env var provider. Máy tôi
   **có** `VNBROKER_BROKER_SSI_*` nên test đầu tiên của tôi fail vì không chặn env — đã sửa bằng
   `patch.dict` đặt rõ 6 biến. Test mới đã độc lập với `.env`, nhưng ai sửa tiếp cần nhớ điều này.
5. **Mỗi test "không được treo" để lại daemon thread quay vô hạn ở lần chạy fail-trước.** Vô hại vì
   daemon và suite vẫn kết thúc (6,82 s), nhưng đừng lạ khi thấy CPU cao trong lần đó.

---

## 12. Khuyến nghị cho coordinator

1. **Ưu tiên cao:** mở slice cho §9.1 (`async_client.py:360` `async with RATE_LIMITER` → `AttributeError`).
   Không có agent nào claim file đó.
2. Xác nhận hoặc revert `6e01926` (cache namespace) — tôi tin là nên giữ, nhưng nó ngoài kế hoạch.
3. Xác nhận `a381050` (xoá `get_provider`) nếu ưu tiên AC-11 hơn dead-code cleanup.
4. Ghi `docs/CHANGELOG.md` của repo này (plan §10 yêu cầu ledger nằm ở đây, **không** phải ledger của `vninvest`).
5. Slice 1: `api/bulk.py` chưa được đụng; decision D3 về file đó vẫn nguyên vẹn cho Slice 1.
