"""Routing utilities for auto-selecting open data providers.

This module powers source='AUTO' across vnbroker adapters.
It focuses on two goals:
1. maximize throughput by spreading load across healthy open providers
2. fail over quickly when a provider starts rate-limiting or timing out
"""

from __future__ import annotations

import hashlib
import itertools
import os
import threading
import time
from typing import Any, Dict, List, Tuple

from vnbroker.core.health_store import (
    HealthStore,
    create_store,
    wall_now,
)


AUTO_SOURCE = "auto"

# Open providers only. Do not include providers that require auth/token.
OPEN_SOURCE_CANDIDATES: Dict[str, List[str]] = {
    "quote": ["vci", "kbs"],
    "company": ["vci", "kbs"],
    "news": ["vci", "kbs", "rss_cafef", "rss_vneconomy"],
    "financial": ["vci", "kbs"],
    "trading": ["kbs", "vci"],
    "listing": ["kbs", "vci"],
}

# Primary pools used for throughput-oriented sharding.
# quote uses single-item ["vci"] so hash-shard always picks VCI first;
# trading uses single-item ["kbs"] because current online benchmarks show
# KBS price_board is materially more stable under sustained load.
# Remaining providers activate only on confirmed failover.
PRIMARY_SOURCE_POOLS: Dict[str, List[str]] = {
    "quote": ["vci"],
    "company": ["vci"],
    "news": ["vci", "kbs"],
    "financial": ["vci"],
    "trading": ["kbs"],
    "listing": ["kbs", "vci"],
}

_health_lock = threading.RLock()  # RLock: build_source_order holds the lock
# while _is_in_cooldown -> _ensure_store_loaded re-acquires it (cold-start
# deadlock with Lock; found by P3 SSI AUTO tests on a fresh process).
_health_state: Dict[Tuple[str, str], Dict[str, float]] = {}
_module_counters: Dict[str, "itertools.count[int]"] = {}

# Persist debounce (P4c): batch SQLite writes instead of fsync per request.
_PERSIST_DEBOUNCE_SEC = 1.0
_PERSIST_EVERY_N = 10
_persist_pending = 0
_last_persist_mono = 0.0

# Persistent store singleton (lazy). Restart-safe: failure counters and
# cooldown-remaining are reloaded from disk on first use.
_store: HealthStore | None = None
_store_loaded = False


def _get_store() -> HealthStore:
    global _store
    if _store is None:
        _store = create_store()
    return _store


def reload_store() -> None:
    """Drop the store singleton so the next access recreates it.

    Used by tests to pick up a new ``vnbroker_ROUTER_HEALTH_DB`` value
    (simulates a process restart when combined with in-memory reset).
    """
    global _store, _store_loaded
    with _health_lock:
        _store = None
        _store_loaded = False


def _ensure_store_loaded() -> None:
    global _store_loaded
    if _store_loaded:
        return
    with _health_lock:
        if _store_loaded:
            return
        try:
            persisted = _get_store().load()
        except Exception:
            persisted = {}
        mono_now = time.monotonic()
        wall_current = wall_now()
        for key, vals in persisted.items():
            failures = int(vals.get("failures", 0))
            if failures <= 0:
                continue
            remaining = float(vals.get("cooldown_until_wall", 0.0)) - wall_current
            entry = _health_state.setdefault(key, {})
            entry["failures"] = failures
            entry["cooldown_until"] = mono_now + remaining if remaining > 0 else 0.0
            if vals.get("last_failure_wall") is not None:
                entry["last_failure"] = mono_now  # age unknown post-restart
        _store_loaded = True


def _persist_state(force: bool = False) -> None:
    """Persist health snapshot with debounce (P4c).

    Every ``record_*`` used to fsync SQLite per request (thousands of
    fsync/s at 24 concurrency). Now flush at most once per
    ``_PERSIST_DEBOUNCE_SEC`` or every ``_PERSIST_EVERY_N`` events;
    ``force=True`` flushes immediately (shutdown/tests).
    """
    global _persist_pending, _last_persist_mono
    now = time.monotonic()
    with _health_lock:
        _persist_pending += 1
        if (
            not force
            and _persist_pending < _PERSIST_EVERY_N
            and now - _last_persist_mono < _PERSIST_DEBOUNCE_SEC
        ):
            return
        _persist_pending = 0
        _last_persist_mono = now
    try:
        store = _get_store()
        mono_now = time.monotonic()
        wall_current = wall_now()
        wall_state: Dict[Tuple[str, str], Dict[str, float]] = {}
        with _health_lock:
            snapshot = {k: dict(v) for k, v in _health_state.items()}
        for key, vals in snapshot.items():
            remaining = float(vals.get("cooldown_until", 0.0)) - mono_now
            wall_state[key] = {
                "failures": float(vals.get("failures", 0)),
                "cooldown_until_wall": wall_current + remaining if remaining > 0 else 0.0,
            }
        # Drop entries with no failures to keep the DB small
        wall_state = {k: v for k, v in wall_state.items() if v["failures"] > 0}
        store.save(wall_state)
    except Exception:
        pass


def _get_trading_primary_override() -> str | None:
    value = str(os.getenv("vnbroker_TRADING_AUTO_PRIMARY", "")).strip().lower()
    if value in {"kbs", "vci"}:
        return value
    return None


# SSI extras for AUTO: only modules with native SSI data (empty-fallback
# modules company/financial/news are excluded — an empty DF would record
# a false success). SSI joins as failover; opt-in primary via
# vnbroker_SSI_AUTO_PRIMARY=1 (quota 10rps — never default primary).
SSI_AUTO_CANDIDATES: Dict[str, List[str]] = {
    "quote": ["ssi"],
    "listing": ["ssi"],
    "trading": ["ssi"],
}


def has_ssi_credentials() -> bool:
    """True when SSI market credentials are configured (no network)."""
    return bool(
        (os.getenv("VNBROKER_BROKER_SSI_API_KEY") or "").strip()
        and (os.getenv("VNBROKER_BROKER_SSI_API_SECRET") or "").strip()
    )


def _ssi_primary_enabled() -> bool:
    return (
        str(os.getenv("vnbroker_SSI_AUTO_PRIMARY", "")).strip().lower()
        in {"1", "true", "yes"}
    )


def is_auto_source(source: str | None) -> bool:
    return str(source or "").strip().lower() == AUTO_SOURCE


def get_auto_candidates(module_name: str) -> List[str]:
    candidates = list(OPEN_SOURCE_CANDIDATES.get(module_name, []))
    if module_name == "trading":
        override = _get_trading_primary_override()
        if override in candidates:
            return [override] + [source for source in candidates if source != override]
    for extra in SSI_AUTO_CANDIDATES.get(module_name, []):
        if extra not in candidates and has_ssi_credentials():
            candidates.append(extra)
    return candidates


def _stable_index(key: str, size: int) -> int:
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return int(digest, 16) % size


def _counter_for(module_name: str) -> "itertools.count[int]":
    with _health_lock:
        if module_name not in _module_counters:
            _module_counters[module_name] = itertools.count()
        return _module_counters[module_name]


def _is_in_cooldown(module_name: str, source: str, now: float) -> bool:
    _ensure_store_loaded()
    state = _health_state.get((module_name, source), {})
    return state.get("cooldown_until", 0.0) > now


def is_half_open(module_name: str, source: str, now: float | None = None) -> bool:
    """A source is half-open when its cooldown expired but it still has
    recorded failures and no success since — the next request is a probe."""
    _ensure_store_loaded()
    now = time.monotonic() if now is None else now
    state = _health_state.get((module_name, source), {})
    return (
        int(state.get("failures", 0)) > 0
        and state.get("cooldown_until", 0.0) <= now
    )


def build_source_order(module_name: str, symbol: str | None = None) -> List[str]:
    candidates = get_auto_candidates(module_name)
    if not candidates:
        return []

    now = time.monotonic()
    with _health_lock:
        healthy = [
            source for source in candidates
            if not _is_in_cooldown(module_name, source, now)
        ]
    ordered_pool = healthy or candidates

    primary_candidates = PRIMARY_SOURCE_POOLS.get(module_name, ordered_pool)
    if module_name == "trading":
        override = _get_trading_primary_override()
        if override in ordered_pool:
            primary_candidates = [override]
    if _ssi_primary_enabled() and "ssi" in ordered_pool:
        primary_candidates = ["ssi"] + [
            s for s in primary_candidates if s != "ssi"
        ]

    # Half-open probes go first: a source whose cooldown just expired
    # gets a single trial request before full traffic is restored.
    probes = [
        source for source in candidates
        if is_half_open(module_name, source, now)
    ]

    primary_pool = [
        source for source in primary_candidates
        if source in ordered_pool
    ]
    extras = [source for source in ordered_pool if source not in primary_pool]

    if symbol and primary_pool:
        index = _stable_index(f"{module_name}:{symbol.upper()}", len(primary_pool))
        primary_order = primary_pool[index:] + primary_pool[:index]
        ordered = primary_order + extras
    else:
        pool = primary_pool or ordered_pool
        start = next(_counter_for(module_name)) % len(pool)
        rotated = pool[start:] + pool[:start]
        ordered = rotated + [source for source in ordered_pool if source not in rotated]

    if healthy and len(healthy) < len(candidates):
        unhealthy = [source for source in candidates if source not in healthy]
        ordered.extend(source for source in unhealthy if source not in ordered)

    if probes:
        ordered = [p for p in probes if p in candidates] + [
            s for s in ordered if s not in probes
        ]

    return ordered


def record_success(module_name: str, source: str) -> None:
    _ensure_store_loaded()
    with _health_lock:
        _health_state[(module_name, source)] = {
            "failures": 0,
            "cooldown_until": 0.0,
            "last_success": time.monotonic(),
        }
    _persist_state()


def record_failure(module_name: str, source: str) -> None:
    _ensure_store_loaded()
    with _health_lock:
        state = _health_state.setdefault((module_name, source), {})
        failures = int(state.get("failures", 0)) + 1
        cooldown_seconds = min(90.0, 5.0 * (2 ** max(0, failures - 1)))
        state.update({
            "failures": failures,
            "cooldown_until": time.monotonic() + cooldown_seconds,
            "last_failure": time.monotonic(),
        })
    _persist_state()


def get_source_health_snapshot(module_name: str) -> Dict[str, Dict[str, float | bool | int | None]]:
    """Return current health state for AUTO candidates of a module.

    This is the ``health()`` metric for the circuit breaker: failures,
    cooldown status, half-open probe status, and last-event ages.
    """
    _ensure_store_loaded()
    now = time.monotonic()
    candidates = get_auto_candidates(module_name)
    snapshot: Dict[str, Dict[str, float | bool | int | None]] = {}

    with _health_lock:
        states = {s: dict(_health_state.get((module_name, s), {})) for s in candidates}
    for source in candidates:
        state = states[source]
        cooldown_until = float(state.get("cooldown_until", 0.0))
        last_success = state.get("last_success")
        last_failure = state.get("last_failure")
        snapshot[source.upper()] = {
            "failures": int(state.get("failures", 0)),
            "in_cooldown": cooldown_until > now,
            "half_open": (
                int(state.get("failures", 0)) > 0 and cooldown_until <= now
            ),
            "cooldown_remaining_sec": round(max(0.0, cooldown_until - now), 3),
            "last_success_age_sec": round(now - last_success, 3) if last_success else None,
            "last_failure_age_sec": round(now - last_failure, 3) if last_failure else None,
        }

    return snapshot


def health(module_name: str) -> Dict[str, Dict[str, float | bool | int | None]]:
    """Alias of :func:`get_source_health_snapshot` (circuit-breaker metric)."""
    return get_source_health_snapshot(module_name)


def should_failover(exc: Exception) -> bool:
    # KeyError / LookupError = provider returned payload missing expected keys
    if isinstance(exc, (ConnectionError, TimeoutError, NotImplementedError, KeyError, LookupError)):
        return True

    message = str(exc).lower()
    failover_markers = (
        "429",
        "403",
        "timeout",
        "timed out",
        "too many requests",
        "rate limit",
        "service unavailable",
        "temporarily unavailable",
        "connection",
        "remote disconnected",
        "failed to fetch data",
        "api request failed",
        "does not support",
        "not support",
        "not implemented",
    )
    return any(marker in message for marker in failover_markers)


def annotate_result_source(result: Any, source: str) -> Any:
    source_used = source.upper()
    attrs = getattr(result, "attrs", None)
    if isinstance(attrs, dict):
        attrs["source_used"] = source_used
        return result
    if isinstance(result, dict):
        result.setdefault("source_used", source_used)
    return result


def reset_router_state() -> None:
    global _persist_pending, _last_persist_mono
    with _health_lock:
        _health_state.clear()
        _module_counters.clear()
        _persist_pending = 0
        _last_persist_mono = 0.0
    try:
        _get_store().clear()
    except Exception:
        pass


def flush_router_state() -> None:
    """Force-flush pending health state to disk (shutdown/tests)."""
    _persist_state(force=True)
