# HỒ SƠ TÀI LIỆU TOÀN DIỆN: KIẾN TRÚC & KẾ HOẠCH TRIỂN KHAI PAT-ONLY CHO VNBROKER

Tài liệu này là hồ sơ tổng hợp toàn bộ đề xuất kiến trúc, kết quả đánh giá (audit), kế hoạch triển khai chi tiết, tiêu chí nghiệm thu và danh mục kiểm thử cho việc chuyển đổi thư viện `vnbroker` sang cơ chế xác thực bắt buộc bằng **Personal Access Token (PAT)**.

---

## 1. SO SÁNH `VNBROKER` VÀ `VNSTOCK`

| Tiêu chí | `vnstock` (Bản cộng đồng / Lịch sử) | `vnbroker` (Dự án hiện tại) |
| :--- | :--- | :--- |
| **Kiến trúc mặc định** | **Trực tiếp (Direct):** Client kết nối thẳng tới các API public của CTCK. | **Kép (Dual-mode):** Hỗ trợ cả kết nối trực tiếp và kết nối gián tiếp thông qua SaaS Gateway. |
| **Xác thực người dùng** | Không có xác thực (Anonymous). | Hỗ trợ xác thực PAT key (`vninvest_pat_...`) qua module `vninvest-sdk`. |
| **Bảo mật & Tải trọng** | Không kiểm soát. Dễ bị chặn IP (IP Ban) từ phía các công ty chứng khoán khi gọi nhiều mã. | Tích hợp sẵn `ProxyManager` thông minh và tính năng cô lập dữ liệu (Tenant Isolation). |
| **Hiệu năng & Batching** | Đồng bộ, tuần tự (Sequential) -> Tải chậm khi danh mục nhiều mã. | Hỗ trợ **Async Batch Fetching** (VCI `fetch_multiple`) và Redis Caching tập trung. |
| **Khả năng thương mại** | Không thể thương mại hóa dạng API SaaS vì người dùng tự do kết nối trực tiếp. | Có khả năng phân hạng dịch vụ (Free/Pro/Enterprise) dựa vào hạn mức cuộc gọi (Quota) gắn với PAT. |

---

## 2. HIỆN TRẠNG & VẤN ĐỀ CỦA CƠ CHẾ KÉP (DIRECT & INDIRECT)

Hiện tại, thư viện đang cho phép 2 cơ chế hoạt động song song:
1. **Truy cập trực tiếp (Direct)**: Người dùng tải `vnbroker` về và tự do gọi dữ liệu từ các CTCK mà không cần khai báo bất cứ thông tin định danh nào.
2. **Truy cập gián tiếp (Indirect)**: Sử dụng gói SaaS `vninvest-sdk` gọi qua Gateway trung gian để được quản lý hạn mức, caching và phân quyền.

### Rủi ro của mô hình kép:
* **Lỗ hổng bypass**: Người dùng hoàn toàn có thể "lách luật" bằng cách dùng trực tiếp thư viện `vnbroker` để lấy dữ liệu miễn phí mà không cần trả tiền cho gói dịch vụ SaaS qua PAT key.
* **Rủi ro IP Ban**: Khi người dùng gọi trực tiếp từ máy của họ với tần suất cao, IP của người dùng hoặc của các cụm server chứa thư viện dễ bị phía CTCK chặn, làm gián đoạn ứng dụng của họ.
* **Chi phí bảo trì**: Mỗi khi CTCK thay đổi API thô, chúng ta phải cập nhật lại mã nguồn client và bắt buộc tất cả người dùng cập nhật thư viện `vnbroker` trên máy của họ.

---

## 3. ĐỀ XUẤT KIẾN TRÚC: PAT-ONLY VỚI MÔ HÌNH LAI (HYBRID)

Chuyển đổi thư viện `vnbroker` client-side thành **Thin Client**. Toàn bộ các Broker Explorer cục bộ trên client sẽ bị loại bỏ việc gọi trực tiếp. Mọi cuộc gọi dữ liệu từ client bắt buộc phải đính kèm **PAT Key** và định tuyến qua **SaaS Gateway** trung gian.

```
                  SƠ ĐỒ KIẾN TRÚC MÔ HÌNH LAI (HYBRID MODEL)
                  
  [ vnbroker Client ] --( Gửi PAT + Request )--> [ vninvest SaaS Gateway ]
         |                                                 |
         |                                   (1) Kiểm tra  | (2) Kiểm tra Redis Cache
         |                                     PAT & Quota |
         v                                                 v
  +------------------+                              +--------------+
  | Từ chối / Lỗi    | <--- (Vượt hạn mức/Sai PAT) - |  Redis Cache |
  | 401 / 429        |                              +--------------+
  +------------------+                                     | (Cache Miss)
                                                           v
                                                [ vnbroker Server-side ]
                                                           | (Gọi API gốc)
                                                           v
                                                [ APIs (TCBS/VCI/KBS) ]
```

### 3.1. Giảm thiểu ma sát đăng ký (Onboarding Friction) bằng Default PAT
Để nhà phát triển có thể cài đặt và thử nghiệm ngay mà không cần qua bước đăng ký tài khoản, thư viện sẽ được nhúng sẵn một token mặc định với hạn mức cơ bản.
* **PAT mặc định**: `vninvest_pat_dev_free_default_unregistered_key`
* **Chính sách**: Hạn mức thấp (Ví dụ: 100 requests/ngày). Vượt quá ngưỡng này sẽ nhận mã lỗi `429` kèm hướng dẫn đăng ký tài khoản để nhận PAT cá nhân miễn phí.

### 3.2. Chế độ dự phòng khẩn cấp khi Gateway Down (Emergency Fallback Mode)
Đề phòng rủi ro Gateway bị nghẽn hoặc sập hoàn toàn (Single Point of Failure), thư viện client-side sẽ tích hợp cơ chế tự động hạ cấp khẩn cấp:
* **Hành vi**: Client tự giải quyết bằng cách gọi trực tiếp API của CTCK từ IP local.
* **Giới hạn**: Áp dụng **Strict Rate Limiting cục bộ** (tối đa 10 requests/ngày trong chế độ khẩn cấp) để tránh bị CTCK ban IP và lạm dụng chế độ này.

---

## 4. KẾ HOẠCH TRIỂN KHAI CHI TIẾT

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

## 5. TIÊU CHÍ NGHIỆM THU (ACCEPTANCE CRITERIA)

| ID | Tình huống | Hành vi mong muốn | Mã lỗi |
| :--- | :--- | :--- | :--- |
| **AC-01** | Khởi tạo không truyền PAT | Tự động gán `DEFAULT_PAT`. Request chạy bình thường qua Gateway với hạn mức thấp (100 reqs/ngày). | - |
| **AC-02** | Khai báo sai định dạng PAT | Quăng ngoại lệ cục bộ, không gửi request mạng. | `AuthenticationError` |
| **AC-03** | PAT hết hạn / Bị thu hồi | Gateway từ chối, client quăng lỗi xác thực. | `AuthenticationError` (401) |
| **AC-04** | Sai phân quyền (Scope) | Truy cập `/api/v1/finance` bằng token chỉ có scope `quote:read` -> Bị từ chối. | `AuthorizationError` (403) |
| **AC-05** | Hết hạn mức trong ngày | Vượt quá quota của gói dịch vụ -> Gateway trả về 429. | `QuotaExceededError` (429) |
| **AC-06** | Gateway down hoàn toàn | Tự động chuyển qua Emergency mode, gọi direct từ client. Rate limit tối đa 10 reqs/ngày. | `QuotaExceededError` (khi vượt 10 reqs) |

---

## 6. KỊCH BẢN KIỂM THỬ (TEST CASES)

### Kịch bản Unit Test (Target Coverage: 80%+)
* **Test Case UT-1**: Khởi tạo `Vnbroker` với token hợp lệ, không hợp lệ, và không truyền token (kiểm tra `DEFAULT_PAT`).
* **Test Case UT-2**: Giả lập (Mock) kết nối Gateway lỗi (ConnectionError, Timeout) -> Xác minh hệ thống tự động nhảy vào hàm `_emergency_fallback`.
* **Test Case UT-3**: Mock cuộc gọi khẩn cấp > 10 lần -> Xác minh ném ra lỗi `QuotaExceededError`.
* **Test Case UT-4**: Kiểm tra dữ liệu JSON trả về từ Gateway được parse chuẩn xác thành Pandas DataFrame.

### Kịch bản Integration Test (E2E)
* **Test Case IT-1**: Gửi request qua FastAPI server thật sử dụng token cá nhân hợp lệ -> Trả về data mã ACB thành công.
* **Test Case IT-2**: Chạy kiểm thử đa luồng (concurrency) để xem sliding-window trên Redis của Gateway tính toán quota chuẩn xác khi có hàng trăm request đồng thời.
* Lệnh chạy test: `pytest tests/test_integration_pat.py`

---

## 7. DANH MỤC KIỂM TRA AUDIT (AUDIT CHECKLIST)

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
- [ ] Thiết lập HA cluster cho Gateway (load balancer, phân vùng dự phòng).
