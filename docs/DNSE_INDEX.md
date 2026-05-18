# DNSE Integration Documentation Index

Bộ tài liệu này được thiết kế để đội code có thể thực hiện và không cần hỏi lại, có audit minh chứng.  
**Cập nhật lần cuối:** 2026-05-08 (thêm bộ tài liệu triển khai cho đội code: sprint task board, slice DoD, audit checklist V2 — bổ sung phần I–L, form sign-off 3 vai trò)

---

## Luồng đọc tài liệu — Đội dev mới bắt đầu

### Bước 1 — Nắm bức tranh tổng thể (30 phút)

| Thứ tự | File | Mục đích |
|---|---|---|
| 0 | [DNSE_BROKER_PLATFORM_RFC.md](DNSE_BROKER_PLATFORM_RFC.md) | Đề xuất chiến lược: vì sao DNSE nên trở thành broker platform thay vì chỉ provider dữ liệu |
| 1 | [DNSE_INTEGRATION_PLAN_20260507.md](DNSE_INTEGRATION_PLAN_20260507.md) | Master plan tích hợp DNSE, scope A/B/C, thứ tự slices S1-S11 |
| 2 | [DNSE_MODULE_STRUCTURE.md](DNSE_MODULE_STRUCTURE.md) | Cấu trúc module connector/dnse đã hoàn chỉnh |
| 3 | [DNSE_API_CONTRACT.md](DNSE_API_CONTRACT.md) | Hợp đồng API: endpoints, auth, request/response schema, ghi chú live smoke |
| 3.0 | [DNSE_TAPE_API_GUIDE.md](DNSE_TAPE_API_GUIDE.md) | **Hướng dẫn lập trình viên:** sử dụng intraday tape (lịch sử, phân trang, timezone) |
| 3.1 | [DNSE_PROVIDER_COMPARISON_MATRIX.md](DNSE_PROVIDER_COMPARISON_MATRIX.md) | Ma trận so sánh DNSE / VCI / KBS / TCBS theo từng public function |
| 3.2 | [DNSE_PROVIDER_DECISION_GUIDE.md](DNSE_PROVIDER_DECISION_GUIDE.md) | Hướng dẫn chọn provider theo mục tiêu dự án và mức portable/broker-fit |
| 3.3 | [DNSE_PROJECT_FINAL_RECOMMENDATION.md](DNSE_PROJECT_FINAL_RECOMMENDATION.md) | Tài liệu chốt cuối cùng cho dự án trước khi quyết định |
| 3.4 | [DNSE_EXECUTIVE_DECISION_BRIEF.md](DNSE_EXECUTIVE_DECISION_BRIEF.md) | Bản 1 trang để ra quyết định nhanh |
| 3.5 | [DNSE_IMPLEMENTATION_EXECUTION_PLAYBOOK.md](DNSE_IMPLEMENTATION_EXECUTION_PLAYBOOK.md) | Quy trình triển khai chuẩn cho đội code, không cần hỏi lại |
| 3.6 | [DNSE_SPRINT_TASK_BOARD.md](DNSE_SPRINT_TASK_BOARD.md) | Task board S1–S11: trạng thái, người làm, checklist từng slice, bảng tracking |
| 3.7 | [DNSE_SLICE_DEFINITION_OF_DONE.md](DNSE_SLICE_DEFINITION_OF_DONE.md) | Definition of Done từng slice: validation commands + mẫu ghi evidence |

### Bước 2 — Đọc spec kỹ thuật trước khi code (45 phút)

| Thứ tự | File | Mục đích |
|---|---|---|
| 4 | [DNSE_EXPLORER_SPEC.md](DNSE_EXPLORER_SPEC.md) | **Spec chính:** exact class, exact method, exact schema — đọc kỹ trước khi code |
| 5 | [DNSE_CODING_GUIDE.md](DNSE_CODING_GUIDE.md) | Hướng dẫn từng bước, code mẫu, common pitfalls, checklist trước commit |

### Bước 3 — Viết test (30 phút)

| Thứ tự | File | Mục đích |
|---|---|---|
| 6 | [DNSE_TEST_SPEC_V2.md](DNSE_TEST_SPEC_V2.md) | Test spec đầy đủ: unit test code sẵn, integration test, fixtures, KPI, phản ánh contract live |
| 6.1 | [DNSE_TEST_AND_AUDIT_EVIDENCE_PROTOCOL.md](DNSE_TEST_AND_AUDIT_EVIDENCE_PROTOCOL.md) | Quy trình thu thập test evidence và audit evidence cho từng slice |

### Bước 4 — Audit & sign-off trước merge

| Thứ tự | File | Mục đích |
|---|---|---|
| 7 | [DNSE_AUDIT_CHECKLIST.md](DNSE_AUDIT_CHECKLIST.md) | Checklist 40+ mục V1, có lệnh kiểm tra cụ thể, form sign-off |
| 7.1 | [DNSE_AUDIT_CHECKLIST_V2.md](DNSE_AUDIT_CHECKLIST_V2.md) | **Checklist V2 (dùng cho sprint này):** 12 phần A–L, có cột minh chứng thực tế, form sign-off 3 vai trò |

---

## Tài liệu tham khảo bổ sung

| File | Mục đích |
|---|---|
| [DNSE_IMPLEMENTATION_WORKFLOW.md](DNSE_IMPLEMENTATION_WORKFLOW.md) | Workflow thực hiện ban đầu (Sprint 2026-04-13) |
| [DNSE_BROKER_PLATFORM_RFC.md](DNSE_BROKER_PLATFORM_RFC.md) | Đề xuất chiến lược broker platform cho DNSE và ứng dụng |
| [DNSE_PROVIDER_COMPARISON_MATRIX.md](DNSE_PROVIDER_COMPARISON_MATRIX.md) | Bảng so sánh 4 provider theo public function và DNSE-only extension |
| [DNSE_PROVIDER_DECISION_GUIDE.md](DNSE_PROVIDER_DECISION_GUIDE.md) | Khuyến nghị chọn provider theo use case và tiêu chí ra quyết định |
| [DNSE_PROJECT_FINAL_RECOMMENDATION.md](DNSE_PROJECT_FINAL_RECOMMENDATION.md) | Tài liệu chốt cuối cùng cho dự án trước khi quyết định |
| [DNSE_EXECUTIVE_DECISION_BRIEF.md](DNSE_EXECUTIVE_DECISION_BRIEF.md) | Bản một trang để chốt quyết định nhanh |
| [DNSE_IMPLEMENTATION_EXECUTION_PLAYBOOK.md](DNSE_IMPLEMENTATION_EXECUTION_PLAYBOOK.md) | Playbook triển khai cho đội code, khóa quy trình và thứ tự thực hiện |
| [DNSE_SPRINT_TASK_BOARD.md](DNSE_SPRINT_TASK_BOARD.md) | Task board S1–S11: trạng thái, checklist, bảng tracking, scope in/out, DoD sprint |
| [DNSE_SLICE_DEFINITION_OF_DONE.md](DNSE_SLICE_DEFINITION_OF_DONE.md) | DoD từng slice với validation commands và mẫu ghi evidence |
| [DNSE_AUDIT_CHECKLIST_V2.md](DNSE_AUDIT_CHECKLIST_V2.md) | Audit checklist V2: phần A–L, cột bằng chứng thực tế, form sign-off 3 vai trò |
| [DNSE_TEST_AND_AUDIT_EVIDENCE_PROTOCOL.md](DNSE_TEST_AND_AUDIT_EVIDENCE_PROTOCOL.md) | Protocol ghi minh chứng test/audit cho mọi slice |
| [DNSE_TEST_PLAN.md](DNSE_TEST_PLAN.md) | Test plan gốc từ sprint trước |
| [DNSE_E2E_RUNBOOK.md](DNSE_E2E_RUNBOOK.md) | Runbook E2E cho Trading API, có ghi chú live gap trades |
| [DNSE_HANDOFF_20260413.md](DNSE_HANDOFF_20260413.md) | Handoff notes từ sprint 2026-04-13 |
| [DNSE_DELIVERY_REPORT_20260413.md](DNSE_DELIVERY_REPORT_20260413.md) | Báo cáo giao hàng connector/dnse |

---

## Mục tiêu

- Tích hợp DNSE OpenAPI vào vnbroker với API thống nhất (ngang hàng VCI/TCBS/KBS).
- Tách module theo file riêng, tránh fat file.
- Hỗ trợ đầy đủ 3 nhóm nghiệp vụ:
  - **Market Data:** OHLC history, intraday trades, security definition, instruments listing.
  - **Account:** thông tin tài khoản, số dư, vị thế, gói margin.
  - **Trading:** đặt/sửa/huỷ lệnh với trading token (OTP xác thực).

---

## Định nghĩa done cho toàn bộ scope

- [ ] Explorer layer: `vnbroker/explorer/dnse/` hoạt động, registered vào ProviderRegistry
- [ ] `StockComponents(symbol, source='DNSE')` hoạt động end-to-end
- [ ] `vnbroker().stock(symbol, source='DNSE', api_key=..., api_secret=...)` hoạt động
- [ ] `trade.py` không còn `print()`, có `as_openapi_client()` và `login_and_get_trading_session()`
- [ ] Unit tests pass 100%, coverage ≥ 80%
- [ ] Integration tests pass ≥ 95% (với env có key thật)
- [ ] Audit checklist hoàn thành, không có ❌ FAIL
- [ ] Tất cả doc file đã được cập nhật
