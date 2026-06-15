"""
FastAPI application factory for Vninvest SDK.

Creates and configures the FastAPI application with all middleware, routes, and dependencies.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from vninvest import (
    CacheLayer,
    LocalAdminClient,
    PATStorage,
    QuotaManager,
    StreamManager,
    UsageTracker,
    VninvestClient,
    get_settings,
    setup_observability,
    shutdown_observability,
)
from vninvest.config import Settings

from .middleware import (
    AuthMiddleware,
    MeteringMiddleware,
    QuotaMiddleware,
)
from .routes import (
    admin_router,
    company_router,
    finance_router,
    news_router,
    quote_router,
    stream_router,
)

# Global instances (initialized in lifespan)
_vninvest_client: VninvestClient | None = None
_admin_client: LocalAdminClient | None = None
_quota_manager: QuotaManager | None = None
_usage_tracker: UsageTracker | None = None
_cache_layer: CacheLayer | None = None
_stream_manager: StreamManager | None = None
_pat_storage: PATStorage | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _vninvest_client, _admin_client, _quota_manager, _usage_tracker
    global _cache_layer, _stream_manager, _pat_storage

    settings = get_settings()

    # Setup observability
    if settings.observability.otel_enabled or settings.observability.prometheus_enabled:
        setup_observability(settings.observability)

    # Initialize shared components
    _quota_manager = QuotaManager(
        redis_url=settings.quota.redis_url or settings.redis.url,
        key_prefix=settings.quota.key_prefix,
        fallback_to_memory=settings.quota.fallback_to_memory,
    )

    from vninvest import create_metering_backend
    metering_backend = create_metering_backend(
        redis_url=settings.metering.redis_url or settings.redis.url,
        use_memory=(settings.metering.redis_url or settings.redis.url) is None,
    )
    _usage_tracker = UsageTracker(backend=metering_backend)

    from vninvest import CacheConfig, create_cache_backend
    cache_backend = create_cache_backend(
        redis_url=settings.cache.redis_url or settings.redis.url,
        use_memory=(settings.cache.redis_url or settings.redis.url) is None,
        key_prefix=settings.cache.key_prefix,
        default_ttl=settings.cache.default_ttl,
        serializer=settings.cache.serializer,
    )
    _cache_layer = CacheLayer(
        backend=cache_backend,
        config=CacheConfig(
            enabled=settings.cache.enabled,
            default_ttl=settings.cache.default_ttl,
            max_key_length=settings.cache.max_key_length,
        ),
    )

    _stream_manager = StreamManager(
        redis_url=settings.streaming.redis_url or settings.redis.url,
        max_messages_per_second=settings.streaming.max_messages_per_second,
        deduplication_window_ms=settings.streaming.deduplication_window_ms,
    )

    _pat_storage = PATStorage(
        redis_url=settings.pat.redis_url or settings.redis.url,
        key_prefix=settings.pat.key_prefix,
        default_ttl_days=settings.pat.default_ttl_days,
    )

    # Initialize admin client (local for self-hosted)
    _admin_client = LocalAdminClient(
        redis_url=settings.redis.url,
        quota_manager=_quota_manager,
        metering_backend=metering_backend,
        cache_backend=cache_backend,
        stream_manager=_stream_manager,
        pat_storage=_pat_storage,
    )

    # Store in app state for route access
    app.state.vninvest_client = None  # Will be set per-request via auth
    app.state.admin_client = _admin_client
    app.state.local_admin_client = _admin_client
    app.state.quota_manager = _quota_manager
    app.state.usage_tracker = _usage_tracker
    app.state.cache_layer = _cache_layer
    app.state.stream_manager = _stream_manager
    app.state.pat_storage = _pat_storage

    yield

    # Cleanup
    if _vninvest_client:
        await _vninvest_client.close()
    if _admin_client:
        await _admin_client.close()
    if _quota_manager:
        await _quota_manager.close()
    if _usage_tracker:
        await _usage_tracker.close()
    if _cache_layer:
        await _cache_layer.backend.close()
    if _stream_manager:
        await _stream_manager.close()
    if _pat_storage:
        await _pat_storage.close()

    shutdown_observability()


def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        settings: Optional settings override (uses get_settings() if not provided)

    Returns:
        Configured FastAPI application
    """
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title="Vninvest SaaS API",
        description="Enterprise API for Vietnam stock market data with multi-tenancy, quota management, and real-time streaming",
        version="0.2.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middleware (order matters - auth first, then quota, then metering)
    app.add_middleware(MeteringMiddleware)
    app.add_middleware(QuotaMiddleware)
    app.add_middleware(AuthMiddleware)

    # Include routers
    app.include_router(quote_router, prefix="/api/v1")
    app.include_router(company_router, prefix="/api/v1")
    app.include_router(finance_router, prefix="/api/v1")
    app.include_router(news_router, prefix="/api/v1")
    app.include_router(stream_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")

    # Health check endpoints
    @app.get("/health", tags=["health"])
    async def health_check():
        return {"status": "healthy", "service": "vninvest-api", "version": "0.2.0"}

    @app.get("/healthz", tags=["health"])
    async def healthz():
        return {"status": "ok"}

    @app.get("/ready", tags=["health"])
    async def readiness():
        # Check Redis connectivity
        try:
            if _quota_manager:
                await _quota_manager._get_redis()
            return {"status": "ready"}
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"status": "not ready", "reason": "Redis unavailable"},
            )

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "detail": str(exc) if not settings.is_production else "Internal server error",
            },
        )

    return app


# For running with uvicorn directly
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "vninvest_fastapi.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        reload=settings.is_development,
    )
