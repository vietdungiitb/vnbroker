"""
Centralized configuration management for Vninvest SDK.

Uses pydantic-settings for environment variable parsing with validation.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RedisSettings(BaseSettings):
    """Redis connection settings."""

    model_config = SettingsConfigDict(env_prefix="VNINVEST_REDIS_")

    url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    max_connections: int = Field(default=50, description="Max Redis connections")
    socket_timeout: float = Field(default=5.0, description="Socket timeout in seconds")
    socket_connect_timeout: float = Field(default=5.0, description="Socket connect timeout")
    retry_on_timeout: bool = Field(default=True, description="Retry on timeout")
    health_check_interval: int = Field(default=30, description="Health check interval")


class AuthSettings(BaseSettings):
    """Authentication settings."""

    model_config = SettingsConfigDict(env_prefix="VNINVEST_AUTH_")

    mode: str = Field(default="local", description="Auth mode: local or remote")
    secret_key: str | None = Field(default=None, description="HMAC secret for local mode")
    service_url: str | None = Field(default=None, description="Auth service URL for remote mode")
    service_timeout: float = Field(default=5.0, description="Auth service timeout")
    cache_ttl_seconds: int = Field(default=300, description="Tenant context cache TTL")


class QuotaSettings(BaseSettings):
    """Quota management settings."""

    model_config = SettingsConfigDict(env_prefix="VNINVEST_QUOTA_")

    redis_url: str | None = Field(default=None, description="Redis URL (uses main Redis if not set)")
    key_prefix: str = Field(default="vninvest:quota", description="Redis key prefix")
    fallback_to_memory: bool = Field(default=True, description="Fallback to in-memory if Redis unavailable")


class CacheSettings(BaseSettings):
    """Cache settings."""

    model_config = SettingsConfigDict(env_prefix="VNINVEST_CACHE_")

    redis_url: str | None = Field(default=None, description="Redis URL (uses main Redis if not set)")
    key_prefix: str = Field(default="vninvest:cache", description="Redis key prefix")
    default_ttl: int = Field(default=300, description="Default cache TTL in seconds")
    max_key_length: int = Field(default=200, description="Max cache key length")
    serializer: str = Field(default="json", description="Serializer: json, pickle, msgpack")
    enabled: bool = Field(default=True, description="Enable caching")


class MeteringSettings(BaseSettings):
    """Metering and billing settings."""

    model_config = SettingsConfigDict(env_prefix="VNINVEST_METERING_")

    redis_url: str | None = Field(default=None, description="Redis URL (uses main Redis if not set)")
    key_prefix: str = Field(default="vninvest:metering", description="Redis key prefix")
    retention_days: int = Field(default=90, description="Event retention in days")
    webhook_url: str | None = Field(default=None, description="Billing webhook URL")
    webhook_secret: str | None = Field(default=None, description="Webhook HMAC secret")
    batch_size: int = Field(default=100, description="Batch size for webhook emission")
    flush_interval_seconds: float = Field(default=30.0, description="Flush interval for webhook")


class StreamingSettings(BaseSettings):
    """Streaming settings."""

    model_config = SettingsConfigDict(env_prefix="VNINVEST_STREAM_")

    redis_url: str | None = Field(default=None, description="Redis URL (uses main Redis if not set)")
    max_messages_per_second: int = Field(default=1000, description="Max messages per second per tenant")
    deduplication_window_ms: int = Field(default=100, description="Deduplication window in ms")
    vci_ws_url: str | None = Field(default=None, description="VCI WebSocket URL")
    vci_api_key: str | None = Field(default=None, description="VCI API key for WebSocket auth")


class VnbrokerSettings(BaseSettings):
    """vnbroker integration settings."""

    model_config = SettingsConfigDict(env_prefix="VNINVEST_VNBROKER_")

    default_source: str = Field(default="AUTO", description="Default data source")
    timeout: float = Field(default=30.0, description="Request timeout")
    max_retries: int = Field(default=3, description="Max retries for failed requests")


class ObservabilitySettings(BaseSettings):
    """Observability (tracing, metrics, logging) settings."""

    model_config = SettingsConfigDict(env_prefix="VNINVEST_OBS_")

    # OpenTelemetry
    otel_enabled: bool = Field(default=True, description="Enable OpenTelemetry")
    otel_service_name: str = Field(default="vninvest-sdk", description="Service name for tracing")
    otel_exporter_otlp_endpoint: str | None = Field(default=None, description="OTLP exporter endpoint")
    otel_exporter_otlp_headers: str | None = Field(default=None, description="OTLP exporter headers")
    otel_traces_sampler: str = Field(default="parentbased_always_on", description="Trace sampler")
    otel_traces_sampler_arg: str | None = Field(default=None, description="Trace sampler arg")

    # Prometheus
    prometheus_enabled: bool = Field(default=True, description="Enable Prometheus metrics")
    prometheus_port: int = Field(default=9090, description="Prometheus metrics port")

    # Logging
    log_level: str = Field(default="INFO", description="Log level")
    log_format: str = Field(default="json", description="Log format: json or text")


class PATSettings(BaseSettings):
    """PAT (Personal Access Token) settings."""

    model_config = SettingsConfigDict(env_prefix="VNINVEST_PAT_")

    redis_url: str | None = Field(default=None, description="Redis URL (uses main Redis if not set)")
    key_prefix: str = Field(default="vninvest:pat", description="Redis key prefix")
    default_ttl_days: int = Field(default=90, description="Default PAT TTL in days")
    bcrypt_rounds: int = Field(default=12, description="Bcrypt rounds for token hashing")
    token_prefix: str = Field(default="vninvest_pat_", description="Token prefix")
    prefix_length: int = Field(default=22, description="Prefix length for index lookup")


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    environment: str = Field(default="development", description="Environment: development, staging, production")
    debug: bool = Field(default=False, description="Debug mode")

    # Component settings
    redis: RedisSettings = Field(default_factory=RedisSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    quota: QuotaSettings = Field(default_factory=QuotaSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    metering: MeteringSettings = Field(default_factory=MeteringSettings)
    streaming: StreamingSettings = Field(default_factory=StreamingSettings)
    vnbroker: VnbrokerSettings = Field(default_factory=VnbrokerSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    pat: PATSettings = Field(default_factory=PATSettings)

    # API
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    api_workers: int = Field(default=1, description="API workers")
    api_cors_origins: list[str] = Field(default=["*"], description="CORS allowed origins")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def reset_settings_cache() -> None:
    """Reset settings cache (useful for testing)."""
    get_settings.cache_clear()
