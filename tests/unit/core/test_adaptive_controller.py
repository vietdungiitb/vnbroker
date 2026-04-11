"""Unit tests for the shared AdaptiveController and GlobalPressure."""

import os

import pytest

from vnstock.core.adaptive_controller import (
    AdaptiveController,
    GlobalPressure,
    _env_bool,
    _env_float,
    _env_int,
    get_global_pressure,
)


# ---------------------------------------------------------------------------
# AdaptiveController.compute (stateless)
# ---------------------------------------------------------------------------

class TestAdaptiveControllerCompute:
    def _call(self, **kwargs):
        defaults = dict(
            current=8,
            batch_size=8,
            success_count=8,
            max_concurrency=24,
            min_concurrency=2,
            step_up=2,
            step_down=3,
            fail_threshold=0.2,
            batch_p95_seconds=0.2,
            p95_high_seconds=1.2,
            p95_low_seconds=0.35,
        )
        defaults.update(kwargs)
        return AdaptiveController.compute(**defaults)

    def test_ramps_up_on_clean_low_latency(self):
        assert self._call() == 10  # 8 + step_up=2

    def test_stays_when_latency_mid_range(self):
        assert self._call(batch_p95_seconds=0.7) == 8

    def test_decreases_on_high_fail_ratio(self):
        assert self._call(success_count=5) == 5  # 8 - step_down=3

    def test_decreases_on_high_latency(self):
        assert self._call(batch_p95_seconds=1.5) == 5

    def test_clamps_at_max(self):
        assert self._call(current=24, max_concurrency=24) == 24

    def test_clamps_at_min(self):
        result = self._call(current=2, success_count=0, batch_p95_seconds=2.0, min_concurrency=2)
        assert result == 2

    def test_zero_batch_returns_current(self):
        assert self._call(batch_size=0) == 8

    def test_max_workers_alias(self):
        """max_workers / min_workers aliases must be honoured."""
        result = AdaptiveController.compute(
            current=10,
            batch_size=10,
            success_count=10,
            max_concurrency=1,   # would cap at 1 without alias
            min_concurrency=1,
            max_workers=20,      # alias overrides
            min_workers=2,
            step_up=2,
            step_down=3,
            fail_threshold=0.2,
            batch_p95_seconds=0.1,
            p95_high_seconds=1.2,
            p95_low_seconds=0.35,
        )
        assert result == 12  # 10 + 2, capped at max_workers=20


# ---------------------------------------------------------------------------
# AdaptiveController stateful (.adjust)
# ---------------------------------------------------------------------------

class TestAdaptiveControllerStateful:
    def _ctrl(self, **kwargs):
        defaults = dict(
            start=8, min_workers=2, max_workers=24,
            step_up=2, step_down=3,
            p95_low_seconds=0.35, p95_high_seconds=1.2, fail_threshold=0.2,
        )
        defaults.update(kwargs)
        return AdaptiveController(**defaults)

    def test_adjust_ramps_up(self):
        ctrl = self._ctrl()
        new = ctrl.adjust(batch_size=8, success_count=8, batch_p95_seconds=0.2)
        assert new == 10
        assert ctrl.current == 10

    def test_adjust_backs_off_on_errors(self):
        ctrl = self._ctrl()
        new = ctrl.adjust(batch_size=8, success_count=4, batch_p95_seconds=0.5)
        assert new == 5
        assert ctrl.current == 5

    def test_adjust_respects_cap_max(self):
        ctrl = self._ctrl(start=12)
        new = ctrl.adjust(batch_size=8, success_count=8, batch_p95_seconds=0.2, cap_max=10)
        assert new <= 10

    def test_cap_to(self):
        ctrl = self._ctrl(start=20)
        capped = ctrl.cap_to(10)
        assert capped == 10
        assert ctrl.current == 10


# ---------------------------------------------------------------------------
# AdaptiveController.from_env
# ---------------------------------------------------------------------------

def test_from_env_reads_environment(monkeypatch):
    monkeypatch.setenv("TST_START_CONCURRENCY", "12")
    monkeypatch.setenv("TST_MIN_CONCURRENCY", "3")
    monkeypatch.setenv("TST_MAX_CONCURRENCY", "20")
    monkeypatch.setenv("TST_STEP_UP", "4")
    monkeypatch.setenv("TST_STEP_DOWN", "5")
    ctrl = AdaptiveController.from_env("TST_")
    assert ctrl.current == 12
    assert ctrl.min_workers == 3
    assert ctrl.max_workers == 20
    assert ctrl.step_up == 4
    assert ctrl.step_down == 5


# ---------------------------------------------------------------------------
# GlobalPressure
# ---------------------------------------------------------------------------

class TestGlobalPressure:
    def _fresh(self, threshold=0.3, decay_windows=3):
        return GlobalPressure(threshold=threshold, decay_windows=decay_windows)

    def test_not_stressed_on_clean_batch(self):
        gp = self._fresh()
        gp.record_batch(10, 0)
        assert gp.stressed is False
        assert gp.multiplier == 1.0

    def test_stressed_after_high_error_batch(self):
        gp = self._fresh()
        gp.record_batch(10, 5)  # 50% > threshold 30%
        assert gp.stressed is True
        assert gp.multiplier == 0.5

    def test_recovers_after_decay_windows(self):
        gp = self._fresh(decay_windows=2)
        gp.record_batch(10, 5)   # stress
        gp.record_batch(10, 0)   # clean 1
        assert gp.stressed is True  # not yet recovered
        gp.record_batch(10, 0)   # clean 2 → streak == decay
        assert gp.stressed is False

    def test_stress_resets_streak(self):
        gp = self._fresh(decay_windows=2)
        gp.record_batch(10, 5)   # stress
        gp.record_batch(10, 0)   # clean 1
        gp.record_batch(10, 5)   # stress again → streak resets
        gp.record_batch(10, 0)   # clean 1
        assert gp.stressed is True   # need 2 clean in a row

    def test_get_global_pressure_singleton(self):
        gp1 = get_global_pressure()
        gp2 = get_global_pressure()
        assert gp1 is gp2


# ---------------------------------------------------------------------------
# Env helpers
# ---------------------------------------------------------------------------

def test_env_int_default(monkeypatch):
    monkeypatch.delenv("_TST_INT", raising=False)
    assert _env_int("_TST_INT", default=7) == 7


def test_env_int_reads_env(monkeypatch):
    monkeypatch.setenv("_TST_INT", "42")
    assert _env_int("_TST_INT", default=7) == 42


def test_env_float_clamps(monkeypatch):
    monkeypatch.setenv("_TST_FLT", "-0.5")
    assert _env_float("_TST_FLT", default=0.1, min_value=0.0) == 0.0


def test_env_bool_truthy(monkeypatch):
    for truthy in ("1", "true", "yes", "on"):
        monkeypatch.setenv("_TST_BOOL", truthy)
        assert _env_bool("_TST_BOOL") is True


def test_env_bool_falsy(monkeypatch):
    monkeypatch.setenv("_TST_BOOL", "0")
    assert _env_bool("_TST_BOOL") is False
