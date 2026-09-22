"""
S5: SSI market data — OHLC gom timeframe, index, securities, masterdata. Mocked.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

import pandas as pd
import pytest

from vnbroker.broker.exceptions import BrokerValidationError
from vnbroker.broker.security.credentials import SSICredentialConfig
from vnbroker.broker.session import BrokerSession
from vnbroker.broker.ssi._transport import SSIHttpClient
from vnbroker.broker.ssi.market import SSIMarketService

pytestmark = pytest.mark.ssi

OHLC_BAR = {
    "symbol": "SSI",
    "tradingDate": "2026/01/05",
    "open": 25000.0,
    "high": 25500.0,
    "low": 24900.0,
    "close": 25300.0,
    "volume": 1000000,
    "value": 25300000000.0,
}


class FakeResponse:
    def __init__(self, status_code: int, payload: Any = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers: Dict[str, str] = {}
        self.text = json.dumps(payload or {})

    def json(self) -> Any:
        return self._payload


class FakeSession:
    def __init__(self, script: List[Any]) -> None:
        self._script = list(script)
        self.headers: Dict[str, str] = {}
        self.calls: List[Dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        item = self._script.pop(0)
        assert isinstance(item, FakeResponse)
        return item

    def close(self) -> None:
        return None


def make_market(script: List[Any], monkeypatch: pytest.MonkeyPatch) -> tuple:
    fake = FakeSession(script)
    monkeypatch.setattr("vnbroker.broker.ssi._transport.requests.Session", lambda: fake)
    config = SSICredentialConfig.from_dict({"api_key": "K", "api_secret": "S"})
    session = BrokerSession(provider="SSI")
    session.set_token("T")
    transport = SSIHttpClient(base_url="https://api.ssi.com.vn", rate_limit_rps=0)
    return SSIMarketService(config, session, transport), fake


class TestOhlc:
    def test_history(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_market([FakeResponse(200, {"data": [OHLC_BAR]})], monkeypatch)
        df = svc.get_ohlc("ssi", "1d", "2026/01/01", "2026/01/31")
        assert isinstance(df, pd.DataFrame)
        assert df.iloc[0]["close"] == 25300.0
        assert df.iloc[0]["symbol"] == "SSI"
        assert str(df["volume"].dtype) == "Int64"
        params = fake.calls[0]["params"]
        assert params["timeFrame"] == "1d"
        assert params["from"] == "2026/01/01"

    def test_intraday_defaults_today(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_market([FakeResponse(200, {"data": []})], monkeypatch)
        df = svc.get_ohlc("SSI", "1m")
        assert isinstance(df, pd.DataFrame) and df.empty
        assert fake.calls[0]["params"]["from"] == fake.calls[0]["params"]["to"]

    def test_all_timeframes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_market([FakeResponse(200, {"data": []})] * 8, monkeypatch)
        for tf, wire in [
            ("1m", "1m"),
            ("3m", "3m"),
            ("5m", "5m"),
            ("15m", "15m"),
            ("1h", "1h"),
            ("1d", "1d"),
            ("1w", "1w"),
            ("1M", "1M"),
        ]:
            svc.get_ohlc("SSI", tf)
        assert [c["params"]["timeFrame"] for c in fake.calls] == [
            "1m",
            "3m",
            "5m",
            "15m",
            "1h",
            "1d",
            "1w",
            "1M",
        ]

    def test_bad_timeframe(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_market([], monkeypatch)
        with pytest.raises(BrokerValidationError) as exc:
            svc.get_ohlc("SSI", "2h")
        assert exc.value.code == "INVALID_TIMEFRAME"
        assert fake.calls == []

    def test_raw(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, _ = make_market([FakeResponse(200, {"data": [OHLC_BAR]})], monkeypatch)
        assert svc.get_ohlc("SSI", raw=True) == [OHLC_BAR]

    def test_download_not_implemented(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, _ = make_market([], monkeypatch)
        with pytest.raises(NotImplementedError):
            svc.download_ohlc("SSI")


class TestIndex:
    def test_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, _ = make_market(
            [
                FakeResponse(
                    200,
                    [{"index": "VNINDEX", "indexName": "VN Index", "board": "HOSE"}],
                )
            ],
            monkeypatch,
        )
        df = svc.get_indexes()
        assert df.iloc[0]["index_name"] == "VN Index"

    def test_by_board(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_market([FakeResponse(200, [])], monkeypatch)
        svc.get_indexes(board="hose")
        assert fake.calls[0]["params"] == {"board": "HOSE"}

    def test_bad_board(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_market([], monkeypatch)
        with pytest.raises(BrokerValidationError):
            svc.get_indexes(board="NYSE")
        assert fake.calls == []

    def test_index_summary(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_market(
            [
                FakeResponse(
                    200,
                    [
                        {
                            "tradingDate": "2026/01/05",
                            "indexValue": 1500.0,
                            "indexChange": 5.0,
                        }
                    ],
                )
            ],
            monkeypatch,
        )
        df = svc.get_index_summary("vnindex")
        assert df.iloc[0]["index_value"] == 1500.0
        assert fake.calls[0]["params"] == {"index": "VNINDEX"}

    def test_summary_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, _ = make_market([FakeResponse(200, [])], monkeypatch)
        df = svc.get_index_summary("VNINDEX")
        assert isinstance(df, pd.DataFrame) and df.empty

    def test_board_summary_historical(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_market([FakeResponse(200, [])], monkeypatch)
        svc.get_board_summary("HOSE", trading_date="2026/01/05")
        assert fake.calls[0]["params"] == {
            "board": "HOSE",
            "tradingDate": "2026/01/05",
        }


class TestSecurities:
    INFO = {
        "symbol": "SSI",
        "board": "HOSE",
        "index": "VN30",
        "symbolNameVi": "SSI",
        "symbolNameEn": "SSI Securities",
        "lotSize": 100,
        "listedShare": 1000000,
        "icbCode": "8000",
        "icbName": "Financials",
        "cwUnderlyingSymbol": "",
        "cwExercisePrice": 0.0,
    }

    def test_info_by_symbol(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_market([FakeResponse(200, [self.INFO])], monkeypatch)
        df = svc.get_securities_info(symbol="ssi")
        assert df.iloc[0]["lot_size"] == 100
        assert df.iloc[0]["icb_name"] == "Financials"
        assert fake.calls[0]["params"] == {"symbol": "SSI"}

    def test_info_no_filter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_market([], monkeypatch)
        with pytest.raises(BrokerValidationError) as exc:
            svc.get_securities_info()
        assert exc.value.code == "MISSING_FILTER"
        assert fake.calls == []

    def test_summary(self, monkeypatch: pytest.MonkeyPatch) -> None:
        bar = dict(
            OHLC_BAR,
            average=25100.0,
            priceChange=300.0,
            priceChangePercentage=1.2,
            totalMatch=500,
            totalMatchValue=1e9,
        )
        svc, fake = make_market([FakeResponse(200, {"data": [bar]})], monkeypatch)
        df = svc.get_securities_summary(
            symbol="SSI", from_date="2026/01/01", to_date="2026/01/31"
        )
        assert df.iloc[0]["average"] == 25100.0
        assert df.iloc[0]["price_change_percent"] == 1.2
        assert fake.calls[0]["params"]["symbol"] == "SSI"

    def test_summary_needs_filter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, fake = make_market([], monkeypatch)
        with pytest.raises(BrokerValidationError):
            svc.get_securities_summary()
        assert fake.calls == []

    def test_master_pagination(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rec = {
            "board": "HOSE",
            "symbol": "SSI",
            "tradingDate": "2026/01/05",
            "ceiling": 27000.0,
            "floor": 23000.0,
            "refPrice": 25000.0,
        }
        svc, fake = make_market(
            [
                FakeResponse(200, {"data": [rec], "pagesCount": 3}),
                FakeResponse(200, {"data": [rec], "pagesCount": 3}),
                FakeResponse(200, {"data": [rec], "pagesCount": 3}),
            ],
            monkeypatch,
        )
        df = svc.get_master_data(from_date="2026/01/05", to_date="2026/01/05")
        assert len(df) == 3
        assert df.iloc[0]["ref_price"] == 25000.0
        assert fake.calls[0]["params"]["From"] == "2026/01/05"  # key HOA
        assert [c["params"]["pageIndex"] for c in fake.calls] == [1, 2, 3]

    def test_master_raw(self, monkeypatch: pytest.MonkeyPatch) -> None:
        svc, _ = make_market(
            [FakeResponse(200, {"data": [], "pagesCount": 1})], monkeypatch
        )
        assert svc.get_master_data(raw=True) == []
