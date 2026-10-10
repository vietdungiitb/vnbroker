"""Shared fixtures for SSI explorer unit tests (mock-only, no network, no real keys)."""

from __future__ import annotations

import pytest


@pytest.fixture()
def ssi_keys(monkeypatch: pytest.MonkeyPatch) -> tuple[str, str]:
    """Fake SSI credentials via env (never real secrets in tests)."""
    monkeypatch.setenv("VNBROKER_BROKER_SSI_API_KEY", "test-ssi-key")
    monkeypatch.setenv("VNBROKER_BROKER_SSI_API_SECRET", "test-ssi-secret")
    return ("test-ssi-key", "test-ssi-secret")


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear TTL cache before each test to prevent cache pollution."""
    from vnbroker.core.utils.cache import get_listing_cache, get_industry_cache
    get_listing_cache().clear()
    get_industry_cache().clear()
    yield
    get_listing_cache().clear()
    get_industry_cache().clear()
