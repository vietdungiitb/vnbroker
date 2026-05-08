from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from vnbroker.explorer.dnse.listing import DNSEListing


_SAMPLE_INSTRUMENTS_BODY = {
    "instruments": [
        {"symbol": "VNM", "marketId": "HOSE", "name": "CTCP Sua Viet Nam", "type": "STOCK", "securityGroupId": "VN30"},
        {"symbol": "HPG", "marketId": "HOSE", "name": "CTCP Tap doan Hoa Phat", "type": "STOCK", "securityGroupId": "VN30"},
        {"symbol": "VNINDEX", "marketId": "HOSE", "name": "VN Index", "type": "INDEX"},
    ]
}

_SAMPLE_INDEX_BODY = {
    "indices": [
        {"symbol": "VNINDEX", "marketId": "HOSE", "name": "VN Index", "type": "INDEX"},
    ]
}


def _make_listing():
    with patch.dict(os.environ, {"DNSE_API_KEY": "test-key", "DNSE_API_SECRET": "test-secret"}):
        with patch("vnbroker.connector.dnse.client.DNSEClient") as mock_client_cls:
            mock_client = MagicMock()

            def side_effect(*args, **kwargs):
                if kwargs.get("index_name") == "all":
                    return 200, _SAMPLE_INDEX_BODY
                if kwargs.get("security_group_id") == "VN30":
                    return 200, {
                        "instruments": [
                            row for row in _SAMPLE_INSTRUMENTS_BODY["instruments"]
                            if row.get("securityGroupId", "").upper() == "VN30"
                        ]
                    }
                if kwargs.get("market_id"):
                    return 200, {
                        "instruments": [
                            row for row in _SAMPLE_INSTRUMENTS_BODY["instruments"]
                            if row.get("marketId", "").upper() == str(kwargs["market_id"]).upper()
                        ]
                    }
                return 200, _SAMPLE_INSTRUMENTS_BODY

            mock_client._market.get_instruments.side_effect = side_effect
            mock_client_cls.return_value = mock_client
            return DNSEListing(), mock_client


class TestDNSEListing:
    def test_raises_without_credentials(self, monkeypatch):
        monkeypatch.delenv("DNSE_API_KEY", raising=False)
        monkeypatch.delenv("DNSE_API_SECRET", raising=False)
        with pytest.raises(ValueError):
            DNSEListing()

    def test_all_symbols_returns_dataframe(self):
        listing, mock_client = _make_listing()
        df = listing.all_symbols()

        assert isinstance(df, pd.DataFrame)
        assert "symbol" in df.columns
        assert "exchange" in df.columns
        assert mock_client._market.get_instruments.called

    def test_symbols_by_exchange_and_group(self):
        listing, _ = _make_listing()

        exchange_df = listing.symbols_by_exchange("hose")
        group_df = listing.symbols_by_group("VN30")

        assert not exchange_df.empty
        assert not group_df.empty
        assert exchange_df["exchange"].str.upper().eq("HOSE").all()
        assert group_df["security_group"].str.upper().eq("VN30").all()

    def test_indices_and_fallbacks(self):
        listing, _ = _make_listing()

        indices_df = listing.indices()
        future_df = listing.all_future_indices()
        covered_warrant_df = listing.all_covered_warrant()
        industries_df = listing.symbols_by_industries()

        assert not indices_df.empty
        assert not future_df.empty
        assert covered_warrant_df.empty
        assert not industries_df.empty

    def test_fetch_instruments_exception_returns_empty(self, monkeypatch):
        """_fetch_instruments trả empty DataFrame khi API raise exception."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            with patch("vnbroker.connector.dnse.client.DNSEClient") as mock_cls:
                mc = MagicMock()
                mc._market.get_instruments.side_effect = Exception("network error")
                mock_cls.return_value = mc
                listing = DNSEListing()
                df = listing.all_symbols()
        assert df.empty

    def test_fetch_instruments_body_none_returns_empty(self):
        """_fetch_instruments trả empty DataFrame khi body là None."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            with patch("vnbroker.connector.dnse.client.DNSEClient") as mock_cls:
                mc = MagicMock()
                mc._market.get_instruments.return_value = (200, None)
                mock_cls.return_value = mc
                listing = DNSEListing()
                df = listing.all_symbols()
        assert df.empty

    def test_fetch_instruments_body_dict_fallback_no_list_key(self):
        """_fetch_instruments xử lý body dict không có list key → dùng [body]."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            with patch("vnbroker.connector.dnse.client.DNSEClient") as mock_cls:
                mc = MagicMock()
                mc._market.get_instruments.return_value = (
                    200,
                    {"symbol": "VNM", "marketId": "HOSE"},
                )
                mock_cls.return_value = mc
                listing = DNSEListing()
                df = listing.all_symbols()
        assert len(df) == 1
        assert "symbol" in df.columns

    def test_fetch_instruments_body_list_directly(self):
        """_fetch_instruments xử lý body trả về trực tiếp là list."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            with patch("vnbroker.connector.dnse.client.DNSEClient") as mock_cls:
                mc = MagicMock()
                mc._market.get_instruments.return_value = (
                    200,
                    [{"symbol": "HPG", "marketId": "HOSE"}],
                )
                mock_cls.return_value = mc
                listing = DNSEListing()
                df = listing.all_symbols()
        assert len(df) == 1

    def test_all_symbols_show_log_calls_logger(self):
        """all_symbols không raise và trả kết quả hợp lệ khi show_log=True."""
        listing, _ = _make_listing()
        df = listing.all_symbols(show_log=True)
        assert not df.empty

    def test_symbols_by_exchange_all(self):
        """symbols_by_exchange('ALL') không lọc market_id."""
        listing, mock_client = _make_listing()
        df = listing.symbols_by_exchange("ALL")
        assert not df.empty
        # Đảm bảo gọi với market_id=None
        calls = mock_client._market.get_instruments.call_args_list
        assert any(call.kwargs.get("market_id") is None for call in calls)

    def test_symbols_by_exchange_show_log(self):
        """symbols_by_exchange log khi show_log=True."""
        listing, _ = _make_listing()
        df = listing.symbols_by_exchange("HOSE", show_log=True)
        assert not df.empty

    def test_symbols_by_group_show_log(self):
        """symbols_by_group log khi show_log=True."""
        listing, _ = _make_listing()
        df = listing.symbols_by_group("VN30", show_log=True)
        assert not df.empty

    def test_indices_exception_fallback_with_type_column(self):
        """indices() khi exception xảy ra → fallback lọc type==INDEX."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            with patch("vnbroker.connector.dnse.client.DNSEClient") as mock_cls:
                mc = MagicMock()
                call_count = 0

                def side_effect(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if kwargs.get("index_name") == "all":
                        raise Exception("indices endpoint not found")
                    return 200, {
                        "instruments": [
                            {"symbol": "VNINDEX", "type": "INDEX", "marketId": "HOSE"},
                            {"symbol": "VNM", "type": "STOCK", "marketId": "HOSE"},
                        ]
                    }

                mc._market.get_instruments.side_effect = side_effect
                mock_cls.return_value = mc
                listing = DNSEListing()
                df = listing.indices()

        assert not df.empty
        assert (df["type"] == "INDEX").all()

    def test_indices_body_none_returns_empty(self):
        """indices() trả empty khi body là None."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            with patch("vnbroker.connector.dnse.client.DNSEClient") as mock_cls:
                mc = MagicMock()
                mc._market.get_instruments.return_value = (200, None)
                mock_cls.return_value = mc
                listing = DNSEListing()
                df = listing.indices()
        assert df.empty

    def test_indices_body_list_directly(self):
        """indices() xử lý body là list trực tiếp."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            with patch("vnbroker.connector.dnse.client.DNSEClient") as mock_cls:
                mc = MagicMock()
                mc._market.get_instruments.return_value = (
                    200,
                    [{"symbol": "VNINDEX", "type": "INDEX"}],
                )
                mock_cls.return_value = mc
                listing = DNSEListing()
                df = listing.indices()
        assert len(df) == 1

    def test_industries_icb_returns_empty(self):
        listing, _ = _make_listing()
        df = listing.industries_icb()
        assert df.empty

    def test_all_bonds_and_government_bonds_return_empty(self):
        listing, _ = _make_listing()
        assert listing.all_bonds().empty
        assert listing.all_government_bonds().empty

    def test_show_log_via_instance_flag(self):
        """show_log=True trên instance kích hoạt log path."""
        with patch.dict(os.environ, {"DNSE_API_KEY": "k", "DNSE_API_SECRET": "s"}):
            with patch("vnbroker.connector.dnse.client.DNSEClient") as mock_cls:
                mc = MagicMock()
                mc._market.get_instruments.return_value = (200, _SAMPLE_INSTRUMENTS_BODY)
                mock_cls.return_value = mc
                listing = DNSEListing(show_log=True)
                listing.all_bonds()
                listing.all_covered_warrant()
                listing.industries_icb()
                listing.symbols_by_industries()
