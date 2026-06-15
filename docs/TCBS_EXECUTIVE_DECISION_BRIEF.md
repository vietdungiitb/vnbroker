# TCBS Executive Decision Brief

> Mục tiêu: một trang để chốt quyết định trước khi code.
>
> Trạng thái: Chờ phê duyệt kiến trúc và kế hoạch thực hiện.
>
> Ngày: 2026-05-19

---

## 1. Quyết định đề xuất

**Chọn mô hình dual-plane.**

- **TCBS Broker Plane** là nền tảng chính cho auth, session, account, money, equity order, derivative order, portfolio và reconciliation.
- **Provider Plane** tiếp tục giữ vai trò market-data portable cho `Quote`, `Listing`, `Company`, `Finance`, `Trading` giữa KBS, VCI, TCBS và AUTO.
- **Security Plane** là lớp bắt buộc cho redaction, credential isolation, audit trail, idempotency và write safety.

Nói ngắn gọn:

- Nếu cần **tài khoản thật + tiền + lệnh + danh mục**, dùng **TCBS broker plane**.
- Nếu cần **public market-data portable**, tiếp tục dùng **provider plane**.
- Nếu cần **ứng dụng đầu tư lâu dài**, dùng cả hai nhưng không trộn control-flow, credential hay logging.

---

## 2. Vì sao phải làm như vậy

| Quan sát hiện tại | Ý nghĩa kỹ thuật |
|---|---|
| `vnbroker/common/client.py` đang exchange token TCBS ngay trong `stock()` | Auth broker đang nằm sai chỗ, lẫn vào public entrypoint |
| `vnbroker/common/data.py` đang fallback Listing TCBS sang KBS | TCBS public layer chưa native hoàn chỉnh |
| `vnbroker/api/listing.py` chưa nhận `source='TCBS'` | Provider parity của TCBS còn thiếu |
| `vnbroker/explorer/tcbs/auth.py` đang giữ logic token/env | Auth broker đang mắc trong explorer layer |
| `vnbroker/core/utils/client.py` log nguyên `params` và `payload` khi bật `show_log` | Broker lane không được tái dùng đường request này cho secret/write flows |

---

## 3. Hard rules cần chốt ngay

1. Không dùng `AUTO` trong broker plane.
2. Không reuse generic request logger cho đường có token, OTP, API key, order payload.
3. Token broker mặc định chỉ ở memory; không ghi file plaintext như SDK tham khảo.
4. `Vnbroker.stock(...)` giữ cho provider/public lane; broker lane đi qua entrypoint mới.
5. Mọi write operation phải có `dry_run`, `request_id`, `idempotency_key` và audit evidence.
6. Không retry lệnh write nếu chưa có kiểm tra trạng thái và đảm bảo idempotency.
7. Public TCBS parity là track riêng, không được làm cớ để trì hoãn security substrate của broker lane.

---

## 4. Kiến trúc chốt

```text
Provider Plane        -> Quote / Listing / Company / Finance / Trading
Broker Plane          -> Auth / Account / Money / Equity / Derivatives / Portfolio
Security Plane        -> Credentials / Redaction / Audit / Idempotency / Write Guard
App Integration Plane -> Django / Celery / Redis / Dashboard / Robo-advisor
```

### Phân vai ngắn gọn

- Provider Plane: đọc dữ liệu công khai, đổi provider ít sửa code.
- Broker Plane: mang semantics của tài khoản thật và giao dịch thật.
- Security Plane: cưỡng chế biên giới giữa hai lane và bảo vệ secret.
- App Integration Plane: orchestration, cache, persistence và API cho sản phẩm.

---

## 5. Các quyết định public API

1. Giữ `Vnbroker.stock(...)` cho provider lane.
2. Thêm `Vnbroker.broker(provider='TCBS', ...)` cho broker lane.
3. Bên dưới broker lane tổ chức theo domain:
   - `session()`
   - `account()`
   - `money()`
   - `equity()`
   - `derivatives()`
   - `portfolio()`

---

## 6. Lộ trình thực hiện ngắn

1. Khóa security substrate và registry tách biệt.
2. Mở read-side broker services: auth, account, money, holdings, order query.
3. Mở write-side dưới `dry_run` với idempotency guard.
4. Xây portfolio engine và reconciliation.
5. Hoàn thiện TCBS public provider parity để không còn fallback KBS ở Listing.

---

## 7. Kết luận một câu

**TCBS có thể trở thành primary broker cho vnbroker, nhưng chỉ nếu tách broker lane khỏi provider lane, khóa security-first từ đầu, và coi portfolio là domain riêng chứ không phải phần mở rộng của explorer layer.**
