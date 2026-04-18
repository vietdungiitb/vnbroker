# Sprint Plan - Core API Standardization

> Khung thời gian: 20 ngày làm việc
>
> Team đề xuất: 1 Tech Lead, 2 Core Engineer, 2 Provider Engineer, 1 QA, 1 Docs

---

## Sprint 0 (Day 1-2): Contract lock

Mục tiêu:
- Chốt API contract, schema, capability matrix, error model.

Deliverables:
- RFC được approve.
- Danh sách method chuẩn và alias migration.
- Checklist test contract.

Gate:
- Không qua Sprint 1 nếu chưa sign-off RFC.

---

## Sprint 1 (Day 3-6): Insider chuẩn hoá xuyên provider

Mục tiêu:
- Expose `insider_deals` đồng nhất cho provider có hỗ trợ.

Công việc:
- Tạo alias KBS: `insider_deals -> insider_trading`.
- Chuẩn hoá schema insider chung.
- Bổ sung capability cho từng provider.
- Cập nhật facade để gọi method chuẩn.

Deliverables:
- API insider chạy ổn với source cố định và AUTO.
- Unit test mapping/alias pass.

Gate:
- Schema insider có đủ cột bắt buộc.

---

## Sprint 2 (Day 7-11): Financial chuẩn hoá + snapshot

Mục tiêu:
- Đồng nhất output cho 4 method tài chính cốt lõi.

Công việc:
- Chuẩn hoá cột/đơn vị/period naming.
- Bổ sung `fundamental_snapshot`.
- Gắn metadata `source` và `source_used`.

Deliverables:
- Financial API có schema nhất quán.
- Snapshot chạy cho KBS/VCI/TCBS theo capability.

Gate:
- Contract test cross-provider đạt chuẩn.

---

## Sprint 3 (Day 12-16): Industry comparison API

Mục tiêu:
- Cung cấp API so sánh ngành dùng được ngay cho dashboard/robo-advisor.

Công việc:
- Implement `industry_peers`.
- Implement `industry_benchmark`.
- Implement `industry_rank`.
- Tối ưu: projection trước, vectorized computation sau.

Deliverables:
- API trả kết quả benchmark/rank nhất quán.

Gate:
- Kết quả tính percentile, zscore, rank hợp lệ.

---

## Sprint 4 (Day 17-18): Provider onboarding framework

Mục tiêu:
- Chuẩn hoá đường thêm provider mới với thay đổi tối thiểu.

Công việc:
- Tạo template capability manifest.
- Tạo template schema mapping.
- Viết onboarding checklist.

Deliverables:
- Onboarding provider mới không cần sửa code lõi.

Gate:
- Mock provider mới onboard thành công theo checklist.

---

## Sprint 5 (Day 19-20): Hardening + Release readiness

Mục tiêu:
- Đảm bảo ổn định trước khi merge/release.

Công việc:
- Integration + regression suite.
- Cập nhật docs usage/migration.
- Chốt release notes nội bộ.

Deliverables:
- Full test pass.
- Tài liệu đầy đủ cho handoff.

Gate:
- QA sign-off và Tech Lead sign-off.

---

## Risk register

1. Lệch schema giữa provider
- Giảm thiểu: mapping layer riêng, contract test bắt buộc.

2. AUTO failover làm đổi schema
- Giảm thiểu: normalization chạy sau fetch, trước return.

3. Provider thiếu field quan trọng
- Giảm thiểu: bắt buộc null-safe + cột bắt buộc luôn tồn tại.

4. Khối lượng task lớn trong 20 ngày
- Giảm thiểu: ưu tiên Insider + Financial trước Industry.

---

## Quy tắc merge

- Mọi PR bắt buộc có:
  - Cập nhật test liên quan
  - Cập nhật docs liên quan
  - Cập nhật file audit tập trung
