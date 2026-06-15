# TCBS API Contract

**Version:** 1.0  
**Cập nhật:** 2026-05-19  
**Phạm vi:** Broker lane dành cho `vnbroker/broker/tcbs/` — KHÔNG áp dụng cho explorer/public provider lane.

---

## 1. Mục đích

Tài liệu này là contract kỹ thuật ràng buộc giữa TCBS OpenAPI và lớp broker của vnbroker. Mọi thay đổi endpoint, schema, hoặc auth flow phải được phản ánh vào tài liệu này trước khi được merge vào nhánh `dev`.

---

## 2. Khởi tạo Client

```python
from vnbroker.broker.tcbs.client import TCBSBrokerClient

# Khởi tạo cơ bản (api_key qua env var)
client = TCBSBrokerClient()

# Khởi tạo tường minh
client = TCBSBrokerClient(
    api_key="<VNBROKER_BROKER_TCBS_API_KEY>",
    base_url="https://openapi.tcbs.com.vn",
    timeout_seconds=30.0,
    show_log=False,
)

# Xác thực (bắt buộc trước mọi cuộc gọi broker)
client.authenticate(otp="123456")
```

**Env vars được đọc theo thứ tự ưu tiên:**

| Thứ tự | Biến | Ghi chú |
|---|---|---|
| 1 | `VNBROKER_BROKER_TCBS_API_KEY` | Namespace chuẩn mới |
| 2 | `vnbroker_TCBS_OPENAPI_API_KEY` | Compat từ explorer layer |
| 3 | `TCBS_OPENAPI_API_KEY` | Legacy |
| 4 | `TCBS_API_KEY` | Legacy cuối cùng |
| — | `VNBROKER_BROKER_TCBS_BASE_URL` | Override base URL |
| — | `TCBS_OPENAPI_BASE_URL` | Legacy base URL override |
| — | `VNBROKER_BROKER_TCBS_AUTH_TOKEN` | Inject sẵn JWT (bỏ qua OTP flow) |
| — | `TCBS_AUTH_TOKEN` | Legacy auth token inject |

---

## 3. Endpoint Contract

### 3.1 Auth — Lấy JWT Token

| Thuộc tính | Giá trị |
|---|---|
| **Method** | `POST` |
| **URL** | `https://openapi.tcbs.com.vn/gaia/v1/oauth2/openapi/token` |
| **Auth** | Không cần (public endpoint) |
| **Content-Type** | `application/json` |

**Request body:**
```json
{
  "apiKey": "<string>",
  "otp": "<string — 6 chữ số>"
}
```

**Response thành công (200):**
```json
{
  "token": "<JWT string>",
  "expiredTime": "<ISO8601 string | epoch millis>"
}
```

**Response lỗi:**
```json
{
  "code": "INVALID_OTP",
  "message": "OTP không hợp lệ hoặc đã hết hạn."
}
```

**Lưu ý quan trọng:**
- Token có hiệu lực ~8 giờ kể từ thời điểm cấp.
- `apiKey` và `otp` tuyệt đối KHÔNG được log ngay cả ở debug level.
- Sau khi nhận token, lưu vào `BrokerSession` — không ghi ra file hoặc environment.

---

### 3.2 Account — Thông tin tài khoản

#### 3.2.1 Danh sách tài khoản

| Method | URL |
|---|---|
| `GET` | `/gaia/v1/openapi/account/list` |

**Auth header:** `Authorization: Bearer <JWT>`

**Response (200):**
```json
[
  {
    "accountNo": "0123456789",
    "custodyCode": "C123456",
    "fullName": "NGUYEN VAN A",
    "accountType": "EQUITY",
    "status": "ACTIVE"
  }
]
```

---

#### 3.2.2 Hồ sơ tài khoản

| Method | URL |
|---|---|
| `GET` | `/gaia/v1/openapi/account/{accountNo}/profile` |

**Path param:** `accountNo` — mã tài khoản chứng khoán.

**Response (200):**
```json
{
  "accountNo": "0123456789",
  "custodyCode": "C123456",
  "fullName": "NGUYEN VAN A",
  "idNo": "**REDACTED**",
  "phone": "**REDACTED**",
  "email": "**REDACTED**"
}
```

---

#### 3.2.3 Số dư tài khoản

| Method | URL |
|---|---|
| `GET` | `/gaia/v1/openapi/account/{accountNo}/balance` |

**Response (200):**
```json
{
  "accountNo": "0123456789",
  "totalAsset": 100000000,
  "cashBalance": 20000000,
  "stockValue": 80000000,
  "debtBalance": 0,
  "availableAdvanceAmount": 15000000
}
```

---

#### 3.2.4 Sức mua

| Method | URL |
|---|---|
| `GET` | `/gaia/v1/openapi/account/{accountNo}/portfolio/purchasing-power` |

**Response (200):**
```json
{
  "accountNo": "0123456789",
  "purchasingPower": 12000000,
  "marginPurchasingPower": 0,
  "marginRatio": 0.0
}
```

---

### 3.3 Money — Dòng tiền

#### 3.3.1 Tiền mặt

| Method | URL |
|---|---|
| `GET` | `/gaia/v1/openapi/account/{accountNo}/money/cash` |

**Response (200):**
```json
{
  "accountNo": "0123456789",
  "withdrawableAmount": 10000000,
  "pendingSettlement": 5000000,
  "cashBalance": 20000000
}
```

---

#### 3.3.2 Margin

| Method | URL |
|---|---|
| `GET` | `/gaia/v1/openapi/account/{accountNo}/money/margin` |

**Response (200):**
```json
{
  "accountNo": "0123456789",
  "marginLimit": 0,
  "marginUsed": 0,
  "marginAvailable": 0,
  "maintenanceMarginRate": 0.0
}
```

---

### 3.4 Equity — Lệnh cơ sở

#### 3.4.1 Danh sách lệnh trong ngày

| Method | URL |
|---|---|
| `GET` | `/gaia/v1/openapi/account/{accountNo}/orders` |

**Query params:**

| Tham số | Kiểu | Bắt buộc | Mô tả |
|---|---|---|---|
| `page` | int | Không | Trang hiện tại, mặc định 0 |
| `size` | int | Không | Số lệnh mỗi trang, mặc định 50, max 100 |

**Response (200):**
```json
{
  "total": 3,
  "data": [
    {
      "orderId": "ORD123456",
      "symbol": "VNM",
      "side": "BUY",
      "orderType": "LIMIT",
      "quantity": 100,
      "price": 80000,
      "filledQuantity": 0,
      "status": "PENDING",
      "createdAt": "2026-05-19T09:00:00+07:00"
    }
  ]
}
```

---

#### 3.4.2 Chi tiết lệnh

| Method | URL |
|---|---|
| `GET` | `/gaia/v1/openapi/account/{accountNo}/orders/{orderId}` |

---

#### 3.4.3 Lịch sử giao dịch khớp

| Method | URL |
|---|---|
| `GET` | `/gaia/v1/openapi/account/{accountNo}/executions` |

**Query params:** `fromDate` (YYYY-MM-DD), `toDate` (YYYY-MM-DD), `page`, `size`

**Response (200):**
```json
{
  "total": 5,
  "data": [
    {
      "executionId": "EXE789",
      "orderId": "ORD123456",
      "symbol": "VNM",
      "side": "BUY",
      "executedQuantity": 100,
      "executedPrice": 80200,
      "executedAt": "2026-05-19T10:30:00+07:00",
      "fee": 80,
      "tax": 0
    }
  ]
}
```

---

#### 3.4.4 Lịch sử lệnh (historical)

| Method | URL |
|---|---|
| `GET` | `/gaia/v1/openapi/account/{accountNo}/orders/history` |

**Query params:** `fromDate`, `toDate`, `symbol` (tùy chọn), `page`, `size`

---

#### 3.4.5 Đặt lệnh mua/bán *(write — dry_run bắt buộc trong alpha)*

| Method | URL |
|---|---|
| `POST` | `/gaia/v1/openapi/account/{accountNo}/orders` |

**Request body:**
```json
{
  "symbol": "VNM",
  "side": "BUY",
  "orderType": "LIMIT",
  "quantity": 100,
  "price": 80000,
  "requestId": "<UUID — idempotency key>",
  "pinCode": "<6 chữ số — KHÔNG log>"
}
```

**Response thành công (201):**
```json
{
  "orderId": "ORD999",
  "symbol": "VNM",
  "status": "PENDING",
  "createdAt": "2026-05-19T09:15:00+07:00"
}
```

---

#### 3.4.6 Sửa lệnh *(write — dry_run bắt buộc trong alpha)*

| Method | URL |
|---|---|
| `PUT` | `/gaia/v1/openapi/account/{accountNo}/orders/{orderId}` |

**Request body:**
```json
{
  "quantity": 200,
  "price": 79500,
  "requestId": "<UUID>"
}
```

---

#### 3.4.7 Huỷ lệnh *(write — dry_run bắt buộc trong alpha)*

| Method | URL |
|---|---|
| `DELETE` | `/gaia/v1/openapi/account/{accountNo}/orders/{orderId}` |

**Request body:**
```json
{
  "requestId": "<UUID>"
}
```

---

### 3.5 Derivatives — Phái sinh

#### 3.5.1 Danh mục vị thế phái sinh

| Method | URL |
|---|---|
| `GET` | `/gaia/v1/openapi/account/{accountNo}/derivatives/positions` |

**Response (200):**
```json
[
  {
    "symbol": "VN30F2406",
    "side": "LONG",
    "openQuantity": 1,
    "openPrice": 1260.0,
    "currentPrice": 1265.0,
    "unrealizedPnl": 500000,
    "margin": 15000000
  }
]
```

---

#### 3.5.2 Lệnh phái sinh trong ngày

| Method | URL |
|---|---|
| `GET` | `/gaia/v1/openapi/account/{accountNo}/derivatives/orders` |

---

### 3.6 Portfolio — Danh mục cổ phiếu nắm giữ

#### 3.6.1 Danh mục holdings

| Method | URL |
|---|---|
| `GET` | `/gaia/v1/openapi/account/{accountNo}/portfolio/holdings` |

**Response (200):**
```json
[
  {
    "symbol": "VNM",
    "quantity": 500,
    "availableQuantity": 400,
    "averageCost": 79500,
    "currentPrice": 80200,
    "marketValue": 40100000,
    "unrealizedPnl": 350000,
    "unrealizedPnlPercent": 0.88
  }
]
```

---

## 4. Error Contract

Tất cả lỗi broker phải được wrap thành exception từ `vnbroker/broker/tcbs/exceptions.py`.

| Exception class | HTTP status | Khi nào raise |
|---|---|---|
| `BrokerAuthError` | 401 | Token hết hạn, OTP sai, apiKey không hợp lệ |
| `BrokerPermissionError` | 403 | Tài khoản không đủ quyền cho operation |
| `BrokerValidationError` | 400 | Input sai schema, symbol không hợp lệ, quantity âm |
| `BrokerRateLimitError` | 429 | Vượt rate limit TCBS |
| `BrokerOrderError` | 422 | Lỗi nghiệp vụ lệnh (không đủ sức mua, ngoài giờ giao dịch, v.v.) |
| `BrokerSessionExpiredError` | 401 code=SESSION_EXPIRED | Session đã bị huỷ hoặc token hết hạn (phân biệt với BrokerAuthError) |
| `BrokerNetworkError` | timeout / 5xx | Lỗi mạng hoặc server TCBS |

**Required fields trên mọi BrokerError:**
```python
class BrokerError(Exception):
    code: str        # TCBS error code hoặc internal code
    message: str     # Message rõ ràng cho dev, không chứa secret
    http_status: int # HTTP status code nhận được
    request_id: str  # request_id đã gửi (để trace log)
```

---

## 5. dry_run Contract

Mọi write method (đặt lệnh, sửa lệnh, huỷ lệnh) phải hỗ trợ `dry_run=True`.

Khi `dry_run=True`:
- Không gửi HTTP request đến TCBS.
- Trả về `dict` chứa debug object:
```python
{
  "dry_run": True,
  "method": "POST",
  "url": "https://openapi.tcbs.com.vn/gaia/v1/openapi/account/0123456789/orders",
  "headers": {"Authorization": "Bearer ***REDACTED***"},
  "payload": {
    "symbol": "VNM",
    "side": "BUY",
    "quantity": 100,
    "price": 80000,
    "pinCode": "***REDACTED***",
    "requestId": "uuid-here"
  }
}
```
- Các field nhạy cảm (`pinCode`, `Authorization`) phải được redact.

---

## 6. Backward Compatibility

| Điều kiện | Hành vi |
|---|---|
| Caller dùng `vnbroker.explorer.tcbs.auth.request_openapi_token()` | Vẫn hoạt động (bridge giữ lại), nhưng emit `DeprecationWarning` từ S10 |
| Caller dùng `Vnbroker.stock(source="TCBS", otp=...)` | Tiếp tục hoạt động, log `DeprecationWarning` gợi ý dùng `.broker()` |
| Caller dùng `Vnbroker.broker()` | Entrypoint mới, trả về `TCBSBrokerClient` hoàn chỉnh |

---

## 7. Ghi chú Live (cập nhật theo trải nghiệm thực tế)

> *Điền vào đây khi kiểm tra với sandbox/production TCBS. Không để trống quá 2 sprint.*

| Ngày | Endpoint | Phát hiện | Người ghi |
|---|---|---|---|
| — | — | — | — |
