# Implementation Playbook - Core API Standardization

> Tài liệu điều phối để đội code thực thi ngay theo vai trò và nhịp làm việc hằng ngày.

---

## 1) Team setup đề xuất

- 1 Tech Lead: giữ contract, chốt quyết định kiến trúc.
- 2 Core Engineers: adapter, normalizer, router integration.
- 2 Provider Engineers: KBS/VCI/TCBS mapping.
- 1 QA Engineer: contract, integration, regression.
- 1 Docs Engineer: cập nhật hướng dẫn + audit.

---

## 2) Luồng triển khai chuẩn cho mỗi API mới

1. Chốt signature và schema trên RFC.
2. Implement ở provider layer.
3. Implement normalizer/mapping layer.
4. Integrate vào facade/API layer.
5. Viết unit + contract + integration tests.
6. Cập nhật docs + audit file.
7. Mở PR theo checklist.

---

## 3) Branching và commit guideline

- Branch naming:
  - `feature/core-insider-standardization`
  - `feature/core-financial-normalization`
  - `feature/core-industry-comparison`
- Commit format:
  - `feat(insider): add normalized insider_deals alias for kbs`
  - `test(financial): add cross-provider contract tests`
  - `docs(core): update standardization index and schemas`

---

## 4) Daily ritual (15-20 phút)

1. Mở `CORE_API_STANDARDIZATION_TASK_BOARD.md` xác nhận task trong ngày.
2. Chốt owner cho từng task.
3. Báo blocker sớm trước 11:00.
4. Cuối ngày cập nhật trạng thái + file audit.

---

## 5) Definition of Ready cho task

Task chỉ được bắt đầu khi:
- Có contract rõ (input, output, error).
- Có owner rõ.
- Có test expectation rõ.
- Có file target rõ.

---

## 6) Definition of Done cho task

Task chỉ hoàn tất khi:
- Code pass tất cả test liên quan.
- Không vi phạm contract schema.
- Docs cập nhật đầy đủ.
- Audit file đã append chính xác.

---

## 7) Escalation rules

- Blocker > 4 giờ: escalate Tech Lead.
- Blocker do provider API thay đổi: tạo hotfix mapping issue và đánh dấu mức độ ảnh hưởng.
- Blocker do schema mismatch: ưu tiên giữ schema chuẩn, fill null + warning.

---

## 8) Handoff package cuối sprint

Mỗi sprint bàn giao tối thiểu:
- Danh sách PR đã merge.
- Kết quả test summary.
- Danh sách risk còn mở.
- Cập nhật docs index.
- Cập nhật file audit tập trung.
