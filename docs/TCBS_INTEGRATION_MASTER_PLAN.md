# TCBS Integration Master Plan

> Mục tiêu: kế hoạch thực hiện chi tiết để đội code hoặc AI agent khác có thể triển khai TCBS-primary mà không hỏi lại context.
>
> Trạng thái: Chờ phê duyệt trước khi code.
>
> Ngày: 2026-05-19

---

## 1. Scope và kết quả cần đạt

### Trong scope

- Xây broker lane mới cho TCBS với registry, session, security substrate và domain services.
- Thêm public entrypoint broker vào `Vnbroker`.
- Hoàn thiện read-side cho account, money, holdings, order query và derivative state.
- Mở write-side dưới `dry_run` trước, có idempotency và audit.
- Xây portfolio engine tối thiểu cho holdings, cost basis, PnL và reconciliation.
- Nâng TCBS public provider parity để không còn fallback KBS ở Listing và giảm các compatibility gaps.
- Bổ sung tests, audit, docs và module tree.

### Ngoài scope

- WebSocket streaming realtime.
- Multi-broker order router.
- Full production write rollout mặc định.
- Lưu token lâu dài xuống plaintext file.
- Refactor kiến trúc KBS/VCI ngoài các điểm tương thích bị ảnh hưởng trực tiếp.

---

## 2. Hiện trạng vs mục tiêu

| Thành phần | Trạng thái | Gap |
|---|---|---|
| Broker entrypoint | ❌ Missing | Chưa có `Vnbroker.broker(...)` |
| Broker registry | ❌ Missing | Chưa có abstraction riêng cho authenticated broker providers |
| TCBS auth placement | ⚠️ Partial | Logic auth nằm ở explorer/public lane |
| Broker security substrate | ❌ Missing | Chưa có redactor, audit sink, idempotency guard riêng |
| Broker HTTP client | ❌ Missing | Không thể dùng trực tiếp generic client có payload logging |
| Account/money/order services | ❌ Missing | Chưa có lane broker service theo domain |
| Portfolio engine | ❌ Missing | Chưa có ledger và reconciliation |
| TCBS public listing | ❌ Missing | `explorer/tcbs/listing.py` trống, adapter listing chưa nhận TCBS |
| Quote/company/financial compatibility | ⚠️ Partial | Thiếu `price_depth`, alias và harmonized signatures |
| Test coverage cho broker lane | ❌ Missing | Chưa có test package riêng cho broker/tcbs |

---

## 3. Ghi chú kiến trúc

- Broker lane và provider lane phải tách bằng package path, registry và public API.
- Security substrate phải triển khai trước broker domain services.
- Public TCBS parity là track riêng; có thể chạy song song sau khi broker security substrate đã chốt.
- Với mọi lệnh test trong tài liệu này, ưu tiên `python -m pytest` vì môi trường hiện tại không đảm bảo `pytest` có sẵn trên PATH shell.
- Mọi slice chạm source hoặc docs tree đều phải cập nhật `module_tree_full.md` và `docs/CENTRAL_MODIFIED_FILES_AUDIT.md`.

---

## 4. Task breakdown

| Task ID | Tên | Artifact chính | DoD |
|---|---|---|---|
| S0 | Khóa docs và source of truth | `docs/TCBS_*.md` | Bộ tài liệu được duyệt, thứ tự ưu tiên rõ ràng |
| S1 | Tạo broker package skeleton | `vnbroker/broker/**`, `vnbroker/api/broker.py` | Imports sạch, registry và base abstractions tồn tại |
| S2 | Credential model và config partition | `vnbroker/core/settings.py`, `vnbroker/broker/security/credentials.py` | TCBS broker dùng namespace config riêng, không lẫn provider env |
| S3 | Redaction, audit và secure HTTP substrate | `vnbroker/broker/security/*.py`, `vnbroker/broker/tcbs/client.py` | Không có secret/raw payload vào log broker path |
| S4 | Broker session và auth service | `vnbroker/broker/session.py`, `vnbroker/broker/tcbs/auth.py` | State machine auth chạy với mocked token flow |
| S5 | Account và money read-side | `vnbroker/broker/tcbs/account.py`, `money.py` | Lấy được account, balance, cash, buying power với tests |
| S6 | Orders, positions và derivatives read-side | `equity.py`, `derivatives.py` | Query state hoàn chỉnh, không có write side-effects |
| S7 | Write-side dry-run + idempotency | `equity.py`, `derivatives.py`, `idempotency.py`, `guards.py` | Place/update/cancel chỉ chạy dưới `dry_run` với guard và audit |
| S8 | Portfolio domain và reconciliation | `portfolio.py`, `tests/unit/broker/tcbs/test_portfolio.py` | Holdings, cost basis, PnL, returns và mismatch detection |
| S9 | TCBS public provider parity | `vnbroker/explorer/tcbs/*.py`, `vnbroker/api/listing.py`, `vnbroker/common/data.py` | Listing native tối thiểu, quote/company/finance pass compatibility tests |
| S10 | Public integration vào `Vnbroker` | `vnbroker/common/client.py`, `api/broker.py` | `Vnbroker.broker(provider='TCBS')` hoạt động, không làm vỡ `stock()` |
| S11 | Test, smoke, docs, audit và sign-off | `tests/**`, `docs/**`, `module_tree_full.md` | Test suite mục tiêu pass, audit evidence đầy đủ |

---

## 5. Dependency graph

```text
S0 -> S1 -> S2 -> S3 -> S4 -> S5 -> S6 -> S7 -> S8 -> S10 -> S11
                  \--------------------------------> S9 -----------/
```

Giải thích:

- S3 là ranh giới quan trọng nhất; chưa xong S3 thì không mở S4–S7.
- S9 có thể làm song song sau khi S2 chốt cấu hình và policy isolation.
- S10 chỉ nên làm sau khi read-side broker ổn định và public/provider parity đã rõ.

---

## 6. Chi tiết từng task

### S1 — Broker package skeleton

**Mục tiêu:** tạo bộ khung package cho broker lane, registry riêng và public API skeleton.

**Files bị ảnh hưởng:**

- `vnbroker/broker/__init__.py` (CREATE)
- `vnbroker/broker/base.py` (CREATE)
- `vnbroker/broker/registry.py` (CREATE)
- `vnbroker/api/broker.py` (CREATE)

**DoD:**

- [ ] Import không lỗi.
- [ ] Có `BrokerRegistry` và base abstractions tối thiểu.
- [ ] Chưa chạm behavior public `stock()`.

### S2 — Credential model và config partition

**Mục tiêu:** tách cấu hình broker TCBS khỏi provider env/config hiện hữu.

**Files bị ảnh hưởng:**

- `vnbroker/core/settings.py` (MODIFY)
- `vnbroker/broker/security/credentials.py` (CREATE)

**DoD:**

- [ ] Có namespace env riêng kiểu `VNBROKER_BROKER_TCBS_*`.
- [ ] Không đọc lẫn credential provider-public một cách silent.
- [ ] Missing credential raise lỗi rõ nghĩa.

### S3 — Redaction, audit và secure HTTP substrate

**Mục tiêu:** khóa secret leakage trước khi có bất kỳ broker method thực sự nào.

**Files bị ảnh hưởng:**

- `vnbroker/broker/security/redaction.py` (CREATE)
- `vnbroker/broker/security/audit.py` (CREATE)
- `vnbroker/broker/security/idempotency.py` (CREATE)
- `vnbroker/broker/security/guards.py` (CREATE)
- `vnbroker/broker/tcbs/client.py` (CREATE)

**DoD:**

- [ ] Secret fields bị mask trong logs và audit events.
- [ ] Broker client không log raw `payload`/`headers` thô.
- [ ] Write guard và idempotency primitives tồn tại.

### S4 — Broker session và auth service

**Mục tiêu:** gom auth/token lifecycle vào session layer có state machine.

**Files bị ảnh hưởng:**

- `vnbroker/broker/session.py` (CREATE)
- `vnbroker/broker/tcbs/auth.py` (CREATE)
- `vnbroker/explorer/tcbs/auth.py` (MODIFY hoặc deprecate bridge sau này)

**DoD:**

- [ ] Có state machine `created/authenticating/authenticated_read/authenticated_write_enabled/expired/locked`.
- [ ] Có mocked tests cho token exchange và expiry handling.
- [ ] Chưa mở write mode mặc định.

### S5 — Account và money read-side

**Mục tiêu:** lấy trạng thái tài khoản thật một cách an toàn, read-only.

**Files bị ảnh hưởng:**

- `vnbroker/broker/tcbs/account.py` (CREATE)
- `vnbroker/broker/tcbs/money.py` (CREATE)

**DoD:**

- [ ] Trả object/DataFrame chuẩn hóa cho account list, balances, cash, buying power.
- [ ] Có tests cho mapping và error model.
- [ ] Không có side-effect write.

### S6 — Orders, positions và derivatives read-side

**Mục tiêu:** đọc trạng thái lệnh, vị thế và phái sinh trước khi mở write path.

**Files bị ảnh hưởng:**

- `vnbroker/broker/tcbs/equity.py` (CREATE)
- `vnbroker/broker/tcbs/derivatives.py` (CREATE)

**DoD:**

- [ ] Query order history/detail/execution/position hoạt động qua mocks.
- [ ] Semantics cơ sở và phái sinh tách rõ.
- [ ] Có tests cho empty, partial, permission-denied, expired-session.

### S7 — Write-side dry-run + idempotency

**Mục tiêu:** mở place/update/cancel theo hướng an toàn nhất có thể.

**Files bị ảnh hưởng:**

- `vnbroker/broker/tcbs/equity.py` (MODIFY)
- `vnbroker/broker/tcbs/derivatives.py` (MODIFY)
- `vnbroker/broker/security/idempotency.py` (MODIFY)
- `vnbroker/broker/security/guards.py` (MODIFY)

**DoD:**

- [ ] Mọi write method có `dry_run` và `request_id`.
- [ ] Guard chặn write nếu chưa enable explicit.
- [ ] Retry policy không thể gửi trùng lệnh khi thiếu status check.

### S8 — Portfolio domain và reconciliation

**Mục tiêu:** biến broker state thành portfolio engine dùng được cho đầu tư thực tế.

**Files bị ảnh hưởng:**

- `vnbroker/broker/tcbs/portfolio.py` (CREATE)
- `tests/unit/broker/tcbs/test_portfolio.py` (CREATE)

**DoD:**

- [ ] Có holdings ledger, cash ledger, average cost.
- [ ] Có realized/unrealized PnL, allocation và return metrics cơ bản.
- [ ] Có reconciliation result và mismatch classification.

### S9 — TCBS public provider parity

**Mục tiêu:** hoàn thiện public/provider compatibility của TCBS mà không kéo broker lane trở lại explorer-first.

**Files bị ảnh hưởng:**

- `vnbroker/explorer/tcbs/listing.py` (CREATE or FILL)
- `vnbroker/api/listing.py` (MODIFY)
- `vnbroker/common/data.py` (MODIFY)
- `vnbroker/explorer/tcbs/quote.py` (MODIFY)
- `vnbroker/explorer/tcbs/company.py` (MODIFY)
- `vnbroker/explorer/tcbs/financial.py` (MODIFY)

**DoD:**

- [ ] `Listing(source='TCBS')` hoạt động.
- [ ] Không còn fallback KBS silent cho TCBS listing ở mục tiêu release.
- [ ] `price_depth`, `financial_ratios` và signatures cần thiết pass tests chung.

### S10 — Public integration vào `Vnbroker`

**Mục tiêu:** expose broker lane qua API công khai nhưng không vỡ luồng cũ.

**Files bị ảnh hưởng:**

- `vnbroker/common/client.py` (MODIFY)
- `vnbroker/api/broker.py` (MODIFY)
- `README.md` hoặc `docs/VNBROKER_USAGE_GUIDE.md` (MODIFY nếu cần)

**DoD:**

- [ ] Có `Vnbroker.broker(provider='TCBS', ...)`.
- [ ] `Vnbroker.stock(...)` vẫn giữ semantics provider-public.
- [ ] Auth broker không còn khởi phát từ `stock()` ở final target.

### S11 — Test, smoke, docs, audit và sign-off

**Mục tiêu:** khóa chất lượng và bằng chứng triển khai.

**Files bị ảnh hưởng:**

- `tests/unit/broker/tcbs/**` (CREATE)
- `tests/unit/explorer/test_provider_api_compatibility.py` (MODIFY)
- `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` (MODIFY)
- `module_tree_full.md` (MODIFY)

**DoD:**

- [ ] Test read-side pass.
- [ ] Test write-side dry-run pass.
- [ ] Contract compatibility tests của TCBS pass theo phạm vi release.
- [ ] Audit file và module tree cập nhật đầy đủ.

---

## 7. Validation gates toàn workstream

- [ ] `python -m pytest tests/unit/broker/tcbs -q` PASS
- [ ] `python -m pytest tests/unit/api/test_tcbs_auth_token.py -q` PASS hoặc được thay bằng suite broker auth mới
- [ ] `python -m pytest tests/unit/explorer/test_provider_api_compatibility.py -q` PASS
- [ ] `python -c "from vnbroker import Vnbroker; print(hasattr(Vnbroker, 'broker'))"` trả `True`
- [ ] `git diff --check` sạch
- [ ] `module_tree_full.md` regenerated
- [ ] `docs/CENTRAL_MODIFIED_FILES_AUDIT.md` đã append đủ bằng chứng

---

## 8. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Log rò rỉ token/OTP/order payload | High | Critical | Hoàn tất S3 trước mọi broker service khác |
| Thiết kế broker lane lẫn provider lane | Medium | High | Registry riêng, entrypoint riêng, tests riêng |
| Public TCBS parity kéo lệch focus khỏi broker core | High | Medium | Chạy S9 như track song song, không chặn S4–S8 |
| Contract drift giữa docs và live TCBS OpenAPI | Medium | High | Mocked contract tests + live smoke có kiểm soát |
| Gửi lệnh trùng | Medium | Critical | Dry-run mặc định, idempotency key, status check trước retry |
| Portfolio sai số | Medium | High | Ledger + reconciliation thay vì snapshot-only |

---

## 9. Governance artifacts bắt buộc

- `docs/CENTRAL_MODIFIED_FILES_AUDIT.md`: append sau mỗi slice.
- `module_tree_full.md`: cập nhật khi thay đổi source hoặc docs tree.
- `docs/TCBS_SPRINT_TASK_BOARD.md`: đổi trạng thái từng slice.
- `docs/TCBS_SLICE_DEFINITION_OF_DONE.md`: dùng để ghi evidence.
