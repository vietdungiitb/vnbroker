"""Unit tests for performance profile presets."""

import datetime

from vnstock.core.performance_profiles import (
    apply_profile,
    apply_profile_for_current_time,
    get_profile,
    is_market_hours,
    list_profiles,
)


def test_list_profiles_contains_defaults():
    profiles = list_profiles()
    assert "benchmark_max_speed" in profiles
    assert "production_stable" in profiles
    assert "market_hours" in profiles


def test_get_profile_returns_env_mapping():
    profile = get_profile("production_stable")
    assert isinstance(profile, dict)
    assert profile["VNSTOCK_TRADING_AUTO_PRIMARY"] == "kbs"
    assert profile["VNSTOCK_VCI_ADAPTIVE_CONCURRENCY"] == "1"


def test_apply_profile_sets_environment(monkeypatch):
    monkeypatch.delenv("VNSTOCK_VCI_ADAPTIVE_STEP_UP", raising=False)
    applied = apply_profile("benchmark_max_speed", overwrite=True)
    assert applied["VNSTOCK_VCI_ADAPTIVE_STEP_UP"] == "3"


# ---- is_market_hours tests ----

_ICT = datetime.timezone(datetime.timedelta(hours=7))


def _ict(weekday: int, hour: int, minute: int = 0) -> datetime.datetime:
    """Build a datetime fixed on *weekday* (0=Mon) at the given time in ICT."""
    # 2026-03-30 is a Monday
    base = datetime.datetime(2026, 3, 30, tzinfo=_ICT)
    return base + datetime.timedelta(days=weekday, hours=hour, minutes=minute)


def test_is_market_hours_morning_session():
    assert is_market_hours(_ict(0, 10, 0)) is True   # Mon 10:00 ICT


def test_is_market_hours_afternoon_session():
    assert is_market_hours(_ict(2, 14, 0)) is True   # Wed 14:00 ICT


def test_is_market_hours_lunch_break():
    assert is_market_hours(_ict(1, 12, 0)) is False  # Tue 12:00 — lunch break


def test_is_market_hours_evening():
    assert is_market_hours(_ict(3, 18, 0)) is False  # Thu 18:00 — after close


def test_is_market_hours_weekend():
    assert is_market_hours(_ict(5, 10, 0)) is False  # Sat 10:00 — weekend


def test_apply_profile_for_current_time_peak(monkeypatch):
    peak_time = _ict(0, 9, 30)  # Mon morning open
    result = apply_profile_for_current_time(
        peak_profile="market_hours",
        offpeak_profile="benchmark_max_speed",
        overwrite=True,
        now=peak_time,
    )
    assert result["_applied_profile"] == "market_hours"
    assert result.get("VNSTOCK_VCI_ADAPTIVE_START_CONCURRENCY") == "4"


def test_apply_profile_for_current_time_offpeak(monkeypatch):
    offpeak_time = _ict(5, 22, 0)  # Saturday evening
    result = apply_profile_for_current_time(
        peak_profile="market_hours",
        offpeak_profile="benchmark_max_speed",
        overwrite=True,
        now=offpeak_time,
    )
    assert result["_applied_profile"] == "benchmark_max_speed"
    assert result.get("VNSTOCK_VCI_ADAPTIVE_START_CONCURRENCY") == "10"
