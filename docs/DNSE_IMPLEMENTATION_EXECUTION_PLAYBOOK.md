# DNSE Implementation Execution Playbook

> Mục tiêu: biến bộ tài liệu DNSE hiện có thành quy trình thực thi cho đội code, không cần hỏi lại từng bước.
>
> Trạng thái: Sẵn sàng triển khai
>
> Ngày: 2026-05-08

---

## 1. Mục đích

Tài liệu này là lớp điều hành cho đội code khi triển khai DNSE vào vnbroker.

Nó có ba nhiệm vụ:

- Khóa thứ tự đọc tài liệu để mọi người dùng cùng một nguồn sự thật.
- Quy định cách chia slice, cách validate, cách ghi minh chứng, và cách audit.
- Loại bỏ việc hỏi lại những quyết định đã được chốt trong bộ tài liệu chiến lược và contract.

---

## 2. Nguồn sự thật và thứ tự ưu tiên

Khi có xung đột giữa các tài liệu, áp dụng thứ tự ưu tiên sau:

1. [DNSE_PROJECT_FINAL_RECOMMENDATION.md](DNSE_PROJECT_FINAL_RECOMMENDATION.md)
2. [DNSE_EXECUTIVE_DECISION_BRIEF.md](DNSE_EXECUTIVE_DECISION_BRIEF.md)
3. [DNSE_PROVIDER_DECISION_GUIDE.md](DNSE_PROVIDER_DECISION_GUIDE.md)
4. [DNSE_PROVIDER_COMPARISON_MATRIX.md](DNSE_PROVIDER_COMPARISON_MATRIX.md)
5. [DNSE_API_CONTRACT.md](DNSE_API_CONTRACT.md)
6. [DNSE_EXPLORER_SPEC.md](DNSE_EXPLORER_SPEC.md)
7. [DNSE_MODULE_STRUCTURE.md](DNSE_MODULE_STRUCTURE.md)
8. [DNSE_INTEGRATION_PLAN_20260507.md](DNSE_INTEGRATION_PLAN_20260507.md)
9. [DNSE_TEST_SPEC_V2.md](DNSE_TEST_SPEC_V2.md)
10. [DNSE_AUDIT_CHECKLIST.md](DNSE_AUDIT_CHECKLIST.md)

Quy tắc xử lý khi còn mâu thuẫn sau khi đọc các tài liệu trên:

- Chọn phương án phù hợp với contract hẹp hơn và ít rủi ro hơn.
- Chọn slice nhỏ nhất có thể đảo ngược.
- Ghi rõ giả định vào audit file.
- Tiếp tục thực thi, không chờ hỏi lại user.

Chỉ dừng để hỏi khi gặp blocker bên ngoài repo, ví dụ:

- thiếu credential;
- môi trường không truy cập được;
- xung đột an ninh hoặc pháp lý.

---

## 3. Quy tắc vận hành bắt buộc

### 3.1 Một slice, một mục tiêu

Mỗi slice chỉ được tập trung vào một thay đổi kiểm soát.

Không trộn các loại thay đổi không cùng bản chất trong cùng một slice nếu có thể tách được.

### 3.2 Sau edit đầu tiên phải validate ngay

Sau khi hoàn tất edit thực chất đầu tiên, bước tiếp theo phải là một validation hẹp.

Ưu tiên theo thứ tự:

1. kiểm tra logic hoặc behavior hẹp nhất;
2. test nhỏ trên slice đã đụng;
3. compile/lint/typecheck hẹp;
4. `git diff --check` chỉ khi không có kiểm tra hẹp hơn.

### 3.3 Không mở rộng scope giữa chừng

Sau khi đã có một giả thuyết cục bộ và một kiểm tra rẻ có thể bác bỏ giả thuyết đó, không quay lại đào rộng sang module lân cận trước khi validate xong slice hiện tại.

### 3.4 Luôn ghi minh chứng

Mỗi thay đổi phải có:

- file đã sửa;
- lệnh đã chạy;
- output tóm tắt;
- kết quả PASS/FAIL/SKIP;
- audit entry tương ứng.

---

## 4. Luồng triển khai chuẩn

### Bước 1. Chốt slice

- Đọc playbook này trước.
- Đối chiếu với master plan và contract.
- Chọn slice nhỏ nhất có thể hoàn tất trong một vòng làm việc.

### Bước 2. Implement

- Chỉ sửa các file nằm trong phạm vi slice.
- Giữ style và API hiện có.
- Không thêm behavior mới nếu contract chưa chốt.

### Bước 3. Validate ngay sau edit

- Chạy kiểm tra hẹp nhất trước.
- Nếu fail, sửa ngay slice đó và chạy lại cùng kiểm tra.
- Không mở rộng phạm vi trước khi kiểm tra hẹp pass.

### Bước 4. Ghi minh chứng

- Cập nhật [docs/CENTRAL_MODIFIED_FILES_AUDIT.md](docs/CENTRAL_MODIFIED_FILES_AUDIT.md).
- Nếu thay đổi cấu trúc file hoặc docs tree, cập nhật [module_tree_full.md](module_tree_full.md) và [docs/DNSE_INDEX.md](docs/DNSE_INDEX.md).

### Bước 5. Đóng gói thay đổi

- Chạy `git diff --check`.
- Chạy lại test hẹp đã dùng để validate.
- Commit riêng slice đó.
- Push lên `dev`.

### Bước 6. Bàn giao

- Ghi rõ commit hash.
- Ghi rõ test evidence.
- Ghi rõ bất kỳ skip nào kèm lý do môi trường.

---

## 5. Kế hoạch triển khai chuẩn cho team code

Khi team code thực hiện lại hoặc mở rộng DNSE, dùng thứ tự logic sau:

1. Khóa contract và source of truth.
2. Chọn slice từ master plan.
3. Implement tối thiểu.
4. Validate hẹp.
5. Ghi audit.
6. Cập nhật tree/index nếu có tài liệu mới.
7. Commit và push.

Nếu slice đụng đến runtime hoặc public API, bắt buộc có unit test hoặc integration evidence tương ứng.

Nếu slice chỉ là docs, vẫn phải có `git diff --check` và audit entry.

---

## 6. Điều kiện hoàn thành slice

Một slice chỉ được coi là xong khi đồng thời thỏa:

- code hoặc docs đã sửa đúng phạm vi;
- validation hẹp đã pass hoặc có skip hợp lệ;
- audit log đã được append;
- file tree và index đã được cập nhật nếu có thay đổi docs;
- commit đã được tạo;
- push lên `dev` đã hoàn tất.

---

## 7. Mẫu ghi nhớ cho người thực hiện

Trước khi chuyển sang slice kế tiếp, tự trả lời 5 câu sau:

1. Slice này có đúng một mục tiêu không?
2. Validation hẹp nhất đã chạy chưa?
3. Có evidence để audit chưa?
4. Có file tree/index cần cập nhật không?
5. Commit/push đã xong chưa?

Nếu một câu trả lời là chưa, slice chưa được đóng.
