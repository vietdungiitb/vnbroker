"""Shared adaptive concurrency controller for all vnstock providers.

Eliminates code duplication between VCI and KBS adaptive implementations and
adds optional cross-provider backpressure via `GlobalPressure`.
"""

from __future__ import annotations

import os
import threading
from typing import Optional


# ---------------------------------------------------------------------------
# Env-var helpers (shared; previously duplicated in VCI & KBS Quote classes)
# ---------------------------------------------------------------------------

def _env_int(name: str, default: int, min_value: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None:
        return max(default, min_value)
    try:
        return max(int(raw), min_value)
    except (ValueError, TypeError):
        return max(default, min_value)


def _env_float(
    name: str,
    default: float,
    min_value: float = 0.0,
    max_value: Optional[float] = None,
) -> float:
    raw = os.getenv(name)
    if raw is None:
        value = max(default, min_value)
        if max_value is not None:
            value = min(value, max_value)
        return value
    try:
        value = float(raw)
    except (ValueError, TypeError):
        value = default
    value = max(value, min_value)
    if max_value is not None:
        value = min(value, max_value)
    return value


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# AdaptiveController
# ---------------------------------------------------------------------------

class AdaptiveController:
    """Thread-safe concurrency controller that adjusts worker count based on
    observed latency and error rates within a batch window.

    Two usage patterns:

    **Stateless** (matches existing per-call behaviour):
        new_w = AdaptiveController.compute(current=w, batch_size=n, ...)

    **Stateful** (persists across `fetch_multiple` calls):
        ctrl = AdaptiveController.from_env("VNSTOCK_VCI_ADAPTIVE_", ...)
        new_w = ctrl.adjust(batch_size=n, success_count=s, batch_p95_seconds=p)
    """

    def __init__(
        self,
        start: int,
        min_workers: int,
        max_workers: int,
        step_up: int,
        step_down: int,
        p95_low_seconds: float,
        p95_high_seconds: float,
        fail_threshold: float,
    ) -> None:
        self.current = max(min_workers, min(start, max_workers))
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.step_up = step_up
        self.step_down = step_down
        self.p95_low_seconds = p95_low_seconds
        self.p95_high_seconds = p95_high_seconds
        self.fail_threshold = fail_threshold
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(
        cls,
        prefix: str,
        *,
        default_start: int = 6,
        default_min: int = 2,
        default_max: int = 16,
        default_step_up: int = 1,
        default_step_down: int = 3,
        default_p95_low: float = 0.35,
        default_p95_high: float = 1.0,
        default_fail_threshold: float = 0.15,
    ) -> "AdaptiveController":
        """Create a controller by reading env vars with the given *prefix*.

        Variables read (prefix + suffix)::

            START_CONCURRENCY   MIN_CONCURRENCY   MAX_CONCURRENCY
            STEP_UP             STEP_DOWN
            FAIL_THRESHOLD      P95_LOW_SECONDS   P95_HIGH_SECONDS
        """
        start = _env_int(f"{prefix}START_CONCURRENCY", default_start)
        min_w = _env_int(f"{prefix}MIN_CONCURRENCY", default_min, min_value=1)
        max_w = _env_int(f"{prefix}MAX_CONCURRENCY", default_max, min_value=min_w)
        step_up = _env_int(f"{prefix}STEP_UP", default_step_up, min_value=1)
        step_down = _env_int(f"{prefix}STEP_DOWN", default_step_down, min_value=1)
        fail_th = _env_float(
            f"{prefix}FAIL_THRESHOLD",
            default_fail_threshold,
            min_value=0.0,
            max_value=1.0,
        )
        p95_low = _env_float(
            f"{prefix}P95_LOW_SECONDS", default_p95_low, min_value=0.01
        )
        p95_high = _env_float(
            f"{prefix}P95_HIGH_SECONDS",
            default_p95_high,
            min_value=p95_low + 0.01,
        )
        return cls(
            start=start,
            min_workers=min_w,
            max_workers=max_w,
            step_up=step_up,
            step_down=step_down,
            p95_low_seconds=p95_low,
            p95_high_seconds=p95_high,
            fail_threshold=fail_th,
        )

    # ------------------------------------------------------------------
    # Core algorithm — stateless pure function (kept for test compatibility)
    # ------------------------------------------------------------------

    @staticmethod
    def compute(
        current: int,
        batch_size: int,
        success_count: int,
        max_concurrency: int,
        min_concurrency: int,
        step_up: int,
        step_down: int,
        fail_threshold: float,
        batch_p95_seconds: float,
        p95_high_seconds: float,
        p95_low_seconds: float,
        # aliases accepted for backward-compat with KBS tests
        max_workers: Optional[int] = None,
        min_workers: Optional[int] = None,
    ) -> int:
        """Pure function: return the suggested new worker count."""
        if batch_size <= 0:
            return current
        eff_max = max_workers if max_workers is not None else max_concurrency
        eff_min = min_workers if min_workers is not None else min_concurrency
        failures = max(batch_size - success_count, 0)
        fail_ratio = failures / float(batch_size)
        if fail_ratio > fail_threshold or batch_p95_seconds >= p95_high_seconds:
            return max(eff_min, current - step_down)
        if failures == 0 and batch_p95_seconds <= p95_low_seconds:
            return min(eff_max, current + step_up)
        return current

    # ------------------------------------------------------------------
    # Stateful interface
    # ------------------------------------------------------------------

    def adjust(
        self,
        batch_size: int,
        success_count: int,
        batch_p95_seconds: float,
        cap_max: Optional[int] = None,
    ) -> int:
        """Compute new worker count from batch metrics, persist and return it."""
        with self._lock:
            effective_max = (
                min(cap_max, self.max_workers) if cap_max is not None else self.max_workers
            )
            new = self.compute(
                current=self.current,
                batch_size=batch_size,
                success_count=success_count,
                max_concurrency=effective_max,
                min_concurrency=self.min_workers,
                step_up=self.step_up,
                step_down=self.step_down,
                fail_threshold=self.fail_threshold,
                batch_p95_seconds=batch_p95_seconds,
                p95_high_seconds=self.p95_high_seconds,
                p95_low_seconds=self.p95_low_seconds,
            )
            self.current = new
            return new

    def cap_to(self, hard_max: int) -> int:
        """Clamp `self.current` to *hard_max* (e.g. per-call concurrency override)."""
        with self._lock:
            self.current = min(self.current, max(self.min_workers, hard_max))
            return self.current


# ---------------------------------------------------------------------------
# GlobalPressure — cross-provider backpressure signal
# ---------------------------------------------------------------------------

class GlobalPressure:
    """Process-wide stress detector that aggregates error signals from all
    providers.  When the combined error ratio across any batch window exceeds
    ``threshold``, the ``stressed`` flag is raised and all providers that
    query ``multiplier`` receive 0.5 instead of 1.0, halving their effective
    concurrency cap.

    The flag self-heals automatically after ``decay_windows`` consecutive
    clean windows (error ratio ≤ threshold).
    """

    def __init__(self, threshold: float = 0.3, decay_windows: int = 3) -> None:
        self._threshold = threshold
        self._decay = decay_windows
        self._lock = threading.Lock()
        self._clean_streak = 0
        self._stressed = False

    def record_batch(self, batch_size: int, error_count: int) -> None:
        """Update stress state based on an observed batch outcome."""
        if batch_size <= 0:
            return
        fail_ratio = max(error_count, 0) / float(batch_size)
        with self._lock:
            if fail_ratio > self._threshold:
                self._stressed = True
                self._clean_streak = 0
            else:
                self._clean_streak += 1
                if self._clean_streak >= self._decay:
                    self._stressed = False

    @property
    def stressed(self) -> bool:
        return self._stressed

    @property
    def multiplier(self) -> float:
        """Return 0.5 under stress, 1.0 otherwise."""
        return 0.5 if self._stressed else 1.0


# Module-level singleton — shared across all providers in the process.
_global_pressure = GlobalPressure()


def get_global_pressure() -> GlobalPressure:
    """Return the process-wide `GlobalPressure` singleton."""
    return _global_pressure


__all__ = [
    "AdaptiveController",
    "GlobalPressure",
    "get_global_pressure",
    "_env_int",
    "_env_float",
    "_env_bool",
]
