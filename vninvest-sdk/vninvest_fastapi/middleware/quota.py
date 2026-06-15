"""
FastAPI quota enforcement middleware for Vninvest SDK.

Enforces daily API call limits and concurrent request limits per tenant.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from vninvest import QuotaManager, TenantContext, get_settings
from vninvest.config import Settings
from vninvest.exceptions import QuotaExceededError, RateLimitError
from vninvest.observability import record_quota_exceeded, trace_span


class QuotaMiddleware(BaseHTTPMiddleware):
    """Middleware for enforcing quota limits."""

    def __init__(
        self,
        app,
        quota_manager: QuotaManager | None = None,
        settings: Settings | None = None,
        exempt_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self._quota_manager = quota_manager
        self._settings = settings or get_settings()
        self._exempt_paths = exempt_paths or [
            "/health",
            "/healthz",
            "/ready",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]

    @property
    def quota_manager(self) -> QuotaManager:
        if self._quota_manager is None:
            self._quota_manager = QuotaManager(
                redis_url=self._settings.quota.redis_url or self._settings.redis.url,
                key_prefix=self._settings.quota.key_prefix,
                fallback_to_memory=self._settings.quota.fallback_to_memory,
            )
        return self._quota_manager

    async def dispatch(self, request: Request, call_next):
        """Process request through quota enforcement."""
        # Skip quota for exempt paths
        if request.url.path in self._exempt_paths:
            return await call_next(request)

        # Skip quota for non-API paths (static files, etc.)
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        # Get tenant context from request state (set by AuthMiddleware)
        if not hasattr(request.state, "tenant_context"):
            # If no tenant context, skip quota (auth middleware should have run first)
            return await call_next(request)

        context: TenantContext = request.state.tenant_context

        # Check daily quota
        try:
            with trace_span("quota.check_daily", {"tenant_id": str(context.tenant_id)}):
                await self.quota_manager.check_daily_quota(context, increment=1)
        except QuotaExceededError as e:
            record_quota_exceeded("daily_calls", context.tier.value)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "QUOTA_EXCEEDED",
                    "message": str(e),
                    "limit_type": e.details.get("limit_type"),
                    "limit_value": e.details.get("limit_value"),
                    "current_value": e.details.get("current_value"),
                    "reset_at": e.details.get("reset_at"),
                },
                headers={"Retry-After": "86400"},  # 24 hours
            )

        # Acquire concurrent slot
        try:
            with trace_span("quota.acquire_concurrent", {"tenant_id": str(context.tenant_id)}):
                await self.quota_manager.acquire_concurrent_slot(context)
        except RateLimitError as e:
            # Release daily quota since we couldn't get concurrent slot
            await self.quota_manager.release_daily_quota(context, decrement=1)
            record_quota_exceeded("concurrent_requests", context.tier.value)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": str(e),
                    "retry_after_seconds": e.details.get("retry_after_seconds", 5),
                },
                headers={"Retry-After": str(e.details.get("retry_after_seconds", 5))},
            )

        # Process request
        response: Response = await call_next(request)

        # Release concurrent slot after request completes
        try:
            await self.quota_manager.release_concurrent_slot(context)
        except Exception:
            # Log but don't fail the response
            pass

        # Add quota headers to response
        usage = await self.quota_manager.get_usage(context)
        response.headers["X-Quota-Limit-Daily"] = str(context.daily_limit)
        response.headers["X-Quota-Remaining-Daily"] = str(max(0, context.daily_limit - usage["daily_calls"]))
        response.headers["X-Quota-Limit-Concurrent"] = str(context.concurrent_limit)
        response.headers["X-Quota-Remaining-Concurrent"] = str(max(0, context.concurrent_limit - usage["concurrent_requests"]))

        return response


# Dependency for manual quota checking in route handlers
async def check_quota(
    context: TenantContext = Depends(lambda request: request.state.tenant_context),
    quota_manager: QuotaManager = Depends(lambda: QuotaManager()),
) -> None:
    """Dependency to manually check quota in a route handler."""
    await quota_manager.check_daily_quota(context, increment=1)
    await quota_manager.acquire_concurrent_slot(context)
