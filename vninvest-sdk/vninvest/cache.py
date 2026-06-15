"""
Redis-backed caching layer for Vninvest SDK.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import pickle
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypeVar

import redis.asyncio as redis

from .exceptions import CacheError, ScopeDeniedError
from .models import PATScope, TenantContext

T = TypeVar("T")


class CacheBackend(ABC):
    """Abstract cache backend."""

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        pass

    @abstractmethod
    async def clear_pattern(self, pattern: str) -> int:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass


class RedisCacheBackend(CacheBackend):
    """Redis cache backend with connection pooling."""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        key_prefix: str = "vninvest:cache",
        default_ttl: int = 300,
        max_connections: int = 50,
        serializer: str = "json",  # json, pickle, msgpack
    ):
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self.default_ttl = default_ttl
        self.max_connections = max_connections
        self.serializer = serializer
        self._pool: redis.ConnectionPool | None = None
        self._redis: redis.Redis | None = None

    async def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._pool = redis.ConnectionPool.from_url(
                self.redis_url,
                max_connections=self.max_connections,
                decode_responses=self.serializer == "json",
            )
            self._redis = redis.Redis(connection_pool=self._pool)
            await self._redis.ping()
        return self._redis

    def _make_key(self, key: str) -> str:
        return f"{self.key_prefix}:{key}"

    def _serialize(self, value: Any) -> str | bytes:
        if self.serializer == "json":
            return json.dumps(value, default=str, separators=(",", ":"))
        elif self.serializer == "pickle":
            return pickle.dumps(value)
        else:
            raise ValueError(f"Unsupported serializer: {self.serializer}")

    def _deserialize(self, data: str | bytes) -> Any:
        if self.serializer == "json":
            return json.loads(data)
        elif self.serializer == "pickle":
            return pickle.loads(data)
        else:
            raise ValueError(f"Unsupported serializer: {self.serializer}")

    async def get(self, key: str) -> Any | None:
        r = await self._get_redis()
        full_key = self._make_key(key)
        try:
            data = await r.get(full_key)
            if data is None:
                return None
            return self._deserialize(data)
        except Exception as e:
            raise CacheError(f"Cache get failed: {e}", operation="get") from e

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        r = await self._get_redis()
        full_key = self._make_key(key)
        ttl = ttl_seconds or self.default_ttl
        try:
            serialized = self._serialize(value)
            await r.setex(full_key, ttl, serialized)
        except Exception as e:
            raise CacheError(f"Cache set failed: {e}", operation="set") from e

    async def delete(self, key: str) -> None:
        r = await self._get_redis()
        full_key = self._make_key(key)
        try:
            await r.delete(full_key)
        except Exception as e:
            raise CacheError(f"Cache delete failed: {e}", operation="delete") from e

    async def exists(self, key: str) -> bool:
        r = await self._get_redis()
        full_key = self._make_key(key)
        try:
            return await r.exists(full_key) > 0
        except Exception as e:
            raise CacheError(f"Cache exists failed: {e}", operation="exists") from e

    async def clear_pattern(self, pattern: str) -> int:
        r = await self._get_redis()
        full_pattern = self._make_key(pattern)
        try:
            count = 0
            async for key in r.scan_iter(match=full_pattern, count=100):
                await r.delete(key)
                count += 1
            return count
        except Exception as e:
            raise CacheError(f"Cache clear pattern failed: {e}", operation="clear_pattern") from e

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
            self._redis = None
        if self._pool:
            await self._pool.disconnect()
            self._pool = None


class InMemoryCacheBackend(CacheBackend):
    """In-memory cache backend for development/testing."""

    def __init__(self, default_ttl: int = 300):
        self.default_ttl = default_ttl
        self._cache: dict[str, tuple[Any, float]] = {}
        self._lock = asyncio.Lock()

    def _is_expired(self, expires_at: float) -> bool:
        return time.time() > expires_at

    async def get(self, key: str) -> Any | None:
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if self._is_expired(expires_at):
                del self._cache[key]
                return None
            return value

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        async with self._lock:
            ttl = ttl_seconds or self.default_ttl
            self._cache[key] = (value, time.time() + ttl)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._cache.pop(key, None)

    async def exists(self, key: str) -> bool:
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            _, expires_at = entry
            if self._is_expired(expires_at):
                del self._cache[key]
                return False
            return True

    async def clear_pattern(self, pattern: str) -> int:
        import fnmatch

        async with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if fnmatch.fnmatch(k, pattern)]
            for k in keys_to_delete:
                del self._cache[k]
            return len(keys_to_delete)

    async def close(self) -> None:
        self._cache.clear()


@dataclass
class CacheConfig:
    """Configuration for cache behavior per data type."""

    # TTL in seconds for different data types
    quote_history_ttl: int = 60
    quote_intraday_ttl: int = 10
    quote_depth_ttl: int = 5
    company_overview_ttl: int = 3600
    company_profile_ttl: int = 3600
    finance_report_ttl: int = 3600
    finance_ratio_ttl: int = 1800
    listing_symbols_ttl: int = 86400
    news_latest_ttl: int = 300
    news_search_ttl: int = 600
    snapshot_heatmap_ttl: int = 60

    # Global settings
    enabled: bool = True
    max_key_length: int = 200
    compress_large_values: bool = True
    compression_threshold_bytes: int = 10240

    def get_ttl(self, data_type: str) -> int:
        """Get TTL for a data type."""
        mapping = {
            "quote_history": self.quote_history_ttl,
            "quote_intraday": self.quote_intraday_ttl,
            "quote_depth": self.quote_depth_ttl,
            "company_overview": self.company_overview_ttl,
            "company_profile": self.company_profile_ttl,
            "finance_report": self.finance_report_ttl,
            "finance_ratio": self.finance_ratio_ttl,
            "listing_symbols": self.listing_symbols_ttl,
            "news_latest": self.news_latest_ttl,
            "news_search": self.news_search_ttl,
            "snapshot_heatmap": self.snapshot_heatmap_ttl,
        }
        return mapping.get(data_type, self.default_ttl)

    @property
    def default_ttl(self) -> int:
        return 300


class CacheLayer:
    """
    High-level cache layer with tenant-aware keys and automatic TTL.

    Features:
    - Tenant-isolated cache keys
    - Per-data-type TTL configuration
    - Automatic cache key generation from request params
    - Cache warming for popular symbols
    - Metrics collection (hit/miss rates)
    - Scope-based access control
    """

    def __init__(
        self,
        backend: CacheBackend,
        config: CacheConfig | None = None,
        tenant_context: TenantContext | None = None,
    ):
        self.backend = backend
        self.config = config or CacheConfig()
        self.tenant_context = tenant_context

        # Metrics
        self._hits = 0
        self._misses = 0
        self._lock = asyncio.Lock()

    def _check_scope(self, required_scope: PATScope) -> None:
        """Check if tenant context has required scope."""
        if self.tenant_context and not self.tenant_context.has_scope(required_scope):
            raise ScopeDeniedError(required_scope.value)

    def _make_cache_key(
        self,
        data_type: str,
        endpoint: str,
        params: dict[str, Any],
    ) -> str:
        """Generate deterministic cache key from request parameters."""
        # Sort params for consistent keys
        sorted_params = sorted(params.items())
        param_str = "&".join(f"{k}={v}" for k, v in sorted_params if v is not None)

        # Hash if too long
        if len(param_str) > self.config.max_key_length:
            param_hash = hashlib.sha256(param_str.encode()).hexdigest()[:16]
            param_str = f"hash:{param_hash}"

        tenant_prefix = f"tenant:{self.tenant_context.tenant_id}:" if self.tenant_context else "global:"
        return f"{tenant_prefix}{data_type}:{endpoint}:{param_str}"

    async def get_or_fetch(
        self,
        data_type: str,
        endpoint: str,
        params: dict[str, Any],
        fetch_func: Callable[[], Any],
        ttl_override: int | None = None,
        required_scope: PATScope | None = None,
    ) -> tuple[Any, bool]:
        """
        Get from cache or fetch and cache.

        Returns:
            Tuple of (value, cache_hit)
        """
        # Check scope if required
        if required_scope:
            self._check_scope(required_scope)

        if not self.config.enabled:
            value = await fetch_func() if asyncio.iscoroutinefunction(fetch_func) else fetch_func()
            return value, False

        cache_key = self._make_cache_key(data_type, endpoint, params)
        ttl = ttl_override or self.config.get_ttl(data_type)

        # Try cache
        cached = await self.backend.get(cache_key)
        if cached is not None:
            async with self._lock:
                self._hits += 1
            return cached, True

        # Cache miss - fetch
        async with self._lock:
            self._misses += 1

        value = await fetch_func() if asyncio.iscoroutinefunction(fetch_func) else fetch_func()

        # Store in cache
        await self.backend.set(cache_key, value, ttl)

        return value, False

    async def invalidate(self, data_type: str, endpoint: str, params: dict[str, Any]) -> None:
        """Invalidate a specific cache entry."""
        cache_key = self._make_cache_key(data_type, endpoint, params)
        await self.backend.delete(cache_key)

    async def invalidate_symbol(self, symbol: str) -> None:
        """Invalidate all cache entries for a symbol."""
        pattern = f"*{symbol.upper()}*"
        await self.backend.clear_pattern(pattern)

    async def invalidate_tenant(self) -> None:
        """Invalidate all cache entries for current tenant."""
        if not self.tenant_context:
            return
        pattern = f"tenant:{self.tenant_context.tenant_id}:*"
        await self.backend.clear_pattern(pattern)

    def get_metrics(self) -> dict[str, Any]:
        """Get cache hit/miss metrics."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "total": total,
            "hit_rate_pct": round(self._hits / total * 100, 2) if total > 0 else 0,
        }

    def reset_metrics(self) -> None:
        """Reset cache metrics."""
        self._hits = 0
        self._misses = 0


class CacheWarmer:
    """
    Background cache warming for popular symbols.

    Pre-fetches and caches data for configured symbols during off-peak hours.
    """

    def __init__(
        self,
        cache_layer: CacheLayer,
        vnbroker_client: Any,  # VninvestClient or vnbroker.Vnbroker
        symbols: list[str],
        data_types: list[str] = None,
        schedule_cron: str = "0 2 * * *",  # 2 AM daily
        max_concurrent: int = 10,
    ):
        self.cache_layer = cache_layer
        self.vnbroker_client = vnbroker_client
        self.symbols = [s.upper() for s in symbols]
        self.data_types = data_types or ["quote_history", "company_overview", "finance_report"]
        self.schedule_cron = schedule_cron
        self.max_concurrent = max_concurrent
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start background warming scheduler."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_scheduler())

    async def stop(self) -> None:
        """Stop background warming."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def warm_now(self) -> dict[str, int]:
        """Trigger immediate cache warming."""
        return await self._warm_symbols()

    async def _run_scheduler(self) -> None:
        import croniter

        cron = croniter.croniter(self.schedule_cron, datetime.now())
        while self._running:
            next_run = cron.get_next(datetime)
            wait_seconds = (next_run - datetime.now()).total_seconds()
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            if self._running:
                await self._warm_symbols()

    async def _warm_symbols(self) -> dict[str, int]:
        """Warm cache for all configured symbols."""
        results = {"warmed": 0, "failed": 0, "skipped": 0}

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def warm_symbol(symbol: str) -> None:
            async with semaphore:
                for data_type in self.data_types:
                    try:
                        await self._warm_symbol_data_type(symbol, data_type)
                        results["warmed"] += 1
                    except Exception:
                        results["failed"] += 1

        await asyncio.gather(*[warm_symbol(s) for s in self.symbols])
        return results

    async def _warm_symbol_data_type(self, symbol: str, data_type: str) -> None:
        """Warm a specific data type for a symbol."""
        # Determine the fetch function based on data type
        if data_type == "quote_history":
            # Warm quote history with default parameters (1D interval, 30 days)
            async def fetch_quote():
                stock = self.vnbroker_client.stock(symbol)
                df = stock.quote.history(interval="1D", count_back=30)
                return df.to_dict(orient="records") if hasattr(df, "to_dict") else df

            await self.cache_layer.get_or_fetch(
                data_type="quote_history",
                endpoint="history",
                params={"symbol": symbol, "interval": "1D", "count_back": 30},
                fetch_func=fetch_quote,
                ttl_override=3600,  # 1 hour TTL for warmed data
            )

        elif data_type == "company_overview":
            # Warm company overview
            async def fetch_company():
                company = self.vnbroker_client.stock(symbol).company
                result = {}
                result["overview"] = company.overview()
                result["profile"] = company.profile()
                return result

            await self.cache_layer.get_or_fetch(
                data_type="company_overview",
                endpoint="overview",
                params={"symbol": symbol},
                fetch_func=fetch_company,
                ttl_override=86400,  # 24 hour TTL for company data
            )

        elif data_type == "finance_report":
            # Warm financial reports
            async def fetch_finance():
                finance = self.vnbroker_client.stock(symbol).finance
                result = {}
                result["income_statement"] = finance.income_statement(period="quarterly", limit=4)
                result["balance_sheet"] = finance.balance_sheet(period="quarterly", limit=4)
                result["cash_flow"] = finance.cash_flow(period="quarterly", limit=4)
                result["ratios"] = finance.ratio(period="quarterly", limit=4)
                return result

            await self.cache_layer.get_or_fetch(
                data_type="finance_report",
                endpoint="report",
                params={"symbol": symbol, "report_type": "all", "period": "quarterly"},
                fetch_func=fetch_finance,
                ttl_override=86400,  # 24 hour TTL for finance data
            )

        elif data_type == "news_latest":
            # Warm latest news
            async def fetch_news():
                news_client = self.vnbroker_client.news()
                if hasattr(news_client, "symbol"):
                    news_client = news_client.symbol(symbol)
                return news_client.latest(limit=20)

            await self.cache_layer.get_or_fetch(
                data_type="news_latest",
                endpoint="latest",
                params={"symbol": symbol, "limit": 20},
                fetch_func=fetch_news,
                ttl_override=1800,  # 30 min TTL for news
            )

        else:
            raise ValueError(f"Unknown data type for warming: {data_type}")


def create_cache_backend(
    redis_url: str | None = None,
    use_memory: bool = False,
    **kwargs,
) -> CacheBackend:
    """Factory function to create cache backend."""
    if use_memory or not redis_url:
        return InMemoryCacheBackend(**kwargs)
    return RedisCacheBackend(redis_url=redis_url, **kwargs)
