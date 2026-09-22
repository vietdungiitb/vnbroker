# vnbroker Codebase Audit Report v3.1.0

**Date:** 2026-06-22  
**Version Analyzed:** v3.1.0 (per pyproject.toml, CHANGELOG.md)  
**Architecture:** Direct Provider Architecture (v3.0+) — No PAT/Gateway dependency

---

## Executive Summary

The vnbroker library is a mature Python toolkit for Vietnamese stock market data and brokerage operations. The codebase has undergone significant cleanup in v3.1.0 (removing MSN, FMP, PAT/Gateway), and **documentation has been synchronized** with the current codebase. The library has **522 unit tests passing** with clean architecture patterns.

**Overall Health:** Good — Core functionality solid, documentation now matches code, but several technical gaps remain for future enhancement.

---

## 1. Documentation Status: ✅ SYNCHRONIZED

All root-level documentation now matches the v3.1.0 codebase:

| File | Status | Notes |
|------|--------|-------|
| `pyproject.toml` | ✅ v3.1.0 | Version synchronized |
| `README.md` | ✅ v3.1.0 | Updated with v3.1.0 changes, DNSE stub note, FX/Crypto warning |
| `CHANGELOG.md` | ✅ v3.1.0 | Accurate, detailed |
| `CLAUDE.md` | ✅ Rewritten | Now documents vnbroker Direct Provider Architecture (not vninvest-sdk) |
| `.env.example` | ✅ Cleaned | Removed FMP, MSN, PAT, VCI_API_KEY, KBS_API_KEY, TCBS_AUTH_TOKEN |
| `.env.dnse.example` | ✅ Cleaned | Removed FMP_API_KEY |
| `TODO.md` | ✅ Updated | Reflects v3.1.0 cleanup complete |
| `vnbroker/config.py` | ✅ v3.1.0 | VERSION_REQUIREMENTS updated to 3.1.0 |

---

## 2. Architecture Overview (Current State)

### Data Flow: Market Data (Direct Provider)
```
Vnbroker.stock(symbol, source="KBS")
    → StockComponents(symbol, source)
        → Quote/Company/Finance/Listing/Trading/News adapters (BaseAdapter)
            → ProviderRegistry.get(module, source)
                → Explorer implementation (vci/kbs/tcbs/dnse)
```

### Data Flow: Brokerage (Private API)
```
Vnbroker.broker(provider="tcbs", api_key="...")
    → BrokerRegistry.create("TCBS", ...)
        → TCBSBrokerClient (iFlash OpenAPI v1.0.0)
            → AuthService → AccountService → MoneyService → EquityService → DerivativesService → MarketService
            → PortfolioEngine (pure compute)
```

### DNSE Dual-Layer Architecture
```
Market Data (HMAC OpenAPI):     vnbroker.connector.dnse.client.DNSEClient
Trading/Account (JWT):          vnbroker.connector.dnse.trade.Trade (wraps DNSEClient)
Brokerage Abstraction:          vnbroker.brokerage.base.BrokerageBase (abstract)
```

### Source Router (AUTO mode)
- **Health-based failover** with exponential backoff cooldown (5s, 10s, 20s, 40s, max 90s)
- **Per-module primary pools**: VCI for quote/company/finance, KBS for trading
- **Hash-based sharding** for symbol-level affinity
- **Thread-safe** in-memory health state

---

## 3. Provider Capability Matrix

| Provider | Quote | Company | Finance | Listing | Trading | News | Stream | Auth |
|----------|-------|---------|---------|---------|---------|------|--------|------|
| VCI | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | None |
| KBS | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | None |
| TCBS | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | None |
| DNSE | ✅ | ⚠️ Stub | ❌ NotImpl | ✅ | ✅ | ❌ | ❌ | HMAC |
| RSS_CAFEF | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | None |
| RSS_VNECONOMY | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | None |
| FMARKET | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | None |

**Key Observations:**
- DNSE Company returns empty DataFrames with warning (by design — DNSE OpenAPI lacks company endpoints)
- DNSE Finance raises `NotImplementedError` (explicit — DNSE doesn't provide financial statements)
- DNSE News/Stream not implemented
- RSS providers only for news

---

## 4. Brokerage Layer Analysis

### Two Distinct TCBS Implementations

| Aspect | `vnbroker.broker.tcbs.client.TCBSBrokerClient` | `vnbroker.brokerage.tcbs.client.TCBSClient` |
|--------|-----------------------------------------------|---------------------------------------------|
| **API** | TCBS iFlash OpenAPI v1.0.0 (Official) | TCBS Private API (HMAC-SHA256) |
| **Auth** | OTP + API Key | API Key + Secret + OTP |
| **Endpoints** | `/tartarus/v1/...`, `/erebos/v1/...` | `/api/v1/...` |
| **Features** | Full: account, money, equity, derivatives, portfolio, market | Full: balance, positions, orders, margin, WebSocket streaming |
| **Tests** | Comprehensive mock-based (522 tests) | Limited |
| **Namespace** | `vnbroker.broker` (Official OpenAPI) | `vnbroker.brokerage` (Private API) |
| **Registry** | `BrokerRegistry` | Not registered in BrokerRegistry |

### DNSE Brokerage Entry Points
1. `vnbroker.connector.dnse.client.DNSEClient` — HMAC OpenAPI (market + orders)
2. `vnbroker.connector.dnse.trade.Trade` — JWT Trading (account + trading, wraps DNSEClient)
3. `vnbroker.brokerage.base.BrokerageBase` — Abstract base (no DNSE implementation yet)
4. `vnbroker.broker.vndirect` — Scaffolded, empty
5. `vnbroker.broker.ssi` — Scaffolded, empty

---

## 5. Identified Technical Gaps & Issues

### 5.1 HIGH PRIORITY

#### Gap 1: FX/Crypto/World Index Stubs Exist But Don't Work
**Location:** `vnbroker/common/client.py` lines 180-350 (`fx()`, `crypto()`, `world_index()` methods)

**Current Behavior:** Creates `Quote` + `Listing` objects with KBS/VCI/TCBS/DNSE sources, but **none of these providers support forex/crypto/world indices**.

**Evidence from CHANGELOG v3.1.0:** "Xóa `fx()`/`crypto()`/`world_index()` tests: Các phương thức này chỉ hoạt động với MSN/FMP — đã bị xóa."

**Documentation Warning Added:** README now states these will raise `NotImplementedError` in future version.

**Options:**
1. **Remove stubs** and raise `NotImplementedError` immediately (clean break)
2. **Implement via new providers** (Binance, CoinGecko, Twelve Data, Alpha Vantage)
3. **Keep stubs with deprecation warning** for one version cycle

#### Gap 2: Empty Analytics Module
**File:** `vnbroker/analytics/indicators.py` — **0 bytes, completely empty**

**Impact:** Users importing `vnbroker.analytics` get empty module. No technical indicators available.

#### Gap 3: Broker Lane Duplication — Two TCBS Implementations
**Problem:** Confusing for users, duplicated maintenance burden, unclear use-case differentiation.

**Recommendation:** Keep both but clearly document:
- `broker.tcbs` = iFlash OpenAPI v1.0.0 (Official, production-ready, comprehensive tests)
- `brokerage.tcbs` = Private API (Advanced, HMAC-SHA256, WebSocket streaming)

#### Gap 4: DNSE Client Fragmentation — Three Entry Points
**Problem:** Users don't know which to use; `Trade` class wraps `DNSEClient` creating confusion.

**Recommendation:** Unify under single namespace with clear dual-auth modes.

### 5.2 MEDIUM PRIORITY

#### Gap 5: Legacy Dispatch Module
**File:** `vnbroker/core/dispatch.py` — Emergency fallback for Gateway (deleted in v3.0.0)

**Status:** Gateway fully deprecated. This module maps Gateway endpoints to VCI explorers only.

**Recommendation:** Remove if no internal tooling depends on it.

#### Gap 6: Inconsistent Provider Registration
- Some explorers use `ProviderRegistry` via `@register_provider` decorator
- Others rely on lazy import in `vnbroker/__init__.py::_ensure_explorer_modules_loaded()`

#### Gap 7: Missing DNSE News/Stream Support
- News: Not implemented for DNSE (only VCI, KBS, TCBS, RSS)
- Stream: Not implemented for any provider

#### Gap 8: Test Environment Documentation
- Integration tests gated by `vnbroker_RUN_LIVE_INTEGRATION=1`
- Required env vars not documented per test suite

#### Gap 9: SSI & VNDirect Brokerage Scaffolds Empty
- `vnbroker/broker/ssi/` — Only `__init__.py`
- `vnbroker/broker/vndirect/` — Only `__init__.py`
- `vnbroker/brokerage/` — No SSI or DNSE implementation

### 5.3 LOW PRIORITY

#### Gap 10: Documentation Gaps
- No API reference documentation (auto-generated or manual)
- No Architecture Decision Records (ADRs)
- Brokerage usage examples missing for DNSE/SSI

#### Gap 11: Type Hint Coverage
- Some public APIs lack full type annotations
- No `.pyi` stub files for IDE support

#### Gap 12: Performance
- No benchmarks in CI
- Adaptive concurrency not fully tested

---

## 6. Test Coverage Summary

| Suite | Status | Count | Notes |
|-------|--------|-------|-------|
| Unit | ✅ Passing | 522 | 9 skipped |
| Integration | ⚠️ Gated | - | Requires `vnbroker_RUN_LIVE_INTEGRATION=1` + live credentials |
| Broker TCBS | ✅ Comprehensive | - | Mock-based, covers auth, account, money, equity, derivatives, portfolio, write gates |

---

## 7. Recommended Action Plan

### Phase 1: Immediate Cleanup (v3.1.1) — **Week 1**
1. **Remove FX/Crypto/World Index stubs** from `Vnbroker` class — raise `NotImplementedError` with clear message
2. **Remove `vnbroker/core/dispatch.py`** (legacy Gateway fallback)
3. **Add basic technical indicators** to `analytics/indicators.py` (SMA, EMA, RSI, MACD, Bollinger Bands)
4. **Document broker lane differentiation** clearly in README and CLAUDE.md

### Phase 2: Architecture Consolidation (v3.2.0) — **Week 2-3**
1. **Unify DNSE entry points** — Single `DNSEClient` with dual auth modes (HMAC + JWT)
2. **Implement DNSE brokerage** in `vnbroker.brokerage.dnse` extending `BrokerageBase`
3. **Standardize provider registration** — Enforce `@ProviderRegistry.register` decorator pattern
4. **Add DNSE News support** (if DNSE provides news API)

### Phase 3: Feature Completion (v3.3.0) — **Week 4-5**
1. **Implement SSI brokerage** client
2. **Implement VNDirect brokerage** client
3. **Add FX/Crypto/World Index providers** (Binance, TwelveData, etc.)
4. **Add async support** for brokerage write operations
5. **Implement circuit breaker** pattern for provider failover

### Phase 4: Quality & Documentation (v3.4.0) — **Week 6**
1. **Generate API reference documentation** (pdoc/sphinx)
2. **Add type stubs** (`.pyi` files)
3. **Add performance benchmarks** to CI
4. **Create Architecture Decision Records** (ADRs)
5. **Full integration test documentation**

---

## 8. Decision Matrix for Phase 1

| Decision | Options | Recommended | Rationale |
|----------|---------|-------------|-----------|
| FX/Crypto/Index stubs | Remove now / Deprecate / Keep | **Remove now** | Already broken, tests deleted, misleading |
| Legacy dispatch.py | Remove / Keep | **Remove** | Gateway fully deprecated since v3.0.0 |
| Analytics indicators | Implement core / Remove module | **Implement core** | High user value, zero dependencies |
| Broker lane docs | Document both / Consolidate | **Document both** | Different use cases, both maintained |

---

## 9. File Inventory for Reference

### Root Configuration (All Synchronized ✅)
- `pyproject.toml` — Version 3.1.0 ✅
- `README.md` — Version 3.1.0 ✅
- `CHANGELOG.md` — Version 3.1.0 ✅
- `CLAUDE.md` — vnbroker Direct Provider Architecture ✅
- `.env.example` — Clean, only live variables ✅
- `.env.dnse.example` — Clean, only DNSE variables ✅
- `TODO.md` — Accurate status ✅
- `vnbroker/config.py` — VERSION_REQUIREMENTS at 3.1.0 ✅

### Core Modules
- `vnbroker/common/client.py` — Main entry, **FX/Crypto/Index stubs need removal**
- `vnbroker/common/data.py` — BaseComponent, adapters, StockComponents, Fund
- `vnbroker/base.py` — BaseAdapter, dynamic_method, ProviderRegistry
- `vnbroker/config.py` — Config, VERSION_REQUIREMENTS
- `vnbroker/core/source_router.py` — AUTO source, health failover
- `vnbroker/core/dispatch.py` — **Legacy Gateway fallback, should remove**
- `vnbroker/core/registry.py` — ProviderRegistry

### Market Data Explorers
- `vnbroker/explorer/vci/` — Quote, Company, Finance, Listing, Trading, News ✅
- `vnbroker/explorer/kbs/` — Quote, Company, Finance, Listing, Trading, News ✅
- `vnbroker/explorer/tcbs/` — Quote, Company, Finance, Listing, Trading, News ✅
- `vnbroker/explorer/dnse/` — Quote, Listing, Trading ✅ | Company (stub) | Finance (NotImplementedError) | News ❌ | Stream ❌
- `vnbroker/explorer/rss_cafef/` — News only ✅
- `vnbroker/explorer/rss_vneconomy/` — News only ✅
- `vnbroker/explorer/fmarket/` — Fund data ✅

### Brokerage
- `vnbroker/broker/tcbs/client.py` — TCBSBrokerClient (iFlash OpenAPI v1.0.0) ✅
- `vnbroker/broker/registry.py` — BrokerRegistry ✅
- `vnbroker/brokerage/tcbs/client.py` — TCBSClient (Private HMAC API) ✅
- `vnbroker/brokerage/base.py` — BrokerageBase (abstract) ✅
- `vnbroker/connector/dnse/client.py` — DNSEClient (HMAC OpenAPI) ✅
- `vnbroker/connector/dnse/trade.py` — Trade (JWT Trading, wraps DNSEClient) ✅
- `vnbroker/broker/ssi/` — Scaffolded only ❌
- `vnbroker/broker/vndirect/` — Scaffolded only ❌

### Analytics & Bot
- `vnbroker/analytics/indicators.py` — **EMPTY (0 bytes) ❌**
- `vnbroker/bot/notify.py` — Messenger (Slack, Telegram, Discord, Lark) ✅

---

## 10. Conclusion

The vnbroker codebase is **functionally solid** with clean architecture, comprehensive tests, and **now fully synchronized documentation**. The primary remaining issues are **architectural duplication** in the brokerage layer and **missing features** (analytics, FX/crypto, DNSE news/stream, SSI/VNDirect brokerage).

**Immediate ROI:** Phase 1 cleanup (removing broken stubs, legacy code, adding basic indicators) can be completed in a few days and will significantly improve code clarity.

**Strategic Decisions Needed:** The broker lane duplication and DNSE fragmentation require explicit architectural decisions before Phase 2 consolidation.

---