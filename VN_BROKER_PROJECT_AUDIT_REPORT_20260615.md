# VNBroker Project Audit Report (Updated)
**Date:** 2026-06-15  
**Version:** v1.0.2 (core v3.4.0)  
**Auditor:** Blackbox AI Assistant  
**Updated:** Based on review findings from `VN_BROKER_AUDIT_REVIEW_20260615.md` (83 test failures discovered)

---

## 1. Executive Summary

VNBroker là thư viện Python công khai cho dữ liệu chứng khoán Việt Nam, hỗ trợ đa nguồn (VCI, KBS, TCBS, MSN, DNSE, AUTO) với kiến trúc PAT-only cho vninvest-sdk. Dự án có 195 unit tests passing theo CHANGELOG, **NHƯNG thực tế có 83/583 test failures** do các bug P0 chưa được phát hiện.

**Trạng thái TCBS:** ĐÃ SỬA CHANGELOG - TCBS **vẫn còn và được sử dụng** (không bị xóa như ghi nhầm trước đó). File `api/screener.py` vẫn tồn tại.

---

## 2. Kiến Trúc Tổng Thể

### 2.1 Pattern Chính
```
Explorer (data sources) → Adapter (API layer) → Client (orchestration)
                                    ↓
                            ProviderRegistry (dynamic discovery)
```

### 2.2 Các Thành Phần Chính
| Component | Vị Trí | Trạng Thái |
|-----------|--------|------------|
| Vnbroker (Main Client) | `vnbroker/common/client.py` | ⚠️ **Bug: Gateway ghi đè source="DNSE"** |
| Quote/Company/Finance/Trading/Listing | `vnbroker/api/*.py` | ✅ BaseAdapter + dynamic_method |
| Source Router (AUTO) | `vnbroker/core/source_router.py` | ✅ VCI-first, exponential backoff |
| Price Transform | `vnbroker/core/utils/transform.py` | ✅ VND/THOUSAND_VND via env var |
| Async Client | `vnbroker/core/utils/async_client.py` | ⚠️ Chưa dùng cho explorers |
| Proxy Manager | `vnbroker/core/utils/proxy_manager.py` | ✅ proxyscrape API |
| TCBS Broker Equity | `vnbroker/broker/tcbs/equity.py` | ❌ **81 test failures: signature mismatch** |
| TCBS Auth Tests | `tests/unit/broker/tcbs/test_session_auth.py` | ❌ **Mock token expired (2026-05-20)** |

### 2.3 Nguồn Dữ Liệu
| Source | Loại | Trạng Thái | Ghi Chú |
|--------|------|------------|---------|
| VCI | Public market data | ✅ Primary cho quote/company/finance | 43-56% success rate at concurrency 8-16 |
| KBS | Public market data | ✅ Primary cho trading | 90% success rate |
| TCBS | Public + Broker | ✅ **VẪN CÒN** | Screener còn, equity write API broken |
| MSN | FX/Crypto/World Index | ✅ | Chỉ MSN |
| DNSE | Broker platform | ⚠️ **Bug: source override không hoạt động** | Cần PAT, không trong OPEN_SOURCE_CANDIDATES |
| AUTO | Router | ✅ VCI→KBS→MSN failover | Exponential cooldown 5s→90s |

---

## 3. Điểm Mạnh (Strengths)

1. **Kiến trúc PAT-only rõ ràng** - Gateway API + Emergency fallback (10 calls/day)
2. **Price unit standardization** - Tập trung ở `transform.py`, config qua `vnbroker_PRICE_UNIT`
3. **AUTO source routing** - VCI-first, failover thông minh, health monitoring
4. **Test infrastructure** - Benchmark suite; cross-provider regression tests
5. **DNSE broker integration** - Đầy đủ account, orders, trading, OTP, margin với docs 20+ files
6. **Lazy loading pattern** - Tránh circular import (dù workaround fragile)
7. **Comprehensive docs** - DNSE spec, coding guide, test spec, audit checklist, sprint board

---

## 4. Critical Issues (P0 - Phải Sửa Ngay - 83 Test Failures)

### 4.1 TCBS Equity Write API Signature Mismatch (81 failures)
**File:** `vnbroker/broker/tcbs/equity.py` ~line 270
**Vấn đề:** Test yêu cầu `place_order(pin_code: str, request_id: str)`, `modify_order(request_id: str)`, `cancel_order(request_id: str)` nhưng implementation thiếu các tham số này.
**Hệ quả:** 81 `TypeError` khi chạy test suite.

### 4.2 Mock Token Expiry (2 failures)
**File:** `tests/unit/broker/tcbs/test_session_auth.py` line 158
**Vấn đề:** Hardcoded `expiredTime: "2026-05-20T18:00:00Z"` đã quá hạn (hôm nay 2026-06-15).
**Hệ quả:** `test_authenticate_success_sets_session_token` fail ngay lập tức.

### 4.3 DNSE Source Override Bug
**File:** `vnbroker/common/client.py` ~line 257
**Vấn đề:** Logic `if self._use_gateway or effective_source.upper() == "GATEWAY":` ghi đè hoàn toàn tham số `source="DNSE"` truyền vào `.stock()`.
**Hệ quả:** `test_vnbroker_stock_supports_dnse` AssertionError.

### 4.4 Screener File Status Inconsistency
**CHANGELOG ghi:** "Removed `api/screener.py`"
**Thực tế:** File `vnbroker/api/screener.py` **vẫn tồn tại** và link với TCBS explorer.

---

## 5. Technical Debt (Weaknesses)

### 5.1 High (P1 - Tuần 2-3)

| Vấn Đề | File | Mô Tả |
|--------|------|-------|
| **Deprecated proxies pollute namespace** | `vnbroker/__init__.py` lines 50-120 | 9 class proxy deprecated (Quote, Company, Finance, Trading, Listing, News, MarketSnapshot, Fund, Messenger) vẫn export |
| **Circular import workaround fragile** | `vnbroker/__init__.py` | Lazy-loading proxy pattern dễ vỡ khi refactor |
| **Config fragmentation** | `pyproject.toml`, `pyproject.toml.testing`, `requirements.txt`, `pytest.ini`, `.flake8` | 5 file config, duplicate pytest/flake8 settings |
| **Async/Sync duplication** | `async_client.py` vs explorers | Chưa có unified HTTP client interface; explorers vẫn sync-only |
| **Error hierarchy chưa thống nhất** | `vnbroker/core/exceptions.py` | Cần VnbrokerError → ProviderError/AuthenticationError/RateLimitError/DataNotFoundError |
| **Hardcoded values** | `source_router.py` | PRIMARY_SOURCE_POOLS, cooldown magic numbers (5, 15, 30, 90) |
| **No unified caching** | - | vninvest-sdk có cache, vnbroker chưa |

### 5.2 Medium (P2 - Tháng 2)

| Vấn Đề | Mô Tả |
|--------|-------|
| **VCI reliability thấp** | 43-56% success rate at concurrency 8-16 (vs KBS 90%) |
| **Rate limiting** | Thay AdaptiveController bằng standardized rate limiting per provider |
| **Type checking** | Thêm mypy, ruff vào CI/CD |
| **Python 3.10 support** | Đánh giá drop 3.10 (require ≥3.11 cho ExceptionGroup, tomllib) |
| **Plugin API** | Thiết kế public plugin API cho custom data sources |

---

## 6. Phân Tích Chi Tiết Theo Module

### 6.1 vnbroker/__init__.py (Lines 1-120)
```python
# VẤN ĐỀ: 9 deprecated proxy classes vẫn được export
class _QuoteProxy: ...
class _CompanyProxy: ...
# ... 7 class nữa
```
**Khuyến nghị:** Xóa lines 50-120, chỉ giữ Vnbroker, constants, connector, exceptions.

### 6.2 vnbroker/common/client.py - **BUG P0**
```python
# Line ~257: BUG - Gateway logic ghi đè source parameter
if self._use_gateway or effective_source.upper() == "GATEWAY":
    return StockComponents(..., "GATEWAY", ...)  # Luôn dùng GATEWAY, bỏ qua DNSE
```
**Fix đề xuất (từ review):**
```python
if (self._use_gateway and (source is None or source.upper() == "GATEWAY")) or effective_source.upper() == "GATEWAY":
```

### 6.3 vnbroker/broker/tcbs/equity.py - **BUG P0 (81 failures)**
```python
# Current signature (THIẾU pin_code, request_id)
def place_order(self, account_no, symbol, side, order_type, quantity, price, *, dry_run=True):
```
**Fix đề xuất (từ review):**
```python
def place_order(self, account_no, symbol, side, order_type, quantity, price: float, pin_code: str, request_id: str, *, dry_run=True):
def modify_order(self, ..., request_id: str, ...):
def cancel_order(self, ..., request_id: str, ...):
```

### 6.4 tests/unit/broker/tcbs/test_session_auth.py - **BUG P0**
```python
# Line 158: Hardcoded expired date (ĐÃ QUÁ HẠN)
"expiredTime": "2026-05-20T18:00:00Z"
```
**Fix đề xuất:**
```python
from datetime import datetime, timezone, timedelta
future_date = (datetime.now(tz=timezone.utc) + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
```

### 6.5 vnbroker/api/screener.py - **CHANGELOG INCONSISTENCY**
File vẫn tồn tại, CHANGELOG ghi "Removed" → Cần cập nhật CHANGELOG hoặc xóa file thực sự.

### 6.6 vnbroker/core/source_router.py
- `PRIMARY_SOURCE_POOLS` hardcoded → nên config-driven
- Cooldown: 5s → 15s → 30s → 90s (magic numbers)

### 6.7 DNSE Documentation Suite (20+ files) - ✅ Tốt
| File | Mục Đích |
|------|----------|
| `DNSE_EXPLORER_SPEC.md` | Exact class/method/schema spec |
| `DNSE_CODING_GUIDE.md` | Implementation order S1-S11, code templates |
| `DNSE_SPRINT_TASK_BOARD.md` | 11 slices với validation commands |
| `DNSE_AUDIT_CHECKLIST_V2.md` | 12-part audit (A-L) với evidence columns |
| `DNSE_TEST_SPEC_V2.md` | Unit/integration test specs với fixtures |
| `DNSE_PROVIDER_COMPARISON_MATRIX.md` | 4-provider comparison |

---

## 7. Kết Quả Benchmark (benchmark_results.json)

| Provider | Concurrency 8 | Concurrency 12 | Concurrency 16 |
|----------|---------------|----------------|----------------|
| VCI | 43-56% success | ~40% | ~35% |
| KBS | 90% success | 85% | 80% |
| AUTO | 100% success, 37.2 rps | 100% success, 41.3 rps | - |

**Kết luận:** VCI unreliable ở concurrency cao. AUTO router hiệu quả (failover sang KBS).

---

## 8. Kế Hoạch Dọn Dẹp & Nâng Cấp (Cleanup & Upgrade Plan)

### Phase 0: Emergency Bug Fixes (HÔM NAY - P0 Critical)
```bash
# 1. Fix TCBS Equity Write API signatures (81 failures)
edit vnbroker/broker/tcbs/equity.py  # Add pin_code, request_id params

# 2. Fix mock token expiry (2 failures)
edit tests/unit/broker/tcbs/test_session_auth.py  # Dynamic future date

# 3. Fix DNSE source override bug
edit vnbroker/common/client.py  # Respect source parameter

# 4. Fix CHANGELOG screener inconsistency
# Option A: Delete vnbroker/api/screener.py (if truly deprecated)
# Option B: Update CHANGELOG to reflect file still exists
```

### Phase 1: Legacy Cleanup (Tuần Này - P1)
```bash
# 1. Xóa deprecated proxies khỏi __init__.py (lines 50-120)
# 2. Gộp config files: pyproject.toml.testing → pyproject.toml, pytest.ini/.flake8 → pyproject.toml
# 3. Verify TCBS read APIs vẫn hoạt động
pytest tests/unit/explorer/tcbs/ -v
```

### Phase 2: Architecture Fixes (Tuần 2-3 - P1)
- [ ] Fix circular imports: `__init__.py` thành simple re-export
- [ ] Unified error hierarchy
- [ ] Unified HTTP client interface (Protocol với sync/async methods)
- [ ] Add async support cho VCI/KBS explorers

### Phase 3: Production Hardening (Tháng 2 - P2)
- [ ] Unified caching layer (port từ vninvest-sdk)
- [ ] Standardized rate limiting per provider
- [ ] Add pytest-asyncio, httpx-mock, pytest-xdist, mypy
- [ ] Enable ruff + mypy trong CI/CD
- [ ] Investigate VCI 43-56% success rate root cause

---

## 9. Câu Hỏi Chiến Lược (Strategic Questions)

1. **Python 3.10:** Drop support? (Require ≥3.11 cho ExceptionGroup, tomllib, better typing)
2. **Open-source vs Commercial:** Core vnbroker public, vninvest-sdk commercial - ranh giới rõ ràng?
3. **Plugin API:** Thiết kế public plugin API cho custom data sources?
4. **Screener:** Giữ hay xóa `api/screener.py`? (CHANGELOG ghi xóa nhưng file còn)
5. **VCI Reliability:** Investigate root cause 43-56% success rate - upstream issue hay client config?

---

## 10. File Danh Sách Thay Đổi Ưu Tiên Cao (High-Priority Change List)

| File | Action | Priority | Test Failures Fixed |
|------|--------|----------|---------------------|
| `vnbroker/broker/tcbs/equity.py` | Add `pin_code`, `request_id` params | **P0 Critical** | 81 |
| `tests/unit/broker/tcbs/test_session_auth.py` | Dynamic mock token expiry | **P0 Critical** | 2 |
| `vnbroker/common/client.py` | Fix DNSE source override logic | **P0 Critical** | 1+ |
| `vnbroker/api/screener.py` | Delete OR update CHANGELOG | **P0 Critical** | 0 (consistency) |
| `vnbroker/__init__.py` | Remove lines 50-120 (deprecated proxies) | P1 | 0 |
| `pyproject.toml` | Consolidate all config | P1 | 0 |
| `pytest.ini` | Delete, move to pyproject.toml | P1 | 0 |
| `.flake8` | Delete, move to pyproject.toml | P1 | 0 |
| `vnbroker/core/source_router.py` | Config-driven pools, cooldown | P1 | 0 |
| `vnbroker/core/exceptions.py` | Unified error hierarchy | P1 | 0 |
| `vnbroker/core/utils/async_client.py` | Unified HTTP client Protocol | P1 | 0 |

---

## 11. Kết Luận

VNBroker có **kiến trúc tốt** nhưng **test suite đang broken (83/583 failures)** do 3 bug P0 cụ thể. Phải fix **Phase 0 ngay hôm nay** trước khi làm bất kỳ cleanup/refactor nào khác.

**Next Action Priority Order:**
1. Fix 3 bug P0 (equity signatures, mock token, DNSE override) → Green build
2. Resolve screener inconsistency
3. Phase 1 legacy cleanup
4. Phase 2 architecture fixes

---

*Report updated: 2026-06-15 (incorporating review findings)*  
*CHANGELOG đã sửa: TCBS không bị xóa, chỉ xóa api/screener.py (nhưng file screener vẫn tồn tại - cần resolve)*