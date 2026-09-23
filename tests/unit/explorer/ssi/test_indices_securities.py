"""Unit tests for SSIIndices / SSISecurities (mock service, no network)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from vnbroker.explorer.ssi.indices import SSIIndices
from vnbroker.explorer.ssi.securities import SSISecurities


def _info(symbol: str, board: str = "HOSE") -> Dict[str, Any]:
    return {
        "symbol": symbol,
        "board": board,
        "index": "VN30",
        "symbol_name_vi": symbol,
        "symbol_name_en": symbol,
        "lot_size": 100,
        "listed_shares": 1000,
        "icb_code": "8300",
        "icb_name": "Banks",
        "maturity_date": "",
        "first_trading_date": "2020/01/01",
        "last_trading_date": "",
        "cw_underlying_symbol": "",
        "cw_exercise_price": 0.0,
        "cw_execution_ratio": "",
        "open_interest": 0,
        "settlement_price": 0.0,
        "i_index": 0.0,
        "i_nav": 0.0,
    }


def _summary_row(symbol: str, day: str = "2024/01/02") -> Dict[str, Any]:
    return {
        "symbol": symbol,
        "trading_date": day,
        "open": 10.0,
        "high": 11.0,
        "low": 9.0,
        "close": 10.5,
        "average": 10.2,
        "price_change": 0.5,
        "price_change_percent": 5.0,
        "total_match": 100,
        "total_match_value": 1050.0,
        "total_buy": 60,
        "total_trade_buy": 6,
        "total_sell": 40,
        "total_trade_sell": 4,
        "total_foreign_buy": 10,
        "total_foreign_buy_value": 105.0,
        "total_foreign_sell": 5,
        "total_foreign_sell_value": 52.0,
        "remain_foreign_room": 900,
        "total_foreign_room": 1000,
        "total_deal": 0,
        "total_deal_value": 0.0,
        "open_interest": 0,
        "settlement_price": 0.0,
    }


class _FakeMarket:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def get_indexes(self, board: Optional[str] = None) -> pd.DataFrame:
        self.calls.append({"method": "get_indexes", "board": board})
        return pd.DataFrame(
            [{"index": "VN30", "index_name": "VN30 Index", "board": board or "HOSE"}]
        )

    def get_securities_info(
        self,
        symbol: Optional[str] = None,
        board: Optional[str] = None,
        index: Optional[str] = None,
    ) -> pd.DataFrame:
        self.calls.append({"method": "get_securities_info", "index": index})
        return pd.DataFrame([_info("ACB"), _info("VNM")])

    def get_index_summary(
        self, index: str, trading_date: Optional[str] = None
    ) -> pd.DataFrame:
        self.calls.append({"method": "get_index_summary", "trading_date": trading_date})
        return pd.DataFrame([{"trading_date": trading_date or "2024/01/02",
                              "index_value": 1000.0}])

    def get_board_summary(
        self, board: str, trading_date: Optional[str] = None
    ) -> pd.DataFrame:
        self.calls.append({"method": "get_board_summary", "board": board})
        return pd.DataFrame([{"trading_date": trading_date or "2024/01/02",
                              "index_value": 1000.0}])

    def get_securities_summary(
        self,
        symbol: Optional[str] = None,
        index: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> pd.DataFrame:
        self.calls.append(
            {"method": "get_securities_summary", "index": index,
             "from_date": from_date, "to_date": to_date}
        )
        return pd.DataFrame([_summary_row("ACB", to_date or "2024/01/02")])

    def get_master_data(
        self, from_date: Optional[str] = None, to_date: Optional[str] = None
    ) -> pd.DataFrame:
        self.calls.append({"method": "get_master_data"})
        return pd.DataFrame(
            [{"board": "HOSE", "symbol": "ACB", "trading_date": to_date or "2024/01/02",
              "ceiling": 11.0, "floor": 9.0, "ref_price": 10.0}]
        )


class TestSSIIndices:
    def test_index_list(self) -> None:
        idx = SSIIndices(api_key="k", api_secret="s", _service=_FakeMarket())  # type: ignore[arg-type]
        df = idx.index_list()
        assert list(df.columns) == ["index", "index_name", "board"]
        assert df.attrs["source_used"] == "SSI"

    def test_index_members_series(self) -> None:
        idx = SSIIndices(api_key="k", api_secret="s", _service=_FakeMarket())  # type: ignore[arg-type]
        s = idx.index_members("VN30")
        assert s.name == "symbol"
        assert list(s) == ["ACB", "VNM"]

    def test_index_summary_by_index(self) -> None:
        idx = SSIIndices(api_key="k", api_secret="s", _service=_FakeMarket())  # type: ignore[arg-type]
        df = idx.index_summary(index="VN30", trading_date="2024-01-02")
        assert df.iloc[0]["trading_date"] == "2024/01/02"

    def test_index_summary_needs_filter(self) -> None:
        idx = SSIIndices(api_key="k", api_secret="s", _service=_FakeMarket())  # type: ignore[arg-type]
        try:
            idx.index_summary()
        except ValueError:
            return
        raise AssertionError("expected ValueError")

    def test_index_history_sorted_attrs(self) -> None:
        idx = SSIIndices(api_key="k", api_secret="s", _service=_FakeMarket())  # type: ignore[arg-type]
        df = idx.index_history("VN30", start="2024-01-01", end="2024-01-02")
        assert df.attrs["index"] == "VN30"
        assert df.attrs["source_used"] == "SSI"


class TestSSISecurities:
    def test_summary_symbol(self) -> None:
        sec = SSISecurities(api_key="k", api_secret="s", _service=_FakeMarket())  # type: ignore[arg-type]
        df = sec.summary(symbol="ACB", start="2024-01-01", end="2024-01-02")
        assert "total_foreign_buy" in df.columns
        assert df.attrs["source_used"] == "SSI"

    def test_master_latest(self) -> None:
        sec = SSISecurities(api_key="k", api_secret="s", _service=_FakeMarket())  # type: ignore[arg-type]
        df = sec.master()
        assert list(df.columns)[:3] == ["board", "symbol", "trading_date"]

    def test_foreign_room_subset(self) -> None:
        sec = SSISecurities(api_key="k", api_secret="s", _service=_FakeMarket())  # type: ignore[arg-type]
        df = sec.foreign_room(symbol="ACB")
        assert "remain_foreign_room" in df.columns
        assert "open" not in df.columns
