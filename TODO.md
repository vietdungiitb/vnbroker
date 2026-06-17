# TODO - Implementation Plan

## Project: vninvest-sdk / vnbroker

**Generated:** 2025-06-17  
**Based on:** ARCHITECTURE.md (updated), BENCHMARK_COMPARISON_REPORT.md

---

## Priority 1: Fix Critical Issues (Blocking)

### 1.1 Bcrypt 72-byte limit (Issue #3) 🔴 Critical
**Problem:** Token > 72 bytes bị cắt hoặc lỗi khi hash (PAT có thể dài tới 81 ký tự)

**Solution:** Hash trước với SHA-256 thay vì bcrypt trực tiếp

```python
# Thay vì:
hash = bcrypt.hash(password[:72])

# Dùng:
hash = bcrypt.hash(sha256(password.encode()).hexdigest()[:72])
```

**Files to modify:**
- `vninvest-sdk/vninvest/auth.py` - APIKeyAuth
- `vninvest-sdk/vninvest/pat.py` - PATStorage

**Estimated:** 2 hours

---

### 1.2 API Contract Endpoint Mismatch (Issue #2) 🔴 Critical
**Problem:** 
- vnbroker: `/api/v1/quote/history`
- vninvest-fastapi: `/api/v1/quote`
- Django Gateway: `/core/v1/market-data/quotes/`

**Solution:** Unified endpoint mapping

**Files to modify:**
- `vnbroker/core/gateway_client.py`
- `vninvest-sdk/vninvest/gateway_client.py`

**Estimated:** 4 hours

---

### 1.3 Direct Mode PAT Requirement Design (Issue #1) 🟡 In Progress
**Problem:** ARCHITECTURE.md says YES (bắt buộc), README.md says NO (optional cho VCI/KBS/TCBS/MSN)

**Proposed Fix:** 
- Direct Mode với VCI/KBS/TCBS/MSN: PAT **optional** (public APIs)
- Direct Mode với DNSE/FMP: PAT **bắt buộc** (requires credentials)
- Gateway Mode: PAT **bắt buộc**

**Files to modify:**
- `vnbroker/common/client.py` - Vnbroker class
- `vninvest-sdk/vninvest/auth.py` - PAT validation logic
- `ARCHITECTURE.md` - Section 1 & 3
- `README.md`

**Estimated:** 3 hours

---

## Priority 2: Provider Resilience

### 2.1 Circuit Breaker for AUTO Mode (Issue #8) 🔴 High
**Problem:** Provider AUTO routing lacks circuit breaker - cascade failure risk

**Solution:** Implement ProviderCircuitBreaker

```python
class ProviderCircuitBreaker:
    failure_threshold = 5
    success_threshold = 3
    cooldown_period = 60
    
    # States: CLOSED → OPEN → HALF_OPEN
    def allow_request(self, provider: str) -> bool: ...
    def record_success(self, provider: str) -> None: ...
    def record_failure(self, provider: str) -> None: ...
```

**Files to create:**
- `vnbroker/core/resilience.py`

**Files to modify:**
- `vnbroker/common/data.py` - StockComponents
- `vnbroker/explorer/*/quote.py` - All quote providers

**Estimated:** 6 hours

---

### 2.2 Provider Health Check
**Problem:** Need health check for AUTO routing

**Solution:** Implement lightweight health check per provider

```python
class ProviderHealthChecker:
    async def check(self, provider: str) -> ProviderHealth:
        # Use /health or /listing endpoint (fast)
        # Check latency threshold: < 2s = healthy
    
    def is_healthy(self, provider: str) -> bool: ...
```

**Files to modify:**
- `vnbroker/core/registry.py`
- `vnbroker/common/client.py`

**Estimated:** 4 hours

---

## Priority 3: Fix Failed Providers (Benchmark)

### 3.1 DNSE - Missing Credentials
**Issue:** DNSE requires API key/secret - all tests fail

**Solution:** Add DNSE credential configuration

**Files to modify:**
- `vnbroker/connector/dnse/core/config.py`
- `vnbroker/connector/dnse/core/http_client.py`
- Add environment variable setup: `DNSE_API_KEY`, `DNSE_API_SECRET`

**Estimated:** 2 hours

---

### 3.2 News Providers - Method Not Found
**Issue:** All News providers fail - "No `market_news` method"

**Solution:** Implement news method for each provider

**Files to create/modify:**
- `vnbroker/explorer/kbs/news.py` - Add news method
- `vnbroker/explorer/vci/news.py` - Add news method
- `vnbroker/explorer/tcbs/news.py` - Add news method

**Estimated:** 4 hours

---

### 3.3 Trading/Price Board - Parameter Mismatch
**Issue:** Wrong param - `symbols` vs `symbol_ls`

**Solution:** Fix parameter mapping

**Files to modify:**
- `vnbroker/explorer/kbs/trading.py` - Fix `symbols` → `symbol_ls`
- `vnbroker/explorer/tcbs/trading.py` - Fix `symbols` → `symbol_ls`
- `vnbroker/explorer/vci/trading.py` - Fix parameter

**Estimated:** 2 hours

---

### 3.4 TCBS Financial - Parameter Mismatch
**Issue:** Financial doesn't accept `lang` parameter

**Solution:** Remove `lang` parameter from TCBS financial requests

**Files to modify:**
- `vnbroker/explorer/tcbs/financial.py`

**Estimated:** 1 hour

---

### 3.5 MSN - Parameter Mismatch
**Issue:** MSN expects `symbol_id` vs `symbol`

**Solution:** Add parameter mapping

**Files to modify:**
- `vnbroker/explorer/msn/quote.py`
- `vnbroker/explorer/msn/listing.py`

**Estimated:** 2 hours

---

### 3.6 FMP - No API Key Configured
**Issue:** FMP требует FMP_API_KEY env var

**Solution:** Add FMP configuration

**Files to modify:**
- `vnbroker/connector/fmp/config.py`
- Add environment setup: `FMP_API_KEY`

**Estimated:** 1 hour

---

## Priority 4: Streaming & Versioning

### 4.1 Unified StreamManager (Issue #9) 🔴 Medium
**Problem:** Gateway (WebSocket) vs Direct (Redis pub/sub) parity

**Solution:** Unified StreamManager interface

**Files to modify:**
- `vninvest-sdk/vninvest/streaming.py`
- `vnbroker/common/stream.py`

**Estimated:** 6 hours

---

### 4.2 API Versioning Strategy (Issue #11) 🔴 Medium
**Problem:** Core API `/core/v1/` - need multi-version support

**Solution:** Add version negotiation

```python
# Client side
client = VninvestClient(
    api_version="v2",  # or "v1", "auto"
)
```

**Files to modify:**
- `vninvest-sdk/vninvest/gateway_client.py`
- `vninvest-sdk/vninvest/config.py`

**Estimated:** 4 hours

---

## Priority 5: Observability & Testing

### 5.1 OpenTelemetry Tracing (Issue #10 Partial)
**Problem:** observability.py needs complete implementation

**Solution:** Full OpenTelemetry integration

**Files to modify:**
- `vninvest-sdk/vninvest/observability.py`

**Estimated:** 4 hours

---

### 5.2 Testing Strategy (Issue #12) 🔴 Medium
**Solution:** Document and implement testing strategy

**Files to create:**
- `tests/unit/` - Mock tests
- `tests/integration/` - Real provider tests
- `tests/contract/` - OpenAPI schema tests

**Estimated:** 8 hours

---

## Priority 6: Documentation

### 6.1 README & Quickstart (Issue #14) 🔴 Low
**Solution:** Complete documentation

**Files to modify:**
- `README.md` - Overview, features, installation
- `docs/QUICKSTART.md` - 5-minute tutorial
- `docs/MIGRATION_GUIDE.md` - v0.1 → v0.2

**Estimated:** 6 hours

---

## Summary

| Priority | Issue | Status | Estimate |
|----------|-------|--------|----------|
| 🔴 1.1 | Bcrypt fix | Not Started | 2h |
| 🔴 1.2 | API Contract | Not Started | 4h |
| 🟡 1.3 | PAT Design | In Progress | 3h |
| 🔴 2.1 | Circuit Breaker | Not Started | 6h |
| 🔴 2.2 | Health Check | Not Started | 4h |
| 🟢 3.1 | DNSE Creds | Not Started | 2h |
| 🟢 3.2 | News Methods | Not Started | 4h |
| 🟢 3.3 | Trading Params | Not Started | 2h |
| 🟢 3.4 | TCBS Finance | Not Started | 1h |
| 🟢 3.5 | MSN Params | Not Started | 2h |
| 🟢 3.6 | FMP Config | Not Started | 1h |
| 🔴 4.1 | StreamManager | Not Started | 6h |
| 🔴 4.2 | Versioning | Not Started | 4h |
| 🟡 5.1 | OpenTelemetry | Partial | 4h |
| 🔴 5.2 | Testing | Not Started | 8h |
| 🔴 6.1 | Docs | Not Started | 6h |

**Total Estimate:** 59 hours

---

## Action Items

1. **Immediate (This Week):**
   - [ ] Fix Bcrypt 72-byte limit
   - [ ] Fix DNSE credentials
   - [ ] Complete PAT Design fix

2. **Next Week:**
   - [ ] Circuit Breaker implementation
   - [ ] News methods implementation
   - [ ] Trading/Price Board fix

3. **Week 3-4:**
   - [ ] Streaming parity
   - [ ] API versioning
   - [ ] OpenTelemetry complete

4. **Week 5:**
   - [ ] Testing strategy
   - [ ] Documentation
