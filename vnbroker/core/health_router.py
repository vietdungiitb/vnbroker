"""Health router for real-time provider health tracking.

Wraps source_router's health store with a latency-aware view:
- delegates failure/success recording to source_router (single source of truth)
- maintains a rolling latency window per provider for ranking
- returns healthy providers sorted by average latency (fastest first)
"""

from __future__ import annotations

import collections
import threading
from typing import Dict, List


class HealthRouter:
    """Tracks provider health in real-time."""

    def __init__(self) -> None:
        self._store = None  # Will use source_router's health store
        self._latency_window: Dict[str, "collections.deque[float]"] = {}
        self._lock = threading.Lock()

    def record_success(self, provider: str, latency_ms: float, module: str = "quote") -> None:
        """Record successful request with latency."""
        from vnbroker.core import source_router
        source_router.record_success(module, provider)
        self._update_latency(provider, latency_ms)

    def record_failure(self, provider: str, error: Exception, module: str = "quote") -> None:
        """Record failed request."""
        from vnbroker.core import source_router
        source_router.record_failure(module, provider)

    def get_healthy_providers(self, module: str) -> List[str]:
        """Return healthy providers sorted by average latency."""
        from vnbroker.core import source_router
        health = source_router.get_source_health_snapshot(module)
        healthy = [p for p, h in health.items() if not h.get("in_cooldown", False)]
        return sorted(healthy, key=lambda p: self._avg_latency(p))

    def _update_latency(self, provider: str, latency_ms: float) -> None:
        """Update rolling latency window."""
        with self._lock:
            if provider not in self._latency_window:
                self._latency_window[provider] = collections.deque(maxlen=50)
            self._latency_window[provider].append(latency_ms)

    def _avg_latency(self, provider: str) -> float:
        """Get average latency for provider (case-insensitive)."""
        with self._lock:
            # source_router returns uppercase keys; we store lowercase
            window: "collections.deque[float]" = self._latency_window.get(
                provider, collections.deque()
            )
            if not window:
                # Try case-insensitive lookup
                for k, v in self._latency_window.items():
                    if k.upper() == provider.upper():
                        window = v
                        break
            return sum(window) / len(window) if window else float("inf")
