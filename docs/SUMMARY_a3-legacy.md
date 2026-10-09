# SUMMARY — a3-legacy: Gỡ path API legacy TCBS

- **Worktree:** `C:\Mujoco Projects\tcbs-a3-legacy`
- **Branch:** `feat/a3-legacy`
- **Commit:** `de4c7f8d1bcb3567906e77299ea3f8f415a4340a` (`de4c7f8`)
- **Ngày:** 2026-10-09
- **Base:** `bec8b82`

> ⚠ **Việc xoá này CHƯA được probe server.** Đây là quyết định của Owner dựa trên
> 2 tài liệu chính thức. Lý do không probe được: TCBS trả `401` **trước** khi routing
> nên không phân biệt được route tồn tại hay không (bài học DNSE: `GET /accounts/orders
> → 405` mới chứng minh route có).
> **KHÔNG phải kết luận "path không tồn tại trên server"** — chỉ là "không có trong tài liệu".

---

## 1. Kết quả: 18/19 path đã gỡ, 1 giữ lại theo AC6

Task liệt kê **19 path**. Kết quả thực tế: **18 gỡ, 1 giữ lại** (xem §4 — AC6).

### Đã gỡ — `broker/tcbs/account.py` (13 path)

| Path |
|---|
| `/erebos/v1/account/asset` |
| `/erebos/v1/account/available-balance` |
| `/erebos/v1/portfolio-asset` |
| `/erebos/v1/portfolio-asset/token` |
| `/erebos/v1/portfolio/stock/{accountNo}/statistic` |
| `/erebos/v2/accounts/{accountNo}/asset` |
| `/erebos/v2/accounts/{accountNo}/available-balance` |
| `/erebos/v2/accounts/{accountNo}/deposit` |
| `/erebos/v2/accounts/{accountNo}/dividend` |
| `/erebos/v2/accounts/{accountNo}/orders/history` |
| `/erebos/v2/accounts/{accountNo}/orders/matching` |
| `/erebos/v2/accounts/{accountNo}/stock-statistic` |
| `/erebos/v2/accounts/{accountNo}/withdraw` |

### Đã gỡ — `broker/tcbs/equity.py` (5 path)

| Path |
|---|
| `/erebos/v2/order/stop-limit` |
| `/erebos/v2/order/stop-limit/orders` |
| `/erebos/v2/order/stop-limit/{orderId}` |
| `/erebos/v2/order/stop-limit/{orderId}/cancel` |
| `/aion/v1/accounts/{accountNo}/orders/history` |

### Giữ lại (NGOẠI LỆ AC6) — 1 path

| Path | Lý do |
|---|---|
| `/aion/v1/accounts` | `BaseBrokerClient.get_account_list()` là `@abstractmethod` |

---

## 2. File đã đổi (7 file, đúng danh sách cho phép)

| File | Thay đổi |
|---|---|
| `vnbroker/broker/tcbs/account.py` | 937 → **489** dòng. Gỡ 13 key khỏi `_PATHS`; thêm `_REMOVED_PATHS` + `_raise_removed()`. 13 method → stub ném lỗi. |
| `vnbroker/broker/tcbs/equity.py` | 980 → **798** dòng. Gỡ 5 key khỏi `_PATHS`; thêm `_REMOVED_PATHS` + `_raise_removed()`. 5 method → stub ném lỗi. Xoá 3 method private `_gated_*_stop_limit_*`. |
| `vnbroker/broker/tcbs/client.py` | 689 → 708 dòng. **18 wrapper** đánh dấu "ĐÃ GỠ" + docstring giải thích. API surface không đổi (wrapper vẫn còn, ném lại lỗi từ service). |
| `vnbroker/brokerage/tcbs/client.py` | **KHÔNG đổi.** Dùng path scheme `/api/v1/*` riêng (HMAC-SHA256), không gọi bất kỳ method bị gỡ nào. AC7 nói "17 wrapper" ở file này — đã kiểm tra, **không có wrapper nào**. |
| `tests/unit/broker/tcbs/test_tcbs_legacy_removed.py` | **TẠO MỚI** — 87 test. |
| `tests/integration/tcbs/test_tcbs_full_acb.py` | `TestPhase1ErebosAccount` + `TestPhase3StopLimitOrders` → assert ném lỗi. |
| `tests/unit/broker/tcbs/test_account_money.py` | Thêm 2 test AC6 (path được giữ + `get_account_list` vẫn implement). |
| `tests/unit/broker/tcbs/test_equity_derivatives.py` | `TestEquityGetOrderHistory` → assert ném lỗi. |

### Sai lệch so với mô tả task — đã kiểm tra, KHÔNG phải lỗi code

1. **`get_account_list` nằm ở `vnbroker/broker/base.py:55-58`, không phải `brokerage/base.py:55`.**
   `brokerage/base.py` không có `get_account_list` (grep toàn repo xác nhận).
2. **`brokerage/tcbs/client.py` không có 17 wrapper.** 17 wrapper nằm ở
   `broker/tcbs/client.py:161-241` (13 Erebos) + `:395-430` (4 stop-limit). File
   `brokerage/tcbs/client.py` là client thứ hai, hoàn toàn khác (path `/api/v1/*`).
3. **Số wrapper thực tế là 18, không phải 17** — vì `get_order_history`
   (`/aion/v1/accounts/{a}/orders/history`, equity.py) cũng là path bị gỡ và
   `broker/tcbs/client.py:311` có wrapper cho nó.

---

## 3. AC — trạng thái từng acceptance criterion

| # | AC | Trạng thái | Bằng chứng |
|---|---|---|---|
| 1 | 19 path bị xoá khỏi `_PATHS` | ✅ **18/19** | `test_exactly_18_paths_removed`, `test_account_path_not_in_PATHS[13]`, `test_equity_path_not_in_PATHS[5]` |
| 2 | Không còn path `erebos/v1`, `erebos/v2`, `aion/v1/accounts` (không param) | ⚠ **18/19** | `test_forbidden_path_prefix_absent[2]` — path đã gỡ chỉ còn trong `_REMOVED_PATHS` + docstring + message lỗi. `/aion/v1/accounts` giữ theo AC6. |
| 3 | Method công khai ném lỗi rõ ràng, không im lặng trả rỗng | ✅ | `test_account_method_raises[13]`, `test_equity_method_raises[5]`, `test_does_not_silently_return_empty`, `test_client_wrappers_propagate_error` |
| 4 | `account.py` và `equity.py` ≤ 800L | ✅ | 489 và 798. `test_file_under_800_lines[2]` |
| 5 | 37 path còn lại không đổi | ✅ | `test_account_path_unchanged[4]`, `test_equity_path_unchanged[8]`, `test_no_extra_or_missing_keys`, `test_kept_paths_all_present_in_openapi` (đọc `openapi-v1.0.0.json` thật) |
| 6 | `get_account_list` là `@abstractmethod` — không phá hợp đồng | ✅ **NGOẠI LỆ** | Path giữ lại. `TestAc6AccountListException[7 test]` |
| 7 | 17/18 wrapper gọi method bị xoá phải sửa hoặc bỏ | ✅ | 18 wrapper đánh dấu "ĐÃ GỠ", vẫn delegate nên ném lỗi. `test_client_removed_wrappers_still_exist_but_raise` |

---

## 4. AC6 — NGOẠI LỄ `/aion/v1/accounts`: giữ lại, có lý do

**Task yêu cầu xoá `/aion/v1/accounts` nhưng AC6 nói: nếu không tìm được nguồn thay thế
trong spec thì GIỮ LẠI. Đã giữ.**

Lý do cụ thể:

- `BaseBrokerClient.get_account_list()` là `@abstractmethod`
  (`vnbroker/broker/base.py:55-58`). Xoá nó ⇒ `TCBSBrokerClient` thành class abstract
  ⇒ **hỏng hợp đồng**, mọi test instantiate client sẽ fail.
- Ứng viên thay thế duy nhất trong spec: `/aion/v1/customers/{custodyId}/accounts`.
  **Không dùng được** — nó cần `custodyId`, tức là cần **chính thông tin mà
  `get_account_list()` sinh ra**. Vòng tròn luận lý.
- Không có endpoint nào khác trong 48 path liệt kê danh sách tài khoản mà không cần
  tham số đầu vào.

Đã ghi ngoại lệ ở 3 nơi: module docstring `account.py`, comment cạnh key `list_accounts`
trong `_PATHS`, docstring `get_account_list()` ở `client.py`. Có test chống regression.

**Cần Owner quyết:** giữ nguyên, hay chấp nhận thay đổi hợp đồng (bỏ `@abstractmethod`).

---

## 5. FAIL → PASS (test mới chứng minh được)

Quy trình: copy 6 file gốc ra `%TEMP%\tcbs-a3-backup` **trước**, rồi restore bằng `Copy-Item`
từ backup (KHÔNG dùng `git checkout --`).

**Trước khi sửa source** (đã restore `account.py` + `equity.py` về bản gốc):

```
.venv\Scripts\python.exe -m pytest tests/unit/broker/tcbs/test_tcbs_legacy_removed.py -q -p no:cacheprovider
→ 69 failed, 18 passed in 21.16s
```

**Sau khi sửa:**

```
→ 87 passed in 3.62s
```

⚠ 3 lần fail đầu tiên sau khi sửa là **lỗi của chính test**, không phải của source —
đã sửa và ghi ở §9.

---

## 6. Gate — output thật

### 6.1 Baseline (đo trên chính worktree này, TRƯỚC khi sửa)

```
.venv\Scripts\python.exe -m pytest tests/ -q --timeout=300 -p no:cacheprovider
→ 1 failed, 1492 passed, 30 skipped, 2 warnings in 137.34s (0:02:17)
   FAILED tests/integration/test_dnse_integration.py::TestEnvVisibility::test_the_env_is_actually_visible
   AssertionError: khong thay DNSE_API_SECRET trong moi truong

.venv\Scripts\python.exe -m ruff check vnbroker     → All checks passed!  (exit 0)
.venv\Scripts\python.exe scripts/check_mypy_baseline.py
→ OK: no new strict errors (baseline 1266, now 1207, fixed 59).   (exit 0)
.venv\Scripts\python.exe -m ruff check tests       → Found 13 errors.  (KNOWN-RED)
```

> **Lưu ý quan trọng:** worktree KHÔNG có file `.env` (gitignore) ⇒ 1 failure DNSE là
> **pre-existing**, không phải do thay đổi này. Số liệu main tree khác worktree này.

### 6.2 Sau khi sửa

```
.venv\Scripts\python.exe -m pytest tests/ -q --timeout=300 -p no:cacheprovider
→ 1 failed, 1597 passed, 30 skipped, 2 warnings in 127.97s (0:02:07)
   FAILED tests/integration/test_dnse_integration.py::TestEnvVisibility::test_the_env_is_actually_visible
   AssertionError: khong thay DNSE_API_SECRET trong moi truong

.venv\Scripts\python.exe -m ruff check vnbroker
→ All checks passed!
   RUFF_EXIT=0

.venv\Scripts\python.exe scripts/check_mypy_baseline.py
→ OK: no new strict errors (baseline 1266, now 1161, fixed 105).
   Note: run with --update to shrink the baseline.
   MYPY_EXIT=0

.venv\Scripts\python.exe -m ruff check tests
→ Found 13 errors.
   RUFF_TESTS_EXIT=1        ← 13 KNOWN-RED, KHÔNG tăng so với baseline
```

**Tái lập:** `cd C:\Mujoco Projects\tcbs-a3-legacy` rồi chạy 4 lệnh trên.

### 6.3 Gate CHƯA CHẠY

| Gate | Lý do |
|---|---|
| Probe server TCBS (xác minh 18 path thật sự không phục vụ) | Cần `TCBS_API_KEY` + OTP còn hiệu lực. **Và ngay cả khi có token vẫn không phân biệt được** vì 401 chạy trước routing — cần token hợp lệ + so sánh status với một path chắc chắn sai. Đây là việc của Giai đoạn 0 theo `docs/PROPOSAL_TCBS_REBUILD_20261009.md` §9. |
| Test integration TCBS thật (`-m integration`) | `SKIPPED [1] ... TCBS_API_KEY not set`. Worktree không có `.env`. |
| So sánh với main tree | Không chạy — task giới hạn chỉ trong worktree này. |

---

## 7. Rủi ro

| # | Rủi ro | Mức | Giảm nhẹ |
|---|---|---|---|
| R1 | **18 path có thể vẫn được TCBS phục vụ.** Nếu có, người dùng gọi sẽ nhận `NotImplementedError` thay vì dữ liệu thật. | **CAO** | Đây là rủi ro đã được Owner chấp nhận. Ném lỗi rõ ràng còn hơn trả rỗng im lặng. Cần probe ở Giai đoạn 0 trước khi ra mắt. |
| R2 | `get_order_history` bị gỡ ⇒ mất chức năng lịch sử lệnh. Đường thay thế `/aion/v1/accounts/{a}/orders` trả **lệnh trong ngày**, không có filter ngày. | TRUNG BÌNH | Message lỗi chỉ đường `/aion/v1/accounts/{a}/matching-details` cho khớp lệnh. |
| R3 | 4 method stop-limit mất hoàn toàn, không có đường thay thế tương đương trong spec. | TRUNG BÌNH | Đã ghi rõ trong docstring + message lỗi. |
| R4 | AC2 không đạt 100% (`/aion/v1/accounts` còn trong mã). | THẤP | Có ngoại lệ có tài liệu + 7 test chống regression. Cần Owner xác nhận. |
| R5 | Downstream code gọi 18 method này sẽ crash (`NotImplementedError`) thay vì fail âm thầm. | THẤP | Đây là **chủ ý** — fail rõ ràng hơn trả rỗng. Grep toàn repo không tìm thấy caller nào ngoài wrapper. |
| R6 | `NotImplementedError` không thuộc hệ `BrokerError` ⇒ code đang `except BrokerError` sẽ không bắt được. | THẤP | Cân nhắc đổi sang exception riêng nếu Owner muốn nhất quán. Đã chọn `NotImplementedError` vì semantic đúng (tính năng không được implement) và không cần file exception ngoài danh sách cho phép. |

---

## 8. Bài học

1. **`Get-Content -Raw` + `Substring` + `Set-Content` KHÔNG an toàn để splice file nhiều dòng.**
   Lần đầu dùng cách này để thay 586 dòng trong `account.py` ⇒ file bị hỏng (method bị
   nhân bản lên đầu file). Phải khôi phục từ backup và làm lại bằng tool Edit.
   → **Dùng `Edit` với `oldString`/`newString` nguyên khối.** Backup vẫn phải làm trước.
2. **`Measure-Object -Line` đếm SAI** — bỏ qua dòng trống, báo 927 dòng cho file thực sự 937.
   → Dùng `len(open(p, encoding="utf-8").read().splitlines())` để kiểm tra giới hạn CLAUDE.md.
3. **`_raise_removed` phải ghi `-> NoReturn`, không phải `-> None`.** Ban đầu dùng `-> None`
   ⇒ mypy báo **18 lỗi mới** `Missing return statement` ở 18 method stub (vì mypy nghĩ có
   nhánh return). Gate `check_mypy_baseline.py` bắt được ngay. Đây là lý do gate này có ích.
4. **`AnnAssign` ≠ `Assign` trong AST.** Test dò path bằng `ast` bỏ sót `_REMOVED_PATHS`
   vì nó có type annotation (`_REMOVED_PATHS: dict[str, str] = {...}`) ⇒ node là
   `AnnAssign` không phải `Assign`. → Khi quét AST phải xử lý **cả hai**.
5. **Test AC2 cần whitelist vùng được phép.** Path đã gỡ **phải** còn trong `_REMOVED_PATHS`
   để giải thích lý cho người đọc. Test ban đầu quét mọi string literal ⇒ fail dù code đúng.
   → Dùng `node.lineno`/`end_lineno` để whitelist chính xác registry + `_raise_removed`.
6. **Module docstring của `equity.py` mô tả sai endpoint.** Nó ghi `/gaia/v1/openapi/account/...`
   nhưng `_PATHS` thật là `/aion/` và `/akhlys/` — `/gaia/` chỉ dùng cho OAuth token.
   Docstring sai khiến người đọc tin nhầm API nào thật sự được gọi. Đã sửa khi gỡ path.
7. **Baseline phải đo trên chính worktree.** Worktree không có `.env` ⇒ 1 failure DNSE
   là pre-existing. Lấy số liệu từ main tree sẽ tưởng mình vừa làm hỏng test.

---

## 9. Sai sót của chính lần làm này (đã sửa, ghi để không lặp lại)

| Sai sót | Cách phát hiện | Đã sửa |
|---|---|---|
| Splice file bằng PowerShell làm hỏng `account.py` | `git diff --stat` + AST parse fail | Khôi phục backup, làm lại bằng Edit |
| Bỏ indent 4 space của `def get_order_history` | `ast.parse` → `IndentationError:219` | Thêm lại indent |
| `_raise_removed -> None` gây 18 lỗi mypy | `check_mypy_baseline.py` exit 1 | Đổi thành `NoReturn` |
| Test `test_equity_method_raises` đặt `pytest.raises` sai chỗ, nuốt luôn vòng lặp tham số | 5 test fail `DID NOT RAISE` | Tách `pytest.raises` ra ngoài, dùng cờ `raised` |
| Test quét AST bỏ sót `AnnAssign` | 2 test fail | Xử lý cả `Assign` và `AnnAssign` |
| Import sai `vnbroker.broker.tcbs.session` | `ModuleNotFoundError` | Sửa thành `vnbroker.broker.session` |

---

## 10. Việc còn lại (không làm trong slice này)

1. **Owner xác nhận AC6**: giữ `/aion/v1/accounts` (hiện tại), hay đổi hợp đồng.
2. **Probe server** ở Giai đoạn 0 — `docs/PROPOSAL_TCBS_REBUILD_20261009.md` §9 mô tả cách
   (bài học DNSE: `405` chứng minh route có, `401` không chứng minh gì).
3. Nếu probe xác nhận 18 path vẫn sống ⇒ hoàn nguyên bằng `git revert de4c7f8` (commit sạch,
   không cần thủ công).
4. Cân nhắc exception riêng cho "path đã gỡ" thay vì `NotImplementedError` (rủi ro R6).
5. Chạy `check_mypy_baseline.py --update` để thu nhỏ baseline (1266 → 1161).