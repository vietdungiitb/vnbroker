# TCBS Implementation Execution Playbook

> Mục tiêu: biến bộ tài liệu TCBS-primary thành quy trình thực thi chuẩn cho đội code.
>
> Trạng thái: Sẵn sàng dùng sau khi plan được duyệt.
>
> Ngày: 2026-05-19

---

## 1. Mục đích

Tài liệu này là lớp điều hành cho workstream TCBS-primary. Nó có bốn nhiệm vụ:

- Khóa thứ tự đọc tài liệu và nguồn sự thật.
- Ép mọi slice đi theo security-first thay vì explorer-first.
- Chuẩn hóa validation, audit evidence và stop conditions.
- Giảm tối đa việc hỏi lại khi đã có plan được duyệt.

---

## 2. Nguồn sự thật và thứ tự ưu tiên

Khi có xung đột giữa các tài liệu, áp dụng thứ tự sau:

1. [TCBS_EXECUTIVE_DECISION_BRIEF.md](TCBS_EXECUTIVE_DECISION_BRIEF.md)
2. [TCBS_BROKER_PLATFORM_RFC.md](TCBS_BROKER_PLATFORM_RFC.md)
3. [TCBS_INTEGRATION_MASTER_PLAN.md](TCBS_INTEGRATION_MASTER_PLAN.md)
4. [TCBS_SPRINT_TASK_BOARD.md](TCBS_SPRINT_TASK_BOARD.md)
5. [TCBS_SLICE_DEFINITION_OF_DONE.md](TCBS_SLICE_DEFINITION_OF_DONE.md)
6. [CENTRAL_MODIFIED_FILES_AUDIT.md](CENTRAL_MODIFIED_FILES_AUDIT.md)

Nếu xung đột với tài liệu cũ nói TCBS chỉ là compatibility path, ghi rõ trong audit rằng workstream này đã được duyệt theo TCBS-primary initiative và tiếp tục thực thi theo bộ TCBS docs mới.

---

## 3. Quy tắc vận hành bắt buộc

### 3.1 Một slice, một mục tiêu

Mỗi slice chỉ tập trung vào một thay đổi kiểm soát. Không trộn security substrate với public parity hoặc portfolio nếu có thể tách.

### 3.2 Sau edit đầu tiên phải validate ngay

Thứ tự ưu tiên validation:

1. test hoặc behavior hẹp nhất của slice;
2. `python -m pytest` cho module test hẹp;
3. import smoke hoặc check source hẹp;
4. `git diff --check` nếu slice là docs hoặc không có kiểm tra hẹp hơn.

### 3.3 Không mở rộng scope giữa chừng

Sau khi bắt đầu slice security hoặc auth, không nhảy sang public parity trước khi validation của slice hiện tại đã rõ PASS/FAIL.

### 3.4 Mọi thay đổi phải có evidence

Mỗi slice bắt buộc ghi:

- files đã sửa;
- lệnh đã chạy;
- output tóm tắt;
- PASS/FAIL/SKIP;
- audit entry.

### 3.5 Ưu tiên `python -m pytest`

Môi trường hiện tại đã quan sát trường hợp `pytest` không có trên PATH. Với repo này, mọi lệnh test trong playbook nên viết theo `python -m pytest` để giảm biến động môi trường shell.

---

## 4. Security red lines

1. Không log full token, OTP, API key, account number hay order payload.
2. Không gửi write request thật nếu chưa ở `dry_run=True` hoặc chưa có sign-off explicit cho slice write.
3. Không cho broker lane dùng `AUTO` hoặc fallback sang provider khác.
4. Không tái sử dụng helper request/logging generic nếu nó chưa qua redaction policy.
5. Không lưu token xuống file plaintext hoặc home directory cache theo mặc định.
6. Không để public/provider object giữ broker session object.

Nếu vi phạm một red line, dừng slice, khóa status về FAIL và ghi lý do vào audit file.

---

## 5. Luồng triển khai chuẩn

### Bước 1. Chốt slice

- Đọc playbook này.
- Đối chiếu `TCBS_INTEGRATION_MASTER_PLAN.md` và `TCBS_SPRINT_TASK_BOARD.md`.
- Chọn slice nhỏ nhất có thể hoàn tất trong một vòng làm việc.

### Bước 2. Implement

- Chỉ sửa các file trong phạm vi slice.
- Không thêm behavior ngoài DoD đã chốt.
- Nếu slice đụng đến secret path, kiểm tra redaction ngay trong lúc code.

### Bước 3. Validate ngay sau edit

- Chạy lệnh trong `TCBS_SLICE_DEFINITION_OF_DONE.md` của slice tương ứng.
- Nếu fail, sửa đúng slice đó và chạy lại cùng lệnh.
- Không mở slice mới trước khi kết quả validation rõ.

### Bước 4. Ghi minh chứng

- Append vào [CENTRAL_MODIFIED_FILES_AUDIT.md](CENTRAL_MODIFIED_FILES_AUDIT.md).
- Cập nhật [TCBS_SPRINT_TASK_BOARD.md](TCBS_SPRINT_TASK_BOARD.md).
- Regenerate `module_tree_full.md` nếu source/docs tree thay đổi.

### Bước 5. Đóng gói thay đổi

- Chạy `git diff --check`.
- Chạy lại test hẹp đã dùng.
- Chỉ sau khi pass mới coi slice là xong.

---

## 6. Khi nào phải dừng để hỏi

Chỉ dừng để hỏi khi gặp blocker ngoài repo hoặc quyết định nghiệp vụ chưa chốt, ví dụ:

- thiếu credential hoặc OTP thật để live smoke;
- phát hiện yêu cầu pháp lý/compliance mới;
- cần quyết định write rollout thật thay vì `dry_run`;
- có mâu thuẫn giữa TCBS docs và yêu cầu kinh doanh mới chưa được chốt.

Các trường hợp còn lại phải tự tiếp tục theo plan và ghi giả định vào audit.

---

## 7. Điều kiện hoàn thành slice

Một slice chỉ được coi là DONE khi đồng thời thỏa:

- code/docs đã sửa đúng phạm vi;
- validation hẹp pass hoặc có SKIP hợp lệ kèm lý do môi trường;
- audit file đã append;
- task board đã cập nhật trạng thái;
- module tree đã cập nhật nếu cần.

---

## 8. Tự kiểm tra trước khi sang slice kế tiếp

1. Slice này có đúng một mục tiêu không?
2. Validation hẹp nhất đã chạy chưa?
3. Có evidence để audit chưa?
4. Có chạm source/docs tree cần cập nhật module tree không?
5. Có red line nào bị vi phạm không?

Nếu một câu trả lời là chưa, slice chưa được đóng.
