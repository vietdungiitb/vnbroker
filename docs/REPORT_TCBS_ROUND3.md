# BÁO CÁO — TCBS Round 3: chặn lệch payload + dọn nợ kỹ thuật

**Ngày:** 2026-10-10 · **Trạng thái:** merge `dev`, **đã push `origin/dev`** · `5f7b83f..c917399`
**Nguồn:** `docs/HANDOFF_TCBS_20261010.md` §1.4 · Lessons áp dụng: L-E01, L-E06, L-P03, L-R06

> **Câu đầu tiên phải đọc:** đợt này **không sửa lỗi** — nó **dựng cổng chặn** rồi
> báo cáo Owner. Lý do ở §0: sửa body 8 write method mà không có JWT thì có thể **phá**
> thay vì chữa.

---

## 0. Phát hiện mở đầu — nghiêm trọng hơn mọi thứ đã tìm trong 2 đợt trước

Đo bằng script trên `docs/references/openapi-v1.0.0.json` (sha `7f97d27b…42bd4a`):

- `requestId` trong **toàn spec** = **0 lần**
- `refId` trong toàn spec = **9 lần**
- Cổng quét **12** write method ⇒ **38 lệch**

| Method | Path | Vấn đề đo được |
|:--|:--|:--|
| `_gated_change_derivative_order` | `POST /khronos/v1/order/change` | ❌ thiếu **6 field `required`** (`accountId` `subAccountId` `orderNo` `refId` `nvol` `nprice`) · sai tên `orderId`≠`orderNo` |
| `_gated_place_derivative_order` | `POST /khronos/v1/order/place` | ❌ thiếu `volume` + `refId` (**bắt buộc**) · gửi `quantity` nhưng spec tên `volume` |
| `_gated_change_derivative_condition_order` | `POST /khronos/v2/order/condition/change` | ❌ thiếu `accountId` `pkOrderNo` `refId` `soPrice` |
| `_gated_cancel_derivative_order` | `POST /khronos/v1/order/cancel` | ❌ thiếu `accountId` `orderNo` |
| `_gated_place_derivative_condition_order` | `POST /khronos/v1/order/condition/place` | ❌ thiếu `volume` `soPrice` `callbackPoint` `activationPrice` |
| 3 method `equity.py` | `/akhlys/...` | ⚠ gửi thừa `requestId`; `_gated_place_order` gửi thêm `pinCode` |

**Nghĩa lý:** `/khronos/v1/order/change` thiếu 6 field bắt buộc ⇒ **lệnh sửa lệnh phái
sinh nhiều khả năng bị TCBS từ chối hoàn toàn**. Không có lệnh nào trong số này từng
được gọi với token thật.

**Vì sao KHÔNG sửa trong đợt này** (theo L-P06 + L-E06):
1. Chưa có JWT ⇒ **không probe server** để biết TCBS có bỏ qua field lạ hay không.
2. Sửa đổi **public API** (`request_id` → `refId`) và hợp đồng người dùng.
3. Nếu tài liệu TCBS **thiếu** mà server thật chấp nhận `requestId`, thì sửa là **phá**.

⇒ **Cần Owner chốt.** Xem §5.

## 1. Cơ chế 4 tầng

| Tầng | File | Vai trò |
|:--|:--|:--|
| Cổng | `scripts/check_tcbs_bodies.py` | AST đọc payload thật → so `properties`/`required` của spec. 3 loại lệch: `EXTRA` · `MISSING` · `SUSPECT` |
| Baseline | `docs/tcbs_body_baseline.json` | 38 dòng nợ đã biết, **sinh bằng `--write-baseline`** |
| Test | `tests/unit/broker/tcbs/test_tcbs_body_contract.py` | 17 test khoá hành vi cổng + 8/12 lỗi tái diễn |
| Chạy tự động | `scripts/check_all.ps1` | Gate `tcbs-bodies` + `--self-test` **có ép exit code** |

## 2. Gate — đo thật

Baseline round 2 (`ddc1a8a`): 1881 passed / 26 skipped · contract 72 · ruff 0 · mypy 1266→1161 · ruff tests 13 KNOWN-RED · coverage 47/48

| Gate | Sau round 3 | Exit |
|---|---|---|
| pytest toàn bộ | **1918 passed, 26 skipped** (**+37**) | 0 |
| contract | **72 passed** | 0 |
| `ruff check vnbroker scripts tests/unit` | `All checks passed!` | 0 |
| mypy strict | baseline 1266 → **1148** (**fix thêm 13**) | 0 |
| `ruff check tests` | **13 KNOWN-RED, không tăng** | 1 *(có sẵn)* |
| `verify_tcbs_coverage.py` | **48 path · 47 nối · 1 chưa** | 0 |
| `check_tcbs_bodies.py` | **12 payload · 38 lệch đã biết · 0 lệch mới** | 0 |
| `check_lessons.py` | **24 lesson / 5 file** | 0 |
| self-test `check_lessons` | **9/9 PASS** | 0 |
| self-test `check_tcbs_bodies` | **10/10 PASS** | 0 |

## 3. Việc đã làm

### 3.1 Cổng chặn payload (S1) — `4654ff7`
Mới. Chi tiết §1.

### 3.2 Tách `derivatives.py` 852L → **462L** (S2/N4/N8) — `61ab18b`
- 10 method write chuyển sang `derivative_orders.py::DerivativeWriteMixin`.
- **API không đổi**: kiểm bằng `inspect.signature` trên cả hai bản ⇒ **0 chữ ký
  public khác biệt**; mất duy nhất `_write_request` (private, đã gỡ) và
  `_post(url)`→`_post(path)` (private).
- **N8**: bỏ 74 dòng `_post`/`_write_request`; mọi write đi qua
  `_write_http.post_json` — status map **đồng nhất** toàn lane.
- **Không còn file TCBS nào vượt 800L.** Còn sát ngưỡng: `equity.py` 798 · `quote.py` 793 · `websocket.py` 791 · `money.py` 773 · `client.py` 772.

### 3.3 Hai lỗi nhỏ (S3) — `93a89e8`
- **F-4**: `auth.py::_store_token` ghi `token_expires_at` **ngoài lock** ⇒ nằm trong `with self._session._lock:`.
- **F-9**: envelope dry-run lộ **tên** field nhạy cảm (`pin`/`otp`/`api_key`) ⇒ `_is_sensitive_kwarg()` lọc ra.

### 3.4 Sửa 1 blocker + 6 major của audit — `ee0fbc5`
| Mức | Vấn đề | Sửa |
|:--|:--|:--|
| **blocker** | Test tự tham chiếu (`git grep` khớp chính file test) ⇒ đỏ vĩnh viễn | Loại chính file khỏi kết quả grep |
| major | Cổng bỏ sót **4/12** write method (payload có annotation ⇒ `AnnAssign`; bỏ `node.keywords`) | Phủ **8 → 12** |
| major | Cổng đếm `_post`/`_put` (tầng HTTP) làm write method | Loại khỏi danh sách |
| major | Baseline gợi ý `pinCode -> price` ⇒ người sửa theo sẽ **gửi PIN vào ô giá** | `_looks_semantically_different()` — chỉ báo `EXTRA` |
| major | `check_all.ps1` **không ép** self-test (in mà không đọc `$LASTEXITCODE`) | Đếm fail + `exit 1`; **chứng minh bằng cách phá self-test** |
| major | `assert ... or True` — assert chết | Thay bằng kiểm thật |
| major | 3 dòng doc/số liệu sai trong test | Sửa (kể cả `8` → `12`) |

### 3.5 Bổ sung 5 bài học — `c917399`
`docs/LESSONS/gate-integrity.md` (L-G01..04) + L-R07. **Tổng 19 → 24 lesson / 3 → 5 file.**

## 4. Bằng chứng fail-trước / pass-sau (đo bằng hành vi)

| Hạng mục | Trước | Sau |
|:--|:--|:--|
| Cổng bắt field sai mới trong method **đã có cờ** | `lech moi: 0`, **exit 0** (lọt im lặng) | `lech moi: 3`, **exit 1** |
| Cổng bắt payload truyền bằng **kwarg** | bỏ sót (0 lệch, exit 0) | đã bắt |
| Cổng quét đủ write method | **8** | **12** |
| Lock ở `_store_token` | test **ĐỎ**: `_store_token ghi token_expires_at NGOAI khoi with...` | 21 PASS |
| `check_all` ép self-test | self-test hỏng ⇒ **exit 0** | `FAIL: 1 self-test gate that FAIL`, **exit 1** |

> **Điều tôi phải nói thẳng:** với AC-S3#1 (lock) tôi đã viết **3 test hành vi**, cả 3
> **xanh ở cả hai trạng thái** ⇒ bằng chứng bằng 0 ⇒ **đã gỡ, không giữ làm vỏ**. Lý do
> ghi trong docstring test. Test giữ lại là test **cấu trúc** (AST) — **ĐỎ** khi bỏ
> `with`, đã kiểm chứng bằng cách thay file.

## 5. ⚠ CHƯA CHẠY — không được ghi là PASS

| Việc | Vì sao |
|---|---|
| **Probe server TCBS thật** | **Chưa có JWT** — cần Smart OTP từ app TCInvest. `pwsh -File "$env:TEMP\getjwt.ps1"` |
| **Sửa 38 lệch payload** | Cần Owner chốt (đổi public API) **+** JWT để probe |
| **Đo tập `rc` thật** | Cần JWT |
| **Đo TTL thật của JWT** | Cần token thật |
| **Probe 18 path đợt 1 đã gỡ** | 401 chạy trước routing |
| CI GitHub Actions | Job bị từ chối do billing |

## 6. Rủi ro còn lại

| # | Rủi ro | Mức | Xử lý |
|:--|:--|:--|:--|
| **R1** | **38 lệch payload vẫn tồn tại** — write path phái sinh có thể bị TCBS từ chối | **cao** | Cổng chặn tái diễn + baseline liệt kê đủ. **Cần Owner chốt cách sửa** |
| **R2** | HTTP 200 ≠ thành công (`rc`) — chưa đo được tập mã | cao | `describe_business_code()` + cảnh báo docstring |
| **R3** | Cổng có thể còn lỗi phủ khác — **tự nó không chứng minh được** | trung bình | Đã qua audit độc lập 1 vòng; 5 lesson `gate-integrity.md` ghi lại |
| **R4** | `equity.py` 798L / `quote.py` 793L / `websocket.py` 791L — chỉ còn 2–9L | trung bình | Ngoài phạm vi; ghi N4 |
| **R5** | Nợ `_post` trùng lặp: còn 2 bản riêng (`equity.py`, `money.py`) | thấp | N8 — `derivative_orders` đã chuyển sang helper chung |

## 7. Quyết định cần Owner — theo thứ tự ưu tiên

1. **38 lệch payload** — sửa thẳng theo spec (đổi `request_id`→`refId`, thêm
   `volume`/`nvol`/`nprice`/`soPrice`/`orderNo`…), hay giữ tương thích và map?
   **Cần JWT để xác nhận trước khi sửa.**
2. `/api/v1/derivatives/contracts` — REST hay WebSocket? (spec tự mâu thuẫn)
3. `requestId` hư cấu trong `equity.py:394,454,525` — gỡ luôn hay để lát sau?

## 8. Rollback

```bash
git revert ee0fbc5   # chỉ sửa audit
git revert 93a89e8   # chỉ 2 fix nhỏ
git revert 61ab18b   # chỉ tách derivatives
git revert 4654ff7   # chỉ cổng chặn payload
```