"""
Usage metering and billing event emission for Vninvest SDK.
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timedelta
from uuid import UUID

import redis.asyncio as redis

from .models import MeteringEvent, TenantContext, UsageMetrics


class MeteringBackend(ABC):
    """Abstract backend for storing metering events."""

    @abstractmethod
    async def record_event(self, event: MeteringEvent) -> None:
        pass

    @abstractmethod
    async def get_events(
        self,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
        limit: int = 10000,
    ) -> list[MeteringEvent]:
        pass

    @abstractmethod
    async def aggregate_usage(
        self,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
    ) -> UsageMetrics:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass


class RedisMeteringBackend(MeteringBackend):
    """Redis-backed metering storage with time-series optimization."""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        key_prefix: str = "vninvest:metering",
        retention_days: int = 90,
    ):
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self.retention_days = retention_days
        self._redis: redis.Redis | None = None
        self._owns_client = True

    async def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
            await self._redis.ping()
        return self._redis

    async def close(self) -> None:
        if self._owns_client and self._redis:
            await self._redis.aclose()
            self._redis = None

    def _daily_key(self, tenant_id: UUID, date: str) -> str:
        return f"{self.key_prefix}:events:{tenant_id}:{date}"

    def _index_key(self, tenant_id: UUID, date: str) -> str:
        return f"{self.key_prefix}:index:{tenant_id}:{date}"

    async def record_event(self, event: MeteringEvent) -> None:
        r = await self._get_redis()
        date_str = event.timestamp.strftime("%Y-%m-%d")
        daily_key = self._daily_key(event.tenant_id, date_str)
        index_key = self._index_key(event.tenant_id, date_str)

        # Store event as JSON in a sorted set (score = timestamp)
        event_json = event.model_dump_json()
        score = event.timestamp.timestamp()

        pipe = r.pipeline()
        pipe.zadd(daily_key, {event_json: score})
        pipe.zadd(index_key, {event.tenant_id: score})  # For fast tenant lookup
        pipe.expire(daily_key, self.retention_days * 86400)
        pipe.expire(index_key, self.retention_days * 86400)
        await pipe.execute()

    async def get_events(
        self,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
        limit: int = 10000,
    ) -> list[MeteringEvent]:
        r = await self._get_redis()
        events = []

        current = start
        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            daily_key = self._daily_key(tenant_id, date_str)

            start_score = max(current.timestamp(), start.timestamp())
            end_score = min((current + timedelta(days=1)).timestamp(), end.timestamp())

            results = await r.zrangebyscore(daily_key, start_score, end_score, start=0, num=limit)
            for event_json in results:
                try:
                    event = MeteringEvent.model_validate_json(event_json)
                    events.append(event)
                except Exception:
                    continue

            current += timedelta(days=1)
            if len(events) >= limit:
                break

        return events[:limit]

    async def aggregate_usage(
        self,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
    ) -> UsageMetrics:
        events = await self.get_events(tenant_id, start, end, limit=100000)

        if not events:
            return UsageMetrics(
                tenant_id=tenant_id,
                period_start=start,
                period_end=end,
            )

        total_calls = len(events)
        successful = sum(1 for e in events if 200 <= e.status_code < 400)
        failed = total_calls - successful
        total_symbols = set()
        total_bytes = 0
        latencies = []
        by_endpoint = defaultdict(int)
        by_provider = defaultdict(int)
        by_symbol = defaultdict(int)

        for e in events:
            total_symbols.update(e.symbols)
            total_bytes += e.data_bytes
            latencies.append(e.latency_ms)
            by_endpoint[e.endpoint] += 1
            by_provider[e.provider] += 1
            for sym in e.symbols:
                by_symbol[sym] += 1

        latencies.sort()
        n = len(latencies)

        def percentile(p: float) -> float:
            if n == 0:
                return 0.0
            idx = int(n * p)
            return latencies[min(idx, n - 1)]

        return UsageMetrics(
            tenant_id=tenant_id,
            period_start=start,
            period_end=end,
            total_calls=total_calls,
            successful_calls=successful,
            failed_calls=failed,
            total_symbols_accessed=len(total_symbols),
            total_data_bytes=total_bytes,
            avg_latency_ms=sum(latencies) / n if n > 0 else 0,
            p50_latency_ms=percentile(0.5),
            p95_latency_ms=percentile(0.95),
            p99_latency_ms=percentile(0.99),
            by_endpoint=dict(by_endpoint),
            by_provider=dict(by_provider),
            by_symbol=dict(by_symbol),
        )


class InMemoryMeteringBackend(MeteringBackend):
    """In-memory metering backend for development/testing."""

    def __init__(self):
        self._events: dict[UUID, list[MeteringEvent]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def record_event(self, event: MeteringEvent) -> None:
        async with self._lock:
            self._events[event.tenant_id].append(event)

    async def get_events(
        self,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
        limit: int = 10000,
    ) -> list[MeteringEvent]:
        async with self._lock:
            events = self._events.get(tenant_id, [])
            filtered = [e for e in events if start <= e.timestamp <= end]
            return filtered[:limit]

    async def aggregate_usage(
        self,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
    ) -> UsageMetrics:
        events = await self.get_events(tenant_id, start, end, limit=100000)
        # Reuse aggregation logic from Redis backend
        if not events:
            return UsageMetrics(tenant_id=tenant_id, period_start=start, period_end=end)

        total_calls = len(events)
        successful = sum(1 for e in events if 200 <= e.status_code < 400)
        failed = total_calls - successful
        total_symbols = set()
        total_bytes = 0
        latencies = []
        by_endpoint = defaultdict(int)
        by_provider = defaultdict(int)
        by_symbol = defaultdict(int)

        for e in events:
            total_symbols.update(e.symbols)
            total_bytes += e.data_bytes
            latencies.append(e.latency_ms)
            by_endpoint[e.endpoint] += 1
            by_provider[e.provider] += 1
            for sym in e.symbols:
                by_symbol[sym] += 1

        latencies.sort()
        n = len(latencies)

        def percentile(p: float) -> float:
            if n == 0:
                return 0.0
            idx = int(n * p)
            return latencies[min(idx, n - 1)]

        return UsageMetrics(
            tenant_id=tenant_id,
            period_start=start,
            period_end=end,
            total_calls=total_calls,
            successful_calls=successful,
            failed_calls=failed,
            total_symbols_accessed=len(total_symbols),
            total_data_bytes=total_bytes,
            avg_latency_ms=sum(latencies) / n if n > 0 else 0,
            p50_latency_ms=percentile(0.5),
            p95_latency_ms=percentile(0.95),
            p99_latency_ms=percentile(0.99),
            by_endpoint=dict(by_endpoint),
            by_provider=dict(by_provider),
            by_symbol=dict(by_symbol),
        )

    async def close(self) -> None:
        pass


class BillingEventEmitter:
    """
    Emits billing events for external billing systems.

    Supports multiple output targets: webhook, message queue, log.
    """

    def __init__(
        self,
        webhook_url: str | None = None,
        webhook_secret: str | None = None,
        batch_size: int = 100,
        flush_interval_seconds: float = 30.0,
    ):
        self.webhook_url = webhook_url
        self.webhook_secret = webhook_secret
        self.batch_size = batch_size
        self.flush_interval = flush_interval_seconds

        self._buffer: list[MeteringEvent] = []
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start background flush task."""
        if self._running:
            return
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def stop(self) -> None:
        """Stop background flush task and flush remaining."""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self.flush()

    async def emit(self, event: MeteringEvent) -> None:
        """Add event to buffer for batch emission."""
        async with self._lock:
            self._buffer.append(event)
            if len(self._buffer) >= self.batch_size:
                await self._flush_buffer()

    async def flush(self) -> None:
        """Flush all buffered events."""
        async with self._lock:
            await self._flush_buffer()

    async def _flush_loop(self) -> None:
        while self._running:
            await asyncio.sleep(self.flush_interval)
            await self.flush()

    async def _flush_buffer(self) -> None:
        if not self._buffer:
            return

        events = self._buffer
        self._buffer = []

        if self.webhook_url:
            await self._send_webhook(events)

    async def _send_webhook(self, events: list[MeteringEvent]) -> None:
        import hashlib
        import hmac

        import httpx

        payload = {
            "events": [e.model_dump(mode="json") for e in events],
            "count": len(events),
            "timestamp": datetime.utcnow().isoformat(),
        }

        headers = {"Content-Type": "application/json"}
        if self.webhook_secret:
            body = json.dumps(payload, separators=(",", ":"))
            sig = hmac.new(self.webhook_secret.encode(), body.encode(), hashlib.sha256).hexdigest()
            headers["X-Vninvest-Signature"] = sig

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(self.webhook_url, json=payload, headers=headers)
        except Exception:
            # Log error but don't raise - billing emission shouldn't break API
            pass


class UsageTracker:
    """
    High-level usage tracking interface.

    Combines metering backend with billing emission.
    """

    def __init__(
        self,
        backend: MeteringBackend,
        billing_emitter: BillingEventEmitter | None = None,
    ):
        self.backend = backend
        self.billing_emitter = billing_emitter

    async def record_call(
        self,
        context: TenantContext,
        endpoint: str,
        provider: str,
        symbols: list[str],
        latency_ms: int,
        status_code: int,
        data_bytes: int = 0,
        error_message: str | None = None,
        cache_hit: bool = False,
        correlation_id: str | None = None,
    ) -> MeteringEvent:
        """Record a single API call."""
        event = MeteringEvent(
            tenant_id=context.tenant_id,
            endpoint=endpoint,
            provider=provider,
            symbols=symbols,
            request_count=1,
            data_bytes=data_bytes,
            latency_ms=latency_ms,
            status_code=status_code,
            error_message=error_message,
            cache_hit=cache_hit,
            correlation_id=correlation_id,
        )

        await self.backend.record_event(event)

        if self.billing_emitter:
            await self.billing_emitter.emit(event)

        return event

    async def get_usage(
        self,
        tenant_id: UUID,
        start: datetime,
        end: datetime,
    ) -> UsageMetrics:
        """Get aggregated usage metrics for a tenant."""
        return await self.backend.aggregate_usage(tenant_id, start, end)

    async def close(self) -> None:
        await self.backend.close()
        if self.billing_emitter:
            await self.billing_emitter.stop()


def create_metering_backend(
    redis_url: str | None = None,
    use_memory: bool = False,
) -> MeteringBackend:
    """Factory function to create metering backend."""
    if use_memory or not redis_url:
        return InMemoryMeteringBackend()
    return RedisMeteringBackend(redis_url=redis_url)
