# ĐẶC TẢ TÍCH HỢP CẤP PHÉP `vnbroker` ↔ `vnsaas`

**Ngày:** 2026-10-03 · **Trạng thái:** Đề xuất chờ duyệt · **Chưa triển khai**
**Bên nhận hợp đồng phía server:** `vnsaas` (Django 5.2 + DRF), theo `D07 §3.1`, `§10`, `§11`
**Câu hỏi cần `vnsaas` trả lời:** [`OPEN_QUESTIONS_FOR_VNSAAS_20261003.md`](OPEN_QUESTIONS_FOR_VNSAAS_20261003.md)

> **Chưa viết mã.** Theo yêu cầu chủ dự án: `vnbroker` không code cho tới khi
> `vnsaas` thực sự online. Nhóm A trong tài liệu câu hỏi là điều kiện bắt đầu.

---

## 0. Ba quyết định đã chốt

| # | Quyết định | Giá trị |
|:--|:--|:--|
| D1 | Thời hạn lease (entitlement lease) | **24 giờ** |
| D2 | Hỗ trợ offline | **Có** — `vnsaas` không phải lúc nào cũng online |
| D3 | Metering | **Có** — định lượng theo lượt request / dung lượng |

---

## 1. Vấn đề bài toán

`vnsaas` giới hạn `POST /api/v1/entitlements/verify` ở **1.000 lần/phút/PAT**
(`D07 §14`). Đó là khoảng 16,7 lần/giây.

Nếu `vnbroker` gọi endpoint này ở **mỗi thao tác dữ liệu**, một backtest lấy
100.000 nến sẽ cần 100.000 lần xác thực → vượt hạn mức ngay lập tức. Sản phẩm
trở nên không dùng được sau một lần thử.

Ngược lại, nếu không gọi: không kiểm soát được quyền, dễ mất doanh thu.

**Yêu cầu cần đạt:** *không gọi server ở đường nóng* mà *vẫn không thể bỏ qua
kiểm tra quyền*.

---

## 2. Giải pháp: Signed Entitlement Lease

### 2.1 Nguyên lý chuẩn áp dụng

| Nguyên lý | Nguồn |
|:--|:--|
| Lease ký bằng khoá bất đối xứng; client nhúng **khoá công khai**, chỉ verify được, không ký được | RFC 8032 (Ed25519); `pylicensify`, AZgardTek/Infracast |
| Lease có TTL ngắn, gia hạn âm thầm; lỗi mạng thì dùng bản cache còn hạn, không chặn cứng | Windows Activation — bài học triển khai |
| Schema quyền: Entitlement ID · Quantity · Metric (per-device/user/concurrent) · Constraints · Measurement | **ISO/IEC 19770-3:2016** (SWEN) |
| Cache kết quả validate theo TTL; tuân thủ `X-RateLimit-*`; thêm jitter khi refresh hàng loạt | Keygen.sh, Licentric |

### 2.2 Cơ chế

```
  lần khởi động / mỗi 24h        MỌI lời gọi dữ liệu
              │                              │
              ▼                              ▼
   POST /api/v1/entitlements/verify    kiểm tra capability
   (Bearer PAT, 1 lần)                 TRONG lease đã giải mã
              │                              │
              ▼                              ├─ đủ  → chạy
      vnsaas ký Ed25519                    └─ thiếu → chặn + thông báo
              │
              ▼
   ~/.vnbroker/lease.jws  ──► verify bằng public key nhúng sẵn
   (TTL 24h · grace 72h)
```

**Không có lời gọi mạng nào trên đường nóng.**

### 2.3 Tác động lên rate-limit

| | Trước | Sau |
|:--|:--|:--|
| Số lần gọi `/verify` | bằng số lệnh dữ liệu (không giới hạn) | 1 lần / 24h / máy |
| 10 máy × 30 ngày | hàng triệu | **300 lần / tháng** |
| Hạn mức cho phép | — | 43,2 triệu / tháng |
| **Biên an toàn** | vượt ngay | **≈ 144.000×** |

---

## 3. Định dạng lease

JWS (RFC 7515) ký **EdDSA / Ed25519**. Ba phần `header.payload.signature`,
Base64URL, phân tách bằng dấu chấm.

### 3.1 Header

```json
{ "alg": "EdDSA", "typ": "JWT", "kid": "vnsaas-lease-2026a" }
```

`kid` cho phép xoay vòng khoá mà không phải phát hành lại toàn bộ.

### 3.2 Payload

```jsonc
{
  "iss": "vnsaas",
  "sub": "01H8XQ2M4K7P9RZ3N5V8T1Y4B6D",   // decision_id
  "aud": "vnbroker",
  "iat": 1791000000,
  "exp": 1791086400,                          // iat + 86400
  "jti": "01H8XQ2M...",                       // UUIDv7 — chống tái sử dụng

  // Quyền (ISO/IEC 19770-3: Constraints)
  "capabilities": [
    "vnbroker-data.quote",
    "vnbroker-data.bar",
    "vnbroker-data.depth"
  ],

  // Định lượng (ISO/IEC 19770-3: Quantity + Metric)
  "limits": {
    "api_call": { "limit": 100000, "consumed_at_issue": 41230, "unit": "call" },
    "payload_mb": { "limit": 20480, "consumed_at_issue": 8123, "unit": "mb" }
  },

  // Ràng buộc máy (ISO/IEC 19770-3: Device Context)
  "machine": {
    "fingerprint": "sha256:7f3a…",
    "seats_used": 3,
    "seats_limit": 10
  },

  "product_code": "vnbroker-data",
  "tier_code": "professional",
  "legal_terms_version": "2026-10-01"
}
```

`consumed_at_issue` cho phép client khôi phục bộ đếm sau khi khởi động lại mà
không gọi `GET /api/v1/metering/usage/current`.

### 3.3 Ràng buộc bắt buộc khi verify

| Kiểm tra | Hành động khi sai |
|:--|:--|
| Chữ ký hợp lệ với `kid` đang tin cậy | Từ chối — **fail closed** |
| `now < exp` | Từ chối (báo hết hạn, không phải lỗi ký) |
| `aud == "vnbroker"` | Từ chối — chống dùng nhầm lease của sản phẩm khác |
| `iss == "vnsaas"` | Từ chối |
| `machine.fingerprint` khớp máy đang chạy | Từ chối — chống sao chép lease sang máy khác |
| Trong `grace` (hết hạn nhưng chưa quá 72h) | Cho qua ở chế độ giảm tính năng + cảnh báo |

> **Fail closed là bắt buộc.** Lỗi xác minh phải chặn, không phải "cho qua rồi
> log lại". Đây là nguyên tắc từ `grantseal` và là điều kiện để lease còn đáng
> tin.

---

## 4. Module phía `vnbroker`

### 4.1 Vị trí đặt

```
vnbroker/
  core/
    licensing/            ← module MỚI
      __init__.py
      verifier.py         Ed25519 verify, kiểm payload
      lease_store.py      đọc/ghi ~/.vnbroker/lease.jws
      client.py           gọi vnsaas, refresh, retry+jitter
      activation.py       luồng kích hoạt offline 2 bước
      meter.py            bộ đếm + gửi theo lô
      fingerprint.py      tính fingerprint máy ổn định
      errors.py           LicenseError, LeaseExpired, CapabilityDenied…
```

Phụ thuộc sẵn có: `cryptography>=42.0.5` (Ed25519), `tenacity>=8.0.0` (retry +
backoff). **Không cần thêm thư viện mới.**

### 4.2 Cổng vào

Không ép người dùng gọi thủ công — kiểm tra chạy trong `Vnbroker.__init__`:

```python
from vnbroker.core.licensing import LicenseGate

class Vnbroker(BaseAdapter):
    def __init__(self, source: str = "KBS", *, license_key: str | None = None, **kw):
        super().__init__(source=source, **kw)
        self._gate = LicenseGate(license_key=license_key, client_name="vnbroker")
        self._gate.require("vnbroker-data.quote")   # ném LicenseError nếu thiếu
```

Hành vi mong muốn:

| Tình huống | Kết quả |
|:--|:--|
| Không có license, chưa cấu hình | Chạy ở chế độ **community** — có giới hạn, in cảnh báo một lần |
| License hợp lệ | Đầy đủ tính năng |
| License hết hạn, trong grace | Đầy đủ tính năng + cảnh báo đếm ngược |
| License hết hạn, quá grace | Chế độ community — `warnings.warn`, không `raise` |
| Capability cụ thể không có | `raise CapabilityDenied` — chỉ chặn đúng chức năng đó |

> **Không `raise` khi hết hạn.** Chặn cứng khiến khách mất dữ liệu giữa chừng
> khi đang chạy backtest dài. Hạ xuống chế độ community kèm cảnh báo là hành vi
> mà người dùng chấp nhận được. Việc thu tiền thuộc về `vnsaas`.

### 4.3 Xoay vòng khoá công khai

Nhúng **tối thiểu 2 khoá công khai** cùng lúc, mỗi khoá có `kid`:

```python
TRUSTED_KEYS = {
    "vnsaas-lease-2026a": bytes.fromhex("…"),   # khoá hiện hành
    "vnsaas-lease-2025z": bytes.fromhex("…"),   # khoá trước, giữ để gia hạn
}
```

Khi xoay vòng: phát hành lease ký bằng khoá mới → đợi hết TTL lease cũ (~24h) →
gỡ khoá cũ. Không có khoảng thời gian nào mà lease hợp lệ lại bị từ chối.

---

## 5. Chế độ offline (D2)

Cần cho máy air-gapped và cho trường hợp `vnsaas` down kéo dài.

### 5.1 Kích hoạt air-gapped — 2 bước

```
MÁY CỤC BỘ                                    VNSAAS
     │                                           │
     │ ① tạo yêu cầu kích hoạt                  │
     │   request.json = {                        │
     │     fingerprint, public_key, nonce,       │
     │     product_code, requested_ttl_days      │
     │   }                                       │
     ├──────────────►│                            │
     │               │ ② ký lease (Ed25519)     │
     │◄──────────────┤ license.jws               │
     │                                           │
     │ ③ verify → copy vào ~/.vnbroker/          │
```

Yêu cầu bắt buộc: máy cục bộ gửi khoá công khai của nó, để `vnsaas` ràng lease
đúng vào một máy — không phát hành một license offline dùng chung được.

### 5.2 Chính sách khi mất mạng

| Tình huống | Hành động |
|:--|:--|
| Không mạng, lease còn hạn | Chạy bình thường, không cảnh báo |
| Không mạng, lease hết hạn, trong 72h | Chạy + `warnings.warn` đếm ngược giờ grace |
| Không mạng, quá grace | Chuyển community, hướng dẫn liên hệ để gia hạn offline |
| Không mạng > 7 ngày | Xoá cache lease, yêu cầu kích hoạt lại |

### 5.3 Gia hạn offline

Nếu khách cần offline lâu hơn 72h: xuất một lease mới có `exp` xa hơn **từ phía
`vnsaas`**. Đây là quyết định kinh doanh (cho phép bao lâu không cần mạng), không
phải quyết định kỹ thuật — client không có cách nào tự gia hạn.

---

## 6. Metering (D3)

### 6.1 Kết nối với thiết kế sẵn có

`vnsaas` đã có:

- `catalog.Meter` — `unit: call/mb/seat/symbol`, `aggregation: sum/max`, cờ `is_billable`
- `POST /api/v1/metering/usage` — trả **202 bất đồng bộ**, có `decision_id`
- `GET /api/v1/metering/usage/current` — trả `consumed/limit/state`

`Meter` đã thiết kế đúng để "biến metric thành **dữ liệu**" — thêm loại định
lượng mới không phải viết migration.

### 6.2 Gửi theo lô

```json
POST /api/v1/metering/usage
{ "meter_code": "api_call", "quantity": 412, "decision_id": "01H8XQ..." }
```

**Không gửi mỗi lệnh.** Tích luỹ cục bộ, gửi mỗi **15 phút** hoặc khi đủ 500
lượt, tùy điều kiện nào đến trước. Kèm `Idempotency-Key` UUID để retry không
tính hai lần.

Tần suất: 96 lần/ngày/máy ⇒ 10 máy × 30 ngày = **28.800 lần/tháng**, vẫn nằm
xa hạn mức.

### 6.3 Metering khi offline

Không có mạng thì không gửi được. Bộ đếm tích luỹ trong
`~/.vnbroker/meter.pending.json`, kèm chuỗi `seq` tăng đơn điệu:

```json
{ "seq": 17, "meter_code": "api_call", "quantity": 4820,
  "window_start": "2026-10-03T09:00:00Z", "window_end": "2026-10-03T09:15:00Z" }
```

Khi có mạng lại: gửi theo thứ tự `seq`. Server giữ `last_seq` đã nhận; bản ghi có
`seq <= last_seq` bị bỏ qua ⇒ không tính hai lần. `Idempotency-Key` chống trùng
khi client retry.

### 6.4 Giới hạn thật của việc đo

**Cần nói thẳng để không quyết định sai:** khi `vnbroker` nối thẳng tới provider
(VCI/KBS/TCBS/DNSE) mà `vnsaas` không đứng giữa đường truyền, `vnsaas` **không
thể tự đếm** lượng dữ liệu khách đọc. Con số báo cáo là do **chính client báo**.

Hệ quả: một client sửa mã có thể **báo thiếu**, không sửa được phần đã dùng.

| Cách dùng metering | Độ tin cậy | Dùng để |
|:--|:--|:--|
| Báo cáo nội bộ, phân tích nhu cầu nâng gói | Cao — chỉ cần xu hướng | Quyết định giá, gợi ý nâng cấp |
| Tính cướng vượt hạn mức cho khách hợp tác | Trung bình | Hoá đơn, chấp nhận rủi ro có kiểm soát |
| Chống lạm dụng trên client cố ý | Thấp — không chặn được | Không dựa vào |

**Cơ chế cưỡng chế đáng tin cậy là gì:** `seats_limit` và `exp`. Cả hai đều do
`vnsaas` kiểm soát, đều nằm trong lease đã ký, client không thể tự mở rộng.

**Khuyến nghị:** định giá theo **gói + số máy + thời hạn** là hợp đồng chính.
Metering dùng cho *cảnh báo vượt hạn mức* và *gợi ý nâng gói*, không làm nền tảng
thu tiền. Nếu sau này phải tính cướng theo dung lượng một cách chắc chắn, điều
đó đòi dữ liệu đi qua `vnsaas` — tức đảo ngược quyết định kiến trúc đã chốt.

---

## 7. Công việc phía `vnsaas`

Không sửa thiết kế, chỉ bổ sung. Đội phát triển `vnsaas` giữ nguyên tốc độ.

| # | Việc | Ghi chú |
|:--|:--|:--|
| 1 | Thêm biến môi trường `CORE_LICENSE_SIGNING_KEY` | Khoá Ed25519 riêng, **không** dùng chung `CORE_PAT_PEPPER`. `settings.py` hiện có 4 chỗ `raise ImproperlyConfigured` — thêm theo cùng khuôn |
| 2 | `/entitlements/verify` trả kèm `lease` | JWS Ed25519, TTL 86400s, theo schema §3 |
| 3 | Model `Activation` | **Hiện chưa có.** `CoreTenant.max_activations` mới chỉ là con số, không biết máy nào đã kích hoạt. Cần theo `D07 §11` |
| 4 | `entitlement/views.py` + `urls.py` | App có model + migration nhưng **0 view** |
| 5 | Endpoint kích hoạt air-gapped | Nhận `request.json`, trả `license.jws` đã ký |
| 6 | Xử lý `Idempotency-Key` ở `/metering/usage` | `D07 §13.1` đã yêu cầu; cần bảng theo dõi |
| 7 | Ghi `last_seq` cho metering offline | Chống đếm trùng khi client gửi bù |

**Các khoá đã có, không cần làm lại:** `CorePATCredential` (băm HMAC-SHA256 +
pepper, chỉ mục `prefix`, so sánh thời gian hằng), `PATAuditLog` (append-only),
`TenantResolutionMiddleware` (4 lớp chống rò rỉ tenant).

---

## 8. Bảng lỗi client phải hiểu

| HTTP | `code` | Client làm gì |
|:--:|:--|:--|
| 401 | `pat_invalid` / `pat_expired` / `pat_revoked` | Hỏi lại PAT, hướng dẫn tạo PAT mới |
| 403 | `insufficient_scope` | Liệt kê capability còn thiếu |
| 403 | `seat_limit` | Báo `seats_used / seats_limit`, mời admin cấp thêm máy |
| 402 | `approval_pending` | Báo đang chờ duyệt pháp lý |
| 429 | `rate_limited` | Tôn trọng `Retry-After`, backoff + jitter |
| 429 | `activation_limit_reached` | Báo đủ máy, hướng dẫn thu hồi máy cũ |

`reason_code` và `failed_at_step` (`D07 §3.1`) phải hiển thị nguyên văn cho
người dùng — nhờ vậy khi khách khiếu nại, biết chính xác bước nào chặn.

---

## 9. Rủi ro & biện pháp

| # | Rủi ro | Mức | Biện pháp |
|:--|:--|:--|:--|
| 1 | Bẻ khoá offline bằng patch nhị phân | Cao | Không có private key trên client; chấp nhận giới hạn toán học của mọi hệ offline. **Nói rõ với khách, đừng hứa "không thể bẻ"** |
| 2 | Client báo thiếu metering | Cao | Đã phân tích §6.4 — không dựa vào nó làm nền tảng thu tiền |
| 3 | Nhiều máy refresh đúng giờ đồng loạt | Trung bình | Jitter ngẫu nhiên 0–300s khi refresh |
| 4 | `vnsaas` sập khiến cả hệ thư viện dừng | Trung bình | Lease 24h + grace 72h ⇒ mất tối đa 72h, không phải ngay lập tức |
| 5 | Xoay khoá làm hỏng lease đang chạy | Thấp | Giữ 2 khoá công khai trong 24h |
| 6 | Rò rỉ tenant | Thấp | `TenantResolutionMiddleware` đã có 4 lớp |

---

## 10. Kế hoạch kiểm thử

| # | Ca | Kỳ vọng |
|:--|:--|:--|
| T1 | Lease hợp lệ | Đầy đủ tính năng |
| T2 | Sửa 1 byte payload | Từ chối (`fail closed`) |
| T3 | Đổi `exp` | Từ chối |
| T4 | Đổi `machine.fingerprint` | Từ chối |
| T5 | `aud` sai sản phẩm | Từ chối |
| T6 | Hết hạn, trong grace | Chạy + cảnh báo |
| T7 | Hết hạn, quá grace | Community + cảnh báo |
| T8 | Không mạng, lease còn hạn | Chạy, **không** gọi mạng |
| T9 | Kích hoạt air-gapped | Xác thực thành công, ràng đúng máy |
| T10 | Metering retry | Chỉ tính một lần |
| T11 | Metering offline rồi gửi bù | Không trùng, đúng thứ tự `seq` |
| T12 | 1.000 lệnh dữ liệu liên tiếp | **Tổng 1 lần gọi `/verify`** |

T12 là ca quyết định — chứng minh bài toán rate-limit đã được giải.

---

## 11. Công việc phía `vnbroker` theo thứ tự

| # | Việc | Phụ thuộc |
|:--|:--|:--|
| 1 | `fingerprint.py` — fingerprint ổn định, không đổi khi nâng OS | — |
| 2 | `verifier.py` + `lease_store.py` — verify Ed25519, fail closed | 1 |
| 3 | `client.py` — gọi `vnsaas`, refresh 24h + jitter, retry bằng `tenacity` | 2 |
| 4 | `LicenseGate` + cắm vào `Vnbroker.__init__` | 3 |
| 5 | `meter.py` — bộ đếm, gửi lô 15 phút, xử lý offline | 3 |
| 6 | `activation.py` — luồng air-gapped 2 bước | 3 |
| 7 | T12 + toàn bộ T1–T11 vào `tests/` | 4,5,6 |
| 8 | CI quét artifact để chặn lọt khoá (tiền lệ `grantseal`) | 7 |

## 12. Câu hỏi cần `vnsaas` xác nhận

| # | Câu hỏi | Vì sao chặn |
|:--|:--|:--|
| 1 | `decision_id` có giữ nguyên qua cả vòng đời lease không? | `metering/usage` gắn `decision_id` — nếu đổi mỗi lần thì khó đối soát |
| 2 | `/metering/usage` có nhận lô nhiều dòng không? | Quyết định gửi 1 bản ghi hay gửi mảng |
| 3 | Lease có cần `offline_grant_days` riêng không? | Hiện đang đặt cứng 72h |
| 4 | Phạm vi v1.0 chỉ có `vnbroker-data` — capability nào được phát? | `OPEN_QUESTIONS` Q-20 đã chốt `vninvestcharts` + `vnbroker-data` |