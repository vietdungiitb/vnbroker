from __future__ import annotations

from unittest.mock import MagicMock, patch

from vnbroker.common.client import Vnbroker
from vnbroker.api.quote import Quote as QuoteAdapter
from vnbroker.api.listing import Listing as ListingAdapter


def _mock_dnse_client() -> MagicMock:
    client = MagicMock()
    client._market = MagicMock()
    return client


def test_public_adapters_support_dnse(monkeypatch):
    monkeypatch.setenv("DNSE_API_KEY", "key")
    monkeypatch.setenv("DNSE_API_SECRET", "secret")

    with patch("vnbroker.connector.dnse.client.DNSEClient") as mock_cls:
        mock_cls.return_value = _mock_dnse_client()

        quote = QuoteAdapter(source="dnse", symbol="VNM", api_key="key", api_secret="secret")
        listing = ListingAdapter(source="dnse", api_key="key", api_secret="secret")

    assert type(quote.provider).__name__ == "DNSEQuote"
    assert type(listing.provider).__name__ == "DNSEListing"


def test_vnbroker_stock_supports_dnse(monkeypatch):
    monkeypatch.setenv("DNSE_API_KEY", "key")
    monkeypatch.setenv("DNSE_API_SECRET", "secret")

    with patch("vnbroker.connector.dnse.client.DNSEClient") as mock_cls:
        mock_cls.return_value = _mock_dnse_client()

        stock = Vnbroker(show_log=False).stock(
            "VNM",
            source="DNSE",
            api_key="key",
            api_secret="secret",
        )

    assert type(stock.quote.data_source).__name__ == "DNSEQuote"
    assert type(stock.listing.data_source).__name__ == "DNSEListing"
    assert stock.company is None
    assert stock.finance is None
