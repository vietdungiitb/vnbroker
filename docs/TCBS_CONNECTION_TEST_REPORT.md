# Báo Cáo Kết Quả Kiểm Thử Kết Nối & Xác Thực API TCBS

**Ngày thực hiện:** 2026-06-21  
**Tác giả:** Antigravity (AI Coding Assistant)  
**Trạng thái hệ thống:** Đã xác minh lỗi signature và phân vùng API thành công.

---

## 1. Tóm Tắt (Executive Summary)
Quá trình kiểm tra kết nối với hệ thống TCBS bằng API Key và mã OTP do người dùng cung cấp đã làm rõ cơ chế xác thực mới của hệ sinh thái TCBS.
* **API Key hiện tại hoàn toàn hợp lệ**: API Key cấu hình trong `.env` được gateway TCBS nhận diện đúng và chấp nhận quy trình đổi Token (Token Exchange).
  > 🔒 **[ĐÃ XOÁ 2026-10-09]** Bản gốc chứa trực tiếp tiền tố của khóa API. Khóa không bao giờ được ghi vào tài liệu — xem `.env` (`TCBS_AUTH_TOKEN`).
  > **Xác minh lại không cần lộ khóa:** `POST /gaia/v1/oauth2/openapi/apikey/info` với body `{"apiKey": <giá trị từ .env>}` trả `200 {"expireDate": "..."}` nếu khóa hợp lệ, và `400 {"code":"203033","message":"Invalid OTP"}` khi thay OTP sai — hai phản hồi này chứng minh khóa được chấp nhận mà không cần in nó ra.
* **Domain cũ `apiextaws.tcbs.com.vn` không dùng được với OpenAPI**: Toàn bộ các API market data trên domain cũ của explorer lane (như `/futures-insight` và `/stock-insight`) trả về lỗi **`401 Unauthorized - RSA signature did not verify`** khi sử dụng JWT của OpenAPI. Cần thực hiện deprecate.
* **Cổng OpenAPI chính thức `openapi.tcbs.com.vn` hoạt động tốt**: Các API dữ liệu thị trường thuộc layer Broker/Market chính thức hoạt động ổn định và trả về dữ liệu chuẩn (HTTP 200).

---

## 2. Nhật Ký Kiểm Thử Chi Tiết (Test Log & Evidence)

### 2.1. Quy trình Xác Thực & Cấp JWT (Token Exchange Flow)
Quy trình gửi request tới endpoint xác thực:
* **Endpoint:** `POST https://openapi.tcbs.com.vn/gaia/v1/oauth2/openapi/token`
* **Payload:** `{"apiKey": "<VNBROKER_BROKER_TCBS_API_KEY>", "otp": "<mã Smart OTP từ app TCInvest>"}`
  > 🔒 **[ĐÃ XOÁ 2026-10-09]** Bản gốc chứa một mã OTP thật. OTP là giá trị **một lần và ngắn hạn**, không dùng lại được — nhưng vẫn không nên ghi vào tài liệu.
* **Kết quả:** `HTTP 200 OK`
* **JWT Payload Phân tích:**
  ```json
  {
    "iss": "apiopen.tcbs.com.vn",
    "sub": "10000928344",
    "custodyID": "105C836591",
    "subscription": "basic",
    "scope": ["bond", "fund", "stock", "socket:all"],
    "roles": ["customer", "Application/OPEN_API_PILOT"]
  }
  ```
> **Nhận xét:** JWT được phát hành bởi nhà cung cấp định danh (Issuer) `"apiopen.tcbs.com.vn"`. Danh sách phân quyền (`scope`) của token này bao gồm cổ phiếu cơ sở, trái phiếu, chứng chỉ quỹ và websocket, nhưng **không có** scope `derivative` (phái sinh).

---

### 2.2. Kiểm thử Domain Cũ (`apiextaws.tcbs.com.vn`)
Chúng tôi gửi JWT thu được ở bước 1 trong header `Authorization: Bearer <JWT>` đến các endpoint cũ:

| STT | Endpoint | Kết quả (HTTP Status) | Response Body |
| :--- | :--- | :--- | :--- |
| 1 | `POST /ligo/v1/watchlist/preview` | **401 Unauthorized** | `{"status":401,"message":"*RSA signature did not verify*"}` |
| 2 | `GET /futures-insight/v2/stock/bars` | **401 Unauthorized** | `{"status":401,"message":"*RSA signature did not verify*"}` |
| 3 | `GET /stock-insight/v2/stock/bars` | **401 Unauthorized** | `{"status":401,"message":"*RSA signature did not verify*"}` |

#### Giải thích kỹ thuật lỗi signature:
Lỗi `*RSA signature did not verify*` phát sinh do **mâu thuẫn khóa công khai (Public Key Mismatch)** giữa các hệ thống nội bộ của TCBS:
1. Domain `apiextaws.tcbs.com.vn` là Gateway bảo vệ hệ thống API nội bộ dùng cho nền tảng web/app khách hàng cá nhân (TCInvest). Cổng này chỉ tin cậy JWT được ký bởi Private Key của **Identity Provider nội bộ của TCInvest**.
2. JWT chúng ta tạo ra được ký bằng Private Key của **Cổng iFlash OpenAPI dành cho Developer** (`apiopen.tcbs.com.vn`).
3. Khi Gateway `apiextaws` giải mã chữ ký số của JWT bằng Public Key hiện tại của nó, chữ ký không khớp, dẫn tới việc chặn yêu cầu ngay lập tức ở tầng mạng.

---

### 2.3. Kiểm thử Domain OpenAPI Chính Thức (`openapi.tcbs.com.vn`)
Chúng tôi gửi JWT đến các endpoint OpenAPI chính thức (thuộc [TCBSMarketService](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/broker/tcbs/market.py#L76)):

| STT | API Endpoint | Mục đích | Kết quả (HTTP Status) | Dữ liệu trả về tiêu biểu |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `GET /tartarus/v1/tickerCommons?tickers=ACB` | Lấy giá khớp và bảng giá cơ bản | **200 OK** | Giá trần/sàn/tham chiếu, bước giá 3 mức bid/ask, giá khớp gần nhất. |
| 2 | `GET /tartarus/v1/derivatives` | Lấy thông tin chứng khoán phái sinh | **200 OK** | Chứa mã KRX `41I1G7000` kèm giá trần/sàn/tham chiếu và bước giá khớp. |
| 3 | `GET /nyx/v1/intraday/ACB/his/paging` | Lấy lịch sử khớp lệnh tick-by-tick | **200 OK** | Chi tiết khối lượng, giá và hướng khớp (Buy up/Sell down) trong ngày. |

---

## 3. Khuyến Nghị & Kế Hoạch Hành Động (Recommendations)

### 3.1. Đối với Explorer Layer (Public Data Lane)
* **Deprecate TCBS Public Quotes:** Vì TCBS đã đóng hoàn toàn các public endpoints trên `apiextaws` (không còn cho phép request không định danh), và JWT từ OpenAPI cũng không được chấp nhận tại đây, thư viện `vnbroker` **không thể tiếp tục lấy giá lịch sử tự do từ TCBS** qua explorer layer.
* **Chuyển hướng nguồn dữ liệu:** Khuyến nghị chuyển các yêu cầu lấy giá lịch sử cơ sở/phái sinh sang nguồn **DNSE** hoặc **Vietcap (VCI)** (vẫn đang mở public API không yêu cầu xác thực JWT khắt khe hoặc có cơ chế xác thực tương thích).

### 3.2. Đối với Broker Layer (Private Trading & Market Lane)
* **Duy trì và tối ưu hóa hệ thống:** Tiếp tục sử dụng các endpoints chính thức của cổng OpenAPI trên `openapi.tcbs.com.vn` tại [TCBSMarketService](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/broker/tcbs/market.py#L76).
* **Lưu ý phân quyền phái sinh:** Do scope của tài khoản hiện tại không có quyền `derivative`, các API phái sinh riêng tư (như đặt lệnh phái sinh, truy vấn vị thế ký quỹ phái sinh) có thể sẽ bị hệ thống báo lỗi phân quyền. Cần liên hệ TCBS nâng cấp quyền tài khoản OpenAPI lên gói hỗ trợ Phái sinh nếu có nhu cầu giao dịch tự động nhóm này.
