# Nghiên Cứu & Đánh Giá API Chứng Khoán Phái Sinh (Futures) Việt Nam
## KBS, Vietcap (VCI), TCBS, và DNSE

**Ngày cập nhật:** 2026-06-21  
**Tác giả:** Antigravity (AI Coding Assistant)  
**Phạm vi nghiên cứu:** Hệ thống API cung cấp dữ liệu thị trường công khai (Publish APIs) và API giao dịch tài khoản cá nhân (Private Trading APIs).

---

## 1. Tổng Quan Về Thị Trường & Bản Chất API Phái Sinh
Giao dịch chứng khoán phái sinh (Hợp đồng tương lai chỉ số VN30 - VN30 Futures) tại Việt Nam yêu cầu tính thời gian thực cao, ký quỹ nghiêm ngặt và quản lý vị thế liên tục. Khi tiếp cận giải pháp API, chúng ta cần phân tách rõ ràng thành hai nhóm:
1. **API Truy vấn dữ liệu công khai (Publish Market Data APIs):** Lấy danh sách hợp đồng phái sinh, giá trực tiếp, độ sâu sổ lệnh (order book), dữ liệu lịch sử (OHLC/nến). Nhóm này không cần tài khoản giao dịch hoặc chỉ cần xác thực cơ bản (Public Token).
2. **API Giao dịch & Dữ liệu tài khoản (Private Trading APIs):** Đặt lệnh, sửa/hủy lệnh, xem vị thế thực tế (Position), quản lý số dư ký quỹ (Cash/Margin). Nhóm này đòi hỏi bảo mật 2 lớp (Mật khẩu/SmartOTP) và phân quyền chặt chẽ.

---

## 2. Giải Pháp API Truy Vấn Dữ Liệu Công Khai (Publish APIs)
Dưới đây là tổng hợp giải pháp lấy thông tin và dữ liệu phái sinh công khai từ các nhà cung cấp (Providers) được xây dựng trong thư viện `vnbroker`:

### 2.1. Lấy danh sách mã phái sinh hiện hành (Futures Contracts)
Hợp đồng phái sinh tại Việt Nam gồm 4 mã tương lai chỉ số VN30 (tháng hiện tại VN30F1M, tháng kế tiếp VN30F2M, và 2 quý kế tiếp VN30F1Q, VN30F2Q).

| Nhà cung cấp (Provider) | Phương thức trong `vnbroker` | Endpoint HTTP thực tế & Cách hoạt động |
| :--- | :--- | :--- |
| **TCBS** | `all_future_indices()` tại [listing.py](file:///c:/Mujoco Projects/vnbrokder/vnbroker/explorer/tcbs/listing.py#L250-L253) | **POST** `https://apiextaws.tcbs.com.vn/ligo/v1/watchlist/preview` <br> Lọc theo body: `{"filters":[{"key":"indexName","value":"FU_INDEX","operator":"="}],"size":5000}`. |
| **DNSE** | `all_future_indices()` tại [listing.py](file:///c:/Mujoco Projects/vnbrokder/vnbroker/explorer/dnse/listing.py#L229-L231) | **GET** `https://openapi.dnse.com.vn/market/instruments` <br> Lọc theo tham số `index_name=all` hoặc filter các công cụ có type là `INDEX` / `FUTURE`. |
| **Vietcap (VCI)** | `all_future_indices()` tại [listing.py](file:///c:/Mujoco Projects/vnbrokder/vnbroker/explorer/vci/listing.py#L304-L306) | **GET** `https://api.vietcap.com.vn/price/symbols/getByGroup?group=FU_INDEX` |
| **KBSV** | `all_future_indices()` tại [listing.py](file:///c:/Mujoco Projects/vnbrokder/vnbroker/explorer/kbs/listing.py#L387-L401) | **GET** `https://kbsec.com.vn/.../stock/search/data` <br> Tải dữ liệu toàn thị trường và lọc các mã thuộc nhóm phái sinh (Internal code: `DER` hoặc group `FU_INDEX`). |

### 2.2. Lấy dữ liệu giá lịch sử (OHLC/Nến) của mã phái sinh
Để vẽ biểu đồ hoặc chạy backtest chiến lược phái sinh, dữ liệu lịch sử nến là vô cùng quan trọng:

*   **TCBS (Giải pháp tốt nhất cho dữ liệu lịch sử miễn phí):**
    *   **Phương thức:** Lớp `Quote` tại [quote.py](file:///c:/Mujoco Projects/vnbrokder/vnbroker/explorer/tcbs/quote.py#L366-L371).
    *   **Endpoint:** `GET https://apiextaws.tcbs.com.vn/futures-insight/v2/stock/bars` (hoặc `bars-long-term` cho khung Daily/Weekly).
    *   **Tham số:** `ticker` (Ví dụ: `VN30F2606`), `resolution` (Khung thời gian: `1`, `5`, `15`, `30`, `60`, `D`), `type="derivative"`, `countBack` (Số lượng nến lấy ngược từ thời điểm hiện tại), `to` (Timestamp giới hạn).
*   **DNSE:**
    *   **Endpoint:** `GET https://openapi.dnse.com.vn/market/ohlc`
    *   **Tham số:** `bar_type="DERIVATIVE"`, `resolution`, `from`, `to`.

---

## 3. Giải Pháp API Giao Dịch & Dữ Liệu Tài Khoản (Private Trading APIs)
Phần này tách biệt các giải pháp giao dịch phái sinh thực tế của các công ty có hỗ trợ: **DNSE** (hỗ trợ toàn diện) và **TCBS** (chỉ hỗ trợ truy xuất thông tin tài khoản phái sinh ở chế độ Read-only).

### 3.1. DNSE — Hỗ Trợ Đặt Lệnh & Quản Lý Vị Thế Toàn Diện
DNSE cung cấp giải pháp Open API chuyên nghiệp nhất hiện tại ở Việt Nam cho phép khách hàng cá nhân đặt lệnh phái sinh tự động qua API.

#### A. Quy trình xác thực (Authentication Flow)
1. **Lấy JWT Token:** Sử dụng Client ID và Client Secret gửi lên hệ thống DNSE để nhận JWT Token sử dụng cho các API tiếp theo.
2. **Tạo Trading Token (SmartOTP):** Để đặt lệnh hoặc đóng vị thế, bắt buộc phải lấy SmartOTP hoặc Email OTP từ người dùng và gọi:
   * Phương thức `create_trading_token()` để nhận `trading-token`. Token này sẽ được đính kèm vào header `trading-token` của mỗi request đặt/sửa/hủy lệnh.

#### B. Các Endpoint Giao Dịch Phái Sinh
Các endpoint này được triển khai tại [order_service.py](file:///c:/Mujoco Projects/vnbrokder/vnbroker/connector/dnse/services/order_service.py) và [position_service.py](file:///c:/Mujoco Projects/vnbrokder/vnbroker/connector/dnse/services/position_service.py):

*   **Đặt lệnh phái sinh mới (POST):**
    *   **Endpoint:** `POST https://openapi.dnse.com.vn/accounts/orders?marketType=DERIVATIVE`
    *   **Headers:** `Authorization: Bearer <JWT>`, `trading-token: <TradingToken>`
    *   **Payload tiêu biểu:**
        ```json
        {
          "accountNo": "058C123456",
          "symbol": "VN30F2606",
          "side": "BUY",        // hoặc SELL
          "priceType": "LIMIT", // LIMIT, ATO, ATC, MTL, MOK, MAK
          "price": 1250.5,
          "quantity": 1
        }
        ```
*   **Hủy lệnh (DELETE):**
    *   **Endpoint:** `DELETE /accounts/{accountNo}/orders/{orderId}?marketType=DERIVATIVE`
*   **Sửa lệnh (PATCH):**
    *   **Endpoint:** `PATCH /accounts/{accountNo}/orders/{orderId}?marketType=DERIVATIVE`
*   **Truy vấn Vị thế phái sinh hiện tại (Positions):**
    *   **Endpoint:** `GET /accounts/{accountNo}/positions?marketType=DERIVATIVE`
    *   **Trả về:** Danh sách các vị thế đang mở (Symbol, Side: LONG/SHORT, Giá trung bình mở vị thế `openPrice`, Giá thị trường hiện tại `marketPrice`, Lãi lỗ tạm tính `unrealizedPnl`).
*   **Đóng vị thế nhanh (Close Position):**
    *   **Endpoint:** `POST /accounts/positions/{positionId}/close?marketType=DERIVATIVE`

---

### 3.2. TCBS — Giải Pháp Truy Vấn Vị Thế & Ký Quỹ (Read-only)
TCBS **không** có Open API chính thức hỗ trợ đặt lệnh phái sinh cho khách hàng cá nhân. Hệ thống chỉ cho phép truy vấn dữ liệu tài khoản phái sinh thông qua các endpoint nội bộ của nền tảng iFuture (được triển khai tại [derivatives.py](file:///c:/Mujoco Projects/vnbrokder/vnbroker/broker/tcbs/derivatives.py)):

#### A. Lưu Ý Đặc Biệt Về Tài Khoản TCBS Phái Sinh
> [!IMPORTANT]
> Khác với tài khoản cơ sở sử dụng `accountNo` (gồm 6 hoặc 10 chữ số), API phái sinh của TCBS bắt buộc sử dụng **Mã lưu ký (Custody Code)** làm `accountId` (định dạng `105Cxxxxxx`). Ví dụ: `105C334455`.

#### B. Quy trình xác thực
Khách hàng khởi tạo kết nối thông qua việc gửi API Key và mã OTP tại endpoint `/gaia/v1/oauth2/openapi/token` để nhận Bearer Token (JWT). Token này có giá trị khoảng 8 giờ.

#### C. Các API Truy Vấn Tiền & Vị Thế Phái Sinh
*   **Lấy danh sách vị thế đang nắm giữ (Positions):**
    *   **Method & URL:** `GET https://openapi.tcbs.com.vn/khronos/v1/account/portfolio/status?accountId={105C...}&subAccountId={tiểu_khoản}`
    *   **Hàm trong SDK:** `get_positions(account_id, ...)`
    *   **Dữ liệu trả về:** Mã chứng khoán, Side (LONG/SHORT), Số lượng vị thế mở (`openQtty`), Giá mở cửa (`openPrice`), Giá thị trường (`marketPrice`), Lãi lỗ chưa thực hiện (`unrealizedPnl`), Ký quỹ yêu cầu (`margin`).
*   **Lấy danh sách lệnh trong ngày (Orders):**
    *   **Method & URL:** `GET https://openapi.tcbs.com.vn/khronos/v1/order/in-day?accountId={105C...}&symbol={mã_cp}&pageNo=0&pageSize=50`
    *   **Hàm trong SDK:** `get_orders(account_id, ...)`
    *   **Dữ liệu trả về:** Mã lệnh, Trạng thái (đã khớp, chờ khớp, đã hủy), Giá đặt, Số lượng khớp, v.v.
*   **Lấy số dư tài sản và Ký quỹ (Cash & Margin):**
    *   **Method & URL:** `GET https://openapi.tcbs.com.vn/khronos/v1/account/status?accountId={105C...}`
    *   **Hàm trong SDK:** `get_cash(account_id, ...)`
    *   **Dữ liệu trả về:** Số dư tiền (`balance`), Tiền khả dụng rút/nộp ký quỹ (`availableBalance`), Giá trị ký quỹ tại VSD (`margin`), NAV tài khoản phái sinh.

---

## 4. Bảng So Sánh & Đánh Giá Tổng Hợp

| Tiêu chí so sánh | DNSE | TCBS | Vietcap (VCI) | KBSV |
| :--- | :--- | :--- | :--- | :--- |
| **API Market Data Phái sinh** | Hỗ trợ đầy đủ qua OpenAPI | Hỗ trợ đầy đủ qua `/futures-insight` | Có hỗ trợ lấy danh sách mã | Có hỗ trợ cơ bản |
| **API Đặt lệnh Phái sinh** | **Có hỗ trợ chính thức** | Không hỗ trợ chính thức | Không hỗ trợ | Không hỗ trợ |
| **Mức độ an toàn pháp lý** | Cực kỳ an toàn (Open API công khai) | Trung bình (Sử dụng API nội bộ qua Token) | Không khả dụng | Không khả dụng |
| **Xác thực bảo mật khi đặt lệnh** | Token + SmartOTP | JWT Token | Không hỗ trợ | Không hỗ trợ |
| **Chế độ hỗ trợ trong SDK** | Đầy đủ Đặt lệnh & Truy vấn | Chỉ đọc (Read-only) dữ liệu tài sản | Chỉ đọc dữ liệu thị trường | Chỉ đọc dữ liệu thị trường |
| **Tài liệu kỹ thuật (Docs)** | Có tài liệu lập trình viên chính thức | Không công khai tài liệu phái sinh | Không có tài liệu lập trình viên | Không có tài liệu lập trình viên |

---

## 5. Khuyến Nghị Hướng Nghiên Cứu
1. **Nếu mục tiêu là tự động hóa đặt lệnh (Trade Bot):**
   * Ưu tiên tích hợp trực tiếp với **DNSE** thông qua lớp kết nối đã viết trong [trade.py](file:///c:/Mujoco Projects/vnbrokder/vnbroker/connector/dnse/trade.py).
   * Chú ý thiết lập xử lý ngoại lệ cho `trading-token` hết hạn và cơ chế nhập mã SmartOTP tự động/bán tự động khi khởi chạy phiên giao dịch.
2. **Nếu mục tiêu là giám sát tài sản đa tài khoản (Screener / Portfolio Tracker):**
   * Tận dụng giải pháp **TCBS read-only** trong [derivatives.py](file:///c:/Mujoco Projects/vnbrokder/vnbroker/broker/tcbs/derivatives.py). Mặc dù không đặt được lệnh nhưng đây là kênh theo dõi vị thế phái sinh từ hệ sinh thái iFuture của TCBS rất chi tiết.
   * Cần có cơ chế refresh JWT Token định kỳ (sau 6-8 tiếng) để tránh lỗi gián đoạn phiên kết nối.
3. **Quản lý rủi ro:**
   * Vì đặc thù đòn bẩy phái sinh Việt Nam rất cao (ký quỹ khoảng 13-17% tùy thời điểm), hệ thống đặt lệnh tự động cần tích hợp cơ chế ngắt mạch tự động (Circuit Breaker) nếu tỷ lệ ký quỹ tài khoản giảm xuống dưới ngưỡng an toàn (ví dụ: < 80% tỷ lệ khuyến nghị của VSD).
