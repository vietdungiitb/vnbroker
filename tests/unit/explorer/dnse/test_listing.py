from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from vnstock.explorer.dnse.listing import DNSEListing


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
        with patch("vnstock.connector.dnse.client.DNSEClient") as mock_client_cls:
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
