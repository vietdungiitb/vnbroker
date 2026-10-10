# PLAN — vnbroker Code Quality & Performance Fix

- **Task ID:** `VNBROKER-FIX-v1`
- **Planner:** PM + System Designer + Tech Lead
- **Ngày:** 2026-10-08
- **Workdir:** `C:/Mujoco Projects/vnbroker`
- **Trạng thái:** `DRAFT`
- **Baseline commit:** `2812414`

## 1. Mục tiêu

**Hiện trạng:** Audit 2026-10-08 phát hiện:
- Test coverage 55% (15+ module 0%)
- 1 test fail (cache key dùng id())
- 10+ mypy errors, 4 ruff errors
- Cache miss 100% do key chứa id() object
- PRIMARY_SOURCE_POOLS["quote"] = ["vci"] → hash-shard vô nghĩa
- News tái tạo provider mỗi lần gọi
- DNSE/SSI không có fetch_multiple
- Không rate limiting client-side

**Mục tiêu:**
1. Sửa cache key → cache hit > 0%
2. Sửa test fail → 1072 passed
3. Thêm test cho module 0% → coverage > 65%
4. Sửa mypy errors → 0 errors
5. Sửa ruff errors → 0 errors
6. Sửa PRIMARY_SOURCE_POOLS → hash-shard thật
7. Sửa News provider → không tái tạo mỗi lần gọi
8. Thêm fetch_multiple cho DNSE/SSI
9. Thêm rate limiting client-side

## 2. In-scope (phạm vi sửa)

### WP-1: Fix Cache Key + Test Fail (P0)

| # | Path (glob) | Mô tả thay đổi dự kiến |
|---|---|---|
| 1 | `vnbroker/core/utils/cache.py` | Sửa `_make_key` để không dùng `id()` object |
| 2 | `tests/unit/core/test_cache_key.py` | **MỚI:** Test cache key không chứa id() |

### WP-2: Fix Source Router + News Provider (P1)

| # | Path (glob) | Mô tả thay đổi dự kiến |
|---|---|---|
| 1 | `vnbroker/core/source_router.py` | Sửa PRIMARY_SOURCE_POOLS["quote"] = ["vci","kbs"] |
| 2 | `vnbroker/common/data.py` | Sửa News không tái tạo provider mỗi lần gọi |
| 3 | `tests/unit/core/test_source_router_fix.py` | **MỚI:** Test hash-shard thật |

### WP-3: Add Tests for 0% Coverage Modules (P0)

| # | Path (glob) | Mô tả thay đổi dự kiến |
|---|---|---|
| 1 | `tests/unit/api/test_snapshot.py` | **MỚI:** Test MarketSnapshot |
| 2 | `tests/unit/api/test_stream.py` | **MỚI:** Test Stream adapter |
| 3 | `tests/unit/api/test_broker_api.py` | **MỚI:** Test broker API |

### WP-4: Fix Mypy + Ruff Errors (P1)

| # | Path (glob) | Mô tả thay đổi dự kiến |
|---|---|---|
| 1 | `vnbroker/api/company.py` | Thêm type hints, sửa Optional[str] |
| 2 | `vnbroker/api/snapshot.py` | Thêm type hints |
| 3 | `vnbroker/api/broker.py` | Xóa unused imports |
| 4 | `vnbroker/api/stream.py` | Xóa unused imports, sửa undefined name |

### WP-5: Add fetch_multiple for DNSE/SSI (P2)

| # | Path (glob) | Mô tả thay đổi dự kiến |
|---|---|---|
| 1 | `vnbroker/explorer/dnse/quote.py` | Thêm `fetch_multiple` classmethod |
| 2 | `vnbroker/explorer/ssi/quote.py` | Thêm `fetch_multiple` classmethod |
| 3 | `tests/unit/explorer/test_dnse_fetch_multiple.py` | **MỚI:** Test DNSE fetch_multiple |
| 4 | `tests/unit/explorer/test_ssi_fetch_multiple.py` | **MỚI:** Test SSI fetch_multiple |

### WP-6: Rate Limiting Client-Side (P2)

| # | Path (glob) | Mô tả thay đổi dự kiến |
|---|---|---|
| 1 | `vnbroker/core/utils/rate_limiter.py` | **MỚI:** Token bucket rate limiter |
| 2 | `vnbroker/core/utils/client.py` | Tích hập rate limiter |
| 3 | `tests/unit/core/test_rate_limiter.py` | **MỚI:** Test rate limiter |

## 3. Non-goals (KHÔNG làm)

- Không thêm async support (v3.8.0)
- Không thêm FX/Crypto/World Index providers (v4.0.0)
- Không refactor explorer providers
- Không đổi API public
- Không nâng dependency version

## 4. Claim dự kiến

| WP | Agent | Files (glob) |
|:--|:---|:---|
| WP-1 | agent-cache | `vnbroker/core/utils/cache.py`, `tests/unit/core/test_cache_key.py` |
| WP-2 | agent-router | `vnbroker/core/source_router.py`, `vnbroker/common/data.py`, `tests/unit/core/test_source_router_fix.py` |
| WP-3 | agent-tests | `tests/unit/api/test_snapshot.py`, `tests/unit/api/test_stream.py`, `tests/unit/api/test_broker_api.py` |
| WP-4 | agent-types | `vnbroker/api/company.py`, `vnbroker/api/snapshot.py`, `vnbroker/api/broker.py`, `vnbroker/api/stream.py` |
| WP-5 | agent-fetch | `vnbroker/explorer/dnse/quote.py`, `vnbroker/explorer/ssi/quote.py`, `tests/unit/explorer/test_dnse_fetch_multiple.py`, `tests/unit/explorer/test_ssi_fetch_multiple.py` |
| WP-6 | agent-ratelimit | `vnbroker/core/utils/rate_limiter.py`, `vnbroker/core/utils/client.py`, `tests/unit/core/test_rate_limiter.py` |

## 5. Tác động repo khác

| Hệ thống bị ảnh hưởng | Bản chất ảnh hưởng | Cần thông báo ai |
|---|---|---|
| CI pipeline | Test mới có thể fail | DevOps |
| Performance | Cache fix tăng hiệu năng | Team |

## 6. Cách kiểm chứng

| # | Lệnh | Exit code mong đợi | Ý nghĩa khi pass |
|---|---|---|---|
| 1 | `.venv/Scripts/python.exe -m pytest tests/unit tests/contract -q --timeout=120` | `0` | 1072+ tests pass |
| 2 | `.venv/Scripts/python.exe -m mypy vnbroker --strict --no-error-summary` | `0` | 0 mypy errors |
| 3 | `uvx ruff check vnbroker` | `0` | 0 ruff errors |
| 4 | `.venv/Scripts/python.exe -m pytest tests/unit tests/contract --cov=vnbroker --cov-report=term -q` | `0` | Coverage > 65% |

## 7. Rollback

- Lệnh: `git checkout -- vnbroker/`
- Xóa file mới: `rm tests/unit/core/test_cache_key.py tests/unit/core/test_source_router_fix.py tests/unit/api/test_snapshot.py tests/unit/api/test_stream.py tests/unit/api/test_broker_api.py tests/unit/explorer/test_dnse_fetch_multiple.py tests/unit/explorer/test_ssi_fetch_multiple.py tests/unit/core/test_rate_limiter.py vnbroker/core/utils/rate_limiter.py`
- Kiểm tra sau rollback: `git status --porcelain` → rỗng

## 8. Rủi ro

| Rủi ro | Xác suất | Tác động | Giảm thiểu |
|---|---|---|---|
| Cache fix break existing tests | Trung bình | Cao | Chạy test suite sau khi sửa |
| Type hints break runtime | Thấp | Trung bình | Chạy test suite |
| fetch_multiple không hoạt động | Trung bình | Trung bình | Mock test |
| Rate limiter ảnh hưởng performance | Thấp | Trung bình | Benchmark |

## 9. Điều kiện Done

- [ ] Tất cả lệnh mục 6 trả exit code như mong đợi
- [ ] Không file nào ngoài mục 2 bị sửa (`git status --porcelain`)
- [ ] Không sửa file nào thuộc claim của agent khác
- [ ] `pytest tests/unit tests/contract` → 1072+ passed
- [ ] `mypy vnbroker --strict` → 0 errors
- [ ] `ruff check vnbroker` → 0 errors
- [ ] Coverage > 65%
