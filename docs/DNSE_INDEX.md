# DNSE Integration Documentation Index

Bộ tài liệu này được thiết kế để đội code có thể thực hiện và không cần hỏi lại, có audit minh chứng.  
**Cập nhật lần cuối:** 2026-05-08 (đồng bộ live contract, benchmark intraday/price_depth, audit cập nhật, thêm RFC chiến lược broker, thêm ma trận so sánh provider)

---

## Luồng đọc tài liệu — Đội dev mới bắt đầu

### Bước 1 — Nắm bức tranh tổng thể (30 phút)

| Thứ tự | File | Mục đích |
|---|---|---|
| 0 | [DNSE_BROKER_PLATFORM_RFC.md](DNSE_BROKER_PLATFORM_RFC.md) | Đề xuất chiến lược: vì sao DNSE nên trở thành broker platform thay vì chỉ provider dữ liệu |
| 1 | [DNSE_INTEGRATION_PLAN_20260507.md](DNSE_INTEGRATION_PLAN_20260507.md) | Master plan tích hợp DNSE, scope A/B/C, thứ tự slices S1-S11 |
| 2 | [DNSE_MODULE_STRUCTURE.md](DNSE_MODULE_STRUCTURE.md) | Cấu trúc module connector/dnse đã hoàn chỉnh |
| 3 | [DNSE_API_CONTRACT.md](DNSE_API_CONTRACT.md) | Hợp đồng API: endpoints, auth, request/response schema, ghi chú live smoke |
| 3.1 | [DNSE_PROVIDER_COMPARISON_MATRIX.md](DNSE_PROVIDER_COMPARISON_MATRIX.md) | Ma trận so sánh DNSE / VCI / KBS / TCBS theo từng public function |

### Bước 2 — Đọc spec kỹ thuật trước khi code (45 phút)

| Thứ tự | File | Mục đích |
|---|---|---|
| 4 | [DNSE_EXPLORER_SPEC.md](DNSE_EXPLORER_SPEC.md) | **Spec chính:** exact class, exact method, exact schema — đọc kỹ trước khi code |
| 5 | [DNSE_CODING_GUIDE.md](DNSE_CODING_GUIDE.md) | Hướng dẫn từng bước, code mẫu, common pitfalls, checklist trước commit |

### Bước 3 — Viết test (30 phút)

| Thứ tự | File | Mục đích |
|---|---|---|
| 6 | [DNSE_TEST_SPEC_V2.md](DNSE_TEST_SPEC_V2.md) | Test spec đầy đủ: unit test code sẵn, integration test, fixtures, KPI, phản ánh contract live |

### Bước 4 — Audit & sign-off trước merge

| Thứ tự | File | Mục đích |
|---|---|---|
| 7 | [DNSE_AUDIT_CHECKLIST.md](DNSE_AUDIT_CHECKLIST.md) | Checklist 40+ mục, có lệnh kiểm tra cụ thể, form sign-off |

---

## Tài liệu tham khảo bổ sung

| File | Mục đích |
|---|---|
| [DNSE_IMPLEMENTATION_WORKFLOW.md](DNSE_IMPLEMENTATION_WORKFLOW.md) | Workflow thực hiện ban đầu (Sprint 2026-04-13) |
| [DNSE_BROKER_PLATFORM_RFC.md](DNSE_BROKER_PLATFORM_RFC.md) | Đề xuất chiến lược broker platform cho DNSE và ứng dụng |
| [DNSE_PROVIDER_COMPARISON_MATRIX.md](DNSE_PROVIDER_COMPARISON_MATRIX.md) | Bảng so sánh 4 provider theo public function và DNSE-only extension |
| [DNSE_TEST_PLAN.md](DNSE_TEST_PLAN.md) | Test plan gốc từ sprint trước |
| [DNSE_E2E_RUNBOOK.md](DNSE_E2E_RUNBOOK.md) | Runbook E2E cho Trading API, có ghi chú live gap trades |
| [DNSE_HANDOFF_20260413.md](DNSE_HANDOFF_20260413.md) | Handoff notes từ sprint 2026-04-13 |
| [DNSE_DELIVERY_REPORT_20260413.md](DNSE_DELIVERY_REPORT_20260413.md) | Báo cáo giao hàng connector/dnse |

---

## Mục tiêu

- Tích hợp DNSE OpenAPI vào vnstock với API thống nhất (ngang hàng VCI/TCBS/KBS).
- Tách module theo file riêng, tránh fat file.
- Hỗ trợ đầy đủ 3 nhóm nghiệp vụ:
  - **Market Data:** OHLC history, intraday trades, security definition, instruments listing.
  - **Account:** thông tin tài khoản, số dư, vị thế, gói margin.
  - **Trading:** đặt/sửa/huỷ lệnh với trading token (OTP xác thực).

---

## Định nghĩa done cho toàn bộ scope

- [ ] Explorer layer: `vnstock/explorer/dnse/` hoạt động, registered vào ProviderRegistry
- [ ] `StockComponents(symbol, source='DNSE')` hoạt động end-to-end
- [ ] `Vnstock().stock(symbol, source='DNSE', api_key=..., api_secret=...)` hoạt động
- [ ] `trade.py` không còn `print()`, có `as_openapi_client()` và `login_and_get_trading_session()`
- [ ] Unit tests pass 100%, coverage ≥ 80%
- [ ] Integration tests pass ≥ 95% (với env có key thật)
- [ ] Audit checklist hoàn thành, không có ❌ FAIL
- [ ] Tất cả doc file đã được cập nhật
