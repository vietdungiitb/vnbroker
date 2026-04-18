# Branching, Review và Release Procedure

---

## 1) Branching model

Nhánh chính:
- main: nhánh ổn định.
- dev: nhánh tích hợp.

Nhánh tính năng:
- feature/core-insider-*
- feature/core-financial-*
- feature/core-industry-*
- feature/core-provider-ext-*

Nhánh fix:
- fix/core-*

---

## 2) Quy tắc commit

Mẫu:
- feat(insider): ...
- feat(financial): ...
- feat(industry): ...
- test(core): ...
- docs(core): ...
- fix(core): ...

---

## 3) Pull request flow

1. Tạo PR vào dev.
2. Điền đầy đủ checklist PR.
3. Đính kèm bằng chứng test.
4. Reviewer bắt buộc:
- 1 Core reviewer
- 1 QA reviewer
- 1 Docs reviewer nếu đổi contract/schema
5. Merge khi pass tất cả gate.

---

## 4) Merge gate bắt buộc

- CI pass.
- Contract tests pass.
- Không có blocker open.
- Docs cập nhật.
- Audit file cập nhật.

---

## 5) Release procedure

1. Freeze scope.
2. Chạy regression full suite.
3. Chốt release notes.
4. Tech Lead + QA signoff.
5. Merge dev -> main theo policy.

---

## 6) Rollback guideline

Khi gặp lỗi nghiêm trọng sau merge:
1. Tạo hotfix branch từ main.
2. Revert theo commit phạm vi hẹp.
3. Chạy lại smoke + contract tests.
4. Cập nhật incident note trong decision log.

---

## 7) Trách nhiệm vai trò

- Tech Lead: phê duyệt contract và gate cuối.
- Core Engineer: đảm bảo tuân thủ kiến trúc.
- QA: xác nhận test evidence.
- Docs: xác nhận tài liệu và audit.
