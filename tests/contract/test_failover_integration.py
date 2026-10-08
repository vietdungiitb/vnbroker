"""Integration tests for failover and bulk normalization.

Tests that _auto_sources is properly set in production code and that
bulk history results are normalized through the Normalizer.
"""

from __future__ import annotations

import pandas as pd
import pytest

from vnbroker.common.data import Quote
from vnbroker.core import source_router
from vnbroker.core.utils.normalizer import Normalizer

CANONICAL_TZ = "Asia/Ho_Chi_Minh"


@pytest.fixture(autouse=True)
def _clean_router_state():
    """Ensure clean health state for test isolation."""
    source_router.reset_router_state()
    yield
    source_router.reset_router_state()


def _frame(*, naive: bool, times: list[str]) -> pd.DataFrame:
    idx = pd.to_datetime(times)
    if not naive:
        idx = idx.tz_localize(CANONICAL_TZ)
    return pd.DataFrame(
        {
            "time": idx,
            "open": [1.0] * len(times),
            "high": [1.0] * len(times),
            "low": [1.0] * len(times),
            "close": [1.0] * len(times),
            "volume": [1] * len(times),
        }
    )


class _FailingSource:
    """Provider that always raises a network error."""

    symbol = "ACB"

    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.calls = 0

    def history(self, **kw):
        self.calls += 1
        raise self.exc


class _WorkingSource:
    """Provider that returns valid data."""

    symbol = "ACB"

    def __init__(self, *, naive: bool = False) -> None:
        self.naive = naive
        self.calls = 0

    def history(self, **kw):
        self.calls += 1
        return _frame(naive=self.naive, times=["2024-01-02", "2024-01-03"])


def _make_quote(sources: dict[str, object], *, order: list[str] | None = None) -> Quote:
    """Build Quote with real failover logic, only providers are faked."""
    q = Quote("ACB", "AUTO")
    q._auto_sources = sources  # type: ignore[attr-defined]
    if order is not None:
        def _fixed_order(module_name: str, symbol: str | None = None) -> list[str]:
            return [s for s in order if s in sources]
        q._fixed_source_order = _fixed_order  # type: ignore[attr-defined]
    return q


# ------------------------------------------------------------------ failover


def test_auto_source_has_auto_sources():
    """Quote('ACB', 'AUTO') must have _auto_sources attribute populated."""
    q = Quote("ACB", "AUTO")
    assert hasattr(q, "_auto_sources"), "Quote with AUTO source must have _auto_sources"
    assert isinstance(q._auto_sources, dict), "_auto_sources must be a dict"
    assert len(q._auto_sources) > 0, "_auto_sources must not be empty"
    # Should contain at least vci and kbs
    source_names = {s.lower() for s in q._auto_sources.keys()}
    assert "vci" in source_names or "kbs" in source_names, (
        f"Expected vci or kbs in auto sources, got: {source_names}"
    )


def test_failover_on_429():
    """Mock VCI to raise 429, verify KBS serves the request."""
    vci = _FailingSource(ConnectionError("429 rate limit"))
    kbs = _WorkingSource(naive=False)

    q = _make_quote({"vci": vci, "kbs": kbs}, order=["vci", "kbs"])
    df = q.history(start="2024-01-01", end="2024-01-31")

    assert vci.calls > 0, "VCI should have been tried"
    assert kbs.calls >= 1, "KBS should have served after VCI failed"
    assert isinstance(df, pd.DataFrame)
    assert "time" in df.columns
    assert df["time"].dt.tz is not None


def test_bulk_normalization():
    """Bulk history returns tz-aware DataFrames."""
    # Simulate bulk result: list of DataFrames (some naive, some aware)
    naive_df = _frame(naive=True, times=["2024-01-02", "2024-01-03"])
    aware_df = _frame(naive=False, times=["2024-01-04", "2024-01-05"])

    result = Normalizer.normalize_history([naive_df, aware_df], "2024-01-01", "2024-01-31")

    assert isinstance(result, list)
    assert len(result) == 2
    for df in result:
        assert isinstance(df, pd.DataFrame)
        assert df["time"].dt.tz is not None, "All bulk results must be tz-aware"
        assert str(df["time"].dt.tz) == CANONICAL_TZ


def test_bulk_has_manifest():
    """Bulk result includes symbol information via attrs."""
    df = _frame(naive=True, times=["2024-01-02"])
    df.attrs["symbol"] = "ACB"

    result = Normalizer.normalize_history([df], "2024-01-01", "2024-01-31")

    assert isinstance(result, list)
    assert len(result) == 1
    # Normalizer preserves attrs
    assert result[0].attrs.get("symbol") == "ACB"
