"""Routing utilities for auto-selecting open data providers.

This module powers source='AUTO' across vnstock adapters.
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


AUTO_SOURCE = "auto"

# Open providers only. Do not include providers that require auth/token.
OPEN_SOURCE_CANDIDATES: Dict[str, List[str]] = {
    "quote": ["vci", "kbs", "msn"],
    "company": ["vci", "kbs"],
    "news": ["vci", "kbs", "rss_cafef", "rss_vneconomy"],
    "financial": ["vci", "kbs"],
    "trading": ["kbs", "vci"],
    "listing": ["kbs", "vci", "msn"],
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
    "listing": ["kbs", "vci", "msn"],
}

_health_lock = threading.Lock()
_health_state: Dict[Tuple[str, str], Dict[str, float]] = {}
_module_counters: Dict[str, itertools.count] = {}


def _get_trading_primary_override() -> str | None:
    value = str(os.getenv("VNSTOCK_TRADING_AUTO_PRIMARY", "")).strip().lower()
    if value in {"kbs", "vci"}:
        return value
    return None


def is_auto_source(source: str | None) -> bool:
    return str(source or "").strip().lower() == AUTO_SOURCE


def get_auto_candidates(module_name: str) -> List[str]:
    candidates = list(OPEN_SOURCE_CANDIDATES.get(module_name, []))
    if module_name == "trading":
        override = _get_trading_primary_override()
        if override in candidates:
            return [override] + [source for source in candidates if source != override]
    return candidates


def _stable_index(key: str, size: int) -> int:
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return int(digest, 16) % size


def _counter_for(module_name: str) -> itertools.count:
    with _health_lock:
        if module_name not in _module_counters:
            _module_counters[module_name] = itertools.count()
        return _module_counters[module_name]


def _is_in_cooldown(module_name: str, source: str, now: float) -> bool:
    state = _health_state.get((module_name, source), {})
    return state.get("cooldown_until", 0.0) > now


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

    return ordered


def record_success(module_name: str, source: str) -> None:
    with _health_lock:
        _health_state[(module_name, source)] = {
            "failures": 0,
            "cooldown_until": 0.0,
            "last_success": time.monotonic(),
        }


def record_failure(module_name: str, source: str) -> None:
    with _health_lock:
        state = _health_state.setdefault((module_name, source), {})
        failures = int(state.get("failures", 0)) + 1
        cooldown_seconds = min(90.0, 5.0 * (2 ** max(0, failures - 1)))
        state.update({
            "failures": failures,
            "cooldown_until": time.monotonic() + cooldown_seconds,
            "last_failure": time.monotonic(),
        })


def get_source_health_snapshot(module_name: str) -> Dict[str, Dict[str, float | bool | int | None]]:
    """Return current in-memory health state for AUTO candidates of a module."""
    now = time.monotonic()
    candidates = get_auto_candidates(module_name)
    snapshot: Dict[str, Dict[str, float | bool | int | None]] = {}

    with _health_lock:
        for source in candidates:
            state = _health_state.get((module_name, source), {})
            cooldown_until = float(state.get("cooldown_until", 0.0))
            last_success = state.get("last_success")
            last_failure = state.get("last_failure")
            snapshot[source.upper()] = {
                "failures": int(state.get("failures", 0)),
                "in_cooldown": cooldown_until > now,
                "cooldown_remaining_sec": round(max(0.0, cooldown_until - now), 3),
                "last_success_age_sec": round(now - last_success, 3) if last_success else None,
                "last_failure_age_sec": round(now - last_failure, 3) if last_failure else None,
            }

    return snapshot


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
    with _health_lock:
        _health_state.clear()
        _module_counters.clear()
