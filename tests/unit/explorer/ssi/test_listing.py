"""Unit tests for SSIListing (mock service, no network)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
import pytest

from vnbroker.explorer.ssi.listing import SSIListing

_INFO_COLUMNS = [
    "symbol", "board", "index", "symbol_name_vi", "symbol_name_en",
    "lot_size", "listed_shares", "icb_code", "icb_name",
]


def _info(symbol: str, board: str, vi: str, icb: str = "8600", icb_name: str = "Banks") -> Dict[str, Any]:
    return {
        "symbol": symbol,
        "board": board,
        "index": "",
        "symbol_name_vi": vi,
        "symbol_name_en": vi,
        "lot_size": 100,
        "listed_shares": 1000000,
        "icb_code": icb,
        "icb_name": icb_name,
    }


class _FakeMarket:
    """SSIMarketService double for securities info."""

    def __init__(self, by_board: Optional[Dict[str, List[Dict[str, Any]]]] = None) -> None:
        self.by_board = by_board or {}
        self.calls: List[Dict[str, Any]] = []

    def get_securities_info(
        self,
        symbol: Optional[str] = None,
        board: Optional[str] = None,
        index: Optional[str] = None,
        raw: bool = False,
    ) -> pd.DataFrame:
        self.calls.append({"symbol": symbol, "board": board, "index": index})
        if index:
            rows = [r for rows in self.by_board.values() for r in rows if r["symbol"] in ("ACB", "VNM")]
            return pd.DataFrame(rows, columns=_INFO_COLUMNS)
        rows = self.by_board.get(board or "", [])
        return pd.DataFrame(rows, columns=_INFO_COLUMNS)


def _listing(by_board: Optional[Dict[str, List[Dict[str, Any]]]] = None, **kwargs: Any) -> tuple[SSIListing, _FakeMarket]:
    fake = _FakeMarket(by_board)
    lst = SSIListing(api_key="test-ssi-key", api_secret="test-ssi-secret", _service=fake, **kwargs)  # type: ignore[arg-type]
    return lst, fake


_BOARDS = {
    "HOSE": [_info("ACB", "HOSE", "Ngan hang ACB"), _info("VNM", "HOSE", "Vinamilk", "3500", "Food")],
    "HNX": [_info("SHB", "HNX", "SHB"), _info("ACB", "HNX", "Ngan hang ACB")],
    "UPCOM": [],
}


class TestSSIListingInit:
    """Credential tests."""

    def test_raises_without_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("VNBROKER_BROKER_SSI_API_KEY", raising=False)
        monkeypatch.delenv("VNBROKER_BROKER_SSI_API_SECRET", raising=False)
        with pytest.raises(ValueError, match="SSI cần api_key và api_secret"):
            SSIListing()


class TestSSIListingMethods:
    """AC-L1.1-L1.4."""

    def test_all_symbols_loops_boards_and_dedupes(self) -> None:
        lst, fake = _listing(_BOARDS)
        df = lst.all_symbols()
        assert [c["board"] for c in fake.calls] == ["HOSE", "HNX", "UPCOM"]
        assert list(df.columns) == ["symbol", "organ_name"]
        assert sorted(df["symbol"].tolist()) == ["ACB", "SHB", "VNM"]

    def test_symbols_by_exchange_single_request(self) -> None:
        lst, fake = _listing(_BOARDS)
        df = lst.symbols_by_exchange(exchange="HOSE")
        assert len(fake.calls) == 1
        assert list(df.columns) == ["symbol", "organ_name"]
        assert len(df) == 2

    def test_symbols_by_group_series(self) -> None:
        lst, _ = _listing(_BOARDS)
        out = lst.symbols_by_group("VN30")
        assert isinstance(out, pd.Series)
        assert out.name == "symbol"

    def test_listing_cache_single_hit(self) -> None:
        lst, fake = _listing(_BOARDS)
        lst.all_symbols()
        lst.all_symbols()
        assert len(fake.calls) == 3

    def test_unsupported_groups_raise(self, ssi_keys: tuple[str, str]) -> None:
        lst, _ = _listing(_BOARDS)
        for method in ("all_covered_warrant", "all_bonds", "all_future_indices", "all_government_bonds"):
            with pytest.raises(NotImplementedError):
                getattr(lst, method)()

    def test_all_symbols_empty(self) -> None:
        lst, _ = _listing({})
        df = lst.all_symbols()
        assert df.empty
        assert list(df.columns) == ["symbol", "organ_name"]

    def test_all_symbols_include_derivatives(self) -> None:
        boards = dict(_BOARDS)
        boards["DERIVATIVES"] = [_info("VN30F1M", "DERIVATIVES", "VN30F1M")]
        lst, fake = _listing(boards)
        df = lst.all_symbols(include_derivatives=True)
        assert [c["board"] for c in fake.calls] == ["HOSE", "HNX", "UPCOM", "DERIVATIVES"]
        assert "VN30F1M" in df["symbol"].tolist()

    def test_symbols_by_industries(self) -> None:
        lst, _ = _listing(_BOARDS)
        df = lst.symbols_by_industries()
        assert list(df.columns) == ["symbol", "organ_name", "icb_code", "icb_name"]
        assert len(df) == 3  # ACB deduped across HOSE/HNX

    def test_industries_icb(self) -> None:
        lst, _ = _listing(_BOARDS)
        df = lst.industries_icb()
        assert list(df.columns) == ["icb_code", "icb_name"]
        assert len(df) == 2

    def test_lazy_market_construction(self, ssi_keys: tuple[str, str]) -> None:
        from unittest.mock import patch

        from vnbroker.explorer.ssi.listing import SSIListing

        fake = _FakeMarket(_BOARDS)
        with patch(
            "vnbroker.explorer.ssi.listing.get_shared_session"
        ) as mock_shared:
            mock_shared.return_value.market_service.return_value = fake
            lst = SSIListing(api_key="test-ssi-key", api_secret="test-ssi-secret")
            # _market is lazy — only constructed on first network call
            assert lst._service is None
            df = lst.all_symbols()
        assert len(df) == 3
        mock_shared.assert_called_once()
