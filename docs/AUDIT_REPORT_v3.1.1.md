# vnbroker v3.1.1 - Comprehensive Audit Report

**Date:** 2026-06-24  
**Auditor:** Blackbox AI  
**Scope:** Full codebase review against documentation (README.md, CLAUDE.md, CHANGELOG.md, docs/*)  
**Version:** 3.1.1 (Cleanup Release - SSI/VNDirect Removal)

---

## Executive Summary

The vnbroker codebase has undergone significant cleanup in v3.1.0 and v3.1.1, removing dead code (MSN, FMP, SSI, VNDirect scaffolds) and transitioning to a **Direct Provider Architecture**. The codebase is now leaner (522 tests passing, 0 failures) but documentation has several gaps and inconsistencies that need addressing.

**Overall Health:** 🟢 Good - Clean architecture, passing tests, but documentation drift exists.

---

## 1. Documentation vs Code Discrepancies

### 1.1 README.md Issues

| Issue | Location | Current Doc | Actual Code | Severity |
|-------|----------|-------------|-------------|----------|
| **FX/Crypto/World Index** | Lines 180-200 | Claims "planned for v3.2.0+" with specific providers (Binance, TwelveData, Alpha Vantage) | Methods raise `NotImplementedError` with generic messages, no provider integration exists | 🟡 Medium |
| **DNSE Company/Finance** | Line 55 | "DNSE Company/Finance hiện tại trả về DataFrame rỗng (chưa được hỗ trợ bởi DNSE upstream)" | Correct behavior but docs don't mention `NotImplementedError` is raised | 🟢 Low |
| **SUPPORTED_SOURCES Table** | Lines 60-70 | Lists DNSE for Company/Finance/News/Trading | DNSE returns empty DataFrames for Company/Finance/News/Trading (fallback implementations) | 🟡 Medium |
| **Fund Source** | Line 75 | "Fund: FMARKET" | Correct | 🟢 Low |
| **Broker Lane Description** | Lines 220-280 | Two TCBS lanes described | Correct but `vnbroker.brokerage.tcbs` import path in example doesn't match actual module structure | 🟡 Medium |

### 1.2 CLAUDE.md Issues

| Issue | Location | Current Doc | Actual Code | Severity |
|-------|----------|-------------|-------------|----------|
| **Analytics Indicators** | Line 380 | "analytics/indicators.py implemented (SMA, EMA, RSI, MACD, Bollinger Bands, ATR, Stochastic, Williams %R, CCI)" | File exists but is **empty** (only imports, no implementations) | 🔴 High |
| **DNSE Brokerage** | Line 390 | "DNSE brokerage implementation (extend BrokerageBase)" - marked as future | `vnbroker/connector/dnse/trade.py` exists with JWT auth but NOT integrated into `brokerage/` pattern | 🟡 Medium |
| **Project Structure** | Lines 50-80 | Lists `analytics/indicators.py` as implemented | File is empty stub | 🔴 High |
| **Version** | Line 420 | "Current version: **3.1.0**" | pyproject.toml says 3.1.0, CHANGELOG says 3.1.1 | 🟢 Low |

### 1.3 CHANGELOG.md Issues

| Issue | Location | Current Doc | Actual Code | Severity |
|-------|----------|-------------|-------------|----------|
| **v3.1.1 Analytics Claim** | Line 15 | "analytics/indicators.py implemented" | **FALSE** - file is empty | 🔴 High |
| **v3.1.1 FX/Crypto Claim** | Line 16 | "fx()/crypto()/world_index() now raise NotImplementedError with clear guidance" | Partially true - they raise NotImplementedError but guidance mentions providers that don't exist | 🟡 Medium |

### 1.4 docs/ Folder - Outdated/Orphaned Files

The `docs/` folder contains **80+ files** with significant duplication and outdated content:

| Category | Files | Status |
|----------|-------|--------|
| **DNSE Planning** | 25+ files (DNSE_*.md) | Mostly planning/implementation docs from v3.0 era, many superseded |
| **TCBS Planning** | 20+ files (TCBS_*.md) | Mix of current specs and outdated sprint plans |
| **Core API Standardization** | 15+ files (CORE_API_STANDARDIZATION_*.md) | Process docs from v1.0 era, largely obsolete |
| **Derivatives** | 5 files (DERIVATIVES_*.md) | Research/critique docs, some relevant |
| **Stock News** | 6 files (STOCK_NEWS_*.md) | Implementation blueprints, partially current |
| **Price Unit** | 5 files (PRICE_UNIT_*.md) | Standardization docs, relevant |
| **Test Scripts** | 6 files (*.py) | Smoke/regression test scripts mixed with docs |

**Recommendation:** Archive old planning docs to `docs/archive/` and maintain only current reference docs.

---

## 2. Code Quality Issues

### 2.1 Empty/Stub Implementations

| File | Issue | Impact |
|------|-------|--------|
| `vnbroker/analytics/indicators.py` | **Completely empty** - only imports, no indicator implementations | Breaks claimed functionality in CHANGELOG/CLAUDE.md |
| `vnbroker/explorer/dnse/financial.py` | Exists but `finance.py` is the registered provider | Duplicate/confusing naming |
| `vnbroker/explorer/tcbs/tcbs_compatibility.py` | Compatibility layer, unclear if needed | Technical debt |

### 2.2 Inconsistent Error Handling

| Component | Current Behavior | Expected |
|-----------|------------------|----------|
| `Vnbroker.fx()` | Raises `NotImplementedError` with provider names (Binance, TwelveData) | Should either implement or raise clean error without fake provider promises |
| `Vnbroker.crypto()` | Same as above | Same |
| `Vnbroker.world_index()` | Same as above | Same |
| `DNSECompany.*()` | Returns empty DataFrame with warning log | Consistent with `DNSEFinance` - OK |
| `DNSETrading.price_board()` | Returns empty DataFrame with warning log | OK |
| `DNSENews.*()` | Returns empty DataFrame with warning log | OK |

### 2.3 Circular Import Risks

| Location | Risk |
|----------|------|
| `vnbroker/__init__.py` → loads `explorer` modules → which register with `ProviderRegistry` → which may import back | Mitigated by lazy loading but fragile |
| `vnbroker/common/client.py` imports `StockComponents` from `common.data` which imports explorer modules | Works currently but tight coupling |

### 2.4 Duplicate/Confusing Naming

| Files | Issue |
|-------|-------|
| `vnbroker/explorer/dnse/finance.py` vs `financial.py` | Both exist, only `finance.py` registered |
| `vnbroker/broker/tcbs/client.py` vs `vnbroker/brokerage/tcbs/client.py` | Two different TCBS implementations with similar names |
| `vnbroker/connector/dnse/trade.py` vs `vnbroker/brokerage/base.py` | DNSE Trade client not integrated into brokerage pattern |

---

## 3. Architecture Assessment

### 3.1 Strengths ✅

1. **Clean Direct Provider Architecture** - No PAT/Gateway dependency
2. **Provider Registry Pattern** - Extensible, discoverable providers
3. **Source Router with Health-based Failover** - Smart AUTO mode with cooldown/exponential backoff
4. **Separation of Concerns** - Market data (explorer) vs Brokerage (broker/brokerage)
5. **Comprehensive Test Coverage** - 522 unit tests passing
6. **Type Hints Throughout** - mypy strict compliance
7. **Security-First Design** - No credential logging, dry_run defaults

### 3.2 Weaknesses ⚠️

1. **Empty Analytics Module** - Claimed implemented but not
2. **DNSE Brokerage Gap** - Connector exists but not unified with brokerage pattern
3. **Documentation Drift** - 80+ docs files, many outdated
4. **FX/Crypto/World Index** - Stubbed with misleading provider promises
5. **Two TCBS Brokerage Implementations** - Confusing for users (iFlash vs Private API)
6. **No Circuit Breaker** - Only cooldown-based failover
7. **Async Support Missing** - Brokerage write operations are sync-only

---

## 4. Test Coverage Analysis

| Test Suite | Status | Notes |
|------------|--------|-------|
| `tests/unit/` | ✅ 522 passed, 9 skipped | Good coverage |
| `tests/integration/` | ⚠️ Gated by env var | Requires live credentials |
| `test_acb_benchmark.py` | ⚠️ Root level test file | Should be in tests/ |
| `test_tcbs_direct.py` | ⚠️ Root level test file | Should be in tests/ |

---

## 5. Dependency Analysis

### 5.1 requirements.txt vs pyproject.toml

| Package | pyproject.toml | requirements.txt | Status |
|---------|----------------|------------------|--------|
| requests | ✅ | ✅ | OK |
| beautifulsoup4 | ✅ | ✅ | OK |
| pandas | ✅ | ✅ | OK |
| openpyxl | ✅ | ✅ | OK |
| pydantic | ✅ | ✅ | OK |
| pytz | ✅ | ✅ | OK |
| psutil | ✅ | ✅ | OK |
| packaging | ✅ | ✅ | OK |
| importlib-metadata | ✅ | ✅ | OK |
| tenacity | ✅ | ✅ | OK |
| httpx[http2] | ❌ | ✅ | **Missing from pyproject.toml** |
| fake_useragent | ❌ | ✅ | **Missing from pyproject.toml** |
| cryptography | ❌ | ✅ | **Missing from pyproject.toml** |

**Critical:** `httpx`, `fake_useragent`, `cryptography` are in requirements.txt but NOT in pyproject.toml dependencies. This will break `pip install vnbroker`.

---

## 6. Recommendations Priority Matrix

| Priority | Issue | Effort | Impact |
|----------|-------|--------|--------|
| 🔴 **P0** | Fix pyproject.toml missing dependencies (httpx, fake_useragent, cryptography) | Low | High - breaks installs |
| 🔴 **P0** | Implement analytics/indicators.py or remove claims from docs | Medium | High - false advertising |
| 🔴 **P0** | Fix FX/Crypto/World Index NotImplementedError messages (remove fake provider promises) | Low | Medium - user trust |
| 🟡 **P1** | Archive outdated docs/ files to docs/archive/ | Low | Medium - maintainability |
| 🟡 **P1** | Unify DNSE brokerage into brokerage/ pattern | Medium | High - consistency |
| 🟡 **P1** | Add circuit breaker pattern to source_router | Medium | High - resilience |
| 🟡 **P1** | Add async support for brokerage write operations | Medium | Medium - modern API |
| 🟢 **P2** | Remove duplicate dnse/financial.py | Low | Low - cleanup |
| 🟢 **P2** | Move root test files to tests/ | Low | Low - organization |
| 🟢 **P2** | Document two TCBS brokerage lanes clearly | Low | Medium - UX |

---

## 7. Compliance Checklist

| Standard | Status | Notes |
|----------|--------|-------|
| mypy strict | ✅ | Passes |
| ruff linting | ✅ | Passes |
| Type hints on public APIs | ✅ | Good coverage |
| Google-style docstrings | ✅ | Consistent |
| No hardcoded secrets | ✅ | Verified |
| Dry-run default on writes | ✅ | Verified |
| Environment variable config | ✅ | Comprehensive |
| Version single-source (pyproject.toml) | ✅ | Version 3.1.0 |

---

## 8. Conclusion

The vnbroker v3.1.1 codebase is **architecturally sound** with a clean Direct Provider pattern, good test coverage, and security-first design. However, **documentation drift** and **three critical gaps** need immediate attention:

1. **Broken installs** due to missing dependencies in pyproject.toml
2. **False feature claims** for analytics indicators
3. **Misleading error messages** for FX/Crypto/World Index

Once these P0 issues are resolved, the library will be production-ready with honest documentation.