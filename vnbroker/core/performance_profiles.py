"""Performance profile presets for fast runtime tuning via environment variables."""

from __future__ import annotations

import datetime
import os
from typing import Dict, Optional

PROFILE_PRESETS: Dict[str, Dict[str, str]] = {
    "benchmark_max_speed": {
        "vnbroker_TRADING_AUTO_PRIMARY": "kbs",
        "vnbroker_VCI_ADAPTIVE_CONCURRENCY": "1",
        "vnbroker_VCI_ADAPTIVE_START_CONCURRENCY": "10",
        "vnbroker_VCI_ADAPTIVE_MIN_CONCURRENCY": "2",
        "vnbroker_VCI_ADAPTIVE_STEP_UP": "3",
        "vnbroker_VCI_ADAPTIVE_STEP_DOWN": "5",
        "vnbroker_VCI_ADAPTIVE_FAIL_THRESHOLD": "0.25",
        "vnbroker_VCI_ADAPTIVE_P95_LOW_SECONDS": "0.25",
        "vnbroker_VCI_ADAPTIVE_P95_HIGH_SECONDS": "1.20",
        "vnbroker_KBS_ADAPTIVE_CONCURRENCY": "1",
        "vnbroker_KBS_ADAPTIVE_START_CONCURRENCY": "8",
        "vnbroker_KBS_ADAPTIVE_MIN_CONCURRENCY": "2",
        "vnbroker_KBS_ADAPTIVE_STEP_UP": "2",
        "vnbroker_KBS_ADAPTIVE_STEP_DOWN": "4",
        "vnbroker_KBS_ADAPTIVE_FAIL_THRESHOLD": "0.25",
        "vnbroker_KBS_ADAPTIVE_P95_LOW_SECONDS": "0.35",
        "vnbroker_KBS_ADAPTIVE_P95_HIGH_SECONDS": "1.40",
        "vnbroker_MAX_RETRIES": "1",
        "vnbroker_ASYNC_STATS_ENABLED": "0",
    },
    "production_stable": {
        "vnbroker_TRADING_AUTO_PRIMARY": "kbs",
        "vnbroker_VCI_ADAPTIVE_CONCURRENCY": "1",
        "vnbroker_VCI_ADAPTIVE_START_CONCURRENCY": "6",
        "vnbroker_VCI_ADAPTIVE_MIN_CONCURRENCY": "2",
        "vnbroker_VCI_ADAPTIVE_STEP_UP": "1",
        "vnbroker_VCI_ADAPTIVE_STEP_DOWN": "3",
        "vnbroker_VCI_ADAPTIVE_FAIL_THRESHOLD": "0.15",
        "vnbroker_VCI_ADAPTIVE_P95_LOW_SECONDS": "0.35",
        "vnbroker_VCI_ADAPTIVE_P95_HIGH_SECONDS": "1.00",
        "vnbroker_KBS_ADAPTIVE_CONCURRENCY": "1",
        "vnbroker_KBS_ADAPTIVE_START_CONCURRENCY": "4",
        "vnbroker_KBS_ADAPTIVE_MIN_CONCURRENCY": "2",
        "vnbroker_KBS_ADAPTIVE_STEP_UP": "1",
        "vnbroker_KBS_ADAPTIVE_STEP_DOWN": "2",
        "vnbroker_KBS_ADAPTIVE_FAIL_THRESHOLD": "0.15",
        "vnbroker_KBS_ADAPTIVE_P95_LOW_SECONDS": "0.45",
        "vnbroker_KBS_ADAPTIVE_P95_HIGH_SECONDS": "1.20",
        "vnbroker_MAX_RETRIES": "2",
        "vnbroker_ASYNC_STATS_ENABLED": "1",
    },
    # During VN stock-market open hours (09:00-11:30 and 13:00-15:30 ICT, Mon-Fri)
    # servers are under heavy load; use conservative concurrency to avoid 429s.
    "market_hours": {
        "vnbroker_TRADING_AUTO_PRIMARY": "kbs",
        "vnbroker_VCI_ADAPTIVE_CONCURRENCY": "1",
        "vnbroker_VCI_ADAPTIVE_START_CONCURRENCY": "4",
        "vnbroker_VCI_ADAPTIVE_MIN_CONCURRENCY": "2",
        "vnbroker_VCI_ADAPTIVE_STEP_UP": "1",
        "vnbroker_VCI_ADAPTIVE_STEP_DOWN": "2",
        "vnbroker_VCI_ADAPTIVE_FAIL_THRESHOLD": "0.10",
        "vnbroker_VCI_ADAPTIVE_P95_LOW_SECONDS": "0.50",
        "vnbroker_VCI_ADAPTIVE_P95_HIGH_SECONDS": "1.50",
        "vnbroker_KBS_ADAPTIVE_CONCURRENCY": "1",
        "vnbroker_KBS_ADAPTIVE_START_CONCURRENCY": "3",
        "vnbroker_KBS_ADAPTIVE_MIN_CONCURRENCY": "1",
        "vnbroker_KBS_ADAPTIVE_STEP_UP": "1",
        "vnbroker_KBS_ADAPTIVE_STEP_DOWN": "2",
        "vnbroker_KBS_ADAPTIVE_FAIL_THRESHOLD": "0.10",
        "vnbroker_KBS_ADAPTIVE_P95_LOW_SECONDS": "0.60",
        "vnbroker_KBS_ADAPTIVE_P95_HIGH_SECONDS": "1.80",
        "vnbroker_MAX_RETRIES": "3",
        "vnbroker_ASYNC_STATS_ENABLED": "1",
    },
}


def list_profiles() -> list[str]:
    """Return available preset names."""
    return sorted(PROFILE_PRESETS.keys())


def get_profile(name: str) -> Dict[str, str]:
    """Return environment variable mapping for a profile."""
    key = str(name).strip().lower()
    if key not in PROFILE_PRESETS:
        options = ", ".join(list_profiles())
        raise ValueError(f"Unknown performance profile '{name}'. Available: {options}")
    return dict(PROFILE_PRESETS[key])


def apply_profile(name: str, overwrite: bool = True) -> Dict[str, str]:
    """Apply profile to current process environment and return applied values."""
    profile = get_profile(name)
    applied: Dict[str, str] = {}
    for env_name, env_value in profile.items():
        if overwrite or env_name not in os.environ:
            os.environ[env_name] = env_value
            applied[env_name] = env_value
    return applied


# ---------------------------------------------------------------------------
# Market-hour awareness
# ---------------------------------------------------------------------------

# VN market sessions (ICT = UTC+7)
# Morning:   09:00–11:30
# Afternoon: 13:00–15:30
# Weekends are always off-peak.
_ICT = datetime.timezone(datetime.timedelta(hours=7))
_MARKET_SESSIONS = [
    (datetime.time(9, 0), datetime.time(11, 30)),
    (datetime.time(13, 0), datetime.time(15, 30)),
]


def is_market_hours(now: Optional[datetime.datetime] = None) -> bool:
    """Return True if *now* (default: current ICT wall-clock) falls inside a VN
    market session (Mon–Fri, 09:00-11:30 or 13:00-15:30 ICT)."""
    if now is None:
        now = datetime.datetime.now(_ICT)
    else:
        if now.tzinfo is None:
            now = now.replace(tzinfo=_ICT)
        else:
            now = now.astimezone(_ICT)
    # weekday(): 0=Mon … 6=Sun; weekend index >= 5 is always off-peak
    if now.weekday() >= 5:
        return False
    t = now.time()
    return any(start <= t <= end for start, end in _MARKET_SESSIONS)


def apply_profile_for_current_time(
    peak_profile: str = "market_hours",
    offpeak_profile: str = "benchmark_max_speed",
    overwrite: bool = True,
    now: Optional[datetime.datetime] = None,
) -> Dict[str, str]:
    """Apply the correct profile based on the current VN market session.

    During VN market open hours (Mon–Fri 09:00-11:30 or 13:00-15:30 ICT) the
    *peak_profile* is applied (default: ``market_hours``).  At all other times
    (evenings, weekends, public-holiday logic is NOT implemented) the
    *offpeak_profile* is applied (default: ``benchmark_max_speed``).

    Returns the dict of env-vars that were actually applied.
    """
    chosen = peak_profile if is_market_hours(now) else offpeak_profile
    applied = apply_profile(chosen, overwrite=overwrite)
    # Tag which profile was chosen so callers can log it.
    applied["_applied_profile"] = chosen
    return applied


__all__ = [
    "PROFILE_PRESETS",
    "list_profiles",
    "get_profile",
    "apply_profile",
    "is_market_hours",
    "apply_profile_for_current_time",
]
