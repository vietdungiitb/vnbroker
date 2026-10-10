# Tier 1 Data Engine

| | |
|:--|:--|
| **Mã module** | `MOD-T1-01` |
| **Phiên bản** | 1.0 |
| **Files** | `core/bulk_router.py`, `core/health_router.py`, `core/provider_pool.py` |

---

## 1. Tổng quan

Tier 1 Data Engine là bộ phận xử lý dữ liệu thị trường ẩn danh, bao gồm:

- **BulkRouter:** Chia tải bulk trên nhiều provider
- **HealthRouter:** Theo dõi sức khoẻ provider
- **ProviderPool:** Quản lý providers (auth + no-auth)

## 2. BulkRouter

**File:** `vnbroker/core/bulk_router.py`

```python
class BulkRouter:
    def fetch_history(self, symbols: List[str], start: str, end: str, module: str = "quote"):
        # 1. Get healthy providers
        # 2. Distribute symbols (round-robin)
        # 3. Fetch concurrently (ThreadPoolExecutor)
        # 4. Merge results
        ...
```

## 3. HealthRouter

**File:** `vnbroker/core/health_router.py`

```python
class HealthRouter:
    def get_healthy_providers(self, module: str) -> List[str]:
        # 1. Get health snapshot
        # 2. Filter out cooldown providers
        # 3. Sort by average latency
        ...
```

## 4. ProviderPool

**File:** `vnbroker/core/provider_pool.py`

```python
class ProviderPool:
    AUTH_PROVIDERS = {
        "dnse": {"env_key": "DNSE_API_KEY", ...},
        "ssi": {"env_key": "VNBROKER_BROKER_SSI_API_KEY", ...},
        "tcbs": {"env_key": "TCBS_API_KEY", ...},
    }
    
    def get_available_providers(self, module: str) -> List[str]:
        # 1. No-auth providers always available
        # 2. Add auth providers if credentials exist
        ...
```

## 5. Tests

| Test | File |
|:--|:--|
| BulkRouter | `tests/unit/core/test_bulk_router.py` |
| HealthRouter | `tests/unit/core/test_bulk_router.py` |
| ProviderPool | `tests/unit/core/test_provider_pool.py` |
