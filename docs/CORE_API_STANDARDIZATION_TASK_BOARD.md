# Task Board theo ngày - Giao việc thực thi ngay

> Dùng trực tiếp cho daily standup và tracking delivery.

---

## Day 1

- Chốt danh sách API public chuẩn.
- Chốt schema cột bắt buộc cho 3 nhóm dữ liệu.
- Chốt error code và format lỗi.

Acceptance:
- RFC được duyệt bởi Tech Lead + QA Lead.

## Day 2

- Chốt capability matrix cho KBS/VCI/TCBS.
- Chốt backward compatibility policy.
- Chốt kế hoạch alias migration.

Acceptance:
- Có bảng capability đầy đủ theo method.

## Day 3

- Tạo normalization module cho Insider.
- Viết mapping thô cho TCBS insider.

Acceptance:
- TCBS insider trả schema chuẩn tối thiểu.

## Day 4

- Viết alias KBS insider_deals.
- Chuẩn hoá mapping KBS insider.

Acceptance:
- KBS + TCBS pass contract test Insider.

## Day 5

- Nối Insider vào facade + adapter.
- Cập nhật router dùng capability.

Acceptance:
- `source=AUTO` và source cố định đều trả ổn.

## Day 6

- Viết unit test Insider (schema, alias, null-safe).
- Viết integration test Insider.

Acceptance:
- Test Insider pass 100%.

## Day 7

- Tạo normalization module Financial.
- Chuẩn period mapping (`year`, `quarter`, `annual`).

Acceptance:
- Financial chuẩn period naming.

## Day 8

- Mapping `balance_sheet` + `income_statement` cho KBS/VCI/TCBS.

Acceptance:
- 3 provider trả schema cột bắt buộc.

## Day 9

- Mapping `cash_flow` + `ratio` cho KBS/VCI/TCBS.

Acceptance:
- Các field numeric được cast thống nhất.

## Day 10

- Implement `fundamental_snapshot`.
- Bổ sung metadata `source`/`source_used`.

Acceptance:
- Snapshot chạy ít nhất 2 provider.

## Day 11

- Financial contract test + integration test.
- Tối ưu xử lý dữ liệu vectorized.

Acceptance:
- Bộ test Financial pass.

## Day 12

- Implement `industry_peers` từ listing/ICB mapping.

Acceptance:
- Trả danh sách peers hợp lệ cho symbol mẫu.

## Day 13

- Implement `industry_benchmark`.
- Tính median/mean cho metric được chọn.

Acceptance:
- Benchmark trả đúng schema.

## Day 14

- Implement `industry_rank`.
- Tính percentile, zscore, rank.

Acceptance:
- Rank đúng khi test dữ liệu mẫu.

## Day 15

- Null-safe + edge-case handling ngành trống.
- Chuẩn hoá hành vi fallback.

Acceptance:
- Không crash với dữ liệu thiếu ngành.

## Day 16

- Contract/integration test cho Industry API.

Acceptance:
- Bộ test Industry pass.

## Day 17

- Tạo capability manifest template.
- Tạo schema mapping template cho provider mới.

Acceptance:
- Có bộ template onboarding đầy đủ.

## Day 18

- Dry-run onboarding mock provider.

Acceptance:
- Onboard mock provider không sửa code lõi.

## Day 19

- Regression full suite.
- Cập nhật docs usage và migration.

Acceptance:
- Không có regression critical.

## Day 20

- Release readiness checklist.
- Handoff tài liệu + kết quả test cho đội vận hành.

Acceptance:
- QA sign-off + Tech Lead sign-off.

---

## Nhóm công việc song song đề xuất

- Track A (Core): adapter, normalization, router integration.
- Track B (Provider): mapping KBS/VCI/TCBS.
- Track C (QA): contract + integration + regression.
- Track D (Docs): API guide + migration + audit log.
