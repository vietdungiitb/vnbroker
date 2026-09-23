# Kế Hoạch Nghiên Cứu & Thiết Kế Tích Hợp Dữ Liệu Phái Sinh Công Khai (Publish APIs) Trong vnbroker

Báo cáo này đề xuất phương án và giải pháp kiến trúc để tích hợp thông tin và dữ liệu thị trường phái sinh (Futures) công khai trên cả 4 providers (**TCBS, DNSE, Vietcap/VCI, KBSV**) theo đúng kiến trúc của thư viện `vnbroker`.

---

## 1. Tóm Tắt Khởi Động (Executive Summary)
Thư viện `vnbroker` được thiết kế tách biệt rõ ràng giữa hai làn (lanes):
*   **Explorer Lane (`vnbroker/explorer/`):** Thu thập dữ liệu công khai (listing, lịch sử giá OHLC, tin tức, screener) không yêu cầu tài khoản giao dịch của khách hàng hoặc sử dụng các API công khai của các công ty chứng khoán.
*   **Broker/Connector Lane (`vnbroker/broker/` và `vnbroker/connector/`):** Tương tác tài khoản riêng tư (đặt lệnh, quản lý số dư ký quỹ, theo dõi vị thế thực tế) yêu cầu định danh bảo mật cao.

Để hỗ trợ đầy đủ và đồng bộ dữ liệu phái sinh công khai cho cả 4 providers, chúng ta cần hoàn thiện các module `Listing` (để lấy danh sách hợp đồng VN30F) và `Quote` (để lấy dữ liệu lịch sử OHLC/nến) trên từng provider. Đồng thời, giải quyết thách thức chuyển đổi định dạng ký hiệu mã giao dịch (mã cũ VN30F2506 vs mã KRX mới 41I1F7000) vừa được áp dụng tại thị trường Việt Nam từ tháng 5/2025.

---

## 2. Phân Tích Kiến Trúc Hiện Tại Của vnbroker Explorer
Kiến trúc Explorer của `vnbroker` sử dụng cơ chế đăng ký động (`ProviderRegistry`) và bộ chuyển đổi trung gian (`BaseAdapter`) để định tuyến các cuộc gọi từ API lớp ngoài đến các provider tương ứng:

1.  **Lớp API ngoài (`vnbroker/api/`):** 
    *   [vnbroker/api/listing.py](file:///c:/Mujoco Projects/vnbrokder/vnbroker/api/listing.py) cung cấp interface `all_future_indices()`.
    *   [vnbroker/api/quote.py](file:///c:/Mujoco Projects/vnbrokder/vnbroker/api/quote.py) cung cấp interface `history()` và `intraday()`.
2.  **Lớp Base Adapter (`vnbroker/base.py`):**
    *   Định tuyến và ủy quyền cuộc gọi thông qua decorator `@dynamic_method` dựa trên provider được chỉ định (`vci`, `kbs`, `tcbs`, `dnse`).
3.  **Lớp Parser & Tiện ích (`vnbroker/core/utils/parser.py`):**
    *   Hàm `get_asset_type(symbol)` phân tích định dạng ký hiệu mã để phân loại là `derivative`, `stock`, hoặc `index`.
    *   Hàm `convert_derivative_symbol(symbol)` chuyển đổi mã phái sinh cũ sang định dạng KRX mới (được áp dụng từ tháng 5/2025 theo cấu trúc: `41` + tài sản cơ sở + mã năm + mã tháng + `000`).

---

## 3. Khảo Sát & Giải Pháp Cho Từng Provider (Publish APIs)

### 3.1. Provider: TCBS
*   **Danh sách hợp đồng phái sinh (Listing):**
    *   *Hiện trạng:* Đã hỗ trợ tốt qua `symbols_by_group(group="FU_INDEX")`. Gọi API watchlist preview của TCBS (`/ligo/v1/watchlist/preview`).
    *   *Giải pháp:* Duy trì ổn định.
*   **Dữ liệu lịch sử giá OHLC (Quote):**
    *   *Hiện trạng:* Đã hỗ trợ lấy nến phái sinh qua `futures-insight` service.
    *   *Giải pháp:* Đảm bảo kiểm tra tính tương thích khi truyền mã KRX mới. Endpoint `GET https://apiextaws.tcbs.com.vn/futures-insight/v2/stock/bars` cần kiểm tra xem TCBS yêu cầu mã cũ hay mã KRX mới để tự động gọi `convert_derivative_symbol` nếu cần thiết.

### 3.2. Provider: DNSE
*   **Danh sách hợp đồng phái sinh (Listing):**
    *   *Hiện trạng:* Hàm `all_future_indices()` đang bị fallback về `indices()` (lấy toàn bộ index rồi lọc loại INDEX), chưa lấy được chính xác danh sách hợp đồng tương lai phái sinh (Futures).
    *   *Giải pháp:* Nâng cấp hàm `all_future_indices()` bằng cách gọi API `/market/instruments` với tham số `security_group_id="DER"` hoặc `market_id="DERIVATIVE"` để lọc riêng danh mục sản phẩm phái sinh từ cổng OpenAPI của DNSE.
*   **Dữ liệu lịch sử giá OHLC (Quote):**
    *   *Hiện trạng:* Trong file [quote.py](file:///c:/Mujoco Projects/vnbrokder/vnbroker/explorer/dnse/quote.py#L302), thuộc tính `"type": "STOCK"` đang bị fix cứng trong query gửi lên `/price/ohlc`. Khi người dùng truyền vào mã phái sinh, API vẫn gửi `type="STOCK"` dẫn đến lỗi hoặc không có dữ liệu.
    *   *Giải pháp:* Tích hợp hàm `get_asset_type(symbol)` vào `DNSEQuote.history()`. Nếu `asset_type == 'derivative'`, tự động chuyển đổi giá trị `"type"` trong query thành `"DERIVATIVE"`.

### 3.3. Provider: Vietcap (VCI)
*   **Danh sách hợp đồng phái sinh (Listing):**
    *   *Hiện trạng:* Đã hỗ trợ qua `symbols_by_group(group="FU_INDEX")` bằng cách gọi API `/price/symbols/getByGroup?group=FU_INDEX`.
    *   *Giải pháp:* Giữ nguyên kiến trúc hiện tại vì VCI trả về danh sách mã tương đối chính xác.
*   **Dữ liệu lịch sử giá OHLC (Quote):**
    *   *Hiện trạng:* Hàm `history()` của VCI sử dụng `get_asset_type(symbol)` để quyết định payload gửi đi.
    *   *Giải pháp:* Cần xác nhận VCI đã hoàn tất việc hỗ trợ hệ thống KRX mới. Cần tích hợp cơ chế tự động chuyển đổi symbol (nếu hệ thống VCI yêu cầu mã mới) hoặc fallback linh hoạt.

### 3.4. Provider: KBSV (KBS)
*   **Danh sách hợp đồng phái sinh (Listing):**
    *   *Hiện trạng:* Lấy từ danh mục toàn bộ cổ phiếu và lọc theo loại phái sinh (KBS internal code `DER`).
    *   *Giải pháp:* Phương án này hoạt động tốt và phản ánh đúng thiết kế crawler của KBS.
*   **Dữ liệu lịch sử giá OHLC (Quote):**
    *   *Hiện trạng:* KBS là provider duy nhất hiện tại trong explorer chủ động chuyển đổi ký hiệu mã phái sinh cũ sang định dạng KRX mới bằng cách gọi `convert_derivative_symbol(self.symbol)` ngay tại phương thức khởi tạo của lớp `Quote`.
    *   *Giải pháp:* Giữ nguyên và áp dụng mẫu thiết kế (design pattern) này làm tiêu chuẩn cho các explorer providers khác nếu hệ thống KRX mới trở thành bắt buộc ở các API công khai của TCBS và DNSE.

---

## 4. Đề Xuất Giải Pháp Kiến Trúc Đồng Bộ (Unified Architecture)

### 4.1. Chuẩn Hóa Xác Định & Chuyển Đổi Ký Hiệu Mã Giao Dịch
*   Tất cả các provider trong Explorer Lane khi nhận được mã phái sinh dạng cũ (ví dụ: `VN30F2606`) cần có chung cơ chế kiểm tra tính tương thích của API Upstream (phía công ty chứng khoán):
    *   Nếu API Upstream chỉ hỗ trợ mã KRX mới: Sử dụng `convert_derivative_symbol()` để chuyển đổi trước khi gọi API.
    *   Nếu API Upstream vẫn duy trì mã cũ: Giữ nguyên mã người dùng truyền vào.
*   Cơ chế này sẽ được thực hiện thống nhất tại hàm khởi tạo `__init__` của từng lớp `Quote` và `Listing` của các provider.

### 4.2. Cải Tiến Điểm Cuối (Endpoints) Lọc Phái Sinh Trong Listing
*   Để cung cấp hàm `all_future_indices()` trả về dữ liệu đồng nhất (DataFrame/Series chứa mã hợp đồng, tên hợp đồng, ngày đáo hạn), cấu trúc dữ liệu trả về từ 4 providers cần được chuẩn hóa (Normalize Schema) tại Adapter ngoài:
    *   Cột bắt buộc: `symbol` (Mã hợp đồng phái sinh).
    *   Cột tùy chọn bổ sung: `organ_name` (Tên hợp đồng), `exchange` (Sàn niêm yết - mặc định HNX đối với phái sinh tại Việt Nam).

### 4.3. Đồng Bộ Hóa Tham Số Truy Vấn Lịch Sử OHLC
*   Tham số `type` trong API lịch sử nến của DNSE và TCBS phải được chuyển đổi động dựa trên `get_asset_type(symbol)` chứ không được fix cứng là `"STOCK"` hoặc `"derivative"`.
*   Trường hợp tham số resolution/interval không đồng nhất giữa các bên:
    *   Tận dụng bảng ánh xạ `_INTERVAL_MAP` có sẵn trong mỗi provider để chuyển các khung thời gian chuẩn (`1m`, `5m`, `15m`, `30m`, `1H`, `1D`) sang định dạng mà API tương ứng yêu cầu.

---

## 5. Kế Hoạch Triển Khai Chi Tiết (Không Code)
1.  **Bước 1: Khảo sát chi tiết API Upstream (Smoke Tests):**
    *   Gửi request nháp (dry-run hoặc postman) đến các endpoint công khai của 4 bên để ghi nhận định dạng mã phái sinh (mã cũ hay mã KRX mới) mà họ đang chấp nhận đối với dữ liệu lịch sử và danh mục.
2.  **Bước 2: Cập nhật Lớp Explorer của DNSE:**
    *   Cấu trúc lại phương thức `history` của lớp `DNSEQuote` để chuyển đổi động tham số `type` trong request payload dựa trên giá trị trả về của `get_asset_type()`.
    *   Sửa lỗi `all_future_indices()` trong `DNSEListing` để truyền đúng tham số lọc phái sinh lên API `/market/instruments` thay vì dùng fallback lấy chỉ số chung.
3.  **Bước 3: Cập nhật Lớp Explorer của TCBS:**
    *   Đồng bộ hóa kiểm tra `asset_type` cho dữ liệu lịch sử phái sinh tại `Quote.history` để hỗ trợ linh hoạt cả hai định dạng mã cũ/mới của KRX.
4.  **Bước 4: Kiểm Thử Đồng Bộ (Verification & Benchmarking):**
    *   Chạy các test case kiểm tra việc lấy danh sách mã phái sinh từ cả 4 providers.
    *   Chạy benchmark đo độ trễ và tỷ lệ lỗi khi lấy lịch sử giá (OHLC) của hợp đồng phái sinh tháng hiện tại (F1M) trên cả 4 providers để đánh giá mức độ ổn định của từng nguồn dữ liệu.
