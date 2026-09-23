"""Unit tests for SSIQuote.history (mock service, no network)."""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
import pytest

from vnbroker.explorer.ssi.quote import SSIQuote

_TODAY = date.today()


def _candle(symbol: str, trading_date: str, o: float, h: float, lo: float, c: float, v: int) -> Dict[str, Any]:
    return {
        "symbol": symbol,
        "trading_date": trading_date,
        "open": float(o),
        "high": float(h),
        "low": float(lo),
        "close": float(c),
        "volume": v,
        "value": float(c * v),
    }


def _service_df(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(
        rows,
        columns=["symbol", "trading_date", "open", "high", "low", "close", "volume", "value"],
    )
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").astype("Int64")
    for col in ("open", "high", "low", "close", "value"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    return df


class _FakeMarket:
    """SSIMarketService double recording get_ohlc calls."""

    def __init__(self, pages: Optional[Dict[int, List[Dict[str, Any]]]] = None) -> None:
        self.pages = pages or {}
        self.calls: List[Dict[str, Any]] = []

    def get_ohlc(
        self,
        symbol: str,
        timeframe: str = "1d",
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page: int = 1,
        size: int = 1000,
        raw: bool = False,
    ) -> pd.DataFrame:
        self.calls.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "from_date": from_date,
                "to_date": to_date,
                "page": page,
                "size": size,
            }
        )
        return _service_df(self.pages.get(page, []))


def _quote(rows: List[Dict[str, Any]], **kwargs: Any) -> tuple[SSIQuote, _FakeMarket]:
    fake = _FakeMarket(pages={1: rows})
    q = SSIQuote("acb", api_key="test-ssi-key", api_secret="test-ssi-secret", _service=fake, **kwargs)  # type: ignore[arg-type]
    return q, fake


class TestSSIQuoteInit:
    """Init/credential tests."""

    def test_raises_without_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("VNBROKER_BROKER_SSI_API_KEY", raising=False)
        monkeypatch.delenv("VNBROKER_BROKER_SSI_API_SECRET", raising=False)
        with pytest.raises(ValueError, match="SSI cần api_key và api_secret"):
            SSIQuote("ACB")

    def test_symbol_uppercase(self, ssi_keys: tuple[str, str]) -> None:
        fake = _FakeMarket()
        q = SSIQuote("acb", _service=fake)  # type: ignore[arg-type]
        assert q.symbol == "ACB"


class TestSSIQuoteHistory:
    """AC-Q1.1-Q1.5."""

    _ROWS = [
        _candle("ACB", "2024-01-03", 25.3, 25.5, 25.1, 25.4, 1000),
        _candle("ACB", "2024-01-02", 25.0, 25.4, 24.9, 25.2, 2000),
        _candle("ACB", "2024-01-01", 24.8, 25.1, 24.7, 25.0, 3000),
    ]

    def test_schema_sorted_dtypes_attrs(self) -> None:
        q, _ = _quote(self._ROWS)
        df = q.history(start="2024-01-01", end="2024-01-31")
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["time", "open", "high", "low", "close", "volume"]
        assert str(df["time"].dtype).startswith("datetime64")
        assert str(df["volume"].dtype) in ("int64", "Int64")
        assert df["time"].is_monotonic_increasing
        assert df.attrs["source"] == "SSI"
        assert df.attrs["source_used"] == "SSI"
        assert df.attrs["symbol"] == "ACB"

    def test_interval_mapping(self) -> None:
        q, fake = _quote(self._ROWS)
        q.history(start="2024-01-01", end="2024-01-31", interval="1D")
        assert fake.calls[-1]["timeframe"] == "1d"
        q.history(start="2024-01-01", end="2024-01-31", interval="3m")
        assert fake.calls[-1]["timeframe"] == "3m"

    def test_interval_30m_supported(self) -> None:
        # W1: 30m is a native SSI timeframe — must reach the service.
        q, fake = _quote(self._ROWS)
        q.history(start="2024-01-01", end="2024-01-31", interval="30m")
        assert fake.calls[-1]["timeframe"] == "30m"
    def test_invalid_interval_prevalidated(self) -> None:
        """No BrokerValidationError may escape: validate in explorer (AC-Q1.2)."""
        q, fake = _quote(self._ROWS)
        with pytest.raises(ValueError, match="interval"):
            q.history(start="2024-01-01", end="2024-01-31", interval="X")
        assert fake.calls == []

    def test_bad_date_prevalidated(self) -> None:
        q, fake = _quote(self._ROWS)
        with pytest.raises(ValueError, match="[Dd]ate|YYYY-MM-DD"):
            q.history(start="01-01-2024", end="2024-01-31")
        assert fake.calls == []

    def test_default_lookback_365_days(self) -> None:
        q, fake = _quote(self._ROWS)
        q.history()
        expected = (_TODAY - timedelta(days=365)).strftime("%Y/%m/%d")
        assert fake.calls[0]["from_date"] == expected

    def test_get_all_pagination_stop_rule(self) -> None:
        """Page 1 full (1000 rows) + page 2 partial → stop after page 2 (AC-Q1.4)."""
        page1 = [
            _candle("ACB", "2024-01-01", 25.0, 25.1, 24.9, 25.0, 100 + i)
            for i in range(1000)
        ]
        page2 = self._ROWS
        fake = _FakeMarket(pages={1: page1, 2: page2})
        q = SSIQuote("ACB", api_key="k", api_secret="s", _service=fake)  # type: ignore[arg-type]
        df = q.history(start="2024-01-01", end="2024-12-31", get_all=True)
        assert len(df) == 1003
        assert [c["page"] for c in fake.calls] == [1, 2]
        assert "value" in df.columns

    def test_get_all_stops_on_empty_page(self) -> None:
        page1 = [
            _candle("ACB", "2024-01-01", 25.0, 25.1, 24.9, 25.0, 100 + i)
            for i in range(1000)
        ]
        fake = _FakeMarket(pages={1: page1, 2: []})
        q = SSIQuote("ACB", api_key="k", api_secret="s", _service=fake)  # type: ignore[arg-type]
        df = q.history(start="2024-01-01", end="2024-12-31", get_all=True)
        assert len(df) == 1000
        assert [c["page"] for c in fake.calls] == [1, 2]

    def test_single_page_by_default(self) -> None:
        q, fake = _quote(self._ROWS)
        q.history(start="2024-01-01", end="2024-01-31")
        assert len(fake.calls) == 1

    def test_empty_returns_empty_typed_frame(self) -> None:
        q, _ = _quote([])
        df = q.history(start="2024-01-01", end="2024-01-31")
        assert isinstance(df, pd.DataFrame) and df.empty
        assert list(df.columns) == ["time", "open", "high", "low", "close", "volume"]

    def test_to_df_false_returns_json_str(self) -> None:
        q, _ = _quote(self._ROWS)
        out = q.history(start="2024-01-01", end="2024-01-31", to_df=False)
        assert isinstance(out, str)
        assert len(json.loads(out)) == 3

    def test_count_back_tail(self) -> None:
        q, _ = _quote(self._ROWS)
        df = q.history(start="2024-01-01", end="2024-01-31", count_back=2)
        assert len(df) == 2


class TestSSIQuoteUnsupported:
    """AC-Q2.1."""

    def test_intraday_message(self, ssi_keys: tuple[str, str]) -> None:
        q = SSIQuote("ACB", _service=_FakeMarket())  # type: ignore[arg-type]
        with pytest.raises(NotImplementedError) as exc:
            q.intraday()
        for token in ("KBS", "VCI", "stream"):
            assert token in str(exc.value)

    def test_price_depth_message(self, ssi_keys: tuple[str, str]) -> None:
        q = SSIQuote("ACB", _service=_FakeMarket())  # type: ignore[arg-type]
        with pytest.raises(NotImplementedError) as exc:
            q.price_depth()
        for token in ("KBS", "VCI", "stream"):
            assert token in str(exc.value)


class TestSSIQuoteFetchMultiple:
    """P4b: batch history isolates per-symbol failures, preserves order."""

    def test_batch_order_and_keys(self) -> None:
        rows = [
            {"symbol": "X", "trading_date": "2024-01-02", "open": 1.0,
             "high": 1.0, "low": 1.0, "close": 1.0, "volume": 10, "value": 10.0}
        ]
        q = SSIQuote("ACB", api_key="test-ssi-key", api_secret="test-ssi-secret",
                     _service=_FakeMarket(pages={1: rows}))  # type: ignore[arg-type]
        out = q.fetch_multiple(["ACB", "VNM"], start="2024-01-02", end="2024-01-03")
        assert list(out.keys()) == ["ACB", "VNM"]
        assert len(out["ACB"]) == 1

    def test_empty_list(self) -> None:
        q, _ = _quote([])
        assert q.fetch_multiple([]) == {}

    def test_failure_isolated(self) -> None:
        class _Boom:
            def get_ohlc(self, **kwargs: Any) -> Any:
                if kwargs.get("symbol") == "BAD":
                    raise ConnectionError("boom")
                return _service_df([
                    {"symbol": kwargs.get("symbol"), "trading_date": "2024-01-02",
                     "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
                     "volume": 10, "value": 10.0}
                ])

        q = SSIQuote("ACB", api_key="test-ssi-key", api_secret="test-ssi-secret",
                     _service=_Boom())  # type: ignore[arg-type]
        out = q.fetch_multiple(["ACB", "BAD"], start="2024-01-02", end="2024-01-03")
        assert len(out["ACB"]) == 1
        assert out["BAD"].empty
        assert out["BAD"].attrs["error"] == "boom"
