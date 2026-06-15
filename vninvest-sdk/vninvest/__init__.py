"""
vninvest-sdk: Enterprise wrapper for vnbroker with SaaS-grade features.

This package provides:
- Tenant isolation and PAT (Personal Access Token) management
- Quota enforcement per pricing plan
- Usage metering and billing integration
- Redis-backed caching layer
- Real-time WebSocket streaming
- OpenTelemetry observability
- Admin APIs for platform operations
"""

from .admin import AdminClient, LocalAdminClient, SystemHealthReport, TenantUsageReport
from .auth import (
    APIKeyAuth,
    TenantContext,
    resolve_tenant,
    get_tenant_context,
    require_quote_read,
    require_company_read,
    require_finance_read,
    require_news_read,
    require_admin_tenant,
)
from .cache import CacheConfig, CacheLayer, CacheWarmer
from .client import VninvestClient
from .config import Settings, get_settings, reset_settings_cache
from .exceptions import (
    AuthenticationError,
    AuthorizationError,
    CacheError,
    ConfigurationError,
    ProviderError,
    QuotaExceededError,
    RateLimitError,
    ScopeDeniedError,
    StreamingError,
    TenantNotFoundError,
    TenantSuspendedError,
    VninvestError,
)
from .metering import BillingEventEmitter, MeteringEvent, UsageTracker, create_metering_backend
from .cache import CacheConfig, CacheLayer, CacheWarmer, create_cache_backend
from .models import (
    CompanyRequest,
    FinanceRequest,
    HealthCheckResponse,
    NewsRequest,
    PATScope,
    PersonalAccessToken,
    QuoteRequest,
    QuoteResponse,
    StreamingSubscription,
    TenantPlan,
    TenantTier,
    UsageMetrics,
)
from .observability import (
    get_meter,
    get_tracer,
    record_api_call,
    record_cache_hit,
    record_cache_miss,
    record_quota_exceeded,
    set_active_streams,
    set_active_tenants,
    setup_observability,
    shutdown_observability,
    trace_span,
    traced,
)
from .pat import PATStorage
from .quota import PlanLimits, QuotaContextManager, QuotaExceededError, QuotaManager
from .streaming import PriceStream, StreamChannel, StreamConfig, StreamManager

__version__ = "0.2.0"

__all__ = [
    # Main client
    "VninvestClient",
    # Auth & Tenant
    "APIKeyAuth",
    "TenantContext",
    "resolve_tenant",
    "get_tenant_context",
    "require_quote_read",
    "require_company_read",
    "require_finance_read",
    "require_news_read",
    "require_admin_tenant",
    # Quota
    "QuotaManager",
    "PlanLimits",
    "QuotaExceededError",
    "QuotaContextManager",
    # Metering
    "UsageTracker",
    "MeteringEvent",
    "BillingEventEmitter",
    "create_metering_backend",
    # Cache
    "create_cache_backend",
    # Cache
    "CacheLayer",
    "CacheConfig",
    "CacheWarmer",
    # Streaming
    "PriceStream",
    "StreamManager",
    "StreamConfig",
    "StreamChannel",
    # Admin
    "AdminClient",
    "TenantUsageReport",
    "SystemHealthReport",
    "LocalAdminClient",
    # PAT
    "PATStorage",
    # Config
    "Settings",
    "get_settings",
    "reset_settings_cache",
    # Observability
    "setup_observability",
    "get_tracer",
    "get_meter",
    "trace_span",
    "record_api_call",
    "record_cache_hit",
    "record_cache_miss",
    "record_quota_exceeded",
    "set_active_streams",
    "set_active_tenants",
    "shutdown_observability",
    "traced",
    # Exceptions
    "VninvestError",
    "AuthenticationError",
    "AuthorizationError",
    "QuotaExceededError",
    "RateLimitError",
    "ProviderError",
    "CacheError",
    "StreamingError",
    "ConfigurationError",
    "ScopeDeniedError",
    "TenantNotFoundError",
    "TenantSuspendedError",
    # Models
    "TenantPlan",
    "TenantTier",
    "PATScope",
    "PersonalAccessToken",
    "QuoteRequest",
    "QuoteResponse",
    "CompanyRequest",
    "FinanceRequest",
    "NewsRequest",
    "StreamingSubscription",
    "UsageMetrics",
    "HealthCheckResponse",
]
