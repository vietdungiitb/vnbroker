# PLAN AUDIT — TIER1-ENGINE-v1

- **Auditor:** Team Code Leader (Hermes Agent)
- **Ngày:** 2026-10-05
- **Plan file:** `docs/PLAN_TIER1_ENGINE.md`
- **Verdict:** `PASS`

## 1. Đánh giá tổng thể

| Tiêu chí | Đánh giá | Ghi chú |
|:---|:---|:---|
| Mục tiêu rõ ràng | ✅ | 6 mục tiêu cụ thể, đo lường được |
| In-scope chi tiết | ✅ | 5 WP, mỗi WP có file glob cụ thể |
| Non-goals rõ ràng | ✅ | 7 mục bị cấm |
| Claim disjoint | ✅ | check-overlap.cjs exit 0 |
| Cách kiểm chứng | ✅ | 5 lệnh với exit code cụ thể |
| Rollback | ✅ | Lệnh cụ thể, verify được |
| Rủi ro | ✅ | 5 rủi ro với giảm thiểu |
| Điều kiện Done | ✅ | 6 điều kiện verify được |

## 2. Phân tích từng WP

### WP-1: Connection Pool

| Tiêu chí | Đánh giá |
|:---|:---|
| File set rời nhau | ✅ `client.py` + `connection_pool.py` + test |
| Khả năng | ✅ `requests.Session` thread-safe, `HTTPAdapter` hỗ trợ pool |
| Rủi ro | ⚠️ `client.py` được import rộng rãi — cần test kỹ |
| Giảm thiểu | ✅ Test riêng trước khi tích hợp |

### WP-2: Failover + Bulk Normalizer

| Tiêu chí | Đánh giá |
|:---|:---|
| File set rời nhau | ✅ `data.py` + `normalizer.py` + 2 test files |
| Khả năng | ✅ `_auto_sources` đã có logic, chỉ cần set |
| Rủi ro | ⚠️ `data.py` là file lớn (1743 dòng) — cần cẩn thận |
| Giảm thiểu | ✅ Test contract + unit |

### WP-3: Bulk Router + Health Router

| Tiêu chí | Đánh giá |
|:---|:---|
| File set rời nhau | ✅ 2 file mới + 1 test |
| Khả năng | ✅ `source_router.py` đã có health store |
| Rủi ro | ⚠️ Multi-provider concurrency cần test kỹ |
| Giảm thiểu | ✅ Test riêng |

### WP-4: Provider Pool

| Tiêu chí | Đánh giá |
|:---|:---|
| File set rời nhau | ✅ 1 file mới + 1 test |
| Khả năng | ✅ Env detection đơn giản |
| Rủi ro | ⚠️ Auth providers có thể không ổn định |
| Giảm thiểu | ✅ Health router loại tự động |

### WP-5: API Integration

| Tiêu chí | Đánh giá |
|:---|:---|
| File set rời nhau | ✅ `ui/market.py` + `api/bulk.py` + test |
| Khả năng | ✅ Cần WP-1→4 xong |
| Rủi ro | ⚠️ Phụ thuộc WP-1→4 |
| Giảm thiểu | ✅ Chạy tuần tự sau batch 1 |

## 3. Kiểm chứng độc lập

### 3.1 File set disjoint

```bash
node check-overlap.cjs --file docs/CLAIMS.md
# Exit 0 — không chồng lấn
```

### 3.2 Import chain

```
WP-1: client.py ← connection_pool.py (mới)
WP-2: data.py ← normalizer.py (mới), source_router.py (existing)
WP-3: bulk_router.py ← health_router.py (mới), source_router.py (existing)
WP-4: provider_pool.py (mới)
WP-5: ui/market.py ← api/bulk.py ← bulk_router.py, provider_pool.py
```

→ WP-5 phụ thuộc WP-1→4, chạy tuần tự sau batch 1. ✅

### 3.3 Test coverage

- WP-1: `tests/unit/core/test_connection_pool.py` (mới)
- WP-2: `tests/contract/test_failover_integration.py` + `tests/unit/common/test_bulk_normalizer.py` (mới)
- WP-3: `tests/unit/core/test_bulk_router.py` (mới)
- WP-4: `tests/unit/core/test_provider_pool.py` (mới)
- WP-5: `tests/unit/api/test_bulk_api.py` (mới)

→ Tổng 6 test files mới, cover đủ 5 WP. ✅

## 4. Rủi ro kỹ thuật

| Rủi ro | Mức độ | Giảm thiểu |
|:---|:---|:---|
| `client.py` break → cả repo fail | Cao | Test riêng trước khi tích hợp |
| `data.py` merge conflict | Trung bình | Patch từng phần, không ghi đè |
| Multi-provider race condition | Trung bình | ThreadPoolExecutor + as_completed |
| Auth provider không ổn định | Trung bình | Health router loại tự động |
| Test mới fail | Trung bình | Chạy test riêng trước |

## 5. Kết luận

**Verdict: `PASS`**

Plan đã đủ chi tiết, file set rời nhau tuyệt đối, có gate verify được, rủi ro có giảm thiểu. Có thể proceed sang Stage 3 (Claim) và Stage 4 (Code).

**Điều kiện tiên quyết:**
- [x] File set disjoint (check-overlap.cjs exit 0)
- [x] Import chain rõ ràng
- [x] Test coverage đủ
- [x] Rủi ro có giảm thiểu
- [x] Baseline commit: `e2c9c4a`

**Lưu ý:**
- WP-1 và WP-2 là P0, ưu tiên cao nhất
- WP-5 chạy tuần tự sau batch 1
- Cần chạy `pytest tests/unit tests/contract` trước khi dispatch để confirm baseline
