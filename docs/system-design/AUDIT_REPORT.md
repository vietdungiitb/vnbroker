# AUDIT REPORT — vnbroker codebase

- **Ngày:** 2026-10-08
- **Auditor:** PM + System Designer
- **Phạm vi:** Toàn bộ `vnbroker/` (211 file, 52.188 dòng)
- **Phương pháp:** Coverage analysis, mypy, ruff, test execution

---

## 1. TỔNG QUAN

| Chỉ số | Giá trị | Đánh giá |
|:---|:---|:---|
| Test coverage | **55%** | ⚠️ Thấp |
| Tests pass | **1071 passed, 1 failed** | ⚠️ Có lỗi |
| Mypy errors | **10+ errors** | ⚠️ Type safety kém |
| Ruff errors | **4 errors** | ⚠️ Cint issues |
| Module 0% coverage | **15+ modules** | ❌ Critical |

---

## 2. TEST COVERAGE

### 2.1 Coverage theo module

| Module | Coverage | Đánh giá |
|:---|:---|:---|
| `vnbroker/analytics/` | 96% | ✅ Tốt |
| `vnbroker/ui/` | 100% | ✅ Tốt |
| `vnbroker/news/` | 87-100% | ✅ Tốt |
| `vnbroker/core/utils/connection_pool.py` | 100% | ✅ Tốt |
| `vnbroker/core/health_router.py` | 100% | ✅ Tốt |
| `vnbroker/common/data.py` | 70% | ⚠️ Trung bình |
| `vnbroker/api/bulk.py` | 64% | ⚠️ Trung bình |
| `vnbroker/explorer/vci/quote.py` | 41% | ❌ Thấp |
| `vnbroker/explorer/vci/stream.py` | 18% | ❌ Thấp |
| `vnbroker/broker/tcbs/money.py` | 40% | ❌ Thấp |
| `vnbroker/connector/dnse/trade.py` | 30% | ❌ Thấp |
| `vnbroker/api/snapshot.py` | 0% | ❌ Critical |
| `vnbroker/api/stream.py` | 0% | ❌ Critical |
| `vnbroker/api/broker.py` | 0% | ❌ Critical |
| `vnbroker/explorer/fmarket/` | 0% | ❌ Critical |
| `vnbroker/explorer/tcbs/tcbs_compatibility.py` | 0% | ❌ Critical |
| `vnbroker/core/config/` | 0% | ❌ Critical |
| `vnbroker/core/settings.py` | 0% | ❌ Critical |
| `vnbroker/core/utils/ext.py` | 0% | ❌ Critical |
| `vnbroker/core/utils/help.py` | 0% | ❌ Critical |
| `vnbroker/core/utils/market_events.py` | 0% | ❌ Critical |
| `vnbroker/connector/dnse/core/auth.py` | 0% | ❌ Critical |
| `vnbroker/connector/dnse/core/models.py` | 0% | ❌ Critical |
| `vnbroker/explorer/dnse/financial.py` | 0% | ❌ Critical |

### 2.2 Coverage target

| Module | Target | Current | Gap |
|:---|:---|:---|:---|
| `vnbroker/core/` | 80% | ~60% | -20% |
| `vnbroker/common/` | 70% | 70% | 0% |
| `vnbroker/explorer/` | 60% | ~40% | -20% |
| `vnbroker/api/` | 75% | ~50% | -25% |

---

## 3. TEST FAILURES

### 3.1 Failed test

```
FAILED tests/unit/explorer/ssi/test_trading.py::TestSSITradingPriceBoard::test_master_cached_across_calls
assert 0 == 1
```

**Nguyên nhân:** Cache key dùng `id()` object → cache miss khi tạo object mới.

**Fix:** Sửa cache key dùng giá trị, không dùng `id()` (TD-001).

---

## 4. TYPE SAFETY (MYPY)

### 4.1 Errors

| File | Error | Count |
|:---|:---|:---|
| `vnbroker/api/company.py` | Incompatible default for parameter "symbol" | 2 |
| `vnbroker/api/company.py` | Call to untyped function | 1 |
| `vnbroker/api/company.py` | Untyped decorator | 8 |
| `vnbroker/api/snapshot.py` | Call to untyped function | 2 |
| `vnbroker/api/snapshot.py` | Missing type arguments for generic type "Dict" | 2 |
| `vnbroker/api/snapshot.py` | Returning Any from function | 1 |

**Tổng:** 10+ errors

### 4.2 Khuyến nghị

- Thêm type hints đầy đủ cho `api/company.py`
- Thêm type hints đầy đủ cho `api/snapshot.py`
- Sử dụng `Optional[str]` thay vì `str = None`

---

## 5. LINT (RUFF)

### 5.1 Errors

| Rule | Count | Fixable |
|:---|:---|:---|
| F401 unused-import | 3 | ✅ |
| F821 undefined-name | 1 | ❌ |

### 5.2 Khuyến nghị

- Xóa unused imports
- Sửa undefined name

---

## 6. KIẾN TRÚC

### 6.1 Điểm mạnh

| Điểm | Mô tả |
|:---|:---|
| Two-tier architecture | Tách biệt dữ liệu ẩn danh và cá nhân hóa |
| Health-based routing | Tự động chọn provider ổn định |
| Connection pool | Tái sử dụng TCP connection |
| Normalizer tập trung | Đảm bảo schema nhất quán |
| Auth providers auto-detect | Giảm cấu hình cho người dùng |
| Multi-agent workflow | Quy trình SDLC có giám sát |

### 6.2 Điểm yếu

| Điểm | Mô tả | Tác động |
|:---|:---|:---|
| Cache key dùng id() | Cache miss 100% | Hiệu năng |
| PRIMARY_SOURCE_POOLS["quote"] = ["vci"] | Hash-shard vô nghĩa | Không chia tải |
| News tái tạo provider mỗi lần gọi | Cache miss | Hiệu năng |
| Không có async support | Blocking I/O | Không scale |
| DNSE/SSI không có fetch_multiple | Bulk fallback chậm | Hiệu năng |
| Test coverage thấp | 55% | Chất lượng |
| Type safety kém | 10+ mypy errors | Bảo trì |

---

## 7. BẢO MẬT

### 7.1 Điểm mạnh

| Điểm | Mô tả |
|:---|:---|
| Zero-knowledge | Credentials không rời client process |
| No logging | Không log API keys, OTPs, tokens |
| Redaction | Redact trong logs |
| dry_run | Default True cho write operations |

### 7.2 Điểm yếu

| Điểm | Mô tả | Tác động |
|:---|:---|:---|
| Không có rate limiting client-side | Có thể bị provider block | Tính ổn định |
| Không có request signing | Không xác minh nguồn gốc | Bảo mật |
| Không có audit log | Không theo dõi được lịch sử | Giám sát |

---

## 8. HƯỚNG PHÁT TRIỂN

### 8.1 Ngắn hạn (v3.7.0)

| Task | Priority | Effort |
|:---|:---|:---|
| Sửa cache key (TD-001) | High | Small |
| Sửa PRIMARY_SOURCE_POOLS["quote"] | Medium | Small |
| Sửa News tái tạo provider | Medium | Small |
| Thêm test cho module 0% | High | Medium |
| Sửa mypy errors | Medium | Small |
| Sửa ruff errors | Low | Small |

### 8.2 Trung hạn (v3.8.0)

| Task | Priority | Effort |
|:---|:---|:---|
| Async support | High | Large |
| Thêm fetch_multiple cho DNSE/SSI | Medium | Medium |
| Rate limiting client-side | Medium | Medium |
| Request signing | Low | Medium |
| Audit log | Low | Medium |

### 8.3 Dài hạn (v4.0.0)

| Task | Priority | Effort |
|:---|:---|:---|
| FX/Crypto/World Index providers | Medium | Large |
| WebSocket streaming | Medium | Large |
| Distributed caching | Low | Large |
| Plugin system | Low | Large |

---

## 9. KẾT LUẬN

### 9.1 Đánh giá tổng thể

| Tiêu chí | Điểm | Ghi chú |
|:---|:---|:---|
| Kiến trúc | 8/10 | Two-tier rõ ràng, failover hoạt động |
| Chất lượng code | 6/10 | Coverage thấp, type safety kém |
| Bảo mật | 7/10 | Zero-knowledge, thiếu rate limiting |
| Hiệu năng | 7/10 | Connection pool tốt, cache cần sửa |
| Tài liệu | 9/10 | Bộ tài liệu đầy đủ, truy vết được |
| Testing | 5/10 | 55% coverage, 1 test fail |

### 9.2 Khuyến nghị

**Ưu tiên cao:**
1. Sửa cache key (TD-001) — tăng hiệu năng ngay lập tức
2. Thêm test cho module 0% coverage — tăng chất lượng
3. Sửa mypy errors — tăng type safety

**Ưu tiên trung bình:**
4. Async support — tăng khả năng scale
5. Rate limiting client-side — tăng tính ổn định
6. Thêm fetch_multiple cho DNSE/SSI — tăng hiệu năng bulk

**Ưu tiên thấp:**
7. Request signing — tăng bảo mật
8. Audit log — tăng giám sát
9. Plugin system — tăng tính mở rộng
