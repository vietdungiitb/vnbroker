# TCBS Sprint Task Board

> Mục tiêu: bảng theo dõi công việc slice-by-slice cho workstream TCBS-primary broker.
>
> Trạng thái: Chờ duyệt trước khi bắt đầu code.
>
> Ngày: 2026-05-19

---

## 1. Tổng quan sprint

| Hạng mục | Giá trị |
|---|---|
| Sprint goal | TCBS trở thành broker platform chính với security-first dual-plane architecture |
| Độ dài ước tính | 5-8 ngày working, chia theo slice nhỏ có thể audit |
| Branch mục tiêu | `dev` |
| Definition of done toàn sprint | Tất cả slice = DONE, `git diff --check` sạch, test gates pass, audit đầy đủ |

---

## 2. Scope rõ ràng

### Trong scope — không được bỏ

| Scope | Hạng mục |
|---|---|
| A — Security substrate | Credentials, redaction, audit, idempotency, write guard |
| B — Broker core | Registry, base abstractions, session, auth, TCBS client |
| C — Broker services | Account, money, equity, derivatives, positions, order query |
| D — Portfolio | Holdings ledger, cost basis, PnL, returns, reconciliation |
| E — Public parity | Native TCBS listing và compatibility fixes cho quote/company/financial |
| F — Quality | Unit tests, smoke, docs, audit, module tree |

### Ngoài scope — không được thêm

- WebSocket realtime.
- Broker AUTO routing.
- Plaintext token persistence mặc định.
- Production live write mặc định.
- Refactor rộng toàn bộ KBS/VCI ngoài phạm vi compatibility bị tác động trực tiếp.

---

## 3. Task board — Slice S0–S11

### Cột mô tả

- **Slice**: ký hiệu ngắn
- **File tác động**: file hoặc nhóm file chính
- **Mục tiêu slice**: output đo được
- **Phụ thuộc**: slice phải xong trước
- **Ước tính**: thời gian kỳ vọng
- **Trạng thái**: `🔲 TODO` / `🔄 IN PROGRESS` / `✅ DONE` / `⏭ SKIP`
- **Bằng chứng**: lệnh validation trọng tâm

---

### S0 — Khóa bộ docs và source of truth

| Trường | Giá trị |
|---|---|
| **File tác động** | `docs/TCBS_*.md`, `module_tree_full.md`, `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` |
| **Mục tiêu slice** | Bộ tài liệu TCBS-primary tồn tại đầy đủ và thống nhất thứ tự ưu tiên |
| **Phụ thuộc** | Không có |
| **Ước tính** | 0.5 ngày |
| **Trạng thái** | ✅ DONE |
| **Bằng chứng** | `git diff --check` → 0 whitespace error. 13 TCBS docs created. |

**Checklist S0:**

- [x] Có index, brief, RFC, master plan, playbook, task board, DoD.
- [x] Ghi rõ xử lý xung đột với tài liệu TCBS compatibility cũ.
- [x] Audit file và module tree đã cập nhật.

---

### S1 — Tạo broker package skeleton

| Trường | Giá trị |
|---|---|
| **File tác động** | `vnbroker/broker/__init__.py`, `base.py`, `registry.py`, `api/broker.py` |
| **Mục tiêu slice** | Import được `vnbroker.api.broker` và `BrokerRegistry` |
| **Phụ thuộc** | S0 |
| **Ước tính** | 0.5 ngày |
| **Trạng thái** | ✅ DONE |
| **Bằng chứng** | `python -c "from vnbroker.broker.registry import BrokerRegistry; print('S1 PASS')"` → S1 PASS. 13/13 unit tests PASS. |

**Checklist S1:**

- [x] Có package `vnbroker/broker/`.
- [x] Có `BrokerRegistry` tách khỏi provider registry.
- [x] Chưa thay đổi behavior hiện tại của `Vnbroker.stock(...)`.

---

### S2 — Credential model và config partition

| Trường | Giá trị |
|---|---|
| **File tác động** | `vnbroker/core/settings.py`, `vnbroker/broker/security/credentials.py` |
| **Mục tiêu slice** | TCBS broker đọc credential từ namespace riêng, không lẫn provider env |
| **Phụ thuộc** | S1 |
| **Ước tính** | 0.5 ngày |
| **Trạng thái** | ✅ DONE |
| **Bằng chứng** | `python -m pytest tests/unit/broker/tcbs/test_credentials.py -q` → 29/29 PASS. Validation gate: S2 PASS. |

**Checklist S2:**

- [x] Có model config riêng cho broker TCBS (`TCBSCredentialConfig`).
- [x] Thiếu credential raise lỗi rõ nghĩa (`ValueError` + tên env var).
- [x] Không fallback silent sang env public/provider cũ.
- [x] `repr()` TCBSCredentialConfig che api_key, auth_token.
- [x] Redactor: redact_dict() (nested + list), redact_headers(), mask_account_no() — 21 SENSITIVE_KEYS.

---

### S3 — Secure HTTP, redaction và audit substrate

| Trường | Giá trị |
|---|---|
| **File tác động** | `vnbroker/broker/security/*.py`, `vnbroker/broker/tcbs/client.py` |
| **Mục tiêu slice** | Secret không lọt vào log/audit ở broker lane |
| **Phụ thuộc** | S2 |
| **Ước tính** | 1 ngày |
| **Trạng thái** | ✅ DONE |
| **Bằng chứng** | `python -m pytest tests/unit/broker/test_s3_security.py -q` → 32/32 PASS. S3 PASS gate OK. |

**Checklist S3:**

- [x] `apiKey`, `otp`, `authorization`, `token`, `payload` được mask (SENSITIVE_KEYS 21 keys + Redactor).
- [x] Có `AuditSink`, `AuditRecord` (structured JSON, propagate=False, UTC timestamp).
- [x] Broker client không gọi đường logging generic chưa redacted (`audit.py` dùng logger riêng).
- [x] `IdempotencyStore` TTL in-memory, check_and_store, mark_completed, purge_expired.
- [x] `@write_gate`: dry_run=True default, BrokerPermissionError khi write chưa enabled.
- [x] `vnbroker/broker/exceptions.py`: BrokerError hierarchy đầy đủ (7 exception class).

---

### S4 — Session và auth service

| Trường | Giá trị |
|---|---|
| **File tác động** | `vnbroker/broker/session.py`, `vnbroker/broker/tcbs/auth.py` |
| **Mục tiêu slice** | Token lifecycle và state machine hoạt động qua mocked flow |
| **Phụ thuộc** | S3 |
| **Ước tính** | 0.5 ngày |
| **Trạng thái** | ✅ DONE |
| **Bằng chứng** | `python -m pytest tests/unit/broker/tcbs/test_session_auth.py -q` → 37/37 PASS. |

**Checklist S4:**

- [x] Có state machine session rõ ràng (6 states: CREATED/AUTHENTICATING/READ/WRITE/EXPIRED/LOCKED).
- [x] Có xử lý expiry (auto-expire khi past expires_at) và lock state (vĩnh viễn, không unlock).
- [x] Write mode vẫn tắt mặc định (is_write_enabled=False sau init và sau set_token).
- [x] TCBSAuthService: OTP validation, HTTP mocked, 401→BrokerAuthError, timeout→BrokerNetworkError.
- [x] tcbs/exceptions.py re-export đúng class identity (không tạo class mới).
- [x] Token KHÔNG xuất hiện trong repr, log, hay error message.

---

### S5 — Account và money read-side

| Trường | Giá trị |
|---|---|
| **File tác động** | `vnbroker/broker/tcbs/account.py`, `money.py` |
| **Mục tiêu slice** | Query account, balances, cash, buying power ổn định |
| **Phụ thuộc** | S4 |
| **Ước tính** | 1 ngày |
| **Trạng thái** | ✅ DONE |
| **Bằng chứng** | `python -m pytest tests/unit/broker/tcbs/test_account_money.py -q` → 39/39 PASS. Full regression 150/150 PASS. |

**Checklist S5:**

- [x] Chuẩn hóa output read-side (DataFrame + raw=True, snake_case columns, float64 dtypes, category dtype cho enum fields).
- [x] Error model đúng class (BrokerAuthError/BrokerPermissionError/BrokerNetworkError/BrokerValidationError với code string).
- [x] Không tạo side-effect write (no @write_gate, no POST/PUT/DELETE — test_no_write_gate_on_read_services PASS).
- [x] PII fields (idNo, phone, email, custodyCode) redacted trong raw=False output.
- [x] 401 → revoke session → BrokerAuthError; session.state == EXPIRED sau 401.
- [x] Không dùng core/utils/client; requests trực tiếp. Không log token/api_key.

---

### S6 — Orders, positions và derivatives read-side

| Trường | Giá trị |
|---|---|
| **File tác động** | `vnbroker/broker/tcbs/equity.py`, `derivatives.py` |
| **Mục tiêu slice** | Query order/position state đầy đủ cho cơ sở và phái sinh |
| **Phụ thuộc** | S5 |
| **Ước tính** | 1 ngày |
| **Trạng thái** | ✅ DONE |
| **Bằng chứng** | `python -m pytest tests/unit/broker/tcbs/test_equity_derivatives.py -q` → 40/40 PASS. Full regression 190/190 PASS. |

**Checklist S6:**

- [x] Cơ sở (equity) và phái sinh (derivatives) tách service riêng, semantics rõ ràng.
- [x] Tests đầy đủ cho empty/error/expired-session/401-revoke/429-rate-limit/timeout.
- [x] Chưa mở write-side (get_orders read-only; S8 mới có place/modify/cancel).
- [x] DataFrame output chuẩn: snake_case, float64/Int64/category dtypes, empty list → empty df với đúng columns.
- [x] 429 → BrokerRateLimitError, 401 → revoke + BrokerAuthError.

---

### S7 — Write-side dry-run và idempotency

| Trường | Giá trị |
|---|---|
| **File tác động** | `equity.py`, `derivatives.py`, `idempotency.py`, `guards.py` |
| **Mục tiêu slice** | Place/update/cancel chạy được ở `dry_run` với guard và audit |
| **Phụ thuộc** | S6 |
| **Ước tính** | 1 ngày |
| **Trạng thái** | 🔲 TODO |
| **Bằng chứng** | `python -m pytest tests/unit/broker/tcbs/test_order_write_flow.py -q` |

**Checklist S7:**

- [ ] Tất cả write method có `dry_run=True` mặc định trong phase đầu.
- [ ] Có `request_id` và `idempotency_key`.
- [ ] Không retry mù.

---

### S8 — Portfolio engine và reconciliation

| Trường | Giá trị |
|---|---|
| **File tác động** | `vnbroker/broker/tcbs/portfolio.py`, `tests/unit/broker/tcbs/test_portfolio.py` |
| **Mục tiêu slice** | Tính được holdings, average cost, PnL, returns và mismatch reconciliation |
| **Phụ thuộc** | S5, S6 |
| **Ước tính** | 1 ngày |
| **Trạng thái** | 🔲 TODO |
| **Bằng chứng** | `python -m pytest tests/unit/broker/tcbs/test_portfolio.py -q` |

**Checklist S8:**

- [ ] Có holdings ledger và cash ledger.
- [ ] Có realized/unrealized PnL.
- [ ] Có mismatch classification cho reconciliation.

---

### S9 — Public TCBS provider parity

| Trường | Giá trị |
|---|---|
| **File tác động** | `vnbroker/explorer/tcbs/*.py`, `vnbroker/api/listing.py`, `vnbroker/common/data.py` |
| **Mục tiêu slice** | `Listing(source='TCBS')` hoạt động và TCBS pass compatibility tests theo phạm vi |
| **Phụ thuộc** | S2 |
| **Ước tính** | 1 ngày |
| **Trạng thái** | 🔲 TODO |
| **Bằng chứng** | `python -m pytest tests/unit/explorer/test_provider_api_compatibility.py -q` |

**Checklist S9:**

- [ ] Có native listing tối thiểu cho TCBS.
- [ ] Bỏ fallback KBS silent ở mục tiêu release.
- [ ] Bổ sung `price_depth`, `financial_ratios`, harmonized signatures nếu còn thiếu.

---

### S10 — Public integration vào `Vnbroker`

| Trường | Giá trị |
|---|---|
| **File tác động** | `vnbroker/common/client.py`, `vnbroker/api/broker.py`, docs usage |
| **Mục tiêu slice** | `Vnbroker.broker(provider='TCBS')` hoạt động mà không vỡ `stock()` |
| **Phụ thuộc** | S4, S5, S6, S9 |
| **Ước tính** | 0.5 ngày |
| **Trạng thái** | 🔲 TODO |
| **Bằng chứng** | `python -c "from vnbroker import Vnbroker; print(hasattr(Vnbroker(), 'broker'))"` |

**Checklist S10:**

- [ ] Có broker entrypoint riêng.
- [ ] Public provider path vẫn giữ behavior cũ.
- [ ] Auth broker không còn khởi tạo trong `stock()` ở final target.

---

### S11 — Test, smoke, docs, audit và sign-off

| Trường | Giá trị |
|---|---|
| **File tác động** | `tests/**`, `docs/**`, `module_tree_full.md`, `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` |
| **Mục tiêu slice** | Có đủ test evidence, docs, audit để sign-off |
| **Phụ thuộc** | S7, S8, S9, S10 |
| **Ước tính** | 0.5-1 ngày |
| **Trạng thái** | 🔲 TODO |
| **Bằng chứng** | `git diff --check` + test gates toàn sprint |

**Checklist S11:**

- [ ] Test suite mục tiêu pass.
- [ ] Docs usage/update hoàn chỉnh.
- [ ] Audit file và module tree đã append/update.
