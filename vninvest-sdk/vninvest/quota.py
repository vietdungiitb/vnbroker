"""
Quota management and rate limiting for Vninvest SDK.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

import redis.asyncio as redis

from .exceptions import QuotaExceededError, RateLimitError, ScopeDeniedError
from .models import PATScope, TenantContext, TenantPlan


@dataclass
class PlanLimits:
    """Runtime plan limits with current usage."""

    daily_calls: int
    concurrent_requests: int
    symbols_per_request: int
    cache_ttl_seconds: int
    webhook_enabled: bool
    streaming_enabled: bool
    priority_support: bool
    dedicated_provider_pool: bool

    # Current usage (updated by quota manager)
    current_daily_calls: int = 0
    current_concurrent: int = 0

    @classmethod
    def from_plan(cls, plan: TenantPlan) -> PlanLimits:
        return cls(
            daily_calls=plan.daily_api_calls,
            concurrent_requests=plan.concurrent_requests,
            symbols_per_request=plan.symbols_per_request,
            cache_ttl_seconds=plan.cache_ttl_seconds,
            webhook_enabled=plan.webhook_enabled,
            streaming_enabled=plan.streaming_enabled,
            priority_support=plan.priority_support,
            dedicated_provider_pool=plan.dedicated_provider_pool,
        )


class QuotaManager:
    """
    Manages quota enforcement for tenants.

    Uses Redis for distributed state (daily counters, concurrent tracking).
    Falls back to in-memory if Redis unavailable.
    """

    def __init__(
        self,
        redis_url: str | None = None,
        redis_client: redis.Redis | None = None,
        key_prefix: str = "vninvest:quota",
        fallback_to_memory: bool = True,
    ):
        self.redis_url = redis_url or "redis://localhost:6379/0"
        self._redis_client = redis_client
        self._owns_client = redis_client is None
        self.key_prefix = key_prefix
        self.fallback_to_memory = fallback_to_memory

        # In-memory fallback
        self._memory_daily: dict[str, int] = defaultdict(int)
        self._memory_concurrent: dict[str, int] = defaultdict(int)
        self._memory_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        self._redis: redis.Redis | None = None

    async def _get_redis(self) -> redis.Redis | None:
        if self._redis is None and self._redis_client is None:
            try:
                self._redis = redis.from_url(self.redis_url, decode_responses=True)
                await self._redis.ping()
            except Exception:
                self._redis = None
        return self._redis or self._redis_client

    async def close(self) -> None:
        if self._owns_client and self._redis:
            await self._redis.aclose()
            self._redis = None

    def _daily_key(self, tenant_id: UUID, date: str | None = None) -> str:
        if date is None:
            date = time.strftime("%Y-%m-%d")
        return f"{self.key_prefix}:daily:{tenant_id}:{date}"

    def _concurrent_key(self, tenant_id: UUID) -> str:
        return f"{self.key_prefix}:concurrent:{tenant_id}"

    async def check_daily_quota(self, context: TenantContext, increment: int = 1) -> bool:
        """
        Check if tenant has remaining daily quota.

        Args:
            context: Tenant context
            increment: Number of calls to reserve (default 1)

        Returns:
            True if quota available

        Raises:
            QuotaExceededError: If quota would be exceeded
        """
        redis_client = await self._get_redis()
        key = self._daily_key(context.tenant_id)
        limit = context.daily_limit

        if redis_client:
            try:
                # Use Lua script for atomic check-and-increment
                lua_script = """
                local current = tonumber(redis.call('GET', KEYS[1]) or '0')
                local limit = tonumber(ARGV[1])
                local increment = tonumber(ARGV[2])
                if current + increment > limit then
                    return {0, current}
                end
                local new_val = redis.call('INCRBY', KEYS[1], increment)
                redis.call('EXPIRE', KEYS[1], 86400)
                return {1, new_val}
                """
                result = await redis_client.eval(lua_script, 1, key, limit, increment)
                if result[0] == 0:
                    raise QuotaExceededError(
                        f"Daily API call quota exceeded ({result[1]}/{limit})",
                        limit_type="daily_calls",
                        limit_value=limit,
                        current_value=result[1],
                        reset_at=time.strftime("%Y-%m-%d 23:59:59"),
                    )
                return True
            except QuotaExceededError:
                raise
            except Exception:
                if not self.fallback_to_memory:
                    raise

        # Fallback to memory
        async with self._memory_locks[key]:
            current = self._memory_daily[key]
            if current + increment > limit:
                raise QuotaExceededError(
                    f"Daily API call quota exceeded ({current}/{limit})",
                    limit_type="daily_calls",
                    limit_value=limit,
                    current_value=current,
                    reset_at=time.strftime("%Y-%m-%d 23:59:59"),
                )
            self._memory_daily[key] = current + increment
            return True

    async def release_daily_quota(self, context: TenantContext, decrement: int = 1) -> None:
        """Release reserved daily quota (e.g., on request failure)."""
        redis_client = await self._get_redis()
        key = self._daily_key(context.tenant_id)

        if redis_client:
            try:
                await redis_client.decrby(key, decrement)
                return
            except Exception:
                if not self.fallback_to_memory:
                    raise

        async with self._memory_locks[key]:
            self._memory_daily[key] = max(0, self._memory_daily[key] - decrement)

    async def acquire_concurrent_slot(self, context: TenantContext) -> bool:
        """
        Acquire a concurrent request slot.

        Args:
            context: Tenant context

        Returns:
            True if slot acquired

        Raises:
            RateLimitError: If concurrent limit reached
        """
        redis_client = await self._get_redis()
        key = self._concurrent_key(context.tenant_id)
        limit = context.concurrent_limit

        if redis_client:
            try:
                lua_script = """
                local current = tonumber(redis.call('GET', KEYS[1]) or '0')
                local limit = tonumber(ARGV[1])
                if current >= limit then
                    return {0, current}
                end
                local new_val = redis.call('INCR', KEYS[1])
                redis.call('EXPIRE', KEYS[1], 300)
                return {1, new_val}
                """
                result = await redis_client.eval(lua_script, 1, key, limit)
                if result[0] == 0:
                    raise RateLimitError(
                        f"Concurrent request limit reached ({result[1]}/{limit})",
                        retry_after_seconds=5,
                    )
                return True
            except RateLimitError:
                raise
            except Exception:
                if not self.fallback_to_memory:
                    raise

        # Fallback to memory
        async with self._memory_locks[key]:
            current = self._memory_concurrent[key]
            if current >= limit:
                raise RateLimitError(
                    f"Concurrent request limit reached ({current}/{limit})",
                    retry_after_seconds=5,
                )
            self._memory_concurrent[key] = current + 1
            return True

    async def release_concurrent_slot(self, context: TenantContext) -> None:
        """Release a concurrent request slot."""
        redis_client = await self._get_redis()
        key = self._concurrent_key(context.tenant_id)

        if redis_client:
            try:
                await redis_client.decr(key)
                return
            except Exception:
                if not self.fallback_to_memory:
                    raise

        async with self._memory_locks[key]:
            self._memory_concurrent[key] = max(0, self._memory_concurrent[key] - 1)

    async def get_usage(self, context: TenantContext) -> dict[str, int]:
        """Get current usage for a tenant."""
        redis_client = await self._get_redis()
        daily_key = self._daily_key(context.tenant_id)
        concurrent_key = self._concurrent_key(context.tenant_id)

        if redis_client:
            try:
                daily = int(await redis_client.get(daily_key) or 0)
                concurrent = int(await redis_client.get(concurrent_key) or 0)
                return {"daily_calls": daily, "concurrent_requests": concurrent}
            except Exception:
                pass

        return {
            "daily_calls": self._memory_daily.get(daily_key, 0),
            "concurrent_requests": self._memory_concurrent.get(concurrent_key, 0),
        }

    async def get_quota_status(self, context: TenantContext) -> dict:
        """Get full quota status for a tenant."""
        usage = await self.get_usage(context)
        return {
            "tenant_id": str(context.tenant_id),
            "tier": context.tier.value,
            "limits": {
                "daily_calls": context.daily_limit,
                "concurrent_requests": context.concurrent_limit,
                "symbols_per_request": context.plan.symbols_per_request,
            },
            "usage": usage,
            "remaining": {
                "daily_calls": max(0, context.daily_limit - usage["daily_calls"]),
                "concurrent_requests": max(0, context.concurrent_limit - usage["concurrent_requests"]),
            },
            "utilization_pct": {
                "daily_calls": round(usage["daily_calls"] / context.daily_limit * 100, 2) if context.daily_limit > 0 else 0,
                "concurrent_requests": round(usage["concurrent_requests"] / context.concurrent_limit * 100, 2) if context.concurrent_limit > 0 else 0,
            },
        }

    def reset_tenant_quota(self, tenant_id: UUID) -> None:
        """Reset quota for a tenant (admin operation)."""
        daily_key = self._daily_key(tenant_id)
        concurrent_key = self._concurrent_key(tenant_id)

        self._memory_daily.pop(daily_key, None)
        self._memory_concurrent.pop(concurrent_key, None)


class QuotaContextManager:
    """
    Async context manager for automatic quota acquisition/release.

    Usage:
        async with QuotaContextManager(quota_manager, context) as q:
            # Make API calls
            pass
        # Automatically releases concurrent slot
    """

    def __init__(
        self,
        quota_manager: QuotaManager,
        context: TenantContext,
        reserve_daily: int = 1,
        required_scope: PATScope | None = None,
    ):
        self.quota_manager = quota_manager
        self.context = context
        self.reserve_daily = reserve_daily
        self.required_scope = required_scope
        self._acquired = False

    async def __aenter__(self) -> QuotaContextManager:
        # Check scope if required
        if self.required_scope and not self.context.has_scope(self.required_scope):
            raise ScopeDeniedError(self.required_scope.value)

        await self.quota_manager.check_daily_quota(self.context, self.reserve_daily)
        await self.quota_manager.acquire_concurrent_slot(self.context)
        self._acquired = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._acquired:
            await self.quota_manager.release_concurrent_slot(self.context)
            # Note: We don't release daily quota on success - it's consumed
            # On failure, caller should call release_daily_quota manually if needed
            self._acquired = False
