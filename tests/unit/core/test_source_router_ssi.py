"""Unit tests for SSI-aware AUTO routing + persist debounce (no network)."""

from __future__ import annotations

import pytest

from vnbroker.core import source_router


def _no_ssi_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VNBROKER_BROKER_SSI_API_KEY", raising=False)
    monkeypatch.delenv("VNBROKER_BROKER_SSI_API_SECRET", raising=False)


def _with_ssi_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VNBROKER_BROKER_SSI_API_KEY", "test-key")
    monkeypatch.setenv("VNBROKER_BROKER_SSI_API_SECRET", "test-secret")
    monkeypatch.delenv("vnbroker_SSI_AUTO_PRIMARY", raising=False)


class _FakeStore:
    """Counting HealthStore double."""

    def __init__(self, saves: list) -> None:
        self._saves = saves

    def save(self, state: dict) -> None:
        self._saves.append(dict(state))

    def load(self) -> dict:
        return {}

    def clear(self) -> None:
        pass


@pytest.mark.unit
class TestSSIAutoCandidates:
    def setup_method(self) -> None:
        source_router.reset_router_state()

    def teardown_method(self) -> None:
        source_router.reset_router_state()

    def test_no_ssi_without_credentials(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _no_ssi_keys(monkeypatch)
        assert source_router.get_auto_candidates("quote") == ["vci", "kbs"]
        assert "ssi" not in source_router.get_auto_candidates("trading")

    def test_ssi_appended_as_failover(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _with_ssi_keys(monkeypatch)
        assert source_router.get_auto_candidates("quote") == ["vci", "kbs", "ssi"]
        assert source_router.get_auto_candidates("listing")[-1] == "ssi"

    def test_ssi_excluded_from_empty_modules(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _with_ssi_keys(monkeypatch)
        assert "ssi" not in source_router.get_auto_candidates("company")
        assert "ssi" not in source_router.get_auto_candidates("financial")
        assert "ssi" not in source_router.get_auto_candidates("news")

    def test_ssi_last_in_build_order_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _with_ssi_keys(monkeypatch)
        order = source_router.build_source_order("quote", symbol="ACB")
        assert order[-1] == "ssi"
        assert order[0] == "vci"

    def test_ssi_opt_in_primary(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _with_ssi_keys(monkeypatch)
        monkeypatch.setenv("vnbroker_SSI_AUTO_PRIMARY", "1")
        order = source_router.build_source_order("quote", symbol="ACB")
        assert order[0] == "ssi"


@pytest.mark.unit
class TestPersistDebounce:
    def setup_method(self) -> None:
        source_router.reset_router_state()

    def teardown_method(self) -> None:
        source_router.reset_router_state()

    def test_rapid_records_coalesce_saves(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        saves: list = []
        monkeypatch.setattr(source_router, "_get_store", lambda: _FakeStore(saves))
        for _ in range(5):
            source_router.record_failure("quote", "vci")
        assert len(saves) <= 1

    def test_every_n_forces_flush(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        saves: list = []
        monkeypatch.setattr(source_router, "_get_store", lambda: _FakeStore(saves))
        for _ in range(source_router._PERSIST_EVERY_N):
            source_router.record_failure("quote", "vci")
        assert len(saves) >= 1

    def test_force_flush_persists_pending(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        saves: list = []
        monkeypatch.setattr(source_router, "_get_store", lambda: _FakeStore(saves))
        source_router.record_failure("quote", "vci")
        source_router.flush_router_state()
        assert len(saves) >= 1
