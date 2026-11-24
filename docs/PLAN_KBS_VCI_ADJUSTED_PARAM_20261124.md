# Plan: tham số `adjusted` cho `history()` của KBS/VCI (fail rõ ràng)

**Ngày:** 2026-11-24  
**Branch:** `docs/kbs-vci-raw-price-probe` (sẽ đổi tên nếu cần; base `e996cb4`)  
**Evidence gốc:** `docs/evidence/KBS_VCI_RAW_PRICE_PROBE_20261124.md`  
**Lessons áp dụng: [L-P06, L-E01, L-E06, L-P03]**

## 1. Mục tiêu

Thêm tham số `adjusted` vào `history()` của KBS và VCI. Giá trị mặc định `True` giữ nguyên hành vi hiện tại. `adjusted=False` **ném lỗi rõ ràng**, không âm thầm trả giá đã điều chỉnh.

Không hứa có giá thô — đây là "AC đã đổi" theo L-P06: API công khai của KBS/VCI không có cơ chế giá thô (đo ở evidence: VCI `raw-chart` 404, mọi payload/query `adjust*` vô dụng; KBS mọi `adjust*` trả y hệt baseline).

## 2. Bằng chứng đã tự mở đọc (file:line)

- `vnbroker/explorer/vci/quote.py:299,525` — `gap-chart` cứng trong cả `history_async` lẫn `history`; `:286-350`, `:483-572` là 2 entry point cần sửa.
- `vnbroker/explorer/kbs/quote.py:287-302` — signature `history()`; `:162-176` — `fetch_multiple()`; `:341-356` — nhánh parallel.
- `vnbroker/base.py:178-180` — `_call_provider_method` lọc kwargs bằng `inspect.signature`; `:210-215` — AUTO failover theo `should_failover`.
- `vnbroker/common/data.py:831-857` — `_filter_kwargs` cũng lọc theo `inspect.signature` ⇒ **không cần sửa** file 1823L này.
- `vnbroker/core/source_router.py:476-479,493` — `ProviderBadRequestError` là lỗi **không failover**; `NotImplementedError` thì có (`:493`) ⇒ **không dùng** `NotImplementedError`.
- `vnbroker/core/exceptions.py:413-426` — `ProviderBadRequestError(message, http_status=...)` sẵn có.
- `vnbroker/api/quote.py:123-131` — `@retry` **trần** (không filter, không `reraise`); `ProviderBadRequestError` sẽ bị retry `Config.RETRIES=3` lần rồi thoát dưới dạng `tenacity.RetryError` ⇒ phải sửa decorator (O-1). `:332-405` — `fetch_multiple` liệt kê cứng kwargs, **không có** `adjusted` ⇒ AC-4 chỉ áp cho explorer (O-3).

## 3. Tiêu chí nghiệm thu (Given/When/Then)

| ID | Given | When | Then |
|---|---|---|---|
| AC-1 | KBS `Quote`, mock HTTP | `history(adjusted=False)` | raise `ProviderBadRequestError`; message nêu rõ "giá thô"/"KBS" và link evidence; `send_request` **không** được gọi |
| AC-2 | VCI `Quote`, mock HTTP | `history(adjusted=False)` | tương tự AC-1 với "VCI"; `async_send_request`/`send_request` không được gọi |
| AC-3 | KBS/VCI, `adjusted=True` (mặc định hoặc tường minh) | `history(start=..., end=...)` | trả DataFrame như cũ; behavior không đổi |
| AC-4 | **Explorer** `Quote.fetch_multiple(adjusted=False)` (KBS/VCI) | gọi trực tiếp classmethod | raise ngay trước vòng lặp; không gọi mạng. `api.quote.fetch_multiple` **không** nằm trong AC này (kwargs cứng, không có `adjusted` ⇒ `TypeError`, vẫn là fail rõ ràng) |
| AC-5 | `vnbroker.api.quote.Quote(source="KBS"/"VCI")`, thay provider bằng **hàm thật có signature** (`def history(self, adjusted=True, **kwargs)`) đếm lời gọi — **KHÔNG dùng `MagicMock` thường** (`base.py:178-180` lọc theo `inspect.signature`, mock thường có `(*args, **kwargs)` ⇒ `adjusted` bị bỏ ⇒ test xanh giả) | `history(adjusted=False)` | assert `call_kwargs["adjusted"] is False` **và** raise `ProviderBadRequestError` **không** bị bọc `RetryError`; provider được gọi **đúng 1 lần** |
| AC-6 | `should_failover(exc)` với exception từ AC-1 | gọi hàm | trả `False` (đảm bảo AUTO không âm thầm đổi provider) |
| AC-7 | KBS/VCI, `history(adjusted=False, parallel=True, symbols=["ACB"])` | gọi history | raise ngay ở **dòng đầu** `history()`, `fetch_multiple` không được gọi (O-2) |
| AC-8 | `api.quote.Quote(source="KBS")` | `history()` bình thường (network error giả lập, patch `tenacity.nap.sleep`) | vẫn retry theo `Config.RETRIES`, `reraise=True` trả exception gốc (không regression) |
| AC-9 | VCI `Quote`, `history_async(adjusted=False)` | await hàm | raise `ProviderBadRequestError` trước khi gọi `async_send_request` |

## 4. Baseline cổng (đo trước khi sửa, lệnh kèm theo)

| Lệnh | Kết quả |
|---|---|
| `python -m pytest tests/unit/common/test_quote_kwargs.py tests/unit/api/test_quote.py -q` | **13 passed** (27.91s) @ `e996cb4` |
| `python -m ruff --version` | 0.15.17 |
| `python -m mypy --version` | 2.1.0 |
| `pwsh -File scripts/check_all.ps1 -Quick` | **CHƯA CHẠY** — sẽ chạy ở B7; không báo PASS trước |

Máy này **không có `.venv`** (đã kiểm `Test-Path .venv\Scripts\python.exe` → False); dùng `python` hệ thống 3.13.14. Ghi rõ thay thế trong báo cáo.

## 5. SCOPE / LIMIT / non-goals / rollback

**SCOPE (file chạm):**
1. `vnbroker/explorer/kbs/quote.py` — helper + `adjusted` trong `history`, `fetch_multiple`.
2. `vnbroker/explorer/vci/quote.py` — helper + `adjusted` trong `history`, `history_async`, `fetch_multiple`.
3. `vnbroker/api/quote.py` — chữ ký + docstring tường minh (`adjusted: Optional[bool] = None`) **và** sửa `@retry` ở `:123`: thêm `retry=retry_if_not_exception_type(ProviderBadRequestError), reraise=True` (giữ retry cho network error — AC-8). Import bổ sung: `retry_if_not_exception_type` từ `tenacity` (`:10` hiện chỉ có 3 symbol), `ProviderBadRequestError` từ `vnbroker.core.exceptions` (khởi tạo với `http_status=400` — keyword-only, không default).
4. `tests/unit/explorer/test_quote_adjusted_parameter.py` (mới) — AC-1..AC-5.
5. `tests/unit/core/test_adjusted_failover.py` (mới) — AC-6.
6. `docs/CODE_CHANGE_AUDIT_LEDGER.md`, `docs/handoffs/...` — bàn giao.

**LIMIT:** 1 slice, tối đa 3 vòng sửa/bước, không thêm provider, không đụng `broker/`, không đụng `common/data.py` (đang có claim stale, 1823L), không đụng `source_router.py`.

**Non-goals:** không trả giá thô; không đổi mặc định; không sửa `AUDIT_HISTORICAL_DATA_SYNC.md` (tài liệu cũ giữ làm bằng chứng); không thêm endpoint/bịa tham số provider; **không** thêm `capabilities()["quote"]["adjusted_modes"]` (concept này chỉ có ở broker lane, không có registry quote tương ứng — evidence §4 đã đính chính). `api.quote.fetch_multiple` không nhận `adjusted` (kwargs cứng) → TypeError, chấp nhận là fail rõ ràng.

**Rollback:** `git revert` commit slice này; evidence doc giữ lại (không code).

## 6. Ma trận truy vết REQ → task → test

| REQ | Task | Test |
|---|---|---|
| REQ-1 tham số tường minh | T1 KBS, T2 VCI, T3 API | AC-1, AC-2, AC-5, AC-9 |
| REQ-2 fail rõ ràng, không failover | T1 helper dùng `ProviderBadRequestError` | AC-1, AC-6, AC-7 |
| REQ-3 không đổi hành vi mặc định | T1/T2 giữ `adjusted=True`; T3 retry filter | AC-3, AC-8 |
| REQ-4 parallel cũng chặn | T1/T2 `fetch_multiple` + check đầu `history` | AC-4, AC-7 |

## 7. Thứ tự thực thi (TDD, đỏ trước)

1. Viết test AC-1..AC-9. Chạy → phải **ĐỎ** đúng lý do "thiếu tham số/exception", dán output. AC-5 dùng hàm thật có signature, không `MagicMock` thường.
2. T1: helper + KBS, đặt `_require_raw_price_support(...)` ở **dòng đầu** `history()` trước nhánh parallel. Chạy lại AC-1/AC-3/AC-4(explorer)/AC-7.
3. T2: VCI, cùng vị trí helper. Chạy lại AC-2/AC-3/AC-4(explorer)/AC-7/AC-9.
4. T3: `api/quote.py` chữ ký + retry filter. Chạy lại AC-5/AC-6/AC-8.
5. Chạy full unit + contract + gate; re-audit; bàn giao.

## 8. Rủi ro đã chốt (L-P03)

- Dùng `ProviderBadRequestError` thay vì `NotImplementedError` vì `should_failover` xử lý 2 cái ngược nhau. Đã chốt ở plan, không đẩy cho implementer tự quyết.
- `api/quote.py` có `@dynamic_method`: thân hàm có thể không chạy. Chữ ký chỉ để discover; functionality đi qua `_call_provider_method` lọc theo signature provider — đã kiểm chứng ở §2.
- O-1: `@retry` trần ở `:123` biến lỗi thành `RetryError`; đã đưa vào SCOPE T3. Không đổi AC-5 thành chấp nhận `RetryError` vì mất "fail rõ ràng".
- O-5: claim `coordinator-w34` (`CLAIMS.md:46`) stale — branch chỉ có trên `origin/`, local không có, không có worktree (đo `git branch -a --list '*w34*'`). Không chặn file của tôi; vẫn verify trước khi append claim.
- O-6: `base.py:178-180` lọc kwargs bằng `inspect.signature` **không có nhánh VAR_KEYWORD** — AC-5 bắt buộc hàm thật/mock `autospec=True`, assert `adjusted` tới được provider.
- Reservation: `reraise=True` ở `api/quote.py:123` đổi exception cuối từ `RetryError` sang gốc — không test hiện hữu nào assert `RetryError` (đã grep), nhưng phải ghi CHANGELOG ở bước bàn giao (file shared — coordinator xử lý).
