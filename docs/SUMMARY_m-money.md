# SUMMARY — lát M (TCBS Round 2, GĐ5 — 4 endpoint tiền/vay)

**Agent:** M · **Branch:** `feat/m-money` · **Base:** `dev @ 3e252ac`
**Kế hoạch:** `docs/PLAN_TCBS_ROUND2.md` §3 (S-M, AC M1..M9) · **Audit:** `docs/PLAN_AUDIT_TCBS_ROUND2.md` (F-5, F-6/P5, §4)
**Spec:** `docs/references/openapi-v1.0.0.json` — sha256 `7f97d27b…42bd4a` (KHOOP, `verify_tcbs_coverage.py` tự kiểm)

> **Trạng thái: HOÀN TẤT 9/9 AC. Không có blocker kỹ thuật chặn merge lát này.**
> 2 việc còn lại thuộc **coordinator** (wire `client.py` + `__init__.py`) — xem §7.

---

## 1. File đã đổi

| File | Hành động | Dòng |
|---|---|---|
| `vnbroker/broker/tcbs/money.py` | sửa | 563 → **791** (`git diff --stat`: `235 insertions(+), 7 deletions(-)`) |
| `tests/unit/broker/tcbs/test_tcbs_money_endpoints.py` | **tạo mới** | 419 dòng, 49 test |

Không đụng file nào ngoài claim (`auth.py`, `token_manager.py`, `__init__.py`, `client.py`,
`equity.py`, `derivatives.py`, `guards.py`, `session.py`, `explorer/**`, test có sẵn).

**4 endpoint mới trong `_PATHS`** (`money.py:57-60`):

```python
"pricing_policy": "/hydros/v1/account/{accountNo}/pricing-policy",
"cash_deposit":   "/khronos/v1/cash/deposit/update",
"cash_withdraw":  "/khronos/v1/cash/withdraw/update",
"stock_transfer": "/physis/v1/stock/transfer",
```

**Method công khai mới** (coordinator wire vào `client.py`):

| Method | Line | Verb |
|---|---|---|
| `get_pricing_policy(account_no, product_id=None)` | `money.py:525` | GET |
| `deposit_margin(account_id, sub_account_id, amount, payment_content="", *, dry_run=True)` | `money.py:553` | POST |
| `withdraw_margin(...)` — tham số giống trên | `money.py:593` | POST |
| `transfer_between_sub_accounts(source_account_number, destination_account_number, amount, description, *, dry_run=True)` | `money.py:626` | POST |

---

## 2. AC — 9/9 đạt

| AC | Yêu cầu | Bằng chứng | Trạng thái |
|---|---|---|---|
| **M1** | `pricing-policy`: `productId` không gửi khi rỗng; validate `account_no` | `money.py:542-546`; test `TestPricingPolicyRead` 6 test, gồm `product_id=None`/`""` ⇒ `params == {}` | ✅ |
| **M2** | deposit: `@write_gate`, `dry_run=True` mặc định, `amount > 0` **trước** gate | `money.py:553-580` | ✅ |
| **M3** | withdraw: như M2 | `money.py:593-608` | ✅ |
| **M4** | transfer: `description` bắt buộc theo spec | `money.py:643` (`MISSING_DESCRIPTION`) | ✅ |
| **M5** | cả 3 write đi qua `@write_gate`; `dry_run=False` chưa `enable_write()` ⇒ `BrokerPermissionError`, **không** gửi HTTP | `TestWriteGateBothBranches` — 3 method × 3 nhánh = 9 test | ✅ |
| **M6** | body đúng tên field spec; **không** `requestId` | `TestBodyMatchesSpec` 5 test, assert `body == {...}` (so khớp từng key) | ✅ |
| **M7** | đọc field response bằng `.get()`, không `[...]` | `TestMissingResponseFields` 5 test + `test_money_py_khong_dung_index_de_doc_response` | ✅ |
| **M8** | `money.py` ≤ 800L | **791L** — lệnh tái lập ở §4 | ✅ |
| **M9** | sửa docstring "RULE: Không có write method" | `money.py:1-24` (docstring module) + `money.py:66` (docstring class) | ✅ |

### Ghi chú M2/M3 — bằng chứng thứ tự "validate TRƯỚC gate"

`test_amount_am_validate_truoc_gate` gọi `deposit_margin(..., 0)` **với `dry_run=True`** và
đòi phải ném `BrokerValidationError`. Nếu gate chạy trước validation thì `dry_run=True` sẽ
trả envelope ⇒ test đỏ. Vậy test chứng minh **thứ tự**, không chỉ "có validate".

---

## 3. Bằng chứng fail-trước / pass-sau (hazard 10)

Quy trình (không dùng `git checkout --`): copy file ra `%TEMP%` → `git show HEAD:<file> > <file>`
→ chạy → copy ngược lại.

### Lần FAIL — `money.py` ở `HEAD` (563L, chưa có code lát M)

```powershell
Copy-Item "vnbroker/broker/tcbs/money.py" "$env:TEMP\money_sliceM_backup.py" -Force
git show HEAD:vnbroker/broker/tcbs/money.py > vnbroker/broker/tcbs/money.py
.venv\Scripts\python.exe -m pytest tests/unit/broker/tcbs/test_tcbs_money_endpoints.py -q -p no:cacheprovider
```

Output thật (rút gọn):

```
FAILED ...::TestPricingPolicyRead::test_path_dung_spec
FAILED ...::TestPricingPolicyRead::test_product_id_none_khong_gui
FAILED ...::TestPricingPolicyRead::test_product_id_rong_khong_gui
FAILED ...::TestPricingPolicyRead::test_product_id_co_duoc_gui
...
FAILED ...::TestMissingResponseFields::test_withdraw_response_khong_con_oID_va_rs - AttributeError: 'TCBSMoneyService' object has no attribute 'withdraw_margin'
FAILED ...::TestMissingResponseFields::test_pricing_policy_response_rong - AttributeError: 'TCBSMoneyService' object has no attribute 'get_pricing_policy'
FAILED ...::TestMoneyModuleContract::test_docstring_khong_con_noi_khong_co_write_method - assert 'RULE: Kh\xf4ng c\xf3 write method' not in '...'
======================== 47 failed, 2 passed in 3.92s =========================
```

**47 failed, 2 passed.** 2 test xanh là 2 assert của dạng phủ định vô hại.

### Lần PASS — sau khi khôi phục code lát M

```powershell
Copy-Item "$env:TEMP\money_sliceM_backup.py" "vnbroker/broker/tcbs/money.py" -Force
.venv\Scripts\python.exe -m pytest tests/unit/broker/tcbs/test_tcbs_money_endpoints.py -q -p no:cacheprovider
```

```
============================= 49 passed in 2.74s =============================
```

### Đối chứng độc lập — bằng chứng code THỰC SỰ nối endpoint, không chỉ là test xanh

Cùng lệnh `verify_tcbs_coverage.py`, chạy ở hai trạng thái:

| Trạng thái `money.py` | Kết quả |
|---|---|
| `HEAD` (bản gốc) | `chua noi : 9` |
| Bản lát M | `chua noi : 5` |

Con số 9 → 5 **sinh ra từ thay đổi của lát M**, không tới từ yếu tố khác.

---

## 4. Gate — **đã chạy thật**, dán dòng kết quả

Tất cả chạy tại worktree `C:\Mujoco Projects\tcbs-m-money`, branch `feat/m-money`.

| # | Lệnh | Baseline `dev@3e252ac` | Kết quả lát M | Exit |
|---|---|---|---|---|
| 1 | `.venv\Scripts\python.exe -m pytest tests/unit/broker/tcbs/ -q -p no:cacheprovider` | `312 passed` | **`361 passed in 7.18s`** | 0 |
| 2 | `.venv\Scripts\python.exe -m pytest tests/contract -q -p no:cacheprovider` | `72 passed` | **`72 passed in 56.51s`** | 0 |
| 3 | `.venv\Scripts\python.exe -m ruff check vnbroker` | `All checks passed!` | **`All checks passed!`** | 0 |
| 4 | `.venv\Scripts\python.exe scripts/check_mypy_baseline.py` | `OK: no new strict errors (baseline 1266, now 1161, fixed 105)` | **`OK: no new strict errors (baseline 1266, now 1161, fixed 105)`** | 0 |
| 5 | `.venv\Scripts\python.exe scripts/verify_tcbs_coverage.py` | `chua noi : 9` | **`chua noi : 5`** | 0 |

Chi tiết gate 5 (output đầy đủ):

```
spec sha256 : 7f97d27bde1c6f4b9fb4168bd4ee18c8e9a27fd35e515e3348244e3d2742bd4a  (KHOOP)
spec paths  : 48
da noi      : 43
chua noi    : 5
_REMOVED_PATHS: 18 key | van con trong spec: 0
```

5 path còn lại **không phải của lát M**, đều thuộc lát khác hoặc N1:
`/ananke/v1/securities` + `/khronos/v1/order/condition/cancel` (lát E) ·
`/gaia/v1/oauth2/openapi/apikey/info` + `…/apikey/extend` (lát T) ·
`/api/v1/derivatives/contracts` (N1 — spec tự mâu thuẫn, chờ Owner).

**M8 — đo ngân sách dòng (AC cứng):**

```powershell
(Get-Content vnbroker/broker/tcbs/money.py -Encoding utf8).Count   # → 791
```

791 ≤ 800 ✅. Cũng đã có test tự khoá: `TestMoneyModuleContract::test_money_py_khong_vuot_800_dong`.

**`ruff check tests` (KNOWN-RED, chỉ đòi không tăng):**

```powershell
.venv\Scripts\python.exe -m ruff check tests
# Found 13 errors.   ← đúng bằng baseline 13, KHÔNG tăng
# exit=1 (đã đỏ sẵn)
```

Kiểm tra file mới có bị flag không:
```powershell
.venv\Scripts\python.exe -m ruff check tests 2>&1 | Select-String "test_tcbs_money_endpoints" | Measure-Object
# → Count: 0
```

**Gate CHƯA CHẠY (có lý do):**

| Gate | Lý do |
|---|---|
| Probe server thật TCBS (kiểm tra response `rc`/`oID` thật, xem server có thật sự chấp nhận body không có `requestId`) | **Chưa có JWT.** Cần Smart OTP từ app TCInvest. Đây là lý do N3 của plan. **Không suy ra "chắc là được" từ test offline.** |
| `pytest tests/` toàn repo (1696 test, ~3 phút) | Không nằm trong 5 gate được giao cho lát M; 2 thư mục liên quan (`tests/unit/broker/tcbs/`, `tests/contract/`) đã chạy đầy đủ |

---

## 5. Quyết định thiết kế đáng ghi lại

### 5.1 `_post` cho `money.py` — trùng lệnh có chủ đích, đã ghi nợ (N8)

`_post` viết riêng cho `money.py`, **không** import từ `derivatives.py` (file bị cấm chạm) và
**không** refactor file người khác. Xử lý lỗi **giống hệt `_get` cùng file** (401 → revoke +
`TOKEN_EXPIRED`, 403 → `FORBIDDEN`, 5xx → `SERVER_ERROR`, timeout → `NETWORK_TIMEOUT`,
cùng thông điệp tiếng Việt, cùng exception class). Docstring của `_post` trỏ thẳng về
`derivatives.py:714` và `equity.py:651` để người đọc sau thấy đây là **nợ N8**, không phải
lựa chọn kiến trúc.

### 5.2 Rút `_check_status` dùng chung `_get` + `_post`

Bản đầu tiên copy nguyên khối 19 dòng xử lý status sang `_post` ⇒ `money.py` **860 dòng, vượt
M8**. Thay vì bóp docstring hoặc bỏ bớt kiểm tra lỗi, rút 19 dòng đó thành `_check_status(resp)`
(`money.py:744`) dùng chung — **hành vi `_get` không đổi một byte**, test cũ 312 test vẫn xanh
là bằng chứng. Đây là refactor **trong file của mình**, không đụng file người khác.

### 5.3 `get_pricing_policy` trả raw dict, **không** ép DataFrame

Spec không mô tả schema `responses.200` (không có `content`) ⇒ bịa tên cột là hư cấu.
Cùng lập luận với E5 của lát E. Docstring ghi rõ lý do.

### 5.4 Write method trả **nguyên envelope** của TCBS, không chuẩn hoá

`deposit/withdraw` trả `{cmd, rc, rs, oID, data}` và transfer trả `{code, message}` — đúng
như spec, không đổi tên field (đổi tên `oID` → `order_id` là tự đặt hợp đồng mới). Hệ quả
vận hành nêu ở §6 R1.

---

## 6. Rủi ro còn lại

| # | Mức | Rủi ro | Bằng chứng / đường tái lập |
|---|---|---|---|
| **R1** | **Cao** | **HTTP 200 ≠ giao dịch thành công.** Spec ghi `rc`: *"1: success, < 0: error"* và `code`: *"200 = success"*. Cả 3 write method trả nguyên envelope ⇒ **caller phải tự kiểm `rc == "1"` / `code == "200"`**, nếu không sẽ tưởng nạp/rút/chuyển thành công khi server đã báo lỗi nghiệp vụ. Chưa có test nào chốt được điều này vì **chưa có response thật** | spec `openapi-v1.0.0.json` (`rc`, `code`) |
| **R2** | Trung bình | **`_post` không map 400/422/429**, chỉ 401/403/5xx ⇒ lỗi 4xx khác rơi xuống `resp.json()` và **trả về như thành công**. Đây là **cùng hành vi với `_get` cùng file** (giữ đúng lệnh "theo style `_get` sẵn có"), nhưng `derivatives._write_request:757-774` thì **có** map 400/422/429 ⇒ hai tầng write trong cùng repo hành xử khác nhau | `money.py:702-742` vs `derivatives.py:757-774` |
| **R3** | Trung bình | **`requestId` hư cấu vẫn còn ở `equity.py:523-525` và `derivatives.py:702-705`** (N7). Lát M **không** copy pattern đó, nhưng hai file kia vẫn gửi field không có trong spec | đếm `requestId` trong spec = **0** lần (lệnh §8) |
| **R4** | Thấp | `_validate_amount` ép `float()`, nên `amount="1e9"` được chấp nhận. Vô hại với server (gửi `double`) nhưng không khớt chặt kiểu | `money.py:769-783` |
| **R5** | Thấp | Test `test_money_py_khong_vuot_800_dong` dùng đường dẫn **tương đối** ⇒ phụ thuộc CWD = repo root. Đúng convention sẵn có của `test_tcbs_legacy_removed.py:426` nên không sửa | — |
| **R6** | Thấp | 3 endpoint mới **chưa** được wire vào `TCBSBrokerClient` (`client.py`) ⇒ gọi từ facade hiện chưa được. Đúng thiết kế lát (coordinator giữ `client.py` để tránh weld) | §7 |

---

## 7. Việc ngoài phạm vi — thấy nhưng KHÔNG sửa

1. **`client.py` (facade) + `__init__.py`** — chưa wire 4 method mới + chưa export.
   Cả hai thuộc danh sách "coordinator giữ" (plan §5). **Đây là việc còn lại để lát M dùng được
   từ facade** — không phải blocker kỹ thuật.
2. **N7 — gỡ `requestId` khỏi `equity.py:523-525` + `derivatives.py:702-705`**: `derivatives.py`
   bị cấm chạm; `equity.py` chỉ còn 2L dưới ngân sách. **Mở ticket riêng.**
3. **N8 — gộp 4 bản `_post`/`_write_request`**: đã trở thành **5** bản sau lát này
   (`derivatives.py:714`, `equity.py:651`, `money.py:702`, + 2 file mới của lát E). Không
   refactor âm thầm.
4. **N4 — `derivatives.py` 852L đã vượt 800**: không đụng.
5. **`explorer/tcbs/quote.py` 793L / `websocket.py` 791L**: chỉ còn 7–9L dưới ngân sách, lát
   sau thêm là vượt im lặng. Ghi nhớ cho Stage 8.

---

## 8. Bài học cho Stage 8

1. **`write_gate` đọc `dry_run` từ `kwargs` (`guards.py:46`) ⇒ test quên `dry_run=False` sẽ
   xanh MÀ SAI.** Lần viết test đầu, 18 test đỏ vì tôi quên `dry_run=False` ở nhánh "live".
   Nguy hiểm thật nằm ở chiều ngược lại: một test kiểu *"response thiếu field không KeyError"*
   mà **quên** `dry_run=False` sẽ **PASS TRÁI Ý NGHĨA** — nó chỉ kiểm tra envelope dry-run, chưa
   từng chạm tới `resp.json()`. Vì vậy mọi test "live" ở đây **luôn** assert
   `m.assert_called_once()` / so payload, không chỉ assert kết quả trả về.
2. **mypy baseline đếm lỗi TRÙNG LẶP theo file** (`check_mypy_baseline.py:40-52`: *"adding a
   second identical error in the same file still counts as new"*). Viết `params: dict = {}`
   trong code mới là **lỗi mới**, dù file đã có 11 lỗi `type-arg` y hệt từ trước. Phải viết
   `dict[str, Any]`. Nếu không biết điều này thì sẽ tưởng mình "không thêm lỗi nào".
3. **Fail-before/pass-after bắt được loại bug mà test xanh không bắt được.** Ở đây nó còn bắt
   luôn **bằng chứng nối endpoint**: `verify_tcbs_coverage.py` chạy ở cả hai trạng thái cho ra
   `9` vs `5`. Đây là bằng chứng rẻ nhất và mạnh nhất — nên chạy cho **mọi** lát có thêm path.
4. **Đọc spec, không tin bản tóm tắt của kế hoạch** (P5): đếm `requestId` trong toàn spec = 0,
   trong khi `equity.py` vẫn gửi. Lát nào có "tiền đề" về tên field đều phải đếm lại.
5. **Ngân sách 800L là ràng buộc thiết kế, không phải kiểm tra cuối.** Bản đầu copy `_post`
   nguyên khối lên 860L. Cách thoát đúng là **rút phần trùng lặp trong file của mình**
   (`_check_status`), **không** phải cắt bớt docstring hay bỏ bớt kiểm tra lỗi — hai cách sau
   làm giảm chất lượng để đổi lấy một con số.
6. **Sửa file với `Edit` xong phải `ast.parse` + đếm `FunctionDef` trùng tên.** Một lần sửa
   xoá nhầm dòng `def _post(...)` và một lần tạo trùng `_require_text`; cả hai đều lọt qua mắt
   và chỉ bị lộ khi chạy script kiểm tra node trùng tên.

---

## 9. Lệnh tái lập toàn bộ

```powershell
# 5 gate
.venv\Scripts\python.exe -m pytest tests/unit/broker/tcbs/ -q -p no:cacheprovider
.venv\Scripts\python.exe -m pytest tests/contract -q -p no:cacheprovider
.venv\Scripts\python.exe -m ruff check vnbroker
.venv\Scripts\python.exe scripts/check_mypy_baseline.py
.venv\Scripts\python.exe scripts/verify_tcbs_coverage.py

# M8 — ngân sách dòng
(Get-Content vnbroker/broker/tcbs/money.py -Encoding utf8).Count

# P5 — requestId là hư cấu (0 lần trong toàn spec)
.venv\Scripts\python.exe -c "print(open('docs/references/openapi-v1.0.0.json',encoding='utf-8').read().count('requestId'))"

# M6 — body đúng tên field
.venv\Scripts\python.exe -m pytest tests/unit/broker/tcbs/test_tcbs_money_endpoints.py::TestBodyMatchesSpec -v

# M5 — cả 2 nhánh gate cho cả 3 endpoint
.venv\Scripts\python.exe -m pytest tests/unit/broker/tcbs/test_tcbs_money_endpoints.py::TestWriteGateBothBranches -v
```