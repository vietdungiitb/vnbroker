"""ISSUE-03: circuit-breaker persistent (fail → cooldown → half-open → recover)."""

from __future__ import annotations

import time

import pytest

from vnbroker.core import source_router


@pytest.fixture(autouse=True)
def _clean_router(monkeypatch):
    monkeypatch.setenv("vnbroker_ROUTER_HEALTH_DB", "memory")
    source_router.reload_store()
    source_router.reset_router_state()
    yield
    source_router.reset_router_state()
    source_router.reload_store()


def _expire_cooldown(module: str, source: str) -> None:
    state = source_router._health_state[(module, source)]
    state["cooldown_until"] = time.monotonic() - 1.0


def test_fail_cooldown_halfopen_recover():
    source_router.record_failure("quote", "vci")

    snap = source_router.get_source_health_snapshot("quote")
    assert snap["VCI"]["failures"] == 1
    assert snap["VCI"]["in_cooldown"] is True
    assert snap["VCI"]["half_open"] is False

    # Cooldown expires → half-open probe goes first
    _expire_cooldown("quote", "vci")
    snap2 = source_router.health("quote")
    assert snap2["VCI"]["in_cooldown"] is False
    assert snap2["VCI"]["half_open"] is True
    assert source_router.is_half_open("quote", "vci") is True
    order = source_router.build_source_order("quote", symbol="ACB")
    assert order[0] == "vci"

    # Probe succeeds → circuit closes
    source_router.record_success("quote", "vci")
    snap3 = source_router.get_source_health_snapshot("quote")
    assert snap3["VCI"]["failures"] == 0
    assert snap3["VCI"]["half_open"] is False


def test_halfopen_probe_failure_reopens_with_backoff():
    source_router.record_failure("quote", "vci")
    first_remaining = source_router.get_source_health_snapshot("quote")["VCI"][
        "cooldown_remaining_sec"
    ]
    _expire_cooldown("quote", "vci")
    assert source_router.is_half_open("quote", "vci") is True

    source_router.record_failure("quote", "vci")  # probe fails
    snap = source_router.get_source_health_snapshot("quote")
    assert snap["VCI"]["failures"] == 2
    assert snap["VCI"]["in_cooldown"] is True
    assert snap["VCI"]["half_open"] is False
    # Exponential backoff: 2nd failure cools down longer than the 1st
    assert snap["VCI"]["cooldown_remaining_sec"] > first_remaining


def test_state_survives_restart_with_sqlite(tmp_path, monkeypatch):
    db = str(tmp_path / "router_health.sqlite3")
    monkeypatch.setenv("vnbroker_ROUTER_HEALTH_DB", db)
    source_router.reload_store()

    source_router.record_failure("trading", "kbs")
    assert source_router.get_source_health_snapshot("trading")["KBS"]["failures"] == 1

    # Simulate process restart: drop memory + store singleton, reload from disk
    source_router._health_state.clear()
    source_router.reload_store()

    snap = source_router.get_source_health_snapshot("trading")
    assert snap["KBS"]["failures"] == 1
    assert snap["KBS"]["in_cooldown"] is True
    assert snap["KBS"]["cooldown_remaining_sec"] > 0
