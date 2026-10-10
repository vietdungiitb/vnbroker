# PLAN — TCBS Round 3: chặn lệch payload + dọn nợ kỹ thuật

**Base:** `dev @ 5f7b83f` · **Ngày:** 2026-10-10 · **Mode B (self-supervised solo)**
**Nguồn:** `docs/HANDOFF_TCBS_20261010.md` §1.4 · Lessons áp dụng: L-E01, L-E06, L-P03, L-R06

> **Vì sao Mode B:** cả 3 lát đều chạm `vnbroker/broker/tcbs/` ⇒ **file chồng nhau**.
> Chạy song song sẽ tái tạo Hazard 1 (weld hunk). Theo `multi-agent-workflow` §Modes:
> "Prefer Mode B whenever slices overlap."

---

## 0. Phát hiện mở đầu — 8 write method gửi body KHÔNG khớp spec

Đo bằng script trên `docs/references/openapi-v1.0.0.json` (sha `7f97d27b…42bd4a`):

- `requestId` trong **toàn spec** = **0 lần**
- `refId` trong toàn spec = **9 lần**

| # | Path | Spec `required` | Code gửi | Lệch |
|:--|:--|:--|:--|:--|
| 1 | `POST /khronos/v1/order/place` | `…, volume, orderType, refId` | `quantity`, `requestId` | ❌ thiếu `refId` (**bắt buộc**) · ❌ `quantity` không tồn tại, spec tên `volume` |
| 2 | `POST /khronos/v1/order/change` | `accountId, subAccountId, orderNo, refId, nvol, nprice` | `orderId, quantity, price, requestId` | ❌ thiếu **4 field bắt buộc** · ❌ `orderId` ≠ spec `orderNo` |
| 3 | `POST /khronos/v2/order/condition/change` | `accountId, pkOrderNo, refId, soPrice` | `pkOrderNo, quantity, price, trigger_price, requestId`? | ❌ thiếu `refId`, `soPrice` (**bắt buộc**) |
| 4 | `POST /khronos/v1/order/condition/place` | không bắt buộc `refId` | `requestId` | ⚠ field lạ, spec có `refId` (optional) |
| 5 | `POST /khronos/v1/order/cancel` | `accountId, orderNo` | `orderId, requestId` | ⚠ field lạ |
| 6 | `POST /akhlys/v1/accounts/{n}/orders` | `execType, symbol, priceType, price, quantity` | + `requestId` | ⚠ field lạ |
| 7 | `PUT /akhlys/v1/accounts/{n}/orders/{orderId}` | `price, quantity` | + `requestId` | ⚠ field lạ |
| 8 | `PUT /akhlys/v1/accounts/{n}/cancel-orders` | `ordersList` | + `requestId` | ⚠ field lạ |

**Proof:** `derivatives.py:473,546,606,662,704` · `equity.py:394,454,525` @ `5f7b83f`.

> ⚠ **KHÔNG sửa body trong đợt này.** Lý do, theo L-P06 + L-E06:
> (a) chưa có JWT ⇒ **không probe server** được để xác nhận TCBS có bỏ qua field lạ hay không;
> (b) sửa đổi **public API** (`request_id` → `refId`) và **contract** người dùng;
> (c) nếu TCBS thực ra chấp nhận `requestId` (tài liệu có thể thiếu) thì sửa là **phá**.
> **Cần Owner chốt.** Đợt này làm việc chắc chắn đúng: **dựng cổng chặn lệch** để không
> tái diễn, và **ghi bảng lệch** có máy đọc được.

---

## 1. Slicing (tuần tự — file chồng nhau)

### S1 — Cổng chặn lệch payload (giá trị cao nhất)
| File | Việc |
|---|---|
| `scripts/check_tcbs_bodies.py` **(mới)** | AST đọc payload dict của mọi method ghi trong `broker/tcbs/*.py`, đối chiếu `properties`/`required` của spec → **FAIL khi lệch** |
| `tests/unit/broker/tcbs/test_tcbs_body_contract.py` **(mới)** | Test khoá hành vi của chính cổng |

**AC-S1**
| # | AC |
|:--|:--|
| 1 | Cổng đọc payload bằng **AST**, không regex; tự kiểm sha256 spec (như `verify_tcbs_coverage.py`) |
| 2 | Báo **3 loại lệch** tách biệt: field **thừa** (không có trong `properties`) · field `required` **thiếu** · tên field **sai** |
| 3 | Chạy `--report` ⇒ in **bảng lệch hiện tại** và **exit 0** (dùng để lập backlog) |
| 4 | Chạy mặc định ⇒ **exit 1** khi còn lệch (đây là cổng chặn) |
| 5 | `--baseline <file>`: chấp nhận lệch đã **biết** nếu nằm trong baseline ⇒ **không** đỏ vì nợ cũ |
| 6 | `--self-test`: ≥ 8 case âm thực, có **CONTROL** (mẫu sạch ⇒ exit 0) |
| 7 | **Fail-trước/pass-sau**: chứng minh gate đỏ trên payload sai, xanh trên payload đúng |

> **Quyết định thiết kế:** mặc định **baseline rỗng** ⇒ gate đỏ ngay, ghi nhận 8 lệch làm
> nợ đã biết. **KHÔNG** bật `--no-baseline` để gate xanh giả — đó là lặp lại đúng lỗi
> mà `verify_tcbs_coverage.py` từng có (F-10: exit 0 dù path hở).

### S2 — Tách `derivatives.py` (N4 + N8)
| File | Việc |
|---|---|
| `vnbroker/broker/tcbs/derivative_orders.py` **(mới)** | `DerivativeWriteMixin` chứa 10 method write (dòng 389–708) |
| `vnbroker/broker/tcbs/derivatives.py` | Kế thừa mixin · bỏ `_write_request` (69L) dùng `_write_http.post_json` |

**AC-S2**
| # | AC |
|:--|:--|
| 1 | `derivatives.py` **≤ 800L** (đang 852) — và **≤ 550L** để có headroom thật |
| 2 | `TCBSDerivativesService` giữ **nguyên** mọi public method — `inspect.signature` giống hệt trước/sau |
| 3 | `_write_request` **biến mất** khỏi `derivatives.py`; mọi write dùng `_write_http.post_json` ⇒ **status map đồng nhất** toàn lane |
| 4 | `dry_run` vẫn **keyword-only** ở cả 10 method (kiểm bằng `inspect.signature`) |
| 5 | Test cũ **không sửa 1 dòng** mà vẫn xanh (`test_equity_derivatives.py`, `test_tcbs_full_acb.py`) |
| 6 | **Fail-trước/pass-sau**: test mới chứng minh lỗi cũ (thiếu map 404) bị chặn |

### S3 — Hai lỗi nhỏ còn treo (F-4, F-9)
| File | Việc |
|---|---|
| `vnbroker/broker/tcbs/auth.py` | `_store_token` ghi `token_expires_at` **ngoài lock** (`:272-273`) ⇒ nằm trong `session._lock` |
| `vnbroker/broker/security/guards.py` | Envelope dry-run trả `kwargs_keys` ⇒ **tên** field nhạy cảm (`pin`/`otp`/`apiKey`) lọt log |

**AC-S3**
| # | AC |
|:--|:--|
| 1 | `token_expires_at` chỉ được ghi **dưới lock** — test chứng minh bằng thread, không bằng đọc code |
| 2 | Envelope dry-run **không** chứa tên field nhạy cảm; giữ nguyên phần còn lại |
| 3 | **KHÔNG** đổi chữ ký public của `guards.write_gate` |

---

## 2. Ngoài phạm vi (có lý do)

| # | Việc | Lý do |
|:--|:--|:--|
| N1 | Sửa body 8 write method theo spec | Cần Owner chốt + JWT để probe. Đã đưa vào cổng S1 để chặn tái diễn |
| N2 | `/api/v1/derivatives/contracts` | Spec tự mâu thuẫn — chờ Owner |
| N3 | Sửa `session.set_token(expires_in_seconds)` thành `Optional[int]` | `session.py` là hạ tầng dùng chung nhiều lane; đợt này chỉ vá điểm ghi race |
| N4 | `check_and_update_state()` đang **0 caller** | Bẫy đang ngủ; ghi ở báo cáo, chưa sửa |

## 3. Gate đầy đủ sau lát

```powershell
pwsh -NoProfile -File scripts/check_all.ps1
```

Baseline bắt buộc phải giữ: `pytest tests/ 1881 passed / 26 skipped` · contract 72 ·
`ruff check vnbroker` exit 0 · mypy `1266→1161` · `ruff check tests` **13 KNOWN-RED không tăng** ·
`verify_tcbs_coverage.py` `48/47/1`.

## 4. Rollback

```bash
git revert <merge-sha-s1>   # chỉ cổng chặn
git revert <merge-sha-s2>   # chỉ tách derivatives
git revert <merge-sha-s3>   # chỉ 2 lỗi nhỏ
```