# Vninvest SaaS - Code Review Report (UPDATED)

**Project:** vninvest-sdk (Enterprise wrapper for vnbroker)  
**Date:** 2026-06-14  
**Reviewer:** Blackbox AI  
**Version:** 0.1.0 (Alpha)

---

## 📋 Executive Summary

`vninvest-sdk` is designed as a **SaaS-grade enterprise wrapper** around the `vnbroker` library, providing multi-tenancy, quota enforcement, usage metering, caching, real-time streaming, and admin APIs.

**Overall Assessment:** 🟡 **Architecture solid, but NOT production-ready** — Critical missing pieces: main client implementation, FastAPI integration, tests, real vnbroker integration, **and PAT (Personal Access Token) system**.

---

## ✅ Strengths

| Module | File | Highlights |
|--------|------|------------|
| **Authentication** | `auth.py` | Dual-mode (local HMAC / remote HTTP), 5-min cache TTL, proper error types (suspended, not found) |
| **Quota Management** | `quota.py` | Atomic Redis Lua scripts (check-and-increment), in-memory fallback, `QuotaContextManager` async context manager |
| **Metering & Billing** | `metering.py` | Redis sorted-set time-series storage, p50/p95/p99 latency aggregation, batched webhook emitter |
| **Caching** | `cache.py` | Multi-serializer (JSON/pickle), tenant-isolated keys, `CacheWarmer` cron scheduler, hit/miss metrics |
| **Streaming** | `streaming.py` | Multi-provider (VCI/KBS), deduplication window, backpressure handling (bounded queues), failover design |
| **Admin API** | `admin.py` | Full CRUD tenant, usage reporting, health checks, quota overrides, CSV export, `LocalAdminClient` for self-hosted |
| **Data Models** | `models.py` | Pydantic v2, strict validation (symbols, intervals), tier-based plan defaults (Free/Pro/Enterprise) |
| **Exceptions** | `exceptions.py` | Clear hierarchy, `to_dict()` for API responses, proper HTTP status codes |

---

## ⚠️ Critical Issues (P0 - Blockers)

### 1. **Main Client Stub** — `vninvest/client.py`
```python
# Current content:
test content
```
- `__init__.py` exports `VninvestClient` but implementation is a stub.
- **SDK cannot be used** — no entry point to wire auth → quota → cache → vnbroker.

### 2. **PAT (Personal Access Token) System Missing** — **NEWLY IDENTIFIED**
- **Only legacy API Key format supported**: `vninvest_{tenant_id}_{timestamp}_{hmac_signature}`
- **No PAT support**: User-created tokens with scopes, expiry, revocation, rotation.
- **Security gaps**: 
  - Tenant ID exposed in API key (enumeration risk)
  - No fine-grained scopes (all-or-nothing access)
  - No token expiry/rotation policy
  - No audit trail per token (which token called what)
  - User cannot self-service token creation/revocation

### 3. **FastAPI Integration Empty** — `vninvest_fastapi/`
```
vninvest_fastapi/
├── middleware/  # EMPTY
└── routes/      # EMPTY
```
- `pyproject.toml` declares `optional-dependencies.fastapi` but zero implementation.
- Need: Auth/Quota/Metering middleware + REST routes (`/quote`, `/company`, `/finance`, `/stream`, `/admin`).

### 4. **No Tests** — `tests/`
- Directory exists but completely empty.
- No unit/integration tests for quota, cache, metering, streaming, auth.

### 5. **Streaming Stub Methods** — `streaming.py`
- `VCIStreamProvider._send_subscription()` — `pass` (no WebSocket implementation)
- `KBSStreamProvider._poll_once()` — `pass` (no polling implementation)
- `CacheWarmer._warm_symbol_data_type()` — `pass` (no warming implementation)

### 6. **Missing Import** — `admin.py`
- `LocalAdminClient` uses `redis.asyncio` but no import for `redis` module at line 267

### 7. **No Configuration Management**
- Hardcoded Redis URLs, key prefixes scattered across modules.
- `pydantic-settings` in deps but unused — no `config.py`/`settings.py`.

### 8. **Observability Not Implemented**
- `opentelemetry-*` dependencies declared but **zero usage** in codebase (no tracing, metrics export).

### 9. **Symbol Authorization Missing**
- `SymbolNotAllowedError` defined in exceptions but **never enforced** in quota/cache/streaming layers.

---

## 🔧 Recommended Priority Fixes (UPDATED)

| Priority | Task | Est. Effort |
|----------|------|-------------|
| 🔴 **P0** | **PAT System: Model, Storage, Auth Resolution, Scope Authorization** | 3-4 days |
| 🔴 **P0** | **PAT Admin API: CRUD, Rotation, Revocation, Audit** | 2 days |
| 🔴 **P0** | Implement `VninvestClient` in `client.py` — wire all components | 2-3 days |
| 🔴 **P0** | Write core tests (QuotaManager, CacheLayer, UsageTracker) using `fakeredis` | 2 days |
| 🟠 **P1** | Scaffold `vninvest_fastapi`: middleware (auth, quota, metering) + 3-4 REST routes | 3-4 days |
| 🟠 **P1** | Hook real vnbroker streaming into `VCIStreamProvider`/`KBSStreamProvider` | 2-3 days |
| 🟡 **P2** | Add `config.py` with `pydantic-settings` — centralize Redis, prefixes, timeouts | 1 day |
| 🟡 **P2** | Integrate OpenTelemetry tracing for request flows | 1-2 days |
| 🟢 **P3** | Implement symbol-level authorization (whitelist/blacklist per tenant) | 1-2 days |
| 🟢 **P3** | Complete `CacheWarmer` implementation | 1 day |

---

## 🔑 PAT (Personal Access Token) — Detailed Design Required

### PAT vs Legacy API Key

| Feature | Legacy API Key | PAT (Required) |
|---------|----------------|----------------|
| **Creator** | System (Admin) | User (Self-service) |
| **Format** | `vninvest_{tenant_id}_{ts}_{sig}` | Opaque: `vninvest_pat_{random32}` |
| **Scope** | Tenant-wide (plan limits) | Fine-grained: `quote:read`, `stream:price`, `admin:tenant` |
| **Expiry** | Hardcoded 1 year | Configurable (7d/30d/90d/never) |
| **Revocation** | Suspend tenant only | Per-token revoke (user + admin) |
| **Rotation** | Not supported | Supported with overlap window |
| **Audit** | Tenant-level only | Per-token: `pat_id`, `user_id`, `last_used_at`, `scopes` |

### Required Components

#### A. Models (`models.py` — Add)
```python
class PATScope(str, Enum):
    QUOTE_READ = "quote:read"
    COMPANY_READ = "company:read"
    FINANCE_READ = "finance:read"
    NEWS_READ = "news:read"
    STREAM_PRICE = "stream:price"
    STREAM_DEPTH = "stream:depth"
    STREAM_TRADE = "stream:trade"
    ADMIN_TENANT = "admin:tenant"

class PersonalAccessToken(BaseModel):
    pat_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    user_id: UUID
    name: str
    token_hash: str          # bcrypt/argon2, NEVER plaintext
    prefix: str              # "vninvest_pat_abc123" (first 12 chars for lookup)
    scopes: List[PATScope]
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    revoked_at: Optional[datetime]
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

#### B. Auth Extension (`auth.py`)
```python
class APIKeyAuth:
    async def resolve_tenant(self, credential: str) -> TenantContext:
        if credential.startswith("vninvest_pat_"):
            return await self._resolve_pat(credential)
        elif credential.startswith("vninvest_"):
            return await self._resolve_legacy_api_key(credential)
        raise AuthenticationError("Invalid credential format")

    async def _resolve_pat(self, pat_token: str) -> TenantContext:
        # 1. Lookup by prefix -> pat_id
        # 2. Verify bcrypt hash
        # 3. Check expiry, revocation
        # 4. Load tenant + merge PAT scopes into effective limits
        # 5. Async update last_used_at
        pass
```

#### C. TenantContext Extension
```python
class TenantContext(BaseModel):
    # ... existing ...
    pat_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    effective_scopes: List[PATScope] = Field(default_factory=list)
    # effective_limits = merge(plan_limits, pat_scope_limits)
```

#### D. Scope Authorization (New Exception + Middleware)
```python
# exceptions.py
class ScopeDeniedError(VninvestError):
    def __init__(self, required_scope: str):
        super().__init__(f"Token missing required scope: {required_scope}", 
                         code="SCOPE_DENIED", status_code=403)

# FastAPI dependency
async def require_scope(scope: PATScope):
    def dep(context: TenantContext = Depends(get_tenant_context)):
        if scope not in context.effective_scopes:
            raise ScopeDeniedError(scope.value)
    return dep
```

#### E. Redis Schema for PAT
| Key | TTL | Value |
|-----|-----|-------|
| `vninvest:pat:{pat_id}` | 90d / expiry | Full PAT JSON |
| `vninvest:pat:index:{prefix}` | 90d / expiry | `pat_id` (lookup) |
| `vninvest:pat:tenant:{tenant_id}` | Set | `{pat_id}` |
| `vninvest:pat:user:{user_id}` | Set | `{pat_id}` |

#### F. Admin API Extensions (`admin.py`)
```python
class AdminClient:
    async def create_pat(self, tenant_id, user_id, name, scopes, expires_in_days=30) -> tuple[PersonalAccessToken, str]:
        # Returns (model, plaintext_token) — plaintext shown ONCE
        pass
    async def list_pats(self, tenant_id, user_id=None) -> List[PersonalAccessToken]: pass
    async def revoke_pat(self, pat_id: UUID) -> bool: pass
    async def rotate_pat(self, pat_id: UUID, overlap_hours=24) -> tuple[PersonalAccessToken, str]: pass
```

#### G. Migration Path
1. Deprecate legacy format — log warning on use.
2. Auto-migrate: On legacy key use, create PAT with `scopes=ALL`, `name="Legacy API Key"`.
3. Hard cutoff: 6 months after PAT GA → reject legacy keys.

---

## 🏗️ Proposed `VninvestClient` Architecture

```python
# vninvest/client.py (to be implemented)
class VninvestClient:
    def __init__(
        self,
        api_key: str,
        *,
        auth: APIKeyAuth = None,
        quota: QuotaManager = None,
        cache: CacheLayer = None,
        metering: UsageTracker = None,
        stream: StreamManager = None,
        vnbroker_source: str = "AUTO",
    ):
        # 1. Resolve tenant context (supports PAT + legacy)
        self.context = await auth.resolve_tenant(api_key)
        
        # 2. Initialize vnbroker client per tenant config
        self._broker = Vnbroker(source=vnbroker_source)
        
        # 3. Wire middleware components
        self._quota = quota
        self._cache = cache
        self._metering = metering

    async def quote(self, request: QuoteRequest) -> QuoteResponse:
        async with QuotaContextManager(self._quota, self.context):
            # Check cache
            cached, hit = await self._cache.get_or_fetch(...)
            if hit: return cached
            
            # Call vnbroker
            start = time.time()
            df = self._broker.stock(request.symbols[0]).quote.history(...)
            latency = int((time.time() - start) * 1000)
            
            # Record metering
            await self._metering.record_call(...)
            
            # Cache & return
            await self._cache.set(...)
            return QuoteResponse(...)
```

---

## 📦 Dependency Notes

- `vnbroker>=1.0.2` — available in monorepo (`../vnbroker`); use **path dependency** for local dev:
  ```toml
  dependencies = [
      "vnbroker @ file://../vnbroker",
      ...
  ]
  ```
- `fakeredis` in `dev` deps — excellent for testing without real Redis.
- **Add for PAT**: `bcrypt` or `argon2-cffi` for token hashing.

---

## 📊 Scorecard (UPDATED)

| Criterion | Score | Notes |
|-----------|-------|-------|
| **Architecture** | 6/10 | Modular but coupling via Redis keys, no PAT, no abstraction for vnbroker |
| **Completeness** | 2/10 | Missing core client, PAT, FastAPI, tests |
| **Code Quality** | 6/10 | Type hints good; Lua TTL overhead, dedup leak, security concerns |
| **Production Ready** | ❌ No | Cannot run without `VninvestClient` + PAT system |

---

## 🎯 Next Steps (Priority Order)

1. **Implement PAT System** (Model, Storage, Auth, Scopes) — **unblocks secure multi-tenant access**
2. **Implement `VninvestClient`** — wires PAT auth → quota → cache → vnbroker
3. **Add test suite** — `fakeredis` + `pytest-asyncio` for quota/cache/metering/PAT
4. **Scaffold FastAPI** — middleware stack + minimal routes for demo
5. **Integration test** with real `vnbroker` (local path dependency)

---

*Generated by Blackbox AI Code Review*