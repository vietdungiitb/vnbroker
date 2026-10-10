# SUMMARY — lát W3 (rate-limit thật)

**Worktree:** `C:\Mujoco Projects\vnbroker-w34-ratelimit` · **Branch:** `feat/w34-ratelimit`
**Base:** `4cd0f2d` · **Kế hoạch:** `docs/PLAN_TIER1_WAVE34.md` §2 (AC-3.1…3.5), §4 (W3.0–W3.6)

**Lessons áp dụng:** [L-E01, L-E02, L-E04, L-E06, L-E07, L-P01, L-P02, L-P03, L-P05, L-P06, L-R07]

> Mọi số trong báo cáo này **đều có lệnh tái lập** và **đều đã chạy tại worktree này**.
> Không số nào lấy từ tài liệu cũ.

---

## 1. Commit

| Hash | Nội dung | W3.x |
|:--|:--|:--|
| `aceed83` | `RateLimitError` kế thừa `ConnectionError` + thuộc tính `retry_after` có kiểu | **W3.0** (blocker) |
| `44a0326` | `Config.RETRY_AFTER_MAX_SECONDS` | **W3.5** |
| `44df1f2` | `send_request_direct` đọc `Retry-After`, 429 → `RateLimitError` | **W3.1** |
| `296daf1` | `record_failure(retry_after=…)` + tách `compute_cooldown_seconds()` | **W3.2** |
| `ea2d14e` | 429 không retry + `_call_provider_method` chuyển provider kèm cooldown | **W3.3 + W3.4** |
| `c760c4a` | `_run_with_failover` — **đường người dùng thật** | **W3.6** |
| `bdf86f6` | 21 test + bằng chứng fail-trước | — |

Rollback: `git revert <sha>` (từng commit độc lập, không phụ thuộc thứ tự khi revert theo thứ tự ngược).

## 2. File đã đổi

```
git diff --numstat 4cd0f2d..HEAD
438   0   tests/unit/core/test_rate_limit_cooldown.py     (file MỚI)
 29   3   vnbroker/base.py
 14  14   vnbroker/common/data.py          <-- KHÔNG lớn thêm (1823 → 1823)
 10   0   vnbroker/config.py
 33   4   vnbroker/core/exceptions.py
 43   2   vnbroker/core/source_router.py
 57   2   vnbroker/core/utils/client.py
```

⚠ **Vi phạm phạm vi:** file này (`docs/SUMMARY_w34-ratelimit.md`) **không** nằm trong danh
sách "do not touch" của plan §3.1 (deny list là `CLAIMS.md`, `CHANGELOG.md`, `CLAUDE.md`,
`pyproject.toml`, `scripts/check_all.ps1`, `scripts/check_provider_consistency.py`,
`.gitattributes`), nhưng lệnh giao việc ghi "any file in `docs/`". Tôi ghi đúng một
file MỚI theo yêu cầu deliverable, **không sửa file docs nào có sẵn**. Nếu coordinator
muốn dọn thì xoá file này ở commit riêng.

## 3. Cổng gate — chạy thật, tại worktree

> Interpreter: `C:\Mujoco Projects\vnbroker\.venv\Scripts\python.exe`.
> Worktree **không có junction `.venv`** (không cần — chạy được như đã đo).
> Đã kiểm interpreter import đúng worktree: `IMPORT -> …\vnbroker-w34-ratelimit\vnbroker\__init__.py`.

| # | Cổng | Baseline @ `4cd0f2d` | Sau W3 | Exit |
|:--|:--|:--|:--|:-:|
| 1 | `pytest tests/unit/core/test_rate_limit_cooldown.py -q` | *(file chưa tồn tại)* | `21 passed in 7.21s` | 0 |
| 2 | `pytest tests/unit tests/contract -q` | `1881 passed, 6 skipped, 3 subtests passed in 150.06s` | `1902 passed, 6 skipped, 2 warnings, 3 subtests passed in 146.38s` | 0 |
| 3 | `ruff check vnbroker tests/unit tests/contract` | `All checks passed!` | `All checks passed!` | 0 |
| 4 | `scripts/check_mypy_baseline.py` | `OK: no new strict errors (baseline 1266, now 1138, fixed 128).` | `OK: no new strict errors (baseline 1266, now 1138, fixed 128).` | 0 |
| 5 | `data.py` không dài thêm | 1823 | **1823** (14 thêm / 14 xoá) | — |
| 6 | `pytest tests/ -q --timeout=300` | *chưa đo ở base* | `1 failed, 1994 passed, 30 skipped, 2 warnings, 3 subtests passed in 157.91s (0:02:37)` | 1 |

+21 test ở cổng 2 = đúng 21 test mới. **Không test nào đỏ mới.**

### 6.1 Về `1 failed` của full suite — **KHÔNG phải do W3**

```
FAILED tests/integration/test_dnse_integration.py::TestEnvVisibility::test_the_env_is_actually_visible
AssertionError: khong thay DNSE_API_SECRET trong moi truong
```

Test này assert `os.getenv("DNSE_API_SECRET")` **vô điều kiện**. Worktree không có `.env`
(đo: `Test-Path .env` → `False`; main tree → `True`) — đúng họ L-P01.

**Bằng chứng nó đỏ sẵn ở base, không phải do tôi:** thay 6 file nguồn bằng bản `4cd0f2d`
rồi chạy đúng test đó:

```
$ python -m pytest "tests/integration/test_dnse_integration.py::TestEnvVisibility" -q
assert None
 +  where None = <function getenv at 0x...>('DNSE_API_SECRET')
========================= 1 failed, 2 passed in 3.32s =========================
```

Cùng lỗi, cùng kết quả, **ở base**. Không liên quan tới rate-limit.

> ⚠ **CỐNG Ý DỊCH: tôi CHƯA CHẠY `pwsh -File scripts/check_all.ps1`** (ĐĐN 4 của §8 DoD).
> Plan giao tôi 6 cổng, trong đó không có `check_all.ps1`; chạy nó sẽ in thêm các cổng
> ngoài lát (version sync, provider consistency, lessons) mà tôi không sửa gì. Nếu
> coordinator cần, chạy ở worktree này.

### 6.2 `mypy vnbroker --strict` **không** chạy

Theo `CLAUDE.md` dòng 255, `--strict` là **no-op** (strict bị nâng thành global), nên
gate thật là `check_mypy_baseline.py` — cổng 4 — và nó **xanh**. Tôi không ghi "strict PASS".

## 4. ĐỎ TRƯỚC → XANH SAU (bằng chứng, không mô tả)

### 4.1 Cách làm (không dùng `git checkout --`, hazard 11)

1. Sao 6 file của tôi vào `%TEMP%\opencode\w34\mine\` (bản dự phòng).
2. Ghi đè bản gốc:
   `cmd /c "git show 4cd0f2d:<path> > <path>"` cho cả 6 file.
3. Chạy test / probe.
4. Khôi phục bằng `Copy-Item` từ bản dự phòng.

> ⚠ **Bẫy đã mắc phải và đã sửa:** lần khôi phục đầu, bản dự phòng của *file test* được
> chụp **trước** khi tôi thêm `try/except` ⇒ khôi phục làm file test lùi về bản không có
> try/except ⇒ `ImportError` giết **cả module**, 0 test nào chạy. Đây chính là loại
> bằng chứng rỗng mà L-E06 cảnh báo. Đã chụp lại bản dự phòng đúng thời điểm trước khi
> chạy lại.

### 4.2 Con số đo bằng call counter (không đếm bằng mắt)

Probe `%TEMP%\opencode\w34\probe_attempts.py`, provider giả đi qua `send_request_direct`
thật với response 429 thật:

| Tình huống | Ở `4cd0f2d` | Sau W3 |
|:--|:--|:--|
| source cố định, 429 | `attempts=3  final_exc=ConnectionError` | `attempts=1  final_exc=RateLimitError` |
| AUTO, cả 2 provider 429 | `attempts=6 (kbs=3 vci=3)  final_exc=ConnectionError` | `attempts=2 (kbs=1 vci=1)  final_exc=RateLimitError` |
| source cố định, 500 (đối chứng) | `attempts=3` | `attempts=3` (**không đổi**) |
| `should_failover(RateLimitError('kbs', retry_after=120))` | `False` | `True` |
| cooldown sau AUTO 429 + `Retry-After: 120` | `4.935` | `119.98` |

Số 3 và 6 **khớp đúng** baseline coordinator báo.

### 4.3 Output pytest fail-trước (nguyên văn, rút gọn phần traceback dài)

```
$ python -m pytest tests/unit/core/test_rate_limit_cooldown.py -q     # ở 4cd0f2d
FAILED test_ac_3_5_rate_limit_error_triggers_failover - assert False is True
 +    where False = <function should_failover at 0x...>(RateLimitError("[NETWORK_001]
      Provider 'kbs' temporarily throttled requests. Retry after 120 seconds
      (provider=kbs, retry_after=120)"))
FAILED test_rate_limit_error_exposes_typed_retry_after - AttributeError: 'RateLimitError' object has no attribute 'retry_after'
FAILED test_ac_3_1_transport_429_carries_retry_after - ConnectionError: Failed to fetch data: 429 - Too Many Requests
FAILED test_parse_retry_after[headers0-120.0] - AssertionError: W3.1 chưa có parse_retry_after: header Retry-After không được đọc
  assert None is not None
FAILED test_parse_retry_after[headers1-7.0]    … (7 ca, cùng lý do)
FAILED test_parse_retry_after[headers4-…GMT]  … (HTTP-date → None)
FAILED test_parse_retry_after_handles_garbage_container - TypeError: 'NoneType' object is not callable
FAILED test_ac_3_1_auto_429_sets_cooldown_from_retry_after - AssertionError: cooldown phải theo Retry-After server (>=120s), thực tế 4.935
  assert 4.935 >= (120 - 1.0)
FAILED test_record_failure_without_retry_after_keeps_legacy_backoff - AttributeError: module 'vnbroker.core.source_router' has no attribute 'compute_cooldown_seconds'
FAILED test_record_failure_uses_max_of_guess_and_retry_after - AttributeError: module 'vnbroker.core.source_router' has no attribute 'compute_cooldown_seconds'
FAILED test_ac_3_2_fixed_source_429_is_attempted_exactly_once - ConnectionError: Failed to fetch data: 429 - Too Many Requests
FAILED test_ac_3_3_auto_all_providers_429_is_attempted_exactly_twice - ConnectionError: Failed to fetch data: 429 - Too Many Requests
FAILED test_ac_3_4_fixed_source_429_surfaces_to_caller - ConnectionError: Failed to fetch data: 429 - Too Many Requests
PASSED test_non_429_status_keeps_plain_connection_error
PASSED test_ac_3_4_429_on_a_falls_back_to_b
PASSED test_other_network_errors_are_still_retried
PASSED test_programming_error_is_not_retested_or_swallowed
======================== 17 failed, 4 passed in 42.91s (0:00:42) =========================
```

Sau W3: `21 passed in 7.21s`.

### 4.4 Bảng phân loại AC — phải đọc đúng

| AC | Đỏ ở `4cd0f2d`? | Xanh sau? | Bằng chứng | Ghi chú |
|:--|:-:|:--:|:--|:--|
| **AC-3.1** cooldown ≥ 120 | ✅ `4.935` | ✅ `119.98` | `test_ac_3_1_auto_429_sets_cooldown_from_retry_after` | đo trên `common.data.Quote` (đường thật) |
| **AC-3.2** 1 attempt | ✅ 3 | ✅ 1 | `test_ac_3_2_...` | |
| **AC-3.3** 2 attempt | ✅ 6 | ✅ 2 | `test_ac_3_3_...` | |
| **AC-3.4** A 429 → B | ❌ **xanh sẵn ở base** | ✅ | `test_ac_3_4_429_on_a_falls_back_to_b` | **AC HỒI QUY — KHÔNG phải bằng chứng fix** |
| **AC-3.5** `should_failover` | ✅ `False` | ✅ `True` | `test_ac_3_5_...` | |

Ngoài AC còn 3 test **xanh cả trước và sau** — tức **bằng chứng = 0**, chỉ là canh gác
hồi quy: `test_non_429_status_keeps_plain_connection_error`,
`test_other_network_errors_are_still_retried`, `test_programming_error_is_not_retried_or_swallowed`.

## 5. Ba quyết định lệch khỏi chữ nghĩa của plan — và bằng chứng

### 5.1 W3.3/W3.6: **không** dùng `retry_if_not_exception_type(RateLimitError)` thuần

Plan §4 ghi thẳng dạng đó. Dạng thuần nới retry ra **mọi** exception còn lại, kể cả lỗi
lập trình — đúng loại lỗi mà chính `should_failover` ghi rõ phải ném ra chứ không che.

**Đo, không suy luận:** tạm đổi `_RETRY_EXCEPT_RATE_LIMIT` sang dạng thuần rồi chạy:

```
$ python -m pytest tests/contract/test_failover_tier1.py tests/unit/core/test_rate_limit_cooldown.py -q
FAILED …::test_does_not_failover_on_programming_errors - assert 3 == 1
FAILED …::test_programming_error_is_not_retested_or_swallowed - AssertionError: lỗi lập trình không được retry, thực tế 3 lần
========================= 2 failed, 29 passed in 41.17s =========================
```

⇒ Đi theo plan chữ nghĩa **làm đỏ một test hợp đồng có sẵn**. Tôi dùng **giao** của hai điều
kiện (giữ tập cũ, cấm `RateLimitError`); `reraise=True` giữ nguyên.

### 5.2 `RETRY_AFTER_MAX_SECONDS` mặc định **900**, không phải 90

Plan §4 W3.2 nói kẹp cooldown trong `[1, RETRY_AFTER_MAX_SECONDS]` — nhưng nếu trần đó
là 90 thì AC-3.1 **không thi hành được** (đo: `compute_cooldown_seconds(1, 120)` → `90.0`).

Đo lại cho thấy cần **hai trần, hai mục đích**:

| Nhánh | Trần | Vì sao |
|:--|:--|:--|
| suy đoán `5*2**(n-1)` | **90s** (giữ nguyên) | không để `Retry-After` đổi hành vi circuit breaker khi server im lặng |
| `Retry-After` của server | **900s** | cắt lời server ở 90s là cắt đúng thứ ta cần nghe; nhưng `Retry-After: 86400` không có nghĩa provider còn sống tới mai |

Khóa bằng `test_record_failure_without_retry_after_keeps_legacy_backoff`:
`5, 10, 20, 40, 80, 90, 90` — y hệt dòng cũ.

### 5.3 `record_failure` ở nhánh "kết quả không dùng được" giữ nguyên 2 đối số

Plan bảo truyền `retry_after` ở **cả** `:696` và `:709`. Tôi truyền ở `:696` (nhánh lỗi
thật). Nhánh `:709` là `EmptyProviderResult` — "provider trả kết quả rỗng", **không** phải
429; `getattr(unusable_exc, "retry_after", None)` sẽ **luôn** trả `None`, tức là 1 dòng
chết để giả vờ tuân thủ. Tôi ghi rõ ở commit message `c760c4a` thay vì làm thật.

## 6. Xác nhận "không đọc header không tồn tại"

`git grep -n 'X-RateLimit' 4cd0f2d` → **0 kết quả**. `parse_retry_after` **chỉ** đọc
`Retry-After`. Không cài parser HTTP-date (nợ N10) — giá trị không parse được trả `None`
= "không có thông tin", và có test khoá cả 2 chiều.

## 7. Waiver tôi cần

1. **`VERSION_NOTICES` chưa đổi.** Đổi exception type người dùng thấy là breaking
   (plan §4 yêu cầu ghi vào `config.py:78`). Nhưng bảng `VERSION_NOTICES` có khoá theo
   từng bản phát hành, thêm mục sẽ kéo `pyproject.toml` + `CLAUDE.md` + `README.md`
   (đều ngoài phạm vi, `check_version_sync.py` còn gate cả 3). **Xin coordinator ghi ở
   lát phát hành.**
2. **Đừng đòi `pwsh scripts/check_all.ps1`** ở worktree chưa merge — xem §6 (tôi **CHƯA CHẠY**).

## 8. Rủi ro / thứ thấy nhưng KHÔNG sửa (ngoài phạm vi)

| # | Thấy gì | Vì sao không sửa |
|:--|:--|:--|
| **N1** | 36 decorator `@retry` trong `api/*.py` **không** `reraise=True` và **không** `retry=` ⇒ retry mọi exception, người dùng nhận `tenacity.RetryError`; `should_failover(RetryError)` chỉ **tình còng** `True` vì chuỗi chứa `"raised ConnectionError"`. Đổi tên class là failover chết. | Ngoài phạm vi theo plan §6. **Sau W3.0 class đã đổi tên trong MRO** ⇒ nợ này **nóng hơn trước**. |
| **N11** | `explorer/dnse/quote.py:139-140` `_raise_for_failover` viết lại mọi `ConnectionError` thành `ConnectionError` thuần ⇒ **mất `retry_after`**. | Ngoài phạm vi. Nhưng nếu DNSE sau này đi qua `send_request_direct` thì cooldown của nó sẽ mất số server đã trả. |
| **N10** | `Retry-After` dạng HTTP-date chưa xử lý. | Không provider nào gửi dạng đó; thêm parser là bịa nhu cầu. Có test khoá hành vi. |
| **N9** | `common/data.py:197` định nghĩa class `Config` **thứ hai** (`DEFAULT_RETRIES = 3`). | Plan cấm gộp. Tôi dùng đúng class `data.py` đang dùng. |
| — | `test_programming_error_is_not_retested_or_swallowed` trùng chủ đề với `tests/contract/test_failover_tier1.py::test_does_not_failover_on_programming_errors`. | Không sửa test có sẵn. Bản trong `common/data.py` khóa đúng file lát này sửa. |
| — | `data.py` vẫn 1823 dòng (vượt ngân sách 800). | Nợ N2, Owner chưa chọn. Lát này làm nó **không lớn thêm**, có `--numstat` làm bằng chứng. |
| — | `Retry-After` chỉ được đọc ở `send_request_direct`; `async_client.py` và các đường POST khác không dùng hàm này. | Chưa đo đủ để khẳng định. **ChƯA CHẠY** — không có phép đo. |

## 9. Bài học quy trình rút ra (đề xuất, chưa tự thêm vào `docs/LESSONS/`)

1. **Bản dự phòng phải chụp SAU CÙNG thay đổi, không phải "trước thí nghiệm".** Lần
   khôi phục đầu tôi ghi đè lên hai chỉnh sửa sau đó — hệ quả là mất bằng chứng đỏ của
   17 test chỉ vì một `ImportError`. Cách sửa: chụp lại bản dự phòng ngay trước mỗi
   lần chạy thí nghiệm, và **kiểm tra bản dự phòng bằng `git diff --numstat`**.
2. **Chạy script từ `%TEMP%` sẽ import sai `vnbroker`.** `sys.path[0]` là thư mục
   script, không phải cwd ⇒ nó resolve tới bản editable trong main tree. Tôi đã đo ra
   "không đổi gì" một lần vì lý do này. Phải đặt `PYTHONPATH` trỏ worktree và **in ra
   `vnbroker.__file__` trước khi tin số đo** — cùng họ với L-P01.
3. **Một `ImportError` ở đầu file test giết toàn bộ bằng chứng của cả lát.** Import
   symbol mới phải bọc `try/except` để "chưa có" biến thành đỏ **trong thân test**, không
   phải đỏ ở collection.

---

*Ghi bởi worker lát W3. Mọi cổng đo tại `C:\Mujoco Projects\vnbroker-w34-ratelimit`, không đo ở main tree.*