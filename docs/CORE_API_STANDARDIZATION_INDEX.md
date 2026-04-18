# Core API Standardization - Bộ tài liệu triển khai

> Mục tiêu: Chuẩn hoá API cho 3 nhóm chức năng (Tài chính cơ bản, Giao dịch nội bộ, So sánh ngành) theo kiến trúc adapter/provider hiện có, và mở rộng provider mới với thay đổi tối thiểu.
>
> Trạng thái: Implemented, validated, production-ready gate passed
>
> Cập nhật: 2026-04-18

---

## Bộ tài liệu này gồm

1. `CORE_API_STANDARDIZATION_RFC.md`
- Định nghĩa contract chuẩn cho API, schema, error model, capability matrix.

2. `CORE_API_STANDARDIZATION_SPRINT_PLAN.md`
- Kế hoạch theo sprint, phụ thuộc kỹ thuật, deliverable từng giai đoạn.

3. `CORE_API_STANDARDIZATION_TASK_BOARD.md`
- Task breakdown theo ngày để team code bắt tay ngay.

4. `CORE_API_STANDARDIZATION_PROVIDER_ONBOARDING.md`
- Quy chuẩn thêm provider mới mà không sửa nhiều code lõi.

5. `CORE_API_STANDARDIZATION_TEST_ACCEPTANCE.md`
- Test plan + tiêu chí nghiệm thu (DoD, gate release).

6. `CENTRAL_MODIFIED_FILES_AUDIT.md`
- Nhật ký tập trung liệt kê toàn bộ file thay đổi để kiểm toán.

7. `CORE_API_STANDARDIZATION_JSON_SCHEMA.md`
- JSON schema mẫu cho Insider, Financial, Industry comparison.

8. `CORE_API_STANDARDIZATION_PR_CHECKLIST.md`
- Checklist PR chuẩn để kiểm soát contract, test, docs, audit.

9. `CORE_API_STANDARDIZATION_IMPLEMENTATION_PLAYBOOK.md`
- Playbook điều phối thực thi theo vai trò và quy trình hằng ngày.

10. `CORE_API_STANDARDIZATION_RISK_REGISTER.md`
- Sổ đăng ký rủi ro kỹ thuật và phương án giảm thiểu.

11. `CORE_API_STANDARDIZATION_EXECUTION_STATUS_TEMPLATE.md`
- Mẫu báo cáo tiến độ hằng ngày cho đội code.

12. `CORE_API_STANDARDIZATION_CODE_READY_CHECKLIST.md`
- Checklist GO/NO-GO trước khi bắt đầu coding.

13. `CORE_API_STANDARDIZATION_WORK_ITEMS.md`
- Danh sách ticket chi tiết theo epic để đưa thẳng vào board.

14. `CORE_API_STANDARDIZATION_BRANCHING_RELEASE.md`
- Quy trình branch, review, merge gate, release, rollback.

15. `CORE_API_STANDARDIZATION_DECISION_LOG.md`
- Nhật ký quyết định kỹ thuật để đồng bộ team.

16. `CORE_API_STANDARDIZATION_KICKOFF_SIGNOFF.md`
- Biên bản signoff chính thức trước khi vào coding.

---

## Cách sử dụng bộ tài liệu (khuyến nghị)

1. Team lead đọc RFC và chốt lại contract cuối cùng.
2. Core team dùng Sprint Plan để lập mốc giao hàng.
3. Dev owner nhận việc từ Task Board theo ngày.
4. Provider engineer tuân theo Onboarding guide.
5. QA chạy Test/Acceptance checklist trước merge.
6. Mọi thay đổi file đều bắt buộc cập nhật Audit file.

---

## Mốc thực thi đề xuất

- Ngày 1-2: Chốt contract và capability matrix.
- Ngày 3-6: Chuẩn hoá Insider API xuyên provider.
- Ngày 7-11: Chuẩn hoá Financial API và snapshot.
- Ngày 12-16: Hoàn thiện So sánh ngành.
- Ngày 17-20: Hardening, regression, release docs.

---

## Quy tắc kỹ thuật cốt lõi

- Không sửa logic lõi cho từng provider mới.
- Provider mới chỉ thêm: class implementation + register + capability manifest + schema mapping + test contract.
- Mọi API public mới phải có schema chuẩn, metadata source/source_used, và error code nhất quán.
