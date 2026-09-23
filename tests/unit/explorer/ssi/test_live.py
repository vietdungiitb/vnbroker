"""Unit tests for SSILive (fake stream, no network)."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import pandas as pd
import pytest

from vnbroker.broker.ssi.stream import MarketStatus, QuoteUpdate, TradeTick, _topics_msg
from vnbroker.explorer.ssi.live import SSILive


class _FakeStream:
    """Stream-manager double: replays queued messages then returns."""

    def __init__(self, messages: Optional[List[Any]] = None) -> None:
        self.messages = messages or []
        self.subscribed: List[str] = []
        self.connected = False
        self.disconnected = False
        self._on_data: Optional[Callable[[Any], Any]] = None

    @property
    def on_data(self) -> Any:
        return self._on_data

    @on_data.setter
    def on_data(self, callback: Any) -> None:
        self._on_data = callback

    def connect(self) -> None:
        self.connected = True

    def subscribe_symbol_trade(self, symbols: List[str]) -> None:
        self.subscribed += [f"trade.{s}" for s in symbols]

    def subscribe_symbol_quote(self, symbols: List[str]) -> None:
        self.subscribed += [f"quote.{s}" for s in symbols]

    def subscribe_symbol_market_status(self, symbols: List[str]) -> None:
        self.subscribed += [f"market.{s}" for s in symbols]

    def wait(self, timeout: Optional[float] = None) -> None:
        assert self._on_data is not None
        for msg in self.messages:
            self._on_data(msg)

    def disconnect(self) -> None:
        self.disconnected = True


def _tick(symbol: str = "ACB") -> TradeTick:
    return TradeTick(
        symbol=symbol,
        trading_time="2024/01/02 09:15:01",
        price=10.5,
        quantity=100,
        side="B",
        total_volume=1000,
    )


def _quote(symbol: str = "ACB") -> QuoteUpdate:
    return QuoteUpdate(
        symbol=symbol,
        trading_time="2024/01/02 09:15:01",
        bid_prices=[10.4, 10.3],
        bid_volumes=[50, 60],
        ask_prices=[10.6],
        ask_volumes=[70],
    )


def _live(messages: List[Any], **kwargs: Any) -> SSILive:
    return SSILive(
        "ACB",
        api_key="k",
        api_secret="s",
        _stream_factory=lambda: _FakeStream(messages),
        **kwargs,
    )


class TestSSILive:
    def test_init_requires_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("VNBROKER_BROKER_SSI_API_KEY", raising=False)
        monkeypatch.delenv("VNBROKER_BROKER_SSI_API_SECRET", raising=False)
        with pytest.raises(ValueError, match="api_key"):
            SSILive("ACB")

    def test_intraday_ticks_schema(self) -> None:
        df = _live([_tick(), _tick()]).intraday_ticks(timeout=1.0)
        assert list(df.columns) == ["time", "price", "volume", "side"]
        assert len(df) == 2
        assert df.attrs["source_used"] == "SSI"

    def test_intraday_ticks_ignores_other_symbols(self) -> None:
        df = _live([_tick("VNM")]).intraday_ticks(timeout=1.0)
        assert df.empty

    def test_intraday_bad_timeout(self) -> None:
        with pytest.raises(ValueError, match="timeout"):
            _live([]).intraday_ticks(timeout=0)

    def test_depth_snapshot_ladder(self) -> None:
        df = _live([_quote()]).depth_snapshot(timeout=1.0)
        assert list(df.columns) == ["side", "price", "volume"]
        assert df["side"].tolist() == ["BID", "BID", "ASK"]
        assert df["price"].tolist() == [10.4, 10.3, 10.6]

    def test_depth_empty_without_messages(self) -> None:
        df = _live([]).depth_snapshot(timeout=1.0)
        assert df.empty

    def test_session_flags_schema(self) -> None:
        msg = MarketStatus(market="HOSE", status="LO", trading_date="2024/01/02")
        df = _live([msg]).session_flags(["HOSE"], timeout=1.0)
        assert list(df.columns) == ["market", "status", "trading_date"]
        assert df.iloc[0]["status"] == "LO"

    def test_session_flags_empty_symbols(self) -> None:
        with pytest.raises(ValueError, match="symbols_list"):
            _live([]).session_flags([], timeout=1.0)

    def test_market_topic_format(self) -> None:
        msg = _topics_msg("subscribe", "DATA", "market", ["ACB"])
        assert msg["topics"] == ["market.ACB"]
        assert msg["method"] == "subscribe"

    def test_session_snapshot_from_master(self) -> None:
        master = pd.DataFrame(
            [
                {"board": "HOSE", "symbol": "ACB",
                 "trading_date": "2024/01/02", "ceiling": 11.0,
                 "floor": 9.0, "ref_price": 10.0},
                {"board": "HOSE", "symbol": "VNM",
                 "trading_date": "2024/01/02", "ceiling": 22.0,
                 "floor": 18.0, "ref_price": 20.0},
            ]
        )

        class _Svc:
            def get_master_data(
                self, from_date: Optional[str] = None, to_date: Optional[str] = None
            ) -> pd.DataFrame:
                assert from_date == "2024/01/02"
                return master

        live = SSILive("ACB", api_key="k", api_secret="s", _service=_Svc())
        df = live.session_snapshot(["ACB"], trading_date="2024-01-02")
        assert list(df.columns) == ["symbol", "board", "trading_date",
                                    "ceiling", "floor", "ref"]
        assert df.iloc[0]["ref"] == 10.0
