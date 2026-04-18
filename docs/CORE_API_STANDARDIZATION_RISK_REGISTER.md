# Risk Register - Core API Standardization

---

## R1 - Method mismatch giữa provider

Mô tả:
- Provider A/B dùng tên method khác nhau cho cùng nghiệp vụ (ví dụ insider).

Xác suất: Cao
Ảnh hưởng: Cao

Giảm thiểu:
- Bắt buộc alias chuẩn ở adapter/provider.
- Contract test method surface.

Owner: Core Engineer

---

## R2 - Schema drift khi AUTO failover

Mô tả:
- AUTO chuyển provider làm schema trả về khác cột/kiểu.

Xác suất: Trung bình
Ảnh hưởng: Cao

Giảm thiểu:
- Chuẩn hoá schema sau fetch trước return.
- Bắt buộc cột tối thiểu + null-safe.

Owner: Core Engineer

---

## R3 - Thiếu dữ liệu ngành cho so sánh

Mô tả:
- Một số mã thiếu thông tin ngành hoặc mapping ICB không đầy đủ.

Xác suất: Trung bình
Ảnh hưởng: Trung bình

Giảm thiểu:
- Fallback industry = Khác.
- Bổ sung rule loại trừ cho benchmark khi thiếu peer hợp lệ.

Owner: Provider Engineer

---

## R4 - Performance giảm khi tính benchmark/rank

Mô tả:
- Tính toán theo vòng lặp gây chậm khi số peer lớn.

Xác suất: Trung bình
Ảnh hưởng: Trung bình

Giảm thiểu:
- Dùng Pandas vectorized.
- Benchmark trước/sau cho API mới.

Owner: Core Engineer

---

## R5 - Regression ngoài phạm vi

Mô tả:
- Thay đổi lớp lõi gây ảnh hưởng module khác.

Xác suất: Thấp
Ảnh hưởng: Cao

Giảm thiểu:
- Regression suite bắt buộc.
- PR nhỏ theo module, không gộp thay đổi lớn.

Owner: QA Engineer

---

## R6 - Thiếu cập nhật tài liệu/audit

Mô tả:
- Đội code merge xong nhưng thiếu tài liệu và nhật ký file.

Xác suất: Trung bình
Ảnh hưởng: Trung bình

Giảm thiểu:
- PR checklist bắt buộc có mục docs + audit.
- Gate merge bởi docs owner.

Owner: Docs Engineer
