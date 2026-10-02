"""Unit tests for SSIScreener (mock service, no network)."""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd
import pytest

from vnbroker.explorer.ssi.screener import SSIScreener


def _info(symbol: str, icb: str = "Banks", shares: int = 1000) -> Dict[str, Any]:
    return {
        "symbol": symbol,
        "board": "HOSE",
        "symbol_name_vi": symbol,
        "symbol_name_en": symbol,
        "lot_size": 100,
        "listed_shares": shares,
        "icb_code": "8300",
        "icb_name": icb,
    }


class _FakeMarket:
    def get_securities_info(
        self,
        symbol: Optional[str] = None,
        board: Optional[str] = None,
        index: Optional[str] = None,
    ) -> pd.DataFrame:
        rows = [_info("ACB", "Banks", 5000), _info("VNM", "Food", 2000)]
        if index:
            return pd.DataFrame(rows)
        if board and board != "HOSE":
            return pd.DataFrame(columns=list(rows[0].keys()))
        return pd.DataFrame(rows)

    def get_securities_summary(
        self, index: Optional[str] = None, **kwargs: Any
    ) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"symbol": "ACB", "total_match": 1000, "total_match_value": 1e7},
                {"symbol": "VNM", "total_match": 10, "total_match_value": 1e5},
            ]
        )


def _screener() -> SSIScreener:
    return SSIScreener(api_key="k", api_secret="s", _service=_FakeMarket())  # type: ignore[arg-type]


class TestSSIScreener:
    def test_default_universe_limit(self) -> None:
        df = _screener().stock(limit=1)
        assert len(df) == 1
        assert df.attrs["source_used"] == "SSI"

    def test_icb_filter(self) -> None:
        df = _screener().stock(params={"icb": "bank"})
        assert list(df["symbol"]) == ["ACB"]

    def test_min_listed_shares(self) -> None:
        df = _screener().stock(params={"min_listed_shares": 3000})
        assert list(df["symbol"]) == ["ACB"]

    def test_liquidity_filter_needs_index(self) -> None:
        with pytest.raises(ValueError, match="indexName"):
            _screener().stock(params={"min_total_match": 100})

    def test_liquidity_filter_with_index(self) -> None:
        df = _screener().stock(
            params={"indexName": "VN30", "min_total_match": 100}
        )
        assert list(df["symbol"]) == ["ACB"]

    def test_empty_universe(self) -> None:
        df = _screener().stock(params={"exchangeName": "HNX"})
        assert df.empty
