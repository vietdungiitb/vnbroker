# TEST_REPORT_DNSE_FIX: Bằng chứng kiểm chứng đợt sửa DNSE OpenAPI

- **Base**: `f6cf68b` · **HEAD**: `d8fab65` · **Ngày**: 2026-10-16
- **Máy**: dev Windows · **Python**: 3.13 (venv) · **Ngày**: phiên 14:00–18:30 ICT

> **Lessons áp dụng: [L-E01, L-E02, L-E03, L-E04, L-E05, L-E06, L-E07]**

## 1. Baseline @ `f6cf68b` (đo trước khi sửa)

| Lệnh | Kết quả | Exit |
|---|---|---|
| `pytest tests/ -q --timeout=300` | 2177 passed, 26 skipped, 3 subtests (187s) | 0 |
| `pytest tests/contract -q` | 117 passed | 0 |
| `pytest tests/unit/connector/dnse tests/contract -q` | 332 passed | 0 |
| `ruff check vnbroker tests/unit tests/contract` | All checks passed | 0 |
| `ruff check tests` | 13 KNOWN-RED | 1 |
| `scripts/check_mypy_baseline.py` | baseline 1266, now **1138** | 0 |
| `scripts/check_lessons.py` | 24/40 lesson | 0 |

> ⚠ **Số sai đã từng được chép sai.** `CLAUDE.md` ghi "1414 passed, 30 skipped" và
> `docs/AGENT_PROTOCOL.md` bản đầu ghi contract = **72**. Cả hai đều cũ. Audit
> bắt được; đã đo lại thành 2177 / 117 (L-E01).

## 2. Sau khi sửa @ `d8fab65`

### 2.1 Cổng đầy đủ — `pwsh -File scripts\check_all.ps1`

| Gate | Trạng | Chi tiết |
|---|---|---|
| `ruff-src` | **PASS** | All checks passed |
| `ruff-tests-all` | KNOWN-RED | 13 lỗi, **không tăng** so với baseline |
| `version-sync` | **PASS** | 3.7.2 (pyproject, README, CLAUDE.md, config.py, tests/, dist) |
| `lessons` | **PASS** | 24/40 lesson — sạch |
| `tcbs-coverage` | **PASS** | spec sha256 khoá |
| `tcbs-bodies` | **PASS** | lệch đã biết: 0 |
| `provider-consistency` | **PASS** | không vi phạm |
| `mypy-baseline` | **PASS** | baseline 1266, now **1133**, fixed 133 |
| `encoding` | **PASS** | 449 file, không mojibake (cổng mới) |
| `pytest-contract` | **PASS** | 117 passed |
| `pytest-full` | **PASS** | **2246 passed, 26 skipped**, 3 subtests (162s) |

**`CHECK_ALL_EXIT=0`.**

### 2.2 Delta số đo

| Chỉ số | Baseline | Sau | Delta |
|---|---|---|---|
| `pytest tests/` | 2177 passed | **2246 passed** | **+69** |
| `tests/unit/connector/dnse` | 332 (kèm contract) | 284 DNSE + 117 contract = **401** | +69 |
| `mypy` (số lỗi) | 1138 | **1133** | **−5** |

> Không có "delta" nào được suy ra: cả hai vế đều **chạy thật**.

### 2.3 Cổng mới: `scripts/check_encoding.py`

| Chế độ | Kết quả |
|---|---|
| `--self-test` | **3/3** (sạch / double-encoding / smart-quote) |
| quét | **449 file, 0 mojibake**, exit 0 |

Cổng này có **vì sao** riêng: blocker nghiêm trọng nhất của đợt này lọt qua
**mọi** gate hiện có vì file hỏng vẫn decode hợp lệ là UTF-8. Chi tiết ở
`docs/AUDIT_DNSE_FIX_20261016.md` §3.

## 3. Kiểm chứng **giá trị** của test (mutation test)

Vì một test xanh **không** chứng minh nó kiểm được gì, từng fix đã được đảo ngược
tạm thời rồi chạy lại:

| Fix đảo ngược | Kết quả mong đợi | **Thực tế** |
|---|---|---|
| Bỏ chuẩn hoá ms trong `_history_query` | test đỏ | **6 test FAIL** |
| Đưa `quote.py` về `json_normalize` | test đỏ | **1 test FAIL** |
| Cho `page_index=None` gửi đi | test đỏ | **1 test FAIL** |
| Xoá `GIÂY` khỏi docstring | test đỏ | **5 test FAIL** |

⇒ **4/4 mutation đều bị test bắt.** Sau mỗi lần đảo, file được khôi phục và
suite xanh lại (282 → … → 401 passed).

## 4. Kiểm chứng **live** trên production (không VPN)

Lệnh: `.venv\Scripts\python.exe scripts\probe_dnse_readonly.py`
Kết quả: **`PASS=40 FAIL=16`** — 16 FAIL là **probe phủ định có chủ ý**.

| Defect | Trước khi sửa | Sau khi sửa (đo lại) |
|---|---|---|
| D1 working-dates | trả hằng, 0 ms | **200**, 257 `workingDates` |
| D2 `get_orders` | `400 pageIndex is required` | **200** |
| D3/D4 order_history | `400 from/to is required` | **200** |
| D5 corporate-action | `404 API ROUTE NOT FOUND` | **200** `{accountNo, data, pagination}` |
| D6 `position_id="fake"` | gửi đi ⇒ **500** | **chặn client-side, 0 request** |
| D7 volume-profile | `400 invalid param 'time'` | **200** với `time="2026-10-16", boardId="G1"` |
| D8 ms | `400 range exceeds maximum time range` | **tự chuẩn hoá thành giây → 200** |
| D9 market_index | không guard | chặn trước network; cùng ngày **200** |
| D10 `boardId` | 24 giá trị đoán đều hỏng | **G1,G2,G3,G4,G7,G8 → 200** |
| D11 `marketId` | 24 giá trị đoán đều hỏng | **STO,HCX,UPX,STX,DVX → 200** |

## 5. CHƯA CHẠY — không được ghi là PASS

| # | Việc | Lý do |
|---|---|---|
| 1 | **CI GitHub Actions** | job bị từ chối khởi động do billing; badge không phải bằng chứng |
| 2 | **`Trade.login()` JWT** | `.env` thiếu `DNSE_USERNAME`/`DNSE_PASSWORD` |
| 3 | **Lệnh thật (post/cancel/close)** | chưa được phép; mọi write chỉ test dry-run envelope + write gate |
| 4 | **`403` ở `position_id=999999`** | đo 3 lần đều 403 — **không** kết luận là lỗi client |
| 5 | **Sandbox** | không probe lại; chưa biết nhận `pageIndex`/`pageSize` không |
| 6 | **WS tick stream** | không probe trong đợt này |
| 7 | **`orderCategory` bắt buộc?** | đo thấy `400 INVALID_ORDER_CATEGORY` khi thiếu, nhưng **quyết định** còn treo |
| 8 | **`boardId`/`marketId` ngoài tập đo** | đo trên **một** mã, **một** ngày ⇒ cố tình không validate cứng |

## 6. Bằng chứng **không** có HTTP transcript gốc

Các chuỗi lỗi trích trong báo cáo (`400 pageIndex is required`, `404 not found
boardId`, …) lấy từ `str(exc)` của probe ở thời điểm chạy. **Không** có log hay
transcript thô lưu trong repo. Đây là hạn chế thật của bằng chứng này, ghi lại để
người sau không tưởng nó mạnh hơn nó là (L-E02).

## 7. Ghi chú về cổng

`scripts/check_all.ps1 -SelfTest` chứng minh script **FAIL** khi gate đỏ. Cổng
`encoding` mới cũng có `--self-test` riêng (3/3) vì lý do nêu ở `check_all.ps1:26`:
một gate "không chạy được" phải báo lỗi, không được im lặng xanh.