# PLAN — TIER 1 DATA ENGINE UPGRADE

- **Task ID:** `TIER1-ENGINE-v1`
- **Planner:** Team Code Leader (Hermes Agent)
- **Ngày:** 2026-10-05
- **Workdir:** `C:/Mujoco Projects/vnbroker`
- **Trạng thái:** `DRAFT`
- **Baseline commit:** `e2c9c4a`

## 1. Mục tiêu

**Hiện trạng:** Tầng 1 (dữ liệu thị trường ẩn danh) có code failover, health store, adaptive controller nhưng **không chạy trên đường chính** (`_auto_sources` chỉ set trong test). Bulk có nhưng **vỡ schema** (tz-naive) và **mất dữ liệu âm thầm**. Connection pool bị mất 4-5× tốc độ do thread-local session. Multi-provider chưa có. Auth providers không tham gia pool.

**Mục tiêu:** 
1. Failover tự động chạy thật trên đường chính (health store + circuit breaker)
2. Bulk đa mã chuẩn hoá đúng schema (tz-aware, có manifest)
3. Connection pool dùng chung → 4-5× nhanh hơn
4. Multi-provider cùng tải bulk dựa trên sức khoẻ
5. Auth providers (DNSE/SSI/TCBS) tự động tham gia pool khi có env key
6. API `Market(auto=True).bulk.history(symbols=[...])` hoạt động được

## 2. In-scope (phạm vi sửa)

### WP-1: Connection Pool (P0, 4-5× speedup)

| # | Path (glob) | Mô tả thay đổi dự kiến |
|---|---|---|
| 1 | `vnbroker/core/utils/client.py` | Sửa `_get_thread_session()` để dùng shared session pool |
| 2 | `vnbroker/core/utils/connection_pool.py` | **MỚI**: `ConnectionPool` singleton với `HTTPAdapter(pool_connections=256, pool_maxsize=256)` |
| 3 | `tests/unit/core/test_connection_pool.py` | **MỚI**: Test connection reuse, thread safety, performance |

### WP-2: Failover + Bulk Normalizer (P0)

| # | Path (glob) | Mô tả thay đổi dự kiến |
|---|---|---|
| 1 | `vnbroker/common/data.py` | Sửa `Quote.__init__` để set `_auto_sources` khi `source="AUTO"`; sửa `Quote.history` để chuẩn hoá bulk |
| 2 | `vnbroker/core/utils/normalizer.py` | **MỚI**: `Normalizer` class chuẩn hoá DataFrame (tz, boundary, sort) |
| 3 | `tests/contract/test_failover_integration.py` | **MỚI**: Test failover thật trên đường chính |
| 4 | `tests/unit/common/test_bulk_normalizer.py` | **MỚI**: Test bulk normalization |

### WP-3: Bulk Router + Health Router (P1)

| # | Path (glob) | Mô tả thay đổi dự kiến |
|---|---|---|
| 1 | `vnbroker/core/bulk_router.py` | **MỚI**: `BulkRouter` chia tải symbols theo sức khoẻ provider, chạy đồng thời |
| 2 | `vnbroker/core/health_router.py` | **MỚI**: `HealthRouter` quản lý sức khoẻ provider theo thời gian thực |
| 3 | `tests/unit/core/test_bulk_router.py` | **MỚI**: Test bulk routing, health-based distribution |

### WP-4: Provider Pool (P1)

| # | Path (glob) | Mô tả thay đổi dự kiến |
|---|---|---|
| 1 | `vnbroker/core/provider_pool.py` | **MỚI**: `ProviderPool` tự động detect auth providers từ env, quản lý pool |
| 2 | `tests/unit/core/test_provider_pool.py` | **MỚI**: Test provider detection, auth provider integration |

### WP-5: API Integration (P1, cần WP-1→4 xong)

| # | Path (glob) | Mô tả thay đổi dự kiến |
|---|---|---|
| 1 | `vnbroker/ui/market.py` | Thêm `bulk` property trả về `BulkAPI` |
| 2 | `vnbroker/api/bulk.py` | **MỚI**: `BulkAPI` class với `history()`, `price_board()` |
| 3 | `tests/unit/api/test_bulk_api.py` | **MỚI**: Test bulk API end-to-end |

## 3. Non-goals (KHÔNG làm)

- Không sửa `vnbroker/explorer/*` (provider implementations)
- Không sửa `vnbroker/broker/*` (tier 2)
- Không sửa `vnbroker/api/quote.py` (BaseAdapter stack)
- Không thêm provider mới
- Không đổi schema database
- Không nâng dependency version
- Không sửa `vnbroker/core/source_router.py` (đã có sẵn, chỉ cần nối vào)

## 4. Claim dự kiến

| WP | Agent | Files (glob) |
|:--|:---|:---|
| WP-1 | agent-connpool | `vnbroker/core/utils/client.py`, `vnbroker/core/utils/connection_pool.py`, `tests/unit/core/test_connection_pool.py` |
| WP-2 | agent-failover | `vnbroker/common/data.py`, `vnbroker/core/utils/normalizer.py`, `tests/contract/test_failover_integration.py`, `tests/unit/common/test_bulk_normalizer.py` |
| WP-3 | agent-bulkrouter | `vnbroker/core/bulk_router.py`, `vnbroker/core/health_router.py`, `tests/unit/core/test_bulk_router.py` |
| WP-4 | agent-providerpool | `vnbroker/core/provider_pool.py`, `tests/unit/core/test_provider_pool.py` |
| WP-5 | agent-api | `vnbroker/ui/market.py`, `vnbroker/api/bulk.py`, `tests/unit/api/test_bulk_api.py` |

## 5. Tác động repo khác

| Hệ thống bị ảnh hưởng | Bản chất ảnh hưởng | Cần thông báo ai |
|---|---|---|
| CI pipeline | Test mới có thể fail nếu không đồng bộ | DevOps |
| Performance benchmark | Connection pool thay đổi có thể ảnh hưởng benchmark hiện tại | Team |

## 6. Cách kiểm chứng

| # | Lệnh | Exit code mong đợi | Ý nghĩa khi pass |
|---|---|---|---|
| 1 | `.venv/Scripts/python.exe -m pytest tests/unit tests/contract -q --timeout=300` | `0` | 1006+ tests pass |
| 2 | `.venv/Scripts/python.exe -c "from vnbroker.core.utils.connection_pool import ConnectionPool; print('OK')"` | `0` | Connection pool import được |
| 3 | `.venv/Scripts/python.exe -c "from vnbroker.common.data import Quote; q=Quote('ACB','AUTO',show_log=False); print('OK' if hasattr(q,'_auto_sources') else 'FAIL')"` | `0` | Failover được nối vào |
| 4 | `.venv/Scripts/python.exe -c "from vnbroker.core.bulk_router import BulkRouter; print('OK')"` | `0` | Bulk router import được |
| 5 | `.venv/Scripts/python.exe -c "from vnbroker.core.provider_pool import ProviderPool; print('OK')"` | `0` | Provider pool import được |

## 7. Rollback

- Lệnh: `git checkout -- vnbroker/core/utils/client.py vnbroker/common/data.py vnbroker/ui/market.py`
- Xóa file mới: `rm vnbroker/core/utils/connection_pool.py vnbroker/core/utils/normalizer.py vnbroker/core/bulk_router.py vnbroker/core/health_router.py vnbroker/core/provider_pool.py vnbroker/api/bulk.py`
- Kiểm tra sau rollback: `git status --porcelain` → rỗng

## 8. Rủi ro

| Rủi ro | Xác suất | Tác động | Giảm thiểu |
|---|---|---|---|
| Connection pool không thread-safe | Trung bình | Cao | Dùng `requests.Session` (thread-safe) + `HTTPAdapter` |
| Failover loop vô hạn | Thấp | Cao | Health store có cooldown + max retries |
| Bulk router chia không đều | Trung bình | Trung bình | Weighted round-robin theo health |
| Auth providers không ổn định | Trung bình | Trung bình | Health router loại tự động |
| Test mới fail | Trung bình | Thấp | Chạy test riêng trước khi tích hợp |

## 9. Điều kiện Done

- [ ] Tất cả lệnh mục 6 trả exit code như mong đợi
- [ ] Không file nào ngoài mục 2 bị sửa (`git status --porcelain`)
- [ ] Không sửa file nào thuộc claim của agent khác
- [ ] `pytest tests/unit tests/contract` → 1006+ passed
- [ ] Benchmark: 100 symbols bulk < 5s (hiện tại ~53s)
- [ ] Failover test: VCI 429 → KBS phục vụ
