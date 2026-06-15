# Vninvest SaaS - Implementation Plan & Handover Document

**Project:** vninvest-sdk (Enterprise wrapper for vnbroker)  
**Version:** 0.2.0 (PAT + Core Client)  
**Date:** 2026-06-14  
**Status:** READY FOR EXECUTION  
**Author:** Blackbox AI Code Review

---

## 1. Project Information

| Field | Value |
|-------|-------|
| **Project** | vninvest-sdk |
| **Repository** | `c:\Mujoco Projects\vnbrokder\vninvest-sdk` |
| **Target Version** | 0.2.0 |
| **Python** | 3.10+ |
| **Key Dependencies** | FastAPI (optional), Pydantic v2, Redis async, bcrypt |

---

## 2. Scope

### In Scope (P0 - Must Have)

| ID | Deliverable | Description |
|----|-------------|-------------|
| **PAT-01** | PAT Models | `PATScope`, `PersonalAccessToken` in `models.py` |
| **PAT-02** | PAT Storage | Redis schema + CRUD operations (create, list, revoke, rotate) |
| **PAT-03** | PAT Auth | `_resolve_pat()` in `auth.py`, credential routing (PAT vs Legacy) |
| **PAT-04** | Scope Authorization | `ScopeDeniedError`, `TenantContext.effective_scopes`, FastAPI dependency |
| **PAT-05** | PAT Admin API | `AdminClient.create_pat/list_pats/revoke_pat/rotate_pat` |
| **CORE-01** | `VninvestClient` | Main entry point wiring auth→quota→cache→metering→vnbroker |
| **CORE-02** | Core Methods | `quote()`, `company()`, `finance()`, `news()`, `stream()` |
| **TEST-01** | Unit Tests | `fakeredis` tests for Quota, Cache, Metering, PAT |
| **TEST-02** | Integration Tests | PAT flow + Client flow with vnbroker mock |

### Out of Scope (Deferred to Phase 2)

- FastAPI middleware/routes (`vninvest_fastapi/`)
- Streaming providers implementation (VCI/KBS WebSocket)
- OpenTelemetry observability
- CacheWarmer implementation
- Symbol-level authorization

---

## 3. Technical Design

### 3.1 PAT Data Model (`vninvest/models.py`)

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
    token_hash: str          # bcrypt hash
    prefix: str              # "vninvest_pat_abc123" (12 chars)
    scopes: List[PATScope]
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    revoked_at: Optional[datetime]
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### 3.2 Redis Schema

| Key Pattern | TTL | Value |
|-------------|-----|-------|
| `vninvest:pat:{pat_id}` | max(90d, expiry) | PAT JSON |
| `vninvest:pat:index:{prefix}` | max(90d, expiry) | `pat_id` |
| `vninvest:pat:tenant:{tenant_id}` | Set | `{pat_id}` |
| `vninvest:pat:user:{user_id}` | Set | `{pat_id}` |

### 3.3 Auth Flow (`vninvest/auth.py`)

```python
async def resolve_tenant(self, credential: str) -> TenantContext:
    if credential.startswith("vninvest_pat_"):
        return await self._resolve_pat(credential)
    elif credential.startswith("vninvest_"):
        return await self._resolve_legacy_api_key(credential)
    raise AuthenticationError("Invalid credential format")

async def _resolve_pat(self, pat_token: str) -> TenantContext:
    # 1. Extract prefix (first 22 chars: "vninvest_pat_abcdefgh")
    # 2. Redis GET vninvest:pat:index:{prefix} -> pat_id
    # 3. Redis GET vninvest:pat:{pat_id} -> PAT data
    # 4. Verify bcrypt hash
    # 5. Check revoked_at, expires_at
    # 6. Load tenant, merge scopes -> effective_limits
    # 7. Fire-and-forget update last_used_at
    # 8. Return TenantContext(pat_id=..., user_id=..., effective_scopes=...)
```

### 3.4 TenantContext Extension (`vninvest/models.py`)

```python
class TenantContext(BaseModel):
    # ... existing fields ...
    pat_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    effective_scopes: List[PATScope] = Field(default_factory=list)
    effective_limits: PlanLimits  # merged from plan + PAT scopes
```

### 3.5 Scope Authorization

```python
# exceptions.py
class ScopeDeniedError(VninvestError):
    def __init__(self, required_scope: str):
        super().__init__(f"Token missing required scope: {required_scope}",
                         code="SCOPE_DENIED", status_code=403)

# FastAPI dependency (in vninvest_fastapi/middleware/auth.py)
async def require_scope(scope: PATScope):
    def dependency(context: TenantContext = Depends(get_tenant_context)):
        if scope not in context.effective_scopes:
            raise ScopeDeniedError(scope.value)
    return dependency
```

### 3.6 VninvestClient (`vninvest/client.py`)

```python
class VninvestClient:
    def __init__(self, api_key: str, *, 
                 auth: APIKeyAuth = None,
                 quota: QuotaManager = None,
                 cache: CacheLayer = None,
                 metering: UsageTracker = None,
                 stream: StreamManager = None,
                 vnbroker_source: str = "AUTO"):
        self.context = await auth.resolve_tenant(api_key)
        self._broker = Vnbroker(source=vnbroker_source)
        self._quota = quota
        self._cache = cache
        self._metering = metering
        self._stream = stream

    async def quote(self, request: QuoteRequest) -> QuoteResponse:
        async with QuotaContextManager(self._quota, self.context, reserve_daily=1):
            # Check scope
            if PATScope.QUOTE_READ not in self.context.effective_scopes:
                raise ScopeDeniedError("quote:read")
            # Cache key
            cache_key = self._cache._make_cache_key("quote", "history", request.model_dump())
            cached, hit = await self._cache.get_or_fetch(cache_key, lambda: self._fetch_quote(request))
            # Metering
            await self._metering.record_call(...)
            return cached

    async def stream(self, config: StreamConfig) -> PriceStream:
        if PATScope.STREAM_PRICE not in self.context.effective_scopes:
            raise ScopeDeniedError("stream:price")
        return PriceStream(self._stream, self.context, config)
```

---

## 4. Work Breakdown

### Sprint 1: PAT Foundation (3-4 days)

| Task | Owner | Est. | Dependencies |
|------|-------|------|--------------|
| PAT-01: Add `PATScope`, `PersonalAccessToken` to `models.py` | Backend | 0.5 day | - |
| PAT-02: Create `vninvest/pat.py` — PAT storage backend (Redis CRUD) | Backend | 1.5 days | PAT-01 |
| PAT-03: Extend `auth.py` — `_resolve_pat()`, credential routing | Backend | 1 day | PAT-02 |
| PAT-04: Extend `TenantContext` in `models.py` — `pat_id`, `user_id`, `effective_scopes` | Backend | 0.5 day | PAT-01 |
| PAT-05: Add `ScopeDeniedError` to `exceptions.py` | Backend | 0.5 day | - |
| PAT-06: Unit tests for PAT storage + auth resolution | QA | 1 day | PAT-02, PAT-03 |

### Sprint 2: PAT Admin API + Scope Enforcement (2 days)

| Task | Owner | Est. | Dependencies |
|------|-------|------|--------------|
| PAT-07: `AdminClient.create_pat/list_pats/revoke_pat/rotate_pat` | Backend | 1 day | PAT-02 |
| PAT-08: Scope enforcement in `QuotaManager`/`CacheLayer`/`StreamManager` | Backend | 0.5 day | PAT-04 |
| PAT-09: Integration tests (PAT create → use → revoke) | QA | 0.5 day | PAT-07 |

### Sprint 3: VninvestClient Core (2-3 days)

| Task | Owner | Est. | Dependencies |
|------|-------|------|--------------|
| CORE-01: Implement `VninvestClient` in `client.py` | Backend | 1.5 days | PAT-03, PAT-04 |
| CORE-02: Implement `quote()`, `company()`, `finance()`, `news()` methods | Backend | 1 day | CORE-01 |
| CORE-03: Implement `stream()` method returning `PriceStream` | Backend | 0.5 day | CORE-01 |
| CORE-04: Integration tests (Client full flow) | QA | 1 day | CORE-02 |

### Sprint 4: Polish & Handoff (1 day)

| Task | Owner | Est. |
|------|-------|------|
| Update `pyproject.toml` — add `bcrypt` dependency | Backend | 0.5 day |
| Update `__init__.py` exports | Backend | 0.5 day |
| Write `HANDOVER.md` (this doc) | Tech Lead | 0.5 day |
| Code review & merge | Team | 1 day |

---

## 5. Quality Gates

| Gate | Requirement |
|------|-------------|
| **Code Style** | `ruff check .` pass, `black --check .` pass |
| **Type Check** | `mypy vninvest` pass (strict mode) |
| **Unit Tests** | `pytest tests/ -v --cov=vninvest --cov-fail-under=80` |
| **Integration Tests** | PAT flow + Client flow pass with `fakeredis` |
| **Security** | No plaintext tokens in logs, bcrypt cost >= 12 |
| **Performance** | Quota check < 5ms (Redis), Cache hit < 2ms |

---

## 6. Risks & Mitigation

| Risk | Severity | Mitigation |
|------|----------|------------|
| `fakeredis` doesn't fully support Lua scripts | High | Test quota Lua script on real Redis in CI (testcontainers) |
| vnbroker API breaking changes | Medium | Pin `vnbroker` version, daily integration test |
| PAT migration from legacy key complex | Low | Defer migration logic to Phase 2, only log warning |
| bcrypt performance at high throughput | Low | Use async bcrypt (thread pool), cache verified PAT 5min |

---

## 7. Handover Checklist

### Files to Create/Modify

```
vninvest-sdk/
├── vninvest/
│   ├── models.py          # + PATScope, PersonalAccessToken, TenantContext extensions
│   ├── exceptions.py      # + ScopeDeniedError
│   ├── auth.py            # + _resolve_pat, credential routing
│   ├── pat.py             # NEW: PAT storage backend (Redis CRUD)
│   ├── client.py          # NEW: VninvestClient implementation
│   ├── admin.py           # + create_pat, list_pats, revoke_pat, rotate_pat
│   ├── quota.py           # + scope check in QuotaContextManager
│   ├── cache.py           # + scope check in CacheLayer
│   ├── streaming.py       # + scope check in StreamManager/PriceStream
│   └── __init__.py        # + export new symbols
├── tests/
│   ├── test_pat.py        # NEW: PAT storage + auth tests
│   ├── test_client.py     # NEW: VninvestClient tests
│   ├── test_quota.py      # EXTEND: add scope tests
│   ├── test_cache.py      # EXTEND: add scope tests
│   └── conftest.py        # NEW: fakeredis fixtures
├── pyproject.toml         # + bcrypt dependency
└── HANDOVER.md            # THIS DOCUMENT
```

### New Dependencies

```toml
# pyproject.toml
dependencies = [
    ...
    "bcrypt>=4.0",        # PAT token hashing
    "vnbroker @ file://../vnbroker",  # local path dependency
]
```

### Test Fixtures (`tests/conftest.py`)

```python
import pytest
import fakeredis.aioredis
from vninvest.pat import PATStorage
from vninvest.models import PersonalAccessToken, PATScope
from uuid import uuid4
from datetime import datetime, timedelta
import bcrypt

@pytest.fixture
async def redis_client():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()

@pytest.fixture
async def pat_storage(redis_client):
    return PATStorage(redis_client=redis_client)

@pytest.fixture
def sample_pat():
    return PersonalAccessToken(
        tenant_id=uuid4(),
        user_id=uuid4(),
        name="Test PAT",
        token_hash=bcrypt.hashpw(b"test_token", bcrypt.gensalt(12)).decode(),
        prefix="vninvest_pat_abcdefgh",
        scopes=[PATScope.QUOTE_READ, PATScope.COMPANY_READ],
        expires_at=datetime.utcnow() + timedelta(days=30),
    )
```

### Migration Notes (for Phase 2)

- Legacy API key: log warning, auto-create PAT with `scopes=ALL`, `name="Legacy API Key"`
- Hard cutoff: 6 months after PAT GA
- Document at `docs/PAT_MIGRATION_GUIDE.md`

---

## 8. Acceptance Criteria

| Feature | Criteria |
|---------|----------|
| **PAT Create** | Admin creates PAT via `AdminClient.create_pat()` → returns `(PAT_model, plaintext_token)` only once |
| **PAT Auth** | `APIKeyAuth.resolve_tenant("vninvest_pat_...")` → `TenantContext` with correct `effective_scopes` |
| **Scope Enforcement** | Client calls `quote()` but PAT lacks `quote:read` → raises `ScopeDeniedError(403)` |
| **PAT Revoke** | `AdminClient.revoke_pat(pat_id)` → PAT unusable immediately |
| **PAT Rotate** | `AdminClient.rotate_pat(pat_id, overlap_hours=24)` → new PAT active, old expires after 24h |
| **VninvestClient** | `client = VninvestClient(pat_token); await client.quote(QuoteRequest(...))` → returns `QuoteResponse` |
| **Metering** | Every call via Client records `MeteringEvent` with `pat_id`, `user_id`, `scopes` |
| **Tests** | Coverage >= 80%, all tests pass on `fakeredis` |

---

## 9. Timeline

| Week | Sprint | Deliverables |
|------|--------|--------------|
| 1 | Sprint 1 | PAT Models, Storage, Auth, TenantContext, ScopeDeniedError, Unit Tests |
| 2 | Sprint 2 | PAT Admin API, Scope Enforcement, Integration Tests |
| 3 | Sprint 3 | VninvestClient (quote, company, finance, news, stream), Integration Tests |
| 4 | Sprint 4 | Polish, Dependencies, Exports, Handover Doc, Code Review |

**Total Estimate: 8-10 working days (2 weeks)**

---

## 10. Contacts & Escalation

| Role | Contact | Channel |
|------|---------|---------|
| Tech Lead | [Name] | Slack #vninvest-sdk |
| Backend Dev | [Name] | Slack #vninvest-sdk |
| QA | [Name] | Slack #vninvest-sdk |
| Product Owner | [Name] | Email/Slack |

---

**Document Version:** 1.0  
**Created:** 2026-06-14  
**Status:** READY FOR EXECUTION  
**Approval:** [ ] Tech Lead  [ ] Product Owner