# KẾ HOẠCH TRIỂN KHAI & TIÊU CHÍ NGHIỆM THU (PAT-ONLY ARCHITECTURE)

Tài liệu này phác thảo kế hoạch chi tiết, các tiêu chí nghiệm thu (acceptance criteria), kịch bản kiểm thử (test suite) và danh mục kiểm tra an toàn/hiệu năng (audit checklist) cho việc triển khai mô hình lai bắt buộc sử dụng PAT key dựa trên bản đề xuất [vnstock_vnbroker_pat_proposal.md](file:///c:/Mujoco%20Projects/vnbrokder/docs/vnstock_vnbroker_pat_proposal.md).

---

## 1. Mục tiêu & Phạm vi Thay đổi
Chuyển đổi thư viện `vnbroker` thành một Thin Client, chuyển tiếp các yêu cầu dữ liệu qua API Gateway `vninvest-sdk` bằng khóa cá nhân Personal Access Token (PAT).
* **Mô hình**: Hỗ trợ cơ chế Lai (Hybrid) -> mặc định gọi qua Gateway bằng PAT cá nhân/Default PAT, tự động chuyển về chế độ Emergency Fallback nếu Gateway sập.

---

## 2. Kế hoạch Thực hiện chi tiết

### Phase 1: Nền tảng Auth & Gateway Client (Client-side)
* **Task 1.1**: Định nghĩa các lớp lỗi tùy chỉnh mới tại `vnbroker/core/exceptions.py` (`AuthenticationError`, `AuthorizationError`, `QuotaExceededError`, `ProviderError`).
* **Task 1.2**: Xây dựng client chuyển tiếp `GatewayHttpClient` tại `vnbroker/core/utils/gateway_client.py` để đóng gói request và xử lý lỗi HTTP.
* **Task 1.3**: Sửa đổi constructor của `Vnbroker` tại `vnbroker/common/client.py` để hỗ trợ `DEFAULT_PAT`.

### Phase 2: Triển khai Emergency Fallback (Client-side)
* **Task 2.1**: Thiết kế module điều phối cục bộ `vnbroker/core/dispatch.py` có khả năng map các endpoints `/api/v1/...` sang các local explorer cũ (VCI, KBS, TCBS...).
* **Task 2.2**: Triển khai cơ chế đếm hạn mức cục bộ (Client-side throttling) giới hạn tối đa 10 requests/ngày trong chế độ khẩn cấp.

### Phase 3: Gateway Server-side & API (vninvest-sdk)
* **Task 3.1**: Cấu hình Middleware kiểm tra PAT thô và ánh xạ Tenant/Scope trong FastAPI (`vninvest-sdk/vninvest_fastapi/middleware/auth.py`).
* **Task 3.2**: Tích hợp Redis sliding-window để tính quota và cấu hình TTL cho cache của mỗi tenant.

---

## 3. Đề xuất Thay đổi (Proposed Changes)

### `vnbroker` (Client-side Library)

#### [MODIFY] [client.py](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/common/client.py)
* Tích hợp cấu hình `pat_key` mặc định (`DEFAULT_PAT`).
* Điều hướng các module con (`Quote`, `Company`, `Finance`) sử dụng `_gateway_client`.

#### [NEW] [gateway_client.py](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/core/utils/gateway_client.py)
* Triển khai session HTTP, đính kèm token PAT.
* Xử lý cơ chế tự động hạ cấp khẩn cấp khi nhận lỗi kết nối hoặc timeout mạng.

#### [NEW] [dispatch.py](file:///c:/Mujoco%20Projects/vnbrokder/vnbroker/core/dispatch.py)
* Điều phối cuộc gọi thô đến các local explorer cũ khi Gateway bị sập.

---

## 4. Tiêu chí Đạt được (Acceptance Criteria)

| ID | Tình huống | Hành vi mong muốn | Mã lỗi |
| :--- | :--- | :--- | :--- |
| **AC-01** | Khởi tạo không truyền PAT | Tự động gán `DEFAULT_PAT`. Request chạy bình thường qua Gateway với hạn mức thấp (100 reqs/ngày). | - |
| **AC-02** | Khai báo sai định dạng PAT | Quăng ngoại lệ cục bộ, không gửi request mạng. | `AuthenticationError` |
| **AC-03** | PAT hết hạn / Bị thu hồi | Gateway từ chối, client quăng lỗi xác thực. | `AuthenticationError` (401) |
| **AC-04** | Sai phân quyền (Scope) | Truy cập `/api/v1/finance` bằng token chỉ có scope `quote:read` -> Bị từ chối. | `AuthorizationError` (403) |
| **AC-05** | Hết hạn mức trong ngày | Vượt quá quota của gói dịch vụ -> Gateway trả về 429. | `QuotaExceededError` (429) |
| **AC-06** | Gateway down hoàn toàn | Tự động chuyển qua Emergency mode, gọi direct từ client. Rate limit tối đa 10 reqs/ngày. | `QuotaExceededError` (khi vượt 10 reqs) |

---

## 5. Kịch bản Kiểm thử (Verification & Test Cases)

### Kịch bản Unit Test (Target Coverage: 80%+)
* **Test Case UT-1**: Khởi tạo `Vnbroker` với token hợp lệ, không hợp lệ, và không truyền token (kiểm tra `DEFAULT_PAT`).
* **Test Case UT-2**: Giả lập (Mock) kết nối Gateway lỗi (ConnectionError, Timeout) -> Xác minh hệ thống tự động nhảy vào hàm `_emergency_fallback`.
* **Test Case UT-3**: Mock cuộc gọi khẩn cấp > 10 lần -> Xác minh ném ra lỗi `QuotaExceededError`.
* **Test Case UT-4**: Kiểm tra dữ liệu JSON trả về từ Gateway được parse chuẩn xác thành Pandas DataFrame.

### Kịch bản Integration Test (E2E)
* **Test Case IT-1**: Gửi request qua FastAPI server thật sử dụng token cá nhân hợp lệ -> Trả về data mã ACB thành công.
* **Test Case IT-2**: Chạy kiểm thử đa luồng (concurrency) để xem sliding-window trên Redis của Gateway tính toán quota chuẩn xác khi có hàng trăm request đồng thời.
* Chạy test suite: `pytest tests/test_integration_pat.py`

---

## 6. Danh mục Kiểm tra Audit (Audit Checklist)

### 🛡️ An toàn bảo mật (Security Audit)
- [ ] Không lưu trữ PAT thô (plaintext) trên database hoặc log của server (Bắt buộc dùng hash Bcrypt/Argon2).
- [ ] Mọi thông tin truyền tải dữ liệu chứa token qua Gateway phải chạy trên HTTPS.
- [ ] Không để lộ ID của Tenant trong chuỗi PAT (Sử dụng chuỗi ngẫu nhiên Base64/UUID làm token).

### ⚡ Hiệu năng (Performance Audit)
- [ ] Đo đạc overhead độ trễ khi qua Gateway: Đảm bảo tổng độ trễ tăng thêm ở trạng thái cache miss không vượt quá **50ms**.
- [ ] Xác minh tỷ lệ trúng cache (Cache Hit Rate) đạt từ **65% trở lên** đối với các symbol phổ biến (như VN30) trong các khung giờ cao điểm giao dịch.
- [ ] Không có hiện tượng rò rỉ bộ nhớ (Memory leak) ở client-side khi duy trì phiên gửi request đồng thời (Concurrent sessions).

### 🌀 Tính chịu lỗi (Resilience Audit)
- [ ] Khi Gateway hồi sinh từ trạng thái down, client tự động ngắt Emergency Mode và phục hồi kết nối Gateway bình thường cho các request tiếp theo.
