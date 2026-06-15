"""
FastAPI metering middleware for Vninvest SDK.

Records API call metrics for billing and analytics.
"""

from __future__ import annotations

import time

from fastapi import Depends, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from vninvest import TenantContext, UsageTracker, get_settings
from vninvest.config import Settings
from vninvest.observability import record_api_call, trace_span


class MeteringMiddleware(BaseHTTPMiddleware):
    """Middleware for recording API call metrics."""

    def __init__(
        self,
        app,
        usage_tracker: UsageTracker | None = None,
        settings: Settings | None = None,
        exempt_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self._usage_tracker = usage_tracker
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
    def usage_tracker(self) -> UsageTracker:
        if self._usage_tracker is None:
            from vninvest import create_metering_backend
            backend = create_metering_backend(
                redis_url=self._settings.metering.redis_url or self._settings.redis.url,
                use_memory=(self._settings.metering.redis_url or self._settings.redis.url) is None,
            )
            self._usage_tracker = UsageTracker(backend=backend)
        return self._usage_tracker

    async def dispatch(self, request: Request, call_next):
        """Process request and record metrics."""
        # Skip metering for exempt paths
        if request.url.path in self._exempt_paths:
            return await call_next(request)

        # Skip metering for non-API paths
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        # Get tenant context
        if not hasattr(request.state, "tenant_context"):
            return await call_next(request)

        context: TenantContext = request.state.tenant_context

        # Record start time
        start_time = time.time()

        # Extract endpoint info
        endpoint = self._get_endpoint_name(request)
        provider = getattr(request.state, "provider_used", "unknown")
        symbols = getattr(request.state, "symbols_accessed", [])
        cache_hit = getattr(request.state, "cache_hit", False)
        data_bytes = getattr(request.state, "response_bytes", 0)

        # Process request
        response: Response = await call_next(request)

        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)

        # Record metrics (fire-and-forget)
        try:
            with trace_span("metering.record_call", {"tenant_id": str(context.tenant_id), "endpoint": endpoint}):
                await self.usage_tracker.record_call(
                    context=context,
                    endpoint=endpoint,
                    provider=provider,
                    symbols=symbols,
                    latency_ms=latency_ms,
                    status_code=response.status_code,
                    data_bytes=data_bytes,
                    cache_hit=cache_hit,
                    correlation_id=request.headers.get("X-Correlation-ID"),
                )

                # Also record Prometheus metrics
                record_api_call(
                    endpoint=endpoint,
                    provider=provider,
                    status=response.status_code,
                    tenant_tier=context.tier.value,
                    latency_seconds=latency_ms / 1000.0,
                )
        except Exception:
            # Metering failures should not break the API
            pass

        return response

    def _get_endpoint_name(self, request: Request) -> str:
        """Extract a normalized endpoint name from the request."""
        path = request.url.path
        method = request.method

        # Normalize path parameters
        # e.g., /api/v1/quote/ACB -> /api/v1/quote/{symbol}
        normalized = path
        parts = path.split("/")
        for i, part in enumerate(parts):
            # Replace UUIDs and symbols with placeholders
            if len(part) == 36 and part.count("-") == 4:  # UUID
                parts[i] = "{id}"
            elif part.isupper() and len(part) <= 10 and part.isalpha():  # Stock symbol
                parts[i] = "{symbol}"
        normalized = "/".join(parts)

        return f"{method} {normalized}"


# Dependency for manual metering in route handlers
async def record_metering(
    context: TenantContext,
    endpoint: str,
    provider: str,
    symbols: list[str],
    latency_ms: int,
    status_code: int,
    data_bytes: int = 0,
    cache_hit: bool = False,
    correlation_id: str | None = None,
    usage_tracker: UsageTracker = Depends(lambda: UsageTracker()),
) -> None:
    """Dependency to manually record metering in a route handler."""
    await usage_tracker.record_call(
        context=context,
        endpoint=endpoint,
        provider=provider,
        symbols=symbols,
        latency_ms=latency_ms,
        status_code=status_code,
        data_bytes=data_bytes,
        cache_hit=cache_hit,
        correlation_id=correlation_id,
    )
