# Kế Hoạch Triển Khai Phương Án B: Hard Cut-off Kết Nối Trực Tiếp

**Ngày:** 15/06/2026  
**Dự án:** VNBroker (c:\Mujoco Projects\vnbrokder)  
**Mục tiêu:** Loại bỏ hoàn toàn Direct Mode của các module dữ liệu thị trường (Quote, Company, Finance...) để giảm thiểu tối đa chi phí bảo trì (maintenance cost).

---

## 1. Các Thay Đổi Mã Nguồn Đề Xuất (Proposed Changes)

### 1.1 Khóa cứng chế độ Gateway trong `vnbroker` Core

Cần cập nhật mã nguồn để loại bỏ hoàn toàn khả năng khởi tạo các adapter kết nối trực tiếp, hướng toàn bộ luồng đọc dữ liệu thị trường qua Gateway.

#### [MODIFY] [data.py](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/common/data.py)
*   Trong lớp `StockComponents`, `Quote`, `Company`, `Listing`, `Trading`, `News`, `Finance`:
    *   Hạn chế biến `SUPPORTED_SOURCES` về chỉ còn `["GATEWAY", "AUTO"]`.
    *   Xóa bỏ logic kiểm tra nguồn trực tiếp thô trong phương thức `_load_data_source()` (ví dụ: các điều kiện `if self.source == "DNSE": ...`).
    *   Gán cứng cấu hình sử dụng Gateway: `self._use_gateway = True`.

#### [MODIFY] [client.py](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/common/client.py)
*   Cập nhật `SUPPORTED_SOURCES` thành `["GATEWAY", "AUTO"]`.
*   Sửa đổi phương thức `.stock()` để luôn chuyển tiếp về `StockComponents` chế độ Gateway, không xử lý tham số ghi đè `source` trực tiếp nữa.

---

## 2. Loại Bỏ Các Bài Kiểm Thử Direct Mode Cũ

Để tránh lỗi build và làm sạch test suite, cần dọn dẹp các tệp tin kiểm thử thuộc về chế độ trực tiếp:

#### [DELETE] [test_adapters.py](file:///c:/Mujoco%20Projects/vnbrokder/tests/unit/explorer/dnse/test_adapters.py)
*   Xóa toàn bộ tệp test này do nhiệm vụ của nó là kiểm thử adapter DNSE trực tiếp không qua Gateway.

#### [MODIFY] [test_tcbs_auth_token.py](file:///c:/Mujoco%20Projects/vnbrokder/tests/unit/api/test_tcbs_auth_token.py)
*   Xóa hoặc lược bỏ các test case kiểm tra việc truyền auth_token trực tiếp xuống các provider cũ (từ dòng 62 trở đi: `test_api_quote_passes_auth_token_to_tcbs_provider`, `test_vnbroker_stock_propagates_auth_token_to_tcbs_components`, `test_vnbroker_stock_can_exchange_openapi_token`).

---

## 3. Kế Hoạch Xác Minh (Verification Plan)

### Kiểm thử tự động (Automated Tests)
*   Chạy lại toàn bộ bộ kiểm thử để đảm bảo các lỗi lệch cấu hình cũ đã biến mất và test suite đạt trạng thái 100% xanh lá:
    ```bash
    .venv\Scripts\python -m pytest
    ```
