"""Unit tests for KBS adaptive worker control — now backed by AdaptiveController."""

from vnbroker.core.adaptive_controller import AdaptiveController


def test_adjust_worker_count_increase_on_clean_low_latency():
    next_value = AdaptiveController.compute(
        current=6,
        batch_size=6,
        success_count=6,
        max_concurrency=16,
        min_concurrency=2,
        step_up=2,
        step_down=3,
        fail_threshold=0.2,
        batch_p95_seconds=0.3,
        p95_high_seconds=1.5,
        p95_low_seconds=0.5,
    )
    assert next_value == 8


def test_adjust_worker_count_decrease_on_high_fail_ratio():
    next_value = AdaptiveController.compute(
        current=10,
        batch_size=10,
        success_count=7,
        max_concurrency=16,
        min_concurrency=2,
        step_up=2,
        step_down=3,
        fail_threshold=0.2,
        batch_p95_seconds=0.4,
        p95_high_seconds=1.5,
        p95_low_seconds=0.5,
    )
    assert next_value == 7


def test_adjust_worker_count_decrease_on_high_latency():
    next_value = AdaptiveController.compute(
        current=10,
        batch_size=10,
        success_count=10,
        max_concurrency=16,
        min_concurrency=2,
        step_up=2,
        step_down=3,
        fail_threshold=0.2,
        batch_p95_seconds=1.8,
        p95_high_seconds=1.5,
        p95_low_seconds=0.5,
    )
    assert next_value == 7
