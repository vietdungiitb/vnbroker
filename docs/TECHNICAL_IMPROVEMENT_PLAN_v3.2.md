# vnbroker v3.2 - Technical Improvement Plan

**Date:** 2026-06-24  
**Based on:** AUDIT_REPORT_v3.1.1.md  
**Target Release:** v3.2.0 (Q3 2026)

---

## Overview

This plan addresses critical gaps, performance bottlenecks, and architectural improvements identified in the v3.1.1 audit. Organized by priority (P0=Critical, P1=High, P2=Medium, P3=Low).

---

## P0 - Critical (Must Fix Before v3.2 Release)

### 1. Fix Missing Dependencies in pyproject.toml
**Issue:** `httpx[http2]`, `fake_useragent`, `cryptography` in requirements.txt but missing from pyproject.toml
**Impact:** `pip install vnbroker` will fail for users
**Fix:** Add to `[project.dependencies]` in pyproject.toml
```toml
dependencies = [
    ...
    "httpx[http2]>=0.27.0",
    "fake_useragent>=1.5.1",
    "cryptography>=42.0.5",
]
```
**Effort:** 15 min | **Risk:** Low

### 2. Implement analytics/indicators.py or Remove Claims
**Issue:** CHANGELOG v3.1.1 and CLAUDE.md claim indicators implemented (SMA, EMA, RSI, MACD, Bollinger Bands, ATR, Stochastic, Williams %R, CCI) but file is empty
**Options:**
- **Option A (Recommended):** Implement core indicators using pandas/numpy (no new deps)
- **Option B:** Remove claims from CHANGELOG/CLAUDE.md, mark as v3.3 feature
**Implementation (Option A):**
```python
# vnbroker/analytics/indicators.py
import pandas as pd
import numpy as np

def sma(series: pd.Series, window: int) -> pd.Series: ...
def ema(series: pd.Series, window: int) -> pd.Series: ...
def rsi(series: pd.Series, window: int = 14) -> pd.Series: ...
def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame: ...
def bollinger_bands(series: pd.Series, window: int = 20, num_std: float = 2) -> pd.DataFrame: ...
def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series: ...
def stochastic(high: pd.Series, low: pd.Series, close: pd.Series, k: int = 14, d: int = 3) -> pd.DataFrame: ...
def williams_r(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series: ...
def cci(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 20) -> pd.Series: ...
```
**Effort:** 4-6 hours | **Risk:** Low

### 3. Fix FX/Crypto/World Index Error Messages
**Issue:** `NotImplementedError` messages promise specific providers (Binance, TwelveData, Alpha Vantage) that don't exist
**Fix:** Update error messages in `vnbroker/common/client.py` to be honest:
```python
raise NotImplementedError(
    "FX/forex data is not supported by current Vietnamese market data providers "
    "(KBS, VCI, TCBS, DNSE). FX support requires integration with international "
    "providers (planned for future release)."
)
```
**Effort:** 15 min | **Risk:** Low

---

## P1 - High (Core Improvements for v3.2)

### 4. Unify DNSE Brokerage into brokerage/ Pattern
**Current State:** 
- `vnbroker/connector/dnse/client.py` - HMAC OpenAPI client (market data + trading)
- `vnbroker/connector/dnse/trade.py` - JWT trading client (legacy pattern)
- `vnbroker/brokerage/base.py` - Abstract `BrokerageBase` with HMAC + WebSocket pattern
- `vnbroker/brokerage/tcbs/client.py` - TCBS Private API implementation

**Gap:** DNSE not integrated into `brokerage/` pattern, uses different auth (HMAC vs JWT dual mode)

**Plan:** Create `vnbroker/brokerage/dnse/client.py` extending `BrokerageBase`:
```python
class DNSEBrokerageClient(BrokerageBase):
    """DNSE Direct Brokerage - HMAC-SHA256 + JWT Trading Token"""
    
    def _get_base_url(self, sandbox: bool) -> str:
        return "https://openapi.dnse.com.vn" if not sandbox else "https://openapi-sandbox.dnse.com.vn"
    
    def _get_default_headers(self) -> Dict[str, str]:
        return {"Content-Type": "application/json", "Accept": "application/json"}
    
    def _sign_request(self, method: str, path: str, payload: Dict) -> Dict[str, str]:
        # HMAC-SHA256 signing per DNSE spec
        ...
    
    def _handle_otp_challenge(self, response) -> Response:
        # JWT trading token flow
        ...
    
    # Implement all abstract methods: get_balance, get_positions, get_orders, 
    # get_margin_info, place_order, cancel_order, modify_order
```
**Effort:** 16-24 hours | **Risk:** Medium (requires DNSE API access for testing)

### 5. Add Circuit Breaker Pattern to Source Router
**Current:** Cooldown-based failover only (exponential backoff 5s→90s)
**Problem:** No protection against cascading failures, no half-open state testing

**Design:** Add circuit breaker per (module, source):
```python
class CircuitBreaker:
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject fast
    HALF_OPEN = "half_open"  # Testing recovery
    
    def __init__(self, failure_threshold=5, recovery_timeout=60, half_open_max_calls=3):
        ...
    
    def call(self, func, *args, **kwargs):
        if self.state == OPEN:
            if time.time() > self.last_failure + self.recovery_timeout:
                self.state = HALF_OPEN
            else:
                raise CircuitOpenError()
        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise
```
**Integration:** Wrap provider calls in `source_router.py` or `BaseComponent._execute_with_failover()`
**Effort:** 8-12 hours | **Risk:** Medium

### 6. Add Async Support for Brokerage Write Operations
**Current:** All brokerage write operations (place_order, cancel_order, modify_order) are sync-only
**Need:** Async variants for high-frequency trading, WebSocket integration

**Plan:** Add async methods to `BrokerageBase` and implementations:
```python
# In BrokerageBase
@abstractmethod
async def place_order_async(self, request: OrderRequest) -> OrderResponse: ...

@abstractmethod  
async def cancel_order_async(self, order_id: str) -> OrderResponse: ...

@abstractmethod
async def modify_order_async(self, order_id: str, **kwargs) -> OrderResponse: ...

# TCBS implementation uses httpx.AsyncClient (already exists in _async_client)
```
**Effort:** 12-16 hours | **Risk:** Low (httpx already supports async)

### 7. Archive Outdated Documentation
**Current:** 80+ files in docs/ with significant duplication
**Action:** 
```
docs/
├── archive/                    # NEW - move old planning docs here
│   ├── DNSE_*_202604*.md      # Old DNSE planning
│   ├── TCBS_*_202604*.md      # Old TCBS planning  
│   ├── CORE_API_STANDARDIZATION_*.md  # v1.0 process docs
│   └── DERIVATIVES_*.md       # Old research
├── reference/                  # Keep current reference docs
│   ├── DNSE_API_CONTRACT.md
│   ├── TCBS_API_CONTRACT.md
│   ├── TCBS_BROKER_SPEC.md
│   └── PRICE_UNIT_STANDARDIZATION.md
├── guides/                     # User-facing guides
│   ├── VNBROKER_USAGE_GUIDE.md
│   ├── QUICKSTART.md
│   └── BROKERAGE_GUIDE.md
└── AUDIT_REPORT_v3.1.1.md     # This audit
    TECHNICAL_IMPROVEMENT_PLAN_v3.2.md  # This plan
```
**Effort:** 2 hours | **Risk:** Low

---

## P2 - Medium (Performance & Developer Experience)

### 8. Optimize Provider Registry Lazy Loading
**Current:** `vnbroker/__init__.py` loads all explorer modules at import time via `_ensure_explorer_modules_loaded()`
**Issue:** Slow import, loads unused providers
**Fix:** True lazy loading - register providers on first use:
```python
# In ProviderRegistry.get()
if key not in cls._registry:
    cls._auto_discover_provider(provider_type, source_name)
```
**Effort:** 4-6 hours | **Risk:** Low

### 9. Add Connection Pooling & HTTP/2 Optimization
**Current:** `send_request` creates new connections per call (via requests/httpx)
**Optimization:** 
- Use `httpx.Client` with connection pooling (already in DNSE connector)
- Enable HTTP/2 for supported endpoints (TCBS, DNSE)
- Add keep-alive headers
**Effort:** 6-8 hours | **Risk:** Low

### 10. Implement Request Deduplication (In-Flight Request Coalescing)
**Problem:** Multiple simultaneous calls for same symbol+interval hit provider repeatedly
**Solution:** Cache in-flight promises, return same future to concurrent callers
```python
_inflight_cache: Dict[str, asyncio.Future] = {}

async def _get_or_create_inflight(key: str, coro_factory):
    if key in _inflight_cache:
        return await _inflight_cache[key]
    future = asyncio.create_task(coro_factory())
    _inflight_cache[key] = future
    try:
        return await future
    finally:
        _inflight_cache.pop(key, None)
```
**Effort:** 4-6 hours | **Risk:** Low

### 11. Add Type Stubs (.pyi) for IDE Support
**Current:** Type hints in .py files only
**Benefit:** Faster IDE autocomplete, better type checking for consumers
**Files to stub:** `vnbroker/common/client.py`, `vnbroker/common/data.py`, `vnbroker/broker/tcbs/client.py`
**Effort:** 4-6 hours | **Risk:** Low

### 12. Standardize DNSE Company/Finance to NotImplementedError
**Current:** Returns empty DataFrame with warning log
**Better:** Raise `NotImplementedError` with clear message (consistent with FX/Crypto)
```python
def overview(self, **kwargs) -> pd.DataFrame:
    raise NotImplementedError(
        "DNSE OpenAPI does not provide company overview endpoints. "
        "Use VCI, KBS, or TCBS for company data."
    )
```
**Effort:** 1 hour | **Risk:** Low (breaking change - needs deprecation period)

---

## P3 - Low (Nice to Have)

### 13. Add FX/Crypto/World Index Providers (Binance, TwelveData)
**Scope:** New provider implementations in `explorer/binance/`, `explorer/twelvedata/`
**Effort:** 40+ hours | **Target:** v3.3+

### 14. Add Prometheus Metrics / Observability
**Scope:** Export provider health, latency, error rates
**Effort:** 8-12 hours

### 15. Implement Request/Response Caching with TTL
**Current:** LRU cache only on listing methods
**Extend:** Cache quote history, company overview, finance ratios
**Effort:** 6-8 hours

### 16. Add Batch/Parallel APIs for Multi-Symbol Requests
**Current:** `Quote.fetch_multiple()` exists for VCI/TCBS
**Extend:** Unified `Vnbroker.batch_quote()` across all providers
**Effort:** 8-12 hours

---

## Implementation Timeline (v3.2.0 Target: 6-8 weeks)

| Week | Focus | Deliverables |
|------|-------|--------------|
| 1 | P0 Fixes | Fixed pyproject.toml, indicators implemented, error messages corrected |
| 2-3 | P1: DNSE Brokerage | `brokerage/dnse/client.py` with full BrokerageBase implementation |
| 3-4 | P1: Circuit Breaker | Circuit breaker integrated into source_router/BaseComponent |
| 4-5 | P1: Async Brokerage | Async write operations for TCBS (and DNSE when ready) |
| 5 | P1: Doc Archive | docs/ reorganized, outdated files archived |
| 6 | P2: Performance | Lazy registry, connection pooling, request deduplication |
| 7 | P2: Type Stubs | .pyi files for public APIs |
| 8 | Testing & Release | Full test suite, integration testing, v3.2.0 release |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| DNSE API access for testing | Use sandbox environment; mock tests for CI |
| Breaking changes (DNSE Company/Finance) | Deprecation warning in v3.1.2, remove in v3.2 |
| Circuit breaker complexity | Start with per-provider simple implementation, iterate |
| Async migration | Keep sync API, add async variants (not replace) |

---

## Success Criteria for v3.2.0

- [ ] `pip install vnbroker` works without missing dependencies
- [ ] `analytics.indicators` provides 9+ technical indicators
- [ ] FX/Crypto/World Index errors are honest (no fake provider promises)
- [ ] DNSE brokerage integrated into `brokerage/` pattern
- [ ] Circuit breaker prevents cascade failures
- [ ] Async write operations available for TCBS brokerage
- [ ] docs/ folder clean with only current reference docs
- [ ] All 522+ tests pass, new tests for new features
- [ ] mypy strict + ruff clean

---

## Appendix: Code Quality Metrics Target

| Metric | Current | Target v3.2 |
|--------|---------|-------------|
| Test Coverage | ~85% | >90% |
| Import Time | ~2.5s | <1.5s |
| Avg Quote Latency (KBS) | ~800ms | <500ms (with pooling) |
| Failed Request Recovery | 5-90s cooldown | <30s (circuit breaker) |
| Documentation Currency | ~60% | 100% (current refs only) |