# Báo Cáo Audit Đối Chiếu: Bản Kế Hoạch PAT-Only vs Codebase Thực Tế

**Ngày lập:** 15/06/2026  
**Chủ đề:** Đối chiếu tài liệu đặc tả kiến trúc PAT-Only với mã nguồn thực tế của dự án VNBroker  
**Người chuẩn bị:** AI Assistant (Antigravity)

---

## 1. Tổng Quan Trạng Thái Hoàn Thành

Qua đối chiếu trực tiếp giữa các tài liệu định hướng (`docs/vnstock_vnbroker_pat_proposal.md`, `docs/vnstock_vnbroker_pat_implementation_plan.md`) và mã nguồn thực tế trong thư mục làm việc, chúng tôi ghi nhận hệ thống Thin Client và cơ chế Gateway xác thực qua **Personal Access Token (PAT)** đã được cài đặt hoàn tất ở mức độ cao. 

Tuy nhiên, có một số điểm khác biệt lớn giữa mã nguồn thực tế và tài liệu đặc tả, ảnh hưởng đến khả năng tương thích ngược và việc thực thi kiểm thử (test suite).

---

## 2. Bảng Đối Chiếu Chi Tiết Các Hạng Mục

| Hạng mục đặc tả (Tài liệu) | Hiện trạng mã nguồn (Codebase) | Đánh giá |
| :--- | :--- | :--- |
| **Task 1.1**: Định nghĩa các lớp lỗi tùy chỉnh (`AuthenticationError`, `AuthorizationError`...) | Đã hoàn thành tại [exceptions.py](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/core/exceptions.py#L452). | **Đạt** |
| **Task 1.2**: Xây dựng client chuyển tiếp `GatewayHttpClient` | Đã hoàn thành tại [gateway_client.py](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/core/utils/gateway_client.py). | **Đạt** (Hỗ trợ retry, log, và timeout). |
| **Task 1.3**: Constructor `Vnbroker` hỗ trợ `DEFAULT_PAT` | Đã hoàn thành tại [client.py](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/common/client.py#L65). | **Đạt** |
| **Task 2.1**: Thiết kế module điều phối cục bộ `local_dispatch_fallback` | Đã hoàn thành tại [dispatch.py](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/core/dispatch.py). | **Đạt** (Ánh xạ đúng 100% endpoint). |
| **Task 2.2**: Giới hạn hạn mức khẩn cấp (Emergency Limit = 10) | Đã hoàn thành tại [gateway_client.py](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/core/utils/gateway_client.py#L229). | **Đạt** (Bảo vệ an toàn tránh IP ban). |
| **Task 3.1 & 3.2**: FastAPI Middleware & Redis sliding window | Đã hoàn thành tại `vninvest-sdk/vninvest_fastapi/middleware/auth.py` và `vninvest-sdk/vninvest/quota.py`. | **Đạt** |
| **Kịch bản kiểm thử AC-01 đến AC-06** | Đã viết và vượt qua hoàn toàn tại [test_pat_auth.py](file:///c:/Mujoco%20Projects/vnbrokder/tests/test_pat_auth.py) và [test_gateway_integration.py](file:///c:/Mujoco%20Projects/vnbrokder/tests/test_gateway_integration.py). | **Đạt** |

---

## 3. Các Điểm Khác Biệt & Mâu Thuẫn Kỹ Thuật (Critical Discrepancies)

### Điểm 1: Khóa cứng chế độ Gateway trong lớp [StockComponents](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/common/data.py#L260)
*   **Mô tả trong tài liệu:** Tài liệu yêu cầu thư viện phải hỗ trợ cơ chế cắm ghép linh hoạt. Nếu người dùng ghi đè nguồn trực tiếp (ví dụ: `source="DNSE"`, `source="TCBS"`), thư viện phải tôn trọng tham số này để giữ tương thích ngược và phục vụ viết kiểm thử.
*   **Thực tế trong code:** 
    *   Mặc dù [client.py](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/common/client.py) đã được sửa để cho phép bỏ qua Gateway khi ghi đè nguồn, lớp [StockComponents](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/common/data.py) bên trong lại bị khóa cứng chế độ Gateway:
        1.  `self._use_gateway = True` bị gán cứng tại dòng 319.
        2.  Phương thức `_initialize_components()` gán cứng `source="GATEWAY"` cho toàn bộ các lớp con (`Quote`, `Company`, `Listing`, `Trading`...) từ dòng 337 đến 353.
    *   **Hệ quả:** Tùy chọn ghi đè nguồn trực tiếp bị vô hiệu hóa hoàn toàn từ bên trong, khiến test case `test_vnbroker_stock_supports_dnse` bị thất bại vì luôn nhận được `GatewayQuoteAdapter` thay vì `DNSEQuote`.

### Điểm 2: Xử lý tệp tin Screener
*   **Mô tả trong tài liệu:** Có sự mâu thuẫn khi CHANGELOG ghi nhận đã xóa nhưng tệp tin `vnbroker/api/screener.py` vẫn tồn tại.
*   **Thực tế trong code:** Sau đợt cập nhật Phase 0, tệp `vnbroker/api/screener.py` đã được xóa sạch hoàn toàn khỏi codebase. Proxy `_ScreenerProxy` và `Screener` cũng đã bị gỡ khỏi [vnbroker/__init__.py](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/__init__.py). Điều này giúp codebase đồng bộ đúng với định hướng Thin Client trong tài liệu.

---

## 4. Đề Xuất Phương Án Thảo Luận Nhóm (Discussion Agenda)

Để đồng bộ hoàn toàn giữa tài liệu đặc tả và codebase, đội ngũ cần thảo luận và lựa chọn một trong hai phương án sau:

### Phương án A: Duy trì tương thích ngược cho Direct Mode (TCBS/DNSE)
*   **Hành động:** 
    *   Sửa logic trong [data.py](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/common/data.py) để `self._use_gateway` không bị gán cứng là `True` mà phụ thuộc vào tham số `source` truyền vào.
    *   Truyền đúng tham số `source` thực tế cho các lớp con trong `_initialize_components()`.
*   **Ưu điểm:** Giúp các bài test cũ (như kiểm tra DNSE adapter) vượt qua thành công, giữ lại khả năng kiểm thử độc lập các module CTCK không qua Gateway.
*   **Nhược điểm:** Tồn tại mã nguồn gọi trực tiếp thô, chưa đạt 100% "Thin Client" hoàn toàn.

### Phương án B: Cắt bỏ hoàn toàn Direct Mode (Hard cut-off)
*   **Hành động:**
    *   Xóa bỏ các bài kiểm thử kiểm tra adapter trực tiếp (như `test_vnbroker_stock_supports_dnse`).
    *   Cập nhật lại tài liệu để xác nhận Direct Mode đã bị khai tử hoàn toàn ở phiên bản này thay vì v2.0.
*   **Ưu điểm:** Đưa codebase về trạng thái Thin Client tối giản đúng như mục tiêu cao nhất của kiến trúc PAT-only.
*   **Nhược điểm:** Mất hoàn toàn khả năng tương thích ngược và khả năng chạy độc lập của client-side.
