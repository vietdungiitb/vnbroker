# TCBS Broker Platform RFC

> Mục tiêu: mô tả kiến trúc kỹ thuật chi tiết cho việc đưa TCBS trở thành broker platform chính trong vnbroker.
>
> Trạng thái: Draft for approval.
>
> Ngày: 2026-05-19

---

## 1. Bối cảnh

TCBS trong repo hiện nay mới dừng ở trạng thái provider/public layer một phần. Repo đã có các explorer TCBS cho quote, company, financial, trading; đồng thời đã có auth helper cho OpenAPI. Tuy nhiên, các thành phần này chưa tạo thành một broker platform hoàn chỉnh, an toàn và tách biệt.

Các bằng chứng cục bộ quan trọng:

| File hiện tại | Quan sát | Kết luận |
|---|---|---|
| `vnbroker/common/client.py` | `stock()` có thể exchange TCBS token khi nhận OTP | Broker auth đang đi qua public stock entrypoint |
| `vnbroker/common/data.py` | `StockComponents(source='TCBS')` fallback Listing sang KBS | TCBS provider parity chưa hoàn chỉnh |
| `vnbroker/api/listing.py` | `source='TCBS'` chưa được chấp nhận | Adapter public chưa xem TCBS là listing source hợp lệ |
| `vnbroker/explorer/tcbs/listing.py` | File trống | Native TCBS listing đang thiếu |
| `vnbroker/explorer/tcbs/auth.py` | Chứa token/env resolver và token exchange | Auth broker đang nằm sai lớp |
| `vnbroker/core/utils/client.py` | `show_log=True` sẽ log `Params` và `Payload` nguyên văn | Không an toàn cho broker secrets và order payload |
| `vnbroker/core/utils/user_agent.py` | Generic header builder có random user-agent và generic Authorization | Phù hợp provider layer, không phù hợp broker lane có audit/compliance |
| `vnbroker/connector/dnse/client.py` | Đã tách connector rõ theo service | Đây là mẫu gần nhất để thiết kế broker lane cho TCBS |

---

## 2. Mục tiêu

### 2.1 Trong scope

- Biến TCBS thành broker platform chính cho xác thực, tài khoản, tiền, đặt/sửa/hủy lệnh cơ sở và phái sinh.
- Tạo broker lane riêng, không dùng AUTO và không failover sang provider khác.
- Thêm portfolio domain cho holdings, cost basis, realized/unrealized PnL, returns và reconciliation.
- Duy trì TCBS public provider như một track riêng để cải thiện tính tương thích với hệ provider hiện có.
- Chuẩn hóa security controls: credential isolation, redaction, audit trail, idempotency và write safety.

### 2.2 Ngoài scope

- Broker AUTO-routing giữa nhiều công ty chứng khoán.
- WebSocket streaming và real-time push cho phase đầu.
- Tự động lưu token plaintext xuống đĩa.
- Mở production write mặc định trước khi có audit sign-off.
- Refactor toàn bộ KBS/VCI sang broker registry mới.

---

## 3. Kiến trúc đề xuất

```text
                            +-------------------------+
                            |    App Integration      |
                            | Django / Celery / APIs |
                            +------------+------------+
                                         |
                     +-------------------+-------------------+
                     |                                       |
          +----------v----------+                 +----------v----------+
          |    Provider Plane   |                 |    Broker Plane     |
          | Quote/Listing/...   |                 | TCBS Session/Auth   |
          | KBS/VCI/TCBS/AUTO   |                 | Account/Money/Order |
          +----------+----------+                 +----------+----------+
                     |                                       |
                     +-------------------+-------------------+
                                         |
                            +------------v------------+
                            |     Security Plane      |
                            | Credentials/Redaction   |
                            | Audit/Idempotency/Guard |
                            +------------+------------+
                                         |
                            +------------v------------+
                            |    Portfolio Domain     |
                            | Ledger/PnL/Returns      |
                            | Reconciliation          |
                            +-------------------------+
```

---

## 4. Thiết kế module khuyến nghị

### 4.1 Package mới

```text
vnbroker/
  broker/
    __init__.py
    registry.py
    base.py
    session.py
    security/
      credentials.py
      redaction.py
      audit.py
      idempotency.py
      guards.py
    tcbs/
      __init__.py
      client.py
      auth.py
      account.py
      money.py
      equity.py
      derivatives.py
      portfolio.py
      exceptions.py
```

### 4.2 Public integration surface

```text
vnbroker/
  api/
    broker.py
  common/
    client.py   # thêm Vnbroker.broker(...)
```

### 4.3 Track riêng cho provider parity

```text
vnbroker/
  api/listing.py
  common/data.py
  explorer/tcbs/listing.py
  explorer/tcbs/quote.py
  explorer/tcbs/company.py
  explorer/tcbs/financial.py
```

---

## 5. Capability model

| Domain | Capability | Phase đầu | Ghi chú |
|---|---|---|---|
| Session | OTP exchange, token lifecycle, expiry check | Có | Không lưu file plaintext |
| Account | account list, profile, balances | Có | Read-side trước |
| Money | cash, buying power, margin data | Có | Read-side trước |
| Equity | order book query, order detail, execution detail | Có | Write tách phase |
| Equity write | place/update/cancel | Có nhưng `dry_run` trước | Phải có idempotency |
| Derivatives | positions, orders, write flow | Có nhưng tách sau equity read-side | Track riêng vì semantics khác |
| Portfolio | holdings ledger, average cost, PnL, returns | Có | Không chỉ dựa snapshot broker |
| Audit/Ops | request tracing, payload hash, result code | Có | Không log raw secret |

---

## 6. Security invariants

1. Broker session không được dùng `AUTO` hoặc failover sang provider khác.
2. Mỗi broker session chỉ gắn với một provider và một account context.
3. Token mặc định chỉ sống trong memory, không ghi file plaintext trừ khi có secure storage rõ ràng và bật explicit.
4. `show_log=True` của generic client không được dùng trong broker secret path.
5. Header builder của broker phải deterministic; không random user-agent như provider helper.
6. Tất cả trường `apiKey`, `authorization`, `otp`, `token`, `accountNo`, `custodyCode`, `payload` phải qua redactor trước khi vào log/audit.
7. Mọi write operation phải có `request_id` và `idempotency_key`.
8. Retry cho write chỉ được phép sau kiểm tra trạng thái và có bằng chứng idempotency.
9. `dry_run=True` là bắt buộc ở giai đoạn rollout đầu cho mọi phương thức write.
10. Provider plane không được giữ broker credential hay session object.

---

## 7. Session lifecycle

```text
created
  -> authenticating
  -> authenticated_read
  -> authenticated_write_enabled
  -> expired
  -> locked
```

### Quy tắc state machine

- `created -> authenticating`: bắt đầu OTP exchange hoặc token validation.
- `authenticating -> authenticated_read`: có token hợp lệ, chưa bật write.
- `authenticated_read -> authenticated_write_enabled`: chỉ sau khi caller explicit bật write mode.
- `authenticated_* -> expired`: khi token hết hạn hoặc broker trả lỗi auth không thể recover.
- Bất kỳ state nào -> `locked`: khi phát hiện policy violation, secret mismatch hoặc audit failure nghiêm trọng.

---

## 8. Error model

Không nên tái sử dụng nguyên xi lỗi provider/open-data cho broker lane. Cần nhóm lỗi riêng:

- `BrokerError`
- `BrokerAuthError`
- `BrokerPermissionError`
- `BrokerValidationError`
- `BrokerRateLimitError`
- `BrokerOrderError`
- `BrokerSessionExpiredError`
- `BrokerReconciliationError`

Mỗi lỗi phải chứa ít nhất:

- `provider`
- `operation`
- `request_id`
- `status_code`
- `error_code`
- `message`
- `safe_details`

---

## 9. Portfolio domain

Portfolio không nên là wrapper mỏng quanh snapshot broker. Domain này cần các thành phần sau:

1. Holdings ledger: trạng thái số lượng, average cost, phí, thuế, side effects của order fills.
2. Cash ledger: nạp/rút/chuyển tiền, khớp lệnh, phí, lãi vay, tiền chờ về.
3. Performance engine: realized PnL, unrealized PnL, TWR, XIRR, exposure, allocation.
4. Reconciliation service: đối chiếu ledger nội bộ với snapshot broker theo từng account/date.
5. Policy layer: quy tắc bỏ qua mismatch nhỏ, flag mismatch lớn, và escalation.

---

## 10. Hiện trạng vs mục tiêu

| Thành phần | Trạng thái hiện tại | Mục tiêu |
|---|---|---|
| TCBS auth | Có helper trong explorer | Tách sang broker auth service + session policy |
| TCBS listing public | Trống/fallback KBS | Native tối thiểu, adapter hợp lệ |
| TCBS quote public | Có một phần | Bổ sung `price_depth` và compatibility gaps |
| TCBS company/financial | Có nhưng chưa chuẩn contract | Đồng bộ signature và alias với tests chung |
| HTTP/logging | Generic, chưa redact | Broker HTTP client riêng + redactor |
| Config | Chưa có namespace broker TCBS | Credential namespace riêng, immutable session config |
| Portfolio | Chưa có engine đúng nghĩa | Ledger + returns + reconciliation |
| Public API | Chưa có `broker()` entrypoint | `Vnbroker.broker(provider='TCBS')` |

---

## 11. Rollout phases

| Phase | Mục tiêu | Kết quả |
|---|---|---|
| P0 | Lock kiến trúc, tài liệu, security rules | Bộ docs được duyệt |
| P1 | Security substrate | Credentials, redaction, audit, idempotency |
| P2 | Broker core skeleton | Registry, base classes, session, TCBS client |
| P3 | Read-side services | Account, money, order query, positions |
| P4 | Write-side under dry-run | Equity/derivative place-update-cancel có guard |
| P5 | Portfolio domain | Ledger, PnL, returns, reconciliation |
| P6 | Public TCBS parity | Listing native + compatibility fixes |
| P7 | Hardening | Tests, smoke, docs, audit, sign-off |

---

## 12. Quyết định kỹ thuật đã chốt trong RFC này

1. Dual-plane là bắt buộc, không phải optional refactor.
2. Broker lane phải có registry riêng.
3. Broker lane không dùng generic request logging hiện có ở đường mang secret.
4. Portfolio là domain riêng, không đặt trong explorer layer.
5. Public TCBS parity là một track release quan trọng nhưng không được kéo broker lane trở lại kiến trúc explorer.

---

## 13. Tiêu chí chấp nhận kiến trúc

- Có thể chỉ ra biên giới giữa provider lane và broker lane bằng package path, public entrypoint và test suite riêng.
- Không còn đường control-flow nào cho phép TCBS broker secret đi vào generic logger hiện có.
- Một session TCBS không thể lẫn state với KBS/VCI/AUTO.
- Public TCBS listing không còn phụ thuộc silent fallback KBS trong release mục tiêu.
- Mọi tài liệu, module tree và audit file được cập nhật đồng bộ.
