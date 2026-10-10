# AUDIT — Tier-1 Wave 3 + Wave 4 (code)

**Ngày:** 2026-10-10 · **Base:** `0b2c9ba` · **HEAD khi audit:** `3fb4415`
**Auditor:** agent độc lập, **read-only**, dùng instrument **khác** (script probe
riêng, không chạy test của tác giả rồi tin).
**Kế hoạch:** `docs/PLAN_TIER1_WAVE34.md` · **Audit kế hoạch:** `docs/PLAN_AUDIT_TIER1_WAVE34.md`

---

## 1. KẾT LUẬN

| Vòng | Phạm vi | Kết quả |
|:--|:--|:--|
| Audit kế hoạch vòng 1 | `docs/PLAN_TIER1_WAVE34.md` | `NEED_REVISION` — 1 blocker · 5 major · 15 minor |
| Audit kế hoạch vòng 2 | bản sửa sau vòng 1 | `NEED_REVISION` — 1 blocker · 4 major |
| **Audit code** | `1025bd6` + `cc41be2` | `NEED_REVISION` — **0 blocker · 1 major · 4 minor** |
| **Audit xác minh sau sửa** | `3fb4415` | **`PASS`** — 0 blocker · 0 major · 2 minor (residual) |

`confidence: high` — mọi số dưới đây tái lập được bằng lệnh nêu kèm.

---

## 2. BLOCKER ĐÃ BẮT — `RateLimitError` làm AUTO failover chết

| | |
|:--|:--|
| **Claim của kế hoạch v1** | `should_failover` "**đã** trả `True` cho `429` ⇒ failover không cần sửa" |
| **Đo @ `4cd0f2d`** | `should_failover(RateLimitError('kbs', retry_after=120))` → **`False`** |
| **Lệnh** | `python -c "from vnbroker.core.source_router import should_failover; from vnbroker.core.exceptions import RateLimitError; print(should_failover(RateLimitError('kbs', retry_after=120)))"` |
| **Vì sao** | `exceptions.py:292` là `RateLimitError(NetworkError)` ⇒ MRO **không có** `OSError`. `should_failover` (`source_router.py:426`) xét `isinstance(OSError, NotImplementedError, KeyError, LookupError)` trước, rồi mới xét 15 marker — chuỗi của class ghi *"throttled requests"*, **không** có `"429"` lẫn `"rate limit"` |
| **Hậu quả** | `base.py:180-185` rơi vào nhánh `raise`: không `record_failure`, không thử provider kế tiếp — **tệ hơn trạng thái trước đợt** |
| **Sửa** | `RateLimitError(NetworkError, ConnectionError)` |
| **Đo lại sau sửa** | `should_failover` → **`True`**; `isinstance(OSError)` → **`True`**; MRO `[RateLimitError, NetworkError, vnbrokerError, ConnectionError, OSError, Exception]` |

Đây là loại lỗi mà chỉ **đọc code** không thấy: class trông đúng, hàm trông đúng,
chỉ chạy mới biết hợp đồng của `should_failover` là `isinstance`, không phải
so chuỗi.

---

## 3. BLOCKER THỨ HAI — tôi tự dẫn nhầm đường dẫn người dùng

Bản kế hoạch v2 lập luận: *"`common.data.Quote.history` không có wrapper tenacity
⇒ 1 lệnh = 1 attempt"* — và **tôi tin vào đó khi viết AC**.

Đo lại bằng call counter thật (`%TEMP%\opencode\recheck_attempts.py`):

| Đường | Đo được | AC của bản v2 đòi |
|:--|:--|:--|
| `common.data.Quote.history`, source **cố định** | **3** attempt | 1 |
| `common.data.Quote.history`, **AUTO**, cả 2 provider 429 | **6** attempt | 2 |

**Nguyên nhân tôi sai:** tôi soi `hasattr(Quote.history, 'retry')` → `False`, và
kết luận "không retry". Nhưng `@retry` **không phải nơi retry xảy ra** ở đường
này — nó nằm **bên trong** `_run_with_failover` (`common/data.py:647-656` cho
source cố định, `:665-674` cho AUTO). Docstring ở `common/data.py:722-730` nói
rõ: *"Method này KHÔNG có decorator `@retry`"*.

⇒ `common/data.py` — **đường người dùng thật** — vào lát W3 (W3.6).

**Bài học (L-E06 + hazard 10):** một phép kiểm *gián tiếp* (`hasattr`) trả về kết
quả đúng không cứu được kết luận sai. Phải **đếm** cái mà AC nói tới.

---

## 4. MAJOR ĐÃ ĐÓNG — waiver `VERSION_NOTICES` chưa đóng

| | |
|:--|:--|
| **Yêu cầu** | `PLAN_TIER1_WAVE34.md` §4 W3.1: đổi exception type người dùng thấy là **breaking** ⇒ phải ghi `VERSION_NOTICES` |
| **Đo tại `cc41be2`** | `git tag --points-at cc41be2` → rỗng; `git grep -n RateLimitError -- CHANGELOG.md README.md CLAUDE.md` → **không có**; `VERSION_NOTICES["3.6.0"]` không có mục nào về 429 |
| **Sửa @ `3fb4415`** | Bump **3.7.0**: `pyproject.toml`, `README.md` (badge + mục Breaking Changes), `CLAUDE.md`, `config.py` (`VERSION_REQUIREMENTS` + `VERSION_NOTICES` + `PYTHON_VERSION_SUPPORT`), `CHANGELOG.md` |
| **Đo lại** | `python scripts/check_version_sync.py` → `version-sync OK: 3.7.0` exit 0 |

---

## 5. MINOR ĐÃ ĐÓNG (4/4)

| # | Lỗi | Đo trước | Sau |
|:--|:--|:--|:--|
| 1 | `bearer of the bond coupon` bị bóp méo thành `Bearer ***REDACTED*** the bond coupon` — **đúng dạng L-R07** mà plan §5 cấm | `'bearer of the bond coupon'` bị đổi | **3/3 câu prose giữ nguyên**; token thật (JWT / ≥16 ký tự) vẫn bị che; casing scheme giữ nguyên |
| 2 | JWT `alg:none` (chữ ký rỗng) lọt nguyên văn | `'eyJhbGciOiJub25lIn0.eyJzdWIi….` không đổi | bị che |
| 3 | `retry_after` mất ở đường `PROXY` + `ProxyMode.TRY` | mọi proxy thất → bọc `ConnectionError("All proxies failed…")` | ném nguyên `RateLimitError`, `retry_after == 120` |
| 4 | `details["url"]` của 429 chứa **query string** — provider HMAC đặt credential trong query | `url=…?token=SECRETVALUE` | `url=https://api.example.vn/quote` |
| 5 | `Retry-After: 0.5` in ra `"Retry after 0 seconds"` | `int()` cắt mất phần thập phân | `"Retry after 0.5 seconds"` |

⚠ **Lưu ý đánh giá mình (L-R07):** bản sửa #1 là **đánh đổi có chủ ý** — token
 bearer ≤15 ký tự **không** còn bị che. Chấp nhận được vì bắt nó sẽ phá prose;
 đã ghi rõ trong comment tại `logger.py` và trong `CHANGELOG.md`.

---

## 6. MINOR CÒN LẠI (residual, không chặn merge)

| # | Lỗi | Vì sao chấp nhận |
|:--|:--|:--|
| R1 | `Bearer <token ≤15 ký tự>` lọt | đánh đổi L-R07 nêu trên; ghi trong comment + CHANGELOG |
| R2 | `show_log=True` vẫn log URL thô | **đã sửa** trong `3fb4415` (`_url_without_query`); đo lại: `?signature=abc&api_key=SECRETVALUE` → `https://api.example.vn/quote` |

---

## 7. ĐÃ KIỂM VÀ **SẠCH** (nêu ra để báo cáo không thiên lệch)

| Kiểm | Kết quả |
|:--|:--|
| **Không test nào bị làm yếu/xoá** | `git diff 0b2c9ba..HEAD --diff-filter=D` → **rỗng**; 2 file test mới là thuần thêm (255/0, 438/0) |
| **Không `# noqa` / `# type: ignore` mới** | `git diff 0b2c9ba..HEAD -- vnbroker/ \| Select-String '^\+.*(noqa\|type:\s*ignore)'` → rỗng |
| **Không secret hardcode, không network trong unit test** | cả hai grep rỗng |
| **`common/data.py` không dài thêm** | `1823` dòng trước · `1823` sau (đo bằng **Python**, không phải PowerShell — PowerShell đếm thiếu) |
| **`retry_after` được kẹp trước khi ghi** | `compute_cooldown_seconds(1, 999999999)` → `900.0`; số vô hạn/NaN → không crash |
| **Cooldown sống sót restart** | ghi SQLite → `reload_store()` → còn `in_cooldown: True` |
| **Non-429 không đổi hành vi** | `ConnectionError` vẫn 3 attempt (cố định) và 3+3 (AUTO) |
| **Retry-predicate composite** | dùng **giao** của type-set cũ với `retry_if_not_exception_type(RateLimitError)`, không dùng dạng thuần — dạng thuần làm hỏng `test_does_not_failover_on_programming_errors` (retry `TypeError` 3 lần). Worker đã đo và ghi lý do |
| **AC nào xanh sẵn ở base** | `AC-3.4` (failover A→B) và `AC-4.2` (5 chuỗi prose) **xanh sẵn** ⇒ là **canh gác hồi quy**, **không** phải bằng chứng fix. Đã ghi rõ trong cả plan lẫn `CHANGELOG` |
| **Không AC nào đòi PASS từ gate đang đỏ** (hazard 6) | 2 gate đỏ (`ruff check tests`, mypy raw) bị loại đúng vào nợ N3/N4 |

---

## 8. AC — tái lập độc lập, không dùng test của tác giả

| AC | Kết quả | Lệnh |
|:--|:--|:--|
| AC-3.1 | cooldown `119.93`s với `Retry-After: 120` | `get_source_health_snapshot("quote")["KBS"]["cooldown_remaining_sec"]` |
| AC-3.2 | **1** attempt (base: 3) | call counter trên `common.data.Quote` |
| AC-3.3 | **2** attempt (base: 6) | call counter, AUTO 2 provider |
| AC-3.4 | `source_used = VCI`, `kbs failures = 1` | ⚠ **xanh sẵn ở base** — canh gác hồi quy |
| AC-3.5 | `should_failover(RateLimitError(...)) is True` | đo trực tiếp |
| AC-4.1 | rò **0/10** (base **4/10**) | chạy `redact_sensitive_data` trên 10 chuỗi |
| AC-4.2 | **5/5** không đổi | ⚠ **xanh sẵn ở base** — canh gác hồi quy |
| AC-4.3 | `monkey=abc` không đổi (base: **bị đổi**) | đo trực tiếp |
| AC-4.4 | dict 2 khóa: không `TypeError`, dòng log còn | `log.info("x=%s", {"a":1,"b":2})` |
| AC-4.5 | dict chứa Bearer: JWT không lộ **và** dòng đọc được | `x={'Authorization': 'Bearer ***REDACTED***'}` |

---

## 9. GATE

`docs/TEST_REPORT_TIER1_WAVE34.md`. Tóm tắt: `check_all.ps1` **exit 0** ·
9 PASS · 1 KNOWN-RED · `2032 passed, 26 skipped` · contract **91** ·
mypy baseline **1138** (không lỗi mới) · ruff **0** · version-sync **3.7.0**.