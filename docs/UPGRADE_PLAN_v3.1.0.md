# vnbroker Upgrade & Remediation Plan v3.1.0

**Based on:** Audit Report v3.1.0 (2026-06-22)  
**Target:** v3.1.1 (Immediate Cleanup) → v3.2.0 (Architecture Consolidation) → v3.3.0 (Feature Completion) → v3.4.0 (Quality & Documentation)

---

## Phase 1: Immediate Cleanup (v3.1.1) — **Week 1**

**Goal:** Remove broken/legacy code, add basic analytics, clarify documentation. Zero breaking changes for working features.

### 1.1 Remove FX/Crypto/World Index Stubs
**File:** `vnbroker/common/client.py` (lines 180-350)

**Action:** Replace `fx()`, `crypto()`, `world_index()` methods with `NotImplementedError`:
```python
def fx(self, symbol: Optional[str] = 'EURUSD', source: Optional[str] = None):
    raise NotImplementedError(
        "FX data not supported by current providers (KBS, VCI, TCBS, DNSE). "
        "Support planned for v3.2.0 via new providers (Binance, TwelveData, etc.)."
    )
```

**Rationale:** 
- Already broken (tests deleted in v3.1.0)
- Misleading API — returns Quote/Listing objects that fail at runtime
- CHANGELOG explicitly states tests removed because "only worked with MSN/FMP"

### 1.2 Remove Legacy Dispatch Module
**File:** `vnbroker/core/dispatch.py`

**Action:** Delete file entirely. Verify no imports in codebase first:
```bash
grep -r "from vnbroker.core.dispatch" --include="*.py"
grep -r "import.*dispatch" --include="*.py"
```

**Rationale:** Gateway fully deprecated since v3.0.0. Module maps Gateway endpoints to VCI only.

### 1.3 Implement Core Technical Indicators
**File:** `vnbroker/analytics/indicators.py` (currently 0 bytes)

**Action:** Add pure pandas/numpy implementations (zero dependencies):
```python
# indicators.py
import pandas as pd
import numpy as np

def sma(series: pd.Series, window: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=window, min_periods=1).mean()

def ema(series: pd.Series, window: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=window, adjust=False).mean()

def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=window).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
    """MACD: returns (macd_line, signal_line, histogram)."""
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def bollinger_bands(series: pd.Series, window: int = 20, num_std: float = 2) -> tuple:
    """Bollinger Bands: returns (upper, middle, lower)."""
    middle = sma(series, window)
    std = series.rolling(window=window).std()
    upper = middle + (std * num_std)
    lower = middle - (std * num_std)
    return upper, middle, lower
```

**Update:** `vnbroker/analytics/__init__.py` to export indicators.

### 1.4 Clarify Broker Lane Documentation
**Files:** `README.md`, `CLAUDE.md`

**Action:** Add clear differentiation section:
- `vnbroker.broker.tcbs` — TCBS iFlash OpenAPI v1.0.0 (Official, production-ready)
- `vnbroker.brokerage.tcbs` — TCBS Private API (Advanced, HMAC-SHA256, WebSocket)

### 1.5 Update TODO.md
**Action:** Mark Phase 1 items as done, add Phase 2 items.

---

## Phase 2: Architecture Consolidation (v3.2.0) — **Week 2-3**

**Goal:** Resolve duplication and fragmentation. Requires explicit architectural decisions.

### 2.1 DNSE Unification — **DECISION REQUIRED**

**Current Fragmentation:**
1. `connector.dnse.client.DNSEClient` — HMAC OpenAPI (market + orders)
2. `connector.dnse.trade.Trade` — JWT Trading (wraps DNSEClient)
3. `brokerage.base.BrokerageBase` — Abstract base (no DNSE implementation)

**Option A: Single DNSE Client with Dual Auth Modes (Recommended)**
```python
class DNSEClient:
    def __init__(self, api_key=None, api_secret=None, username=None, password=None):
        # Auto-detect auth mode from provided credentials
    def use_hmac(self): ...      # Market data + orders
    def use_jwt(self): ...       # Account + trading
```

**Option B: Two Classes, Single Namespace**
```
vnbroker.connector.dnse.DNSEOpenAPI   # HMAC
vnbroker.connector.dnse.DNSETrade     # JWT (extends DNSEOpenAPI)
```

**Option C: Brokerage Integration**
- Implement `DNSEBrokerageClient` extending `BrokerageBase`
- Register in `BrokerRegistry`
- Use via `Vnbroker.broker(provider="dnse", ...)`

**Recommendation:** Option A + C — Clean separation, brokerage integration.

### 2.2 Broker Lane Strategy — **DECISION REQUIRED**

**Current State:** Two TCBS implementations with different APIs.

**Option A: Keep Both, Clear Differentiation (Recommended)**
```
vnbroker.broker.tcbs     → TCBS iFlash OpenAPI v1.0.0 (Official, production-ready)
vnbroker.brokerage.tcbs  → TCBS Private API (Advanced, HMAC-SHA256, WebSocket streaming)
```
- Add clear docstrings and README guidance
- Different use cases: Official OpenAPI vs Private API with streaming

**Option B: Consolidate Under Single Namespace**
```
vnbroker.broker.tcbs.openapi  → iFlash OpenAPI
vnbroker.broker.tcbs.private  → Private API
```
- Single entry point: `Vnbroker.broker(provider="tcbs", api_type="openapi|private")`

**Option C: Deprecate One**
- Keep `broker.tcbs` (more complete, better tested, official API)
- Deprecate `brokerage.tcbs` with migration guide

**Recommendation:** Option A — Both serve different needs. Document clearly.

### 2.3 Standardize Provider Registration
**Action:** Audit all explorer modules, enforce `@ProviderRegistry.register` decorator pattern.

**Current:** Mix of decorator + lazy import in `__init__.py::_ensure_explorer_modules_loaded()`

**Target:** All providers registered via decorator at module load time.

### 2.4 DNSE Company/Finance — Proper Error Handling
**Files:** `vnbroker/explorer/dnse/company.py`, `vnbroker/explorer/dnse/financial.py`

**Current:** Company returns empty DataFrames with warning; Finance raises `NotImplementedError`.

**Action:** Align behavior — both should raise `NotImplementedError` with clear message directing to VCI/KBS/TCBS.

---

## Phase 3: Feature Completion (v3.3.0) — **Week 4-5**

### 3.1 Implement SSI Brokerage Client
**Location:** `vnbroker/broker/ssi/`, `vnbroker/brokerage/ssi/`

**Action:** Extend `BrokerageBase` for SSI API, register in `BrokerRegistry`.

### 3.2 Implement VNDirect Brokerage Client
**Location:** `vnbroker/broker/vndirect/`, `vnbroker/brokerage/dnse/`

**Action:** Extend `BrokerageBase` for VNDirect API (DNSE brokerage).

### 3.3 Add FX/Crypto/World Index Providers
**New Modules:** `vnbroker/explorer/binance/`, `vnbroker/explorer/twelvedata/`, etc.

**Action:** 
1. Create provider explorers for crypto (Binance, CoinGecko)
2. Create provider explorers for FX/World Index (TwelveData, Alpha Vantage)
3. Register in `ProviderRegistry`
4. Update `Vnbroker.fx()`, `crypto()`, `world_index()` to use new providers

### 3.4 Add Async Support for Brokerage
**Action:** Implement async versions of write operations in `BrokerageBase` and subclasses.

### 3.5 Implement Circuit Breaker Pattern
**Location:** `vnbroker/core/source_router.py` or new `vnbroker/core/circuit_breaker.py`

**Action:** Add circuit breaker for provider failover (beyond current health-based cooldown).

---

## Phase 4: Quality & Documentation (v3.4.0) — **Week 6**

### 4.1 API Reference Documentation
**Action:** Generate with `pdoc` or `sphinx`, publish to `docs/API_REFERENCE.md` or GitHub Pages.

### 4.2 Type Stubs (.pyi files)
**Action:** Generate stub files for all public APIs for IDE support.

### 4.3 Performance Benchmarks
**Action:** Add `benchmarks/` directory, run in CI nightly.

### 4.4 Architecture Decision Records (ADRs)
**Action:** Create `docs/adr/` with records for key decisions:
- ADR-001: Direct Provider Architecture (v3.0)
- ADR-002: Broker Lane Dual Implementation
- ADR-003: DNSE Dual Auth Modes
- ADR-004: Source Router Health-Based Failover

### 4.5 Integration Test Documentation
**Action:** Create `docs/INTEGRATION_TESTING.md` with required env vars per test suite.

### 4.6 Brokerage Usage Guide
**Action:** Create `docs/BROKERAGE_GUIDE.md` with TCBS/DNSE/SSI examples.

---

## Decision Matrix Summary

| Decision | Options | Recommended | Blocking? |
|----------|---------|-------------|-----------|
| Broker Lane | A/B/C | A (Document both) | No |
| DNSE Unification | A/B/C | A + C | Yes (affects brokerage API) |
| FX/Crypto/Index | A/B/C | Remove stubs now, implement v3.3 | No |
| Analytics | Implement core / Remove | Implement core | No |
| Legacy Dispatch | Keep/Remove | Remove | No |
| DNSE Company/Finance | Empty DF / NotImplementedError | NotImplementedError | No |

---

## Success Criteria

### v3.1.1 (Immediate Cleanup)
- [ ] `fx()`, `crypto()`, `world_index()` raise `NotImplementedError`
- [ ] `vnbroker/core/dispatch.py` removed
- [ ] `analytics/indicators.py` implemented with SMA, EMA, RSI, MACD, Bollinger Bands
- [ ] Broker lane differentiation documented in README and CLAUDE.md
- [ ] All 522 unit tests still pass
- [ ] `mypy --strict` passes (or at least no new errors)

### v3.2.0 (Architecture Consolidation)
- [ ] DNSE unified under single `DNSEClient` with dual auth modes
- [ ] DNSE brokerage implemented in `brokerage.dnse` extending `BrokerageBase`
- [ ] Provider registration standardized (all via decorator)
- [ ] DNSE Company/Finance raise `NotImplementedError` consistently
- [ ] Broker lane strategy documented and implemented

### v3.3.0 (Feature Completion)
- [ ] SSI brokerage client implemented
- [ ] VNDirect brokerage client implemented
- [ ] FX/Crypto/World Index providers added (Binance, TwelveData)
- [ ] `Vnbroker.fx()`, `crypto()`, `world_index()` functional
- [ ] Async brokerage write operations implemented
- [ ] Circuit breaker pattern implemented

### v3.4.0 (Quality & Documentation)
- [ ] API reference documentation published
- [ ] Type stubs (`.pyi`) generated
- [ ] Performance benchmarks in CI
- [ ] ADRs created for key architectural decisions
- [ ] Integration test guide published
- [ ] Brokerage guide with TCBS/DNSE/SSI examples published

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking changes in FX/Crypto removal | Low | Low | Already broken, tests deleted, clear error message |
| Removing dispatch.py breaks unknown tooling | Low | Medium | Verify no imports via grep before removal |
| DNSE unification breaks existing users | Low | Medium | Maintain backward compatibility aliases |
| Broker lane consolidation confusion | Medium | High | Clear documentation, deprecation warnings if needed |
| Analytics scope creep | Medium | Medium | Define minimal MVP (SMA, EMA, RSI, MACD, BB) |

---

## Resource Estimates

| Phase | Effort | Duration | Dependencies |
|-------|--------|----------|--------------|
| Phase 1 | 16-24 hours | Week 1 | None |
| Phase 2 | 24-32 hours | Week 2-3 | Decisions on 2 items |
| Phase 3 | 40-56 hours | Week 4-5 | Phase 2 complete |
| Phase 4 | 24-32 hours | Week 6 | Phase 3 complete |

**Total:** ~104-144 hours over 6 weeks

---

## Immediate Next Steps (This Week)

1. **Verify no imports of `dispatch.py`** — Run grep commands
2. **Implement `analytics/indicators.py`** — Core 5 indicators
3. **Replace FX/Crypto/Index stubs** with `NotImplementedError`
4. **Remove `dispatch.py`** after verification
5. **Update documentation** (README, CLAUDE.md) with broker lane clarification
6. **Run full test suite** to ensure no regressions
7. **Run mypy/ruff** to ensure code quality

---

## Approval Required

Please confirm the following decisions before Phase 2 implementation:

1. **Broker Lane Strategy:** Option A (Document both), B (Consolidate), or C (Deprecate one)?
2. **DNSE Unification:** Option A (Single client dual auth), B (Two classes), or C (Brokerage integration)?
3. **DNSE Company/Finance:** Align to `NotImplementedError` (consistent with Finance)?
4. **Phase 1 Scope:** Proceed with immediate cleanup as outlined?

Once approved, I'll begin Phase 1 implementation.