"""Unit tests for SSITrading.price_board (mock service, no network)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd
import pytest

from vnbroker.explorer.ssi.trading import SSITrading

EXPECTED_COLUMNS = [
    "symbol", "time", "exchange",
    "ceiling_price", "floor_price", "reference_price",
    "open_price", "high_price", "low_price", "close_price",
    "average_price", "volume_accumulated", "total_value",
    "price_change", "percent_change",
    "foreign_buy_volume", "foreign_sell_volume",
]

_SUMMARY_COLUMNS = [
    "symbol", "trading_date", "open", "high", "low", "close", "average",
    "price_change", "price_change_percent", "total_match", "total_match_value",
    "total_buy", "total_trade_buy", "total_sell", "total_trade_sell",
    "total_foreign_buy", "total_foreign_buy_value", "total_foreign_sell",
    "total_foreign_sell_value", "remain_foreign_room", "total_foreign_room",
    "total_deal", "total_deal_value", "open_interest", "settlement_price",
]


def _summary(symbol: str) -> Dict[str, Any]:
    row: Dict[str, Any] = {c: 0 for c in _SUMMARY_COLUMNS}
    row.update(
        {
            "symbol": symbol,
            "trading_date": "2024-01-31",
            "open": 25.0, "high": 25.5, "low": 24.8, "close": 25.2,
            "average": 25.1, "price_change": 0.2, "price_change_percent": 0.8,
            "total_match": 1000, "total_match_value": 25200.0,
            "total_foreign_buy": 100, "total_foreign_sell": 50,
        }
    )
    return row


class _FakeMarket:
    """SSIMarketService double for summary + master data."""

    def __init__(self, symbols: List[str]) -> None:
        self._symbols = symbols
        self.summary_calls: List[str] = []
        self.master_calls = 0

    def get_securities_summary(
        self,
        symbol: Optional[str] = None,
        index: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        raw: bool = False,
    ) -> pd.DataFrame:
        self.summary_calls.append(str(symbol))
        if symbol in self._symbols:
            return pd.DataFrame([_summary(symbol)], columns=_SUMMARY_COLUMNS)
        return pd.DataFrame(columns=_SUMMARY_COLUMNS)

    def get_master_data(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        raw: bool = False,
    ) -> pd.DataFrame:
        self.master_calls += 1
        return pd.DataFrame(
            [
                {"board": "HOSE", "symbol": s, "trading_date": "2024-01-31",
                 "ceiling": 27.0, "floor": 23.5, "ref_price": 25.0}
                for s in self._symbols
            ],
            columns=["board", "symbol", "trading_date", "ceiling", "floor", "ref_price"],
        )


def _trading(symbols: List[str], **kwargs: Any) -> tuple[SSITrading, _FakeMarket]:
    fake = _FakeMarket(symbols)
    t = SSITrading("ACB", api_key="test-ssi-key", api_secret="test-ssi-secret", _service=fake, **kwargs)  # type: ignore[arg-type]
    return t, fake


class TestSSITradingInit:
    """Credential tests."""

    def test_raises_without_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("VNBROKER_BROKER_SSI_API_KEY", raising=False)
        monkeypatch.delenv("VNBROKER_BROKER_SSI_API_SECRET", raising=False)
        with pytest.raises(ValueError, match="SSI cần api_key và api_secret"):
            SSITrading("ACB")

    def test_empty_symbols_raise(self, ssi_keys: tuple[str, str]) -> None:
        t, _ = _trading(["ACB"])
        with pytest.raises(ValueError, match="symbols_list"):
            t.price_board([])


class TestSSITradingPriceBoard:
    """AC-T1.1-T1.3."""

    def test_schema_17_columns(self) -> None:
        t, _ = _trading(["ACB", "VNM", "HPG"])
        df = t.price_board(["ACB", "VNM", "HPG"])
        assert len(df) == 3
        assert list(df.columns) == EXPECTED_COLUMNS
        row = df.iloc[0]
        assert row["symbol"] == "ACB"
        assert row["ceiling_price"] == 27.0
        assert row["floor_price"] == 23.5
        assert row["reference_price"] == 25.0
        assert row["exchange"] == "HOSE"
        assert df.attrs["source_used"] == "SSI"

    def test_master_cached_across_calls(self) -> None:
        t, fake = _trading(["ACB", "VNM"])
        t.price_board(["ACB", "VNM"])
        t.price_board(["ACB"])
        assert fake.master_calls == 1
        assert fake.summary_calls == ["ACB", "VNM", "ACB"]

    def test_missing_master_row_nan(self) -> None:
        t, fake = _trading(["ACB"])
        df = t.price_board(["ACB", "XXX"])
        assert len(df) == 1
        assert df.iloc[0]["symbol"] == "ACB"

    def test_large_batch_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        symbols = [f"S{i:03d}" for i in range(25)]
        t, _ = _trading(symbols)
        with caplog.at_level(logging.WARNING, logger="vnbroker.explorer.ssi.trading"):
            t.price_board(symbols)
        assert any("KBS" in r.message for r in caplog.records)
