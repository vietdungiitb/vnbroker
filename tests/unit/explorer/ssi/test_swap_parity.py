"""P0 swap-parity regression tests (W1-W5 audit fixes, mock-only, no network)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
import pytest

from vnbroker.broker.ssi._enums import Timeframe, safe_parse
from vnbroker.broker.ssi.market import _validate_ssi_from_to
from vnbroker.common.data import Company, Listing, Quote, Trading
from vnbroker.core.exceptions import UnsupportedMethodError
from vnbroker.explorer.ssi.company import SSICompany
from vnbroker.explorer.ssi.financial import SSIFinancial
from vnbroker.explorer.ssi.news import SSINews
from vnbroker.explorer.ssi.quote import SSIQuote, _validate_date
from vnbroker.explorer.ssi.trading import SSITrading


def _no_ssi_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VNBROKER_BROKER_SSI_API_KEY", raising=False)
    monkeypatch.delenv("VNBROKER_BROKER_SSI_API_SECRET", raising=False)


class _FakeMarket:
    """get_ohlc double recording calls."""

    def __init__(self, rows: Optional[List[Dict[str, Any]]] = None) -> None:
        self._rows = rows or []
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
            }
        )
        if not self._rows:
            return pd.DataFrame(
                columns=[
                    "symbol",
                    "trading_date",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "value",
                ]
            )
        return pd.DataFrame(self._rows)


def _candle(day: str) -> Dict[str, Any]:
    return {
        "symbol": "ACB",
        "trading_date": day,
        "open": 10.0,
        "high": 11.0,
        "low": 9.0,
        "close": 10.5,
        "volume": 100,
        "value": 1050.0,
    }


class TestW1Interval30m:
    def test_enum_has_30m(self) -> None:
        assert safe_parse(Timeframe, "30m") is Timeframe.MINUTE_30

    def test_resolve_30m_no_raise(self) -> None:
        q = SSIQuote(
            "ACB", api_key="k", api_secret="s", _service=_FakeMarket()  # type: ignore[arg-type]
        )
        assert q._resolve_timeframe("30m") == "30m"

    def test_history_30m_reaches_service(self) -> None:
        fake = _FakeMarket(rows=[_candle("2024-01-02")])
        q = SSIQuote("ACB", api_key="k", api_secret="s", _service=fake)  # type: ignore[arg-type]
        df = q.history(start="2024-01-02", end="2024-01-03", interval="30m")
        assert fake.calls[0]["timeframe"] == "30m"
        assert len(df) == 1


class TestW5DatetimeWindows:
    def test_validate_accepts_datetime(self) -> None:
        assert _validate_date("2024-01-02 09:00:00", "start") == "2024-01-02 09:00:00"
        assert _validate_date("2024-01-02", "start") == "2024-01-02"

    def test_validate_rejects_garbage(self) -> None:
        with pytest.raises(ValueError):
            _validate_date("02/01/2024", "start")

    def test_history_forwards_datetime_wire_format(self) -> None:
        fake = _FakeMarket(rows=[_candle("2024-01-02")])
        q = SSIQuote("ACB", api_key="k", api_secret="s", _service=fake)  # type: ignore[arg-type]
        q.history(
            start="2024-01-02 09:00:00",
            end="2024-01-02 15:00:00",
            interval="15m",
        )
        assert fake.calls[0]["from_date"] == "2024/01/02 09:00:00"
        assert fake.calls[0]["to_date"] == "2024/01/02 15:00:00"

    def test_history_start_after_end_raises(self) -> None:
        q = SSIQuote(
            "ACB", api_key="k", api_secret="s", _service=_FakeMarket()  # type: ignore[arg-type]
        )
        with pytest.raises(ValueError):
            q.history(start="2024-01-03 09:00:00", end="2024-01-02", interval="1D")

    def test_market_from_to_accepts_datetime(self) -> None:
        assert (
            _validate_ssi_from_to("2024/01/02 09:00:00", "from_date")
            == "2024/01/02 09:00:00"
        )
        assert _validate_ssi_from_to("2024/01/02", "from_date") == "2024/01/02"


class TestW4LazyAuthFallbackModules:
    def test_company_init_without_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _no_ssi_keys(monkeypatch)
        c = SSICompany("ACB")
        assert c.overview().empty

    def test_financial_init_without_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _no_ssi_keys(monkeypatch)
        f = SSIFinancial("ACB")
        assert f.balance_sheet().empty

    def test_news_init_without_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _no_ssi_keys(monkeypatch)
        n = SSINews()
        assert n.latest().empty


class TestW2FallbackMaps:
    def test_one_way_ssi_maps(self) -> None:
        expected = {"DNSE": ["KBS", "VCI"], "SSI": ["KBS", "VCI"]}
        assert Trading.FALLBACK_MAP == expected
        assert Company.FALLBACK_MAP == expected
        assert Quote.FALLBACK_MAP == expected
        assert Listing.FALLBACK_MAP == expected

    def test_no_reverse_fallback_into_ssi(self) -> None:
        for cls in (Quote, Listing, Trading, Company):
            for targets in cls.FALLBACK_MAP.values():
                assert "SSI" not in targets


class TestW3UnsupportedMethodFallback:
    def test_unsupported_method_error_falls_back(self) -> None:
        comp = Company(
            symbol="ACB", source="SSI", api_key="k", api_secret="s", show_log=False
        )

        class _Primary:
            def overview(self, **kwargs: Any) -> pd.DataFrame:
                raise UnsupportedMethodError(
                    provider="ssi", method="overview"
                )

        expected = pd.DataFrame([{"symbol": "ACB"}])

        class _Fallback:
            def overview(self, **kwargs: Any) -> pd.DataFrame:
                return expected

        comp.data_source = _Primary()
        comp._load_fallback_provider = lambda source: _Fallback()  # type: ignore[method-assign]
        assert comp._call_with_fallback("overview") is expected


class TestPriceBoardTradingDate:
    def _service(self) -> Any:
        class _Svc:
            def __init__(self) -> None:
                self.summary_calls: List[Dict[str, Any]] = []

            def get_master_data(
                self, from_date: str, to_date: str
            ) -> pd.DataFrame:
                return pd.DataFrame(
                    [
                        {
                            "symbol": "ACB",
                            "board": "HOSE",
                            "trading_date": from_date,
                            "ceiling": 11.0,
                            "floor": 9.0,
                            "ref_price": 10.0,
                        }
                    ]
                )

            def get_securities_summary(
                self, symbol: str, from_date: str, to_date: str
            ) -> pd.DataFrame:
                self.summary_calls.append(
                    {"symbol": symbol, "from_date": from_date, "to_date": to_date}
                )
                return pd.DataFrame(
                    [
                        {
                            "symbol": symbol,
                            "trading_date": from_date,
                            "open": 10.0,
                            "high": 11.0,
                            "low": 9.0,
                            "close": 10.5,
                            "average": 10.2,
                            "price_change": 0.5,
                            "price_change_percent": 5.0,
                            "total_match": 100,
                            "total_match_value": 1050.0,
                            "total_foreign_buy": 10,
                            "total_foreign_sell": 5,
                        }
                    ]
                )

        return _Svc()

    def test_trading_date_forwarded(self) -> None:
        svc = self._service()
        t = SSITrading("ACB", api_key="k", api_secret="s", _service=svc)  # type: ignore[arg-type]
        df = t.price_board(["ACB"], trading_date="2024-01-02")
        assert svc.summary_calls[0]["from_date"] == "2024/01/02"
        assert df.iloc[0]["symbol"] == "ACB"
        assert df.attrs["source_used"] == "SSI"

    def test_order_preserved_concurrent(self) -> None:
        svc = self._service()
        t = SSITrading("ACB", api_key="k", api_secret="s", _service=svc)  # type: ignore[arg-type]
        df = t.price_board(
            ["ACB", "VNM"], trading_date="2024/01/02", max_concurrency=2
        )
        assert list(df["symbol"]) == ["ACB", "VNM"]
