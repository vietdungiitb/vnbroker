# SUMMARY — lát E (`feat/e-cond-sec`): condition/cancel + ananke securities

**Base:** `dev @ 3e252ac` · **Worktree:** `C:\Mujoco Projects\tcbs-e-cond-sec` · **Ngày:** 2026-10-10
**Phạm vi:** AC E1..E5 của `docs/PLAN_TCBS_ROUND2.md` §3 (S-E).

---

## 1. File đã đổi (4 file trong claim — không file nào khác)

| File | Trạng thái | Dòng |
|---|---|---|
| `vnbroker/broker/tcbs/condition_orders.py` | **TẠO MỚI** | **187** |
| `vnbroker/explorer/tcbs/listing.py` | sửa | 373 → **421** (+48) |
| `tests/unit/broker/tcbs/test_tcbs_condition_order.py` | **TẠO MỚI** | 34 test |
| `tests/unit/explorer/tcbs/test_tcbs_ananke_securities.py` | **TẠO MỚI** | 20 test |

Lệnh đo: `(Get-Content -Encoding utf8 <file>).Count`

**Không chạm** (đã kiểm bằng `git status --short` — chỉ 4 dòng trên):
`derivatives.py` (852L, nguyên vẹn) · `equity.py` (798L, nguyên vẹn) · `money.py` ·
`auth.py` · `token_manager.py` · `__init__.py` · `client.py` · `guards.py` · `session.py` ·
mọi file test có sẵn.

---

## 2. AC — trạng thái từng cái

| AC | Nội dung | Trạng thái | Bằng chứng |
|---|---|---|---|
| **E1** | body đúng spec `{accountId, subAccountId, orderNo}`, `required: ['accountId','orderNo']` | ✅ | `condition_orders.py:114-116`; test `TestPayloadTheoSpec` (5 test) |
| **E2** | `fields`/`filter` là **query param**, bỏ trống ⇒ không gửi | ✅ | `listing.py:305-310`; test `TestQueryParam` (6 test) |
| **E3** | module mới, `equity.py` không vượt 800L | ✅ | `equity.py` = 798L **không đổi**; `derivatives.py` = 852L **không đổi**; test sẵn `test_file_under_800_lines[...equity.py-800]` PASSED |
| **E4** | `@write_gate`, `dry_run=True` mặc định | ✅ | `condition_orders.py:107` + `:113` (`*, dry_run: bool = True`); test `TestCancelConditionOrderDryRun` (4) + `TestWriteGate` (2) |
| **E5** | `/ananke/v1/securities` trả **raw dict**, không ép DataFrame, docstring ghi rõ shape chưa tài liệu hoá | ✅ | `listing.py:293-325`; test `TestRawDict` (4) + `TestResponseThieuField` (5) + `TestDocstring` (1) |

### E1 — chi tiết field

```
accountId      ← bắt buộc (spec required)   : validate non-empty → INVALID_ACCOUNT_ID
orderNo        ← bắt buộc (spec required)   : validate non-empty → INVALID_ORDER_NO
subAccountId   ← tuỳ chọn (KHÔNG required)   : bỏ trống ⇒ KHÔNG gửi field này
```

**Quyết định diễn giải (cần coordinator xác nhận):** vì `subAccountId` không nằm trong
`required`, hàm **bỏ field** khi rỗng thay vì gửi `""`. Payload chỉ gồm key có thật trong
`spec.properties` — không thêm, không đổi tên. Có 2 test khoá cả hai nhánh
(`test_payload_dung_ten_field_trong_spec` và `test_sub_account_id_bo_trong_khi_rong`).
Suy ra từ `required` trong spec; **không có probe server thật** để xác nhận TCBS có chấp
nhận `subAccountId: ""` hay không (xem §5).

---

## 3. ⚠ P5 — `requestId` là field HƯ CẤU, lát này KHÔNG copy

Đo lại trên spec:

```
.venv\Scripts\python.exe -c "print(open('docs/references/openapi-v1.0.0.json',encoding='utf-8').read().count('requestId'))"
requestId count = 0
```

`derivatives.py:702-705` và `equity.py:523-525` **vẫn đang gửi** nó — bug có sẵn (N7 của
plan), **ngoài phạm vi lát E ⇒ KHÔNG sửa**. Lát E chỉ có `test_payload_khong_co_requestId`
khoá hành vi đúng.

---

## 4. NỢ NHÂN BẢN (N8) — ghi nhận

`condition_orders.py:_post` (`:120-187`) là **bản chép** từ `derivatives.py:_write_request`
(`:714-782`), rút gọn cho đúng 1 method POST, theo phương án (c) mà coordinator chốt ở
`PLAN_TCBS_ROUND2.md` §5b.

- **Không** import từ `derivatives.py` (file cấm chạm) · **không** refactor file đó.
- **Không cải tiến âm thầm** — mapping lỗi 400/401/403/422/429/5xx giữ nguyên, `Authorization`
  không log, `except BrokerSessionExpiredError: raise` giữ nguyên.
- Chỉ khác 1 chỗ: chữ ký dùng `Dict[str, Any]` thay vì `dict` trần, vì gate mypy chặn
  `Missing type arguments for generic type "dict"` (xem §6).

⇒ Repo nay có **5 bản** `_post`/`_write_request` trùng nhau: `derivatives.py:711`,
`money.py:509`, `equity.py`, `money.py` (lát M), và file mới này. **N8 vẫn mở.**

---

## 5. Gate CHƯA CHẠY

| Gate | Vì sao chưa chạy |
|---|---|
| **Probe server thật** `/khronos/v1/order/condition/cancel` | **Chưa có JWT** — cần Smart OTP từ app TCInvest (N3 của plan). Mọi test đều offline, monkeypatch `requests.request`. |
| **Probe server thật** `/ananke/v1/securities` | Như trên. **Thêm nữa**: `responses.200` trong spec **không có `content`** ⇒ không có schema để đối chiếu, kể cả có JWT cũng chưa biết shape kỳ vọng. |
| Xác nhận server chấp nhận bỏ `subAccountId` | Như trên (xem quyết định ở §2). |

---

## 6. Gate ĐÃ CHẠY — output thật

Tất cả chạy tại `C:\Mujoco Projects\tcbs-e-cond-sec`, sau khi code + test hoàn tất.

```
.venv\Scripts\python.exe -m pytest tests/unit/broker/tcbs/ tests/unit/explorer/tcbs/ -q -p no:cacheprovider
============================= 462 passed in 5.31s =============================
```
> 312 → 346 ở `tests/unit/broker/tcbs/` (**+34** = đúng số test file mới)
> 96 → 116 ở `tests/unit/explorer/tcbs/` (**+20** = đúng số test file mới)

```
.venv\Scripts\python.exe -m pytest tests/contract -q -p no:cacheprovider
============================= 72 passed in 56.97s =============================
```

```
.venv\Scripts\python.exe -m ruff check vnbroker
All checks passed!
EXIT=0
```

```
.venv\Scripts\python.exe scripts/check_mypy_baseline.py
OK: no new strict errors (baseline 1266, now 1161, fixed 105).
EXIT=0
```
> Lần chạy **đầu tiên** ĐỎ (exit 1, **6 lỗi mới**): 4 lỗi trong `condition_orders.py`
> (`Missing type arguments for generic type "dict"` ×3, `Returning Any ... [no-any-return]`)
> + 2 lỗi trong `listing.py` (`Argument "show_log" ... bool | None`, `Missing type arguments
> for generic type "Dict"`). Đã sửa bằng `Dict[str, Any]` + `show_log=bool(show_log)`.
> Lưu ý: `listing.py` đã có sẵn 2 bản lỗi `show_log` trong baseline ⇒ lỗi thứ 3 là lỗi MỚI.

```
.venv\Scripts\python.exe scripts/verify_tcbs_coverage.py
spec sha256 : 7f97d27bde1c6f4b9fb4168bd4ee18c8e9a27fd35e515e3348244e3d2742bd4a  (KHOOP)
spec paths  : 48
da noi      : 41
chua noi    : 7
_REMOVED_PATHS: 18 key | van con trong spec: 0
EXIT=0
```
> **Bằng chứng bắt buộc đạt:** `chua noi` **9 → 7**. `/khronos/v1/order/condition/cancel` và
> `/ananke/v1/securities` **không còn** trong danh sách chưa nối.
> `van con trong spec: 0` ⇒ **không bịa path** (mới nối đúng path có thật, không làm tăng
> số path hư cấu).

```
.venv\Scripts\python.exe -m ruff check tests --output-format=concise
Found 13 errors.
```
> **13 = đúng con số KNOWN-RED ở `dev@3e252ac`, KHÔNG tăng.** Cả 13 nằm ở
> `tests\acceptance\test_tier1_dod.py`, `tests\examples\vci_proxy_demo.py`,
> `tests\test_acb_all_providers.py` — **không file test nào của lát E.**

---

## 7. Bằng chứng fail-trước / pass-sau (hazard 10)

Test được viết **trước**, chạy **trước khi có code**.

### Lần FAIL — broker (chưa có module)

```
.venv\Scripts\python.exe -m pytest tests/unit/broker/tcbs/test_tcbs_condition_order.py -q -p no:cacheprovider
E   ModuleNotFoundError: No module named 'vnbroker.broker.tcbs.condition_orders'
=========================== short test summary info ===========================
ERROR tests/unit/broker/tcbs/test_tcbs_condition_order.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 13.88s ==============================
```

### Lần FAIL — explorer (chưa có method)

```
.venv\Scripts\python.exe -m pytest tests/unit/explorer/tcbs/test_tcbs_ananke_securities.py -q -p no:cacheprovider
FAILED tests/unit/explorer/tcbs/test_tcbs_ananke_securities.py::TestRawDict::test_tra_ve_raw_dict_nguyen_ban - AttributeError: 'Listing' object has no attribute 'get_securities_info'
...
FAILED tests/unit/explorer/tcbs/test_tcbs_ananke_securities.py::TestDocstring::test_docstring_ghi_shape_chua_duoc_tai_lieu_hoa - AttributeError: type object 'Listing' has no attribute 'get_securities_info'
======================== 17 failed, 3 passed in 7.30s =========================
```
> 3 test PASS ngay cả khi FAIL (assert path có trong spec — đọc file spec, không cần code).

### Lần PASS — sau khi viết code

```
.venv\Scripts\python.exe -m pytest tests/unit/broker/tcbs/test_tcbs_condition_order.py tests/unit/explorer/tcbs/test_tcbs_ananke_securities.py -q -p no:cacheprovider
============================= 54 passed in 2.86s ==============================
```

**Ghi chú trung thực:** 1 test từng ĐỎ **cả ở lần chạy đầu tiên có code** —
`TestSignature::test_write_gate_duoc_dung` do tôi viết **sai** (assert `__wrapped__` trên
method **public** trong khi `@write_gate` nằm trên `_gated_cancel_condition_order`, đúng
house style `derivatives.py`). Đã sửa test — không sửa code cho vừa test sai.

---

## 8. Rủi ro còn lại

1. **Service chưa được wire** — `client.py` và `__init__.py` thuộc coordinator (plan §5b).
   `TCBSConditionOrderService` hiện **chỉ import được bằng đường dẫn module**, chưa
   `from vnbroker.broker.tcbs import ...` và chưa gắn vào `TCBSBrokerClient`. **Cần
   coordinator làm ở commit hợp nhất**, nếu không thì AC E1 "nối được" mới chỉ đúng ở tầng file.
2. **`subAccountId` bỏ hay gửi `""`** — chưa có server để quyết (§2).
3. **Nhân bản `_post`** — 5 bản trong repo (N8 vẫn mở).
4. **`derivatives.py` vẫn giữ 3 endpoint condition-order** + 852L; hệ quả gọi huỷ lệnh điều kiện
   giờ có **2 nơi** (`derivatives.cancel_derivative_order` huỷ `/khronos/v1/order/cancel`,
   và file mới huỷ `/khronos/v1/order/condition/cancel`) — khác path nên không trùng chức năng,
   nhưng người đọc dễ lẫn.
5. **Bẫy `write_gate` đã khoá bằng test**: `test_dry_run_keyword_only_default_true` kiểm
   `inspect.Parameter.KEYWORD_ONLY` cho **cả** 2 method — nếu sau này ai đó đổi `dry_run`
   thành positional thì test đỏ, vì `guards.py:46` đọc `dry_run` từ `kwargs`.

---

## 9. Việc ngoài phạm vi thấy nhưng KHÔNG sửa

| # | Vấn đề | Vị trí | Vì sao không sửa |
|---|---|---|---|
| 1 | `requestId` (không tồn tại trong spec) vẫn được gửi | `derivatives.py:702-705`, `equity.py:523-525` | N7 của plan, đã ghi backlog. `derivatives.py` cấm chạm; `equity.py` chỉ còn 2L dưới ngân sách — **cần ticket riêng**. |
| 2 | `derivatives.py` 852L vượt ngân sách | `derivatives.py` | N4 — ngoài phạm vi. |
| 3 | Docstring module `money.py` vẫn ghi *"RULE: Không có write method"* trong khi lát M sẽ thêm write | `money.py:9` | Lát M sửa ở branch khác — **hai nhánh đều sửa cùng dòng docstring này nếu M không chạm tới**. Cần coordinator gộp khi merge. |
| 4 | `write_gate` trả `kwargs_keys` trong envelope (F-9) — tên `pin`/`otp` có thể lọt log | `guards.py:56` | Ngoài phạm vi; file cấm chạm. Ở lát E `kwargs` chỉ có `dry_run` nên không rò. |
| 5 | `_PATHS` docstring của `derivatives.py` vẫn mô tả `condition_orders` là path `condition/detail` | `derivatives.py:44` | Cấm chạm. |

---

## 10. Bài học cho Stage 8

1. **Đặt tên hằng ảnh hưởng tới gate.** `verify_tcbs_coverage.py` chỉ quét hằng `isupper()` **kết
   thúc bằng `PATHS`/`ENDPOINTS`** và **giá trị phải là `dict`**; nếu tên kết thúc bằng `PATHS`
   mà giá trị là chuỗi thì nhánh `continue` làm **hằng đó biến mất khỏi bảng đo**. Vì vậy
   `_SECURITIES_PATH` (số ít) mới được tính, và nó được tính qua nhánh *literal*.
   → Đặt tên hằng mới phải kiểm lại bằng `verify_tcbs_coverage.py`, không "thấy đường dẫn là
   chắc đã nối".
2. **`response` không có `content` ≠ schema rỗng.** `responses.200` thiếu `content` nghĩa là
   **thiếu tài liệu**; dựng DataFrame từ đó là bịa. Hàm trả raw dict + docstring nói rõ.
3. **Gate `mypy --strict` bắt được code mới ngay cả khi file đó "copy y hệt" file khác** —
   vì file cũ đã nằm trong baseline. Copy nguyên văn `-> dict` vào file mới là thêm lỗi mới.
4. **Ghi chú của gate, không phải của tôi, là bằng chứng:** `now 1161` khớp đúng baseline, còn
   6 lỗi lần đầu là lỗi thật của tôi. Đừng báo "PASS" khi chưa sửa.
5. **Fail-before nên chạy 2 lệnh tách** (broker / explorer) vì broker fail ở tầng **import**
   (`ModuleNotFoundError`) làm `Interrupted`, che hết test còn lại — bằng chứng fail của explorer
   sẽ không bao giờ hiện.

---

## 11. Commit

Branch `feat/e-cond-sec`. Xem `git log -1` của branch sau khi commit.