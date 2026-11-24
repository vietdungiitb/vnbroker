"""P1/R1-R7: Vnbroker.daily_bars, bulk_year, coverage gate, reconcile_prices."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from vnbroker import Vnbroker
from vnbroker.reference import CafefReference
from vnbroker.reference import client as cafef_client
from vnbroker.reference.parser import REFERENCE_COLUMNS

pytestmark = pytest.mark.unit

GOLDEN = {
    "time": pd.Timestamp("2022-01-04", tz="Asia/Ho_Chi_Minh"),
    "open": 41500.0, "high": 43250.0, "low": 41300.0,
    "close": 42750.0, "close_raw": 42750.0, "close_adjusted": 17940.0,
    "volume": 11034900, "value": 467_260_000_000,
    "put_through_volume": 0, "put_through_value": 0.0,
    "source": "cafef", "fetched_at": "2026-11-24T00:00:00+00:00",
}


def _frame(rows: list[dict[str, Any]] | None = None) -> pd.DataFrame:
    data = rows if rows is not None else [dict(GOLDEN)]
    return pd.DataFrame(data, columns=REFERENCE_COLUMNS)


@pytest.fixture
def mock_history(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    calls: dict[str, Any] = {"n": 0, "args": None}

    def fake(self: Any, symbol: str, start: Any = None, end: Any = None, **kwargs: Any) -> pd.DataFrame:
        calls["n"] += 1
        calls["args"] = (symbol, start, end)
        return _frame()

    monkeypatch.setattr(CafefReference, "history", fake)
    return calls


class TestDailyBars:
    def test_facade_returns_canonical_both(self, mock_history: dict[str, Any]) -> None:
        df = Vnbroker().daily_bars("TPB", "2022-01-01", "2022-01-06", basis="both")
        assert mock_history["n"] == 1
        assert df.iloc[0]["close_raw"] == 42750.0
        assert df.iloc[0]["close_adjusted"] == 17940.0
        assert df.iloc[0]["value"] == 467_260_000_000
        assert df.iloc[0]["source"] == "cafef"
        assert df.iloc[0]["price_basis"] == "both"
        assert str(df.iloc[0]["time"].tz) == "Asia/Ho_Chi_Minh"
        # Bài học nến 1970: assert NGÀY, không chỉ giá.
        assert df.iloc[0]["time"].strftime("%Y-%m-%d") == "2022-01-04"

    def test_basis_raw_and_adjusted_share_one_path(self, mock_history: dict[str, Any]) -> None:
        raw = Vnbroker().daily_bars("TPB", "2022-01-01", "2022-01-06", basis="raw")
        adj = Vnbroker().daily_bars("TPB", "2022-01-01", "2022-01-06", basis="adjusted")
        assert mock_history["n"] == 2
        assert "close_raw" in raw.columns and "close_adjusted" not in raw.columns
        assert "close_adjusted" in adj.columns and "close_raw" not in adj.columns
        assert raw.iloc[0]["price_basis"] == "raw"
        assert adj.iloc[0]["price_basis"] == "adjusted"

    def test_coverage_missing_not_empty_silence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def empty(self: Any, symbol: str, start: Any = None, end: Any = None, **kwargs: Any) -> pd.DataFrame:
            return _frame([])

        def no_tpb(exchange: str, year: int, show_log: bool = False) -> list[dict[str, Any]]:
            return [{"symbol": "VIC", "date": "2011-01-04"}]

        monkeypatch.setattr(CafefReference, "history", empty)
        monkeypatch.setattr("vnbroker.reference.cafef.fetch_bulk_year", no_tpb)
        df = Vnbroker().daily_bars("TPB", "2011-01-01", "2011-12-31")
        assert len(df) == 0
        assert df.attrs["coverage"] == "missing"
        assert "coverage" in df.columns

    def test_coverage_no_trading_days_distinguished(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def empty(self: Any, symbol: str, start: Any = None, end: Any = None, **kwargs: Any) -> pd.DataFrame:
            return _frame([])

        def has_tpb(exchange: str, year: int, show_log: bool = False) -> list[dict[str, Any]]:
            return [{"symbol": "TPB", "date": "2022-01-04"}]

        monkeypatch.setattr(CafefReference, "history", empty)
        monkeypatch.setattr("vnbroker.reference.cafef.fetch_bulk_year", has_tpb)
        df = Vnbroker().daily_bars("TPB", "2022-01-01", "2022-01-06")
        assert len(df) == 0
        assert df.attrs["coverage"] == "no_trading_days"

    def test_default_start_is_2011(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: dict[str, Any] = {}

        def spy(self: Any, symbol: str, start: Any = None, end: Any = None, **kwargs: Any) -> pd.DataFrame:
            seen["start"] = start
            return _frame()

        monkeypatch.setattr(CafefReference, "history", spy)
        Vnbroker().daily_bars("VIC", end="2022-01-06")
        assert seen["start"] == "2011-01-01"

    def test_invalid_basis_raises(self) -> None:
        with pytest.raises(ValueError, match="basis"):
            Vnbroker().daily_bars("TPB", "2022-01-01", "2022-01-06", basis="nope")


class TestBulkYear:
    def test_bulk_year_all_uses_one_xlsx_call_and_cache(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = {"n": 0, "sleep": 0}

        def fake_get(*args: Any, **kwargs: Any) -> Any:
            calls["n"] += 1
            assert kwargs["params"]["Symbol"] == "ALL"
            class R:
                content = _XLSX_ALL_BYTES
                status_code = 200
                headers: dict[str, str] = {}
                def raise_for_status(self) -> None: pass
            return R()

        monkeypatch.setattr(cafef_client.requests, "get", fake_get)
        monkeypatch.setattr(cafef_client.time, "sleep", lambda _s: calls.__setitem__("sleep", calls["sleep"] + 1))

        ref = CafefReference()
        first = ref.bulk_year("HOSE", 2022)
        cached = ref.bulk_year("HOSE", 2022)

        # Cache is on raw records; parse_records builds a fresh frame each call.
        pd.testing.assert_frame_equal(cached.drop(columns=["fetched_at"]), first.drop(columns=["fetched_at"]))
        assert calls["n"] == 1  # only one network request thanks to cache
        assert "symbol" in first.columns
        assert len(first) == 1
        assert first.iloc[0]["close_raw"] == 42750.0

    def test_reconcile_prices_accepts_real_provider_frame(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        provider = pd.DataFrame({
            "time": [pd.Timestamp("2022-01-04", tz="Asia/Ho_Chi_Minh")],
            "close": [16783.0],
        })
        monkeypatch.setattr(CafefReference, "history", lambda self, *a, **kw: _frame())
        report = Vnbroker().reconcile_prices(provider, symbol="TPB", start="2022-01-01", end="2022-01-06")
        assert report.verdict in {"adjusted_confirmed", "rebase_suspected", "double_adjust_suspected"}
        assert abs(report.ratio_mean - 16783.0 / 17940.0) < 1e-6


_XLSX_ALL_BYTES = None


def _make_all_bytes() -> bytes:
    import io
    frame = pd.DataFrame([{
        "Mã": "TPB", "Ngày": "04/01/2022",
        "Giá mở cửa": 41.5, "Giá cao nhất": 43.25, "Giá thấp nhất": 41.3,
        "Giá đóng cửa": 42.75, "Giá điều chỉnh": 17.94,
        "Khối lượng khớp lệnh": 11034900, "Giá trị khớp lệnh": 467.26,
        "Khối lượng thỏa thuận": 0, "Giá trị thỏa thuận": 0.0,
        "Thay đổi": "",
    }])
    buf = io.BytesIO()
    frame.to_excel(buf, index=False)
    return buf.getvalue()


_XLSX_ALL_BYTES = _make_all_bytes()
