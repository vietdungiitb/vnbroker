# Báo cáo Rà soát Toàn diện Hệ thống & Kiến trúc vnbroker

Tài liệu này cung cấp một cái nhìn tổng quan, phân tích chuyên sâu về kiến trúc và các cơ chế vận hành nội tại của thư viện Python **vnbroker**.

---

## 1. Tổng quan Thư viện (Package Overview)

`vnbroker` là một thư viện Python cung cấp một lớp truy cập dữ liệu (data access layer) thống nhất để lấy dữ liệu chứng khoán, ngoại hối, tiền điện tử, chỉ số thế giới và quỹ đầu tư tại Việt Nam. Thư viện tự động chuẩn hóa đầu ra dưới dạng `pandas.DataFrame` giúp giảm chi phí tích hợp cho các hệ thống phân tích, dashboard và bot giao dịch.

### 1.1. Các Thành phần Chính

| Thành phần | Mục đích |
| --- | --- |
| `Vnbroker` | Client cấp cao nhất, điều phối toàn bộ luồng dữ liệu của stock, FX, crypto, world index và quỹ. |
| `Quote` | Cung cấp dữ liệu giá lịch sử (OHLCV), intraday khớp lệnh từng lô và độ sâu sổ lệnh (price depth). |
| `Company` | Hồ sơ doanh nghiệp, ban lãnh đạo, giao dịch nội bộ, tỷ lệ sở hữu. |
| `Finance` | Bảng cân đối kế toán, kết quả kinh doanh, lưu chuyển tiền tệ và các chỉ số tài chính (ratios). |
| `Listing` | Danh sách mã cổ phiếu niêm yết, phân nhóm chỉ số (VN30, HNX30), nhóm ngành. |
| `Trading` | Dữ liệu giao dịch trực tiếp và bảng giá (market board). |
| `Screener` | Bộ lọc cổ phiếu (hiện hỗ trợ nguồn dữ liệu TCBS). |
| `News` | Tin tức chuẩn hóa thu thập từ các nguồn báo chí (Cafef, Vneconomy, v.v.). |
| `MarketSnapshot` | Snapshot thị trường phục vụ vẽ bản đồ nhiệt (heatmap) và thống kê nhanh ngành. |
| `Fund` | Tra cứu thông tin chứng chỉ quỹ từ cổng FMarket. |
| `Messenger` | Gửi cảnh báo/thông báo đến Slack, Telegram, Discord, Lark. |

### 1.2. Các Nguồn Dữ liệu Hỗ trợ (Data Providers)
Thư viện quản lý kết nối đến cả các nguồn dữ liệu mở (scraping) và các kết nối API chính thức:
*   **Nhóm Chứng khoán Việt Nam:** TCBS, DNSE, KBS, VCI.
*   **Nhóm Ngoại hối & Quốc tế:** MSN, FMP (Financial Modeling Prep), Binance.
*   **Nhóm Quỹ & Tin tức:** FMarket, RSS Cafef, RSS Vneconomy.

---

## 2. Phân tích Sâu Kiến trúc & Cơ chế của vnbroker (Python Internals)

Thư viện sở hữu thiết kế module động, xử lý tối ưu các vấn đề về độ trễ, giới hạn băng thông (rate limit) và tính nhất quán dữ liệu thông qua 5 cơ chế cốt lõi:

### 2.1. Cơ chế Tải chậm Tránh Deadlock (Lazy Load Pattern)
Trong file `vnbroker/__init__.py`, để ngăn chặn hiện tượng **circular import deadlock** (bế tắc nhập vòng) khi các module con gọi chéo nhau lúc khởi động package:
*   Biến toàn cục `_vnbroker` ban đầu được gán `None`.
*   Phương thức proxy `__new__` trên class `Vnbroker` chỉ gọi hàm nạp thực tế `from vnbroker.common.client import Vnbroker` tại lần khởi tạo thực tế đầu tiên.
*   Hàm `_ensure_explorer_modules_loaded()` chịu trách nhiệm import các adapter nguồn (`dnse`, `tcbs`, `kbs`, v.v.) một cách an toàn và chỉ thực hiện một lần duy nhất khi cần thiết.

### 2.2. Bộ đăng ký Nhà cung cấp động (Provider Registry Pattern)
Mọi adapter nguồn (ví dụ: `VCIQuote`, `KBSQuote`, `TCBSQuote`) không được khởi tạo thủ công bằng hardcode mà đăng ký thông qua lớp `ProviderRegistry` (`vnbroker/core/registry.py`):
*   Khi import module, các adapter sẽ tự động đăng ký vào registry:
    ```python
    ProviderRegistry.register('quote', 'vci', Quote)
    ```
*   Tất cả các adapter lớp trên kế thừa từ `BaseAdapter` (`vnbroker/base.py`). Lớp này sử dụng **reflection** (`inspect.signature`) để phân tích constructor của từng adapter thực tế nhằm lọc sạch các tham số dư thừa, tránh lỗi Runtime khi cấu hình thay đổi.
*   Bộ decorator `@dynamic_method` tự động định tuyến phương thức đến provider tương ứng và kiểm soát tham số đầu vào.

### 2.3. Định tuyến Nguồn & Phục hồi lỗi (Adaptive Sourcing & Failover)
Khi cấu hình nguồn dữ liệu là `source="AUTO"`, bộ định tuyến `source_router.py` sẽ tự động quản lý:
1.  **Phân bổ tải sharding (Load Balancing):**
    *   Đối với các truy vấn chứa Symbol cụ thể (ví dụ: `ACB`), hệ thống sử dụng thuật toán băm md5 để phân phối mã ổn định đến một nguồn chính (`_stable_index(f"{module_name}:{symbol}", pool)`), giúp tăng hiệu quả lưu bộ nhớ đệm (caching).
    *   Đối với truy vấn chung, hệ thống xoay vòng (Round Robin) bằng bộ đếm luồng an toàn.
2.  **Thời gian Cooldown phục hồi lỗi (Exponential Backoff):**
    *   Khi một nguồn dữ liệu phát sinh lỗi (lỗi kết nối, timeout, mã lỗi HTTP 429/403), hệ thống gọi `record_failure` để đưa nguồn đó vào trạng thái cooldown (tạm ngưng sử dụng).
    *   Thời gian ngưng tăng dần theo cấp số nhân: \( \min(90.0, 5.0 \times 2^{\text{failures} - 1}) \) giây để bảo vệ tài nguyên hệ thống và giảm tải cho máy chủ đối tác.

### 2.4. Kiểm soát Luồng và Cầu chì Toàn cục (Adaptive Concurrency & Backpressure)
Thư viện cung cấp thuật toán kiểm soát dòng tải tự động nhằm tối ưu hóa thông lượng:
*   **AdaptiveController (`vnbroker/core/adaptive_controller.py`):** Hoạt động theo mô hình AIMD (Additive Increase Multiplicative Decrease). Nếu số lượng lỗi trong batch vượt ngưỡng hoặc độ trễ P95 chạm ngưỡng trần (`p95_high_seconds`), số luồng worker lập tức giảm đi `step_down` (mặc định giảm 3). Khi chạy ổn định hoàn hảo, số luồng sẽ nhích dần lên `step_up` (+1 luồng).
*   **GlobalPressure (Cầu chì toàn cục):** Lớp singleton giám sát trạng thái chịu tải của toàn bộ tiến trình. Nếu tỷ lệ lỗi trung bình vượt quá **30%**, hệ thống chuyển sang trạng thái stress và **giảm một nửa (halving)** năng lực xử lý luồng song song của tất cả các provider. Hệ thống tự phục hồi sau 3 chu kỳ sạch liên tiếp (tỷ lệ lỗi dưới 30%).

### 2.5. Quy ước Chuẩn hóa Đơn vị Giá (Price Unit Standardization)
Chứng khoán Việt Nam có đơn vị giá hiển thị trên bảng điện tử lệch 1.000 lần so với VND tuyệt đối. Để đồng bộ dữ liệu đa nguồn:
*   Mặc định hệ thống trả về giá tuyệt đối theo **VND**.
*   Có chế độ tương thích ngược trả về **Nghìn VND** khi đặt biến môi trường:
    ```powershell
    $env:vnbroker_PRICE_UNIT = "THOUSAND_VND"
    ```
*   Mỗi DataFrame trả về luôn mang siêu dữ liệu (metadata) `df.attrs['price_unit']` lưu trữ thông tin đơn vị giá để các lớp dữ liệu phía sau dễ dàng kiểm chứng (assert).

---

## 3. Quy định Quản trị & Chuẩn Chất lượng (Governance & Quality Standards)

1.  **Duy trì price_unit đồng nhất:**
    *   Mọi adapter khi trả về DataFrame bắt buộc phải gán nhãn đơn vị giá thông qua thuộc tính `.attrs['price_unit']` để tránh việc sai lệch dữ liệu hệ số 1000 lần.
2.  **Nguyên tắc Failover an toàn:**
    *   Chỉ các nhà cung cấp dữ liệu công khai (Open Sourced) không yêu cầu khóa bí mật/token cá nhân mới được đưa vào danh sách ứng viên của cơ chế `AUTO` nguồn.
3.  **Tối ưu hóa tài nguyên:**
    *   Sau khi thực hiện các hoạt động thu thập song song, bắt buộc phải giải phóng bộ nhớ đệm và dọn dẹp tiến trình con để tránh rò rỉ bộ nhớ (memory leaks).
