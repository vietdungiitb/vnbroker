# SSOT Phase 1 — vnbroker rate-limit & bulk failover (2026-11-27)

Repo `vnbroker`, branch `feat/ssot-phase1`, claim `ssot-phase1`. Theo `SSOT_ADJUSTMENT_DESIGN_REV2` D-05 + D-09. **Không đụng secret, không migration.**

## Fail-before

`tests/unit/core/test_ssot_phase1.py` mới: **4 failed** (`429` vẫn retry, `418` không có marker, DNSE mất `retry_after`, provider dính rate-limit làm rơi symbol). Sau fix: **8 passed** (thêm shared budget, benchmark 418, inject limiter). Cùng chạy với `test_async_client.py`: **17 passed**.

## Changes (file:line)

| File | Change |
|---|---|
| `core/exceptions.py` | `RateLimitError` đã có; giữ nguyên, dùng làm tín hiệu failover |
| `core/utils/client.py` | `418` + `429` → `RateLimitError` có `retry_after`; dùng **shared provider bucket** thay bucket module-local |
| `core/utils/async_client.py` | `_is_retryable_status` chỉ retry `>=500`; `418/429` ném `RateLimitError` ngay; `async with` dùng shared bucket; stats đếm cả 418 |
| `core/utils/rate_limiter.py` | Thêm `rate` property, `__aenter__/__aexit__` (dùng chung 1 bucket sync+async), `get_provider_limiter()` / `reset_provider_limiters()` |
| `core/bulk_router.py` | `fetch_history` gom `failed_symbols` rồi **requeue trong cùng lời gọi** sang provider khác; `results.setdefault().extend()` |

| `api/bulk.py` | `resolve_frame_symbol()` — trả `None` thay nhãn `"unknown"`, frame không xác định được symbol bị bỏ và đếm riêng |
| `explorer/vci/quote.py`, `kbs/quote.py` | `except RateLimitError: raise` TRƯỚC handler nuốt lỗi per-symbol |
| `explorer/dnse/quote.py` | `_FAILOVER_MARKERS` thêm `"418"`; `_raise_for_failover` giữ nguyên `RateLimitError`/`retry_after`; không nuốt ở record path |
| `tests/examples/vci_perf_benchmark.py` | Nhãn output `418/429=` |
| `tests/unit/core/test_async_client.py` | Test retry stats dùng `500` (vì 429 không còn retry theo D-05) |

**Sửa sau B8 NEED_REVISION (vòng 1)**: async `_send_with_retry` re-raise `RateLimitError` trước `except Exception` (giữ `retry_after`); DNSE record path re-raise trước `except ConnectionError`; `rate_limiter.py` thêm `set_provider_limiter()` để caller inject (vninvest Phase 4); `api/bulk.py` đếm `dropped_frames` thay vì chỉ `continue`.

**AC7 trung thực**: `get_profile()` (`performance_profiles.py:83-89`) hiện **chỉ** được dùng lại bên trong `apply_profile()` — đường bulk/client chưa đọc profile theo dict. AC7 đạt ở dạng **no-op/giữ tương thích**, không phải đã chuyển bulk sang profile-driven. `performance_profiles.py` đã bị bỏ khỏi danh sách file thay đổi trong claim.

## Gates chạy thật

| Gate | Kết quả |
|---|---|
| `pytest tests/unit/core/test_ssot_phase1.py` | **7 passed** |
| Regression 6 suite liên quan | **133 passed** |
| Full `pytest -q` (basetemp riêng) | **2355 passed, 30 skipped, 1 deselected**, 3 subtests passed |
| `ruff check` (10 file đổi) | **All checks passed** |
| `mypy` | **956 errors / 99 files** — pre-existing (follow imports vào `explorer/tcbs/news.py` chưa đổi), không phải do slice này; **KHÔNG báo PASS** |
| Test DNSE env | **CHƯA CHẠY** — `DNSE_API_SECRET` không có trong env ⇒ deselect `test_the_env_is_actually_visible` |
| Publish 3.11.0 / pin vào vninvest | **CHƯA LÀM** (Phase 4) |

## Bất biến đã khóa

- 418/429 = rate-limit, không retry cùng provider, luôn có `retry_after`.
- Provider dính rate-limit giữa batch → symbol được provider khác gánh **trong cùng `BulkAPI.history()`**.
- Mỗi provider **1 budget chung** cho sync + async.
- Không có frame `"unknown"` (bỏ frame vô chủ thay vì gán nhãn giả).
