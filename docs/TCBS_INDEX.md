# TCBS Primary Broker Documentation Index

Bộ tài liệu này được tạo cho workstream đưa TCBS trở thành broker platform chính trong vnbroker theo hướng bảo mật ưu tiên cao, tách biệt provider rõ ràng, và vẫn giữ tương thích với lớp provider hiện có.

**Cập nhật lần cuối:** 2026-05-19

---

## Cách đọc bộ tài liệu này

### Bước 1 — Chốt quyết định kiến trúc

| Thứ tự | File | Mục đích |
|---|---|---|
| 0 | [TCBS_EXECUTIVE_DECISION_BRIEF.md](TCBS_EXECUTIVE_DECISION_BRIEF.md) | Bản một trang để chốt nhanh mô hình dual-plane và các quyết định an toàn bắt buộc |
| 1 | [TCBS_BROKER_PLATFORM_RFC.md](TCBS_BROKER_PLATFORM_RFC.md) | RFC kỹ thuật chi tiết cho kiến trúc TCBS-primary, provider isolation, security plane và portfolio domain |

### Bước 2 — Lập kế hoạch triển khai

| Thứ tự | File | Mục đích |
|---|---|---|
| 2 | [TCBS_INTEGRATION_MASTER_PLAN.md](TCBS_INTEGRATION_MASTER_PLAN.md) | Master plan với scope, gap, task breakdown, dependency graph, validation gates và risk register |
| 3 | [TCBS_SPRINT_TASK_BOARD.md](TCBS_SPRINT_TASK_BOARD.md) | Task board chi tiết theo slice S0–S11 để đội code thực thi không hỏi lại |

### Bước 3 — Điều hành thực thi

| Thứ tự | File | Mục đích |
|---|---|---|
| 4 | [TCBS_IMPLEMENTATION_EXECUTION_PLAYBOOK.md](TCBS_IMPLEMENTATION_EXECUTION_PLAYBOOK.md) | Playbook điều hành: thứ tự đọc, validation hẹp, security red lines, audit protocol |
| 5 | [TCBS_SLICE_DEFINITION_OF_DONE.md](TCBS_SLICE_DEFINITION_OF_DONE.md) | Definition of Done cho từng slice, kèm lệnh validation và mẫu evidence |

### Bước 4 — Tài liệu kỹ thuật thực thi (đọc trước khi code)

| Thứ tự | File | Mục đích |
|---|---|---|
| 6 | [TCBS_API_CONTRACT.md](TCBS_API_CONTRACT.md) | Endpoint thật, auth flow, request/response schema, error model, dry-run contract — contract ràng buộc với TCBS OpenAPI |
| 7 | [TCBS_MODULE_STRUCTURE.md](TCBS_MODULE_STRUCTURE.md) | Sơ đồ file chính xác cho `vnbroker/broker/tcbs/`, quy tắc tách layer, naming, logging rules |
| 8 | [TCBS_BROKER_SPEC.md](TCBS_BROKER_SPEC.md) | **Spec quan trọng nhất**: exact class/method signatures, schema contracts, output dtype — đọc là biết viết gì |
| 9 | [TCBS_CODING_GUIDE.md](TCBS_CODING_GUIDE.md) | Step-by-step code mẫu từng bước, common pitfalls, checklist trước commit |

### Bước 5 — Test và audit

| Thứ tự | File | Mục đích |
|---|---|---|
| 10 | [TCBS_TEST_SPEC.md](TCBS_TEST_SPEC.md) | Test code stubs sẵn, fixtures, KPI coverage, integration test template — đội test không phải tự đoán |
| 11 | [TCBS_AUDIT_CHECKLIST.md](TCBS_AUDIT_CHECKLIST.md) | Checklist 14 phần (82 hạng mục) có lệnh validation + cột bằng chứng + form sign-off 3 vai trò |

---

## Thứ tự ưu tiên khi có xung đột tài liệu

Áp dụng thứ tự sau cho workstream TCBS-primary:

1. [TCBS_EXECUTIVE_DECISION_BRIEF.md](TCBS_EXECUTIVE_DECISION_BRIEF.md)
2. [TCBS_BROKER_PLATFORM_RFC.md](TCBS_BROKER_PLATFORM_RFC.md)
3. [TCBS_API_CONTRACT.md](TCBS_API_CONTRACT.md)
4. [TCBS_BROKER_SPEC.md](TCBS_BROKER_SPEC.md)
5. [TCBS_INTEGRATION_MASTER_PLAN.md](TCBS_INTEGRATION_MASTER_PLAN.md)
6. [TCBS_IMPLEMENTATION_EXECUTION_PLAYBOOK.md](TCBS_IMPLEMENTATION_EXECUTION_PLAYBOOK.md)
7. [TCBS_MODULE_STRUCTURE.md](TCBS_MODULE_STRUCTURE.md)
8. [TCBS_CODING_GUIDE.md](TCBS_CODING_GUIDE.md)
9. [TCBS_TEST_SPEC.md](TCBS_TEST_SPEC.md)
10. [TCBS_AUDIT_CHECKLIST.md](TCBS_AUDIT_CHECKLIST.md)
11. [TCBS_SPRINT_TASK_BOARD.md](TCBS_SPRINT_TASK_BOARD.md)
12. [TCBS_SLICE_DEFINITION_OF_DONE.md](TCBS_SLICE_DEFINITION_OF_DONE.md)

Nếu xung đột với các tài liệu cũ kết luận TCBS chỉ là compatibility path, dùng bộ tài liệu TCBS này cho riêng workstream TCBS-primary. Các tài liệu DNSE cũ vẫn được giữ như tư liệu lịch sử cho workstream DNSE và không bị xóa giá trị ngoài phạm vi initiative này.

---

## Mục tiêu của workstream

- Đưa TCBS thành broker platform chính cho xác thực, tài khoản, tiền, chứng khoán cơ sở, phái sinh và các luồng giao dịch.
- Giữ lớp provider-compatible hiện có cho Quote, Listing, Company, Finance, Trading để không làm vỡ hệ sinh thái KBS/VCI/TCBS/AUTO.
- Tách riêng broker lane và provider lane để không lẫn credential, token, session, logging và retry behavior.
- Thêm portfolio domain thực thụ cho holdings, cost basis, PnL, return metrics và reconciliation thay vì chỉ dùng snapshot thị trường.
- Cưỡng chế security-first qua redaction, audit trail, idempotency và write gates.

---

## Định nghĩa done ở mức chương trình

- [ ] Có broker lane riêng cho TCBS, không đi qua generic provider flow ở các đường chứa secret hoặc write.
- [ ] Có public entrypoint mới cho broker, tách khỏi `Vnbroker.stock(...)`.
- [ ] Không còn secret-bearing payload đi qua logger generic hiện hữu.
- [ ] TCBS public provider parity được nâng lên mức native tối thiểu cho Listing và tương thích tốt hơn cho Quote, Company, Finance.
- [ ] Portfolio domain có ledger và reconciliation, không chỉ đọc snapshot thô.
- [ ] Unit tests, contract tests, docs, audit file và module tree được cập nhật đầy đủ.

---

## Tài liệu liên quan nên đọc thêm

| File | Vai trò |
|---|---|
| [DNSE_BROKER_PLATFORM_RFC.md](DNSE_BROKER_PLATFORM_RFC.md) | Blueprint tham chiếu cho connector/bridge/app integration |
| [DNSE_IMPLEMENTATION_EXECUTION_PLAYBOOK.md](DNSE_IMPLEMENTATION_EXECUTION_PLAYBOOK.md) | Mẫu quy trình thực thi đã được chấp nhận trong repo |
| [DNSE_SPRINT_TASK_BOARD.md](DNSE_SPRINT_TASK_BOARD.md) | Mẫu task board slice-by-slice |
| [CENTRAL_MODIFIED_FILES_AUDIT.md](CENTRAL_MODIFIED_FILES_AUDIT.md) | Audit log tập trung bắt buộc phải append sau mỗi slice |
| [VNBROKER_USAGE_GUIDE.md](VNBROKER_USAGE_GUIDE.md) | Bản đồ public API hiện tại cần giữ tương thích |
