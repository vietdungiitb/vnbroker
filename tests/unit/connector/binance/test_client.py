"""ISSUE-04: Binance connector unit tests (mocked HTTP)."""

from __future__ import annotations

import pytest

from vnbroker import Vnbroker
from vnbroker.connector.binance import (
    BinanceClient,
    normalize_interval,
    normalize_symbol,
)


def _kline(open_time_ms: int, price: str = "67000.0", volume: str = "12.5"):
    return [
        open_time_ms, price, "67100.0", "66900.0", "67050.0", volume,
        open_time_ms + 86_399_999, "800000.0", 100, "6.0", "400000.0", "0",
    ]


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _mock_get(payload):
    def _get(url, params=None, timeout=None):
        _get.captured = {"url": url, "params": params}
        return _FakeResponse(payload)

    return _get


def test_normalize_symbol():
    assert normalize_symbol("BTC") == "BTCUSDT"
    assert normalize_symbol("btc") == "BTCUSDT"
    assert normalize_symbol("BTCUSDT") == "BTCUSDT"
    assert normalize_symbol("BTC/USDT") == "BTCUSDT"
    with pytest.raises(ValueError):
        normalize_symbol("")


def test_normalize_interval():
    assert normalize_interval("1D") == "1d"
    assert normalize_interval("1H") == "1h"
    with pytest.raises(ValueError):
        normalize_interval("2Y")


def test_history_schema_and_attrs(monkeypatch):
    monkeypatch.setattr(
        "vnbroker.connector.binance.client.requests.get",
        _mock_get([_kline(1_704_067_200_000), _kline(1_704_153_600_000)]),
    )
    client = BinanceClient(symbol="BTC")
    df = client.history(start="2024-01-01", end="2024-01-02", interval="1D")

    assert list(df.columns) == ["time", "open", "high", "low", "close", "volume"]
    assert len(df) == 2
    assert df.iloc[0]["close"] == pytest.approx(67050.0)
    assert df.attrs["symbol"] == "BTCUSDT"
    assert df.attrs["source"] == "BINANCE"
    assert df.attrs["price_unit"] == "USDT"


def test_history_empty_response(monkeypatch):
    monkeypatch.setattr(
        "vnbroker.connector.binance.client.requests.get", _mock_get([])
    )
    df = BinanceClient(symbol="ETH").history(interval="1D")
    assert len(df) == 0
    assert df.attrs["price_unit"] == "USDT"


def test_intraday_defaults_to_1m(monkeypatch):
    fake = _mock_get([_kline(1_704_067_200_000)])
    monkeypatch.setattr("vnbroker.connector.binance.client.requests.get", fake)
    df = BinanceClient(symbol="BTC").intraday(limit=10)
    assert fake.captured["params"]["interval"] == "1m"
    assert fake.captured["params"]["limit"] == 10
    assert df.attrs["price_unit"] == "USDT"


def test_vnbroker_crypto_factory():
    vn = Vnbroker(show_log=False)
    client = vn.crypto("BTC")
    assert isinstance(client, BinanceClient)
    assert client.symbol == "BTCUSDT"
    with pytest.raises(ValueError, match="not supported"):
        vn.crypto("BTC", source="YAHOO")
