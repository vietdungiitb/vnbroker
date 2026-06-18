# TODO - Implementation Plan

## Project: vninvest-sdk / vnbroker

**Generated:** 2025-06-17  
**Aligned with:** ARCHITECTURE.md (vninvest Auth Resolve API)

---

## Zero-Matrix: Deployment Mode × Feature Tier

### 1. Deployment Mode (chọn 1)
| Mode | Mô tả | Use Case |
|------|-------|----------|
| **Gateway** | Gọi Core API (vninvest SaaS) | Production, multi-tenant, billing |
| **Direct** | Gọi providers local qua vnbroker | Giảm tải Gateway, tránh rate-limit |

### 2. Feature Tier (mặc định Simple)
| Tier | Dependencies | Features |
|------|-------------|----------|
| **Simple (default)** | 0 extra | Auth + Scope check + Local metering (memory) |
| **Advanced (opt-in)** | Redis/SQLite optional | Quota enforce + Billing webhook + Persistent metering |

### 3. Matrix kết hợp

| | Gateway Simple | Gateway Advanced | Direct Simple | Direct Advanced |
||-|:-:|:-:|:-:|:-:|
| **Auth** | ✅ | ✅ | ✅ | ✅ |
| **Scope** | ✅ | ✅ | ✅ | ✅ |
| **Quota** | ❌ (read-only) | ✅ Enforce | ❌ (read-only) | ✅ Enforce |
| **Metering** | Memory | SQLite + Webhook | Memory | SQLite + atexit |
| **Billing** | ❌ | ✅ | ❌ | ✅ |

### Quick Config
```bash
# Simple (default)
VNINVEST_API_KEY=vninvest_pat_...
VNINVEST_GATEWAY_ENABLED=true|false
# Running immediately - no Redis/SQLite/webhook needed

# Advanced (opt-in)
VNINVEST_BILLING_ENABLED=true
VNINVEST_BILLING_WEBHOOK_URL=https://...
VNINVEST_QUOTA_BACKEND=redis
VNINVEST_METERING_BACKEND=sqlite
```

---

## Priority 0: Critical Security & Revenue Protection (Week 1) 🔴 P0

### P0.1 AuthResolver Client Implementation 🔴
**Problem:** Direct Mode cần validate PAT via vninvest `/core/v1/auth/resolve` với local caching (TTL 5 min). No JWT — server là source of truth.

**Solution:** Implement `AuthResolver` class với in-memory cache, TTL, automatic refresh on cache miss/expiry/401.

**Files:**
- `vninvest-sdk/vninvest/auth.py` — Add `AuthResolver` class
- `vninvest-sdk/vninvest/gateway_client.py` — Integrate AuthResolver

**Status:** ✅ Done

---

### P0.2 SQLite Metering Backend + atexit Flush 🔴
**Problem:** Short-lived scripts (backtesting, cron) lose metering events — 30s/100-event flush never triggers. Revenue leakage.

**Solution:** `SQLiteMeteringBackend` persists events immediately to local `.vninvest_metering.db`, forces flush on `atexit` / context manager exit.

**Files:**
- `vninvest-sdk/vninvest/metering.py` — Add `SQLiteMeteringBackend` class
- `vninvest-sdk/vninvest/backends/metering.py` — Backend protocol

**Status:** ✅ Done

---

### P0.3 Bcrypt 72-byte Limit Fix 🔴
**Problem:** PAT > 72 bytes truncated/error when hashed (PAT up to 81 chars).

**Solution:** Pre-hash with SHA-256 before bcrypt.

```python
# Instead of: bcrypt.hash(password[:72])
# Use: bcrypt.hash(sha256(password.encode()).hexdigest()[:72])
```

**Files:**
- `vninvest-sdk/vninvest/auth.py` — APIKeyAuth
- `vninvest-sdk/vninvest/pat.py` — PATStorage

**Status:** ✅ Done

---

## Priority 1: API Contract Unification & PAT Enforcement (Week 1-2) 🔴 P1

### P1.1 Unified Endpoint Mapping 🔴
**Problem:** 
- vnbroker: `/api/v1/quote/history`
- vninvest-fastapi: `/api/v1/quote`
- Django Gateway: `/core/v1/market/quote/history`

**Solution:** Single source of truth = Django Gateway endpoints. Update all clients.

**Files:**
- `vnbroker/core/gateway_client.py`
- `vninvest-sdk/vninvest/gateway_client.py`

**Status:** ✅ Done

---

### P1.2 Vnbroker Client PAT Enforcement 🔴
**Problem:** ARCHITECTURE.md says PAT required for Direct Mode, but code allows direct provider access without PAT.

**Solution:** 
- `Vnbroker.__init__` requires `pat_key` (and optional `gateway_url`)
- Initialize `AuthResolver` + `GatewayHttpClient` (if gateway_url) or Direct backends
- Deprecate `Quote()`, `Company()`, etc. direct instantiation

**Files:**
- `vnbroker/common/client.py` — Vnbroker class
- `vninvest-sdk/vninvest/auth.py` — PAT validation logic
- `ARCHITECTURE.md` — Section 1 & 3
- `README.md`

**Status:** ✅ Done (with broker_auth_bypass support)

---

### P1.3 Direct Mode Public Tier Clarification 🟡
**Decision:** Direct Mode with VCI/KBS/TCBS/MSN: PAT **required** (license enforcement). Public tier = separate documented rate-limited endpoints (not via SDK).

**Files:**
- `ARCHITECTURE.md` — Section 1 table + notes
- `README.md` — Clarify PAT requirement

**Status:** ✅ Done

---

## Priority 2: Zero-Dependency Direct Mode & Provider Resilience (Week 2-3) 🔴 P2

### P2.1 Zero-Dependency Backend Defaults 🔴
**Problem:** Mandating Redis for local dev is a DX barrier.

**Solution:** Default to in-memory/SQLite backends. Redis only for distributed deployments.

**Files:**
- `vninvest-sdk/vninvest/backends/quota.py` — `QuotaBackend` protocol + `MemoryQuotaBackend`
- `vninvest-sdk/vninvest/backends/cache.py` — `CacheBackend` protocol + `MemoryCacheBackend`
- `vninvest-sdk/vninvest/backends/metering.py` — (from P0.2) `SQLiteMeteringBackend`, `MemoryMeteringBackend`

**Status:** ✅ Done

---

### P2.2 Provider Circuit Breaker & Health Check 🔴
**Problem:** AUTO routing lacks circuit breaker — cascade failure risk.

**Solution:** `ProviderCircuitBreaker` (CLOSED→OPEN→HALF_OPEN) + `ProviderHealthChecker` (lightweight `/health` or `/listing` check, <2s = healthy).

**Files:**
- `vnbroker/core/resilience.py` — CircuitBreaker, HealthChecker
- `vnbroker/common/data.py` — StockComponents routing
- `vnbroker/explorer/*/quote.py` — All quote providers

**Status:** ✅ Done (in codebase)

---

### P2.3 Fix Failed Providers (Benchmark) 🟢
| Provider | Issue | Fix |
|----------|-------|-----|
| DNSE | Missing credentials | Add `DNSE_API_KEY`, `DNSE_API_SECRET` env + config |
| News (KBS/VCI/TCBS) | No `market_news` method | Implement news method per provider |
| Trading (KBS/TCBS/VCI) | Wrong param `symbols` vs `symbol_ls` | Fix parameter mapping |
| TCBS Financial | Doesn't accept `lang` param | Remove `lang` from requests |
| MSN | Expects `symbol_id` vs `symbol` | Add parameter mapping |
| FMP | No API key configured | Add `FMP_API_KEY` env + config |

**Files:** `vnbroker/explorer/*/`, `vnbroker/connector/*/`

**Status:** 🟡 Partial (ongoing)

---

## Priority 3: Observability, Streaming & Versioning (Week 3-4) 🟡 P3

### P3.1 OpenTelemetry Tracing Complete 🟡
**Problem:** `observability.py` partial — needs full integration.

**Solution:** Traces for auth resolve, quota check, cache hit/miss, provider calls, metering flush.

**Files:**
- `vninvest-sdk/vninvest/observability.py`

**Status:** ✅ Done

---

### P3.2 Unified StreamManager 🟡
**Problem:** Gateway (WebSocket) vs Direct (Redis pub/sub) parity.

**Solution:** Unified `StreamManager` interface with backend implementations.

**Files:**
- `vninvest-sdk/vninvest/streaming.py`
- `vnbroker/common/stream.py`

**Status:** ✅ Done

---

### P3.3 API Version Negotiation 🟡
**Problem:** Core API `/core/v1/` — need multi-version support.

**Solution:** Client declares `api_version="v1"|"v2"|"auto"`, negotiates with Gateway.

**Files:**
- `vninvest-sdk/vninvest/gateway_client.py`
- `vninvest-sdk/vninvest/config.py`

**Status:** ✅ Done

---

## Priority 4: Testing & Documentation (Week 4-5) 🟡 P4

### P4.1 Test Isolation Fix 🟡
**Problem:** Fixtures leak from `brokerplatform` project — pytest finds wrong `conftest.py`.

**Solution:** Local `conftest.py` in `tests/`, `pytest.ini` with `pythonpath` pointing to current project.

**Files:**
- `tests/conftest.py` — Shared mock fixtures
- `pytest.ini` — `pythonpath = .`

**Status:** ✅ Done

---

### P4.2 Testing Strategy Implementation 🟡
**Structure:**
```
tests/
├── unit/           # Mocked: client, auth, quota, cache, metering
├── integration/    # Real providers (skipped w/o creds)
└── contract/       # OpenAPI schema validation
```

**Files:** Test files per above structure.

**Status:** ✅ Done

---

### P4.3 Documentation 🟢
**Files:**
- `README.md` — Overview, features, installation, PAT requirement
- `docs/QUICKSTART.md` — 5-minute tutorial
- `docs/MIGRATION_GUIDE.md` — v0.1 → v0.2
- `docs/TROUBLESHOOTING.md` — Common errors

**Status:** ✅ Done

---

## Summary

| Priority | Task | Status |
|----------|------|--------|
| ✅ P0.1 | AuthResolver Client | Done |
| ✅ P0.2 | SQLite Metering + atexit | Done |
| ✅ P0.3 | Bcrypt SHA-256 Pre-hash | Done |
| ✅ P1.1 | Unified Endpoints | Done |
| ✅ P1.2 | Vnbroker PAT Enforcement | Done |
| ✅ P1.3 | Public Tier Clarification | Done |
| ✅ P2.1 | Zero-Dependency Backends | Done |
| ✅ P2.2 | Circuit Breaker + Health Check | Done |
| 🟡 P2.3 | Fix Failed Providers | Partial |
| ✅ P3.1 | OpenTelemetry Complete | Done |
| ✅ P3.2 | Unified StreamManager | Done |
| ✅ P3.3 | API Versioning | Done |
| ✅ P4.1 | Test Isolation Fix | Done |
| ✅ P4.2 | Testing Strategy | Done |
| ✅ P4.3 | Documentation | Done |

**Status:** ✅ All Core Tasks Complete

---

## Action Items (Completed)

### P0 (Week 1): ✅
- [x] P0.1 AuthResolver implementation
- [x] P0.2 SQLite Metering Backend + atexit
- [x] P0.3 Bcrypt fix

### P1 (Week 1-2): ✅
- [x] P1.1 Unified endpoints
- [x] P1.2 Vnbroker PAT enforcement + broker_auth_bypass
- [x] P1.3 Simple Mode default

### P2 (Week 2-3): ✅
- [x] P2.1 Advanced Mode backends (optional)
- [x] P2.2 Circuit breaker + health check
- [x] P2.3 Fix failed providers (partial)

### P3 (Week 3-4): ✅
- [x] P3.1 OpenTelemetry complete
- [x] P3.2 StreamManager + Versioning
- [x] P4.1 Test isolation + strategy

### P4 (Week 4-5): ✅
- [x] P4.3 Documentation

---

## Code Implementation Details

### 15.1 Config — Feature Tier Flag
```python
class Settings(BaseSettings):
    billing_enabled: bool = False    # Simple: no enforce
    quota_backend: str = "memory"
    metering_backend: str = "memory"  # No persistence in Simple
    
    billing_webhook_url: str | None = None
```

### 15.2 Quota — Conditional Enforce
```python
async def check_quota(self, tenant_id: str, scope: str, cost: int = 1) -> QuotaResult:
    if not settings.billing_enabled:
        return QuotaResult(allowed=True, remaining=999999)  # Simple: no enforce
    return await self.backend.check_quota(tenant_id, scope, cost)
```

### 15.3 Metering — Simple vs Advanced
```python
class MemoryMeteringBackend:
    # Simple: buffer in memory only
    async def record_event(self, event):
        self._buffer.append(event)  # Drop on overflow

class SQLiteMeteringBackend:
    # Advanced: persistent + atexit flush
    async def record_event(self, event):
        await self._persist(event)
```

## Note: Simple Mode as Default

> **Important:** Simple Mode (auth only, no billing/SQLite/Redis) is the **default** recommendation for most users. This ensures zero friction - user can install and use immediately.

Advanced Mode (metering/billing/quota) should be **opt-in** for production/commercial use.
