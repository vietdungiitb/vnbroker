# CÂU HỎI CẦN `vnsaas` XÁC NHẬN — TÍCH HỢP CẤP PHÉP `vnbroker`

**Ngày lập:** 2026-10-03
**Gửi:** Đội phát triển `vnsaas` · **Nhận từ:** `vnbroker`
**Tài liệu gốc:** `docs/LICENSING_VNSAAS_INTEGRATION_SPEC_20261003.md`
**Trạng thái:** Chờ trả lời · **`vnbroker` chưa viết mã cho tới khi có câu trả lời**

---

## Vì sao tài liệu này tồn tại

Đặc tả cần `vnsaas` cung cấp một **lease ký số** (entitlement lease) mà `vnbroker`
xác thực cục bộ. Hợp đồng giữa hai bên đã đề xuất xong, nhưng còn các điểm mà
`vnsaas` phải quyết trước khi `vnbroker` bắt đầu viết mã.

Vì `vnsaas` chưa chạy thật, `vnbroker` **không code theo giả định** — mỗi điểm
dưới đây đều có thể làm đổi thiết kế module `vnbroker/core/licensing/`.

---

## A. CHẶN — không có câu trả lời thì `vnbroker` không bắt đầu được

### A1. `decision_id` có giữ nguyên suốt vòng đời lease không?

`D07 §3.1` trả `decision_id` trong phản hồi. `D07 §10.1` yêu cầu client gửi
`decision_id` kèm mỗi bản ghi metering.

**Cần chốt:** `decision_id` là *định danh một lần quyết định* (đổi mỗi lần
verify) hay *định danh quan hệ cấp phép* (giữ nguyên suốt đời lease)?

**Vì sao quan trọng:** `vnbroker` gửi metering theo lô 15 phút. Nếu
`decision_id` đổi mỗi lần verify, client phải lưu danh sách id để quy về, phức
tạp và dễ sai khi đối soá. Nếu giữ nguyên, một id cho cả kỳ thanh toán — đối
chiếu một lần là xong.

### A2. `limits.consumed` có được trả tại thời điểm cấp lease không?

`vnbroker` cần biết lượng đã tiêu ở thời điểm nhận lease, để khôi phục bộ đếm
sau khi tiến trình khởi động lại mà **không** phải gọi thêm
`GET /api/v1/metering/usage/current`.

Đặc tả hiện có `limits` trong phản hồi 200 nhưng chưa nói rõ `consumed` có luôn
đi kèm không.

### A3. Scope/capability nào được phát cho `vnbroker` ở v1.0?

`OPEN_QUESTIONS` Q-20 đã chốt v1.0 chỉ bán `vninvestcharts` + `vnbroker-data`.
Còn danh sách capability cụ thể của `vnbroker-data` thì chưa thấy.

**Cần:** danh sách capability chính thức, theo dạng:

```
vnbroker-data.quote      ← giá
vnbroker-data.bar        ← nến
vnbroker-data.depth      ← order book
vnbroker-data.finance    ← tài chính
```

`vnbroker` sẽ gate từng capability này. Danh sách khác với đề xuất ⇒ đổi bảng
gate.

> **Lưu ý liên quan:** `vnbroker-data` **không thể** bao gồm lane SSI. SSI là
> ngân hàng chứng khoán, OpenAPI của họ chính là API trading, không có public
> data API riêng — bán gói data chứa SSI thì bắt buộc phải có tài khoản môi giới.
> Điều này phải nêu trên trang bán hàng.

### A4. Ai giữ khoá ký Ed25519, và vòng đời xoay khoá thế nào?

`vnbroker` sẽ nhúng **khoá công khai** (Ed25519, RFC 8032). Khoá riêng tư chỉ
nằm ở `vnsaas`.

**Cần chốt:**

| # | Câu hỏi |
|:--|:--|
| A4.1 | Khoá lưu ở đâu — biến môi trường, KMS, hay secret manager? |
| A4.2 | Bao lâu xoay một lần? |
| A4.3 | Có hỗ trợ hai `kid` hoạt động cùng lúc không? (để lease đang chạy không bị từ chối khi xoay) |
| A4.4 | Có cơ chế thu hồi (`kid` bị vô hiệu) không? |

`vnbroker` cần nhúng **tối thiểu 2 khoá công khai** cùng lúc để gia hạn không
gián đoạn. Nếu `vnsaas` chỉ hỗ trợ một `kid` tại một thời điểm, cơ chế xoay khoá
phải chậm hơn.

> **Không dùng chung `CORE_PAT_PEPPER`.** Đó là bí mật đối xứng dùng để băm PAT.
> Ký lease cần khoá bất đối xứng riêng — nếu chung, việc lộ pepper cho phép ký
> lease giả.

### A5. Model `Activation` sẽ ai xây, khi nào?

Đọc `packages/core/backend/src/` toàn bộ: **22 model, không có cái nào tên
activation**. `CoreTenant.max_activations` chỉ là một con số (`IntegerField`),
**không biết máy nào đã kích hoạt**.

Nhưng `D07 §11` đặc tả đầy đủ:
- `POST /api/v1/activations`
- `GET /api/v1/activations`
- `DELETE /api/v1/activations/{id}`

Cần model lưu: `credential`, `fingerprint`, `activated_at`, `last_seen_at`,
`machine_label`.

**Đây là thứ chặn cả luồng offline** — ràng lease vào đúng một máy là cơ chế
chống sao chép license.

---

## B. CẦN THIẾT ĐỂ LÀM ĐÚNG — có thể chờ, nhưng nên có sớm

### B1. `/metering/usage` có nhận lô nhiều dòng không?

`vnbroker` gửi mỗi 15 phút. Hiện tại mẫu một dòng:
```json
{ "meter_code": "api_call", "quantity": 412, "decision_id": "01H8XQ..." }
```

**Câu hỏi:** có `{ "items": [...] }` không? Nếu không, `vnbroker` phải gửi N
request → tăng tải và tăng rủi ro trùng.

### B2. `offline_grant_days` có cấu hình được không?

Đặc tả đang đặt cứng **72 giờ**. Có khách cần offline lâu hơn (môi trường
air-gapped, quy trình phê duyệt nội bộ kéo dài vài tuần).

**Câu hỏi:** theo hợp đồng, theo gói, hay cấu hình toàn hệ thống?

### B3. `entitlement` app có 0 view — khi nào có?

`entitlement/` có `models.py` + `migrations/` nhưng **không có `views.py`, không
có `urls.py`**. Tức là `POST /api/v1/entitlements/verify` — cổng duy nhất mà
`vnbroker` cần — hiện **chưa tồn tại**.

**Cần:** mốc thời gian có endpoint chạy được để `vnbroker` test tích hợp.

### B4. Login/JWT đã cấu hình chưa?

`requirements.txt` có `djangorestframework-simplejwt==5.3.1` và
`PyJWT==2.12.1`, nhưng grep `settings.py` **không thấy** `SIMPLE_JWT` nào.

`D07 §4.3` mô tả `POST /api/v1/auth/login` và `identity_access/urls.py` hiện chỉ
có `auth/me` + `health`. Cần biết login bao giờ có để `vnbroker` viết luồng
`PAT = login → POST /auth/pat`.

### B5. `/entitlements/verify` chạy được bằng PAT ngay khi phát?

`PATAuthentication` đã hoàn chỉnh (băm HMAC+pepper, chỉ mục `prefix`, so sánh
thời gian hằng, chặn revoked/expired/tenant_suspended). Nhưng
`POST /api/v1/auth/pat` để **cấp** PAT chưa có trong `identity_access/urls.py`.

**Câu hỏi:** có thể tạo PAT bằng đường admin (Payload/Django admin) trước khi
cổng `/auth/pat` xong không? `vnbroker` cần ít nhất một PAT để test.

---

## C. XÁC NHẬN HIỂU BIẾN — cần trả lời "đúng" hoặc "sai"

| # | Nội dung đề xuất | Cần xác nhận |
|:--|:--|:--|
| C1 | `vnsaas` ký lease, `vnbroker` verify cục bộ bằng khoá công khai nhúng | |
| C2 | `vnbroker` gọi `/verify` **một lần / 24 giờ**, không gọi ở đường nóng | |
| C3 | `vnsaas` **không** đếm được lượng dữ liệu khách đọc (client nối thẳng provider) | |
| C4 | Metering là client tự báo ⇒ dùng cho cảnh báo, **không** làm nền tảng thu tiền | |
| C5 | Hợp đồng chính tính theo **gói × số máy × thời hạn** | |
| C6 | `seats_limit` và `exp` là hai cơ chế cưỡng chế đáng tin cậy | |
| C7 | `vnbroker` chỉ lưu: PAT, lease đã ký, bộ đếm chưa gửi. **Không** lưu dữ liệu tài chính | |

---

## D. RỦI RO CẦN `vnsaas` CÂU TRẢ LỜI

### D1. Quy mô `vnsaas` khi chạy thật

`vnbroker` cần biết để chọn mức jitter khi refresh:

| # | Câu hỏi |
|:--|:--|
| D1.1 | Số máy dự kiến dùng đồng thời trong 6 tháng đầu? |
| D1.2 | Có bao giờ deploy nhiều instance không? |

`vnbroker` sẽ thêm jitter ngẫu nhiên 0–300 giây khi refresh để không dồn
request. Nếu quy mô nhỏ thì có thể giảm; nếu lớn thì jitter phải rộng hơn.

### D2. Có bao giờ ngắt kết nối dài không?

Nếu `vnsaas` bảo trì hơn 72 giờ, mọi client rơi vào chế độ community cùng lúc.
`vnbroker` cần biết để điều chỉnh thông điệp và hạn grace cho phù hợp.

### D3. `TenantResolutionMiddleware` áp cho `/entitlements/*` chứ?

File `middleware.py` liệt kê `EXEMPT_PATH_PREFIXES` — cần xác nhận
`/api/v1/entitlements/` và `/api/v1/activations/` **không** nằm trong danh sách
miễn. Cả hai đều cần tenant bắt buộc.

---

## E. THỨ `vnsaas` KHÔNG CẦN TRẢ LỜI

Để tránh làm mất thời gian hai bên, những điểm sau `vnbroker` đã tự quyết:

| # | Vấn đề | `vnbroker` tự xử lý |
|:--|:--|:--|
| E1 | Chữ ký Ed25519 theo RFC 7515/8032 | Đã chốt |
| E2 | TTL 24 giờ, grace 72 giờ | Đã chốt |
| E3 | Cấu trúc thư mục module, fingerprint máy, cache lease trên đĩa | Thuộc `vnbroker` |
| E4 | Metering gửi lô 15 phút, `Idempotency-Key` phía client | Thuộc `vnbroker` |
| E5 | Luồng kích hoạt air-gapped 2 bước — phía client | Thuộc `vnbroker` |
| E6 | Khi hết hạn thì hạ xuống community chứ không `raise` | Thuộc `vnbroker` |
| E7 | Bộ test T1–T12 | Thuộc `vnbroker` |

---

## Tóm tắt

| Nhóm | Số câu | Chặn `vnbroker`? |
|:--|--:|:--|
| **A — Chặn** | 5 | **Có** |
| **B — Cần thiết** | 5 | Không, nhưng chậm sẽ nghẽn |
| **C — Xác nhận hiểu biến** | 7 | Không |
| **D — Rủi ro** | 3 câu (6 ý) | Không |
| **E — Không cần hỏi** | 7 | — |

**Cách trả lời:** trả lời trực tiếp trong file này, hoặc tạo file cùng thư mục.
`vnbroker` sẽ bắt đầu viết mã khi nhóm A có câu trả lời cho **A1, A2, A3**.