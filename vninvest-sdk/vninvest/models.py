"""
Pydantic models for Vninvest SDK requests, responses, and domain objects.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class TenantTier(str, Enum):
    """Tenant pricing tiers."""

    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class PATScope(str, Enum):
    """Personal Access Token scopes for fine-grained authorization."""

    QUOTE_READ = "quote:read"
    COMPANY_READ = "company:read"
    FINANCE_READ = "finance:read"
    NEWS_READ = "news:read"
    STREAM_PRICE = "stream:price"
    STREAM_DEPTH = "stream:depth"
    STREAM_TRADE = "stream:trade"
    ADMIN_TENANT = "admin:tenant"


class PersonalAccessToken(BaseModel):
    """Personal Access Token model for user-created API credentials."""

    pat_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    user_id: UUID
    name: str
    token_hash: str
    prefix: str
    scopes: list[PATScope]
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def is_active(self) -> bool:
        """Check if PAT is active (not revoked and not expired)."""
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and self.expires_at < datetime.utcnow():
            return False
        return True


class TenantPlan(BaseModel):
    """Tenant subscription plan configuration."""

    tier: TenantTier = TenantTier.FREE
    daily_api_calls: int = 1000
    concurrent_requests: int = 5
    symbols_per_request: int = 10
    cache_ttl_seconds: int = 60
    webhook_enabled: bool = False
    streaming_enabled: bool = False
    priority_support: bool = False
    dedicated_provider_pool: bool = False
    custom_rate_limits: dict[str, int] = Field(default_factory=dict)

    # Symbol authorization
    allowed_symbols: list[str] = Field(default_factory=list, description="Whitelist of allowed symbols (empty = all allowed)")
    blocked_symbols: list[str] = Field(default_factory=list, description="Blacklist of blocked symbols")

    @classmethod
    def from_tier(cls, tier: TenantTier) -> TenantPlan:
        """Get default plan limits for a tier."""
        plans = {
            TenantTier.FREE: cls(
                tier=TenantTier.FREE,
                daily_api_calls=1_000,
                concurrent_requests=5,
                symbols_per_request=10,
                cache_ttl_seconds=300,
                webhook_enabled=False,
                streaming_enabled=False,
            ),
            TenantTier.PRO: cls(
                tier=TenantTier.PRO,
                daily_api_calls=100_000,
                concurrent_requests=50,
                symbols_per_request=100,
                cache_ttl_seconds=60,
                webhook_enabled=True,
                streaming_enabled=True,
                priority_support=True,
            ),
            TenantTier.ENTERPRISE: cls(
                tier=TenantTier.ENTERPRISE,
                daily_api_calls=1_000_000,
                concurrent_requests=200,
                symbols_per_request=500,
                cache_ttl_seconds=30,
                webhook_enabled=True,
                streaming_enabled=True,
                priority_support=True,
                dedicated_provider_pool=True,
            ),
        }
        return plans[tier]


class TenantContext(BaseModel):
    """Resolved tenant context for request processing."""

    tenant_id: UUID
    api_key_hash: str
    plan: TenantPlan
    tier: TenantTier
    status: str = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)
    resolved_at: datetime = Field(default_factory=datetime.utcnow)
    pat_id: UUID | None = None
    user_id: UUID | None = None
    effective_scopes: list[PATScope] = Field(default_factory=list)

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def daily_limit(self) -> int:
        return self.plan.daily_api_calls

    @property
    def concurrent_limit(self) -> int:
        return self.plan.concurrent_requests

    def has_scope(self, scope: PATScope) -> bool:
        """Check if context has the required scope."""
        return scope in self.effective_scopes

    def require_scope(self, scope: PATScope) -> None:
        """Raise ScopeDeniedError if scope not present."""
        if not self.has_scope(scope):
            from .exceptions import ScopeDeniedError
            raise ScopeDeniedError(scope.value)

    def is_symbol_allowed(self, symbol: str) -> bool:
        """Check if a symbol is allowed for this tenant."""
        symbol = symbol.upper().strip()

        # Check blacklist first
        if symbol in [s.upper() for s in self.plan.blocked_symbols]:
            return False

        # Check whitelist (if configured)
        allowed = [s.upper() for s in self.plan.allowed_symbols]
        if allowed and symbol not in allowed:
            return False

        return True

    def require_symbol_allowed(self, symbol: str) -> None:
        """Raise SymbolNotAllowedError if symbol not allowed."""
        if not self.is_symbol_allowed(symbol):
            from .exceptions import SymbolNotAllowedError
            raise SymbolNotAllowedError(symbol=symbol)

    def filter_allowed_symbols(self, symbols: list[str]) -> list[str]:
        """Filter a list of symbols to only allowed ones."""
        return [s for s in symbols if self.is_symbol_allowed(s)]


# Request/Response Models


class QuoteRequest(BaseModel):
    """Request model for quote data."""

    symbols: list[str] = Field(..., min_length=1, description="List of stock symbols")
    interval: str = Field(default="1D", description="Time interval (1m, 5m, 15m, 30m, 1H, 1D, 1W, 1M)")
    start_date: str | None = Field(default=None, description="Start date (YYYY-MM-DD)")
    end_date: str | None = Field(default=None, description="End date (YYYY-MM-DD)")
    count_back: int | None = Field(default=None, ge=1, description="Number of bars to look back")
    length: str | int | None = Field(default=None, description="Flexible lookback (e.g., '3M', '100b')")
    source: str = Field(default="AUTO", description="Data source (AUTO, VCI, KBS, MSN, TCBS, DNSE)")
    adjust_price: bool = Field(default=True, description="Adjust for splits/dividends")
    to_df: bool = Field(default=True, description="Return as DataFrame (True) or JSON (False)")

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, v: list[str]) -> list[str]:
        return [s.upper().strip() for s in v if s.strip()]

    @field_validator("interval")
    @classmethod
    def validate_interval(cls, v: str) -> str:
        valid = {"1m", "5m", "15m", "30m", "1H", "1D", "1W", "1M"}
        if v not in valid:
            raise ValueError(f"Invalid interval. Must be one of: {valid}")
        return v


class QuoteResponse(BaseModel):
    """Response model for quote data."""

    symbol: str
    data: Any  # DataFrame or JSON-serializable
    source_used: str
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    cache_hit: bool = False
    latency_ms: int = 0
    row_count: int = 0
    price_unit: str = "VND"


class CompanyRequest(BaseModel):
    """Request model for company data."""

    symbol: str
    source: str = Field(default="AUTO")
    include_overview: bool = True
    include_profile: bool = True
    include_shareholders: bool = False
    include_insiders: bool = False
    include_subsidiaries: bool = False
    include_officers: bool = False
    include_events: bool = False


class FinanceRequest(BaseModel):
    """Request model for financial data."""

    symbol: str
    source: str = Field(default="AUTO")
    report_type: str = Field(default="all", description="income_statement, balance_sheet, cash_flow, ratio, or all")
    period: str = Field(default="quarterly", description="quarterly or yearly")
    language: str = Field(default="vi", description="vi or en")
    limit: int | None = Field(default=None, ge=1)


class NewsRequest(BaseModel):
    """Request model for news data."""

    symbol: str | None = None
    query: str | None = None
    sources: list[str] | None = None
    from_time: str | None = None
    to_time: str | None = None
    limit: int = Field(default=20, ge=1, le=100)
    source: str = Field(default="AUTO")


class StreamingSubscription(BaseModel):
    """WebSocket streaming subscription request."""

    symbols: list[str] = Field(..., min_length=1)
    channels: list[str] = Field(default=["price"], description="price, depth, trade, news")
    tenant_id: UUID
    auth_token: str


class UsageMetrics(BaseModel):
    """Usage metrics for a tenant."""

    tenant_id: UUID
    period_start: datetime
    period_end: datetime
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_symbols_accessed: int = 0
    total_data_bytes: int = 0
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    by_endpoint: dict[str, int] = Field(default_factory=dict)
    by_provider: dict[str, int] = Field(default_factory=dict)
    by_symbol: dict[str, int] = Field(default_factory=dict)


class HealthCheckResponse(BaseModel):
    """System health check response."""

    status: str  # healthy, degraded, unhealthy
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = "0.1.0"
    components: dict[str, dict[str, Any]] = Field(default_factory=dict)
    uptime_seconds: float = 0.0


class MeteringEvent(BaseModel):
    """Single API call metering event."""

    event_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    endpoint: str
    provider: str
    symbols: list[str]
    request_count: int = 1
    data_bytes: int = 0
    latency_ms: int
    status_code: int
    error_message: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    cache_hit: bool = False
    correlation_id: str | None = None


class TenantUsageReport(BaseModel):
    """Tenant usage report for admin dashboard."""

    tenant_id: UUID
    tenant_name: str
    tier: TenantTier
    period_start: datetime
    period_end: datetime
    metrics: UsageMetrics
    quota_utilization_pct: float
    estimated_cost_usd: float = 0.0
    overage_charges_usd: float = 0.0


class SystemHealthReport(BaseModel):
    """System-wide health report."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_tenants: int
    active_tenants: int
    total_calls_24h: int
    avg_latency_ms: float
    error_rate_pct: float
    provider_health: dict[str, dict[str, Any]]
    cache_hit_rate_pct: float
    active_streams: int
    alerts: list[dict[str, Any]] = Field(default_factory=list)
