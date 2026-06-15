"""
OpenTelemetry observability integration for Vninvest SDK.

Provides tracing, metrics, and structured logging.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.semconv.resource import ResourceAttributes
from prometheus_client import Counter, Gauge, Histogram, start_http_server

from .config import ObservabilitySettings, get_settings

# Global state
_tracer_provider: TracerProvider | None = None
_meter_provider: MeterProvider | None = None
_prometheus_server_started: bool = False

# Custom metrics
api_calls_total = Counter(
    "vninvest_api_calls_total",
    "Total API calls",
    ["endpoint", "provider", "status", "tenant_tier"],
)
api_latency_seconds = Histogram(
    "vninvest_api_latency_seconds",
    "API call latency in seconds",
    ["endpoint", "provider"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)
cache_hits_total = Counter(
    "vninvest_cache_hits_total",
    "Total cache hits",
    ["data_type", "tenant_tier"],
)
cache_misses_total = Counter(
    "vninvest_cache_misses_total",
    "Total cache misses",
    ["data_type", "tenant_tier"],
)
quota_exceeded_total = Counter(
    "vninvest_quota_exceeded_total",
    "Total quota exceeded events",
    ["limit_type", "tenant_tier"],
)
active_streams = Gauge(
    "vninvest_active_streams",
    "Number of active streaming connections",
    ["tenant_id"],
)
active_tenants = Gauge(
    "vninvest_active_tenants",
    "Number of active tenants",
)


def setup_observability(settings: ObservabilitySettings | None = None) -> None:
    """
    Initialize OpenTelemetry tracing, metrics, and logging.

    Call this once at application startup.
    """
    global _tracer_provider, _meter_provider, _prometheus_server_started

    if settings is None:
        settings = get_settings().observability

    if not settings.otel_enabled and not settings.prometheus_enabled:
        return

    # Create resource
    resource = Resource.create({
        ResourceAttributes.SERVICE_NAME: settings.otel_service_name,
        ResourceAttributes.SERVICE_VERSION: "0.2.0",
        "environment": get_settings().environment,
    })

    # Setup tracing
    if settings.otel_enabled:
        _tracer_provider = TracerProvider(resource=resource)

        # Add OTLP exporter if configured
        if settings.otel_exporter_otlp_endpoint:
            otlp_exporter = OTLPSpanExporter(
                endpoint=settings.otel_exporter_otlp_endpoint,
                headers=settings.otel_exporter_otlp_headers,
            )
            _tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        else:
            # Default to console exporter for development
            _tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

        trace.set_tracer_provider(_tracer_provider)

        # Auto-instrument libraries
        HTTPXClientInstrumentor().instrument()
        RedisInstrumentor().instrument()
        RequestsInstrumentor().instrument()

    # Setup metrics
    if settings.prometheus_enabled:
        # Prometheus exporter
        prometheus_reader = PrometheusMetricReader()
        _meter_provider = MeterProvider(resource=resource, metric_readers=[prometheus_reader])

        # Also add OTLP metric exporter if configured
        if settings.otel_exporter_otlp_endpoint:
            otlp_metric_exporter = OTLPMetricExporter(
                endpoint=settings.otel_exporter_otlp_endpoint,
                headers=settings.otel_exporter_otlp_headers,
            )
            otlp_reader = PeriodicExportingMetricExporter(otlp_metric_exporter)
            _meter_provider = MeterProvider(resource=resource, metric_readers=[prometheus_reader, otlp_reader])

        metrics.set_meter_provider(_meter_provider)

        # Start Prometheus HTTP server
        if not _prometheus_server_started:
            try:
                start_http_server(settings.prometheus_port)
                _prometheus_server_started = True
            except OSError:
                # Port might be in use, ignore
                pass

    # Setup structured logging
    _setup_logging(settings)


def _setup_logging(settings: ObservabilitySettings) -> None:
    """Configure structured JSON logging."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    if settings.log_format == "json":
        from pythonjsonlogger import jsonlogger

        handler = logging.StreamHandler(sys.stdout)
        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s",
            timestamp=True,
        )
        handler.setFormatter(formatter)

        root_logger = logging.getLogger()
        root_logger.handlers = [handler]
        root_logger.setLevel(log_level)
    else:
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            stream=sys.stdout,
        )

    # Reduce noise from third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("redis").setLevel(logging.WARNING)
    logging.getLogger("opentelemetry").setLevel(logging.WARNING)


def get_tracer(name: str = "vninvest") -> trace.Tracer:
    """Get a tracer instance."""
    return trace.get_tracer(name)


def get_meter(name: str = "vninvest") -> metrics.Meter:
    """Get a meter instance."""
    return metrics.get_meter(name)


@contextmanager
def trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL,
) -> Generator[trace.Span, None, None]:
    """
    Context manager for creating traced spans.

    Usage:
        with trace_span("fetch_quote", {"symbol": "ACB"}) as span:
            # do work
            span.set_attribute("result_count", 100)
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name, kind=kind) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            raise


def record_api_call(
    endpoint: str,
    provider: str,
    status: int,
    tenant_tier: str,
    latency_seconds: float,
) -> None:
    """Record API call metrics."""
    api_calls_total.labels(
        endpoint=endpoint,
        provider=provider,
        status=str(status),
        tenant_tier=tenant_tier,
    ).inc()
    api_latency_seconds.labels(
        endpoint=endpoint,
        provider=provider,
    ).observe(latency_seconds)


def record_cache_hit(data_type: str, tenant_tier: str) -> None:
    """Record cache hit."""
    cache_hits_total.labels(data_type=data_type, tenant_tier=tenant_tier).inc()


def record_cache_miss(data_type: str, tenant_tier: str) -> None:
    """Record cache miss."""
    cache_misses_total.labels(data_type=data_type, tenant_tier=tenant_tier).inc()


def record_quota_exceeded(limit_type: str, tenant_tier: str) -> None:
    """Record quota exceeded event."""
    quota_exceeded_total.labels(limit_type=limit_type, tenant_tier=tenant_tier).inc()


def set_active_streams(tenant_id: str, count: int) -> None:
    """Set active streams gauge."""
    active_streams.labels(tenant_id=tenant_id).set(count)


def set_active_tenants(count: int) -> None:
    """Set active tenants gauge."""
    active_tenants.set(count)


def shutdown_observability() -> None:
    """Shutdown observability providers."""
    global _tracer_provider, _meter_provider, _prometheus_server_started

    if _tracer_provider:
        _tracer_provider.shutdown()
        _tracer_provider = None

    if _meter_provider:
        _meter_provider.shutdown()
        _meter_provider = None

    _prometheus_server_started = False


# Convenience decorators
def traced(name: str | None = None, attributes: dict[str, Any] | None = None):
    """
    Decorator to trace a function.

    Usage:
        @traced("fetch_data", {"source": "vci"})
        async def fetch_data(symbol: str):
            ...
    """
    def decorator(func):
        import functools

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            span_name = name or f"{func.__module__}.{func.__qualname__}"
            with trace_span(span_name, attributes) as span:
                return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            span_name = name or f"{func.__module__}.{func.__qualname__}"
            with trace_span(span_name, attributes) as span:
                return func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
