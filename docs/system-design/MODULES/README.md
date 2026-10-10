# MODULES — Dossier từng module

| Module | Description | Files |
|:--|:--|:--|
| [Tier 1 Data Engine](tier1-data-engine.md) | Bulk router, health router, provider pool | `core/bulk_router.py`, `core/health_router.py`, `core/provider_pool.py` |
| [Connection Pool](connection-pool.md) | Shared session pool | `core/utils/connection_pool.py` |
| [Normalizer](normalizer.md) | Data normalization | `core/utils/normalizer.py` |
| [Source Router](source-router.md) | Health-based failover | `core/source_router.py` |
| [Provider Registry](provider-registry.md) | Provider registration | `core/registry.py` |
| [Health Store](health-store.md) | Health state persistence | `core/health_store.py` |
| [Cache](cache.md) | TTL cache | `core/utils/cache.py` |
| [Bulk API](bulk-api.md) | Bulk operations API | `api/bulk.py` |
| [Market UI](market-ui.md) | Market facade | `ui/market.py` |
