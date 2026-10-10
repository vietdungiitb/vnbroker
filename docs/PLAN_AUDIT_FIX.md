# PLAN AUDIT — VNBROKER-FIX-v1

- **Auditor:** PM + System Designer + Tech Lead
- **Ngày:** 2026-10-08
- **Plan file:** `docs/PLAN_FIX_v1.md`
- **Verdict:** `PASS`

## 1. Đánh giá tổng thể

| Tiêu chí | Đánh giá | Ghi chú |
|:---|:---|:---|
| Mục tiêu rõ ràng | ✅ | 9 mục tiêu cụ thể, đo lường được |
| In-scope chi tiết | ✅ | 6 WP, mỗi WP có file glob cụ thể |
| Non-goals rõ ràng | ✅ | 5 mục bị cấm |
| Claim disjoint | ✅ | check-overlap.cjs exit 0 |
| Cách kiểm chứng | ✅ | 4 lệnh với exit code cụ thể |
| Rollback | ✅ | Lệnh cụ thể, verify được |
| Rủi ro | ✅ | 4 rủi ro với giảm thiểu |
| Điều kiện Done | ✅ | 8 điều kiện verify được |

## 2. Phân tích từng WP

### WP-1: Fix Cache Key + Test Fail

| Tiêu chí | Đánh giá |
|:---|:---|
| File set rời nhau | ✅ `cache.py` + test |
| Khả năng | ✅ Sửa `_make_key` để không dùng `id()` |
| Rủi ro | ⚠️ Có thể break existing tests |
| Giảm thiểu | ✅ Chạy test suite sau khi sửa |

### WP-2: Fix Source Router + News Provider

| Tiêu chí | Đánh giá |
|:---|:---|
| File set rời nhau | ✅ `source_router.py`, `data.py` + test |
| Khả năng | ✅ Sửa PRIMARY_SOURCE_POOLS, sửa News |
| Rủi ro | ⚠️ Có thể ảnh hưởng failover |
| Giảm thiểu | ✅ Test failover |

### WP-3: Add Tests for 0% Coverage Modules

| Tiêu chí | Đánh giá |
|:---|:---|
| File set rời nhau | ✅ 3 test files mới |
| Khả năng | ✅ Test MarketSnapshot, Stream, broker API |
| Rủi ro | ⚠️ Test có thể fail |
| Giảm thiểu | ✅ Mock-based tests |

### WP-4: Fix Mypy + Ruff Errors

| Tiêu chí | Đánh giá |
|:---|:---|
| File set rời nhau | ✅ 4 file API |
| Khả năng | ✅ Thêm type hints, xóa unused imports |
| Rủi ro | ⚠️ Type hints có thể break runtime |
| Giảm thiểu | ✅ Chạy test suite |

### WP-5: Add fetch_multiple for DNSE/SSI

| Tiêu chí | Đánh giá |
|:---|:---|
| File set rời nhau | ✅ 2 explorer files + 2 test files |
| Khả năng | ✅ Thêm classmethod fetch_multiple |
| Rủi ro | ⚠️ Không hoạt động với provider thật |
| Giảm thiểu | ✅ Mock test |

### WP-6: Rate Limiting Client-Side

| Tiêu chí | Đánh giá |
|:---|:---|
| File set rời nhau | ✅ `rate_limiter.py` + `client.py` + test |
| Khả năng | ✅ Token bucket rate limiter |
| Rủi ro | ⚠️ Ảnh hưởng performance |
| Giảm thiểu | ✅ Benchmark |

## 3. Kiểm chứng độc lập

### 3.1 File set disjoint

```bash
node check-overlap.cjs --file docs/CLAIMS.md
# Exit 0 — không chồng lấn
```

### 3.2 Import chain

```
WP-1: cache.py (standalone)
WP-2: source_router.py, data.py (existing)
WP-3: test files (standalone)
WP-4: api/company.py, api/snapshot.py, api/broker.py, api/stream.py (existing)
WP-5: explorer/dnse/quote.py, explorer/ssi/quote.py (existing)
WP-6: rate_limiter.py (new), client.py (existing)
```

→ Không có phụ thuộc chéo giữa các WP. ✅

### 3.3 Test coverage

- WP-1: `tests/unit/core/test_cache_key.py` (mới)
- WP-2: `tests/unit/core/test_source_router_fix.py` (mới)
- WP-3: `tests/unit/api/test_snapshot.py`, `test_stream.py`, `test_broker_api.py` (mới)
- WP-4: Không thêm test (chỉ sửa code)
- WP-5: `tests/unit/explorer/test_dnse_fetch_multiple.py`, `test_ssi_fetch_multiple.py` (mới)
- WP-6: `tests/unit/core/test_rate_limiter.py` (mới)

→ Tổng 8 test files mới. ✅

## 4. Rủi ro kỹ thuật

| Rủi ro | Mức độ | Giảm thiểu |
|:---|:---|:---|
| Cache fix break tests | Trung bình | Chạy test suite sau khi sửa |
| Type hints break runtime | Thấp | Chạy test suite |
| fetch_multiple không hoạt động | Trung bình | Mock test |
| Rate limiter ảnh hưởng performance | Thấp | Benchmark |

## 5. Kết luận

**Verdict: `PASS`**

Plan đã đủ chi tiết, file set rời nhau tuyệt đối, có gate verify được, rủi ro có giảm thiểu. Có thể proceed sang Stage 3 (Claim) và Stage 4 (Code).

**Điều kiện tiên quyết:**
- [x] File set disjoint (check-overlap.cjs exit 0)
- [x] Import chain rõ ràng
- [x] Test coverage đủ
- [x] Rủi ro có giảm thiểu
- [x] Baseline: 1072 passed, 6 skipped

**Lưu ý:**
- WP-1 và WP-3 là P0, ưu tiên cao nhất
- WP-6 có thể chạy song song với WP-1→5
- Cần chạy `pytest tests/unit tests/contract` sau khi merge mỗi WP
