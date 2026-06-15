# TCBS Slice Definition of Done

> Mục tiêu: quy định chính xác “xong” nghĩa là gì cho từng slice S0–S11.
>
> Trạng thái: Tài liệu thực thi.
>
> Ngày: 2026-05-19

---

## Cách dùng tài liệu này

Sau khi hoàn tất code hoặc edit một slice, người thực hiện phải:

1. Chạy các lệnh validation của slice tương ứng.
2. Ghi output tóm tắt vào audit evidence.
3. Điền PASS/FAIL/SKIP.
4. Append vào `docs/CENTRAL_MODIFIED_FILES_AUDIT.md`.
5. Cập nhật `docs/TCBS_SPRINT_TASK_BOARD.md`.

Không được chuyển sang slice kế tiếp khi slice hiện tại chưa có evidence đầy đủ.

---

## S0 — Docs và source of truth

### Validation commands

```powershell
git diff --check
python -c "import pathlib; files=['docs/TCBS_INDEX.md','docs/TCBS_EXECUTIVE_DECISION_BRIEF.md','docs/TCBS_BROKER_PLATFORM_RFC.md','docs/TCBS_INTEGRATION_MASTER_PLAN.md','docs/TCBS_IMPLEMENTATION_EXECUTION_PLAYBOOK.md','docs/TCBS_SPRINT_TASK_BOARD.md','docs/TCBS_SLICE_DEFINITION_OF_DONE.md']; missing=[f for f in files if not pathlib.Path(f).exists()]; print('S0 PASS' if not missing else f'S0 FAIL {missing}')"
```

---

## S1 — Broker package skeleton

### Validation commands

```powershell
python -c "from vnbroker.broker.registry import BrokerRegistry; print('S1 V1 PASS')"
python -c "from vnbroker.api.broker import Broker; print('S1 V2 PASS')"
git diff --check
```

### Mẫu evidence

```text
Slice: S1
V1 output: ___________
V2 output: ___________
git diff --check: ___________
PASS/FAIL/SKIP: ___________
```

---

## S2 — Credential model và config partition

### Validation commands

```powershell
python -m pytest tests/unit/broker/tcbs/test_credentials.py -q
python -c "from vnbroker.broker.security.credentials import TCBSCredentialResolver; print('S2 V2 PASS')"
```

### DoD tối thiểu

- Có namespace env riêng cho broker TCBS.
- Thiếu credential raise lỗi rõ nghĩa.
- Không fallback silent sang provider env public.

---

## S3 — Secure HTTP, redaction và audit substrate

### Validation commands

```powershell
python -m pytest tests/unit/broker/tcbs/test_security.py -q
python -c "from vnbroker.broker.security.redaction import redact_mapping; sample={'apiKey':'abc','Authorization':'Bearer secret','otp':'123456'}; redacted=redact_mapping(sample); assert redacted['apiKey'] != 'abc'; assert redacted['Authorization'] != 'Bearer secret'; assert redacted['otp'] != '123456'; print('S3 V2 PASS')"
```

### DoD tối thiểu

- Secret fields bị mask.
- Broker client không log raw payload.
- Có `AuditSink` và `IdempotencyGuard`.

---

## S4 — Session và auth service

### Validation commands

```powershell
python -m pytest tests/unit/broker/tcbs/test_session_auth.py -q
python -c "from vnbroker.broker.session import BrokerSessionState; print('S4 V2 PASS', [s.name for s in BrokerSessionState])"
```

### DoD tối thiểu

- State machine session tồn tại.
- Có test cho token exchange và expiry.
- Write mode mặc định vẫn tắt.

---

## S5 — Account và money read-side

### Validation commands

```powershell
python -m pytest tests/unit/broker/tcbs/test_account_money.py -q
python -c "from vnbroker.broker.tcbs.account import TCBSAccountService; from vnbroker.broker.tcbs.money import TCBSMoneyService; print('S5 V2 PASS')"
```

### DoD tối thiểu

- Có account list, balances, cash, buying power.
- Không có side-effect write.
- Error model có context đủ để audit.

---

## S6 — Orders, positions và derivatives read-side

### Validation commands

```powershell
python -m pytest tests/unit/broker/tcbs/test_orders_positions.py -q
python -c "from vnbroker.broker.tcbs.equity import TCBSEquityService; from vnbroker.broker.tcbs.derivatives import TCBSDerivativesService; print('S6 V2 PASS')"
```

### DoD tối thiểu

- Query order/position state cho cơ sở và phái sinh.
- Có test cho empty/error/expired-session.
- Chưa phát sinh write request thật.

---

## S7 — Write-side dry-run và idempotency

### Validation commands

```powershell
python -m pytest tests/unit/broker/tcbs/test_order_write_flow.py -q
python -c "from vnbroker.broker.security.idempotency import IdempotencyGuard; print('S7 V2 PASS')"
```

### DoD tối thiểu

- Mọi write method có `dry_run`.
- Có `request_id` và `idempotency_key`.
- Không retry mù.

### Gate an toàn bắt buộc

Không chạy live write thật trong slice S7. Nếu cần smoke với môi trường thật, chỉ smoke `dry_run` hoặc endpoint validate không tạo lệnh.

---

## S8 — Portfolio engine và reconciliation

### Validation commands

```powershell
python -m pytest tests/unit/broker/tcbs/test_portfolio.py -q
python -c "from vnbroker.broker.tcbs.portfolio import PortfolioEngine; print('S8 V2 PASS')"
```

### DoD tối thiểu

- Có holdings ledger.
- Có realized/unrealized PnL.
- Có reconciliation result và mismatch classification.

---

## S9 — Public TCBS provider parity

### Validation commands

```powershell
python -m pytest tests/unit/explorer/test_provider_api_compatibility.py -q
python -c "from vnbroker.api.listing import Listing; lst = Listing(source='TCBS'); print('S9 V2 PASS', type(lst).__name__)"
python -m pytest tests/unit/api/test_tcbs_auth_token.py -q
```

### DoD tối thiểu

- `Listing(source='TCBS')` hoạt động.
- Không còn fallback KBS silent cho listing ở mục tiêu release.
- Quote/company/financial đạt compatibility gate trong phạm vi đã chốt.

---

## S10 — Public integration vào `Vnbroker`

### Validation commands

```powershell
python -c "from vnbroker import Vnbroker; broker = Vnbroker().broker(provider='TCBS'); print('S10 V1 PASS', broker.__class__.__name__)"
python -c "from vnbroker import Vnbroker; stock = Vnbroker().stock('VNM', source='TCBS'); print('S10 V2 PASS', hasattr(stock, 'quote'))"
```

### DoD tối thiểu

- Có broker entrypoint riêng.
- `stock()` không bị vỡ.
- Auth broker không còn khởi phát ở `stock()` trong final target.

---

## S11 — Test, smoke, docs, audit và sign-off

### Validation commands

```powershell
python -m pytest tests/unit/broker/tcbs -q
python -m pytest tests/unit/explorer/test_provider_api_compatibility.py -q
git diff --check
```

### DoD tối thiểu

- Test gates toàn workstream pass.
- Docs/audit/module tree cập nhật.
- Có evidence đầy đủ cho sign-off.
