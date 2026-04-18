# Test Plan và Acceptance Criteria - Core API Standardization

---

## 1) Mục tiêu test

- Đảm bảo contract API đồng nhất xuyên provider.
- Đảm bảo AUTO failover không làm vỡ schema.
- Đảm bảo backward compatibility trong giai đoạn chuyển đổi.

---

## 2) Test strategy

### 2.1 Unit tests

Phạm vi:
- Mapping raw -> normalized schema.
- Alias compatibility (`insider_deals`/`insider_trading`).
- Null-safe cho field thiếu.
- Kiểm tra parse period/metric.

### 2.2 Contract tests

Phạm vi:
- Mỗi method chuẩn trả đủ cột bắt buộc.
- Kiểu dữ liệu cột trọng yếu đúng (datetime/numeric/string).
- Metadata `source` và `source_used` tồn tại.

### 2.3 Integration tests

Phạm vi:
- Chạy source cố định KBS/VCI/TCBS.
- Chạy `AUTO` trong điều kiện provider success/failure.

### 2.4 Regression tests

Phạm vi:
- Các API cũ vẫn chạy được.
- Không phá module unrelated (quote, news, snapshot).

---

## 3) Bộ test tối thiểu theo module

### Insider

- Test alias method tồn tại ở provider KBS.
- Test output có đủ cột chuẩn insider.
- Test filter date range và actor_type.
- Test behavior khi provider không có dữ liệu.

### Financial

- Test period `quarter`/`year`/`annual`.
- Test schema chuẩn cho 4 method tài chính.
- Test `fundamental_snapshot` với metrics subset.

### Industry comparison

- Test `industry_peers` trả peer list không trùng.
- Test `industry_benchmark` trả median/mean hợp lệ.
- Test `industry_rank` trả rank từ 1..N, percentile 0..100.

---

## 4) Acceptance Criteria (Go/No-Go)

1. Contract pass rate: 100%.
2. Integration pass rate: >= 95% (network flake được retry theo policy).
3. Regression critical defects: 0.
4. Performance baseline:
- Benchmark API mới không chậm hơn > 20% so với baseline tương ứng.
5. Documentation complete:
- API docs, migration notes, audit file cập nhật.

---

## 5) Release checklist

1. RFC status = Approved.
2. Sprint deliverables hoàn tất.
3. QA sign-off.
4. Tech Lead sign-off.
5. Changelog + audit files cập nhật.

---

## 6) Post-release monitoring

- Theo dõi error code distribution 72h đầu.
- Theo dõi tỉ lệ fallback AUTO.
- Theo dõi schema validation failure.
