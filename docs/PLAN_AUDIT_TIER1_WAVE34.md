# PLAN AUDIT — Tier-1 Wave 3 + 4

**Ngày:** 2026-10-10 · **Kế hoạch:** `docs/PLAN_TIER1_WAVE34.md`
**Auditor:** agent độc lập, **read-only**, dùng instrument khác (script AST + chạy
code thật), không đọc lại kết luận của tác giả.
**Base:** `4cd0f2d`

---

## 1. KẾT LUẬN VÒNG 1

`VERDICT: NEED_REVISION` · `confidence: high`

**21 finding**: 1 **blocker**, 5 **major**, 15 **minor**. Dưới đây chỉ liệt kê cái
làm thay đổi kế hoạch; các minor còn lại đã được ghi thẳng vào plan.

---

## 2. BLOCKER — `RateLimitError` sẽ làm AUTO failover chết

| | |
|:--|:--|
| **Claim của plan v1** | `should_failover` "**đã** trả `True` cho `429` ⇒ failover không cần sửa" |
| **Đo** | `should_failover(RateLimitError('kbs', retry_after=120))` → **`False`** |
| **Lệnh** | `python -c "from vnbroker.core.source_router import should_failover; from vnbroker.core.exceptions import RateLimitError; print(should_failover(RateLimitError('kbs', retry_after=120)))"` |
| **Vì sao** | `exceptions.py:292` `RateLimitError(NetworkError)` ⇒ MRO không có `OSError`. `should_failover` (`source_router.py:426`) xét `isinstance(OSError, NotImplementedError, KeyError, LookupError)` trước, rồi mới xét 15 marker chuỗi — chuỗi của class này ghi *"throttled requests"*, **không** chứa `"429"` lẫn `"rate limit"` |
| **Hậu quả** | `base.py:180-185` rơi vào nhánh `raise`: không `record_failure`, không thử provider kế tiếp. **Tệ hơn trạng thái hiện tại** |
| **Sửa** | `RateLimitError(NetworkError, ConnectionError)` — **đã kiểm chứng chạy thật**: MRO `[RateLimitError, NetworkError, vnbrokerError, ConnectionError, OSError, Exception]` · `isinstance(OSError)=True` · `should_failover=True` |
| **Trạng thái** | ✅ đã sửa ở plan v2 §1 W3.2b + §4 W3.0; thêm **AC-3.5** canh gác trực tiếp |

---

## 3. MAJOR

| # | Finding | Xử lý |
|:--|:--|:--|
| **6/17** | 36 decorator `@retry` trong `api/*.py` không có `reraise=` **và không có `retry=`** ⇒ tenacity mặc định retry **mọi** exception ⇒ AC-3.2/3.4 viết trên đường đó **không thi hành được trong phạm vi** | Đo lại: `common.data.Quote.history` (đường người dùng thật) **không** có wrapper ⇒ 1 lệnh = 1 attempt. AC chuyển sang đo trên đường thật đó. Ghi rõ trong §2 |
| **7** | Plan v1 nói `explorer/tcbs/auth.py` và `broker/ssi/auth.py` dùng logger rò — **cả hai sai**. `tcbs/auth.py` **không có logger**; `ssi/auth.py` dùng `logging.getLogger` chuẩn, `SensitiveDataFilter` không gắn ở đó | Bảng "phạm vi thật" trong §1 T4, chỉ `connector/dnse/trade.py` là đúng |
| **19** (L-R07) | Cách tự nhiên làm T4.4 (cho dấu cách làm dấu phân cách) **phá huỷ dữ liệu**: `'the user name is bob'` → `'the user: "***REDACTED***" is bob'`, vì `SENSITIVE_KEYS` chứa `user`/`key`/`auth` | T4.4 đổi thành **word-boundary + neo chữ số**; AC-4.2 thêm 2 câu prose + `monkey=abc` làm ca phải giữ nguyên |
| **17** | AC-4.2 là proxy **đã xanh sẵn**; và T4.3 (args không phải str) **không có AC** nào | Thêm `monkey=abc` (lỗi quá rộng **đang sống**) và thêm **AC-4.4** |
| **18** (L-P03) | `vnbroker/api/quote.py` không thuộc lát nào, không nằm deny list, nhưng từng là nơi AC dựa vào | Mục §6.1 chốt rõ: W3 **không** sửa file này; nợ N1 đã ghi |

---

## 4. MINOR — đã sửa trong plan v2

| # | Finding | Sửa |
|:--|:--|:--|
| **5** | `RateLimitError` **đã** có `retry_after` trong `details` ⇒ plan v1 "sửa nó để mang `retry_after`" là chữa bệnh không có | W3.0 chỉ thêm **thuộc tính** `retry_after` kiểu `float \| None` (hiện chỉ có `details[...]`) |
| **9** | "10 file >800L" chỉ đúng trong `vnbroker/`; cả repo = **12** | §0.1 ghi rõ phạm vi đo |
| **12** | "75 call site" là đếm chuỗi thô; AST cho **58** call + 9 import | §1 W3.1 dùng số AST |
| **14** | "8 PASS" thực ra là **9 PASS** | §0 sửa |
| **20** | Bỏ guard `isinstance(arg, str)` sẽ phá `%d`/`%r` | T4.3 ghi rõ: đi vào `record.getMessage()` một lần, **không** `str()` hoá mọi arg |
| **21** | AC-3.1 chỉ đúng ở chế độ AUTO (`base.py:163-164` early-return khi source cố định); `RETRY_AFTER_MAX_SECONDS` chưa tồn tại | AC-3.1 ghi rõ "**ở chế độ AUTO**"; W3.5 thêm hằng vào `Config` |

---

## 5. ĐÃ KIỂM TRA VÀ **KHÔNG** CÓ VẤN ĐỀ

| Kiểm tra | Kết quả |
|:--|:--|
| Hazard 6 — AC đòi PASS từ gate đang đỏ? | **Sạch.** Definition-of-done chỉ đòi `check_all.ps1` exit 0 (đúng bằng baseline); 2 gate đỏ bị loại đúng vào N3/N4 |
| Phạm vi lát có chồng nhau? | **Không.** W3 vs T4 không có cặp file trùng |
| Rủi ro **dưới** redact ở T4? | **Không thấy.** `Bearer <token>` + JWT trần bắt đủ 4 ca đo; AC-4.1 khoá bằng đúng 10 chuỗi đã đo |
| Số `common/data.py` = 1823 | Tái lập đúng |
| 40 `@retry` / 36 không reraise / 4 có | Tái lập đúng bằng script AST |
| 0 test gọi `configure_rate_limiter`/`get_rate_limiter` | Tái lập đúng |
| Baseline §0 | Tái lập đúng từng dòng, exit 0 |

---

## 6. VÒNG 2 — sau khi sửa

Xem `docs/PLAN_AUDIT_TIER1_WAVE34_R2.md`.